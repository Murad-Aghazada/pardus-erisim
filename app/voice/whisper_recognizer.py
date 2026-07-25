"""
Whisper tabanlı Türkçe tanıma (faster-whisper, çevrimdışı) — yüksek doğruluk.

Küçük Vosk modelinin sözlük sınırlarına takılmaz; komut kelimeleriyle
yönlendirilmiş (initial_prompt) Whisper 'small' modeli kullanır. Enerji
tabanlı konuşma algılama (VAD) ile cümle sınırları bulunur; cümle bitince
~1.5-2 sn içinde metin üretilir ve aynı komut hattına verilir.

Sinyal arayüzü VoiceRecognizer ile birebir aynıdır; uygulama motorlar
arasında sorunsuz geçiş yapar.
"""

from __future__ import annotations

import queue

from app.voice.recognizer import VoiceRecognizer

_MODEL = None          # süreç boyunca tek yükleme (yeniden başlatma anında olur)
_MODEL_NAME = "small"


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def _get_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(_MODEL_NAME, device="cpu", compute_type="int8")
    return _MODEL


def _command_prompt() -> str:
    """Whisper'ı komut sözlüğüne yönlendiren Türkçe bağlam metni."""
    from app.voice.commands import CATALOG
    phrases = ", ".join(dict.fromkeys(c.phrase.replace(" ...", "") for c in CATALOG))
    return f"Bilgisayara Türkçe sesli komutlar veriliyor: {phrases}."


class WhisperRecognizer(VoiceRecognizer):
    """VoiceRecognizer'ın Whisper motoruyla çalışan türevi."""

    BLOCK = 1600            # 100 ms @ 16 kHz
    SILENCE_END = 8         # cümle sonu: 0.8 sn sessizlik
    MIN_SPEECH = 3          # en az 0.3 sn konuşma
    MAX_BLOCKS = 100        # en çok 10 sn

    def __init__(self, router, parent=None):
        super().__init__(router, parent)
        self.sensitivity = 60   # arayüzdeki mikrofon duyarlılığı (10-100)

    def stop(self):
        self._running = False
        self.wait(9000)         # süren bir çözümleme bitebilsin

    def run(self):
        self._running = True
        self.status.emit("starting")
        try:
            import numpy as np
            import sounddevice as sd
        except Exception:
            self.capability.emit(False)
            self.status.emit("no_lib")
            return
        try:
            model = _get_model()    # ilk kullanımda modeli indirir (~460 MB)
        except Exception:
            self.capability.emit(False)
            self.status.emit("no_model")
            return

        self.capability.emit(True)
        prompt = _command_prompt()
        q: queue.Queue = queue.Queue()

        def callback(indata, frames, time_info, status_flags):
            q.put(bytes(indata))

        if not self._running:
            self.status.emit("idle")
            return

        # duyarlılık: yüksek değer → daha alçak sesle tetiklenir
        sens = max(10, min(100, self.sensitivity))
        thr_scale = 1.7 - sens / 100.0          # 0.7 .. 1.6

        try:
            with sd.RawInputStream(samplerate=16000, blocksize=self.BLOCK,
                                   dtype="int16", channels=1, callback=callback):
                self.status.emit("listening")
                floor = 60.0
                buf: list[bytes] = []
                speech_blocks = 0
                silence_blocks = 0
                collecting = False

                while self._running:
                    try:
                        data = q.get(timeout=0.3)
                    except queue.Empty:
                        continue
                    if self._muted:
                        # TTS konuşuyor: bu bloğu at, yarım kalan toplamayı
                        # iptal et — kendi sesini komut sanıp duymasın
                        if collecting:
                            collecting = False
                            buf = []
                            speech_blocks = silence_blocks = 0
                        continue
                    pcm = np.frombuffer(data, dtype=np.int16)
                    rms = float(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)) + 1e-6)

                    thr_start = max(220.0, floor * 3.2) * thr_scale
                    thr_keep = max(150.0, floor * 1.8) * thr_scale

                    if not collecting:
                        if rms >= thr_start:
                            collecting = True
                            buf = [data]
                            speech_blocks, silence_blocks = 1, 0
                        else:
                            floor = 0.97 * floor + 0.03 * rms
                        continue

                    buf.append(data)
                    if rms >= thr_keep:
                        speech_blocks += 1
                        silence_blocks = 0
                    else:
                        silence_blocks += 1

                    if silence_blocks >= self.SILENCE_END or len(buf) >= self.MAX_BLOCKS:
                        if speech_blocks >= self.MIN_SPEECH:
                            self.status.emit("heard")
                            audio = (np.frombuffer(b"".join(buf), dtype=np.int16)
                                     .astype(np.float32) / 32768.0)
                            text = self._transcribe(model, audio, prompt)
                            if text:
                                self.partial_text.emit(text)
                                self._on_final(text, "")
                            # çözümleme sırasında biriken sesi at (yankı önlemi)
                            while not q.empty():
                                try:
                                    q.get_nowait()
                                except queue.Empty:
                                    break
                        collecting = False
                        buf = []
                        self.status.emit("listening")
        except Exception:
            self.status.emit("error")
            return
        finally:
            self.status.emit("idle")

    @staticmethod
    def _transcribe(model, audio, prompt: str) -> str:
        try:
            segments, _info = model.transcribe(
                audio, language="tr", beam_size=2,
                initial_prompt=prompt,
                condition_on_previous_text=False,
                no_speech_threshold=0.5,
            )
            return " ".join(s.text.strip() for s in segments).strip()
        except Exception:
            return ""
