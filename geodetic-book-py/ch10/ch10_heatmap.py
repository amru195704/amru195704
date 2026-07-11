#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P10-1: ヒートマップの縮約版（架空テストデータ内蔵版）。

第10章「補正量を面で可視化する」の教材の縮約版。メッシュ内を粗い格子で走査し、
各セルの補正量の大きさ（水平変位[m]）を数値の面として出す。実際のヒートマップは
これを matplotlib で色に落とすだけで、計算の核はこの「面の数値化」にある。

★ 補正量は誇張した架空のテストデータです。実際の変位量ではありません。
"""
import math

SEC_TO_M = math.pi * 6371000 / 648000
LAT0, LON0 = 35.675, 139.7625
LAT_STEP, LON_STEP = 1 / 120, 1 / 80
CORNERS = {"SW": (12.0, -8.0), "NW": (12.4, -8.6),
           "SE": (12.2, -8.2), "NE": (12.8, -9.0)}
GRID = 5                                        # 縮約: 5×5 セル


def bilerp(v00, v10, v01, v11, t, s):
    return (v00 * (1 - t) * (1 - s) + v10 * t * (1 - s)
            + v01 * (1 - t) * s + v11 * t * s)


def magnitude_m(t, s):
    """内分比 (t,s) での補正量の大きさ[m]。"""
    d_b = bilerp(CORNERS["SW"][0], CORNERS["NW"][0],
                 CORNERS["SE"][0], CORNERS["NE"][0], t, s)
    d_l = bilerp(CORNERS["SW"][1], CORNERS["NW"][1],
                 CORNERS["SE"][1], CORNERS["NE"][1], t, s)
    lat = LAT0 + t * LAT_STEP
    dy = d_b * SEC_TO_M
    dx = d_l * SEC_TO_M * math.cos(math.radians(lat))
    return math.hypot(dy, dx)


if __name__ == "__main__":
    print("=== P10-1 ヒートマップ縮約版（補正量の大きさ[m]）===")
    field = []
    for i in range(GRID):                        # 上が北になるよう反転出力
        row = []
        for j in range(GRID):
            t = i / (GRID - 1)
            s = j / (GRID - 1)
            row.append(magnitude_m(t, s))
        field.append(row)

    print("（行=南→北, 列=西→東, 単位 m）")
    for i in range(GRID - 1, -1, -1):
        print("  " + " ".join(f"{v:6.1f}" for v in field[i]))
    flat = [v for row in field for v in row]
    print(f"最小 {min(flat):.2f} m / 最大 {max(flat):.2f} m")
    print("→ この数値の面を色に写せばヒートマップ。核は面の数値化。")
