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
    # NOT — tutma süreleri neden jeste göre çok farklı:
    # long_blink'te tutma süresi ASIL güvenlik katmanıdır, çünkü istemsiz
    # göz kırpma da aynı sinyali üretir; ayırt eden tek şey süredir (doğal
    # kırpma ~0.1 sn). wink_*'te ise güvenliği SİNYALİN KENDİSİ sağlar:
    # istemsiz kırpma simetriktir, sol-sağ farkı ~0 kalır (bkz. _signal).
    # Bu yüzden wink'te uzun tutma istemek güvenlik katmaz, yalnız
    # kullanılabilirliği bozar — kısa ve çok-kareli doğrulama yeterlidir.
    PARAMS = {
        "long_blink": (0.55, 0.45, 0.40),
        "wink_left": (None, None, 0.12),
        "wink_right": (None, None, 0.12),
        "brow": (None, None, 0.18),      # uyarlanabilir taban kullanır
        "mouth": (0.50, 0.35, 0.25),
        "smile": (0.50, 0.35, 0.28),
    }
    BROW_DELTA_IN = 0.24
    BROW_DELTA_OUT = 0.12
    BROW_DELTA_FREEZE = 0.10
    # wink_*: sol-sağ göz kapama FARKI kişiden kişiye dinlenme halinde bile
    # sıfır değildir (kamera açısı, yüz asimetrisi) — bu yüzden brow gibi
    # UYARLANABİLİR TABAN kullanılır; taban çıkarılmadan sabit bir eşik
    # kullanmak imleci kalıcı dondurabilirdi (kişinin doğal asimetrisi eşiği
    # sürekli aşar).
    WINK_DELTA_IN = 0.22
    WINK_DELTA_OUT = 0.11
    WINK_DELTA_FREEZE = 0.09
    # Taban, TEK gürültülü kareden değil ilk birkaç karenin MEDYANINDAN
    # kurulur (bkz. _adaptive) — kamera açısı/ışık yüzünden o an rastgele
    # yüksek gelen bir kare tabanı yanlış yere çivilememesi için.
    BASELINE_FRAMES = 8
    # Taban yalnız GERÇEKTEN sakin karelerde uyum sağlar. Eskiden çıkış
    # eşiğine (0.17) kadar uyum sürüyordu; jest yükselirken taban da onu
    # kovalayıp sinyali yiyor, jest eşiğe hiç ulaşamıyordu.
    BASELINE_QUIET_BAND = 0.05
    # Başarısız bir denemeden sonra kullanıcı hemen yeniden dener; uzun bir
    # bekleme bu denemeyi sessizce yutup "algılamadı" hissi veriyordu.
    REFRACTORY = 0.55        # iki tıklama arası en az süre
    # Erken dondurma: jest sinyali yükselmeye BAŞLAR başlamaz imleç sabitlenir
    # (jest mimiği yüzü oynatır; imlecin hedeften kaymaması için)
    FREEZE_THR = {"long_blink": 0.30, "mouth": 0.28, "smile": 0.28}
    FREEZE_DELTA = {"brow": BROW_DELTA_FREEZE, "wink_left": WINK_DELTA_FREEZE,
                    "wink_right": WINK_DELTA_FREEZE}

    def __init__(self, gesture: str = "off"):
        self.gesture = gesture if gesture in GESTURES else "off"
        self.sensitivity = 55        # 0-100; yüksek = daha kolay tetiklenir
        self._active_t: float | None = None
        self._fired = False
        self._last_click = -10.0
        self._base: float | None = None
        self._base_collect: list[float] = []

    @property
    def _scale(self) -> float:
        """Hassasiyet ölçeği: yüksek hassasiyet → düşük eşik, kısa tutma.

        Kamera açısı, ışık ve yüz yapısı kişiden kişiye çok değişir; tek bir
        sabit eşik herkese uymuyor (biri hiç tetikleyemezken başkası yanlış
        tetikliyor). 0.60..1.60 aralığı, ölçülen uçları kapsar.
        """
        return 1.60 - max(0, min(100, self.sensitivity)) / 100.0

    def set_gesture(self, gesture: str):
        # Aynı jest yeniden atanırsa DOKUNMA: apply_config her ayar
        # değişikliğinde tüm yuvalara set_gesture çağırır; koşulsuz sıfırlama
        # öğrenilmiş tabanı siler ve jest ~0.4 sn boyunca ölü kalırdı.
        if gesture in GESTURES and gesture != self.gesture:
            self.gesture = gesture
            self._active_t = None
            self._fired = False
            self._base = None
            self._base_collect = []

    def _adaptive(self, raw: float, delta_in: float, delta_out: float) -> tuple[float, float, float]:
        """Kişiye uyarlanabilir taban çizgisi (brow ve wink_* ortak mantığı).

        Taban, ilk BASELINE_FRAMES karenin MEDYANIYLA kurulur (tek kareye
        değil) — toplama sırasında jest algılanmaz (~0.4 sn, fark edilmez).

        Sonrasında taban YALNIZ gerçekten sakin karelerde (raw, taban +
        BASELINE_QUIET_BAND altındayken) ve jest ETKİN DEĞİLKEN uyum sağlar.
        Bu iki koşul şart: aksi halde jest yükselirken taban da onu kovalar,
        v = raw - taban hiç büyümez ve jest eşiğe ulaşamaz (kullanıcının
        "4-5 kez denemek zorunda kaldım" dediği asıl neden buydu).
        """
        if self._base is None:
            self._base_collect.append(raw)
            if len(self._base_collect) < self.BASELINE_FRAMES:
                return 0.0, delta_in, delta_out
            s = sorted(self._base_collect)
            self._base = s[len(s) // 2]
            self._base_collect = []
        elif self._active_t is None and raw < self._base + self.BASELINE_QUIET_BAND:
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
        k = self._scale
        thr_in *= k
        thr_out *= k
        if self.gesture in self.FREEZE_DELTA:
            # v zaten taban çıkarılmış (bkz. _adaptive) — doğrudan karşılaştır
            freeze = v > self.FREEZE_DELTA[self.gesture] * k
        else:
            freeze = v > self.FREEZE_THR.get(self.gesture, 0.30) * k

        if self._active_t is None:
            if v >= thr_in and (t - self._last_click) >= self.REFRACTORY:
                self._active_t = t
                self._fired = False
        else:
            hold = self.PARAMS[self.gesture][2] * k
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

    def set_sensitivity(self, sensitivity: int):
        for slot in self._slots.values():
            slot.sensitivity = sensitivity

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
