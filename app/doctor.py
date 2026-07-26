"""
Sistem doktoru — `python3 main.py --doctor`

Uygulama bir makinede (özellikle taze Linux/Pardus kurulumunda ya da sanal
makinede) çalışmadığında nedenini TEK TEK bulur ve Türkçe çözüm önerir.
Arayüz açılmadan çalışır; Qt platform eklentisi yüklenemese bile teşhis koyar.
"""

from __future__ import annotations

import ctypes.util
import importlib.util
import os
import platform
import shutil
import sys

OK, WARN, FAIL = "TAMAM", "UYARI", "SORUN"
_results: list[tuple[str, str, str]] = []


def _add(level: str, name: str, hint: str = ""):
    _results.append((level, name, hint))


def _have(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def _check_python():
    v = sys.version_info
    if v >= (3, 10):
        _add(OK, f"Python {v.major}.{v.minor}")
    else:
        _add(FAIL, f"Python {v.major}.{v.minor} çok eski",
             "Python 3.10+ gerekir (Pardus 23'te python3 zaten uygundur)")


def _check_display():
    if platform.system() != "Linux":
        return
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        _add(FAIL, "Grafik oturumu yok (DISPLAY boş)",
             "Uygulamayı masaüstü oturumunun İÇİNDEN çalıştır (SSH'tan değil)")
    elif os.environ.get("XDG_SESSION_TYPE") == "wayland":
        _add(WARN, "Wayland oturumu",
             "Wayland, güvenlik gereği hiçbir uygulamanın ekranın geri "
             "kalanında imleci sürmesine/tıklamasına izin vermez. Pardus "
             "Erişim bunu, çekirdek seviyesinde sanal bir fare (/dev/uinput) "
             "oluşturarak aşar — Xorg'a geçmen GEREKMEZ. Aşağıdaki "
             "'sanal fare izni' denetimine bak; SORUN diyorsa tek seferlik "
             "kurulum gerekiyor demektir (sh install-pardus.sh).")
    else:
        _add(OK, "X11 grafik oturumu")


def _check_uinput_permission():
    """Wayland'da fare kontrolü için gereken /dev/uinput yazma izni."""
    if platform.system() != "Linux":
        return
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        return  # X11'de pynput zaten çalışır, uinput gerekmez
    if not _have("evdev"):
        _add(WARN, "Sanal fare (uinput) — evdev kitaplığı eksik",
             "pip install evdev")
        return
    uinput_ok = os.path.exists("/dev/uinput") and os.access("/dev/uinput", os.W_OK)
    if uinput_ok:
        _add(OK, "Sanal fare izni (uinput) — Wayland'da fare kontrolü çalışır")
    else:
        _add(WARN, "Sanal fare izni (uinput) yok — Wayland'da fare/tıklama çalışmaz",
             "Tek seferlik kurulum: sh install-pardus.sh (udev kuralı + "
             "'input' grubu ekler). Elle kurulum: "
             "echo 'KERNEL==\"uinput\", GROUP=\"input\", MODE=\"0660\"' | "
             "sudo tee /etc/udev/rules.d/99-pardus-erisim-uinput.rules && "
             "sudo udevadm control --reload-rules && sudo udevadm trigger && "
             "sudo usermod -aG input $USER — SONRA OTURUMU KAPAT/AÇ "
             "(grup üyeliği yeni girişte etkinleşir).")


def _check_qt_libs():
    """Qt'nin xcb eklentisinin istediği sistem kitaplıkları (pip kuramaz)."""
    if platform.system() != "Linux":
        _add(OK, "Qt sistem kitaplıkları (Windows/macOS: gömülü)")
        return
    needed = {
        "xcb-cursor": "libxcb-cursor0",   # Qt >= 6.5 için ZORUNLU
        "GL": "libgl1",
        "EGL": "libegl1",
        "xkbcommon-x11": "libxkbcommon-x11-0",
        "dbus-1": "libdbus-1-3",
    }
    missing = [pkg for lib, pkg in needed.items()
               if ctypes.util.find_library(lib) is None]
    if missing:
        _add(FAIL, "Qt sistem kitaplıkları eksik (arayüz hiç açılmaz!)",
             "sudo apt install -y " + " ".join(missing))
    else:
        _add(OK, "Qt sistem kitaplıkları")


def _check_pyside():
    if not _have("PySide6"):
        _add(FAIL, "PySide6 kurulu değil", "pip install PySide6")
        return
    _add(OK, "PySide6")


def _check_audio():
    if not _have("sounddevice"):
        _add(WARN, "sounddevice kurulu değil", "pip install sounddevice")
        return
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        ins = [d for d in devs if d.get("max_input_channels", 0) > 0]
        if ins:
            _add(OK, f"Mikrofon ({len(ins)} giriş aygıtı)")
        else:
            _add(WARN, "Mikrofon aygıtı görünmüyor",
                 "Sanal makinede: ses girişini VM ayarlarından etkinleştir")
    except OSError:
        _add(FAIL, "PortAudio sistem kitaplığı yok (ses tanıma çalışmaz)",
             "sudo apt install -y libportaudio2")


def _check_camera():
    if not _have("cv2"):
        _add(WARN, "OpenCV kurulu değil (kafa kontrolü çalışmaz)",
             "pip install opencv-python  (Linux'ta ayrıca: sudo apt install -y libgl1)")
        return
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            _add(OK, "Kamera (aygıt 0)")
            cap.release()
        else:
            _add(WARN, "Kamera açılamadı",
                 "Sanal makinede: VirtualBox → Aygıtlar → Web Kameraları → "
                 "kamerayı bağla (Guest Additions gerekir); "
                 "VMware → VM → Removable Devices → kamera")
    except Exception:
        _add(WARN, "Kamera denetimi başarısız", "")


def _check_vision():
    if _have("mediapipe"):
        _add(OK, "MediaPipe")
    else:
        _add(WARN, "MediaPipe kurulu değil (kafa kontrolü çalışmaz)",
             "pip install mediapipe")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    task = os.path.join(root, "models", "face_landmarker.task")
    if os.path.isfile(task) and os.path.getsize(task) > 1_000_000:
        _add(OK, "Yüz modeli (face_landmarker.task)")
    else:
        _add(WARN, "Yüz modeli henüz inmemiş",
             "Kafa/göz takibi için gereken dosya bilgisayarında yok. Sorun "
             "değil: Kafa Kontrolü'nü ilk açışında kendiliğinden inecek "
             "(internet bağlantısı gerekir, birkaç saniye sürer).")


def _check_voice_models():
    has_w = _have("faster_whisper")
    if has_w:
        _add(OK, "Whisper motoru (faster-whisper) — yüksek doğruluk")
    else:
        _add(WARN, "faster-whisper kurulu değil",
             "pip install faster-whisper  (ilk kullanımda ~460 MB model iner)")
    if not _have("vosk"):
        if has_w:
            _add(WARN, "Vosk kurulu değil (yedek motor — gerekli değil)",
                 "Zaten daha isabetli olan Whisper motorunu kullanıyorsun, "
                 "bu eksik seni etkilemez. Vosk yalnızca Whisper'ın "
                 "çalışmadığı zayıf donanımlarda yedek olarak gerekir: "
                 "pip install vosk")
        else:
            _add(WARN, "Vosk kurulu değil (çevrimdışı yedek motor)",
                 "Whisper de kurulu değil; sesli komutlar hiç çalışmaz. "
                 "En az birini kur: pip install faster-whisper  (önerilen) "
                 "ya da pip install vosk")
        return
    try:
        from app.voice.recognizer import find_model
        if find_model():
            _add(OK, "Vosk Türkçe modeli")
        elif has_w:
            _add(WARN, "Vosk Türkçe modeli yok (önemli değil)",
                 "Whisper zaten kurulu ve devrede; bu yalnız Ayarlar'dan "
                 "motoru elle 'vosk' yaparsan gerekir. İndirme adresi: "
                 "https://alphacephei.com/vosk/models → vosk-model-small-tr-0.3 "
                 "→ models/ klasörüne aç (install-pardus.sh bunu kendisi yapar)")
        else:
            _add(WARN, "Vosk Türkçe modeli yok",
                 "Sesli komutlar bu model olmadan çalışmaz. İndir: "
                 "https://alphacephei.com/vosk/models → vosk-model-small-tr-0.3 "
                 "→ models/ klasörüne aç (install-pardus.sh bunu kendisi yapar)")
    except Exception:
        _add(WARN, "Vosk model denetimi başarısız", "")


def _check_control():
    if not _have("pynput"):
        _add(FAIL, "pynput kurulu değil (imleç/klavye kontrolü yok)",
             "pip install pynput")
    else:
        _add(OK, "Sistem denetimi (pynput)")


def _check_tts():
    if platform.system() == "Linux" and not shutil.which("spd-say"):
        _add(WARN, "speech-dispatcher yok",
             "Sesli okuma (metni Türkçe seslendirme) bu sistem servisini "
             "kullanır; kurulu değilse yazılar ekranda görünür ama sesli "
             "okunmaz. Kur: sudo apt install -y speech-dispatcher")
    else:
        _add(OK, "Sesli okuma altyapısı")


def _check_assist():
    try:
        from app.assist.gemini_client import has_key
        if has_key():
            _add(OK, "Gemini API anahtarı")
        else:
            _add(WARN, "Gemini anahtarı yok",
                 "Anahtar olmadan yalnız şunlar çalışmaz: Asistan sohbeti ve "
                 "hazır listede olmayan doğal sesli isteklerin ('youtube'da "
                 "kedi videoları aç' gibi) akıllı çözümü. Kafa/göz kontrolü "
                 "ve temel sesli komutlar bundan etkilenmez. Eklemek için: "
                 "Ayarlar ekranı → Gemini API anahtarı kutusuna yapıştır → "
                 "Kaydet.")
    except Exception:
        _add(WARN, "Asistan denetimi başarısız", "")


def run() -> int:
    print("Pardus Erişim — sistem doktoru\n" + "=" * 46)
    for fn in (_check_python, _check_display, _check_uinput_permission,
               _check_qt_libs, _check_pyside,
               _check_audio, _check_camera, _check_vision, _check_voice_models,
               _check_control, _check_tts, _check_assist):
        try:
            fn()
        except Exception as exc:
            _add(WARN, f"{fn.__name__} beklenmedik hata: {exc}", "")

    fails = 0
    for level, name, hint in _results:
        mark = {OK: "  +", WARN: "  !", FAIL: "  X"}[level]
        print(f"{mark} [{level:5s}] {name}")
        if hint:
            print(f"            → {hint}")
        fails += (level == FAIL)

    print("=" * 46)
    if fails:
        print(f"{fails} engelleyici sorun var. Yukarıdaki → satırlarını uygula.")
        print("Pardus/Debian'da tek komutla: sh install-pardus.sh")
    else:
        print("Engelleyici sorun yok. Başlat: python3 main.py")
    return 1 if fails else 0
