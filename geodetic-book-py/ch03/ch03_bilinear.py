#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-2: メッシュコード算出＋バイリニア補間（架空テストデータ内蔵版）。

第3章「グリッド補正の実装」の教材。GeoCoreJP（Swift/C#）のソースではなく、
国土地理院の3次メッシュ仕様とバイリニア補間を Python で再表現したもの。
par ファイル不要で単体実行できる。

★ このスクリプトの補正量は「誇張した架空のテストデータ」です。
   計算のしくみを確かめるためのもので、実際の変位量ではありません。
   （実データの隅どうしの差は 0.001 秒ほど。ここでは補間の効きが見えるよう
    約1000倍に誇張している。絶対値は TKY2JGD 相当の約400mに合わせた）
"""
import math

SEC_TO_M = math.pi * 6371000 / 648000        # 1秒 ≈ 30.887 m

# 東京駅を含む3次メッシュ 53394611 の南西隅ノードと格子間隔
LAT0, LON0 = 35.675, 139.7625                # 南西隅ノードの緯度・経度
LAT_STEP = 1 / 120                           # 3次メッシュ 緯度間隔（約1km）
LON_STEP = 1 / 80                            # 3次メッシュ 経度間隔

# 囲む4隅ノードの補正量 [秒]（★架空・誇張値）。(dB=緯度補正, dL=経度補正)
#   SW=南西, NW=北西, SE=南東, NE=北東
CORNERS = {
    "SW": (12.0, -8.0),
    "NW": (12.4, -8.6),
    "SE": (12.2, -8.2),
    "NE": (12.8, -9.0),
}


def latlon_to_mesh(lat, lon):
    """緯度経度から3次メッシュコード（8桁）を組み立てる。"""
    p = int(lat * 1.5)                        # 1次（緯度）
    u = int(lon) - 100                        # 1次（経度）
    rl = lat * 1.5 - p
    rL = lon - int(lon)
    q = int(rl * 8)                           # 2次（緯度）
    v = int(rL * 8)                           # 2次（経度）
    r = int((rl * 8 - q) * 10)                # 3次（緯度）
    w = int((rL * 8 - v) * 10)                # 3次（経度）
    return f"{p:02d}{u:02d}{q}{v}{r}{w}"


def bilerp(v00, v10, v01, v11, t, s):
    """双線形補間。v00=南西, v10=北西, v01=南東, v11=北東。
    t=南北の内分比（0=南…1=北）, s=東西の内分比（0=西…1=東）。"""
    return (v00 * (1 - t) * (1 - s) + v10 * t * (1 - s)
            + v01 * (1 - t) * s + v11 * t * s)


def correction_sec(lat, lon):
    """点(lat,lon)の補正量[秒]を4隅から双線形補間して返す。"""
    t = (lat - LAT0) / LAT_STEP               # t: 南北（緯度方向）の内分比
    s = (lon - LON0) / LON_STEP               # s: 東西（経度方向）の内分比
    d_b = bilerp(CORNERS["SW"][0], CORNERS["NW"][0],
                 CORNERS["SE"][0], CORNERS["NE"][0], t, s)
    d_l = bilerp(CORNERS["SW"][1], CORNERS["NW"][1],
                 CORNERS["SE"][1], CORNERS["NE"][1], t, s)
    return t, s, d_b, d_l


def sec_to_m(d_b_sec, d_l_sec, lat):
    """補正量[秒]を水平距離[m]へ。経度側は cos(緯度) を掛ける。"""
    dy = d_b_sec * SEC_TO_M
    dx = d_l_sec * SEC_TO_M * math.cos(math.radians(lat))
    return dy, dx, math.hypot(dy, dx)


if __name__ == "__main__":
    lat, lon = 35.6810, 139.7670             # 東京駅（付近）
    print("=== P3-2 バイリニア補間（架空テストデータ）===")
    print(f"入力     : 緯度 {lat}  経度 {lon}")
    print(f"メッシュ : {latlon_to_mesh(lat, lon)}")
    t, s, d_b, d_l = correction_sec(lat, lon)
    print(f"内分比   : t(南北)={t:.4f}  s(東西)={s:.4f}")
    print(f"補正量   : Δ緯度 = {d_b:.5f} 秒   Δ経度 = {d_l:.5f} 秒")
    dy, dx, dist = sec_to_m(d_b, d_l, lat)
    print(f"距離換算 : 南北 {dy:.2f} m   東西 {dx:.2f} m   水平 {dist:.2f} m")
