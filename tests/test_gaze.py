"""
Bakış eşleyici doğruluk testleri — sentetik senaryolar.

Gerçek bir göz benzetimi kurulur: kişi ekranda (X, Y) noktasına bakarken
iris oranının nasıl ölçüleceği bilinen bir ileri modelle üretilir (gürültü ve
kafa pozu etkisi dahil). Kalibrasyon bu ölçümlerle yapılır; sonra hiç
görülmemiş noktalarda eşleme hatası piksel cinsinden ölçülür.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

SCREEN_W, SCREEN_H = 1920, 1080
GRID = [
    (0.08, 0.10), (0.5, 0.10), (0.92, 0.10),
    (0.08, 0.5),  (0.5, 0.5),  (0.92, 0.5),
    (0.08, 0.90), (0.5, 0.90), (0.92, 0.90),
]


class SyntheticEye:
    """İleri model: bakılan nokta + kafa pozu → ölçülen bakış metriği.

    Yeni metrik (landmark_engine): yatay köşe-arası oran (nötr ~0.5),
    dikey köşe çizgisine göre göz-genişliği birimi (nötr ~0.0).
    """

    def __init__(self, rng, noise_std=0.010, curvature=0.03):
        self.rng = rng
        self.noise = noise_std
        self.curve = curvature

    def measure(self, X, Y, yaw=0.0, pitch=0.0):
        # doğrusal taban + hafif eğrilik + kafa pozu kaçağı + gürültü
        rx = 0.50 + 0.28 * (X - 0.5) + self.curve * (X - 0.5) ** 2 + 0.10 * yaw
        ry = 0.00 + 0.14 * (Y - 0.5) + self.curve * (Y - 0.5) ** 2 + 0.12 * pitch
        rx += self.rng.normal(0, self.noise)
        ry += self.rng.normal(0, self.noise)
        return rx, ry


def calibrate(mapper, eye, yaw_fn, pitch_fn, samples_per_point=21):
    from app.vision.gaze_mapper import GazeMapper
    mapper.clear()
    for gx, gy in GRID:
        yaw, pitch = yaw_fn(gx, gy), pitch_fn(gx, gy)
        obs = [eye.measure(gx, gy, yaw, pitch) for _ in range(samples_per_point)]
        rxs = sorted(o[0] for o in obs)
        rys = sorted(o[1] for o in obs)
        med = (rxs[len(rxs) // 2], rys[len(rys) // 2])
        mapper.add_sample(med[0], med[1], yaw, pitch,
                          gx * SCREEN_W, gy * SCREEN_H)
    assert mapper.fit(), "kalibrasyon fit edilemedi"


def eval_error(mapper, eye, yaw=0.0, pitch=0.0, n=50, average=20):
    """Görülmemiş noktalarda TIKLAMA hatası (px).

    average=20: dwell tıklaması 900 ms bakış penceresinin ORTALAMASINA gider
    (gaze_overlay), ~21 fps'te ≈20 kare. Ölçülen şey, kullanıcının tıklamak
    istediği noktaya tıklamanın ne kadar yakın düştüğüdür.
    """
    rng = np.random.default_rng(7)
    errs = []
    for _ in range(n):
        X, Y = rng.uniform(0.05, 0.95), rng.uniform(0.05, 0.95)
        # birden çok kare ortalaması (filtrenin durağan etkisine eşdeğer)
        pts = [mapper.map(*eye.measure(X, Y, yaw, pitch), yaw, pitch)
               for _ in range(average)]
        px = np.mean([p[0] for p in pts])
        py = np.mean([p[1] for p in pts])
        errs.append(np.hypot(px - X * SCREEN_W, py - Y * SCREEN_H))
    return float(np.mean(errs)), float(np.max(errs))


def main():
    from app.vision.gaze_mapper import GazeMapper

    results = []
    rng = np.random.default_rng(42)

    # ---- Senaryo 1: sabit kafa, normal gürültü ----
    eye = SyntheticEye(rng)
    m = GazeMapper(SCREEN_W, SCREEN_H); m.forget()
    calibrate(m, eye, lambda x, y: 0.0, lambda x, y: 0.0)
    mean, worst = eval_error(m, eye)
    results.append(("Sabit kafa, gürültülü ölçüm", mean, worst, 35))

    # ---- Senaryo 2: yüksek gürültü (kötü ışık) ----
    eye2 = SyntheticEye(rng, noise_std=0.02)
    m2 = GazeMapper(SCREEN_W, SCREEN_H); m2.forget()
    calibrate(m2, eye2, lambda x, y: 0.0, lambda x, y: 0.0)
    mean2, worst2 = eval_error(m2, eye2)
    results.append(("Yüksek gürültü (kötü ışık)", mean2, worst2, 60))

    # ---- Senaryo 3: kafa hareketi — kalibrasyonda hafif poz çeşitliliği,
    #      değerlendirmede belirgin poz kayması ----
    eye3 = SyntheticEye(rng)
    m3 = GazeMapper(SCREEN_W, SCREEN_H); m3.forget()
    pose_rng = np.random.default_rng(3)
    calibrate(m3, eye3,
              lambda x, y: pose_rng.normal(0, 0.05),
              lambda x, y: pose_rng.normal(0, 0.04))
    mean3, worst3 = eval_error(m3, eye3, yaw=0.08, pitch=0.05)
    results.append(("Kafa 8° sağa dönük", mean3, worst3, 80))

    # ---- Senaryo 4: güçlü eğrilik (geniş ekran kenarları) ----
    # (0.06 ≈ eski metrikteki 0.08'in yeni dar aralığa oranlanmışı)
    eye4 = SyntheticEye(rng, curvature=0.06)
    m4 = GazeMapper(SCREEN_W, SCREEN_H); m4.forget()
    calibrate(m4, eye4, lambda x, y: 0.0, lambda x, y: 0.0)
    mean4, worst4 = eval_error(m4, eye4)
    results.append(("Doğrusal olmayan göz tepkisi", mean4, worst4, 45))

    # ---- Senaryo 5: kalibrasyonsuz varsayılan eşleme çalışıyor mu ----
    # (nötr metrik: rx≈0.5, ry≈0.0 — canlı probe ölçümüyle uyumlu)
    m5 = GazeMapper(SCREEN_W, SCREEN_H); m5.forget()
    x, y = m5.map(0.5, 0.0)
    assert abs(x - SCREEN_W / 2) < SCREEN_W * 0.1, "varsayılan merkez sapması"
    ok_default = abs(y - SCREEN_H * 0.5) < SCREEN_H * 0.25

    # ---- Rapor ----
    print(f"{'Senaryo':38s} {'ort.px':>8s} {'maks.px':>8s} {'eşik':>6s}  sonuç")
    failed = 0
    for name, mean, worst, thr in results:
        ok = mean <= thr
        failed += (0 if ok else 1)
        print(f"{name:38s} {mean:8.1f} {worst:8.1f} {thr:6d}  {'GEÇTİ' if ok else 'KALDI'}")
    print(f"{'Kalibrasyonsuz varsayılan eşleme':38s} {'—':>8s} {'—':>8s} {'—':>6s}  "
          f"{'GEÇTİ' if ok_default else 'KALDI'}")
    failed += (0 if ok_default else 1)

    # dwell yarıçapı 42 px; ort. hata bunun altındaysa bakışla tıklama güvenilir
    if failed:
        print(f"\n{failed} senaryo BAŞARISIZ")
        sys.exit(1)
    print("\nTÜM BAKIŞ SENARYOLARI GEÇTİ")


if __name__ == "__main__":
    main()
