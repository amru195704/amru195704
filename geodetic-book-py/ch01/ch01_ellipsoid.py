#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-1: 楕円体の基本量（GRS80）。

定義値（長半径 a と逆扁平率 1/f）から、短半径・離心率などの派生量を求める。
これらは架空値ではなく GRS80 の実定数なので、公表値と厳密に照合できる。

GRS80 定義値:
  a   = 6378137.0 m
  1/f = 298.257222101
"""
import math

A = 6378137.0
INV_F = 298.257222101


def grs80():
    f = 1.0 / INV_F
    b = A * (1.0 - f)                 # 短半径
    e2 = f * (2.0 - f)               # 第一離心率の2乗 e^2
    ep2 = e2 / (1.0 - e2)            # 第二離心率の2乗 e'^2
    n = f / (2.0 - f)               # 第3扁平率 n
    return {"f": f, "b": b, "e2": e2, "e": math.sqrt(e2),
            "ep2": ep2, "n": n}


if __name__ == "__main__":
    v = grs80()
    print("=== P1-1 GRS80 楕円体の基本量 ===")
    print(f"長半径 a       : {A:.4f} m")
    print(f"扁平率 f       : {v['f']:.12f}  (1/f = {1/v['f']:.9f})")
    print(f"短半径 b       : {v['b']:.6f} m")
    print(f"第一離心率^2 e2: {v['e2']:.14f}")
    print(f"第一離心率   e : {v['e']:.12f}")
    print(f"第二離心率^2 e'2: {v['ep2']:.14f}")
    print(f"第3扁平率 n    : {v['n']:.14f}")
