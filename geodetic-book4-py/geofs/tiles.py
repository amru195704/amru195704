# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""Web メルカトル（EPSG:3857）とタイル番号の計算（第4巻 12 章）。v2 段階 C-4。計算のみ。"""
from __future__ import annotations
import math
R = 6378137.0
MAX = math.pi * R


def latlon_to_mercator(lat: float, lon: float):
    """WGS84 緯度経度 → EPSG:3857 (x 東, y 北)[m]"""
    x = math.radians(lon) * R
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R
    return x, y


def mercator_to_latlon(x: float, y: float):
    lon = math.degrees(x / R)
    lat = math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)
    return lat, lon


def latlon_to_tile(lat: float, lon: float, z: int):
    """緯度経度 → (x, y) タイル番号（XYZ・左上原点）"""
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def tile_bounds(x: int, y: int, z: int):
    """タイル番号 → (south, west, north, east) 緯度経度"""
    n = 2 ** z
    west = x / n * 360 - 180
    east = (x + 1) / n * 360 - 180
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return south, west, north, east


def tms_y(y: int, z: int) -> int:
    """XYZ の y ⇄ TMS の y（上下反転）"""
    return 2 ** z - 1 - y


def pixel_size_m(lat: float, z: int, tile_px: int = 256) -> float:
    return 2 * MAX / (2 ** z * tile_px) * math.cos(math.radians(lat))
