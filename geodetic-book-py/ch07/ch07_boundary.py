#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P7-1: 境界（4隅欠損）メッシュの扱い（架空テストデータ内蔵版）。

第7章「境界の問題と品質指標」の教材。4隅の一部が欠けたメッシュで、
補正量の求め方が方式によって変わることを見せる。

  - 真値方式  : 4隅すべてが分かっている理想（比較の基準）
  - 0埋め方式 : 欠けた隅を 0 とみなして補間を続行（GeoCoreJP 系）
  - 地理院方式: 1隅でも欠けたら補正しない（4隅必須）

欠けた隅（ここでは北東 NE）に近い点ほど、0埋めの結果が真値からずれる。
これが CCQ（座標変換クオリティー）が問題にする「隅の充足度」の正体。
※ CCQ の指標値そのものの算出は本書の別節に譲り、ここでは方式差だけを見る。

★ 補正量は誇張した架空のテストデータです。実際の変位量ではありません。
"""
import math

SEC_TO_M = math.pi * 6371000 / 648000
LAT0, LON0 = 35.675, 139.7625
LAT_STEP, LON_STEP = 1 / 120, 1 / 80

# 4隅の「真の」補正量[秒]（P3-2と同じ）。NE を欠損させて実験する
CORNERS_TRUE = {"SW": (12.0, -8.0), "NW": (12.4, -8.6),
                "SE": (12.2, -8.2), "NE": (12.8, -9.0)}
MISSING = "NE"                              # 欠けている隅


def bilerp(v00, v10, v01, v11, t, s):
    return (v00 * (1 - t) * (1 - s) + v10 * t * (1 - s)
            + v01 * (1 - t) * s + v11 * t * s)


def ts(lat, lon):
    return (lat - LAT0) / LAT_STEP, (lon - LON0) / LON_STEP


def corr_true(lat, lon):
    """4隅すべて既知として補間（比較の基準）。"""
    t, s = ts(lat, lon)
    c = CORNERS_TRUE
    d_b = bilerp(c["SW"][0], c["NW"][0], c["SE"][0], c["NE"][0], t, s)
    d_l = bilerp(c["SW"][1], c["NW"][1], c["SE"][1], c["NE"][1], t, s)
    return d_b, d_l


def corr_zerofill(lat, lon):
    """欠けた隅を 0 とみなして補間（GeoCoreJP 系）。"""
    t, s = ts(lat, lon)
    c = {k: ((0.0, 0.0) if k == MISSING else v)
         for k, v in CORNERS_TRUE.items()}
    d_b = bilerp(c["SW"][0], c["NW"][0], c["SE"][0], c["NE"][0], t, s)
    d_l = bilerp(c["SW"][1], c["NW"][1], c["SE"][1], c["NE"][1], t, s)
    return d_b, d_l


def corr_gsi(lat, lon):
    """1隅でも欠けたら補正しない（地理院方式）。"""
    return 0.0, 0.0


def dist_sec_m(db1, dl1, db2, dl2, lat):
    """2つの補正量[秒]の差を水平距離[m]で返す。"""
    dy = (db1 - db2) * SEC_TO_M
    dx = (dl1 - dl2) * SEC_TO_M * math.cos(math.radians(lat))
    return math.hypot(dy, dx)


if __name__ == "__main__":
    print("=== P7-1 境界（NE欠損）での方式差・架空データ ===")
    # 欠損隅(NE)からの近さを変えた2点で比較
    points = {
        "SW寄り(t=0.2,s=0.2)": (LAT0 + 0.2 * LAT_STEP, LON0 + 0.2 * LON_STEP),
        "NE寄り(t=0.8,s=0.8)": (LAT0 + 0.8 * LAT_STEP, LON0 + 0.8 * LON_STEP),
    }
    for name, (lat, lon) in points.items():
        tb, tl = corr_true(lat, lon)
        zb, zl = corr_zerofill(lat, lon)
        gap = dist_sec_m(zb, zl, tb, tl, lat)   # 0埋め − 4隅そろいの値
        print(f"[{name}]")
        print(f"  4隅そろい Δ緯度={tb:.4f}秒 Δ経度={tl:.4f}秒（参考）")
        print(f"  0埋め    Δ緯度={zb:.4f}秒 Δ経度={zl:.4f}秒")
        print(f"  地理院   補正なし（4隅必須＝ここは穴になる）")
        print(f"  → 0埋めが仮の0に引かれる量: {gap:.2f} m")
