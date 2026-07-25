"""Ayarlar — bileşen durumu, kısayollar ve uygulama bilgisi."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton

from app.theme import Palette, Space
from app.ui.pages.base import Page
from app.ui.widgets import Card, SectionHeader, StatusPill, Divider


class _CapRow(QHBoxLayout):
    def __init__(self, title, hint):
        super().__init__()
        self.setSpacing(Space.md)
        box = QVBoxLayout(); box.setSpacing(2)
        t = QLabel(title); t.setObjectName("H3")
        self.hint = QLabel(hint); self.hint.setObjectName("Muted"); self.hint.setWordWrap(True)
        box.addWidget(t); box.addWidget(self.hint)
        self.addLayout(box, 1)
        self.pill = StatusPill("Denetleniyor", "idle")
        self.addWidget(self.pill, 0, Qt.AlignRight | Qt.AlignVCenter)

    def set(self, ok, ok_text, bad_text, bad_hint=None):
        if ok:
            self.pill.set_status(ok_text, "live")
        else:
            self.pill.set_status(bad_text, "warn")
            if bad_hint:
                self.hint.setText(bad_hint)


class SettingsPage(Page):
    def __init__(self, state, bridge, parent=None):
        super().__init__(parent)
        self.state = state
        self.bridge = bridge

        self.add(SectionHeader(
            "Ayarlar", "Sistem ve bileşenler",
            "Erişilebilirlik motorlarının çalışması için gereken bileşenlerin "
            "durumu ve genel tercihler."))

        # Bileşen durumu
        caps = Card()
        h = QLabel("Bileşen durumu"); h.setObjectName("H3")
        caps.body.addWidget(h)
        caps.body.addSpacing(Space.xs)

        self.row_vision = _CapRow(
            "Görü motoru",
            "Göz izleme için MediaPipe ve OpenCV gerekir.")
        self.row_voice = _CapRow(
            "Ses motoru",
            "Türkçe komutlar için Vosk ve sounddevice gerekir.")
        self.row_control = _CapRow(
            "Sistem denetimi",
            "İmleç ve klavye kontrolü için pynput gerekir.")
        self.row_assist = _CapRow(
            "Yapay zekâ asistanı",
            "Sohbet ve akıllı komut çözümleme için Gemini anahtarı gerekir.")

        for i, row in enumerate((self.row_vision, self.row_voice,
                                 self.row_control, self.row_assist)):
            if i:
                caps.body.addWidget(Divider())
            caps.body.addLayout(row)
        self.add(caps)

        # Gemini API anahtarı
        keycard = Card()
        kh = QLabel("Gemini API anahtarı"); kh.setObjectName("H3")
        keycard.body.addWidget(kh)
        kd = QLabel("Asistan ve akıllı ses komutları bu anahtarı kullanır. "
                    "Anahtar yalnızca bu bilgisayarda, config.json içinde tutulur.")
        kd.setObjectName("Muted"); kd.setWordWrap(True)
        keycard.body.addWidget(kd)
        krow = QHBoxLayout(); krow.setSpacing(Space.sm)
        self.key_field = QLineEdit()
        self.key_field.setEchoMode(QLineEdit.Password)
        self.key_field.setPlaceholderText("API anahtarını buraya yapıştır")
        from app.assist import config as assist_config
        if assist_config.load().get("gemini_api_key"):
            self.key_field.setText(assist_config.load()["gemini_api_key"])
        krow.addWidget(self.key_field, 1)
        save_btn = QPushButton("Kaydet")
        save_btn.setObjectName("Ghost")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save_key)
        krow.addWidget(save_btn, 0)
        keycard.body.addLayout(krow)
        self.add(keycard)

        # Kurulum ipucu
        install = Card()
        ih = QLabel("Kurulum"); ih.setObjectName("H3")
        install.body.addWidget(ih)
        tip = QLabel("Tüm bileşenler için:\n"
                     "pip install -r requirements.txt\n\n"
                     "Türkçe ses modeli, alphacephei.com/vosk/models adresinden "
                     "(vosk-model-small-tr) indirilip proje içindeki models/ "
                     "klasörüne açılır.")
        tip.setObjectName("Lead"); tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {Palette.ink_soft}; font-family: monospace;")
        install.body.addWidget(tip)
        self.add(install)

        # Güvenlik / durdurma
        safety = Card()
        sh = QLabel("Güvenli durdurma"); sh.setObjectName("H3")
        safety.body.addWidget(sh)
        st = QLabel("Her iki sistemi anında kapatmak için sağ üstteki durdurma düğmesini "
                    "kullan ya da menüden kapat. Kontrolü kaybettiğini hissedersen "
                    "klavye her zaman önceliklidir.")
        st.setObjectName("Lead"); st.setWordWrap(True)
        safety.body.addWidget(st)
        self.add(safety)

        # Hakkında
        about = Card()
        ah = QLabel("Hakkında"); ah.setObjectName("H3")
        about.body.addWidget(ah)
        at = QLabel("Pardus Erişim. Bakış ve sesle bilgisayar kullanımı.\n"
                    "TEKNOFEST · Pardus İşletim Sistemi kategorisi için geliştirildi.\n"
                    "Sürüm 1.0")
        at.setObjectName("Lead"); at.setWordWrap(True)
        about.body.addWidget(at)
        self.add(about)

        state.capability_changed.connect(lambda *_: self._sync())
        self._sync()

    def _save_key(self):
        self.bridge.set_api_key(self.key_field.text())
        self._sync()
        # asistan sayfasındaki hazır durumunu da tazele
        if self.bridge.window and "assist" in self.bridge.window.pages:
            self.bridge.window.pages["assist"]._sync_ready()

    def _sync(self):
        c = self.state.capabilities
        self.row_vision.set(c.get("vision"), "Hazır", "Kurulu değil",
                            "Kafa/göz ile fare kontrolü bu bileşenler olmadan "
                            "açılmaz. Kur: pip install mediapipe opencv-python")
        self.row_voice.set(c.get("voice"), "Hazır", "Kurulu değil",
                           "Sesli komutlar bu bileşenler olmadan çalışmaz. "
                           "Kur (önerilen, yüksek doğruluk): "
                           "pip install faster-whisper sounddevice — ya da "
                           "hafif yedek: pip install vosk sounddevice")
        control = self.bridge.control
        if c.get("control") and getattr(control, "wayland_limited", False):
            if getattr(control, "using_uinput", False):
                self.row_control.pill.set_status("Hazır (Wayland: sanal fare)", "live")
                self.row_control.hint.setText(
                    "Bu oturum Wayland; normalde imleç kontrolü çalışmaz ama "
                    "sanal fare (uinput) izni kurulu olduğu için fare/tıklama "
                    "burada da çalışıyor. Bir şey yapmana gerek yok.")
            else:
                self.row_control.pill.set_status("Kısıtlı (Wayland)", "warn")
                self.row_control.hint.setText(
                    "Bu oturum Wayland; güvenlik gereği fare imleci başka "
                    "pencerelerde sürülemez/tıklanamaz ve gerçek farenle "
                    "çakışabilir. Düzeltmek için sanal fare izni gerekir "
                    "(oturum türünü değiştirmen GEREKMEZ) — adım adım rehber: "
                    "Yardım sayfası → “Fare/imleç çalışmıyor?” bölümü.")
        else:
            self.row_control.set(c.get("control"), "Hazır", "Kurulu değil",
                                 "İmleç ve klavye kontrolü bu bileşen olmadan "
                                 "çalışmaz. Kur: pip install pynput")
        self.row_assist.set(c.get("assist"), "Hazır", "Anahtar yok",
                            "Asistan sohbeti ve listede olmayan doğal sesli "
                            "isteklerin akıllı çözümü için Gemini API anahtarı "
                            "gerekir. Aşağıya yapıştırıp Kaydet'e bas — kalan "
                            "her şey (kafa/göz, temel sesli komutlar) anahtarsız "
                            "da çalışır.")
