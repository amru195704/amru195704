# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""KML／KMZ（第4巻 5 章）⇄ GeoFeatureSet。

KML は WGS84 の lon,lat[,alt] 固定（高さの基準は altitudeMode で「地表から」などが変わる。
測量の標高・楕円体高どちらかは補足ファイルの height.datum で補う）。
Folder は layer に、description と ExtendedData は属性に入れる。MultiGeometry は要素ごとの地物にばらす。
"""
from __future__ import annotations
import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, List
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet
from ..sidecar import for_output
from ._common import build_metadata, name_from

KML_NS = "http://www.opengis.net/kml/2.2"


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _child(el, name):
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _children(el, name):
    return [c for c in el if _local(c.tag) == name]


def _text(el, name, default=""):
    c = _child(el, name)
    return (c.text or "").strip() if c is not None else default


def _coords(text: str, fs) -> List[Vertex]:
    out = []
    for tok in text.split():
        p = tok.split(",")
        if len(p) < 2:
            continue
        v = Vertex(lat=float(p[1]), lon=float(p[0]))
        if len(p) > 2 and p[2] != "" and fs.height.datum != "none":
            v.h = float(p[2]) + (fs.source.offset_to_TP or 0.0)
        out.append(v)
    return out


def _ring(el, fs):
    vs = _coords(_text(el, "coordinates"), fs)
    if len(vs) >= 2 and vs[0].lat == vs[-1].lat and vs[0].lon == vs[-1].lon:
        vs = vs[:-1]
    return vs


def _geoms(el, fs) -> List[Geometry]:
    out = []
    for g in el:
        t = _local(g.tag)
        if t == "Point":
            vs = _coords(_text(g, "coordinates"), fs)
            if vs:
                out.append(Geometry("point", vs[0]))
        elif t == "LineString":
            vs = _coords(_text(g, "coordinates"), fs)
            if len(vs) >= 2:
                out.append(Geometry("line", vs))
        elif t == "LinearRing":
            vs = _ring(g, fs)
            if len(vs) >= 3:
                out.append(Geometry("polygon", Polygon(vs)))
        elif t == "Polygon":
            ob = _child(g, "outerBoundaryIs")
            outer = _ring(_child(ob, "LinearRing"), fs) if ob is not None and _child(ob, "LinearRing") is not None else []
            holes = []
            for ib in _children(g, "innerBoundaryIs"):
                lr = _child(ib, "LinearRing")
                if lr is not None:
                    holes.append(_ring(lr, fs))
            if len(outer) >= 3:
                out.append(Geometry("polygon", Polygon(outer, holes)))
        elif t == "MultiGeometry":
            out += _geoms(g, fs)
    return out


def _walk(el, folder: Optional[str], fs: FeatureSet, counter: list, keys: list):
    for c in el:
        t = _local(c.tag)
        if t in ("Document", "Folder"):
            name = _text(c, "name")
            _walk(c, name if t == "Folder" else folder, fs, counter, keys)
        elif t == "Placemark":
            counter[0] += 1
            attrs = {}
            desc = _text(c, "description")
            if desc:
                attrs["description"] = desc
            ed = _child(c, "ExtendedData")
            if ed is not None:
                for d in _children(ed, "Data"):
                    attrs[d.get("name", "")] = _text(d, "value")
                for sd in _children(ed, "SchemaData"):
                    for s in _children(sd, "SimpleData"):
                        attrs[s.get("name", "")] = (s.text or "").strip()
            for k in attrs:
                if k not in keys:
                    keys.append(k)
            name = _text(c, "name") or name_from(attrs, "name", "点名")
            fid = c.get("id") or str(counter[0])
            gs = _geoms(c, fs)
            if not gs:
                fs.features.append(Feature(id=fid, name=name, geometry=None, attributes=attrs, layer=folder))
                continue
            for i, g in enumerate(gs):
                fs.features.append(Feature(id=fid if len(gs) == 1 else f"{fid}-{i+1}", name=name,
                                           geometry=g, attributes=dict(attrs), layer=folder))


def _read_kml_text(fmt, path, text: str, sidecar, params) -> FeatureSet:
    held = {"crs": {"datum": "WGS84", "system": "geographic"},
            "axis": {"order": "lon,lat", "unit": "deg", "format": "dd"}, "encoding": "UTF-8"}
    sc = dict(sidecar or {})
    if "crs" in sc:
        held["crs"] = {"datum": sc["crs"].get("datum", "WGS84"), "system": "geographic"}
    fs = build_metadata(fmt, path, held, sc, params, required=())
    root = ET.fromstring(text)
    keys: list = []
    _walk(root if _local(root.tag) != "kml" else root, None, fs, [0], keys)
    fs.fields = keys
    return fs


def read_kml(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    with open(path, "rb") as f:
        return _read_kml_text("kml", path, f.read().decode("utf-8-sig"), sidecar, params)


def read_kmz(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".kml")]
        if not names:
            raise ValueError("kmz: .kml が入っていない")
        main = "doc.kml" if "doc.kml" in names else names[0]
        text = z.read(main).decode("utf-8-sig")
    fs = _read_kml_text("kmz", path, text, sidecar, params)
    fs.log.append(f"kmz: {main} を読んだ")
    return fs


# ---- 書き ----
def _cstr(vs, use_h, digits):
    return " ".join(f"{v.lon:.{digits}f},{v.lat:.{digits}f}" + (f",{v.h:.3f}" if use_h and v.h is not None else "")
                    for v in vs)


def _kml_geometry(g: Geometry, use_h, digits) -> str:
    k, c = g.kind, g.coords

    def ring(vs):
        return _cstr(list(vs) + [vs[0]], use_h, digits)

    def poly(p: Polygon):
        s = f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{ring(p.outer)}</coordinates></LinearRing></outerBoundaryIs>"
        for r in p.holes:
            s += f"<innerBoundaryIs><LinearRing><coordinates>{ring(r)}</coordinates></LinearRing></innerBoundaryIs>"
        return s + "</Polygon>"

    if k == "point":
        return f"<Point><coordinates>{_cstr([c], use_h, digits)}</coordinates></Point>"
    if k == "multipoint":
        return "<MultiGeometry>" + "".join(f"<Point><coordinates>{_cstr([v], use_h, digits)}</coordinates></Point>" for v in c) + "</MultiGeometry>"
    if k == "line":
        return f"<LineString><coordinates>{_cstr(c, use_h, digits)}</coordinates></LineString>"
    if k == "multiline":
        return "<MultiGeometry>" + "".join(f"<LineString><coordinates>{_cstr(l, use_h, digits)}</coordinates></LineString>" for l in c) + "</MultiGeometry>"
    if k == "polygon":
        return poly(c)
    if k == "multipolygon":
        return "<MultiGeometry>" + "".join(poly(p) for p in c) + "</MultiGeometry>"
    raise ValueError(k)


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def kml_text(fs: FeatureSet, name: str = "GeoFeatureSet", digits: int = 9) -> str:
    if not fs.crs.is_geographic:
        raise ValueError("kml: KML は WGS84 の緯度経度固定。先に convert() で緯度経度にしてください")
    if fs.crs.datum != "WGS84":
        fs.log.append(f"kml: 測地系 {fs.crs.datum} のまま書いた（規格は WGS84。補足ファイルで補う）")
    use_h = fs.height.datum != "none"
    out = io.StringIO()
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.write(f'<kml xmlns="{KML_NS}">\n<Document>\n<name>{_esc(name)}</name>\n')
    # layer ごとに Folder
    layers = []
    for f in fs.features:
        if f.layer not in layers:
            layers.append(f.layer)
    for layer in layers:
        if layer is not None:
            out.write(f"<Folder><name>{_esc(layer)}</name>\n")
        for f in fs.features:
            if f.layer != layer:
                continue
            out.write(f'<Placemark id="{_esc(f.id)}"><name>{_esc(f.name)}</name>')
            if "description" in f.attributes and f.attributes["description"]:
                out.write(f"<description>{_esc(f.attributes['description'])}</description>")
            rest = {k: v for k, v in f.attributes.items() if k != "description" and v is not None}
            if rest:
                out.write("<ExtendedData>" + "".join(f'<Data name="{_esc(k)}"><value>{_esc(v)}</value></Data>' for k, v in rest.items()) + "</ExtendedData>")
            if f.geometry is not None:
                out.write(_kml_geometry(f.geometry, use_h, digits))
            out.write("</Placemark>\n")
        if layer is not None:
            out.write("</Folder>\n")
    out.write("</Document>\n</kml>\n")
    return out.getvalue()


def write_kml(fs: FeatureSet, path, name: str = "GeoFeatureSet", digits: int = 9) -> dict:
    with open(path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(kml_text(fs, name, digits))
    return for_output(fs, "kml")


def write_kmz(fs: FeatureSet, path, name: str = "GeoFeatureSet", digits: int = 9) -> dict:
    text = kml_text(fs, name, digits)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", text.encode("utf-8"))
    return for_output(fs, "kmz")
