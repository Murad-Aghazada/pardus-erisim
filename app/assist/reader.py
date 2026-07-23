"""
Otomatik Sesli Okuma.

İmleç (kafa işaretçisi, sesli komut ya da fiziksel fare) bir metnin üzerinde
kısa süre durunca, imlecin çevresindeki ekran bölgesi yakalanır, metin
çıkarılır (OCR) ve sesli okunur. Görme güçlüğü olan kullanıcı için ekrandaki
HER metin — tarayıcı, PDF, menü — erişilebilir hale gelir.

Metin çıkarma: yerel tesseract varsa o (çevrimdışı, Pardus: apt install
tesseract-ocr tesseract-ocr-tur), yoksa Gemini görüntü okuma kullanılır.
"""

from __future__ import annotations

import base64
import shutil

from PySide6.QtCore import QObject, QThread, QTimer, Signal, QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication, QCursor


HOVER_MS = 1300          # okumayı tetikleyen bekleme
REGION_W, REGION_H = 640, 260
MOVE_EPS = 45            # bundan az hareket "duruyor" sayılır
RETRIGGER_DIST = 200     # yeniden okuma için uzaklaşma eşiği
COOLDOWN_MS = 4000


def local_ocr_available() -> bool:
    if not shutil.which("tesseract"):
        return False
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


class OcrTask(QThread):
    """PNG baytlarından metin çıkarır (yerel tesseract ya da Gemini görüntü)."""

    done = Signal(str)
    failed = Signal(str)

    def __init__(self, png_bytes: bytes, parent=None):
        super().__init__(parent)
        self._png = png_bytes

    def run(self):
        if local_ocr_available():
            try:
                import io
                import pytesseract
                from PIL import Image
                img = Image.open(io.BytesIO(self._png))
                text = pytesseract.image_to_string(img, lang="tur+eng")
                self.done.emit(text.strip())
                return
            except Exception:
                pass  # Gemini'ye düş

        try:
            import requests
            from app.assist import config
            cfg = config.load()
            key = cfg.get("gemini_api_key", "").strip()
            if not key:
                self.failed.emit("no_key")
                return
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{cfg.get('gemini_model', 'gemini-2.5-flash')}:generateContent")
            body = {
                "contents": [{"parts": [
                    {"text": ("Bu ekran görüntüsündeki okunabilir metni çıkar. "
                              "SADECE metnin kendisini döndür; açıklama, biçim, "
                              "madde işareti ekleme. Okunabilir metin yoksa boş döndür.")},
                    {"inlineData": {"mimeType": "image/png",
                                    "data": base64.b64encode(self._png).decode()}},
                ]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800},
            }
            r = requests.post(url, params={"key": key}, json=body, timeout=30)
            if r.status_code != 200:
                self.failed.emit(f"http_{r.status_code}")
                return
            cand = (r.json().get("candidates") or [{}])[0]
            parts = cand.get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            self.done.emit(text)
        except Exception:
            self.failed.emit("network")


class ReadAloud(QObject):
    """İmleç-altı metni izleyip okuyan yönetici."""

    read_started = Signal(str)     # okunan metin (arayüz gösterimi)
    state_changed = Signal(bool)   # otomatik mod açık/kapalı

    def __init__(self, speaker, parent=None):
        super().__init__(parent)
        self.speaker = speaker
        self.auto_enabled = False

        self._last_pos = None
        self._still_since = None
        self._last_read_pos = None
        self._last_text = ""
        self._cooldown = QTimer(self)
        self._cooldown.setSingleShot(True)
        self._task = None

        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    # ---- Dış denetim ----
    def set_auto(self, on: bool):
        self.auto_enabled = bool(on)
        self.state_changed.emit(self.auto_enabled)
        if not on:
            self.speaker.stop()

    def read_now(self):
        """Sesli 'oku' komutu: imleç neredeyse orayı hemen oku."""
        self._trigger(force=True)

    def stop(self):
        self.speaker.stop()

    # ---- İç ----
    def _poll(self):
        if not self.auto_enabled:
            return
        import time
        pos = QCursor.pos()
        now = time.monotonic()
        if self._last_pos is None:
            self._last_pos, self._still_since = pos, now
            return
        moved = (abs(pos.x() - self._last_pos.x()) > MOVE_EPS
                 or abs(pos.y() - self._last_pos.y()) > MOVE_EPS)
        if moved:
            self._last_pos, self._still_since = pos, now
            return
        # duruyor: yeterince bekledi mi, yeni bir bölge mi?
        if (now - self._still_since) * 1000 >= HOVER_MS:
            if self._last_read_pos is not None:
                dx = pos.x() - self._last_read_pos.x()
                dy = pos.y() - self._last_read_pos.y()
                if dx * dx + dy * dy < RETRIGGER_DIST * RETRIGGER_DIST:
                    return
            self._trigger()

    def _trigger(self, force: bool = False):
        if self._task is not None and self._task.isRunning():
            return
        if not force and self._cooldown.isActive():
            return
        png = self._capture()
        if png is None:
            return
        self._last_read_pos = QCursor.pos()
        self._task = OcrTask(png)
        self._task.done.connect(self._on_text)
        self._task.failed.connect(lambda _e: None)
        self._task.finished.connect(self._task.deleteLater)
        self._task.start()
        self._cooldown.start(COOLDOWN_MS)

    def _capture(self) -> bytes | None:
        try:
            screen = QGuiApplication.primaryScreen()
            pos = QCursor.pos()
            dpr = float(screen.devicePixelRatio() or 1.0)
            x = int(pos.x() - REGION_W / 2)
            y = int(pos.y() - REGION_H / 2)
            pix = screen.grabWindow(0, x, y, REGION_W, REGION_H)
            if pix.isNull():
                return None
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            pix.save(buf, "PNG")
            return bytes(buf.data())
        except Exception:
            return None

    def _on_text(self, text: str):
        text = " ".join(text.split())
        if len(text) < 4 or text == self._last_text:
            return
        self._last_text = text
        self.read_started.emit(text)
        self.speaker.say(text)
