#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-4: ガウス・クリューゲル投影（平面直角座標）。GRS80。

緯度経度 ⇔ 平面直角座標(X=北, Y=東) の順・逆変換をクリューゲル級数で行う。
系9（原点 φ0=36°N, λ0=139°50'E, 縮尺 m0=0.9999）で、
原点→(0,0)・往復一致・「+50000,+50000 → 緯度経度」を確かめる。
※楕円体は GRS80 実定数。座標は架空の指定点だが計算は厳密。
"""
import math

A = 6378137.0
INV_F = 298.257222101
F = 1.0 / INV_F
E2 = F * (2.0 - F)
EP2 = E2 / (1.0 - E2)
M0 = 0.9999                                   # 縮尺係数
PHI0 = math.radians(36.0)                     # 系9 原点緯度
LAMBDA0 = math.radians(139.0 + 50.0 / 60.0)   # 系9 原点経度 139°50'


def meridian_arc(phi):
    """赤道→phi[rad] の子午線弧長[m]（e^2 級数・e^8 まで）。"""
    e2 = E2
    a0 = 1 - e2/4 - 3*e2**2/64 - 5*e2**3/256 - 175*e2**4/16384
    a2 = 3*e2/8 + 3*e2**2/32 + 45*e2**3/1024 + 105*e2**4/4096
    a4 = 15*e2**2/256 + 45*e2**3/1024 + 525*e2**4/16384
    a6 = 35*e2**3/3072 + 175*e2**4/12288
    a8 = 315*e2**4/131072
    return A * (a0*phi - a2*math.sin(2*phi) + a4*math.sin(4*phi)
                - a6*math.sin(6*phi) + a8*math.sin(8*phi))


def forward(phi, lam):
    """緯度経度[rad] → 平面直角 (X 北, Y 東)[m]。"""
    dl = lam - LAMBDA0
    t = math.tan(phi)
    eta2 = EP2 * math.cos(phi) ** 2
    n = A / math.sqrt(1 - E2 * math.sin(phi) ** 2)
    c = math.cos(phi)
    x = (meridian_arc(phi) - meridian_arc(PHI0)
         + n*t*((dl*c)**2/2
                + (dl*c)**4/24 * (5 - t**2 + 9*eta2 + 4*eta2**2)
                + (dl*c)**6/720 * (61 - 58*t**2 + t**4
                                   + 270*eta2 - 330*t**2*eta2)))
    y = n*(dl*c + (dl*c)**3/6 * (1 - t**2 + eta2)
           + (dl*c)**5/120 * (5 - 18*t**2 + t**4
                              + 14*eta2 - 58*t**2*eta2))
    return M0 * x, M0 * y


def _footpoint(x):
    """X/M0 に対応する足緯度 phi1[rad] を反復で求める。"""
    target = meridian_arc(PHI0) + x / M0
    phi = PHI0
    for _ in range(12):
        m = A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
        phi += (target - meridian_arc(phi)) / m
    return phi


def inverse(x, y):
    """平面直角 (X 北, Y 東)[m] → 緯度経度[rad]。"""
    phi1 = _footpoint(x)
    t1 = math.tan(phi1)
    eta1 = EP2 * math.cos(phi1) ** 2
    n1 = A / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    rho1 = A * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    d = y / (M0 * n1)
    phi = phi1 - (n1*t1/rho1) * (d**2/2
        - (5 + 3*t1**2 + eta1 - 9*t1**2*eta1) * d**4/24
        + (61 + 90*t1**2 + 45*t1**4) * d**6/720)
    lam = LAMBDA0 + (d - (1 + 2*t1**2 + eta1) * d**3/6
        + (5 + 28*t1**2 + 24*t1**4 + 6*eta1 + 8*t1**2*eta1)
          * d**5/120) / math.cos(phi1)
    return phi, lam


if __name__ == "__main__":
    print("=== P1-4 ガウス・クリューゲル投影 系9（GRS80）===")
    ox, oy = forward(PHI0, LAMBDA0)
    print(f"原点(36°,139°50') → X={ox:.4f} Y={oy:.4f} m（期待 0,0）")

    phi, lam = inverse(50000.0, 50000.0)
    print(f"+50000,+50000 → 緯度 {math.degrees(phi):.9f}°"
          f"  経度 {math.degrees(lam):.9f}°")
    bx, by = forward(phi, lam)                 # 逆→順で戻す
    print(f"  逆→順で復元 : X={bx:.6f} Y={by:.6f} m")
    err = math.hypot(bx - 50000.0, by - 50000.0) * 1000
    print(f"  往復誤差    : {err:.4f} mm")
