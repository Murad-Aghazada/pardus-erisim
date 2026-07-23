"""Sayfa temeli — kaydırılabilir, ortalanmış editoryal içerik sütunu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
)

from app.theme import Space


class Page(QScrollArea):
    """Dikey kaydırma + max genişlikli içerik. Alt sınıflar `self.column`e ekler."""

    MAX_WIDTH = 940

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)

        host = QWidget()
        host.setAttribute(Qt.WA_StyledBackground, False)
        outer = QHBoxLayout(host)
        outer.setContentsMargins(Space.xxl, Space.xl, Space.xxl, Space.xxl)

        self._col_wrap = QWidget()
        self._col_wrap.setMaximumWidth(self.MAX_WIDTH)
        self.column = QVBoxLayout(self._col_wrap)
        self.column.setContentsMargins(0, 0, 0, 0)
        self.column.setSpacing(Space.lg)
        self.column.setAlignment(Qt.AlignTop)

        outer.addStretch(1)
        outer.addWidget(self._col_wrap, 10)
        outer.addStretch(1)
        # Sütun doğal yüksekliğini alsın; içerik dikeyde gerilmesin
        outer.setAlignment(self._col_wrap, Qt.AlignTop)

        self.setWidget(host)

    def add(self, w):
        self.column.addWidget(w)
        return w

    def add_layout(self, lay):
        self.column.addLayout(lay)
        return lay

    def add_space(self, h: int = Space.md):
        self.column.addSpacing(h)
