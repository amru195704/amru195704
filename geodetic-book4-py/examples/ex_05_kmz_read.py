#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5 章 KMZ: zip の中の doc.kml を読んで、何が入っているかを数える（読むだけ）。
使い方: python3 ex_05_kmz_read.py route.kmz"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from geofs.formats import read_kmz

fs = read_kmz(sys.argv[1])                               # 読む。Folder は layer に、description は属性に
print(fs.summary())
for f in fs.features[:5]:
    print(" ", f.layer, f.id, f.name, f.geometry.kind)
