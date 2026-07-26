"""
Türkçe sesli komut tanıma (Vosk, çevrimdışı).

Ayrı iş parçacığında mikrofonu dinler, Vosk Türkçe modeliyle metne çevirir ve
CommandRouter üzerinden eyleme dönüştürür. Yerel dilbilgisi eşleşmezse metni
`unmatched` sinyaliyle yukarı verir (Gemini niyet çözümlemesi için).
vosk/sounddevice ya da model yoksa çökmeden uygun durumu yayar.
"""

from __future__ import annotations

import glob
import json
import os
import queue

from PySide6.QtCore import QThread, Signal, QTimer, QStandardPaths


# Dilbilgisi-kısıtlı ikinci tanıyıcının kelime dağarcığı: komut kataloğundaki
# tüm kelimeler + doğal dolgu kelimeleri, GERÇEK Türkçe yazımlarıyla.
# Kısıtlı tanıyıcı yalnız bu kelimeleri duyabildiği için komutlarda çok daha
# isabetlidir; serbest metin ("yaz …", "asistan …") açık tanıyıcıdan gelir.
# Not: yalnızca modelin sözlüğünde VAR OLAN kelimeler. Küçük TR modelinde
# 'kaydır', 'kopyala', 'tarayıcı', 'ortala' yoktur; komut kataloğu bu yüzden
# sözlük-içi eşdeğerler de tanır: 'kaydı', 'kopya', 'internete gir',
# 'merkeze al'.
GRAMMAR_WORDS = (
    "tıkla çift sağ sol sola sağa yukarı aşağı kaydı sil giriş enter satır "
    "boşluk hepsini tümünü seç kopya yapıştır geri al yaz asistan "
    "internet internete gir web dosya dosyalar dosyaları "
    "yazı editör metin düzenle terminal konsol "
    "hesap makinesi makinesini ayarlar ayarları belge kelime işlemci "
    "tablo hesap tablosu sunum satranç oyna mağaza uygulama mağazası yazılım "
    "posta mail e-posta pencere pencereyi kapat değiştir diğer "
    "ses sesi aç kıs azalt yükselt sessiz sessize al "
    "göz kafa takip takibi başlat durdur yardım "
    "oku okuma okumayı otomatik merkez merkeze çıkış "
    "youtube google vikipedi wikipedia video videolar "
    "lütfen şimdi biraz sayfayı sayfa bir iki hemen istiyorum "
    "[unk]"
)


def build_grammar() -> str:
    """Vosk dilbilgisi JSON'u (tekilleştirilmiş kelime listesi)."""
    words = list(dict.fromkeys(GRAMMAR_WORDS.split()))
    return json.dumps(words, ensure_ascii=False)


def _is_model_dir(path: str) -> bool:
    """Vosk model klasörü mü? Küçük modellerde final.mdl kökte, büyüklerde am/ olur."""
    if not os.path.isdir(path):
        return False
    return (os.path.isfile(os.path.join(path, "final.mdl"))
            or os.path.isdir(os.path.join(path, "am"))
            or os.path.isdir(os.path.join(path, "graph")))


def find_model() -> str | None:
    """Türkçe Vosk modelini bilinen konumlarda ara."""
    candidates: list[str] = []
    env = os.environ.get("VOSK_MODEL_TR")
    if env:
        candidates.append(env)

    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates.append(os.path.join(here, "models"))
    data = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    candidates.append(os.path.join(data, "models"))

    for base in candidates:
        if not base:
            continue
        if _is_model_dir(base):
            return base
        for path in sorted(glob.glob(os.path.join(base, "*"))):
            if _is_model_dir(path):
                name = os.path.basename(path).lower()
                if "tr" in name or len(glob.glob(os.path.join(base, "*"))) == 1:
                    return path
    return None


class VoiceRecognizer(QThread):
    partial_text = Signal(str)
    final_text = Signal(str)
    action_done = Signal(str)
    unmatched = Signal(str)       # yerel dilbilgisi anlamadı → Gemini'ye
    status = Signal(str)          # idle|starting|listening|heard|no_lib|no_model|error
    capability = Signal(bool)

    def __init__(self, router, parent=None):
        super().__init__(parent)
        self.router = router
        self._running = False
        self.require_wake = False
        self.wake_word = "pardus"
        self._awake = False
        self._muted = False

    def set_muted(self, muted: bool):
        """TTS konuşurken mikrofonu yok say — kendi sesini komut sanıp
        döngüye girmesin (bkz. AppController Speaker.speaking_changed)."""
        self._muted = bool(muted)

    def stop(self):
        self._running = False
        self.wait(6000)

    def run(self):
        # bayrak en başta: model yüklenirken stop() gelirse döngüye girmeyiz
        self._running = True
        self.status.emit("starting")
        try:
            import sounddevice as sd
            import vosk
        except Exception:
            self.capability.emit(False)
            self.status.emit("no_lib")
            return

        model_path = find_model()
        if not model_path:
            self.capability.emit(False)
            self.status.emit("no_model")
            return

        self.capability.emit(True)
        try:
            vosk.SetLogLevel(-1)
            model = vosk.Model(model_path)
            rec = vosk.KaldiRecognizer(model, 16000)
        except Exception:
            self.status.emit("error")
            return

        # Doğruluk katmanı: komut sözlüğüne kısıtlı ikinci tanıyıcı.
        # Açık tanıyıcı serbest metni, kısıtlı olan komutları temiz duyar.
        rec_g = None
        try:
            rec_g = vosk.KaldiRecognizer(model, 16000, build_grammar())
        except Exception:
            rec_g = None   # dilbilgisi desteklenmezse tek tanıyıcıyla sürdür

        q: queue.Queue = queue.Queue()

        def callback(indata, frames, time_info, status_flags):
            q.put(bytes(indata))

        if not self._running:      # init sırasında durduruldu
            self.status.emit("idle")
            return
        try:
            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16",
                                   channels=1, callback=callback):
                self.status.emit("listening")
                while self._running:
                    try:
                        data = q.get(timeout=0.3)
                    except queue.Empty:
                        continue
                    if self._muted:
                        continue    # TTS konuşuyor: kendi sesini duymasın
                    if rec_g is not None:
                        rec_g.AcceptWaveform(data)
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        text = result.get("text", "").strip()
                        grammar_text = ""
                        if rec_g is not None:
                            grammar_text = json.loads(rec_g.FinalResult()).get(
                                "text", "").replace("[unk]", " ").strip()
                            rec_g.Reset()
                        if text or grammar_text:
                            self._on_final(text, grammar_text)
                    else:
                        partial = json.loads(rec.PartialResult()).get("partial", "").strip()
                        if partial:
                            self.partial_text.emit(partial)
                            self.status.emit("listening")
        except Exception:
            self.status.emit("error")
            return
        finally:
            self.status.emit("idle")

    def _choose(self, open_text: str, grammar_text: str) -> str:
        """İki tanıyıcı sonucundan hangisi kullanılacak?

        Serbest metin önekleri ("yaz", "asistan") açık tanıyıcınındır.
        Kısıtlı sonuç bir komutla eşleşiyorsa onu yeğle (komutlarda çok daha
        isabetli). Hiçbiri değilse açık metin (Gemini katmanına gidebilir).
        """
        low = open_text.lower()
        if low.startswith(("yaz ", "asistan")):
            return open_text
        if grammar_text:
            try:
                from app.voice.commands import normalize
                if self.router._match(normalize(grammar_text)) is not None:
                    return grammar_text
            except Exception:
                pass
        return open_text or grammar_text

    def _on_final(self, open_text: str, grammar_text: str = ""):
        text = self._choose(open_text, grammar_text)
        self.final_text.emit(text)
        self.status.emit("heard")

        if self.require_wake and not self._awake:
            if self.wake_word in text.lower():
                self._awake = True
            return

        try:
            done = self.router.handle(text)
        except Exception:
            done = None
        if done:
            self.action_done.emit(done)
        else:
            # yerel katman anlamadı; akıllı katmana devret (zengin açık metinle)
            self.unmatched.emit(open_text or text)
        if self.require_wake:
            self._awake = False
