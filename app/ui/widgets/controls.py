"""Etkileşimli denetimler: anahtar, durum rozeti, bekleme (dwell) butonu."""

from __future__ import annotations

from PySide6.QtCore import (
    Qt, Signal, Property, QPropertyAnimation, QEasingCurve, QRectF, QSize, QTimer,
    QPointF,
)
from PySide6.QtGui import QPainter, QColor, QFont, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget, QHBoxLayout, QLabel, QPushButton

from app.theme import Palette, Type, MIN_TARGET


class ToggleSwitch(QAbstractButton):
    """Büyük, animasyonlu aç/kapa anahtarı. Erişilebilir hedef boyutu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._w, self._h = 62, 34
        self.setFixedSize(self._w, self._h)
        self._offset = 4.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)
        self.setFocusPolicy(Qt.StrongFocus)

    def sizeHint(self) -> QSize:
        return QSize(self._w, self._h)

    def _animate(self, checked: bool):
        start = self._offset
        end = (self._w - self._h + 4) if checked else 4
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, v: float):
        self._offset = v
        self.update()

    offset = Property(float, get_offset, set_offset)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self._w, self._h)
        track = QColor(Palette.live) if self.isChecked() else QColor(Palette.line_strong)
        p.setBrush(track)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, self._h / 2, self._h / 2)

        knob = self._h - 8
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(self._offset, 4, knob, knob))

        if self.hasFocus():
            pen = QPen(QColor(Palette.focus), 2.5)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(1.2, 1.2, -1.2, -1.2), self._h / 2, self._h / 2)


class StatusPill(QWidget):
    """Renkli nokta + etiket. Türü ile durum rengi belirlenir."""

    TONES = {
        "live":  (Palette.live, Palette.live_soft),
        "idle":  (Palette.ink_faint, Palette.sunken),
        "warn":  (Palette.warn, Palette.warn_soft),
        "error": (Palette.danger, Palette.danger_soft),
        "busy":  (Palette.accent, Palette.accent_soft),
    }

    def __init__(self, text: str = "", tone: str = "idle", parent=None):
        super().__init__(parent)
        self._text = text
        self._tone = tone
        self._pulse = False
        self.setMinimumHeight(28)
        self._t = QTimer(self)
        self._t.timeout.connect(self.update)

    def set_status(self, text: str, tone: str, pulse: bool = False):
        self._text, self._tone, self._pulse = text, tone, pulse
        if pulse and not self._t.isActive():
            self._t.start(700)
        elif not pulse and self._t.isActive():
            self._t.stop()
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        return QSize(fm.horizontalAdvance(self._text) + 42, 30)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fg, bg = self.TONES.get(self._tone, self.TONES["idle"])
        fg, bg = QColor(fg), QColor(bg)
        r = QRectF(0, 1, self.width() - 1, self.height() - 2)
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        # nokta
        import math, time
        alpha = 1.0
        if self._pulse:
            alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(time.time() * 4))
        dot = QColor(fg)
        dot.setAlphaF(alpha)
        p.setBrush(dot)
        cy = self.height() / 2
        p.drawEllipse(QPointF(15, cy), 5, 5)

        # metin
        f = QFont(); f.setPointSizeF(10.5); f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(fg)
        p.drawText(QRectF(28, 0, self.width() - 34, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self._text)


class DwellButton(QPushButton):
    """
    Bakışla (dwell) tıklanabilir buton.

    Fare veya bakış üzerine geldiğinde alt kenarda bir ilerleme çizgisi dolar;
    dwell süresi dolunca otomatik tıklar. Klavye/fare ile de çalışır.
    """

    dwell_completed = Signal()

    def __init__(self, text: str, dwell_ms: int = 900, parent=None):
        super().__init__(text, parent)
        self.setObjectName("Primary")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(MIN_TARGET)
        self._dwell_ms = dwell_ms
        self._progress = 0.0
        self._dwell_on = False
        self._elapsed = 0

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def set_dwell_enabled(self, on: bool):
        self._dwell_on = on
        if not on:
            self._reset()

    def set_dwell_ms(self, ms: int):
        self._dwell_ms = max(300, ms)

    def enterEvent(self, e):
        if self._dwell_on:
            self._elapsed = 0
            self._timer.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._reset()
        super().leaveEvent(e)

    def _tick(self):
        self._elapsed += self._timer.interval()
        self._progress = min(1.0, self._elapsed / self._dwell_ms)
        self.update()
        if self._progress >= 1.0:
            self._timer.stop()
            self.dwell_completed.emit()
            self.click()
            self._reset()

    def _reset(self):
        self._timer.stop()
        self._progress = 0.0
        self._elapsed = 0
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._progress > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            h = 4
            w = (self.width() - 24) * self._progress
            path = QPainterPath()
            path.addRoundedRect(QRectF(12, self.height() - h - 6, w, h), 2, 2)
            p.fillPath(path, QColor("#FFFFFF"))
