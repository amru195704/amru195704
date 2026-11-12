#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4 章 GeoJSON: 緯度経度の GeoJSON を読み、平面直角第9系の CSV に書く（面は頂点を点として出る）。
使い方: python3 ex_04_geojson_to_csv.py data/kukaku.geojson /tmp/kukaku.csv"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from geofs import CRS, load_sidecar, save_sidecar, convert
from geofs.formats import read_geojson, write_csv

src, dst = sys.argv[1], sys.argv[2]
fs = read_geojson(src, sidecar=load_sidecar(src))        # 読む。仕様上は WGS84 固定だが、実際の測地系は補足ファイルで宣言
fs2 = convert(fs, CRS("JGD2011", "plane_rectangular", zone=9))   # 変換する。緯度経度 → 第9系 X（北）,Y（東）
save_sidecar(write_csv(fs2, dst), dst)                   # 書く。列順・系番号・高さの意味を補足ファイルに
print(fs.summary(), "→", fs2.summary()); print("\n".join(fs2.log))
