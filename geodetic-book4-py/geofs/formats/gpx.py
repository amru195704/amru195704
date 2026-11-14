# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""GPX（第4巻 5 章）⇄ GeoFeatureSet。

GPX 1.1 は WGS84 の lat/lon 属性固定、ele は規格上は楕円体高だが実機は標高を書くことも多い
（補足ファイルの height.datum で補う）。wpt → 点、rte・trk → 線（trkseg ごとに線）。
書き: 点 → wpt、線 → trk/trkseg、面 → 外周を trk にしてログ。
"""
from __future__ import annotations
import io
import xml.etree.ElementTree as ET
from typing import Optional
from ..model import Vertex, Geometry, Feature, FeatureSet
from ..sidecar import for_output
from ._common import build_metadata


def _local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def _text(el, name):
    for c in el:
        if _local(c.tag) == name:
            return (c.text or "").strip()
    return ""


def _pt(el, fs) -> Vertex:
    v = Vertex(lat=float(el.get("lat")), lon=float(el.get("lon")))
    e = _text(el, "ele")
    if e and fs.height.datum != "none":
        v.h = float(e) + (fs.source.offset_to_TP or 0.0)
    return v


def _attrs(el, keys):
    a = {}
    for c in el:
        t = _local(c.tag)
        if t in ("ele", "name", "trkseg", "rtept", "trkpt"):
            continue
        if len(c) == 0 and c.text and c.text.strip():
            a[t] = c.text.strip()
            if t not in keys:
                keys.append(t)
    return a


def read_gpx(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    held = {"crs": {"datum": "WGS84", "system": "geographic"},
            "axis": {"order": "lat,lon", "unit": "deg", "format": "dd"}, "encoding": "UTF-8"}
    sc = dict(sidecar or {})
    if "crs" in sc:
        held["crs"] = {"datum": sc["crs"].get("datum", "WGS84"), "system": "geographic"}
    fs = build_metadata("gpx", path, held, sc, params, required=())
    root = ET.parse(path).getroot()
    keys: list = []
    n = 0
    for el in root:
        t = _local(el.tag)
        if t == "wpt":
            n += 1
            fs.features.append(Feature(id=str(n), name=_text(el, "name"), geometry=Geometry("point", _pt(el, fs)),
                                       attributes=_attrs(el, keys)))
        elif t == "rte":
            n += 1
            vs = [_pt(p, fs) for p in el if _local(p.tag) == "rtept"]
            if len(vs) >= 2:
                fs.features.append(Feature(id=str(n), name=_text(el, "name"), geometry=Geometry("line", vs),
                                           attributes=_attrs(el, keys), layer="rte"))
            else:
                fs.skipped += 1
        elif t == "trk":
            n += 1
            name = _text(el, "name")
            segs = [[_pt(p, fs) for p in s if _local(p.tag) == "trkpt"] for s in el if _local(s.tag) == "trkseg"]
            segs = [s for s in segs if len(s) >= 2]
            if not segs:
                fs.skipped += 1
                continue
            g = Geometry("line", segs[0]) if len(segs) == 1 else Geometry("multiline", segs)
            fs.features.append(Feature(id=str(n), name=name, geometry=g, attributes=_attrs(el, keys), layer="trk"))
    fs.fields = keys
    return fs


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _ptxml(tag, v: Vertex, use_h, digits, name=None, attrs=None):
    s = f'<{tag} lat="{v.lat:.{digits}f}" lon="{v.lon:.{digits}f}">'
    if use_h and v.h is not None:
        s += f"<ele>{v.h:.3f}</ele>"
    if name:
        s += f"<name>{_esc(name)}</name>"
    for k, val in (attrs or {}).items():
        if val is not None and k in ("desc", "cmt", "sym", "type", "time"):
            s += f"<{k}>{_esc(val)}</{k}>"
    return s + f"</{tag}>"


def write_gpx(fs: FeatureSet, path, creator: str = "GeoFeatureSet", digits: int = 8) -> dict:
    if not fs.crs.is_geographic:
        raise ValueError("gpx: GPX は WGS84 の緯度経度固定。先に convert() で緯度経度にしてください")
    if fs.crs.datum != "WGS84":
        fs.log.append(f"gpx: 測地系 {fs.crs.datum} のまま書いた（規格は WGS84。補足ファイルで補う）")
    use_h = fs.height.datum != "none"
    out = io.StringIO()
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.write(f'<gpx version="1.1" creator="{_esc(creator)}" xmlns="http://www.topografix.com/GPX/1/1">\n')
    trks = []
    polys = 0
    for f in fs.features:
        g = f.geometry
        if g is None:
            continue
        other = {k: v for k, v in f.attributes.items()}
        if g.kind == "point":
            out.write(_ptxml("wpt", g.coords, use_h, digits, f.name, other) + "\n")
        elif g.kind == "multipoint":
            for i, v in enumerate(g.coords):
                out.write(_ptxml("wpt", v, use_h, digits, f"{f.name}#{i+1}", other) + "\n")
        elif g.kind == "line":
            trks.append((f.name, [g.coords], other))
        elif g.kind == "multiline":
            trks.append((f.name, list(g.coords), other))
        elif g.kind == "polygon":
            polys += 1
            trks.append((f.name, [list(g.coords.outer) + [g.coords.outer[0]]], other))
        elif g.kind == "multipolygon":
            polys += 1
            trks.append((f.name, [list(p.outer) + [p.outer[0]] for p in g.coords], other))
    for name, segs, other in trks:
        out.write(f"<trk><name>{_esc(name)}</name>")
        for k, val in other.items():
            if val is not None and k in ("desc", "cmt", "type"):
                out.write(f"<{k}>{_esc(val)}</{k}>")
        for seg in segs:
            out.write("<trkseg>" + "".join(_ptxml("trkpt", v, use_h, digits) for v in seg) + "</trkseg>")
        out.write("</trk>\n")
    if polys:
        fs.log.append(f"gpx: 面 {polys} 地物の外周を trk として書いた（穴は落ちる）")
    out.write("</gpx>\n")
    with open(path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(out.getvalue())
    return for_output(fs, "gpx")
