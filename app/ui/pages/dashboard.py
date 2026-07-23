"""Genel bakış — iki ana sistemin açılıp kapatıldığı karşılama ekranı."""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGridLayout, QSizePolicy,
)

from app.theme import Palette, Space, Type
from app.ui.pages.base import Page
from app.ui.widgets import Card, StatusPill, ToggleSwitch, StatTile


class Emblem(QWidget):
    """Küçük, çizilmiş amblem: 'eye' (göz) veya 'wave' (ses)."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(64, 64)
        self._active = False

    def set_active(self, on: bool):
        self._active = on
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(Palette.accent) if self._active else QColor(Palette.ink_soft)
        cx, cy = 32, 32
        if self.kind == "eye":
            pen = QPen(col, 2.4); pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            path = QRectF(8, 14, 48, 36)
            p.drawArc(path, 20 * 16, 140 * 16)
            p.drawArc(path, 200 * 16, 140 * 16)
            p.setBrush(col); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), 7, 7)
            p.setBrush(QColor(Palette.surface))
            p.drawEllipse(QPointF(cx + 2, cy - 2), 2.2, 2.2)
        else:  # wave
            pen = QPen(col, 2.4); pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(20, cy), 4, 4)
            for i, r in enumerate((11, 19, 27)):
                c = QColor(col); c.setAlphaF(1.0 - i * 0.28)
                pen.setColor(c); p.setPen(pen)
                p.drawArc(QRectF(20 - r, cy - r, 2 * r, 2 * r), -55 * 16, 110 * 16)


class SystemCard(Card):
    """Bir erişim sistemini gösteren büyük kart: durum + anahtar + ayar."""

    def __init__(self, kind: str, title: str, desc: str, bridge, page_key: str, parent=None):
        super().__init__(raised=True, pad=Space.lg + 2, parent=parent)
        self.bridge = bridge
        self.page_key = page_key
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        top = QHBoxLayout()
        top.setSpacing(Space.md)
        self.emblem = Emblem(kind)
        top.addWidget(self.emblem, 0, Qt.AlignTop)

        head = QVBoxLayout(); head.setSpacing(4)
        t = QLabel(title); t.setObjectName("H2")
        d = QLabel(desc); d.setObjectName("Muted"); d.setWordWrap(True)
        head.addWidget(t); head.addWidget(d)
        top.addLayout(head, 1)
        self.body.addLayout(top)

        self.pill = StatusPill("Kapalı", "idle")
        self.body.addWidget(self.pill, 0, Qt.AlignLeft)

        self.body.addStretch(1)

        row = QHBoxLayout()
        self.toggle = ToggleSwitch()
        state_lbl = QLabel("Sistemi aç")
        state_lbl.setObjectName("H3")
        self._state_lbl = state_lbl
        row.addWidget(self.toggle, 0)
        row.addWidget(state_lbl, 0)
        row.addStretch(1)
        cfg = QPushButton("Ayarla  →")
        cfg.setObjectName("Ghost")
        cfg.setCursor(Qt.PointingHandCursor)
        cfg.clicked.connect(lambda: self.bridge.navigate(self.page_key))
        row.addWidget(cfg, 0)
        self.body.addLayout(row)

    def reflect(self, active: bool, status_text: str, tone: str, pulse=False):
        self.toggle.blockSignals(True)
        self.toggle.setChecked(active)
        self.toggle.blockSignals(False)
        self.emblem.set_active(active)
        self._state_lbl.setText("Sistem açık" if active else "Sistemi aç")
        self.pill.set_status(status_text, tone, pulse)


class DashboardPage(Page):
    def __init__(self, state, bridge, parent=None):
        super().__init__(parent)
        self.state = state
        self.bridge = bridge

        # Başlık
        head = QVBoxLayout(); head.setSpacing(6)
        k = QLabel("PARDUS ERİŞİM"); k.setObjectName("Kicker")
        title = QLabel("Küçük bir kafa hareketi,\nbir söz yeter.")
        title.setObjectName("Display")
        lead = QLabel("Fareye ya da klavyeye ihtiyaç duymadan Pardus'u kullan. "
                      "Kafanla imleci taşı, göz kırparak tıkla, Türkçe konuşarak "
                      "komut ver. Ekrandaki metinler sana okunsun.")
        lead.setObjectName("Lead"); lead.setWordWrap(True)
        head.addWidget(k); head.addWidget(title); head.addWidget(lead)
        self.add_layout(head)
        self.add_space(Space.sm)

        # İki sistem kartı
        cards = QHBoxLayout(); cards.setSpacing(Space.lg)
        self.eye_card = SystemCard(
            "eye", "Kafa ile Kontrol",
            "Kafanı hafifçe çevir; imleç seni izler. Gözlerini yarım saniye "
            "kapatınca ya da bekleyince tıklar. Kalibrasyon gerekmez.",
            bridge, "eye")
        self.voice_card = SystemCard(
            "wave", "Ses ile Kontrol",
            "Türkçe komutları çevrimdışı anlar. "
            "“tıkla”, “yaz ...”, “tarayıcı aç” gibi.",
            bridge, "voice")
        cards.addWidget(self.eye_card)
        cards.addWidget(self.voice_card)
        self.add_layout(cards)

        # İstatistik şeridi
        self.add_space(Space.sm)
        grid = QGridLayout(); grid.setSpacing(Space.md)
        self.tile_mode = StatTile("Klavyesiz", "Etkileşim yöntemi")
        self.tile_cal = StatTile("Anında", "Kurulum, kalibrasyonsuz")
        from app.voice.commands import CATALOG
        self.tile_cmd = StatTile(str(len(CATALOG)), "Türkçe komut")
        self.tile_lat = StatTile("Çevrimdışı", "Ses tanıma")
        for i, t in enumerate((self.tile_mode, self.tile_cal, self.tile_cmd, self.tile_lat)):
            grid.addWidget(t, 0, i)
        self.add_layout(grid)

        # Bağlantılar
        state.eye_active_changed.connect(self._sync)
        state.voice_active_changed.connect(self._sync)
        state.eye_status_changed.connect(lambda *_: self._sync())
        state.voice_status_changed.connect(lambda *_: self._sync())
        self.eye_card.toggle.toggled.connect(bridge.toggle_eye)
        self.voice_card.toggle.toggled.connect(bridge.toggle_voice)
        self._sync()

    def _sync(self):
        eye_map = {
            "idle": ("Kapalı", "idle", False),
            "starting": ("Başlatılıyor", "busy", True),
            "tracking": ("Takip ediyor", "live", True),
            "no_face": ("Yüz aranıyor", "warn", True),
            "error": ("Kamera yok", "error", False),
        }
        va_map = {
            "idle": ("Kapalı", "idle", False),
            "starting": ("Başlatılıyor", "busy", True),
            "listening": ("Dinliyor", "live", True),
            "heard": ("Dinliyor", "live", True),
            "no_lib": ("Kütüphane yok", "error", False),
            "no_model": ("Model gerekli", "warn", False),
            "error": ("Mikrofon yok", "error", False),
        }
        et, etone, ep = eye_map.get(self.state.eye_status, eye_map["idle"])
        if not self.state.eye_active:
            et, etone, ep = "Kapalı", "idle", False
        self.eye_card.reflect(self.state.eye_active, et, etone, ep)

        vt, vtone, vp = va_map.get(self.state.voice_status, va_map["idle"])
        if not self.state.voice_active:
            vt, vtone, vp = "Kapalı", "idle", False
        self.voice_card.reflect(self.state.voice_active, vt, vtone, vp)
