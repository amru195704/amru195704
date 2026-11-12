#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本の例の形: 読む → 変換する → 書く の 3 行。

SIMA（JGD2011 平面直角第9系・標高）を読み、JGD2011 の緯度経度に直して GeoJSON に書く。
GeoJSON が自分で持てない「実際の測地系」と「高さの基準」は補足ファイル .acrs に残す。
使い方: python3 ex_09_sima_to_geojson.py genba.sim genba.geojson
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from geofs import CRS, load_sidecar, save_sidecar, convert
from geofs.formats import read_sima, write_geojson

src, dst = sys.argv[1], sys.argv[2]
fs = read_sima(src, sidecar=load_sidecar(src))                      # 読む（座標は動かさない）
fs2 = convert(fs, CRS("JGD2011", "geographic"))                     # 変換する（独立の 1 段）
save_sidecar(write_geojson(fs2, dst), dst)                          # 書く（戻り値＝出力側の補足ファイル）
print(fs.summary(), "→", fs2.summary())
for line in fs2.log:
    print(" ", line)
