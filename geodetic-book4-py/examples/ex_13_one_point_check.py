#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""13 章 1 点で確かめる: 自分の変換（geofs）を、国土地理院「平面直角座標への換算」の値 1 点と比べる。
使い方: python3 ex_13_one_point_check.py   （地理院の値は tests/data/gsi_plane_rectangular.csv と同じ換算ページの 1 点）"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from geofs import projection as P

zone, lat, lon = 9, 35.689472, 139.691722                # 東京都（新宿区）。地理院の換算ページに入れた緯度経度
gsi_x, gsi_y = -34442.2981, -12816.7904                  # 地理院が返した X, Y（GRS80・第9系）
x, y = P.plane_rectangular(zone, "JGD2011").forward(lat, lon)   # 自分の変換
print(f"自分: X={x:.4f} Y={y:.4f}  地理院: X={gsi_x} Y={gsi_y}  差: {abs(x-gsi_x)*1000:.2f} mm, {abs(y-gsi_y)*1000:.2f} mm")
