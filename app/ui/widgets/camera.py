"""Kamera önizleme yüzeyi — göz izleme motorundan gelen kareleri gösterir."""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QImage, QPixmap, QFont, QPen, QBrush
from PySide6.QtWidgets import QWidget

from app.theme import Palette, Radius


class CameraView(QWidget):
    """
    Gelen QImage karesini yuvarlatılmış çerçevede çizer.
    Kare yoksa nazik bir yer tutucu gösterir. Yüz/iris noktaları motor
    tarafından karenin üstüne çizilmiş gelir.
    """

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: QImage | None = None
        self._hint = "Kamera bekleniyor"
        self.setMinimumSize(320, 240)
        self.setCursor(Qt.PointingHandCursor)

    def set_frame(self, image: QImage):
        self._image = image
        self.update()

    def clear_frame(self, hint: str = "Kamera kapalı"):
        self._image = None
        self._hint = hint
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(0, 0, self.width(), self.height())

        path_clip = self.rect()
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addRoundedRect(r, Radius.md, Radius.md)
        p.setClipPath(clip)

        if self._image is not None and not self._image.isNull():
            pix = QPixmap.fromImage(self._image)
            scaled = pix.scaled(self.size(), Qt.KeepAspectRatioByExpanding,
                                Qt.SmoothTransformation)
            x = (scaled.width() - self.width()) / 2
            y = (scaled.height() - self.height()) / 2
            p.drawPixmap(int(-x), int(-y), scaled)
        else:
            p.fillRect(r, QColor(Palette.sunken))
            # kamera simgesi
            p.setPen(QPen(QColor(Palette.ink_faint), 2.5))
            p.setBrush(Qt.NoBrush)
            cx, cy = self.width() / 2, self.height() / 2 - 12
            p.drawRoundedRect(QRectF(cx - 26, cy - 18, 52, 36), 8, 8)
            p.setBrush(QColor(Palette.sunken))
            p.drawEllipse(QRectF(cx - 9, cy - 9, 18, 18))
            f = QFont(); f.setPointSizeF(11)
            p.setFont(f)
            p.setPen(QColor(Palette.ink_faint))
            p.drawText(QRectF(0, cy + 26, self.width(), 30),
                       Qt.AlignHCenter | Qt.AlignTop, self._hint)

        # ince çerçeve
        p.setClipping(False)
        p.setPen(QPen(QColor(Palette.line_strong), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), Radius.md, Radius.md)
