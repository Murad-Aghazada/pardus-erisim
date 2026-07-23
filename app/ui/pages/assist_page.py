"""Asistan — Gemini destekli sohbet. Yazarak ya da sesle soru sorulur."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLineEdit, QSizePolicy,
)

from app.theme import Palette, Space, Type, Radius
from app.ui.pages.base import Page
from app.ui.widgets import Card, SectionHeader, StatusPill, ToggleSwitch, SettingRow


class Bubble(QWidget):
    """Tek konuşma balonu."""

    def __init__(self, text: str, who: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setMaximumWidth(560)

        if who == "user":
            lbl.setStyleSheet(
                f"background: {Palette.accent_soft}; color: {Palette.accent_deep};"
                f"border-radius: {Radius.md}px; padding: 12px 16px;"
                f"font-size: {Type.body}px;")
            lay.addStretch(1)
            lay.addWidget(lbl, 0)
        elif who == "assistant":
            f = QFont(Type.serif.split(",")[0].strip('"'))
            f.setPointSizeF(12.5)
            lbl.setFont(f)
            lbl.setStyleSheet(
                f"background: {Palette.surface_raised}; color: {Palette.ink};"
                f"border: 1px solid {Palette.line};"
                f"border-radius: {Radius.md}px; padding: 12px 16px;")
            lay.addWidget(lbl, 0)
            lay.addStretch(1)
        else:  # sistem notu
            lbl.setStyleSheet(f"color: {Palette.ink_faint}; font-size: {Type.small}px;")
            lay.addStretch(1)
            lay.addWidget(lbl, 0)
            lay.addStretch(1)


class AssistPage(Page):
    def __init__(self, state, bridge, parent=None):
        super().__init__(parent)
        self.state = state
        self.bridge = bridge

        self.add(SectionHeader(
            "Asistan", "Sor, anlatsın; söyle, yapsın",
            "Yapay zekâ asistanına yazarak ya da sesle ulaş. Ses açıkken "
            "“asistan” deyip sorunu sor; yanıt burada belirir ve sesli okunur."))

        # Sohbet alanı
        self.chat_card = Card(raised=True)
        self.chat_col = self.chat_card.body
        self.chat_col.setSpacing(Space.sm)
        self._empty = QLabel("Henüz konuşma yok. Aşağıdan yaz ya da sesle "
                             "“asistan saat kaç” gibi bir soru sor.")
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        self.chat_col.addWidget(self._empty)
        self.add(self.chat_card)

        # Giriş satırı
        input_card = Card()
        row = QHBoxLayout()
        row.setSpacing(Space.sm)
        self.field = QLineEdit()
        self.field.setPlaceholderText("Asistana bir şey sor…")
        self.field.returnPressed.connect(self._send)
        row.addWidget(self.field, 1)
        self.send_btn = QPushButton("Gönder")
        self.send_btn.setObjectName("Primary")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn, 0)
        input_card.body.addLayout(row)

        opts = QHBoxLayout()
        self.pill = StatusPill("Hazır", "idle")
        opts.addWidget(self.pill, 0, Qt.AlignLeft)
        opts.addStretch(1)
        speak_lbl = QLabel("Yanıtları sesli oku")
        speak_lbl.setObjectName("Muted")
        self.speak_sw = ToggleSwitch()
        self.speak_sw.setChecked(bridge.speak_replies)
        self.speak_sw.toggled.connect(bridge.set_speak_replies)
        opts.addWidget(speak_lbl, 0)
        opts.addWidget(self.speak_sw, 0)
        input_card.body.addLayout(opts)
        self.add(input_card)

        self._busy = False
        self._sync_ready()

    # ---- Dışarıdan çağrılır ----
    def add_user(self, text: str):
        self._clear_empty()
        self.chat_col.addWidget(Bubble(text, "user"))
        self._scroll_end()

    def add_reply(self, text: str):
        self._clear_empty()
        self.chat_col.addWidget(Bubble(text, "assistant"))
        self._busy = False
        self._sync_ready()
        self._scroll_end()

    def add_note(self, text: str):
        self._clear_empty()
        self.chat_col.addWidget(Bubble(text, "note"))
        self._busy = False
        self._sync_ready()
        self._scroll_end()

    def set_busy(self):
        self._busy = True
        self.pill.set_status("Düşünüyor", "busy", True)
        self.send_btn.setEnabled(False)

    # ---- İç ----
    def _send(self):
        text = self.field.text().strip()
        if not text or self._busy:
            return
        self.field.clear()
        self.bridge.ask_assistant(text)

    def _sync_ready(self):
        from app.assist.gemini_client import has_key
        if has_key():
            self.pill.set_status("Hazır", "live")
            self.send_btn.setEnabled(True)
        else:
            self.pill.set_status("API anahtarı gerekli (Ayarlar)", "warn")
            self.send_btn.setEnabled(False)

    def _clear_empty(self):
        if self._empty is not None:
            self._empty.deleteLater()
            self._empty = None

    def _scroll_end(self):
        QTimer.singleShot(60, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()))
