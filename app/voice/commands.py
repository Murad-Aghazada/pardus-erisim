"""
Türkçe sesli komut dilbilgisi.

Katman 1: hızlı, çevrimdışı anahtar-sözcük eşleştirme (bulanık toleranslı).
Katman 2: eşleşmeyen serbest ifadeler Gemini niyet çözümleyiciye gider
(application.py yönetir) ve buradaki execute_intent ile çalıştırılır.
"""

from __future__ import annotations

import difflib
import unicodedata
from dataclasses import dataclass
from typing import Callable


def normalize(text: str) -> str:
    """Küçük harf + Türkçe aksan sadeleştirme + noktalama temizliği.

    Whisper noktalama ve büyük harf üretir ("Şimdi tıkla."); eşleştirme
    katmanı bunlardan bağımsız çalışmalıdır.
    """
    text = text.lower().strip()
    text = (text.replace("ı", "i").replace("İ", "i").replace("ş", "s")
            .replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c"))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    for ch in ".,!?;:\"'’“”…":
        text = text.replace(ch, " ")
    return " ".join(text.split())


@dataclass
class Command:
    phrase: str                    # kullanıcıya gösterilen örnek
    keywords: list[str]            # eşleşme için (normalize edilmiş) anahtarlar
    action: str                    # eylem kimliği
    desc: str                      # ne yaptığının açıklaması
    category: str
    arg: object = None


# Komut kataloğu — arayüzde de bu liste gösterilir
CATALOG: list[Command] = [
    # İşaretçi
    Command("yukarı", ["yukari"], "move", "İmleci yukarı taşı", "İmleç", ("up",)),
    Command("aşağı", ["asagi"], "move", "İmleci aşağı taşı", "İmleç", ("down",)),
    Command("sola", ["sola", "sol git"], "move", "İmleci sola taşı", "İmleç", ("left",)),
    Command("sağa", ["saga", "sag git"], "move", "İmleci sağa taşı", "İmleç", ("right",)),
    Command("tıkla", ["tikla", "tikla ona"], "click", "Sol tıkla", "İmleç", ("left",)),
    Command("çift tıkla", ["cift tikla", "cift"], "click", "Çift tıkla", "İmleç", ("double",)),
    Command("sağ tıkla", ["sag tikla"], "click", "Sağ tıkla", "İmleç", ("right",)),
    Command("kaydır yukarı", ["kaydir yukari", "yukari kaydir"], "scroll",
            "Sayfayı yukarı kaydır", "İmleç", (6,)),
    Command("kaydır aşağı", ["kaydir asagi", "asagi kaydir"], "scroll",
            "Sayfayı aşağı kaydır", "İmleç", (-6,)),

    # Yazma
    Command("yaz ...", ["yaz"], "type", "Söylediğin metni yaz", "Yazma"),
    Command("sil", ["sil", "geri sil"], "key", "Bir karakter sil", "Yazma", ("backspace",)),
    Command("giriş", ["giris", "enter", "satir"], "key", "Enter tuşu", "Yazma", ("enter",)),
    Command("boşluk", ["bosluk"], "key", "Boşluk tuşu", "Yazma", ("space",)),
    Command("hepsini seç", ["hepsini sec", "tumunu sec"], "key", "Tümünü seç", "Yazma", ("ctrl", "a")),
    Command("kopyala", ["kopyala", "kopya al", "kopya"], "key",
            "Kopyala", "Yazma", ("ctrl", "c")),
    Command("yapıştır", ["yapistir"], "key", "Yapıştır", "Yazma", ("ctrl", "v")),
    Command("geri al", ["geri al"], "key", "Son işlemi geri al", "Yazma", ("ctrl", "z")),

    # Uygulamalar
    Command("internete gir", ["tarayici", "internet", "web ac"], "app",
            "Web tarayıcısını aç", "Uygulama", "browser"),
    Command("dosyaları aç", ["dosya", "dosyalar"], "app",
            "Dosya yöneticisini aç", "Uygulama", "files"),
    Command("yazı editörü", ["yazi editoru", "editor", "metin duzenle"], "app",
            "Metin düzenleyiciyi aç", "Uygulama", "editor"),
    Command("terminal aç", ["terminal", "konsol", "ucbirim"], "app",
            "Terminali aç", "Uygulama", "terminal"),
    Command("hesap makinesi", ["hesap makinesi", "hesap makinesini"], "app",
            "Hesap makinesini aç", "Uygulama", "calc"),
    Command("ayarları aç", ["ayarlar", "ayarlari"], "app",
            "Sistem ayarlarını aç", "Uygulama", "settings"),
    Command("belge aç", ["belge", "kelime islemci", "yazi belgesi"], "app",
            "LibreOffice Writer'ı aç", "Uygulama", "office_writer"),
    Command("tablo aç", ["tablo", "hesap tablosu"], "app",
            "LibreOffice Calc'ı aç", "Uygulama", "office_calc"),
    Command("sunum aç", ["sunum"], "app",
            "LibreOffice Impress'i aç", "Uygulama", "office_impress"),
    Command("satranç aç", ["satranc"], "app",
            "Satranç oyununu aç", "Uygulama", "chess"),
    Command("uygulama mağazası", ["magaza", "uygulama magazasi", "pardus yazilim"], "app",
            "Pardus Yazılım Merkezi'ni aç", "Uygulama", "software"),
    Command("e-posta aç", ["posta", "mail"], "app",
            "E-posta uygulamasını aç", "Uygulama", "mail"),
    # Sık siteler: ASR "youtube'u aç"ı bozsa bile ("youtube ağaç") site adı
    # yakalanır. Uzun cümleler ("youtube'da kedi videoları aç") Gemini'ye
    # gider ve arama planına dönüşür; bkz. _match'teki kelime sınırı.
    Command("youtube aç", ["youtube", "yutup"], "url",
            "YouTube'u aç", "Uygulama", "https://www.youtube.com"),
    Command("google aç", ["google", "gugil"], "url",
            "Google'ı aç", "Uygulama", "https://www.google.com"),
    Command("vikipedi aç", ["vikipedi", "wikipedia"], "url",
            "Vikipedi'yi aç", "Uygulama", "https://tr.wikipedia.org"),

    # Sistem
    Command("pencereyi kapat", ["pencereyi kapat", "kapat pencere"], "key",
            "Etkin pencereyi kapat", "Sistem", ("alt", "f4")),
    Command("pencere değiştir", ["pencere degistir", "diger pencere"], "key",
            "Pencereler arasında geçiş", "Sistem", ("alt", "tab")),
    Command("sesi aç", ["sesi ac", "ses ac", "sesi yukselt"], "media",
            "Sesi yükselt", "Sistem", ("volup",)),
    Command("sesi kıs", ["sesi kis", "ses kis", "sesi azalt"], "media",
            "Sesi azalt", "Sistem", ("voldn",)),
    Command("sessize al", ["sessiz", "sesi kapat"], "media", "Sesi kapat", "Sistem", ("mute",)),

    # Erişilebilirlik + asistan
    Command("kafa takibini başlat", ["kafa takibi baslat", "kafa baslat",
            "goz takibi baslat", "takip baslat"],
            "eye", "Kafa ile imleç kontrolünü başlat", "Erişim", True),
    Command("kafa takibini durdur", ["kafa takibi durdur", "kafa durdur",
            "goz takibi durdur", "takip durdur"],
            "eye", "Kafa ile imleç kontrolünü durdur", "Erişim", False),
    Command("merkeze al", ["merkeze al", "merkez", "ortala"],
            "recenter", "İmleci ortala; şu anki duruş nötr kabul edilir", "Erişim"),
    Command("oku", ["oku", "burayi oku"],
            "read", "İmlecin altındaki metni sesli oku", "Erişim"),
    Command("okumayı durdur", ["okumayi durdur", "okuma durdur", "sus"],
            "read_stop", "Sesli okumayı durdur", "Erişim"),
    Command("otomatik okumayı aç", ["otomatik okumayi ac", "otomatik okuma ac"],
            "read_auto", "İmleç metin üstünde durunca otomatik oku", "Erişim", True),
    Command("otomatik okumayı kapat", ["otomatik okumayi kapat", "otomatik okuma kapat"],
            "read_auto", "Otomatik okumayı kapat", "Erişim", False),
    Command("asistan ...", ["asistan"], "assist",
            "Soruyu yapay zekâ asistanına sor", "Erişim"),
    Command("yardım", ["yardim"], "help", "Yardım ekranını aç", "Erişim"),
    Command("çıkış", ["cikis", "uygulamadan cik", "uygulamayi kapat"],
            "quit", "Pardus Erişim'i kapat", "Erişim"),
]


# Uygulama adayları: Pardus/Linux öncelikli, Windows'ta geliştirme için yedekler
APP_CANDIDATES: dict[str, list[str]] = {
    "browser": ["firefox", "firefox-esr", "chromium", "google-chrome", "brave-browser"],
    "files": ["nautilus", "nemo", "thunar", "dolphin", "caja", "pcmanfm", "explorer"],
    "editor": ["gedit", "kate", "mousepad", "xed", "pluma", "notepad"],
    "terminal": ["gnome-terminal", "konsole", "xfce4-terminal", "mate-terminal", "xterm",
                 "powershell"],
    "calc": ["gnome-calculator", "kcalc", "galculator", "mate-calc", "calc"],
    "settings": ["gnome-control-center", "systemsettings5", "xfce4-settings-manager",
                 "mate-control-center"],
    "office_writer": ["libreoffice --writer", "lowriter", "abiword", "winword", "write"],
    "office_calc": ["libreoffice --calc", "localc", "gnumeric", "excel"],
    "office_impress": ["libreoffice --impress", "loimpress", "powerpnt"],
    "chess": ["gnome-chess", "kchess", "xboard", "pychess", "chess"],
    "software": ["pardus-software", "gnome-software", "plasma-discover"],
    "mail": ["thunderbird", "evolution", "kmail"],
}


class CommandRouter:
    """Tanınan metni eşleştirir ve ilgili eylemi çalıştırır."""

    STEP = 60          # sesli imleç adımı (px)
    FUZZY = 0.80       # bulanık eşleşme eşiği

    def __init__(self, control, app_actions: dict[str, Callable]):
        self.control = control
        self.app_actions = app_actions
        self._apps = APP_CANDIDATES

    # ---- Katman 1: yerel dilbilgisi ----
    def handle(self, text: str) -> str | None:
        """Metni işle. Bir şey yaptıysa insan-okunur açıklama döndür."""
        norm = normalize(text)
        if not norm:
            return None

        # serbest metin önekleri
        if norm.startswith("yaz "):
            payload = text.strip()[4:].strip()
            if payload:
                self.control.type_text(payload)
                return f"Yazıldı: {payload}"
        if norm.startswith("asistan"):
            payload = text.strip()[7:].strip(" ,.")
            fn = self.app_actions.get("ask_assistant")
            if fn and payload:
                fn(payload)
                return "Asistana soruldu"
            return None

        best = self._match(norm)
        if not best:
            return None
        return self._run(best)

    @staticmethod
    def _word_hit(kw_word: str, text_word: str) -> bool:
        """Türkçe eklere toleranslı kelime eşleşmesi.

        Kısa anahtarlar (örn. 'sil') tam kelime olmalı — 'nasıl' içindeki
        'sil' eşleşmemeli. Uzun anahtarlar kelime başı olabilir: 'tarayici'
        → 'tarayiciyi' gibi çekimli halleri yakalar.
        """
        if len(kw_word) < 4:
            return text_word == kw_word
        if text_word.startswith(kw_word) and len(text_word) <= len(kw_word) + 6:
            return True
        # ASR bazen son harfi düşürür: 'kaydır' → 'kaydı'
        return (len(kw_word) >= 5 and kw_word.startswith(text_word)
                and len(text_word) >= len(kw_word) - 1)

    def _match(self, norm: str) -> Command | None:
        words = norm.split()

        # 1) kelime-sınırlı, ek toleranslı dizi eşleşmesi — en uzun kazanır
        best, best_len = None, 0
        for cmd in CATALOG:
            # site komutları yalnız kısa söyleyişlerde ("youtubeu aç");
            # uzun doğal cümleler Gemini'nin arama planına kalır
            if cmd.action == "url" and len(words) > 3:
                continue
            for kw in cmd.keywords:
                kw_words = kw.split()
                n = len(kw_words)
                if n == 0 or n > len(words) or len(kw) <= best_len:
                    continue
                for i in range(len(words) - n + 1):
                    if all(self._word_hit(k, words[i + j])
                           for j, k in enumerate(kw_words)):
                        best, best_len = cmd, len(kw)
                        break
        if best:
            return best

        # 2) bulanık yedek: ASR bozulmalarını tolere et (kısa anahtarlar hariç)
        best_score = 0.0
        for cmd in CATALOG:
            if cmd.action == "url" and len(words) > 3:
                continue
            for kw in cmd.keywords:
                if len(kw) < 4:
                    continue
                kw_words = kw.split()
                n = len(kw_words)
                if n == 0 or n > len(words):
                    continue
                for i in range(len(words) - n + 1):
                    window = " ".join(words[i:i + n])
                    score = difflib.SequenceMatcher(None, kw, window).ratio()
                    if score >= self.FUZZY and score > best_score:
                        best, best_score = cmd, score
        return best

    def _run(self, cmd: Command) -> str:
        a = cmd.action
        if a == "move":
            d = cmd.arg[0]
            dx = {"left": -self.STEP, "right": self.STEP}.get(d, 0)
            dy = {"up": -self.STEP, "down": self.STEP}.get(d, 0)
            self.control.move_by(dx, dy)
        elif a == "click":
            mode = cmd.arg[0]
            self.control.click("right" if mode == "right" else "left",
                               double=(mode == "double"))
        elif a == "scroll":
            self.control.scroll(cmd.arg[0])
        elif a == "key":
            self.control.press(*cmd.arg)
        elif a == "media":
            self._media(cmd.arg[0])
        elif a == "app":
            ok = self.control.launch(self._apps.get(cmd.arg, []))
            if not ok:
                return f"{cmd.desc}: uygulama bulunamadı"
        elif a == "url":
            self.control.open_url(cmd.arg)
        elif a == "eye":
            fn = self.app_actions.get("set_eye")
            if fn:
                fn(cmd.arg)
        elif a == "recenter":
            fn = self.app_actions.get("recenter")
            if fn:
                fn()
        elif a == "read":
            fn = self.app_actions.get("read_now")
            if fn:
                fn()
        elif a == "read_stop":
            fn = self.app_actions.get("read_stop")
            if fn:
                fn()
        elif a == "read_auto":
            fn = self.app_actions.get("read_auto")
            if fn:
                fn(cmd.arg)
        elif a == "help":
            fn = self.app_actions.get("open_help")
            if fn:
                fn()
        elif a == "quit":
            fn = self.app_actions.get("quit_app")
            if fn:
                fn()
        return cmd.desc

    def _media(self, kind: str):
        keymap = {"volup": "media_volume_up", "voldn": "media_volume_down",
                  "mute": "media_volume_mute"}
        self.control.press(keymap.get(kind, "media_volume_mute"))

    # ---- Katman 2: Gemini niyeti ----
    def execute_intent(self, intent: dict) -> str | None:
        """Gemini'nin JSON niyetini çalıştır. Açıklama döndürür."""
        t = intent.get("type")
        if t == "launch":
            target = str(intent.get("target", ""))
            if target in self._apps:
                ok = self.control.launch(self._apps[target])
                return "Uygulama açılıyor" if ok else "Uygulama bulunamadı"
            return None
        if t == "open_url":
            url = str(intent.get("url", ""))
            if url.startswith("http"):
                self.control.open_url(url)
                return "Site açılıyor"
            return None
        if t == "type":
            text = str(intent.get("text", ""))
            if text:
                self.control.type_text(text)
                return f"Yazıldı: {text[:40]}"
            return None
        if t == "key":
            keys = intent.get("keys")
            if isinstance(keys, list) and keys:
                self.control.press(*[str(k) for k in keys[:3]])
                return "Kısayol uygulandı"
            return None
        if t == "click":
            btn = str(intent.get("button", "left"))
            self.control.click("right" if btn == "right" else "left",
                               double=(btn == "double"))
            return "Tıklandı"
        if t == "scroll":
            try:
                amount = int(intent.get("amount", -6))
            except (TypeError, ValueError):
                amount = -6
            self.control.scroll(max(-20, min(20, amount)))
            return "Kaydırıldı"
        return None   # "answer" ve "none" burada işlenmez
