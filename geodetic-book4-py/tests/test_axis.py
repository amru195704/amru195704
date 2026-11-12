#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""補足ファイル `axis` の区分 A／B／C（付録 7-1・8-4）の動作確認。
B: SIMA・GeoJSON は補足ファイルの axis が既定より優先（警告をログに）／C: GPX・KML は無視（警告をログに）。"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from geofs.formats import read_sima, read_geojson, read_gpx

SIMA = "G00,01,test,,\nZ00,,,,\nA00,,,,\nA01,1,P1,-7891.5678,-35345.1234,12.345,\nA99,,,,\n"
GJ = '{"type":"Feature","properties":{"name":"P1"},"geometry":{"type":"Point","coordinates":[35.6854,139.7514]}}'
GPX = '<?xml version="1.0"?><gpx version="1.1" creator="t"><wpt lat="35.6854" lon="139.7514"><name>P1</name></wpt></gpx>'

def main():
    d = tempfile.mkdtemp()
    ok = True
    # B: SIMA が X＝東・Y＝北 で書かれている → east,north を宣言すると入れ替えて読む
    p = os.path.join(d, "t.sim"); open(p, "w", encoding="cp932").write(SIMA)
    sc = {"crs": {"datum": "JGD2011", "system": "plane_rectangular", "zone": 9}, "height": {"datum": "TP"}}
    v0 = read_sima(p, sidecar=sc).features[0].geometry.coords
    fs = read_sima(p, sidecar=dict(sc, axis={"order": "east,north", "unit": "m"}))
    v1 = fs.features[0].geometry.coords
    t1 = (v0.x, v0.y) == (-7891.5678, -35345.1234) and (v1.x, v1.y) == (-35345.1234, -7891.5678) and any("優先" in l for l in fs.log)
    print("ok " if t1 else "NG ", "[B sima] 既定", (v0.x, v0.y), "→ east,north", (v1.x, v1.y)); ok &= t1
    # B: GeoJSON が [緯度, 経度] → lat,lon を宣言すると入れ替えて読む
    p = os.path.join(d, "t.geojson"); open(p, "w", encoding="utf-8").write(GJ)
    v0 = read_geojson(p).features[0].geometry.coords
    fs = read_geojson(p, sidecar={"axis": {"order": "lat,lon", "unit": "deg", "format": "dd"}})
    v1 = fs.features[0].geometry.coords
    t2 = (v0.lon, v0.lat) == (35.6854, 139.7514) and (v1.lat, v1.lon) == (35.6854, 139.7514) and any("優先" in l for l in fs.log)
    print("ok " if t2 else "NG ", "[B geojson] 既定 lon,lat", (v0.lon, v0.lat), "→ lat,lon", (v1.lat, v1.lon)); ok &= t2
    # C: GPX は名前付きなので axis を書いても無視（警告）
    p = os.path.join(d, "t.gpx"); open(p, "w", encoding="utf-8").write(GPX)
    fs = read_gpx(p, sidecar={"axis": {"order": "lon,lat", "unit": "deg"}})
    v = fs.features[0].geometry.coords
    t3 = (v.lat, v.lon) == (35.6854, 139.7514) and any("無視" in l for l in fs.log)
    print("ok " if t3 else "NG ", "[C gpx] axis を無視", (v.lat, v.lon), [l for l in fs.log if "無視" in l][:1]); ok &= t3
    print("全部 OK" if ok else "NG あり")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
