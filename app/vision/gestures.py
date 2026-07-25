"""
Jest ile tıklama — güvenilir, süre-tabanlı algılama.

Kısa göz kırpma yakalamak kare hızına ve kişiye çok bağımlıdır (21 fps'te
hızlı bir kırpma 1-2 karedir ve kolayca kaçar). Bunun yerine SÜREKLİ sinyal
ölçülür: jest eşiğin üstünde belirli bir süre TUTULUNCA tıklama tetiklenir.
Çok kareli doğrulama, kare hızından bağımsız (zaman tabanlı) ve kişiye uyum
için uyarlanabilir taban çizgisi kullanır.

Jestler (MediaPipe blendshape skorları, 0..1):
- long_blink: iki gözü ~0.4 sn kapalı tut (doğal kırpma daha kısadır)
- wink_left / wink_right: yalnız TEK gözü kapat — sinyal sol-sağ FARKI
  olduğundan, iki gözün BİRLİKTE kapandığı doğal bir kırpma bu eşiği
  aşmaz (bkz. GestureClick docstring — çakışma böyle önlenir). Kişinin
  DİNLENME halindeki doğal göz asimetrisi de brow gibi uyarlanabilir
  tabanla çıkarılır — aksi halde bu asimetri eşiği kalıcı aşıp imleci
  sürekli dondurabilirdi.
- brow: kaşları kaldır ve kısa süre tut
- mouth: ağzı aç ve kısa süre tut (konuşurken yanlış tetiklenebilir)
- smile: gülümse ve kısa süre tut

Üç bağımsız eylem yuvası vardır: sol tık, sağ tık, orta tık — her biri
yukarıdaki jestlerden birine (ya da 'off') bağlanır. Aynı jestin iki eyleme
birden atanması ÇAĞIRAN TARAF (AppController/UI) tarafından engellenir;
bu modül yalnız atanmış jesti izler.
"""

from __future__ import annotations

GESTURES = ("long_blink", "wink_left", "wink_right", "brow", "mouth", "smile", "off")

GESTURE_LABELS = {
    "long_blink": "Uzun göz kapama (iki göz, önerilen)",
    "wink_left": "Sol göz kırpma (tek göz)",
    "wink_right": "Sağ göz kırpma (tek göz)",
    "brow": "Kaş kaldırma",
    "mouth": "Ağız açma",
    "smile": "Gülümseme",
    "off": "Kapalı",
}

ACTIONS = ("left", "right", "middle")

ACTION_LABELS = {
    "left": "Sol tık",
    "right": "Sağ tık",
    "middle": "Orta tık",
}


class _GestureSlot:
    """Tek bir jest türü için zaman tabanlı tetikleyici. update() her karede çağrılır."""

    # jest başına: (giriş eşiği, çıkış eşiği, tutma süresi sn)
    # long_blink girişi 0.55: kamera alttan bakarken kapalı-göz skoru düşük
    # kalabiliyor (canlı ölçüm); 0.40 sn tutma asıl güvenlik katmanıdır.
    # wink_*/brow: giriş-çıkış eşikleri uyarlanabilir taban kullanır
    # (WINK_DELTA_*/BROW_DELTA_*) — buradaki None yalnız yer tutucudur,
    # tutma süresi (üçüncü değer) yine buradan okunur.
    PARAMS = {
        "long_blink": (0.55, 0.45, 0.40),
        "wink_left": (None, None, 0.30),
        "wink_right": (None, None, 0.30),
        "brow": (None, None, 0.22),      # uyarlanabilir taban kullanır
        "mouth": (0.50, 0.35, 0.25),
        "smile": (0.50, 0.35, 0.28),
    }
    BROW_DELTA_IN = 0.28
    BROW_DELTA_OUT = 0.15
    BROW_DELTA_FREEZE = 0.12
    # wink_*: sol-sağ göz kapama FARKI kişiden kişiye dinlenme halinde bile
    # sıfır değildir (kamera açısı, yüz asimetrisi) — bu yüzden brow gibi
    # UYARLANABİLİR TABAN kullanılır; taban çıkarılmadan sabit bir eşik
    # kullanmak imleci kalıcı dondurabilirdi (kişinin doğal asimetrisi eşiği
    # sürekli aşar).
    WINK_DELTA_IN = 0.30
    WINK_DELTA_OUT = 0.17
    WINK_DELTA_FREEZE = 0.13
    # Taban, TEK gürültülü kareden değil ilk birkaç karenin MEDYANINDAN
    # kurulur (bkz. _adaptive) — kamera açısı/ışık yüzünden o an rastgele
    # yüksek gelen bir kare tabanı yanlış yere çivilememesi için.
    BASELINE_FRAMES = 8
    REFRACTORY = 1.0         # iki tıklama arası en az süre
    # Erken dondurma: jest sinyali yükselmeye BAŞLAR başlamaz imleç sabitlenir
    # (jest mimiği yüzü oynatır; imlecin hedeften kaymaması için)
    FREEZE_THR = {"long_blink": 0.30, "mouth": 0.28, "smile": 0.28}
    FREEZE_DELTA = {"brow": BROW_DELTA_FREEZE, "wink_left": WINK_DELTA_FREEZE,
                    "wink_right": WINK_DELTA_FREEZE}

    def __init__(self, gesture: str = "off"):
        self.gesture = gesture if gesture in GESTURES else "off"
        self._active_t: float | None = None
        self._fired = False
        self._last_click = -10.0
        self._base: float | None = None
        self._base_collect: list[float] = []

    def set_gesture(self, gesture: str):
        if gesture in GESTURES:
            self.gesture = gesture
            self._active_t = None
            self._fired = False
            self._base = None
            self._base_collect = []

    def _adaptive(self, raw: float, delta_in: float, delta_out: float) -> tuple[float, float, float]:
        """Kişiye uyarlanabilir taban çizgisi (brow ve wink_* ortak mantığı).

        Taban, ilk BASELINE_FRAMES karenin MEDYANIYLA kurulur (tek kareye
        değil) — toplama sırasında jest algılanmaz (~0.3-0.4 sn, fark
        edilmez). Sonra yalnız DİNLENME halindeyken (raw, taban+çıkış
        eşiğinin altındayken) yavaşça uyum sağlar; jest sırasında donuk
        kalır ki sinyali kendi kendine "yakalayıp" eritmesin.
        """
        if self._base is None:
            self._base_collect.append(raw)
            if len(self._base_collect) < self.BASELINE_FRAMES:
                return 0.0, delta_in, delta_out
            s = sorted(self._base_collect)
            self._base = s[len(s) // 2]
            self._base_collect = []
        elif raw < self._base + delta_out:
            self._base = 0.97 * self._base + 0.03 * raw
        v = max(0.0, raw - self._base)
        return v, delta_in, delta_out

    # ---- sinyal seçimi ----
    def _signal(self, scores: dict) -> tuple[float, float, float]:
        """(taban-çıkarılmış değer, giriş eşiği, çıkış eşiği)"""
        g = self.gesture
        if g == "long_blink":
            v = scores.get("blink", 0.0)
            hi, lo, _ = self.PARAMS[g]
            return v, hi, lo
        if g == "wink_left":
            raw = scores.get("blink_left", 0.0) - scores.get("blink_right", 0.0)
            return self._adaptive(raw, self.WINK_DELTA_IN, self.WINK_DELTA_OUT)
        if g == "wink_right":
            raw = scores.get("blink_right", 0.0) - scores.get("blink_left", 0.0)
            return self._adaptive(raw, self.WINK_DELTA_IN, self.WINK_DELTA_OUT)
        if g == "mouth":
            v = scores.get("jaw", 0.0)
            hi, lo, _ = self.PARAMS[g]
            return v, hi, lo
        if g == "smile":
            v = scores.get("smile", 0.0)
            hi, lo, _ = self.PARAMS[g]
            return v, hi, lo
        # brow: kişiye uyarlanabilir taban çizgisi
        raw = scores.get("brow", 0.0)
        return self._adaptive(raw, self.BROW_DELTA_IN, self.BROW_DELTA_OUT)

    # ---- ana güncelleme ----
    def update(self, scores: dict, t: float) -> tuple[bool, bool]:
        """
        Döndürür: (şimdi tıkla, imleci dondur).

        Dondurma: HER jestte, sinyal yükselmeye başlar başlamaz imleç
        sabitlenir; tıklama kullanıcının nişan aldığı yere düşer.
        """
        if self.gesture == "off":
            return False, False

        v, thr_in, thr_out = self._signal(scores)
        if self.gesture in self.FREEZE_DELTA:
            # v zaten taban çıkarılmış (bkz. _adaptive) — doğrudan karşılaştır
            freeze = v > self.FREEZE_DELTA[self.gesture]
        else:
            freeze = v > self.FREEZE_THR.get(self.gesture, 0.30)

        if self._active_t is None:
            if v >= thr_in and (t - self._last_click) >= self.REFRACTORY:
                self._active_t = t
                self._fired = False
        else:
            hold = self.PARAMS[self.gesture][2]
            if v < thr_out:
                self._active_t = None
                self._fired = False
            elif not self._fired and (t - self._active_t) >= hold:
                self._fired = True
                self._last_click = t
                return True, freeze
        return False, freeze


class GestureClick:
    """Üç bağımsız eylem yuvası (sol/sağ/orta tık), her biri bir jeste bağlanır.

    Aynı jestin iki yuvaya birden atanmaması çağıran tarafın sorumluluğudur
    (bkz. app/ui/pages/eye_page.py — çakışan seçim reddedilir). Bu sınıf
    yalnız atanmış jestleri bağımsız izler; long_blink (iki göz) ile
    wink_left/wink_right (tek göz FARKI) doğaları gereği çakışmaz — simetrik
    bir kırpmada fark sinyali sıfıra yakın kalır.
    """

    def __init__(self, bindings: dict[str, str] | None = None):
        self._slots: dict[str, _GestureSlot] = {a: _GestureSlot("off") for a in ACTIONS}
        if bindings:
            self.set_bindings(bindings)

    def set_bindings(self, bindings: dict[str, str]):
        for action, gesture in bindings.items():
            if action in self._slots:
                self._slots[action].set_gesture(gesture)

    def update(self, scores: dict, t: float) -> tuple[list[str], bool]:
        """Döndürür: (bu karede tetiklenen eylemler, imleci dondur mu)."""
        fired = []
        freeze = False
        for action, slot in self._slots.items():
            clicked, frz = slot.update(scores, t)
            if clicked:
                fired.append(action)
            freeze = freeze or frz
        return fired, freeze
