#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-3: 緯度1度・経度1度あたりの地上距離。GRS80。

緯度が上がるほど「経度1度の距離」が縮み、「緯度1度の距離」はわずかに伸びる。
子午線曲率半径 M と卯酉線曲率半径 N から算出し、公表される距離表と照合する。
※架空値ではなく実定数。
"""
import math

A = 6378137.0
INV_F = 298.257222101
F = 1.0 / INV_F
E2 = F * (2.0 - F)
DEG = math.pi / 180.0


def radii(phi):
    """子午線曲率半径 M と卯酉線曲率半径 N[m]。phi は rad。"""
    w = 1 - E2 * math.sin(phi) ** 2
    m = A * (1 - E2) / w ** 1.5
    n = A / math.sqrt(w)
    return m, n


def degree_lengths(phi_deg):
    """緯度1度・経度1度あたりの距離[m]。"""
    phi = math.radians(phi_deg)
    m, n = radii(phi)
    lat_len = m * DEG                    # 緯度1度＝子午線1度分
    lon_len = n * math.cos(phi) * DEG    # 経度1度＝卯酉線×cosφ
    return lat_len, lon_len


if __name__ == "__main__":
    print("=== P1-3 緯度1度・経度1度あたりの距離（GRS80）===")
    print(f"{'緯度':>4} {'緯度1度[m]':>14} {'経度1度[m]':>14}")
    for deg in (0, 15, 35, 45, 60, 90):
        lat_len, lon_len = degree_lengths(deg)
        print(f"{deg:>3}° {lat_len:14.3f} {lon_len:14.3f}")
