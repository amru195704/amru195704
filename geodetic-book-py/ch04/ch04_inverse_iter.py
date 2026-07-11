#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-1: 逆変換を固定点反復で解く（架空テストデータ内蔵版）。

第4章「逆変換を反復で解く」の教材。P3-2 と同じ順変換（グリッド補正）を使い、
逆を「順変換の反復収束」で解く。自己完結のため grid 部分は P3-2 と同じものを
同梱している（共通部の重複は許容というルール）。

★ 補正量は誇張した架空のテストデータです。実際の変位量ではありません。
"""
import math

SEC_TO_M = math.pi * 6371000 / 648000
LAT0, LON0 = 35.675, 139.7625
LAT_STEP, LON_STEP = 1 / 120, 1 / 80
CORNERS = {"SW": (12.0, -8.0), "NW": (12.4, -8.6),
           "SE": (12.2, -8.2), "NE": (12.8, -9.0)}


def bilerp(v00, v10, v01, v11, t, s):
    return (v00 * (1 - t) * (1 - s) + v10 * t * (1 - s)
            + v01 * (1 - t) * s + v11 * t * s)


def corr_deg(lat, lon):
    """順方向の補正量を度で返す（Δ緯度, Δ経度）。"""
    t = (lat - LAT0) / LAT_STEP
    s = (lon - LON0) / LON_STEP
    d_b = bilerp(CORNERS["SW"][0], CORNERS["NW"][0],
                 CORNERS["SE"][0], CORNERS["NE"][0], t, s)
    d_l = bilerp(CORNERS["SW"][1], CORNERS["NW"][1],
                 CORNERS["SE"][1], CORNERS["NE"][1], t, s)
    return d_b / 3600.0, d_l / 3600.0


def forward(lat, lon):
    """順変換: 補正量を足す。"""
    d_lat, d_lon = corr_deg(lat, lon)
    return lat + d_lat, lon + d_lon


def dist_m(lat_a, lon_a, lat_b, lon_b):
    """2点間の水平距離[m]。"""
    dy = (lat_a - lat_b) * SEC_TO_M * 3600
    dx = (lon_a - lon_b) * SEC_TO_M * 3600 * math.cos(math.radians(lat_a))
    return math.hypot(dy, dx)


def inverse(lat2, lon2, tol_m=1e-6, max_iter=10):
    """forward(lat,lon)==(lat2,lon2) となる (lat,lon) を反復で求める。"""
    lat, lon = lat2, lon2                    # 初期推定＝変換後の座標
    history = []
    for k in range(1, max_iter + 1):
        d_lat, d_lon = corr_deg(lat, lon)    # 現在推定での順補正量
        nlat, nlon = lat2 - d_lat, lon2 - d_lon
        move = dist_m(nlat, nlon, lat, lon)  # 今回の更新量[m]
        history.append((k, move))
        lat, lon = nlat, nlon
        if move < tol_m:                     # 更新が止まった＝収束
            break
    return lat, lon, history


if __name__ == "__main__":
    P = (35.6810, 139.7670)                  # 元の座標（東京駅付近）
    Pp = forward(*P)                         # 順変換した座標
    print("=== P4-1 逆変換（順変換の反復・架空データ）===")
    print(f"元 P    : {P[0]:.7f}, {P[1]:.7f}")
    print(f"順変換 P': {Pp[0]:.7f}, {Pp[1]:.7f}"
          f"  （移動 {dist_m(P[0], P[1], Pp[0], Pp[1]):.2f} m）")
    rec_lat, rec_lon, hist = inverse(Pp[0], Pp[1])
    print("反復ごとの更新量[m]:")
    for k, move in hist:
        print(f"  反復{k}: {move:.6g} m")
    print(f"復元 P  : {rec_lat:.7f}, {rec_lon:.7f}")
    err_mm = dist_m(rec_lat, rec_lon, P[0], P[1]) * 1000
    print(f"往復誤差（復元 − 元）: {err_mm:.5f} mm")
