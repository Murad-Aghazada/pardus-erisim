"""
Jest tıklaması + plan çözümleme testleri.

Jest: 21 fps'lik sentetik skor dizileriyle davranış kilitlenir — doğal (kısa)
göz kırpma ASLA tıklamamalı, ~yarım saniyelik kapama TAM BİR kez tıklamalı,
imleç gözler kapanırken donmalı, art arda tetikleme engellenmeli.

Çok yuvalı (sol/sağ/orta tık) testleri: aynı anda birden fazla eylem
bağımsız jestlere bağlanabilir; simetrik (iki göz) bir kırpma tek-göz
(wink) yuvalarını ASLA tetiklememeli — wink sinyali sol-sağ FARKI olduğu
için simetrik kapanışta sıfıra yakın kalır.

Plan: Gemini yanıtlarının temizlenmesi — izinsiz adımlar atılır, wait
sınırlanır, eski tek-adım biçimi desteklenir.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DT = 1.0 / 21.0     # kullanıcının kamerasında ölçülen kare aralığı


def feed(slot, seq, base=None):
    """Tek yuva (_GestureSlot): (tıklama sayısı, donma karesi sayısı)."""
    clicks = frozen = 0
    t = 100.0
    for v in seq:
        scores = dict(base or {})
        scores.update(v if isinstance(v, dict) else {"blink": v})
        c, f = slot.update(scores, t)
        clicks += c
        frozen += f
        t += DT
    return clicks, frozen


def feed_multi(gc, seq):
    """Çok yuvalı (GestureClick): bu koşu boyunca tetiklenen eylemlerin listesi."""
    fired_all = []
    t = 100.0
    for scores in seq:
        fired, _ = gc.update(scores, t)
        fired_all.extend(fired)
        t += DT
    return fired_all


def main():
    from app.vision.gestures import _GestureSlot, GestureClick
    from app.assist.gemini_client import parse_plan

    checks = []

    # --- doğal hızlı kırpma (2 kare kapalı ≈ 95 ms): tıklama YOK ---
    gs = _GestureSlot("long_blink")
    seq = [0.25] * 20 + [0.85, 0.85] + [0.25] * 20
    c, _ = feed(gs, seq)
    checks.append(("doğal kırpma tıklamaz", c == 0, f"tık={c}"))

    # --- kullanıcının yüksek taban değeri (0.30) yanlış tetiklemez ---
    gs = _GestureSlot("long_blink")
    c, _ = feed(gs, [0.30, 0.35, 0.42, 0.38, 0.30] * 30)
    checks.append(("yüksek açık-göz tabanı güvenli", c == 0, f"tık={c}"))

    # --- yarım saniyelik kapama: TAM BİR tıklama + kapanırken donma ---
    gs = _GestureSlot("long_blink")
    seq = [0.25] * 10 + [0.80] * 11 + [0.25] * 10   # 11 kare ≈ 0.52 sn
    c, f = feed(gs, seq)
    checks.append(("uzun kapama tam 1 tıklar", c == 1, f"tık={c}"))
    checks.append(("kapalıyken imleç donar", f >= 10, f"donma={f} kare"))

    # --- tutmaya devam: yine 1 tıklama (yeniden ateşleme yok) ---
    gs = _GestureSlot("long_blink")
    c, _ = feed(gs, [0.25] * 5 + [0.85] * 40 + [0.25] * 5)
    checks.append(("uzun tutma yine 1 tıklar", c == 1, f"tık={c}"))

    # --- soğuma: iki hızlı ardışık uzun kapama → 2. de sayılır ama
    #     1 sn içindeki denemeler reddedilir ---
    gs = _GestureSlot("long_blink")
    burst = [0.25] * 3 + [0.80] * 10 + [0.25] * 3
    c, _ = feed(gs, burst + burst)          # ikinci giriş ~0.9 sn sonra
    checks.append(("soğuma süresi korur", c == 1, f"tık={c}"))
    gs = _GestureSlot("long_blink")
    c2, _ = feed(gs, burst + [0.25] * 22 + burst)   # araya >1 sn sükunet girince
    checks.append(("soğuma sonrası çalışır", c2 == 2, f"tık={c2}"))

    # --- titreşen sinyal (eşik çevresinde): tıklama yok ---
    gs = _GestureSlot("long_blink")
    c, _ = feed(gs, [0.55, 0.65, 0.40, 0.62, 0.42, 0.60, 0.41] * 8)
    checks.append(("eşik titremesi tıklamaz", c == 0, f"tık={c}"))

    # --- kaş kaldırma: uyarlanabilir taban ---
    gs = _GestureSlot("brow")
    seq = [{"brow": 0.12}] * 30 + [{"brow": 0.55}] * 7 + [{"brow": 0.12}] * 10
    c, _ = feed(gs, seq)
    checks.append(("kaş kaldırma tıklar", c == 1, f"tık={c}"))
    gs = _GestureSlot("brow")
    c, _ = feed(gs, [{"brow": 0.12 + 0.03 * (i % 3)} for i in range(80)])
    checks.append(("doğal kaş oynaması tıklamaz", c == 0, f"tık={c}"))

    # --- ağız açma ---
    gs = _GestureSlot("mouth")
    c, _ = feed(gs, [{"jaw": 0.05}] * 10 + [{"jaw": 0.7}] * 8 + [{"jaw": 0.05}] * 5)
    checks.append(("ağız açma tıklar", c == 1, f"tık={c}"))

    # --- kapalı: hiçbir şey ---
    gs = _GestureSlot("off")
    c, f = feed(gs, [0.9] * 40)
    checks.append(("jest kapalıyken etkisiz", c == 0 and f == 0, ""))

    # ---- AYNA TAKASI: blink_left GERÇEKTEN kullanıcının sol gözü olmalı ----
    # eye_tracker kareyi aynalar, bu yüzden MediaPipe'ın "eyeBlinkLeft"i
    # kullanıcının SAĞ gözüdür. Takas bozulursa sol göz kırpma sağ tıkı
    # tetikler (canlı olarak yaşanan hata) — bu test onu yakalar.
    from app.vision.landmark_engine import LandmarkEngine

    class _FakeCat:
        def __init__(self, name, score):
            self.category_name, self.score = name, score

    class _FakeRes:
        # kullanıcı SOL gözünü kapatıyor: aynalanmış karede bu
        # MediaPipe'a "eyeBlinkRight" olarak görünür
        face_blendshapes = [[_FakeCat("eyeBlinkLeft", 0.10),
                             _FakeCat("eyeBlinkRight", 0.90)]]

    sc = LandmarkEngine._gesture_scores(_FakeRes())
    checks.append(("ayna takası: kullanıcının sol gözü blink_left'e düşer",
                   sc.get("blink_left") == 0.90 and sc.get("blink_right") == 0.10,
                   f"blink_left={sc.get('blink_left')} blink_right={sc.get('blink_right')}"))

    # ---- Tek göz (wink) — simetrik kırpmayla çakışmaz ----
    gs = _GestureSlot("wink_right")
    seq = [{"blink_left": 0.20, "blink_right": 0.20}] * 10 + \
          [{"blink_left": 0.20, "blink_right": 0.85}] * 11 + \
          [{"blink_left": 0.20, "blink_right": 0.20}] * 10
    c, _ = feed(gs, seq)
    checks.append(("sağ göz kırpma (wink_right) tıklar", c == 1, f"tık={c}"))

    gs = _GestureSlot("wink_right")
    # her iki göz BİRLİKTE kapanıyor (doğal kırpma) — fark sıfıra yakın kalmalı
    seq = [{"blink_left": 0.20, "blink_right": 0.20}] * 10 + \
          [{"blink_left": 0.82, "blink_right": 0.85}] * 11 + \
          [{"blink_left": 0.20, "blink_right": 0.20}] * 10
    c, _ = feed(gs, seq)
    checks.append(("simetrik kırpma wink'i tetiklemez", c == 0, f"tık={c}"))

    # --- REGRESYON: kişinin doğal dinlenme asimetrisi (sağ göz her zaman
    #     ~0.20 daha yüksek skorlu, hiç kırpmadan) kalıcı donmaya YOL AÇMAMALI
    #     — taban çıkarılmazsa bu ham fark eşiği sürekli aşar ve imleç
    #     hiç hareket edemez ("çok laggy, hareket etmiyor" hatası) ---
    gs = _GestureSlot("wink_right")
    seq = [{"blink_left": 0.15, "blink_right": 0.35}] * 60   # sabit asimetri, kırpma yok
    _, f = feed(gs, seq)
    checks.append(("doğal dinlenme asimetrisi imleci dondurmaz", f == 0, f"donma={f} kare"))

    # ---- Wink tepkiselliği: doğal süreli (kısa) bir wink tıklamalı ----
    # Eskiden 0.30 sn tutma isteniyordu; gerçek winkler 0.15-0.25 sn sürdüğü
    # için kullanıcı bir düğmeye basmak için 4-5 kez denemek zorunda kalıyordu.
    CALM = [{"blink_left": 0.16, "blink_right": 0.10}] * 20   # taban asimetrisi 0.06

    def wink_seq(frames):
        return (CALM + [{"blink_left": 0.91, "blink_right": 0.12}] * frames
                + [{"blink_left": 0.16, "blink_right": 0.10}] * 10)

    gs = _GestureSlot("wink_left")
    c, _ = feed(gs, wink_seq(4))         # 0.19 sn — rampasız, en zor durum
    checks.append(("kısa kasıtlı wink (0.19 sn) tıklar", c == 1, f"tık={c}"))

    gs = _GestureSlot("wink_left")
    c, _ = feed(gs, wink_seq(2))         # 0.10 sn — fazla kısa, gürültü olabilir
    checks.append(("çok kısa titreşim (0.10 sn) tıklamaz", c == 0, f"tık={c}"))

    # Üç kasıtlı wink arka arkaya: bekleme süresi denemeleri yutmamalı
    gs = _GestureSlot("wink_left")
    seq = list(CALM)
    for _ in range(3):
        seq += [{"blink_left": 0.91, "blink_right": 0.12}] * 5
        seq += [{"blink_left": 0.16, "blink_right": 0.10}] * 13
    c, _ = feed(gs, seq)
    checks.append(("arka arkaya 3 wink = 3 tıklama", c == 3, f"tık={c}"))

    # GÜVENLİK: doğal kırpmada bir göz diğerinden önce kapanabilir; bu geçici
    # asimetri tıklama üretmemeli (wink'in tek güvenlik katmanı asimetridir)
    gs = _GestureSlot("wink_left")
    seq = (CALM
           + [{"blink_left": 0.80, "blink_right": 0.15},
              {"blink_left": 0.90, "blink_right": 0.30},
              {"blink_left": 0.92, "blink_right": 0.55}]
           + [{"blink_left": 0.92, "blink_right": 0.90}] * 6
           + [{"blink_left": 0.16, "blink_right": 0.10}] * 10)
    c, _ = feed(gs, seq)
    checks.append(("bir göz önde kapanan doğal kırpma tıklamaz", c == 0, f"tık={c}"))

    # GÜVENLİK: en yüksek hassasiyette bile simetrik kırpma tıklamamalı
    gs = _GestureSlot("wink_left"); gs.sensitivity = 100
    c, _ = feed(gs, CALM + [{"blink_left": 0.88, "blink_right": 0.85}] * 10
                + [{"blink_left": 0.16, "blink_right": 0.10}] * 10)
    checks.append(("azami hassasiyette simetrik kırpma tıklamaz", c == 0, f"tık={c}"))

    # Hassasiyet gerçekten etkili mi: düşük hassasiyet kısa wink'i reddeder
    gs = _GestureSlot("wink_left"); gs.sensitivity = 10
    lo_c, _ = feed(gs, wink_seq(4))
    gs = _GestureSlot("wink_left"); gs.sensitivity = 100
    hi_c, _ = feed(gs, wink_seq(4))
    checks.append(("hassasiyet kaydırıcısı etkili (düşük=0, yüksek=1)",
                   lo_c == 0 and hi_c == 1, f"düşük={lo_c} yüksek={hi_c}"))

    # ---- Çok yuvalı: bağımsız eylemler, çakışma yok ----
    # sol=long_blink (iki göz), sağ=wink_right (yalnız sağ göz)
    gc = GestureClick({"left": "long_blink", "right": "wink_right", "middle": "off"})
    seq = [{"blink": 0.22, "blink_left": 0.22, "blink_right": 0.22}] * 10 + \
          [{"blink": 0.80, "blink_left": 0.80, "blink_right": 0.80}] * 11 + \
          [{"blink": 0.22, "blink_left": 0.22, "blink_right": 0.22}] * 10
    fired = feed_multi(gc, seq)
    checks.append(("simetrik kırpma yalnız SOL tıkı tetikler, SAĞ'ı asla",
                   fired.count("left") == 1 and fired.count("right") == 0,
                   f"fired={fired}"))

    gc = GestureClick({"left": "long_blink", "right": "wink_right", "middle": "off"})
    seq = [{"blink": 0.20, "blink_left": 0.20, "blink_right": 0.20}] * 10 + \
          [{"blink": 0.475, "blink_left": 0.10, "blink_right": 0.85}] * 11 + \
          [{"blink": 0.20, "blink_left": 0.20, "blink_right": 0.20}] * 10
    fired = feed_multi(gc, seq)
    checks.append(("yalnız sağ göz kırpma SAĞ tıkı tetikler, SOL'u asla",
                   fired.count("right") == 1 and fired.count("left") == 0,
                   f"fired={fired}"))

    # üç bağımsız yuva üç farklı jestle aynı koşuda ayrı ayrı tetiklenebilir
    gc = GestureClick({"left": "wink_left", "right": "wink_right", "middle": "brow"})
    seq = ([{"blink_left": 0.15, "blink_right": 0.15, "brow": 0.10}] * 15
           + [{"blink_left": 0.85, "blink_right": 0.15, "brow": 0.10}] * 11
           + [{"blink_left": 0.15, "blink_right": 0.15, "brow": 0.10}] * 22
           + [{"blink_left": 0.15, "blink_right": 0.85, "brow": 0.10}] * 11
           + [{"blink_left": 0.15, "blink_right": 0.15, "brow": 0.10}] * 22
           + [{"blink_left": 0.15, "blink_right": 0.15, "brow": 0.45}] * 6
           + [{"blink_left": 0.15, "blink_right": 0.15, "brow": 0.10}] * 5)
    fired = feed_multi(gc, seq)
    checks.append(("üç bağımsız yuva sırayla ayrı tetiklenir",
                   fired.count("left") == 1 and fired.count("right") == 1
                   and fired.count("middle") == 1, f"fired={fired}"))

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
    # jest t=101.0'da başladı → kilit, REWIND_S kadar öncesinin konumu.
    # Beklenen değer sabitten TÜRETİLİR: REWIND_S ayarlanınca test yanlış
    # yere çakılı kalmasın (örnekler 0.05 sn aralıklı, x = 100 + 10*i).
    idx = int((101.0 - tr.REWIND_S - 100.0) / 0.05)
    pos = tr._pos_before(101.0 - tr.REWIND_S)
    checks.append(("tıklama jest öncesi konuma kilitlenir",
                   pos == (100 + 10 * idx, 200), f"pos={pos} beklenen_i={idx}"))
    # Geri sarma, nişan alma süresini yutmayacak kadar KISA olmalı: aksi
    # halde kullanıcı düğmeye nişan alıp hemen jest yaptığında tıklama
    # nişan almadan önceki konuma düşer (canlı yaşanan hata).
    checks.append(("geri sarma tamponu kısa (<=0.20 sn)",
                   tr.REWIND_S <= 0.20, f"REWIND_S={tr.REWIND_S}"))
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
