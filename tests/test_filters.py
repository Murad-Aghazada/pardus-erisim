"""One Euro filtresi davranış testleri: durağanlıkta titreme bastırma, harekette düşük gecikme."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np


def main():
    from app.vision.filters import OneEuroFilter, GazeFilter2D

    rng = np.random.default_rng(1)
    dt = 1.0 / 30.0   # 30 fps

    # --- Durağan nokta + gürültü: çıkış titremesi girişten çok küçük olmalı ---
    f = OneEuroFilter(min_cutoff=0.6, beta=0.006)
    xs, ys = [], []
    t = 0.0
    for i in range(300):
        x = 800.0 + rng.normal(0, 15.0)   # 15 px ölçüm gürültüsü
        y = f.apply(x, t)
        t += dt
        if i > 60:
            xs.append(x); ys.append(y)
    in_std = float(np.std(xs))
    out_std = float(np.std(ys))
    print(f"Durağan: giriş titreme {in_std:.1f}px → çıkış {out_std:.1f}px "
          f"(x{in_std / max(out_std, 1e-6):.1f} bastırma)")
    assert out_std < in_std * 0.35, "titreme yeterince bastırılmadı"

    # --- Adım hareketi: yeni konuma makul sürede oturmalı ---
    f2 = OneEuroFilter(min_cutoff=0.6, beta=0.006)
    t = 0.0
    for _ in range(60):
        f2.apply(100.0, t); t += dt
    settle = None
    for i in range(90):
        y = f2.apply(900.0, t); t += dt
        if settle is None and abs(y - 900.0) < 40:
            settle = (i + 1) * dt
    print(f"Adım (100→900px): {settle if settle else '>3.0'} sn içinde oturdu")
    assert settle is not None and settle < 1.0, "hareket gecikmesi çok yüksek"

    # --- 2B sarmalayıcı ve yumuşatma seviyeleri ---
    g = GazeFilter2D()
    for level in (0, 50, 100):
        g.set_smoothing(level)
        assert g.fx.min_cutoff > 0
    g.reset()
    x, y = g.apply(10, 20)
    assert (x, y) == (10, 20), "ilk örnek geçmeli"

    print("\nTÜM FİLTRE TESTLERİ GEÇTİ")


if __name__ == "__main__":
    main()
