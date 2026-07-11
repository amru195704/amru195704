#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P6-1: 複数地震の発生順逐次適用（架空テストデータ内蔵版）。

第6章「複数の地殻変動を積み重ねる」の教材。2つの地震補正グリッドを用意し、
発生順（A→B）に適用する。順序を入れ替える（B→A）と結果が変わること
（＝補正は可換でない）を数値で見せる。自己完結のため格子部は同梱。

★ 補正量は誇張した架空のテストデータです。実際の変位量ではありません。
"""
import math

SEC_TO_M = math.pi * 6371000 / 648000
LAT0, LON0 = 35.675, 139.7625
LAT_STEP, LON_STEP = 1 / 120, 1 / 80

# 2つの架空地震（発生順 A → B）。4隅の変位量[秒]
QUAKE_A = {"SW": (5.0, -3.0), "NW": (5.4, -3.2),
           "SE": (5.1, -3.1), "NE": (5.9, -3.6)}   # 例: 2016年相当
QUAKE_B = {"SW": (-2.0, 4.0), "NW": (-2.6, 4.5),
           "SE": (-2.1, 4.1), "NE": (-3.0, 5.0)}    # 例: 2024年相当


def bilerp(v00, v10, v01, v11, t, s):
    return (v00 * (1 - t) * (1 - s) + v10 * t * (1 - s)
            + v01 * (1 - t) * s + v11 * t * s)


def apply_quake(lat, lon, q):
    """地震補正 q を現在位置に適用し、動いた座標を返す。"""
    t = (lat - LAT0) / LAT_STEP
    s = (lon - LON0) / LON_STEP
    d_b = bilerp(q["SW"][0], q["NW"][0], q["SE"][0], q["NE"][0], t, s)
    d_l = bilerp(q["SW"][1], q["NW"][1], q["SE"][1], q["NE"][1], t, s)
    return lat + d_b / 3600.0, lon + d_l / 3600.0


def dist_m(lat_a, lon_a, lat_b, lon_b):
    dy = (lat_a - lat_b) * SEC_TO_M * 3600
    dx = (lon_a - lon_b) * SEC_TO_M * 3600 * math.cos(math.radians(lat_a))
    return math.hypot(dy, dx)


if __name__ == "__main__":
    P = (35.6810, 139.7670)                    # 出発点（東京駅付近）
    print("=== P6-1 発生順の逐次適用（架空データ）===")

    # 発生順 A → B
    a1 = apply_quake(P[0], P[1], QUAKE_A)
    ab = apply_quake(a1[0], a1[1], QUAKE_B)
    print("[発生順 A→B]")
    print(f"  P         : {P[0]:.7f}, {P[1]:.7f}")
    print(f"  A適用後   : {a1[0]:.7f}, {a1[1]:.7f}"
          f"  （+{dist_m(P[0], P[1], a1[0], a1[1]):.2f} m）")
    print(f"  さらにB後 : {ab[0]:.7f}, {ab[1]:.7f}"
          f"  （+{dist_m(a1[0], a1[1], ab[0], ab[1]):.2f} m）")

    # 誤った順序 B → A
    b1 = apply_quake(P[0], P[1], QUAKE_B)
    ba = apply_quake(b1[0], b1[1], QUAKE_A)
    print("[誤った順 B→A]")
    print(f"  結果      : {ba[0]:.7f}, {ba[1]:.7f}")

    gap_mm = dist_m(ab[0], ab[1], ba[0], ba[1]) * 1000
    print(f"→ 順序の違いによるズレ: {gap_mm:.3f} mm")
