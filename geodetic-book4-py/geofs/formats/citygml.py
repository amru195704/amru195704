# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""PLATEAU CityGML（第4巻 11 章）→ GeoFeatureSet。入力のみ・要素限定。v2 段階 C-3。

lod0 の面（bldg:lod0RoofEdge／lod0FootPrint の gml:posList）と点（gml:Point）だけを読む。
座標は EPSG:6697（JGD2011 緯度 経度 標高）固定（srsName があればそれを見る）。ストリーミング・件数上限。
"""
from __future__ import annotations
import zipfile, io, os
import xml.etree.ElementTree as ET
from typing import Optional, List
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet
from ._common import build_metadata

GML = "{http://www.opengis.net/gml}"


def _local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def _sources(path):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith(".gml") and not os.path.basename(n).startswith("._"):
                    yield n, io.BytesIO(z.read(n))
    else:
        yield os.path.basename(path), open(path, "rb")


def read_citygml(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    params = dict(params or {})
    limit = int(params.get("limit", 100000))
    held = {"crs": {"datum": "JGD2011", "system": "geographic", "epsg": 6697}, "axis": {"order": "lat,lon", "unit": "deg", "format": "dd"},
            "height": {"datum": "TP"}, "encoding": "UTF-8"}
    fs = build_metadata("citygml", path, held, sidecar, params, required=())
    fs.log.append("PLATEAU: EPSG:6697（JGD2011 緯度 経度 標高）として読む。lod0 の面と点だけ")
    n = 0
    counts = {"lod0": 0, "point": 0, "building": 0}
    for name, fp in _sources(path):
        stack = []
        bld_id = None
        for ev, el in ET.iterparse(fp, events=("start", "end")):
            t = _local(el.tag)
            if ev == "start":
                stack.append(t)
                if t == "Building":
                    bld_id = el.get(GML + "id") or el.get("{http://www.opengis.net/gml}id")
                continue
            stack.pop()
            if t in ("lod0RoofEdge", "lod0FootPrint"):
                counts["lod0"] += 1
                outer, holes = None, []
                for g in el.iter():
                    lt = _local(g.tag)
                    if lt in ("exterior", "interior"):
                        pl = None
                        for q in g.iter():
                            if _local(q.tag) == "posList":
                                pl = q.text
                        if pl:
                            nums = [float(x) for x in pl.split()]
                            dim = 3 if len(nums) % 3 == 0 and len(nums) % 2 != 0 or (len(nums) % 3 == 0 and len(nums) >= 12) else 2
                            vs = [Vertex(lat=nums[i], lon=nums[i + 1], h=nums[i + 2] if dim == 3 else None) for i in range(0, len(nums) - dim + 1, dim)]
                            if len(vs) >= 2 and (vs[0].lat, vs[0].lon) == (vs[-1].lat, vs[-1].lon):
                                vs = vs[:-1]
                            if lt == "exterior":
                                outer = vs
                            else:
                                holes.append(vs)
                if outer and len(outer) >= 3:
                    n += 1
                    fs.features.append(Feature(id=str(n), name=bld_id or f"B{n}", geometry=Geometry("polygon", Polygon(outer, [h for h in holes if len(h) >= 3])),
                                               attributes={"種別": t, "gml_id": bld_id or ""}, layer="Building"))
                    counts["building"] += 1
                el.clear()
            elif t == "Point" and "lod0" not in stack:
                for q in el.iter():
                    if _local(q.tag) == "pos" and q.text:
                        nums = [float(x) for x in q.text.split()]
                        if len(nums) >= 2:
                            n += 1
                            counts["point"] += 1
                            fs.features.append(Feature(id=str(n), name=el.get(GML + "id") or f"P{n}",
                                                       geometry=Geometry("point", Vertex(lat=nums[0], lon=nums[1], h=nums[2] if len(nums) >= 3 else None)),
                                                       attributes={"種別": "Point"}, layer="Point"))
                el.clear()
            if n >= limit:
                fs.log.append(f"件数上限 {limit} で止めた")
                break
        fp.close()
    fs.log.append(f"lod0 面 {counts['building']}・点 {counts['point']}")
    fs.fields = ["種別", "gml_id"]
    return fs
