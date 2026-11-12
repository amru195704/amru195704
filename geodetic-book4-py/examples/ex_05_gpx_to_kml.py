#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5 章 GPX → KML: どちらも WGS84 の緯度経度なので変換は要らない。高さの意味（GPX の ele は楕円体高か標高か）だけ補足ファイルで伝える。
使い方: python3 ex_05_gpx_to_kml.py track.gpx /tmp/track.kml"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from geofs import load_sidecar, save_sidecar
from geofs.formats import read_gpx, write_kml

src, dst = sys.argv[1], sys.argv[2]
fs = read_gpx(src, sidecar=load_sidecar(src), params={"height": {"datum": "ellipsoidal"}})  # 読む。ele の意味は受信機しだい
save_sidecar(write_kml(fs, dst), dst)                    # 書く。変換なし。面は無い。trk は線に、wpt は点に
print(fs.summary()); print("\n".join(fs.log))
