#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-2: 子午線弧長（赤道からの経線長）。GRS80。

赤道から緯度 φ までの経線に沿った距離を、級数展開で求める。実装で使う
級数と、数値積分（真値相当）を両方計算して一致を確かめ、赤道→極の値を
GRS80 の公表値 10001965.729 m と照合する。※架空値ではなく実定数。
"""
import math

A = 6378137.0
INV_F = 298.257222101
F = 1.0 / INV_F
E2 = F * (2.0 - F)


def meridian_arc_series(phi):
    """緯度 phi[rad] までの子午線弧長[m]（e^2 級数・e^8 まで）。"""
    e2 = E2
    a0 = 1 - e2/4 - 3*e2**2/64 - 5*e2**3/256 - 175*e2**4/16384
    a2 = 3*e2/8 + 3*e2**2/32 + 45*e2**3/1024 + 105*e2**4/4096
    a4 = 15*e2**2/256 + 45*e2**3/1024 + 525*e2**4/16384
    a6 = 35*e2**3/3072 + 175*e2**4/12288
    a8 = 315*e2**4/131072
    return A * (a0*phi - a2*math.sin(2*phi) + a4*math.sin(4*phi)
                - a6*math.sin(6*phi) + a8*math.sin(8*phi))


def meridian_arc_integral(phi, n=200000):
    """数値積分（合成シンプソン）で求めた子午線弧長[m]＝真値相当。"""
    if n % 2:
        n += 1
    h = phi / n
    total = 0.0
    for i in range(n + 1):
        x = i * h
        fx = A * (1 - E2) / (1 - E2 * math.sin(x)**2) ** 1.5
        w = 1 if i in (0, n) else (4 if i % 2 else 2)
        total += w * fx
    return total * h / 3.0


if __name__ == "__main__":
    print("=== P1-2 子午線弧長（GRS80）===")
    for deg in (15, 30, 45, 90):
        phi = math.radians(deg)
        s = meridian_arc_series(phi)
        q = meridian_arc_integral(phi)
        print(f"φ={deg:>2}° : 級数 {s:15.4f} m   積分 {q:15.4f} m"
              f"   差 {abs(s-q)*1000:.4f} mm")
    print("公表値（赤道→極, GRS80）: 10001965.7290 m")
