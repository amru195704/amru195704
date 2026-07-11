#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P8-1: 検証の型（残差統計）（架空テストデータ内蔵版）。

「正しく変換できたか」を1点ではなく、多数の点の残差統計（最大・平均・RMS）で
語る——第8章の検証論をミニチュアで再現する。ここでは順変換→逆変換の往復残差を
メッシュ内の格子点で集計し、許容値との合否を出す。自己完結のため格子部は同梱。

★ 補正量は誇張した架空のテストデータです。実際の変位量ではありません。
"""
import math

SEC_TO_M = math.pi * 6371000 / 648000
LAT0, LON0 = 35.675, 139.7625
LAT_STEP, LON_STEP = 1 / 120, 1 / 80
CORNERS = {"SW": (12.0, -8.0), "NW": (12.4, -8.6),
           "SE": (12.2, -8.2), "NE": (12.8, -9.0)}
TOL_MM = 1.0                                   # 許容残差[mm]


def bilerp(v00, v10, v01, v11, t, s):
    return (v00 * (1 - t) * (1 - s) + v10 * t * (1 - s)
            + v01 * (1 - t) * s + v11 * t * s)


def corr_deg(lat, lon):
    t = (lat - LAT0) / LAT_STEP
    s = (lon - LON0) / LON_STEP
    d_b = bilerp(CORNERS["SW"][0], CORNERS["NW"][0],
                 CORNERS["SE"][0], CORNERS["NE"][0], t, s)
    d_l = bilerp(CORNERS["SW"][1], CORNERS["NW"][1],
                 CORNERS["SE"][1], CORNERS["NE"][1], t, s)
    return d_b / 3600.0, d_l / 3600.0


def forward(lat, lon):
    d_lat, d_lon = corr_deg(lat, lon)
    return lat + d_lat, lon + d_lon


def inverse(lat2, lon2, tol_m=1e-9, max_iter=12):
    lat, lon = lat2, lon2
    for _ in range(max_iter):
        d_lat, d_lon = corr_deg(lat, lon)
        nlat, nlon = lat2 - d_lat, lon2 - d_lon
        if abs(nlat - lat) < tol_m and abs(nlon - lon) < tol_m:
            return nlat, nlon
        lat, lon = nlat, nlon
    return lat, lon


def dist_m(la, lo, lb, lob):
    dy = (la - lb) * SEC_TO_M * 3600
    dx = (lo - lob) * SEC_TO_M * 3600 * math.cos(math.radians(la))
    return math.hypot(dy, dx)


if __name__ == "__main__":
    print("=== P8-1 検証の型（往復残差の統計・架空データ）===")
    residuals = []
    for i in range(1, 10):                      # メッシュ内 9×9 の格子点
        for j in range(1, 10):
            lat = LAT0 + (i / 10) * LAT_STEP
            lon = LON0 + (j / 10) * LON_STEP
            fw = forward(lat, lon)
            bk = inverse(*fw)
            residuals.append(dist_m(bk[0], bk[1], lat, lon) * 1000)
    n = len(residuals)
    mx = max(residuals)
    mean = sum(residuals) / n
    rms = math.sqrt(sum(r * r for r in residuals) / n)
    print(f"検証点数 : {n}")
    print(f"最大残差 : {mx:.6f} mm")
    print(f"平均残差 : {mean:.6f} mm")
    print(f"RMS 残差 : {rms:.6f} mm")
    print(f"許容 {TOL_MM} mm 以内 : "
          f"{'PASS' if mx < TOL_MM else 'FAIL'}（最大 {mx:.2e} mm）")
