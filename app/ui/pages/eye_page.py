"""Kafa ile kontrol — önizleme, ortalama, sesli okuma ve ayarlar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider, QComboBox,
)

from app.theme import Palette, Space, Type
from app.ui.pages.base import Page
from app.ui.widgets import (
    Card, SectionHeader, StatusPill, ToggleSwitch, SettingRow, Divider, CameraView,
)


def _slider(lo, hi, val):
    s = QSlider(Qt.Horizontal)
    s.setMinimum(lo); s.setMaximum(hi); s.setValue(val)
    s.setMinimumWidth(240)
    s.setCursor(Qt.PointingHandCursor)
    return s


class EyePage(Page):
    """Sayfa anahtarı 'eye' olarak kalır; içerik kafa kontrolüne aittir."""

    def __init__(self, state, bridge, parent=None):
        super().__init__(parent)
        self.state = state
        self.bridge = bridge
        cfg = state.eye

        self.add(SectionHeader(
            "Kafa ile Kontrol", "Kafanı çevir, imleç seni izlesin",
            "Kamera kafa duruşunu izler: hafifçe sağa bak, imleç sağa gider. "
            "Gözlerini yarım saniye kapatınca ya da bir noktada bekleyince "
            "tıklar. Kalibrasyon gerekmez; oturuşun değişirse “merkeze al” "
            "demen yeter."))

        # --- Önizleme + denetim ---
        preview = Card(raised=True)
        row = QHBoxLayout(); row.setSpacing(Space.lg)

        self.camera = CameraView()
        self.camera.setMinimumSize(360, 270)
        row.addWidget(self.camera, 3)

        side = QVBoxLayout(); side.setSpacing(Space.md)
        self.pill = StatusPill("Kapalı", "idle")
        side.addWidget(self.pill, 0, Qt.AlignLeft)

        self.hint = QLabel("Sistemi açtığında ilk saniyede şu anki duruşun "
                           "“merkez” kabul edilir. Ekranın ortasına rahatça "
                           "bakarak başla.")
        self.hint.setObjectName("Muted"); self.hint.setWordWrap(True)
        side.addWidget(self.hint)
        side.addStretch(1)

        self.center_btn = QPushButton("Ortala")
        self.center_btn.setObjectName("Ghost")
        self.center_btn.setCursor(Qt.PointingHandCursor)
        self.center_btn.setToolTip("Şu anki kafa duruşunu merkez kabul et "
                                   "(sesle: “merkeze al”)")
        self.center_btn.clicked.connect(self.bridge.recenter_head)
        side.addWidget(self.center_btn)

        self.start_btn = QPushButton("Kafa takibini başlat")
        self.start_btn.setObjectName("Primary")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._toggle)
        side.addWidget(self.start_btn)
        row.addLayout(side, 2)
        preview.body.addLayout(row)
        self.add(preview)

        # --- Otomatik Sesli Okuma ---
        read = Card()
        rh = QLabel("Otomatik Sesli Okuma"); rh.setObjectName("H3")
        read.body.addWidget(rh)
        rdesc = QLabel("İmleç bir metnin üzerinde kısa süre durunca metin "
                       "sesli okunur; tarayıcı, PDF, menü fark etmez. "
                       "Sesle de yönetilir: “oku”, “okumayı durdur”, "
                       "“otomatik okumayı aç/kapat”.")
        rdesc.setObjectName("Muted"); rdesc.setWordWrap(True)
        read.body.addWidget(rdesc)
        self.read_sw = ToggleSwitch(); self.read_sw.setChecked(cfg.auto_read)
        read.body.addWidget(SettingRow("Otomatik okuma",
                            "İmleç altındaki metni kendiliğinden oku",
                            self.read_sw))
        self.read_last = QLabel("")
        self.read_last.setObjectName("Muted"); self.read_last.setWordWrap(True)
        read.body.addWidget(self.read_last)
        self.add(read)

        # --- Ayarlar ---
        settings = Card()
        sh = QLabel("Hassasiyet ve davranış"); sh.setObjectName("H3")
        settings.body.addWidget(sh)

        self.sens = _slider(10, 100, cfg.sensitivity)
        self.smooth = _slider(0, 100, cfg.smoothing)
        self.dwell = _slider(400, 2000, cfg.dwell_ms)
        self.dwell_sw = ToggleSwitch(); self.dwell_sw.setChecked(cfg.dwell_enabled)
        self.dot_sw = ToggleSwitch(); self.dot_sw.setChecked(cfg.show_gaze_dot)
        self.magnet_sw = ToggleSwitch(); self.magnet_sw.setChecked(cfg.magnet_enabled)

        from app.vision.gestures import GESTURES, GESTURE_LABELS
        self.gesture_box = QComboBox()
        self.gesture_box.setCursor(Qt.PointingHandCursor)
        self.gesture_box.setMinimumWidth(240)
        for g in GESTURES:
            self.gesture_box.addItem(GESTURE_LABELS[g], g)
        idx = self.gesture_box.findData(cfg.click_gesture)
        self.gesture_box.setCurrentIndex(idx if idx >= 0 else 0)

        settings.add(SettingRow("İmleç hassasiyeti",
                     "Az kafa hareketiyle çok yol almak için yükselt", self.sens))
        settings.add(Divider())
        settings.add(SettingRow("Yumuşatma",
                     "Titremeyi azaltır; yüksek değer daha sakin imleç", self.smooth))
        settings.add(Divider())
        settings.add(SettingRow("Köşe mıknatısı",
                     "Köşeye yaklaşınca imleci hedefe oturt (kapat düğmesi gibi)",
                     self.magnet_sw))
        settings.add(Divider())
        settings.add(SettingRow("Bekleyerek tıklama",
                     "İmleç sabit kalınca otomatik tıkla (dwell)", self.dwell_sw))
        self.dwell_row = SettingRow("Bekleme süresi",
                     "Tıklamadan önce beklenen süre (milisaniye)", self.dwell)
        settings.add(self.dwell_row)
        settings.add(Divider())
        settings.add(SettingRow("Jest ile tıklama",
                     "Gözlerini yaklaşık yarım saniye kapalı tut: tıklar. "
                     "İmleç, gözlerin kapanmaya başladığı yerde sabitlenir",
                     self.gesture_box))
        settings.add(Divider())
        settings.add(SettingRow("Ekranda işaretçi noktası",
                     "İmlecin gideceği yeri gösteren yumuşak nokta", self.dot_sw))
        self.add(settings)

        # Bağlantılar
        self.sens.valueChanged.connect(lambda v: self._set("sensitivity", v))
        self.smooth.valueChanged.connect(lambda v: self._set("smoothing", v))
        self.dwell.valueChanged.connect(lambda v: self._set("dwell_ms", v))
        self.dwell_sw.toggled.connect(lambda v: self._set("dwell_enabled", v))
        self.gesture_box.currentIndexChanged.connect(
            lambda i: self._set("click_gesture", self.gesture_box.itemData(i)))
        self.dot_sw.toggled.connect(lambda v: self._set("show_gaze_dot", v))
        self.magnet_sw.toggled.connect(lambda v: self._set("magnet_enabled", v))
        self.read_sw.toggled.connect(self.bridge.set_auto_read)
        bridge.reader.read_started.connect(
            lambda t: self.read_last.setText(f"Son okunan: “{t[:90]}…”"
                                             if len(t) > 90 else f"Son okunan: “{t}”"))

        state.eye_active_changed.connect(lambda *_: self._sync())
        state.eye_status_changed.connect(lambda *_: self._sync())
        state.camera_ready_changed.connect(lambda *_: self._sync())

        self._sync()

    def _toggle(self):
        self.bridge.toggle_eye(not self.state.eye_active)

    def _set(self, key, value):
        setattr(self.state.eye, key, value)
        self.state.save()
        self.bridge.apply_eye_config()
        self._sync()

    def _sync(self):
        active = self.state.eye_active
        self.start_btn.setText("Kafa takibini durdur" if active
                               else "Kafa takibini başlat")
        self.center_btn.setEnabled(active)
        self.dwell.setEnabled(self.state.eye.dwell_enabled)
        self.dwell_row.setEnabled(self.state.eye.dwell_enabled)
        self.read_sw.blockSignals(True)
        self.read_sw.setChecked(self.state.eye.auto_read)
        self.read_sw.blockSignals(False)

        info = {
            "idle": ("Kapalı", "idle", False),
            "starting": ("Başlatılıyor", "busy", True),
            "tracking": ("İzliyor", "live", True),
            "no_face": ("Yüz aranıyor, kameraya dön", "warn", True),
            "error": ("Kamera açılamadı", "error", False),
        }
        text, tone, pulse = info.get(self.state.eye_status, info["idle"])
        if not active:
            text, tone, pulse = "Kapalı", "idle", False
            self.camera.clear_frame("Kafa takibi kapalı")
        self.pill.set_status(text, tone, pulse)

    # Uygulama, kamera karelerini buraya bağlar
    def show_frame(self, image):
        self.camera.set_frame(image)
