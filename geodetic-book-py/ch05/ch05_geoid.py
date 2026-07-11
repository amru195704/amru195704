#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-1: ジオイド高のバイリニア補間（架空テストデータ内蔵版）。

ジオイド・モデルも格子（グリッド）で配られる。対象点を囲む4隅のジオイド高を
バイリニア補間して、その地点のジオイド高 N を求める。第3章の補正グリッドと
同じ補間の仕組み。

★ ジオイド高は誇張していないが架空の格子値です（日本付近のおよそ36〜42mを
   模した作り物）。実際の GSIGEO の値ではありません。
"""
LAT0, LON0 = 35.675, 139.7625
LAT_STEP, LON_STEP = 1 / 120, 1 / 80
# 4隅のジオイド高[m]（架空。日本付近を模した値）
GEOID = {"SW": 36.00, "NW": 36.40, "SE": 36.20, "NE": 36.90}


def bilerp(v00, v10, v01, v11, t, s):
    return (v00 * (1 - t) * (1 - s) + v10 * t * (1 - s)
            + v01 * (1 - t) * s + v11 * t * s)


def geoid_height(lat, lon):
    """対象点のジオイド高 N[m]。"""
    t = (lat - LAT0) / LAT_STEP
    s = (lon - LON0) / LON_STEP
    return bilerp(GEOID["SW"], GEOID["NW"],
                  GEOID["SE"], GEOID["NE"], t, s)


if __name__ == "__main__":
    lat, lon = 35.6810, 139.7670               # 東京駅付近
    n = geoid_height(lat, lon)
    print("=== P5-1 ジオイド高のバイリニア補間（架空データ）===")
    print(f"点 ({lat}, {lon})")
    print(f"内分比 t=(35.6810-35.675)*120=0.72,  s=0.36")
    print(f"ジオイド高 N = {n:.5f} m")
