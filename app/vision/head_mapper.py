"""
Kafa işaretçisi eşleyicisi.

Geometrik kafa pozunu (burun ucunun göz çizgisine göre normalize konumu)
ekran koordinatına çevirir. İşaret kesinliği: aynalanmış karede kullanıcı
kafasını SAĞA çevirince burun görüntüde sağa kayar → yaw artar → imleç sağa.
Yukarı bakınca burun göz çizgisine yaklaşır → pitch küçülür → imleç yukarı.

Kalibrasyon YOKTUR: başlangıçta ~1 saniyelik medyan nötr kabul edilir;
"ortala" komutu/butonu istendiği an yeniden merkezler.
"""

from __future__ import annotations

import math


class HeadMapper:
    # Konforlu kafa hareketi aralığı (geometrik poz birimi: burun ucunun
    # yanak-çizgisi çerçevesindeki, yüz genişliğine oranlı konumu)
    YAW_HALF = 0.16
    PITCH_HALF = 0.12
    NEUTRAL_FRAMES = 25
    # Merkeze yakın istemsiz titremeyi yok sayan ölü bölge (nominal -1..1
    # oranının payı). Ölü bölgeden SONRASI DOĞRUSALDIR — üstel/güç eğrisi
    # KULLANILMAZ: böyle bir eğri uçlara yaklaşırken kazancı ARTIRIR, bu da
    # imlecin köşeye "ışınlanmasına" (ani sıçrama) yol açar. Ölü bölge +
    # yeniden ölçekleme, aynı hassasiyeti tüm menzilde korurken yalnız
    # merkezdeki küçük titremeyi keser.
    DEAD_ZONE = 0.10

    @classmethod
    def _shape(cls, v: float) -> float:
        av = abs(v)
        if av <= cls.DEAD_ZONE:
            return 0.0
        scaled = (av - cls.DEAD_ZONE) / (1.0 - cls.DEAD_ZONE)
        return math.copysign(min(1.0, scaled), v)

    def __init__(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.sensitivity = 55          # 0-100
        self._neutral: tuple[float, float] | None = None
        self._collect: list[tuple[float, float]] = []
        self._collecting = True

    # ---- Nötr yönetimi ----
    @property
    def ready(self) -> bool:
        return self._neutral is not None

    def recenter(self):
        """Bir sonraki karelerden yeni nötr topla (anında etkili değil, ~1 sn)."""
        self._collect.clear()
        self._collecting = True

    def feed_neutral(self, yaw: float, pitch: float) -> bool:
        """Nötr toplama modundaysa örneği al; nötr hazırsa True döndür."""
        if not self._collecting:
            return self.ready
        self._collect.append((yaw, pitch))
        if len(self._collect) >= self.NEUTRAL_FRAMES:
            ys = sorted(s[0] for s in self._collect)
            ps = sorted(s[1] for s in self._collect)
            self._neutral = (ys[len(ys) // 2], ps[len(ps) // 2])
            self._collecting = False
            self._collect.clear()
        return self.ready

    # ---- Eşleme ----
    def map(self, yaw: float, pitch: float) -> tuple[float, float] | None:
        """Ekran pikseli; nötr henüz toplanmadıysa None."""
        if self._neutral is None:
            return None
        # hassasiyet: yüksek değer → dar aralık → az kafa hareketiyle çok yol
        k = 1.55 - (max(0, min(100, self.sensitivity)) / 100.0)   # 0.55..1.55
        half_y = self.YAW_HALF * k
        half_p = self.PITCH_HALF * k

        dx = (yaw - self._neutral[0]) / half_y     # -1..1 nominal
        dy = (pitch - self._neutral[1]) / half_p

        dx = self._shape(dx)
        dy = self._shape(dy)

        x = (0.5 + dx * 0.5) * self.screen_w
        y = (0.5 + dy * 0.5) * self.screen_h
        x = max(0.0, min(self.screen_w - 1.0, x))
        y = max(0.0, min(self.screen_h - 1.0, y))
        return x, y


class CornerMagnet:
    """
    Köşe mıknatısı: imleç bir ekran köşesine yaklaşınca onu köşeye çeker.

    Tam ekran pencerede kapat düğmesi (sağ üst), menüler (sol alt) gibi
    hedefler köşelerde yaşar; kullanıcı kabaca köşeye yönelir, mıknatıs
    imleci oturtur, göz kırpma tıklar.
    """

    RADIUS = 120        # çekim alanı (px)
    PULL = 0.38         # kare başına çekim oranı (asimptotik oturma)
    MARGIN = 4          # hedefin köşeden içeri payı

    def __init__(self, screen_w: int, screen_h: int):
        m = self.MARGIN
        self.hotspots = [
            (screen_w - m, m),              # sağ üst: pencere kapat
            (m, m),                         # sol üst
            (m, screen_h - m),              # sol alt: menü
            (screen_w - m, screen_h - m),   # sağ alt
        ]
        self.enabled = True

    def apply(self, x: float, y: float) -> tuple[float, float]:
        if not self.enabled:
            return x, y
        for hx, hy in self.hotspots:
            dx, dy = hx - x, hy - y
            if dx * dx + dy * dy <= self.RADIUS * self.RADIUS:
                return x + dx * self.PULL, y + dy * self.PULL
        return x, y
