#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-2: 標高と楕円体高の変換 H = h − N（架空テストデータ内蔵版）。

GNSSが返すのは楕円体高 h。地図や水準測量の高さは標高 H。両者はジオイド高 N
だけずれる: H = h − N。ジオイド高は P5-1 と同じ格子補間で求める（自己完結の
ため同梱）。

★ ジオイド格子は架空値（日本付近のおよそ36mを模した作り物）です。
"""
LAT0, LON0 = 35.675, 139.7625
LAT_STEP, LON_STEP = 1 / 120, 1 / 80
GEOID = {"SW": 36.00, "NW": 36.40, "SE": 36.20, "NE": 36.90}
NODATA = 999.0                        # 陸域外の無効値（実データは 999.0/−9999.0）


def bilerp(v00, v10, v01, v11, t, s):
    return (v00 * (1 - t) * (1 - s) + v10 * t * (1 - s)
            + v01 * (1 - t) * s + v11 * t * s)


def geoid_height(lat, lon):
    corners = [GEOID["SW"], GEOID["NW"], GEOID["SE"], GEOID["NE"]]
    if any(v == NODATA or v <= -9999.0 for v in corners):  # 無効値混在
        return None                   # 陸域外＝内挿しない
    t = (lat - LAT0) / LAT_STEP
    s = (lon - LON0) / LON_STEP
    return bilerp(corners[0], corners[1], corners[2], corners[3], t, s)


def ellipsoidal_to_orthometric(lat, lon, h):
    """楕円体高 h[m] → 標高 H[m]。H = h − N。"""
    n = geoid_height(lat, lon)
    if n is None:                     # ジオイドが無い（陸域外）
        return None, None
    return h - n, n


def orthometric_to_ellipsoidal(lat, lon, big_h):
    """標高 H[m] → 楕円体高 h[m]。h = H + N。"""
    n = geoid_height(lat, lon)
    if n is None:
        return None, None
    return big_h + n, n


if __name__ == "__main__":
    lat, lon = 35.6810, 139.7670               # 東京駅付近
    h = 50.000                                 # GNSS が返す楕円体高[m]
    big_h, n = ellipsoidal_to_orthometric(lat, lon, h)
    print("=== P5-2 標高と楕円体高 H = h − N（架空データ）===")
    print(f"楕円体高 h = {h:.3f} m")
    print(f"ジオイド高 N = {n:.5f} m（P5-1と同じ格子補間）")
    print(f"標高 H = h − N = {big_h:.5f} m")
    # 逆（標高→楕円体高）で往復
    h_back, _ = orthometric_to_ellipsoidal(lat, lon, big_h)
    print(f"標高→楕円体高で復元 h = {h_back:.5f} m"
          f"  往復誤差 {abs(h_back - h) * 1000:.4f} mm")
