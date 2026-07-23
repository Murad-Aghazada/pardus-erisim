"""
Bakış eşleyici — iris oranı + kafa pozunu ekran koordinatına çevirir.

Kalibrasyon: 9 noktaya bakılırken toplanan örneklerden ridge (Tikhonov)
regresyonla eşleme öğrenilir. Özellik vektörüne kafa pozu (yaw/pitch) da
girer; böylece kafa hafif oynadığında doğruluk korunur. Kalibrasyon yoksa
iris oranının dar aralığını ekrana açan varsayılan eşleme kullanılır.
"""

from __future__ import annotations

import json
import os
import numpy as np
from PySide6.QtCore import QStandardPaths

FEATURE_VERSION = 3   # özellik seti değişirse eski kalibrasyon geçersiz


def _cal_path() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "calibration.json")


def _features(rx: float, ry: float, yaw: float, pitch: float) -> np.ndarray:
    """Tasarım vektörü: doğrusal + kafa pozu + hafif eğrilik terimleri."""
    return np.array([
        rx, ry, yaw, pitch,
        rx * ry, rx * rx, ry * ry,
        1.0,
    ])


class GazeMapper:
    # Kalibrasyonsuz varsayılan eşleme: yeni bakış metriğinin tipik aralığı.
    # Merkezler canlı ölçümle doğrulandı: ekrana bakan gerçek kullanıcıda
    # nötr rx≈0.506, ry≈0.004 (probe_camera). Dikey aralık yatay bakış
    # açısından dardır; 0.075 kenarlara erişimi kolaylaştırır.
    H_CENTER, H_HALF = 0.50, 0.14
    V_CENTER, V_HALF = 0.00, 0.075

    def __init__(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.sensitivity = 55     # 0-100; yalnız varsayılan eşlemede kullanılır
        self._samples: list[tuple[float, float, float, float, float, float]] = []
        self._Ax: np.ndarray | None = None
        self._Ay: np.ndarray | None = None
        self.load()

    # ---- Kalibrasyon toplama ----
    def clear(self):
        self._samples.clear()

    def add_sample(self, rx: float, ry: float, yaw: float, pitch: float,
                   target_x: float, target_y: float):
        self._samples.append((rx, ry, yaw, pitch, target_x, target_y))

    def fit(self) -> bool:
        """Ridge regresyonla eşlemeyi öğren. Başarılıysa True."""
        if len(self._samples) < 5:
            return False
        arr = np.array(self._samples, dtype=float)
        M = np.vstack([_features(*row[:4]) for row in arr])
        tx, ty = arr[:, 4], arr[:, 5]

        # Hedefler [0,1] ölçeğine indirilir; küçük ridge cezası kararlılık
        # sağlar (bias terimi cezasız). Katsayılar piksele geri ölçeklenir.
        n_feat = M.shape[1]
        reg = np.eye(n_feat) * 1e-4
        reg[-1, -1] = 0.0
        MtM = M.T @ M
        ax_n = np.linalg.solve(MtM + reg, M.T @ (tx / self.screen_w))
        ay_n = np.linalg.solve(MtM + reg, M.T @ (ty / self.screen_h))
        self._Ax = ax_n * self.screen_w
        self._Ay = ay_n * self.screen_h
        self.save()
        return True

    def calibration_residual(self) -> float | None:
        """Kalibrasyon örneklerinde ortalama piksel hatası (öz denetim)."""
        if self._Ax is None or not self._samples:
            return None
        arr = np.array(self._samples, dtype=float)
        M = np.vstack([_features(*row[:4]) for row in arr])
        px = M @ self._Ax
        py = M @ self._Ay
        err = np.hypot(px - arr[:, 4], py - arr[:, 5])
        return float(np.mean(err))

    # ---- Eşleme ----
    def map(self, rx: float, ry: float, yaw: float = 0.0,
            pitch: float = 0.0) -> tuple[float, float]:
        if self._Ax is not None and self._Ay is not None:
            f = _features(rx, ry, yaw, pitch)
            x = float(f @ self._Ax)
            y = float(f @ self._Ay)
        else:
            # hassasiyet yüksekse aralık daralır → az göz hareketi çok yol alır
            k = 1.55 - (max(0, min(100, self.sensitivity)) / 100.0)  # 0.55..1.55
            hx, hy = self.H_HALF * k, self.V_HALF * k
            x = _expand(rx, self.H_CENTER - hx, self.H_CENTER + hx) * self.screen_w
            y = _expand(ry, self.V_CENTER - hy, self.V_CENTER + hy) * self.screen_h
        x = _clamp(x, 0, self.screen_w - 1)
        y = _clamp(y, 0, self.screen_h - 1)
        return x, y

    @property
    def is_calibrated(self) -> bool:
        return self._Ax is not None

    # ---- Kalıcılık ----
    def save(self):
        if self._Ax is None:
            return
        data = {
            "version": FEATURE_VERSION,
            "screen": [self.screen_w, self.screen_h],
            "Ax": self._Ax.tolist(),
            "Ay": self._Ay.tolist(),
        }
        try:
            with open(_cal_path(), "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            pass

    def load(self):
        try:
            with open(_cal_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            if (data.get("version") == FEATURE_VERSION
                    and data.get("screen") == [self.screen_w, self.screen_h]):
                self._Ax = np.array(data["Ax"])
                self._Ay = np.array(data["Ay"])
        except (OSError, ValueError, KeyError):
            pass

    def forget(self):
        self._Ax = None
        self._Ay = None
        try:
            os.remove(_cal_path())
        except OSError:
            pass


def _expand(v: float, lo: float, hi: float) -> float:
    return _clamp((v - lo) / (hi - lo), 0.0, 1.0)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
