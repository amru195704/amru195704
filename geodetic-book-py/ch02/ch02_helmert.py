#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-2: ヘルマート7パラメータ変換（ブルサ・ウォルフ）。

XYZ に平行移動3・回転3・スケール1の剛体変換を掛ける。地図全体を一様に
ずらすだけ＝場所ごとの局所ひずみは表せない。グリッド補正との違いを見る。

例に用いる TOKYO→世界測地系のおおよその3パラメータ（平行移動のみ、
回転・スケール=0）は広く引用される概略値。厳密な地域補正はグリッド（第3章）
が担う、という第2章コラムの主張を数値で確かめる。
"""
import math

# TOKYO → 世界測地系 の概略変換（平行移動[m]・回転[秒]・スケール[ppm]）
PARAMS = {"tx": -146.414, "ty": 507.337, "tz": 680.507,
          "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0}
SEC = math.pi / 180.0 / 3600.0             # 秒 → ラジアン


def helmert(x, y, z, p):
    """7パラメータ変換を XYZ に適用。"""
    rx, ry, rz = p["rx"] * SEC, p["ry"] * SEC, p["rz"] * SEC
    k = 1.0 + p["s"] * 1e-6
    xo = p["tx"] + k * (x - rz * y + ry * z)
    yo = p["ty"] + k * (rz * x + y - rx * z)
    zo = p["tz"] + k * (-ry * x + rx * y + z)
    return xo, yo, zo


def inverse_params(p):
    """逆変換のパラメータ（符号反転・微小量近似）。"""
    return {k: -v for k, v in p.items()}


if __name__ == "__main__":
    print("=== P2-2 ヘルマート変換（TOKYO→世界測地系 概略）===")
    # 距離の離れた2点に同じ変換を掛け、ずれベクトルを比べる
    pts = {"東京付近 XYZ": (-3957200.0, 3310200.0, 3737700.0),
           "九州付近 XYZ": (-3543000.0, 3970000.0, 3440000.0)}
    for name, (x, y, z) in pts.items():
        xo, yo, zo = helmert(x, y, z, PARAMS)
        dx, dy, dz = xo - x, yo - y, zo - z
        d = math.sqrt(dx**2 + dy**2 + dz**2)
        print(f"[{name}] ずれ (dx,dy,dz)="
              f"({dx:.3f},{dy:.3f},{dz:.3f})  大きさ {d:.3f} m")

    # 往復（順→逆）で戻ることの確認
    x, y, z = pts["東京付近 XYZ"]
    xo, yo, zo = helmert(x, y, z, PARAMS)
    xb, yb, zb = helmert(xo, yo, zo, inverse_params(PARAMS))
    err = math.sqrt((xb-x)**2 + (yb-y)**2 + (zb-z)**2) * 1000
    print(f"往復誤差（順→逆）: {err:.4f} mm")
    print("→ 平行移動のみだと全点が同じベクトルでずれる（剛体）。"
          "実際の地域差はグリッド補正が担う＝第2章コラムの通り。")
