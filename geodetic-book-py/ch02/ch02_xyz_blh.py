#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-1: 緯度経度楕円体高(BLH) ⇔ 地心直交座標(XYZ)。GRS80。

BLH→XYZ は閉形式。XYZ→BLH は緯度と曲率半径が循環するため反復で解く
（国土地理院の非反復の新算式は第4章コラム参照。ここでは仕組みが見える反復版）。
※楕円体は GRS80 実定数。座標は例示点だが計算は厳密で、極・赤道で自己照合できる。
"""
import math

A = 6378137.0
INV_F = 298.257222101
F = 1.0 / INV_F
E2 = F * (2.0 - F)


def blh_to_xyz(lat, lon, h):
    """緯度経度[度]・楕円体高[m] → XYZ[m]。"""
    p, l = math.radians(lat), math.radians(lon)
    n = A / math.sqrt(1 - E2 * math.sin(p) ** 2)
    x = (n + h) * math.cos(p) * math.cos(l)
    y = (n + h) * math.cos(p) * math.sin(l)
    z = (n * (1 - E2) + h) * math.sin(p)
    return x, y, z


def xyz_to_blh(x, y, z, tol=1e-12, max_iter=20):
    """XYZ[m] → 緯度経度[度]・楕円体高[m]（反復）。"""
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - E2))         # 初期緯度
    for _ in range(max_iter):
        n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        new = math.atan2(z, p * (1 - E2 * n / (n + h)))
        if abs(new - lat) < tol:
            lat = new
            break
        lat = new
    n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), h


if __name__ == "__main__":
    print("=== P2-1 BLH ⇔ XYZ（GRS80）===")
    # 自己照合: 赤道(0,0,0)→X=a、北極(90,0,0)→Z=b
    print("赤道 (0°,0°,0m)   → XYZ =", tuple(round(v, 4)
          for v in blh_to_xyz(0, 0, 0)), " 期待 X=a=6378137")
    print("北極 (90°,0°,0m)  → XYZ =", tuple(round(v, 4)
          for v in blh_to_xyz(90, 0, 0)), " 期待 Z=b=6356752.314")

    p0 = (35.6810, 139.7670, 50.0)            # 例示点（東京駅付近）
    xyz = blh_to_xyz(*p0)
    back = xyz_to_blh(*xyz)
    print(f"\n例示点 BLH: {p0}")
    print(f"  → XYZ : {xyz[0]:.4f}, {xyz[1]:.4f}, {xyz[2]:.4f}")
    print(f"  → BLH : {back[0]:.9f}, {back[1]:.9f}, {back[2]:.6f}")
    dlat = abs(back[0] - p0[0]) * 111320 * 1000
    dh = abs(back[2] - p0[2]) * 1000
    print(f"  往復誤差: 緯度 {dlat:.4f} mm, 高さ {dh:.4f} mm")
