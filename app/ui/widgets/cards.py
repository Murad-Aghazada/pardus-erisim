"""Düzen bileşenleri: kart, istatistik kutusu, bölüm başlığı, ayar satırı."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QGraphicsDropShadowEffect,
    QSizePolicy,
)

from app.theme import Palette, Type, Space, Radius


def _shadow(widget: QWidget, blur=34, dy=10, alpha=26):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(0)
    eff.setYOffset(dy)
    eff.setColor(QColor(30, 26, 20, alpha))
    widget.setGraphicsEffect(eff)
    return eff


class Card(QFrame):
    """Yumuşak gölgeli içerik kartı."""

    def __init__(self, raised: bool = False, pad: int = Space.lg, parent=None):
        super().__init__(parent)
        self.setObjectName("CardRaised" if raised else "Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(pad, pad, pad, pad)
        self.body.setSpacing(Space.md)
        if raised:
            _shadow(self)

    def add(self, w):
        self.body.addWidget(w)
        return w


class SectionHeader(QWidget):
    """Kicker + başlık + açıklama üçlüsü."""

    def __init__(self, kicker: str, title: str, desc: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        if kicker:
            k = QLabel(kicker.upper())
            k.setObjectName("Kicker")
            lay.addWidget(k)
        t = QLabel(title)
        t.setObjectName("H1")
        t.setWordWrap(True)
        lay.addWidget(t)
        if desc:
            d = QLabel(desc)
            d.setObjectName("Lead")
            d.setWordWrap(True)
            lay.addWidget(d)


class StatTile(QFrame):
    """Tek bir sayı / durum kutusu — büyük değer, altında etiket."""

    def __init__(self, value: str, label: str, accent: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._accent = accent or Palette.ink
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Space.lg, Space.md + 2, Space.lg, Space.md + 2)
        lay.setSpacing(2)

        self.value = QLabel(value)
        vf = QFont(); vf.setPointSizeF(23); vf.setWeight(QFont.Bold)
        self.value.setFont(vf)
        self.value.setStyleSheet(f"color: {self._accent};")

        self.label = QLabel(label)
        self.label.setObjectName("Muted")

        lay.addWidget(self.value)
        lay.addWidget(self.label)

    def set_value(self, v: str):
        self.value.setText(v)

    def set_accent(self, color: str):
        self._accent = color
        self.value.setStyleSheet(f"color: {color};")


class SettingRow(QWidget):
    """Sol: başlık + açıklama. Sağ: bir denetim (anahtar, kaydırıcı vb.)."""

    def __init__(self, title: str, desc: str, control: QWidget, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, Space.sm, 0, Space.sm)
        lay.setSpacing(Space.lg)

        left = QVBoxLayout()
        left.setSpacing(3)
        t = QLabel(title)
        t.setObjectName("H3")
        left.addWidget(t)
        self.desc = None
        if desc:
            self.desc = QLabel(desc)
            self.desc.setObjectName("Muted")
            self.desc.setWordWrap(True)
            left.addWidget(self.desc)
        lay.addLayout(left, 1)

        control.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        lay.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.control = control


class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {Palette.line}; border: none;")


class CommandRow(QWidget):
    """Sesli komut listesi satırı: sol tırnaklı komut, sağ eylem açıklaması."""

    def __init__(self, phrase: str, action: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 7, 0, 7)
        lay.setSpacing(Space.md)

        chip = QLabel(f"  “{phrase}”  ")
        cf = QFont(Type.mono.split(",")[0].strip('"'))
        cf.setPointSizeF(11.5)
        chip.setFont(cf)
        chip.setStyleSheet(
            f"background: {Palette.sunken}; color: {Palette.accent_deep};"
            f"border-radius: {Radius.sm}px; padding: 6px 4px;"
        )
        chip.setMinimumWidth(190)
        lay.addWidget(chip, 0)

        arrow = QLabel("→")
        arrow.setStyleSheet(f"color: {Palette.ink_faint};")
        lay.addWidget(arrow, 0)

        act = QLabel(action)
        act.setObjectName("Lead")
        act.setWordWrap(True)
        lay.addWidget(act, 1)
