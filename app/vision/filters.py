"""
Sinyal filtreleri.

OneEuroFilter: bakış/imleç yumuşatma için altın standart. Durağanken çok
düşük titreme, hızlı hareket ederken çok düşük gecikme sağlar. Basit EMA'nın
aksine kesim frekansını hıza göre uyarlar. (Casiez ve ark., CHI 2012)
"""

from __future__ import annotations

import math
import time


class _LowPass:
    def __init__(self):
        self.y = None

    def apply(self, x: float, alpha: float) -> float:
        if self.y is None:
            self.y = x
        else:
            self.y = alpha * x + (1.0 - alpha) * self.y
        return self.y


class OneEuroFilter:
    """
    min_cutoff: durağan haldeki kesim frekansı (Hz). Küçük = daha pürüzsüz.
    beta: hıza duyarlılık. Büyük = hızlı harekette daha az gecikme.
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007,
                 d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x = _LowPass()
        self._dx = _LowPass()
        self._t = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self):
        self._x = _LowPass()
        self._dx = _LowPass()
        self._t = None

    def apply(self, x: float, t: float | None = None) -> float:
        now = time.monotonic() if t is None else t
        if self._t is None:
            self._t = now
            self._x.apply(x, 1.0)
            self._dx.apply(0.0, 1.0)
            return x
        dt = max(1e-4, now - self._t)
        self._t = now

        dx = (x - self._x.y) / dt
        dx_hat = self._dx.apply(dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        return self._x.apply(x, self._alpha(cutoff, dt))


class GazeFilter2D:
    """İki eksenli One Euro sarmalayıcı; yumuşatma kaydırıcısına (0-100) bağlanır."""

    def __init__(self):
        self.fx = OneEuroFilter()
        self.fy = OneEuroFilter()
        self.set_smoothing(60)

    def set_smoothing(self, level: int):
        """0 = ham/çevik, 100 = çok sakin. min_cutoff 2.2 → 0.25 Hz arası."""
        level = max(0, min(100, level))
        mc = 2.2 - (level / 100.0) * 1.95
        beta = 0.012 - (level / 100.0) * 0.008   # sakin modda hız tepkisi de kısılır
        for f in (self.fx, self.fy):
            f.min_cutoff = mc
            f.beta = beta

    def reset(self):
        self.fx.reset()
        self.fy.reset()

    def apply(self, x: float, y: float, t: float | None = None) -> tuple[float, float]:
        return self.fx.apply(x, t), self.fy.apply(y, t)
