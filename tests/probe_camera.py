"""
Canlı kamera sondası — gerçek webcam + LandmarkEngine hattını doğrular.

~4 saniye kare işler; kare hızı, yüz bulunma oranı, iris/poz/kırpma
üretimini raporlar. Yüz görünmese bile hattın çökmeden çalıştığını kanıtlar.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np


def main():
    import cv2
    from app.vision.landmark_engine import LandmarkEngine

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("KAMERA AÇILAMADI (başka uygulama kullanıyor olabilir)")
        sys.exit(2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    engine = LandmarkEngine()

    frames = faces = 0
    ratios, blinks = [], []
    t0 = time.monotonic()
    while time.monotonic() - t0 < 4.0:
        ok, frame = cap.read()
        if not ok:
            continue
        frames += 1
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        r = engine.process(rgb)
        if r.landmarks is not None:
            faces += 1
            ratios.append((*r.ratio, *r.pose))
            if r.blink_score is not None:
                blinks.append(r.blink_score)

    cap.release()
    engine.close()

    dt = time.monotonic() - t0
    print(f"kareler: {frames} ({frames / dt:.1f} fps)")
    print(f"yüz bulunan kare: {faces} ({(faces / max(frames, 1)) * 100:.0f}%)")
    if ratios:
        arr = np.array(ratios)
        print(f"iris oranı ort: rx={arr[:,0].mean():.3f} ry={arr[:,1].mean():.3f}")
        print(f"kafa pozu ort: yaw={arr[:,2].mean():+.3f} pitch={arr[:,3].mean():+.3f}")
        print(f"iris oranı std: rx={arr[:,0].std():.4f} ry={arr[:,1].std():.4f}")
        if blinks:
            print(f"kırpma skoru ort: {np.mean(blinks):.3f} "
                  f"(açık göz ~0.0-0.2 beklenir)")
        print("SONUÇ: CANLI İZLEME HATTI ÇALIŞIYOR (yüz bulundu)")
    else:
        print("SONUÇ: HAT ÇALIŞIYOR (görüş alanında yüz yoktu)")
    if frames < 20:
        print("UYARI: kare hızı düşük")
        sys.exit(1)


if __name__ == "__main__":
    main()
