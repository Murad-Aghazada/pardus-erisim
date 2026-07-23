"""Ses ile kontrol — durum, canlı deşifre, komut kataloğu ve ayarlar."""

from __future__ import annotations

from itertools import groupby

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider, QLineEdit,
    QComboBox,
)

from app.theme import Palette, Space, Type
from app.ui.pages.base import Page
from app.ui.widgets import (
    Card, SectionHeader, StatusPill, ToggleSwitch, SettingRow, Divider, CommandRow,
)
from app.voice.commands import CATALOG


class VoicePage(Page):
    def __init__(self, state, bridge, parent=None):
        super().__init__(parent)
        self.state = state
        self.bridge = bridge
        cfg = state.voice

        self.add(SectionHeader(
            "Ses ile Kontrol", "Türkçe konuş, sistem yapsın",
            "Komutlar önce cihazda, çevrimdışı çözülür; ses dışarı gitmez. "
            "Listedekine uymayan bir şey söylersen yapay zekâ devreye girer ve "
            "ne istediğini anlamaya çalışır. Serbest yazmak için “yaz” de."))

        # --- Durum + canlı deşifre ---
        live = Card(raised=True)
        top = QHBoxLayout()
        self.pill = StatusPill("Kapalı", "idle")
        top.addWidget(self.pill, 0, Qt.AlignLeft)
        top.addStretch(1)
        self.start_btn = QPushButton("Dinlemeyi başlat")
        self.start_btn.setObjectName("Primary")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._toggle)
        top.addWidget(self.start_btn, 0)
        live.body.addLayout(top)

        self.transcript = QLabel("“…”")
        tf = QFont(Type.serif.split(",")[0].strip('"'))
        tf.setPointSizeF(21)
        self.transcript.setFont(tf)
        self.transcript.setWordWrap(True)
        self.transcript.setStyleSheet(f"color: {Palette.ink}; padding: 6px 0;")
        live.body.addWidget(self.transcript)

        self.action = QLabel("Bir komut duyulunca burada görünür")
        self.action.setObjectName("Muted")
        live.body.addWidget(self.action)
        self.add(live)

        # --- Komut kataloğu ---
        cat = Card()
        head = QLabel("Komutlar"); head.setObjectName("H3")
        cat.body.addWidget(head)
        sub = QLabel("Aşağıdaki kalıpları söyleyebilirsin. Küçük söyleyiş "
                     "farkları tolere edilir.")
        sub.setObjectName("Muted"); sub.setWordWrap(True)
        cat.body.addWidget(sub)
        cat.body.addSpacing(Space.sm)

        for category, items in groupby(CATALOG, key=lambda c: c.category):
            lbl = QLabel(category.upper())
            lbl.setObjectName("Kicker")
            cat.body.addSpacing(Space.sm)
            cat.body.addWidget(lbl)
            for cmd in items:
                cat.body.addWidget(CommandRow(cmd.phrase, cmd.desc))
        self.add(cat)

        # --- Ayarlar ---
        settings = Card()
        sh = QLabel("Dinleme ayarları"); sh.setObjectName("H3")
        settings.body.addWidget(sh)

        self.sens = QSlider(Qt.Horizontal)
        self.sens.setMinimum(10); self.sens.setMaximum(100)
        self.sens.setValue(cfg.sensitivity); self.sens.setMinimumWidth(240)
        self.sens.setCursor(Qt.PointingHandCursor)

        self.wake_sw = ToggleSwitch(); self.wake_sw.setChecked(cfg.require_wake)
        self.wake_field = QLineEdit(cfg.wake_word)
        self.wake_field.setMaximumWidth(180)
        self.wake_field.setPlaceholderText("tetikleyici kelime")
        self.read_sw = ToggleSwitch(); self.read_sw.setChecked(cfg.read_back)

        self.engine_box = QComboBox()
        self.engine_box.setCursor(Qt.PointingHandCursor)
        self.engine_box.setMinimumWidth(240)
        for label, key in (("Otomatik (önerilen)", "auto"),
                           ("Whisper — yüksek doğruluk", "whisper"),
                           ("Vosk — hafif, anlık", "vosk")):
            self.engine_box.addItem(label, key)
        idx = self.engine_box.findData(cfg.engine)
        self.engine_box.setCurrentIndex(idx if idx >= 0 else 0)

        self.engine_row = SettingRow(
            "Tanıma motoru",
            f"Şu an etkin: {bridge.voice_engine_name()}. Whisper belirgin "
            "daha isabetlidir; cümle bitince ~2 sn içinde çözer.",
            self.engine_box)
        settings.add(self.engine_row)
        settings.add(Divider())
        settings.add(SettingRow("Mikrofon duyarlılığı",
                     "Sesini ne kadar kolay yakalasın", self.sens))
        settings.add(Divider())
        settings.add(SettingRow("Tetikleyici kelime iste",
                     "Her komuttan önce anahtar kelimeyi bekle", self.wake_sw))
        settings.add(SettingRow("Tetikleyici kelime",
                     "Örn: “pardus, tarayıcı aç”", self.wake_field))
        settings.add(Divider())
        settings.add(SettingRow("Komutu geri bildir",
                     "Algılanan komutu ekranda yinele", self.read_sw))
        self.add(settings)

        # Bağlantılar
        self.engine_box.currentIndexChanged.connect(
            lambda i: self._set("engine", self.engine_box.itemData(i)))
        self.sens.valueChanged.connect(lambda v: self._set("sensitivity", v))
        self.wake_sw.toggled.connect(lambda v: self._set("require_wake", v))
        self.wake_field.editingFinished.connect(
            lambda: self._set("wake_word", self.wake_field.text().strip().lower() or "pardus"))
        self.read_sw.toggled.connect(lambda v: self._set("read_back", v))

        state.voice_active_changed.connect(lambda *_: self._sync())
        state.voice_status_changed.connect(lambda *_: self._sync())
        state.transcript_changed.connect(self._on_transcript)

        self._sync()

    def _toggle(self):
        self.bridge.toggle_voice(not self.state.voice_active)

    def _set(self, key, value):
        setattr(self.state.voice, key, value)
        self.state.save()
        self.bridge.apply_voice_config()
        if key == "engine":
            self.engine_row.desc.setText(
                f"Şu an etkin: {self.bridge.voice_engine_name()}. Whisper "
                "belirgin daha isabetlidir; cümle bitince ~2 sn içinde çözer.")

    def _on_transcript(self, text: str):
        self.transcript.setText(f"“{text}”" if text else "“…”")

    def show_action(self, desc: str):
        self.action.setText(f"✓  {desc}")
        self.action.setStyleSheet(f"color: {Palette.live}; font-weight: 600;")

    def _sync(self):
        active = self.state.voice_active
        self.start_btn.setText("Dinlemeyi durdur" if active else "Dinlemeyi başlat")
        info = {
            "idle": ("Kapalı", "idle", False),
            "starting": ("Hazırlanıyor (ilk açılışta model yüklenir)", "busy", True),
            "listening": ("Dinliyor", "live", True),
            "heard": ("Algılandı", "live", True),
            "no_lib": ("Ses kütüphanesi kurulu değil", "error", False),
            "no_model": ("Türkçe model bulunamadı", "warn", False),
            "error": ("Mikrofon açılamadı", "error", False),
        }
        text, tone, pulse = info.get(self.state.voice_status, info["idle"])
        if not active and self.state.voice_status in ("idle", "listening", "heard"):
            text, tone, pulse = "Kapalı", "idle", False
        self.pill.set_status(text, tone, pulse)

        if self.state.voice_status == "no_model":
            self.action.setText("Türkçe model bulunamadı. Whisper ilk kullanımda "
                                "kendi modelini indirir; Vosk için: sh install-pardus.sh")
            self.action.setStyleSheet(f"color: {Palette.warn}; font-weight: 600;")
        elif self.state.voice_status == "no_lib":
            self.action.setText("Kurulum: pip install faster-whisper sounddevice "
                                "(ya da: sh install-pardus.sh)")
            self.action.setStyleSheet(f"color: {Palette.danger}; font-weight: 600;")
