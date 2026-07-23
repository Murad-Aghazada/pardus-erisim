"""
Kalibrasyon katmanı.

Tam ekran, koyu bir yüzey. Ekranda sırayla hedefler belirir; kullanıcı her
hedefe bakar. Her hedefte göz izleyiciden o anki iris oranı örneklenir.
Dokuz nokta toplandıktan sonra eşleyiciye afin dönüşüm oturtulur.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget

from app.theme import Palette, Type


# 3×3 hedef ızgarası (ekran oranı)
GRID = [
    (0.08, 0.10), (0.5, 0.10), (0.92, 0.10),
    (0.08, 0.5),  (0.5, 0.5),  (0.92, 0.5),
    (0.08, 0.90), (0.5, 0.90), (0.92, 0.90),
]

SETTLE_MS = 700      # hedefe alışma süresi
SAMPLE_MS = 1000     # örnek toplama süresi (uzun = daha temiz medyan)


class CalibrationOverlay(QWidget):
    finished = Signal(bool)   # başarılı mı

    def __init__(self, tracker, screen_geo, parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setGeometry(screen_geo)
        self.setFocusPolicy(Qt.StrongFocus)

        self._geo = screen_geo
        self._i = -1
        self._phase = "intro"       # intro | settle | sample | done
        self._samples: list[tuple[float, float]] = []
        self._pulse = 0.0

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)

        self._paint = QTimer(self)
        self._paint.timeout.connect(self._animate)
        self._paint.start(16)

    def start(self):
        self.tracker.mapper.clear()
        self.tracker.set_calibrating(True)
        self._i = -1
        self._phase = "intro"
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(1400, self._next_point)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._abort()

    def _abort(self):
        self._tick.stop()
        self.tracker.set_calibrating(False)
        self.finished.emit(False)
        self.close()

    def _next_point(self):
        self._i += 1
        if self._i >= len(GRID):
            self._complete()
            return
        self._phase = "settle"
        self._samples.clear()
        self._tick.start(SETTLE_MS)

    def _on_tick(self):
        self._tick.stop()
        if self._phase == "settle":
            self._phase = "sample"
            self._collect = QTimer(self)
            self._collect.timeout.connect(self._grab)
            self._collect.start(40)
            QTimer.singleShot(SAMPLE_MS, self._finish_sample)

    def _grab(self):
        s = self.tracker.current_sample()
        if s is not None:
            self._samples.append(s)

    def _finish_sample(self):
        self._collect.stop()
        if self._samples:
            # bileşen bazında medyan (gürültüye dayanıklı)
            med = []
            for k in range(4):
                vals = sorted(s[k] for s in self._samples)
                med.append(vals[len(vals) // 2])
            gx, gy = GRID[self._i]
            self.tracker.mapper.add_sample(
                med[0], med[1], med[2], med[3],
                gx * self._geo.width(), gy * self._geo.height())
        self._next_point()

    def _complete(self):
        ok = self.tracker.mapper.fit()
        self.tracker.set_calibrating(False)
        self._phase = "done"
        QTimer.singleShot(700, lambda: self._end(ok))

    def _end(self, ok: bool):
        self._paint.stop()
        self.finished.emit(ok)
        self.close()

    def _animate(self):
        import math, time
        self._pulse = 0.5 + 0.5 * math.sin(time.time() * 3.2)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(22, 21, 18, 250))

        if self._phase in ("intro", "done"):
            p.setPen(QColor(Palette.paper))
            f = QFont(); f.setPointSizeF(20); f.setWeight(QFont.DemiBold)
            p.setFont(f)
            msg = ("Beliren noktalara sırayla bakın"
                   if self._phase == "intro" else "Kalibrasyon tamamlandı")
            p.drawText(self.rect(), Qt.AlignCenter, msg)
            if self._phase == "intro":
                f2 = QFont(); f2.setPointSizeF(12)
                p.setFont(f2)
                p.setPen(QColor(Palette.ink_faint))
                p.drawText(self.rect().adjusted(0, 90, 0, 0),
                           Qt.AlignHCenter | Qt.AlignTop,
                           "Çıkmak için Esc")
            return

        if 0 <= self._i < len(GRID):
            gx, gy = GRID[self._i]
            cx, cy = gx * self.width(), gy * self.height()

            sampling = self._phase == "sample"
            outer = 26 + (10 * self._pulse if sampling else 4 * self._pulse)
            ring = QColor(Palette.scan) if sampling else QColor(Palette.ink_faint)
            p.setPen(QPen(ring, 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), outer, outer)

            core = QColor(Palette.ember) if sampling else QColor(Palette.paper)
            p.setBrush(core)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), 8, 8)

            # ilerleme sayacı
            p.setPen(QColor(Palette.ink_faint))
            f = QFont(); f.setPointSizeF(11)
            p.setFont(f)
            p.drawText(QRectF(0, self.height() - 60, self.width(), 30),
                       Qt.AlignHCenter | Qt.AlignTop,
                       f"{self._i + 1} / {len(GRID)}")
