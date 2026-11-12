#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2 章 CSV: 平面直角座標の CSV（補足ファイルつき）を読み、緯度経度に直して GeoJSON に書く。
使い方: python3 ex_02_csv_to_geojson.py data/genba.csv /tmp/genba.geojson"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from geofs import CRS, load_sidecar, save_sidecar, convert
from geofs.formats import read_csv, write_geojson

src, dst = sys.argv[1], sys.argv[2]
fs = read_csv(src, sidecar=load_sidecar(src))            # 読む。測地系・系番号・高さの意味は補足ファイルから
fs2 = convert(fs, CRS("JGD2011", "geographic"))          # 変換する。第9系 X,Y → 緯度経度（高さはそのまま標高）
save_sidecar(write_geojson(fs2, dst), dst)               # 書く。GeoJSON に書けない「JGD2011・標高」は補足ファイルに残す
print(fs.summary(), "→", fs2.summary()); print("\n".join(fs2.log))
