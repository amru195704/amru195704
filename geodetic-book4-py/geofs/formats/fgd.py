# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""基盤地図情報（基本項目）GML（第4巻 7 章）→ GeoFeatureSet。入力のみ。

- 国土地理院の FG-GML-*.zip（複数 XML）か、中の XML 1 つ。ストリーミング（iterparse）で読み、件数上限で止める。
- 座標は srsName="fguuid:jgd2011.bl"／"fguuid:jgd2024.bl" の 緯度 経度（JGD2011／JGD2024 地理）。
- 要素種別: params["types"]（既定 ["GCP", "ElevPt"]。"*" で全部）。点＝<pos><gml:Point><gml:pos>、
  線＝<loc><gml:Curve>…<gml:posList>、面＝<area><gml:Surface>…<gml:exterior>/<gml:interior>。
- 属性: 子要素のテキスト（fid・type・gcpClass・name・alti …）。alti は高さ（標高）。
"""
from __future__ import annotations
import io
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, List
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet
from ._common import build_metadata

DEFAULT_TYPES = ["GCP", "ElevPt"]
LINE_TYPES = {"AdmBdry", "RdEdg", "RdCompt", "RdMgtBdry", "RdSgmtA", "RailCL", "WL", "Cntr", "BldL", "CommBdry", "RvrMgtBdry", "SBAPt"}
AREA_TYPES = {"BldA", "WA", "AdmArea", "SBArea", "WStrA", "RdArea", "RdASL"}


def _local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def _nums(text):
    return [float(t) for t in (text or "").split()]


def _ring(curve_el) -> List[Vertex]:
    pts: List[Vertex] = []
    for el in curve_el.iter():
        if _local(el.tag) == "posList":
            n = _nums(el.text)
            seg = [Vertex(lat=n[i], lon=n[i + 1]) for i in range(0, len(n) - 1, 2)]
            if pts and seg and (pts[-1].lat, pts[-1].lon) == (seg[0].lat, seg[0].lon):
                seg = seg[1:]
            pts += seg
        elif _local(el.tag) == "pos" and _local(curve_el.tag) in ("Point",):
            n = _nums(el.text)
            if len(n) >= 2:
                pts.append(Vertex(lat=n[0], lon=n[1]))
    if len(pts) >= 2 and (pts[0].lat, pts[0].lon) == (pts[-1].lat, pts[-1].lon):
        pts = pts[:-1]
    return pts


def _feature_from(el, fid: str, fs: FeatureSet, use_h: bool) -> Optional[Feature]:
    t = _local(el.tag)
    attrs = {}
    geom = None
    for c in el:
        name = _local(c.tag)
        if name in ("pos", "loc", "area"):
            if name == "pos":
                p = None
                for g in c.iter():
                    if _local(g.tag) == "pos":
                        n = _nums(g.text)
                        if len(n) >= 2:
                            p = Vertex(lat=n[0], lon=n[1])
                if p:
                    geom = Geometry("point", p)
            elif name == "loc":
                vs = _ring(c)
                if len(vs) >= 2:
                    geom = Geometry("line", vs)
            else:
                outer, holes = None, []
                for g in c.iter():
                    ln = _local(g.tag)
                    if ln == "exterior":
                        outer = _ring(g)
                    elif ln == "interior":
                        holes.append(_ring(g))
                if outer and len(outer) >= 3:
                    geom = Geometry("polygon", Polygon(outer, [h for h in holes if len(h) >= 3]))
        elif len(c) == 0 and c.text and c.text.strip():
            attrs[name] = c.text.strip()
        elif name in ("lfSpanFr", "lfSpanTo", "devDate"):
            for g in c.iter():
                if _local(g.tag) == "timePosition" and g.text:
                    attrs[name] = g.text.strip()
    if geom is None:
        return None
    if use_h and "alti" in attrs:
        try:
            h = float(attrs["alti"])
            for v in geom.vertices():
                v.h = h
        except ValueError:
            pass
    attrs["種別"] = t
    name = attrs.get("name") or attrs.get("gcpCode") or f"{t}_{fid}"
    return Feature(id=fid, name=name, geometry=geom, attributes=attrs, layer=t)


def _sources(path: str):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith(".xml") and not os.path.basename(n).startswith("._"):
                    yield n, io.BytesIO(z.read(n))
    else:
        yield os.path.basename(path), open(path, "rb")


def read_fgd(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    params = dict(params or {})
    types = params.get("types") or DEFAULT_TYPES
    limit = int(params.get("limit", 100000))
    # 測地系は srsName から（最初に見つかったもの）。無ければ JGD2011
    datum = None
    for name, fp in _sources(path):
        head = fp.read(200000)
        fp.close()
        if b"<Dataset" not in head:
            continue
        i = head.find(b'srsName="fguuid:')
        if i >= 0:
            s = head[i + 16:i + 40].decode("ascii", "ignore").lower()
            datum = "JGD2024" if s.startswith("jgd2024") else "JGD2011" if s.startswith("jgd2011") else "JGD2000" if s.startswith("jgd2000") else None
            break
    held = {"crs": {"datum": datum or "JGD2011", "system": "geographic", "epsg": 6668 if (datum or "JGD2011") == "JGD2011" else None},
            "axis": {"order": "lat,lon", "unit": "deg", "format": "dd"}, "encoding": "UTF-8"}
    fs = build_metadata("fgd", path, held, sidecar, params, required=())
    fs.log.append(f"srsName: {datum or '不明（JGD2011 とみなす）'} 緯度 経度")
    if fs.height.datum == "none" and "height" not in (sidecar or {}) and "height" not in params:
        fs.height.datum = "TP"           # 基盤地図情報の alti は標高
        fs.log.append("高さ（alti）は標高（TP）として読む")
    use_h = fs.height.datum != "none"
    counts = {}
    stopped = False
    for name, fp in _sources(path):
        if stopped:
            break
        for ev, el in ET.iterparse(fp, events=("end",)):
            t = _local(el.tag)
            if t in LINE_TYPES | AREA_TYPES | {"GCP", "ElevPt"} or (types == "*" and el.get("{http://www.opengis.net/gml/3.2}id")):
                if el.get("{http://www.opengis.net/gml/3.2}id") is None:
                    continue
                counts[t] = counts.get(t, 0) + 1
                if types == "*" or t in types:
                    f = _feature_from(el, el.get("{http://www.opengis.net/gml/3.2}id"), fs, use_h)
                    if f is None:
                        fs.skipped += 1
                    else:
                        fs.features.append(f)
                        if len(fs.features) >= limit:
                            fs.log.append(f"件数上限 {limit} に達したので止めた")
                            stopped = True
                            break
                el.clear()
        fp.close()
    fs.log.append("要素: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + f"（読んだ種別: {types}）")
    keys = []
    for f in fs.features:
        for k in f.attributes:
            if k not in keys:
                keys.append(k)
    fs.fields = keys
    return fs
