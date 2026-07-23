"""
Jest ile tıklama — güvenilir, süre-tabanlı algılama.

Kısa göz kırpma yakalamak kare hızına ve kişiye çok bağımlıdır (21 fps'te
hızlı bir kırpma 1-2 karedir ve kolayca kaçar). Bunun yerine SÜREKLİ sinyal
ölçülür: jest eşiğin üstünde belirli bir süre TUTULUNCA tıklama tetiklenir.
Çok kareli doğrulama, kare hızından bağımsız (zaman tabanlı) ve kişiye uyum
için uyarlanabilir taban çizgisi kullanır.

Jestler (MediaPipe blendshape skorları, 0..1):
- long_blink: gözleri ~0.4 sn kapalı tut (doğal kırpma daha kısadır)
- brow: kaşları kaldır ve kısa süre tut
- mouth: ağzı aç ve kısa süre tut (konuşurken yanlış tetiklenebilir)
- smile: gülümse ve kısa süre tut
"""

from __future__ import annotations

GESTURES = ("long_blink", "brow", "mouth", "smile", "off")

GESTURE_LABELS = {
    "long_blink": "Uzun göz kapama (önerilen)",
    "brow": "Kaş kaldırma",
    "mouth": "Ağız açma",
    "smile": "Gülümseme",
    "off": "Kapalı",
}


class GestureClick:
    """Zaman tabanlı jest tetikleyici. update() her karede çağrılır."""

    # jest başına: (giriş eşiği, çıkış eşiği, tutma süresi sn)
    # long_blink girişi 0.55: kamera alttan bakarken kapalı-göz skoru düşük
    # kalabiliyor (canlı ölçüm); 0.40 sn tutma asıl güvenlik katmanıdır.
    PARAMS = {
        "long_blink": (0.55, 0.45, 0.40),
        "brow": (None, None, 0.22),      # uyarlanabilir taban kullanır
        "mouth": (0.50, 0.35, 0.25),
        "smile": (0.50, 0.35, 0.28),
    }
    BROW_DELTA_IN = 0.28     # taban + bu kadar yükselince giriş
    BROW_DELTA_OUT = 0.15
    BROW_DELTA_FREEZE = 0.12
    REFRACTORY = 1.0         # iki tıklama arası en az süre
    # Erken dondurma: jest sinyali yükselmeye BAŞLAR başlamaz imleç sabitlenir
    # (jest mimiği yüzü oynatır; imlecin hedeften kaymaması için)
    FREEZE_THR = {"long_blink": 0.30, "mouth": 0.28, "smile": 0.28}

    def __init__(self, gesture: str = "long_blink"):
        self.gesture = gesture if gesture in GESTURES else "long_blink"
        self._active_t: float | None = None
        self._fired = False
        self._last_click = -10.0
        self._brow_base: float | None = None

    def set_gesture(self, gesture: str):
        if gesture in GESTURES:
            self.gesture = gesture
            self._active_t = None
            self._fired = False

    # ---- sinyal seçimi ----
    def _signal(self, scores: dict) -> tuple[float, float, float]:
        """(değer, giriş eşiği, çıkış eşiği)"""
        g = self.gesture
        if g == "long_blink":
            v = scores.get("blink", 0.0)
            hi, lo, _ = self.PARAMS[g]
            return v, hi, lo
        if g == "mouth":
            v = scores.get("jaw", 0.0)
            hi, lo, _ = self.PARAMS[g]
            return v, hi, lo
        if g == "smile":
            v = scores.get("smile", 0.0)
            hi, lo, _ = self.PARAMS[g]
            return v, hi, lo
        # brow: kişiye uyarlanabilir taban çizgisi
        v = scores.get("brow", 0.0)
        if self._brow_base is None:
            self._brow_base = v
        elif v < self._brow_base + self.BROW_DELTA_OUT:
            self._brow_base = 0.97 * self._brow_base + 0.03 * v
        return v, self._brow_base + self.BROW_DELTA_IN, self._brow_base + self.BROW_DELTA_OUT

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
        if self.gesture == "brow":
            freeze = v > (self._brow_base or 0.0) + self.BROW_DELTA_FREEZE
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
