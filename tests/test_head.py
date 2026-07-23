"""
Kafa işaretçisi testleri: YÖN kesinliği, nötr toplama, ortala, hassasiyet,
köşe mıknatısı. Göz modundaki yön hatası dersinden: işaret kuralları burada
sentetik landmarklarla kilitlenir.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

W, H = 1920, 1080


class P:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x, self.y = x, y


def make_face(nose_dx=0.0, nose_dy=0.0, squint=0.0, jaw_drop=0.0):
    """Aynalanmış kare geometrisiyle sahte yüz.

    squint: göz köşelerinin kısılma kayması (jest mimiği benzetimi).
    jaw_drop: çenenin düşmesi (ağız açma benzetimi).
    Yeni poz bu ikisinden ETKİLENMEMELİ (mimik-bağışıklık).
    """
    from app.vision.landmark_engine import (
        L_CORNERS, R_CORNERS, NOSE_TIP, CHIN, FOREHEAD, FACE_SIDES,
    )
    lm = [P(0.5, 0.5) for _ in range(478)]
    lm[L_CORNERS[0]] = P(0.62, 0.45 + squint)
    lm[L_CORNERS[1]] = P(0.52 - squint, 0.45 + squint)
    lm[R_CORNERS[0]] = P(0.48 + squint, 0.45 + squint)
    lm[R_CORNERS[1]] = P(0.38, 0.45 + squint)
    lm[NOSE_TIP] = P(0.50 + nose_dx, 0.58 + nose_dy)
    lm[CHIN] = P(0.50, 0.78 + jaw_drop)
    lm[FOREHEAD] = P(0.50, 0.18)
    lm[FACE_SIDES[0]] = P(0.30, 0.52)
    lm[FACE_SIDES[1]] = P(0.70, 0.52)
    return lm


def main():
    from app.vision.landmark_engine import LandmarkEngine
    from app.vision.head_mapper import HeadMapper, CornerMagnet

    pose = LandmarkEngine._pose_geometric
    checks = []

    # --- geometrik poz işaretleri ---
    y0, p0 = pose(make_face())
    yr, _ = pose(make_face(nose_dx=+0.03))   # kafa sağa (ayna: burun görüntü-sağa)
    yl, _ = pose(make_face(nose_dx=-0.03))
    _, pd = pose(make_face(nose_dy=+0.02))   # kafa aşağı eğik (burun düşer)
    _, pu = pose(make_face(nose_dy=-0.02))
    checks.append(("kafa sağa → yaw artar", yr > y0 > yl, f"{yl:+.3f}<{y0:+.3f}<{yr:+.3f}"))
    checks.append(("kafa aşağı → pitch artar", pd > p0 > pu, f"{pu:+.3f}<{p0:+.3f}<{pd:+.3f}"))

    # --- MİMİK BAĞIŞIKLIĞI: jest yüzü oynatsa da poz DEĞİŞMEMELİ ---
    # (kullanıcı şikayeti: tıklamak için göz kapayınca imleç hedeften kaçıyordu)
    ys, ps = pose(make_face(squint=0.015))       # göz kısma/kapama mimiği
    checks.append(("göz kapama pozu değiştirmez",
                   abs(ys - y0) < 1e-9 and abs(ps - p0) < 1e-9,
                   f"Δyaw={abs(ys-y0):.2e} Δpitch={abs(ps-p0):.2e}"))
    yj, pj = pose(make_face(jaw_drop=0.04))      # ağız açma mimiği
    checks.append(("ağız açma pozu değiştirmez",
                   abs(yj - y0) < 1e-9 and abs(pj - p0) < 1e-9,
                   f"Δyaw={abs(yj-y0):.2e} Δpitch={abs(pj-p0):.2e}"))

    # --- nötr toplama + eşleme yönü ---
    m = HeadMapper(W, H)
    for _ in range(HeadMapper.NEUTRAL_FRAMES):
        m.feed_neutral(y0, p0)
    checks.append(("nötr toplandı", m.ready, ""))
    cx, cy = m.map(y0, p0)
    checks.append(("nötr duruş ekran ortası", abs(cx - W / 2) < 2 and abs(cy - H / 2) < 2,
                   f"({cx:.0f},{cy:.0f})"))
    xr, _ = m.map(yr, p0)
    xl, _ = m.map(yl, p0)
    _, yd = m.map(y0, pd)
    _, yu = m.map(y0, pu)
    checks.append(("sağa çevir → imleç sağa", xr > W / 2 > xl, f"{xl:.0f}|{xr:.0f}"))
    checks.append(("aşağı eğ → imleç aşağı", yd > H / 2 > yu, f"{yu:.0f}|{yd:.0f}"))

    # --- hassasiyet: yüksek değer aynı harekette daha çok yol ---
    m.sensitivity = 20
    x_low, _ = m.map(y0 + 0.05, p0)
    m.sensitivity = 90
    x_high, _ = m.map(y0 + 0.05, p0)
    checks.append(("hassasiyet monoton", x_high >= x_low, f"{x_low:.0f}→{x_high:.0f}"))

    # --- ortala: yeni duruş merkez olur ---
    m.recenter()
    for _ in range(HeadMapper.NEUTRAL_FRAMES):
        m.feed_neutral(y0 + 0.08, p0 + 0.05)
    nx, ny = m.map(y0 + 0.08, p0 + 0.05)
    checks.append(("ortala sonrası yeni duruş merkez",
                   abs(nx - W / 2) < 2 and abs(ny - H / 2) < 2, f"({nx:.0f},{ny:.0f})"))

    # --- köşe mıknatısı ---
    mag = CornerMagnet(W, H)
    fx, fy = mag.apply(W / 2, H / 2)
    checks.append(("merkezde mıknatıs etkisiz", (fx, fy) == (W / 2, H / 2), ""))
    px_, py_ = W - 60, 50   # sağ üst köşeye yakın (kapat düğmesi bölgesi)
    for _ in range(12):
        px_, py_ = mag.apply(px_, py_)
    d = ((px_ - (W - mag.MARGIN)) ** 2 + (py_ - mag.MARGIN) ** 2) ** 0.5
    checks.append(("sağ üst köşede kapat düğmesine oturur", d < 6, f"kalan {d:.1f}px"))
    mag.enabled = False
    gx, gy = mag.apply(W - 60, 50)
    checks.append(("mıknatıs kapatılabilir", (gx, gy) == (W - 60, 50), ""))

    failed = 0
    for name, ok, info in checks:
        print(f"{'GEÇTİ' if ok else 'KALDI':6s} {name}  [{info}]")
        failed += (not ok)
    if failed:
        print(f"\n{failed} KAFA TESTİ BAŞARISIZ")
        sys.exit(1)
    print("\nTÜM KAFA TESTLERİ GEÇTİ")


if __name__ == "__main__":
    main()
