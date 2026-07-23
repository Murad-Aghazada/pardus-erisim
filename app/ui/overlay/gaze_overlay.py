"""
Bakış imleci katmanı.

Tüm ekranı kaplayan, tıklamayı geçiren (click-through) saydam pencere.
Bakışın olduğu yere yumuşak bir nokta çizer. Bakış bir noktada sabit
kalırsa dwell halkası dolar ve o noktaya tıklama üretir.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import Qt, QTimer, Signal, QPointF
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QPen
from PySide6.QtWidgets import QWidget

from app.theme import Palette


class GazeOverlay(QWidget):
    dwell_click = Signal(int, int)   # ekran pikseli

    def __init__(self, screen_geo, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # tıklamayı geçir
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(screen_geo)

        self._x = screen_geo.width() / 2
        self._y = screen_geo.height() / 2
        self._show_dot = True
        self._dwell_enabled = True
        self._dwell_ms = 900
        self._radius = 42          # sabitlik yarıçapı (px)

        self._anchor = None
        self._anchor_t = 0.0
        self._progress = 0.0
        self._last_click_t = 0.0
        # dwell penceresi içindeki bakış ortalaması — tıklama buraya gider
        self._acc_x = 0.0
        self._acc_y = 0.0
        self._acc_n = 0

        self._flash_t = 0.0          # tıklama geri bildirimi (genişleyen halka)
        self._flash_pos = (0.0, 0.0)

        self._paint_timer = QTimer(self)
        self._paint_timer.timeout.connect(self.update)
        self._paint_timer.start(16)

    def flash(self):
        """Tıklama gerçekleşti: imleçte kısa bir halka animasyonu göster."""
        self._flash_t = time.time()
        self._flash_pos = (self._x, self._y)

    def configure(self, show_dot: bool, dwell_enabled: bool, dwell_ms: int):
        self._show_dot = show_dot
        self._dwell_enabled = dwell_enabled
        self._dwell_ms = max(300, dwell_ms)

    def set_gaze(self, x: float, y: float):
        self._x, self._y = x, y
        if self._dwell_enabled:
            self._update_dwell(x, y)

    def _update_dwell(self, x, y):
        now = time.time()
        if self._anchor is None:
            self._anchor = (x, y)
            self._anchor_t = now
            self._progress = 0.0
            self._acc_x = self._acc_y = 0.0
            self._acc_n = 0
            return
        ax, ay = self._anchor
        if math.hypot(x - ax, y - ay) <= self._radius:
            self._acc_x += x
            self._acc_y += y
            self._acc_n += 1
            elapsed = (now - self._anchor_t) * 1000.0
            self._progress = min(1.0, elapsed / self._dwell_ms)
            if self._progress >= 1.0 and (now - self._last_click_t) > 0.8:
                self._last_click_t = now
                # pencere ortalaması: tek karelik değil, niyetin en iyi kestirimi
                mx = self._acc_x / self._acc_n if self._acc_n else ax
                my = self._acc_y / self._acc_n if self._acc_n else ay
                self.dwell_click.emit(int(mx), int(my))
                self._anchor = None
                self._progress = 0.0
        else:
            self._anchor = (x, y)
            self._anchor_t = now
            self._progress = 0.0
            self._acc_x = self._acc_y = 0.0
            self._acc_n = 0

    def paintEvent(self, _):
        if not self._show_dot:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self._x, self._y

        # yumuşak hale
        grad = QRadialGradient(QPointF(cx, cy), 26)
        c = QColor(Palette.gaze)
        c.setAlpha(70)
        grad.setColorAt(0.0, c)
        edge = QColor(Palette.gaze); edge.setAlpha(0)
        grad.setColorAt(1.0, edge)
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), 26, 26)

        # çekirdek nokta
        core = QColor(Palette.gaze)
        p.setBrush(core)
        p.drawEllipse(QPointF(cx, cy), 7, 7)
        p.setPen(QPen(QColor(255, 255, 255, 220), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 7, 7)

        # tıklama geri bildirimi: genişleyip solan halka
        age = time.time() - self._flash_t
        if 0 < age < 0.45:
            k = age / 0.45
            fx, fy = self._flash_pos
            ring = QColor(Palette.live)
            ring.setAlphaF(1.0 - k)
            pen = QPen(ring, 3.5 * (1.0 - k) + 1.0)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(fx, fy), 10 + 34 * k, 10 + 34 * k)

        # dwell ilerleme halkası
        if self._dwell_enabled and self._progress > 0:
            pen = QPen(QColor(Palette.scan), 3.5)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            span = int(-360 * 16 * self._progress)
            r = 16
            p.drawArc(int(cx - r), int(cy - r), 2 * r, 2 * r, 90 * 16, span)
