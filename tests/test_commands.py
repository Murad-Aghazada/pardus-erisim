"""
Sesli komut anlama testleri.

Gerçek kullanımda Vosk'un üreteceği türden metinler (ekler, söyleyiş
farkları, ASR bozulmaları) router'a verilir; doğru eyleme gidip gitmediği
sahte bir SystemControl ile doğrulanır. Gemini niyet çalıştırıcı da test edilir.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeControl:
    """Yapılan çağrıları kaydeder."""

    def __init__(self):
        self.calls = []
        self.available = True

    def move_to(self, x, y): self.calls.append(("move_to", x, y))
    def move_by(self, dx, dy): self.calls.append(("move_by", dx, dy))
    def click(self, button="left", double=False): self.calls.append(("click", button, double))
    def scroll(self, dy): self.calls.append(("scroll", dy))
    def type_text(self, t): self.calls.append(("type", t))
    def press(self, *keys): self.calls.append(("press",) + keys)
    def launch(self, candidates): self.calls.append(("launch", tuple(candidates))); return True
    def open_url(self, url): self.calls.append(("url", url)); return True

    def last(self):
        return self.calls[-1] if self.calls else None


def run_cases():
    from app.voice.commands import CommandRouter

    ctl = FakeControl()
    assist_calls = []
    router = CommandRouter(ctl, {
        "set_eye": lambda on: assist_calls.append(("eye", on)),
        "open_help": lambda: assist_calls.append(("help",)),
        "ask_assistant": lambda q: assist_calls.append(("ask", q)),
    })

    # (söylenen, beklenen çağrı denetimi)
    CASES = [
        # --- birebir komutlar ---
        ("tıkla", lambda: ctl.last() == ("click", "left", False)),
        ("çift tıkla", lambda: ctl.last() == ("click", "left", True)),
        ("sağ tıkla", lambda: ctl.last() == ("click", "right", False)),
        ("yukarı", lambda: ctl.last()[0] == "move_by" and ctl.last()[2] < 0),
        ("aşağı", lambda: ctl.last()[0] == "move_by" and ctl.last()[2] > 0),
        ("sola", lambda: ctl.last()[0] == "move_by" and ctl.last()[1] < 0),
        ("sağa", lambda: ctl.last()[0] == "move_by" and ctl.last()[1] > 0),
        ("kaydır aşağı", lambda: ctl.last() == ("scroll", -6)),
        ("kaydır yukarı", lambda: ctl.last() == ("scroll", 6)),
        ("kopyala", lambda: ctl.last() == ("press", "ctrl", "c")),
        ("yapıştır", lambda: ctl.last() == ("press", "ctrl", "v")),
        ("hepsini seç", lambda: ctl.last() == ("press", "ctrl", "a")),
        ("geri al", lambda: ctl.last() == ("press", "ctrl", "z")),
        ("giriş", lambda: ctl.last() == ("press", "enter")),
        ("sil", lambda: ctl.last() == ("press", "backspace")),
        ("boşluk", lambda: ctl.last() == ("press", "space")),
        ("pencereyi kapat", lambda: ctl.last() == ("press", "alt", "f4")),
        ("pencere değiştir", lambda: ctl.last() == ("press", "alt", "tab")),
        ("sesi aç", lambda: ctl.last() == ("press", "media_volume_up")),
        ("sesi kıs", lambda: ctl.last() == ("press", "media_volume_down")),
        ("sessize al", lambda: ctl.last() == ("press", "media_volume_mute")),

        # --- uygulamalar ---
        ("tarayıcı aç", lambda: ctl.last()[0] == "launch" and "firefox" in ctl.last()[1]),
        ("satranç aç", lambda: ctl.last()[0] == "launch" and "gnome-chess" in ctl.last()[1]),
        ("terminal aç", lambda: ctl.last()[0] == "launch" and "gnome-terminal" in ctl.last()[1]),
        ("hesap makinesi", lambda: ctl.last()[0] == "launch" and "gnome-calculator" in ctl.last()[1]),
        ("belge aç", lambda: ctl.last()[0] == "launch" and any("writer" in c for c in ctl.last()[1])),
        ("uygulama mağazası", lambda: ctl.last()[0] == "launch" and "pardus-software" in ctl.last()[1]),
        ("e-posta aç", lambda: ctl.last()[0] == "launch" and "thunderbird" in ctl.last()[1]),

        # --- doğal ekler / çekimler (Vosk çıktısı böyle gelir) ---
        ("tarayıcıyı aç", lambda: ctl.last()[0] == "launch" and "firefox" in ctl.last()[1]),
        ("şimdi tıkla", lambda: ctl.last() == ("click", "left", False)),
        ("biraz aşağı kaydır", lambda: ctl.last() == ("scroll", -6)),
        ("sayfayı yukarı kaydır", lambda: ctl.last() == ("scroll", 6)),
        ("dosyaları göster", lambda: ctl.last()[0] == "launch" and "nautilus" in ctl.last()[1]),
        ("lütfen sesi kıs", lambda: ctl.last() == ("press", "media_volume_down")),
        ("hesap makinesini aç", lambda: ctl.last()[0] == "launch"),
        ("satranç oyna", lambda: ctl.last()[0] == "launch" and "gnome-chess" in ctl.last()[1]),
        ("internete girmek istiyorum", lambda: ctl.last()[0] == "launch" and "firefox" in ctl.last()[1]),

        # --- sık siteler (ASR bozulmalarıyla birlikte) ---
        ("youtubeu aç", lambda: ctl.last() == ("url", "https://www.youtube.com")),
        ("youtube ağaç", lambda: ctl.last() == ("url", "https://www.youtube.com")),
        ("google aç", lambda: ctl.last() == ("url", "https://www.google.com")),
        ("vikipedi aç", lambda: ctl.last() == ("url", "https://tr.wikipedia.org")),

        # --- ASR bozulmaları (bulanık eşleşme) ---
        ("tikla", lambda: ctl.last() == ("click", "left", False)),
        ("kaydir asagi", lambda: ctl.last() == ("scroll", -6)),
        ("yapistir", lambda: ctl.last() == ("press", "ctrl", "v")),
        ("sacga tıkla", lambda: ctl.last()[0] == "click"),          # 'sağa tıkla' bozuk
        ("kopyla", lambda: ctl.last() == ("press", "ctrl", "c")),   # hece düşmüş

        # --- serbest metin ---
        ("yaz merhaba dünya", lambda: ctl.last() == ("type", "merhaba dünya")),
        ("yaz bugün hava çok güzel", lambda: ctl.last() == ("type", "bugün hava çok güzel")),

        # --- erişim ---
        ("göz takibini başlat", lambda: assist_calls[-1] == ("eye", True)),
        ("göz takibini durdur", lambda: assist_calls[-1] == ("eye", False)),
        ("yardım", lambda: assist_calls[-1] == ("help",)),
        ("asistan bugün günlerden ne", lambda: assist_calls[-1] == ("ask", "bugün günlerden ne")),
    ]

    passed = failed = 0
    for utt, check in CASES:
        n0 = len(ctl.calls)
        desc = router.handle(utt)
        try:
            ok = check() and (desc is not None)
        except (IndexError, TypeError):
            ok = False
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"  KALDI: {utt!r} → desc={desc!r} son_çağrı={ctl.last()!r}")
    print(f"Yerel dilbilgisi: {passed}/{passed + failed} geçti")

    # --- anlaşılmayanlar Gemini'ye gitmeli (None dönmeli) ---
    # uzun doğal site cümleleri Gemini'nin ARAMA planına gitmeli (yerel
    # "youtube aç" kısayolu yalnız ≤3 kelimelik söyleyişlerde çalışır)
    UNMATCHED = ["bana bir fıkra anlat", "saat kaç",
                 "bugün hava nasıl olacak",
                 "youtube'da kedi videoları açar mısın"]
    un_ok = 0
    for utt in UNMATCHED:
        if router.handle(utt) is None:
            un_ok += 1
        else:
            print(f"  YANLIŞ eşleşme: {utt!r} yerel katmanda eşleşti")
    print(f"Devretme (Gemini katmanına): {un_ok}/{len(UNMATCHED)} doğru")

    # --- Gemini niyetleri çalıştırma ---
    INTENTS = [
        ({"type": "launch", "target": "browser"},
         lambda: ctl.last()[0] == "launch"),
        ({"type": "open_url", "url": "https://www.youtube.com"},
         lambda: ctl.last() == ("url", "https://www.youtube.com")),
        ({"type": "type", "text": "selam"}, lambda: ctl.last() == ("type", "selam")),
        ({"type": "key", "keys": ["ctrl", "s"]}, lambda: ctl.last() == ("press", "ctrl", "s")),
        ({"type": "click", "button": "double"}, lambda: ctl.last() == ("click", "left", True)),
        ({"type": "scroll", "amount": -8}, lambda: ctl.last() == ("scroll", -8)),
        ({"type": "launch", "target": "chess"},
         lambda: ctl.last()[0] == "launch" and "gnome-chess" in ctl.last()[1]),
    ]
    int_ok = 0
    for intent, check in INTENTS:
        desc = router.execute_intent(intent)
        if check() and desc:
            int_ok += 1
        else:
            print(f"  NİYET KALDI: {intent}")
    # güvenlik: geçersiz niyetler hiçbir şey yapmamalı
    n0 = len(ctl.calls)
    assert router.execute_intent({"type": "launch", "target": "rm -rf"}) is None
    assert router.execute_intent({"type": "open_url", "url": "javascript:x"}) is None
    assert router.execute_intent({"type": "wipe_disk"}) is None
    assert len(ctl.calls) == n0, "geçersiz niyet çağrı üretti!"
    print(f"Niyet çalıştırma: {int_ok}/{len(INTENTS)} geçti (+3 güvenlik reddi)")

    total_fail = failed + (len(UNMATCHED) - un_ok) + (len(INTENTS) - int_ok)
    if total_fail:
        print(f"\n{total_fail} KOMUT TESTİ BAŞARISIZ")
        sys.exit(1)
    print("\nTÜM KOMUT TESTLERİ GEÇTİ")


if __name__ == "__main__":
    run_cases()
