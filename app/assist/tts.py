"""
Sesli okuma (TTS) — asistan yanıtlarını yüksek sesle okur.

Qt'nin yerel TTS motorunu kullanır: Windows'ta SAPI, Linux/Pardus'ta
speech-dispatcher. Türkçe ses varsa onu seçer. Motor yoksa sessizce devre
dışı kalır; uygulama etkilenmez.
"""

from __future__ import annotations


class Speaker:
    def __init__(self):
        self._tts = None
        self.available = False
        try:
            from PySide6.QtTextToSpeech import QTextToSpeech
            from PySide6.QtCore import QLocale
            self._tts = QTextToSpeech()
            # Türkçe yerel ayar dene
            for loc in self._tts.availableLocales():
                if loc.language() == QLocale.Language.Turkish:
                    self._tts.setLocale(loc)
                    break
            self._tts.setRate(0.0)
            self.available = True
        except Exception:
            self._tts = None

    def say(self, text: str):
        if self._tts is None or not text:
            return
        try:
            self._tts.stop()
            self._tts.say(text[:600])
        except Exception:
            pass

    def stop(self):
        if self._tts is not None:
            try:
                self._tts.stop()
            except Exception:
                pass
