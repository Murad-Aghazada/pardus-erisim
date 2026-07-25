"""
Merkezi uygulama durumu.

Tüm ekranlar buradaki tek nesneye bağlanır. Değişiklikler sinyallerle
yayılır; arayüz reaktif olarak güncellenir. Ayarlar QSettings ile diske yazılır.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from PySide6.QtCore import QObject, Signal, QSettings


@dataclass
class EyeConfig:
    sensitivity: int = 55        # 0-100, imleç hızı
    smoothing: int = 60          # 0-100, titreme bastırma
    dwell_ms: int = 900          # bekleyerek tıklama süresi
    dwell_enabled: bool = True
    # jest tıklaması, üç bağımsız yuva: long_blink|wink_left|wink_right|brow|mouth|smile|off
    # (aynı jest iki yuvaya birden atanamaz — bkz. eye_page.py)
    left_click_gesture: str = "long_blink"
    right_click_gesture: str = "off"   # isteğe bağlı: Ayarlar'dan wink_right seçilebilir
    middle_click_gesture: str = "off"
    show_gaze_dot: bool = False  # ekranda işaretçi noktası (gerçek imleç zaten görünür)
    magnet_enabled: bool = True  # köşe mıknatısı (kapat düğmesi vb.)
    auto_read: bool = False      # otomatik sesli okuma


@dataclass
class VoiceConfig:
    sensitivity: int = 60        # mikrofon eşiği
    wake_word: str = "pardus"    # tetikleyici kelime
    require_wake: bool = False   # her komuttan önce tetikleyici iste
    read_back: bool = True       # komutu sesli tekrarla (geri bildirim)
    engine: str = "auto"         # tanıma motoru: auto | whisper | vosk


class AppState(QObject):
    # Sistem açık/kapalı
    eye_active_changed = Signal(bool)
    voice_active_changed = Signal(bool)

    # Çalışma zamanı durumu
    eye_status_changed = Signal(str)      # "idle" | "starting" | "tracking" | "error"
    voice_status_changed = Signal(str)    # "idle" | "listening" | "heard" | "error"
    camera_ready_changed = Signal(bool)
    mic_ready_changed = Signal(bool)

    # Canlı veri
    gaze_moved = Signal(float, float)     # ekran oranı 0..1
    transcript_changed = Signal(str)      # son duyulan metin
    log_event = Signal(str, str)          # (tür, mesaj)

    # Yetenek durumu (kütüphane kurulu mu)
    capability_changed = Signal(str, bool)  # (ad, mevcut)

    config_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.eye = EyeConfig()
        self.voice = VoiceConfig()

        self._eye_active = False
        self._voice_active = False
        self._eye_status = "idle"
        self._voice_status = "idle"
        self._camera_ready = False
        self._mic_ready = False

        # Yetenekler — motorlar açılışta günceller
        self.capabilities: dict[str, bool] = {
            "vision": False,   # mediapipe + opencv
            "voice": False,    # vosk
            "control": False,  # pynput
        }

        self._load()

    # ---- Aktiflik ----
    @property
    def eye_active(self) -> bool:
        return self._eye_active

    def set_eye_active(self, on: bool) -> None:
        if on != self._eye_active:
            self._eye_active = on
            self.eye_active_changed.emit(on)

    @property
    def voice_active(self) -> bool:
        return self._voice_active

    def set_voice_active(self, on: bool) -> None:
        if on != self._voice_active:
            self._voice_active = on
            self.voice_active_changed.emit(on)

    # ---- Durum ----
    def set_eye_status(self, status: str) -> None:
        self._eye_status = status
        self.eye_status_changed.emit(status)

    def set_voice_status(self, status: str) -> None:
        self._voice_status = status
        self.voice_status_changed.emit(status)

    def set_camera_ready(self, ready: bool) -> None:
        if ready != self._camera_ready:
            self._camera_ready = ready
            self.camera_ready_changed.emit(ready)

    def set_mic_ready(self, ready: bool) -> None:
        if ready != self._mic_ready:
            self._mic_ready = ready
            self.mic_ready_changed.emit(ready)

    def set_capability(self, name: str, available: bool) -> None:
        self.capabilities[name] = available
        self.capability_changed.emit(name, available)

    @property
    def eye_status(self) -> str:
        return self._eye_status

    @property
    def voice_status(self) -> str:
        return self._voice_status

    @property
    def camera_ready(self) -> bool:
        return self._camera_ready

    @property
    def mic_ready(self) -> bool:
        return self._mic_ready

    # ---- Kalıcılık ----
    def _load(self) -> None:
        s = QSettings("PardusErisim", "IZ")
        for key, default in asdict(self.eye).items():
            val = s.value(f"eye/{key}", default)
            setattr(self.eye, key, _coerce(val, default))
        for key, default in asdict(self.voice).items():
            val = s.value(f"voice/{key}", default)
            setattr(self.voice, key, _coerce(val, default))

    def save(self) -> None:
        s = QSettings("PardusErisim", "IZ")
        for key, val in asdict(self.eye).items():
            s.setValue(f"eye/{key}", val)
        for key, val in asdict(self.voice).items():
            s.setValue(f"voice/{key}", val)
        s.sync()
        self.config_changed.emit()


def _coerce(value, default):
    """QSettings her şeyi string döndürebilir; tipi default'a göre düzelt."""
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    if isinstance(default, int):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return value
