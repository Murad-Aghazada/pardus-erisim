"""
Jest tıklaması + plan çözümleme testleri.

Jest: 21 fps'lik sentetik skor dizileriyle davranış kilitlenir — doğal (kısa)
göz kırpma ASLA tıklamamalı, ~yarım saniyelik kapama TAM BİR kez tıklamalı,
imleç gözler kapanırken donmalı, art arda tetikleme engellenmeli.

Plan: Gemini yanıtlarının temizlenmesi — izinsiz adımlar atılır, wait
sınırlanır, eski tek-adım biçimi desteklenir.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DT = 1.0 / 21.0     # kullanıcının kamerasında ölçülen kare aralığı


def feed(gc, seq, base=None):
    """Skor dizisini kare kare ver; (tıklama sayısı, donma karesi sayısı)."""
    clicks = frozen = 0
    t = 100.0
    for v in seq:
        scores = dict(base or {})
        scores.update(v if isinstance(v, dict) else {"blink": v})
        c, f = gc.update(scores, t)
        clicks += c
        frozen += f
        t += DT
    return clicks, frozen


def main():
    from app.vision.gestures import GestureClick
    from app.assist.gemini_client import parse_plan

    checks = []

    # --- doğal hızlı kırpma (2 kare kapalı ≈ 95 ms): tıklama YOK ---
    gc = GestureClick("long_blink")
    seq = [0.25] * 20 + [0.85, 0.85] + [0.25] * 20
    c, _ = feed(gc, seq)
    checks.append(("doğal kırpma tıklamaz", c == 0, f"tık={c}"))

    # --- kullanıcının yüksek taban değeri (0.30) yanlış tetiklemez ---
    gc = GestureClick("long_blink")
    c, _ = feed(gc, [0.30, 0.35, 0.42, 0.38, 0.30] * 30)
    checks.append(("yüksek açık-göz tabanı güvenli", c == 0, f"tık={c}"))

    # --- yarım saniyelik kapama: TAM BİR tıklama + kapanırken donma ---
    gc = GestureClick("long_blink")
    seq = [0.25] * 10 + [0.80] * 11 + [0.25] * 10   # 11 kare ≈ 0.52 sn
    c, f = feed(gc, seq)
    checks.append(("uzun kapama tam 1 tıklar", c == 1, f"tık={c}"))
    checks.append(("kapalıyken imleç donar", f >= 10, f"donma={f} kare"))

    # --- tutmaya devam: yine 1 tıklama (yeniden ateşleme yok) ---
    gc = GestureClick("long_blink")
    c, _ = feed(gc, [0.25] * 5 + [0.85] * 40 + [0.25] * 5)
    checks.append(("uzun tutma yine 1 tıklar", c == 1, f"tık={c}"))

    # --- soğuma: iki hızlı ardışık uzun kapama → 2. de sayılır ama
    #     1 sn içindeki denemeler reddedilir ---
    gc = GestureClick("long_blink")
    burst = [0.25] * 3 + [0.80] * 10 + [0.25] * 3
    c, _ = feed(gc, burst + burst)          # ikinci giriş ~0.9 sn sonra
    checks.append(("soğuma süresi korur", c == 1, f"tık={c}"))
    gc = GestureClick("long_blink")
    c2, _ = feed(gc, burst + [0.25] * 22 + burst)   # araya >1 sn sükunet girince
    checks.append(("soğuma sonrası çalışır", c2 == 2, f"tık={c2}"))

    # --- titreşen sinyal (eşik çevresinde): tıklama yok ---
    gc = GestureClick("long_blink")
    c, _ = feed(gc, [0.55, 0.65, 0.40, 0.62, 0.42, 0.60, 0.41] * 8)
    checks.append(("eşik titremesi tıklamaz", c == 0, f"tık={c}"))

    # --- kaş kaldırma: uyarlanabilir taban ---
    gc = GestureClick("brow")
    seq = [{"brow": 0.12}] * 30 + [{"brow": 0.55}] * 7 + [{"brow": 0.12}] * 10
    c, _ = feed(gc, seq)
    checks.append(("kaş kaldırma tıklar", c == 1, f"tık={c}"))
    gc = GestureClick("brow")
    c, _ = feed(gc, [{"brow": 0.12 + 0.03 * (i % 3)} for i in range(80)])
    checks.append(("doğal kaş oynaması tıklamaz", c == 0, f"tık={c}"))

    # --- ağız açma ---
    gc = GestureClick("mouth")
    c, _ = feed(gc, [{"jaw": 0.05}] * 10 + [{"jaw": 0.7}] * 8 + [{"jaw": 0.05}] * 5)
    checks.append(("ağız açma tıklar", c == 1, f"tık={c}"))

    # --- kapalı: hiçbir şey ---
    gc = GestureClick("off")
    c, f = feed(gc, [0.9] * 40)
    checks.append(("jest kapalıyken etkisiz", c == 0 and f == 0, ""))

    # ---- Plan çözümleme ----
    p = parse_plan('{"say":"Açıyorum","steps":[{"type":"open_url",'
                   '"url":"https://www.youtube.com/results?search_query=kedi"},'
                   '{"type":"wait","ms":99999},'
                   '{"type":"shutdown"},'
                   '{"type":"open_url","url":"javascript:alert(1)"},'
                   '{"type":"type","text":"selam"}]}')
    ok = (p is not None and len(p["steps"]) == 3
          and p["steps"][1]["ms"] == 5000
          and all(s["type"] in ("open_url", "wait", "type") for s in p["steps"]))
    checks.append(("plan temizleme: izinsiz/tehlikeli adımlar atılır", ok, str(p)))

    p2 = parse_plan('{"type":"launch","target":"chess"}')
    checks.append(("eski tek-adım biçimi plana sarılır",
                   p2 is not None and p2["steps"][0]["target"] == "chess", str(p2)))

    p3 = parse_plan('{"type":"answer","text":"Dört eder."}')
    checks.append(("answer → yalnız say",
                   p3 is not None and p3["say"] == "Dört eder." and not p3["steps"], str(p3)))

    p4 = parse_plan('{"say":"Bunu yapamam","steps":[]}')
    checks.append(("reddetme planı geçerli",
                   p4 is not None and not p4["steps"], str(p4)))

    # ---- Geri sarma kilidi: tıklama, jest ÖNCESİ konuma gitmeli ----
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    _app = QCoreApplication.instance() or QCoreApplication([])
    from app.vision.eye_tracker import EyeTracker
    tr = EyeTracker(1920, 1080)
    # imleç düğmeye doğru ilerliyor: t=100.0'dan itibaren 20 örnek
    for i in range(20):
        tr._history.append((100.0 + i * 0.05, 100 + i * 10, 200))
    # jest t=101.0'da başladı → kilit, REWIND_S (0.35 sn) öncesinin konumu
    pos = tr._pos_before(101.0 - tr.REWIND_S)
    checks.append(("tıklama jest öncesi konuma kilitlenir",
                   pos == (230, 200), f"pos={pos}"))
    pos2 = tr._pos_before(99.0)     # tampondan eski istek → en eski konum
    checks.append(("tampon öncesi istek ilk konuma düşer",
                   pos2 == (100, 200), f"pos={pos2}"))

    failed = 0
    for name, ok, info in checks:
        print(f"{'GEÇTİ' if ok else 'KALDI':6s} {name}  [{info if not ok else ''}]")
        failed += (not ok)
    if failed:
        print(f"\n{failed} JEST/PLAN TESTİ BAŞARISIZ")
        sys.exit(1)
    print("\nTÜM JEST VE PLAN TESTLERİ GEÇTİ")


if __name__ == "__main__":
    main()
