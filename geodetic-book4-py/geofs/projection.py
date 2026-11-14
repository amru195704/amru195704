# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""平面直角座標（19 系）・UTM と緯度経度の相互変換（第2巻 1 章の式。国土地理院の公式）。

原点は告示の分数で持つ（6 桁丸めにしない: 指示-20261102-02 の教訓）。
"""
from __future__ import annotations
import math

ELLIPSOIDS = {            # (a, 1/f)
    "GRS80":  (6378137.0, 298.257222101),
    "WGS84":  (6378137.0, 298.257223563),
    "Bessel": (6377397.155, 299.152813),
}
DATUM_ELLIPSOID = {"Tokyo": "Bessel", "JGD2000": "GRS80", "JGD2011": "GRS80",
                   "JGD2024": "GRS80", "WGS84": "WGS84"}

# 平面直角座標系の原点（緯度, 経度）。平成 14 年国土交通省告示第 9 号
_D = lambda d, m=0: d + m / 60.0
PLANE_ORIGINS = {
    1: (_D(33), _D(129, 30)), 2: (_D(33), _D(131)), 3: (_D(36), _D(132, 10)),
    4: (_D(33), _D(133, 30)), 5: (_D(36), _D(134, 20)), 6: (_D(36), _D(136)),
    7: (_D(36), _D(137, 10)), 8: (_D(36), _D(138, 30)), 9: (_D(36), _D(139, 50)),
    10: (_D(40), _D(140, 50)), 11: (_D(44), _D(140, 15)), 12: (_D(44), _D(142, 15)),
    13: (_D(44), _D(144, 15)), 14: (_D(26), _D(142)), 15: (_D(26), _D(127, 30)),
    16: (_D(26), _D(124)), 17: (_D(26), _D(131)), 18: (_D(20), _D(136)),
    19: (_D(26), _D(154)),
}
PLANE_M0 = 0.9999
UTM_M0 = 0.9996
UTM_FALSE_EASTING = 500000.0


class TM:
    """横メルカトル（ガウス・クリューゲル）。国土地理院「平面直角座標への換算」の式。"""

    def __init__(self, ellipsoid: str, phi0_deg: float, lam0_deg: float, m0: float,
                 false_easting: float = 0.0):
        a, inv_f = ELLIPSOIDS[ellipsoid]
        self.a, self.m0 = a, m0
        self.phi0, self.lam0 = math.radians(phi0_deg), math.radians(lam0_deg)
        self.fe = false_easting
        n = 1.0 / (2 * inv_f - 1)
        self.n = n
        n2, n3, n4, n5, n6 = n**2, n**3, n**4, n**5, n**6
        A = [1 + n2/4 + n4/64,
             -1.5 * (n - n3/8 - n5/64),
             15/16 * (n2 - n4/4),
             -35/48 * (n3 - 5/16 * n5),
             315/512 * n4,
             -693/1280 * n5]
        self.alpha = [None,
                      n/2 - 2/3*n2 + 5/16*n3 + 41/180*n4 - 127/288*n5,
                      13/48*n2 - 3/5*n3 + 557/1440*n4 + 281/630*n5,
                      61/240*n3 - 103/140*n4 + 15061/26880*n5,
                      49561/161280*n4 - 179/168*n5,
                      34729/80640*n5]
        self.beta = [None,
                     1/2*n - 2/3*n2 + 37/96*n3 - 1/360*n4 - 81/512*n5,
                     1/48*n2 + 1/15*n3 - 437/1440*n4 + 46/105*n5,
                     17/480*n3 - 37/840*n4 - 209/4480*n5,
                     4397/161280*n4 - 11/504*n5,
                     4583/161280*n5]
        self.delta = [None,
                      2*n - 2/3*n2 - 2*n3 + 116/45*n4 + 26/45*n5 - 2854/675*n6,
                      7/3*n2 - 8/5*n3 - 227/45*n4 + 2704/315*n5 + 2323/945*n6,
                      56/15*n3 - 136/35*n4 - 1262/105*n5 + 73814/2835*n6,
                      4279/630*n4 - 332/35*n5 - 399572/14175*n6,
                      4174/315*n5 - 144838/6237*n6,
                      601676/22275*n6]
        self.Abar = m0 * a / (1 + n) * A[0]
        self.Sbar = m0 * a / (1 + n) * (A[0] * self.phi0 +
                                         sum(A[j] * math.sin(2 * j * self.phi0) for j in range(1, 6)))

    def forward(self, lat_deg: float, lon_deg: float):
        """緯度経度（度）→ (x 北, y 東)[m]。"""
        phi, lam = math.radians(lat_deg), math.radians(lon_deg)
        n = self.n
        k = 2 * math.sqrt(n) / (1 + n)
        t = math.sinh(math.atanh(math.sin(phi)) - k * math.atanh(k * math.sin(phi)))
        tb = math.sqrt(1 + t * t)
        lc, ls = math.cos(lam - self.lam0), math.sin(lam - self.lam0)
        xi = math.atan2(t, lc)
        eta = math.atanh(ls / tb)
        x = self.Abar * (xi + sum(self.alpha[j] * math.sin(2*j*xi) * math.cosh(2*j*eta) for j in range(1, 6))) - self.Sbar
        y = self.Abar * (eta + sum(self.alpha[j] * math.cos(2*j*xi) * math.sinh(2*j*eta) for j in range(1, 6)))
        return x, y + self.fe

    def inverse(self, x: float, y: float):
        """(x 北, y 東)[m] → 緯度経度（度）。"""
        y = y - self.fe
        xi = (x + self.Sbar) / self.Abar
        eta = y / self.Abar
        xi2 = xi - sum(self.beta[j] * math.sin(2*j*xi) * math.cosh(2*j*eta) for j in range(1, 6))
        eta2 = eta - sum(self.beta[j] * math.cos(2*j*xi) * math.sinh(2*j*eta) for j in range(1, 6))
        chi = math.asin(math.sin(xi2) / math.cosh(eta2))
        phi = chi + sum(self.delta[j] * math.sin(2*j*chi) for j in range(1, 7))
        lam = self.lam0 + math.atan2(math.sinh(eta2), math.cos(xi2))
        return math.degrees(phi), math.degrees(lam)


def plane_rectangular(zone: int, datum: str) -> TM:
    phi0, lam0 = PLANE_ORIGINS[zone]
    return TM(DATUM_ELLIPSOID[datum], phi0, lam0, PLANE_M0)


def utm(zone: int, datum: str) -> TM:
    return TM(DATUM_ELLIPSOID[datum], 0.0, 6 * zone - 183, UTM_M0, UTM_FALSE_EASTING)


# ---- 測地系（楕円体）間の概略変換（第2巻 2 章）。Tokyo ⇄ 世界測地系の 3 パラメータ ----
TOKYO_TO_JGD = (-146.414, 507.337, 680.507)      # 平行移動 [m]（概略値。精密には TKY2JGD の格子）


def blh_to_xyz(lat, lon, h, ellipsoid):
    a, inv_f = ELLIPSOIDS[ellipsoid]
    f = 1 / inv_f
    e2 = f * (2 - f)
    phi, lam = math.radians(lat), math.radians(lon)
    N = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    return ((N + h) * math.cos(phi) * math.cos(lam),
            (N + h) * math.cos(phi) * math.sin(lam),
            (N * (1 - e2) + h) * math.sin(phi))


def xyz_to_blh(x, y, z, ellipsoid):
    a, inv_f = ELLIPSOIDS[ellipsoid]
    f = 1 / inv_f
    e2 = f * (2 - f)
    lam = math.atan2(y, x)
    p = math.hypot(x, y)
    phi = math.atan2(z, p * (1 - e2))
    for _ in range(20):
        N = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
        phi_new = math.atan2(z + e2 * N * math.sin(phi), p)
        if abs(phi_new - phi) < 1e-13:
            phi = phi_new
            break
        phi = phi_new
    N = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    h = p / math.cos(phi) - N
    return math.degrees(phi), math.degrees(lam), h


def tokyo_shift(lat, lon, h, to_world: bool):
    """Tokyo（Bessel）⇄ 世界測地系（GRS80）の概略 3 パラメータ変換。"""
    if to_world:
        x, y, z = blh_to_xyz(lat, lon, h, "Bessel")
        x, y, z = x + TOKYO_TO_JGD[0], y + TOKYO_TO_JGD[1], z + TOKYO_TO_JGD[2]
        return xyz_to_blh(x, y, z, "GRS80")
    x, y, z = blh_to_xyz(lat, lon, h, "GRS80")
    x, y, z = x - TOKYO_TO_JGD[0], y - TOKYO_TO_JGD[1], z - TOKYO_TO_JGD[2]
    return xyz_to_blh(x, y, z, "Bessel")
