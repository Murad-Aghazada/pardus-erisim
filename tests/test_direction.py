"""
Bakış YÖN doğruluğu testleri (regresyon kilidi).

Kullanıcı raporuyla yakalanan iki gerçek hata buraya kilitlenir:
1. Aynalanmış karede köşe indeks sırası yatay yönü tersine çeviriyordu.
2. Göz kapağına göre dikey oran, kapaklar bakışı izlediği için dikey yönü
   tersine çeviriyordu (dikey referans köşe çizgisi olmalı).

Sentetik landmarklarla: sola bakış → ekran solu, aşağı bakış → ekran altı,
ve kapak hareketi orana ETKİ ETMEZ garantileri doğrulanır.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class P:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x, self.y = x, y


def make_face(iris_dx=0.0, iris_dy=0.0, lid_shift=0.0):
    """478 landmark'lı sahte yüz (aynalanmış kare geometrisi).

    iris_dx/dy: iris merkezlerinin nötrden kayması (görüntü koordinatı).
    lid_shift: kapakların (iristen bağımsız) aşağı kayması.
    """
    from app.vision.landmark_engine import (
        L_CORNERS, R_CORNERS, L_LID, R_LID, L_IRIS, R_IRIS,
        NOSE_TIP, CHIN, FOREHEAD,
    )
    lm = [P(0.5, 0.5) for _ in range(478)]

    # 33/133 gözü (görüntünün sağı): dış köşe 0.62, iç köşe 0.52
    lm[L_CORNERS[0]] = P(0.62, 0.50)
    lm[L_CORNERS[1]] = P(0.52, 0.50)
    # 362/263 gözü (görüntünün solu): iç 0.48, dış 0.38
    lm[R_CORNERS[0]] = P(0.48, 0.50)
    lm[R_CORNERS[1]] = P(0.38, 0.50)

    # kapaklar (yeni metrikte kullanılmıyor; bağımsızlık testi için)
    lm[L_LID[0]] = P(0.57, 0.485 + lid_shift)
    lm[L_LID[1]] = P(0.57, 0.515 + lid_shift)
    lm[R_LID[0]] = P(0.43, 0.485 + lid_shift)
    lm[R_LID[1]] = P(0.43, 0.515 + lid_shift)

    # iris kümeleri: nötrde göz merkezinde, köşe çizgisi üzerinde
    for i in L_IRIS:
        lm[i] = P(0.57 + iris_dx, 0.50 + iris_dy)
    for i in R_IRIS:
        lm[i] = P(0.43 + iris_dx, 0.50 + iris_dy)

    # kafa pozu noktaları
    lm[NOSE_TIP] = P(0.50, 0.60)
    lm[CHIN] = P(0.50, 0.80)
    lm[FOREHEAD] = P(0.50, 0.20)
    return lm


def main():
    from app.vision.landmark_engine import LandmarkEngine
    from app.vision.gaze_mapper import GazeMapper

    ratio = LandmarkEngine._gaze_ratio
    W, H = 1920, 1080
    m = GazeMapper(W, H)
    m.forget()          # varsayılan eşleme test edilir

    checks = []

    # --- nötr: ekran ortası civarı ---
    rx, ry = ratio(make_face())
    x, y = m.map(rx, ry)
    checks.append(("nötr bakış merkeze yakın",
                   abs(x - W / 2) < W * 0.2 and abs(y - H / 2) < H * 0.30,
                   f"({x:.0f},{y:.0f})"))

    # --- sola bakış (ayna görünümünde iris görüntü-soluna kayar) ---
    rx_l, _ = ratio(make_face(iris_dx=-0.02))
    x_l, _ = m.map(rx_l, ry)
    checks.append(("SOLA bakış → imleç SOL yarıda", x_l < W * 0.5 and rx_l < rx,
                   f"rx={rx_l:.3f} x={x_l:.0f}"))

    # --- sağa bakış ---
    rx_r, _ = ratio(make_face(iris_dx=+0.02))
    x_r, _ = m.map(rx_r, ry)
    checks.append(("SAĞA bakış → imleç SAĞ yarıda", x_r > W * 0.5 and rx_r > rx,
                   f"rx={rx_r:.3f} x={x_r:.0f}"))

    # --- aşağı bakış (iris görüntüde AŞAĞI iner = y artar) ---
    _, ry_d = ratio(make_face(iris_dy=+0.012))
    _, y_d = m.map(rx, ry_d)
    checks.append(("AŞAĞI bakış → imleç ALT yarıda", y_d > H * 0.5 and ry_d > ry,
                   f"ry={ry_d:.3f} y={y_d:.0f}"))

    # --- yukarı bakış ---
    _, ry_u = ratio(make_face(iris_dy=-0.012))
    _, y_u = m.map(rx, ry_u)
    checks.append(("YUKARI bakış → imleç ÜST yarıda", y_u < H * 0.5 and ry_u < ry,
                   f"ry={ry_u:.3f} y={y_u:.0f}"))

    # --- kapak bağımsızlığı: kapaklar kayarsa oran DEĞİŞMEMELİ ---
    r0 = ratio(make_face())
    r1 = ratio(make_face(lid_shift=+0.01))
    checks.append(("kapak hareketi oranı değiştirmez",
                   abs(r0[0] - r1[0]) < 1e-9 and abs(r0[1] - r1[1]) < 1e-9,
                   f"Δ=({abs(r0[0]-r1[0]):.2e},{abs(r0[1]-r1[1]):.2e})"))

    # --- ayna/indeks sırası güvenliği: köşeler ters listelense bile yön aynı ---
    import app.vision.landmark_engine as le
    lm = make_face(iris_dx=-0.02)
    lm[le.L_CORNERS[0]], lm[le.L_CORNERS[1]] = lm[le.L_CORNERS[1]], lm[le.L_CORNERS[0]]
    lm[le.R_CORNERS[0]], lm[le.R_CORNERS[1]] = lm[le.R_CORNERS[1]], lm[le.R_CORNERS[0]]
    rx_swap, _ = ratio(lm)
    checks.append(("köşe sırası değişse de yön korunur", abs(rx_swap - rx_l) < 1e-9,
                   f"rx={rx_swap:.3f}"))

    failed = 0
    for name, ok, info in checks:
        print(f"{'GEÇTİ' if ok else 'KALDI':6s} {name}  [{info}]")
        failed += (not ok)
    if failed:
        print(f"\n{failed} YÖN TESTİ BAŞARISIZ")
        sys.exit(1)
    print("\nTÜM YÖN TESTLERİ GEÇTİ")


if __name__ == "__main__":
    main()
