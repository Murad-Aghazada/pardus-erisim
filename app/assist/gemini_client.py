"""
Gemini istemcisi — sohbet ve sesli komut yorumlama.

İki kullanım:
1. Sohbet: kullanıcının yazdığı/söylediği soruya Türkçe yanıt.
2. Niyet çözümleme: dilbilgisinin anlamadığı serbest komutu yapılandırılmış
   eyleme çevirir (JSON). Ağ yoksa ya da anahtar eksikse sessizce başarısız
   olur; uygulama çevrimdışı çalışmayı sürdürür.
"""

from __future__ import annotations

import json
import re

from PySide6.QtCore import QThread, Signal

from app.assist import config

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

CHAT_SYSTEM = (
    "Sen Pardus Erişim asistanısın. Bilgisayarı gözleri ve sesiyle kullanan, "
    "fare/klavye kullanamayan bir kullanıcıya yardım ediyorsun. Türkçe, kısa, "
    "net ve sıcak yanıtlar ver. Uzun listelerden ve teknik jargondan kaçın; "
    "yanıtın sesli okunacağını unutma."
)

INTENT_SYSTEM = (
    "Bilgisayarı sesle kullanan, fare/klavye kullanamayan bir kullanıcının "
    "sözünü EYLEME çevir. SADECE tek satır JSON döndür, başka hiçbir şey yazma.\n"
    'Biçim: {"say":"kısa Türkçe onay (sesli okunur, isteğe bağlı)",'
    '"steps":[adım, adım, ...]}\n'
    "Adım türleri:\n"
    '{"type":"launch","target":"<app>"} — uygulama aç; target: browser, files, '
    "editor, terminal, calc, settings, office_writer, office_calc, "
    "office_impress, chess, software, mail\n"
    '{"type":"open_url","url":"https://..."} — site/arama aç. Aramalar için '
    "arama URL'si kur: google → https://www.google.com/search?q=..., "
    "youtube → https://www.youtube.com/results?search_query=..., "
    "vikipedi → https://tr.wikipedia.org/wiki/...\n"
    '{"type":"wait","ms":2000} — sonraki adımdan önce bekle (uygulama açılışı)\n'
    '{"type":"type","text":"..."} — metni klavyeden yaz\n'
    '{"type":"key","keys":["ctrl","c"]} — tuş/kısayol (en çok 3 tuş)\n'
    '{"type":"click","button":"left|right|double"} — tıkla\n'
    '{"type":"scroll","amount":-6} — kaydır (negatif aşağı)\n'
    '{"type":"read_screen"} — imlecin altındaki ekran metnini sesli oku\n'
    "Soru soruyorsa steps boş bırak, yanıtı say alanına yaz.\n"
    "En çok 6 adım. Sistem komutları (kapatma, silme, kurulum) YOK; bunlar "
    'için {"say":"Bunu yapamam","steps":[]} döndür.\n'
    "Örnekler:\n"
    "'youtube'da kedi videoları aç' → {\"say\":\"YouTube'da kedi videoları "
    "açıyorum\",\"steps\":[{\"type\":\"open_url\",\"url\":"
    "\"https://www.youtube.com/results?search_query=kedi+videolar%C4%B1\"}]}\n"
    "'yeni belge aç ve içine merhaba dünya yaz' → {\"say\":\"Belge açıp "
    "yazıyorum\",\"steps\":[{\"type\":\"launch\",\"target\":\"editor\"},"
    "{\"type\":\"wait\",\"ms\":2500},{\"type\":\"type\",\"text\":\"merhaba dünya\"}]}\n"
    "'ekranda ne yazıyor' → {\"steps\":[{\"type\":\"read_screen\"}]}\n"
    "'iki kere iki kaç' → {\"say\":\"Dört eder.\",\"steps\":[]}\n"
)


class GeminiTask(QThread):
    """Tek bir Gemini isteği. done(metin) ya da failed(hata) yayar."""

    done = Signal(str)
    failed = Signal(str)

    def __init__(self, messages: list[dict], system: str = CHAT_SYSTEM, parent=None):
        super().__init__(parent)
        self._messages = messages    # [{"role": "user"|"model", "text": ...}]
        self._system = system

    def run(self):
        cfg = config.load()
        key = cfg.get("gemini_api_key", "").strip()
        if not key:
            self.failed.emit("no_key")
            return
        try:
            import requests
        except Exception:
            self.failed.emit("no_lib")
            return

        contents = [
            {"role": m["role"], "parts": [{"text": m["text"]}]}
            for m in self._messages[-12:]
        ]
        body = {
            "system_instruction": {"parts": [{"text": self._system}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1024},
        }
        url = _ENDPOINT.format(model=cfg.get("gemini_model", "gemini-2.5-flash"))
        try:
            resp = None
            for attempt in range(2):     # geçici 5xx için tek yeniden deneme
                resp = requests.post(
                    url, params={"key": key}, json=body, timeout=25)
                if resp.status_code < 500:
                    break
                import time
                time.sleep(1.5)
            if resp is None or resp.status_code != 200:
                self.failed.emit(f"http_{resp.status_code if resp else 0}")
                return
            data = resp.json()
            parts = (data.get("candidates") or [{}])[0].get(
                "content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                self.done.emit(text)
            else:
                self.failed.emit("empty")
        except Exception:
            self.failed.emit("network")


def parse_intent(raw: str) -> dict | None:
    """Model yanıtından JSON niyeti ayıkla (tek adım, eski biçim)."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except ValueError:
        return None
    if isinstance(obj, dict) and "type" in obj:
        return obj
    return None


ALLOWED_STEPS = {"launch", "open_url", "wait", "type", "key", "click",
                 "scroll", "read_screen"}


def parse_plan(raw: str) -> dict | None:
    """Model yanıtından eylem planı ayıkla ve TEMİZLE.

    Dönen biçim: {"say": str, "steps": [geçerli adımlar]} ya da None.
    Tek-adımlık eski biçim ({"type": ...}) plana sarılır.
    """
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None

    if "type" in obj and "steps" not in obj:      # eski tek-adım biçimi
        if obj.get("type") == "answer":
            return {"say": str(obj.get("text", "")), "steps": []}
        obj = {"steps": [obj]}

    say = str(obj.get("say", "") or "")[:400]
    steps_in = obj.get("steps")
    steps: list[dict] = []
    if isinstance(steps_in, list):
        for s in steps_in[:6]:
            if not isinstance(s, dict) or s.get("type") not in ALLOWED_STEPS:
                continue
            if s["type"] == "open_url" and not str(s.get("url", "")).startswith("http"):
                continue
            if s["type"] == "wait":
                try:
                    s["ms"] = max(100, min(5000, int(s.get("ms", 1000))))
                except (TypeError, ValueError):
                    s["ms"] = 1000
            steps.append(s)
    if not steps and not say:
        return None
    return {"say": say, "steps": steps}


def has_key() -> bool:
    return bool(config.load().get("gemini_api_key", "").strip())
