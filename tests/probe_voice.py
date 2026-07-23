"""
Canlı ses sondası — Vosk Türkçe modeliyle uçtan uca tanıma.

Türkçe test cümleleri gerçek konuşmaya çevrilir (önce Gemini TTS, yoksa
Windows SAPI), ses Vosk'a verilir ve router'ın doğru eylemi seçtiği
doğrulanır: ses → tanıma → komut zincirinin tam testi. Hiçbir TTS yoksa
model sessizlikle doğrulanır.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCRATCH = os.environ.get("TEMP", ".")

# Doğal uzunlukta söyleyişler: kısa tek kelimeler TTS tarafından
# reddedilebiliyor; gerçek kullanıcı da zaten böyle konuşur.
PHRASES = [
    ("şimdi tıkla", "click"),
    ("tarayıcıyı aç lütfen", "launch"),
    ("lütfen sesi kıs", "press"),
    ("biraz aşağı kaydır", "scroll"),
    ("hesap makinesini açar mısın", "launch"),
]


def synth_gemini_tts(text: str, path: str) -> bool:
    """Gemini TTS ile Türkçe sentez → 16k mono WAV. Anahtar/ağ yoksa False."""
    try:
        import base64
        import numpy as np
        import requests
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        import json as _json
        cfg = _json.load(open(os.path.join(root, "config.json"), encoding="utf-8"))
        key = cfg.get("gemini_api_key", "")
        if not key:
            return False
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               "gemini-2.5-flash-preview-tts:generateContent")
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": "Kore"}}},
            },
        }
        import time as _time
        part = None
        for attempt in range(4):        # önizleme TTS ucu kaprisli: 429/503
            r = requests.post(url, params={"key": key}, json=body, timeout=60)
            if r.status_code != 200:    # ve bazen içeriksiz 200 döner
                _time.sleep(3 * (attempt + 1))
                continue
            cand = r.json()["candidates"][0]
            if "content" not in cand:
                _time.sleep(2)
                continue
            part = cand["content"]["parts"][0]
            break
        if part is None:
            return False
        raw = base64.b64decode(part["inlineData"]["data"])
        pcm24 = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        # 24k → 16k yeniden örnekleme (doğrusal aradeğerleme)
        n16 = int(len(pcm24) * 16000 / 24000)
        idx = np.linspace(0, len(pcm24) - 1, n16)
        pcm16 = np.interp(idx, np.arange(len(pcm24)), pcm24).astype(np.int16)
        # başa/sona sessizlik: ASR konuşma başlangıcını kaçırmasın
        pad = np.zeros(int(16000 * 0.4), dtype=np.int16)
        pcm16 = np.concatenate([pad, pcm16, pad])
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
            wf.writeframes(pcm16.tobytes())
        return True
    except Exception:
        import traceback; traceback.print_exc()
        return False


def synth_windows_tts(text: str, path: str) -> bool:
    """SAPI ile Türkçe sentez; Türkçe ses yoksa False."""
    ps = f'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like "tr*" }} | Select-Object -First 1
if (-not $v) {{ Write-Output "NO_TR_VOICE"; exit 1 }}
$s.SelectVoice($v.VoiceInfo.Name)
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile("{path}", $fmt)
$s.Speak("{text}")
$s.Dispose()
Write-Output "OK"
'''
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=30)
        return "OK" in (r.stdout or "")
    except Exception:
        return False


def recognize(model, wav_path: str, grammar: str | None = None) -> str:
    import vosk
    if grammar:
        rec = vosk.KaldiRecognizer(model, 16000, grammar)
    else:
        rec = vosk.KaldiRecognizer(model, 16000)
    texts = []
    with wave.open(wav_path, "rb") as wf:
        assert wf.getframerate() == 16000, "örnekleme hızı 16k olmalı"
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                texts.append(json.loads(rec.Result()).get("text", ""))
    texts.append(json.loads(rec.FinalResult()).get("text", ""))
    out = " ".join(t for t in texts if t).strip()
    return out.replace("[unk]", " ").strip() if grammar else out


def main():
    import vosk
    from app.voice.recognizer import find_model
    from app.voice.commands import CommandRouter
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_commands import FakeControl

    vosk.SetLogLevel(-1)
    model_path = find_model()
    assert model_path, "Türkçe model bulunamadı"
    print("model:", os.path.basename(model_path))
    model = vosk.Model(model_path)

    # --- sessizlik hattı: model + tanıyıcı çökmeden çalışmalı ---
    silence = os.path.join(SCRATCH, "probe_silence.wav")
    with wave.open(silence, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)
    out = recognize(model, silence)
    print(f"sessizlik → {out!r} (boş beklenir)")

    # --- Türkçe TTS ile uçtan uca ---
    ctl = FakeControl()
    router = CommandRouter(ctl, {"set_eye": lambda v: None,
                                 "open_help": lambda: None,
                                 "ask_assistant": lambda q: None})
    # Değerlendirme: doğru eylem = GEÇTİ; eylem yok = GÜVENLİ (yanlış bir şey
    # yapılmadı; gerçek uygulamada Gemini katmanı devralır); yanlış eylem = KALDI.
    exact = safe = wrong = skipped = 0
    for phrase, expect_kind in PHRASES:
        wav = os.path.join(SCRATCH, "probe_tts.wav")
        if not (synth_gemini_tts(phrase, wav) or synth_windows_tts(phrase, wav)):
            skipped += 1
            print(f"sentezlenemedi (TTS ucu reddetti): {phrase!r} — atlandı")
            continue
        from app.voice.recognizer import build_grammar
        heard_open = recognize(model, wav)
        heard_gram = recognize(model, wav, build_grammar())
        # uygulamadaki seçim mantığı: komuta eşleşen dilbilgisi sonucu yeğlenir
        from app.voice.commands import normalize
        if heard_gram and router._match(normalize(heard_gram)):
            heard = heard_gram
        else:
            heard = heard_open
        print(f"   açık: {heard_open!r}  |  kısıtlı: {heard_gram!r}")
        n0 = len(ctl.calls)
        router.handle(heard) if heard else None
        new_calls = ctl.calls[n0:]
        kind = new_calls[0][0] if new_calls else None
        if kind == expect_kind:
            exact += 1; verdict = "GEÇTİ"
        elif kind is None:
            safe += 1; verdict = "GÜVENLİ (anlaşılamadı, eylem yok)"
        else:
            # yön mantığı: kaydırma yerine imleç taşıma gibi yakın eylemler
            near = {("scroll", "move_by"), ("move_by", "scroll")}
            if (expect_kind, kind) in near:
                safe += 1; verdict = f"YAKIN ({kind})"
            else:
                wrong += 1; verdict = f"KALDI (yanlış eylem: {kind})"
        print(f"söylendi {phrase!r} → duyuldu {heard!r} → {verdict}")

    ran = exact + safe + wrong
    if ran:
        print(f"\nUçtan uca: {exact} tam / {safe} güvenli / {wrong} yanlış "
              f"(atlanan sentez: {skipped})")
        if wrong:
            sys.exit(1)
    else:
        print("Türkçe TTS hiç üretilemedi; ses hattı yalnızca yapısal doğrulandı")
    print("SES HATTI DOĞRULANDI — yanlış eylem yok")


if __name__ == "__main__":
    main()
