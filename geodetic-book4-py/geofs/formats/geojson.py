# -*- coding: utf-8 -*-
"""GeoJSON（第4巻 4 章）⇄ GeoFeatureSet。

RFC 7946 では座標は WGS84 の lon,lat（10 進度）固定。「実際の測地系」（JGD2011 など）は
補足ファイルの crs.datum で補える（system は geographic のまま）。高さ（3 つ目の値）の基準は持たない
ので補足ファイルの height.datum で補う。GeometryCollection は要素ごとの地物にばらす。
"""
from __future__ import annotations
import json
from typing import Optional
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet
from ..sidecar import for_output
from ._common import build_metadata, name_from

NAME_KEYS = ("name", "名称", "点名", "title", "label", "Name", "NAME")


def _v(c, fs):
    if (fs.source.axis_order or "lon,lat").replace(" ", "") == "lat,lon":   # 区分 B: 補足ファイルが lat,lon なら入れ替えて読む
        v = Vertex(lat=float(c[0]), lon=float(c[1]))
    else:
        v = Vertex(lat=float(c[1]), lon=float(c[0]))
    if len(c) > 2 and c[2] is not None and fs.height.datum != "none":
        v.h = float(c[2]) + (fs.source.offset_to_TP or 0.0)
    return v


def _ring(coords, fs):
    vs = [_v(c, fs) for c in coords]
    if len(vs) >= 2 and vs[0].lat == vs[-1].lat and vs[0].lon == vs[-1].lon:
        vs = vs[:-1]
    return vs


def _geoms(g: dict, fs) -> list:
    """GeoJSON geometry → [Geometry]（GeometryCollection は複数）。"""
    t = g.get("type")
    c = g.get("coordinates")
    if t == "Point":
        return [Geometry("point", _v(c, fs))]
    if t == "MultiPoint":
        return [Geometry("multipoint", [_v(p, fs) for p in c])]
    if t == "LineString":
        return [Geometry("line", [_v(p, fs) for p in c])]
    if t == "MultiLineString":
        return [Geometry("multiline", [[_v(p, fs) for p in l] for l in c])]
    if t == "Polygon":
        return [Geometry("polygon", Polygon(_ring(c[0], fs), [_ring(r, fs) for r in c[1:]]))]
    if t == "MultiPolygon":
        return [Geometry("multipolygon", [Polygon(_ring(p[0], fs), [_ring(r, fs) for r in p[1:]]) for p in c])]
    if t == "GeometryCollection":
        out = []
        for gg in g.get("geometries", []):
            out += _geoms(gg, fs)
        return out
    raise ValueError(f"geojson: 未対応の geometry type {t}")


def read_geojson(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    held = {"crs": {"datum": "WGS84", "system": "geographic"},
            "axis": {"order": "lon,lat", "unit": "deg", "format": "dd"}, "encoding": "UTF-8"}
    sc = dict(sidecar or {})
    if "crs" in sc:                      # 「実際の測地系」は補足ファイルが勝つ（system は geographic のまま）
        held["crs"] = {"datum": sc["crs"].get("datum", "WGS84"), "system": "geographic"}
    fs = build_metadata("geojson", path, held, sc, params, required=())
    with open(path, "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    if d.get("crs"):
        fs.log.append(f"GeoJSON の crs メンバ（旧仕様）: {json.dumps(d['crs'], ensure_ascii=False)}")
    feats = d.get("features", []) if d.get("type") == "FeatureCollection" else \
        [d] if d.get("type") == "Feature" else [{"type": "Feature", "geometry": d, "properties": {}}]
    keys = []
    for n, fd in enumerate(feats, start=1):
        props = dict(fd.get("properties") or {})
        for k in props:
            if k not in keys:
                keys.append(k)
        g = fd.get("geometry")
        fid = str(fd.get("id", n))
        name = name_from(props, *NAME_KEYS)
        if g is None:
            fs.features.append(Feature(id=fid, name=name, geometry=None, attributes=props))
            continue
        try:
            gs = _geoms(g, fs)
        except (ValueError, TypeError, IndexError) as e:
            fs.skipped += 1
            fs.log.append(f"feature {fid}: {e} → 読み飛ばし")
            continue
        for i, gg in enumerate(gs):
            fs.features.append(Feature(id=fid if len(gs) == 1 else f"{fid}-{i+1}", name=name,
                                       geometry=gg, attributes=dict(props)))
    fs.fields = keys
    return fs


def _c(v: Vertex, use_h, digits):
    c = [round(v.lon, digits), round(v.lat, digits)]
    if use_h and v.h is not None:
        c.append(round(v.h, 3))
    return c


def _ringc(vs, use_h, digits):
    out = [_c(v, use_h, digits) for v in vs]
    out.append(out[0])          # GeoJSON は閉じる
    return out


def _poly(p: Polygon, use_h, digits):
    return [_ringc(p.outer, use_h, digits)] + [_ringc(r, use_h, digits) for r in p.holes]


def to_geojson_geometry(g: Geometry, use_h=True, digits=9) -> dict:
    k, c = g.kind, g.coords
    if k == "point":
        return {"type": "Point", "coordinates": _c(c, use_h, digits)}
    if k == "multipoint":
        return {"type": "MultiPoint", "coordinates": [_c(v, use_h, digits) for v in c]}
    if k == "line":
        return {"type": "LineString", "coordinates": [_c(v, use_h, digits) for v in c]}
    if k == "multiline":
        return {"type": "MultiLineString", "coordinates": [[_c(v, use_h, digits) for v in l] for l in c]}
    if k == "polygon":
        return {"type": "Polygon", "coordinates": _poly(c, use_h, digits)}
    if k == "multipolygon":
        return {"type": "MultiPolygon", "coordinates": [_poly(p, use_h, digits) for p in c]}
    raise ValueError(k)


def write_geojson(fs: FeatureSet, path, digits: int = 9, indent: Optional[int] = 1) -> dict:
    """緯度経度の集合を GeoJSON に書く。投影座標なら ValueError（先に convert()）。"""
    if not fs.crs.is_geographic:
        raise ValueError("geojson: GeoJSON は WGS84 の緯度経度固定。先に convert() で緯度経度にしてください")
    if fs.crs.datum != "WGS84":
        fs.log.append(f"geojson: 測地系 {fs.crs.datum} のまま書いた（規格は WGS84。補足ファイルで補う）")
    use_h = fs.height.datum != "none"
    feats = []
    for f in fs.features:
        props = {}
        if f.name:
            props["name"] = f.name
        if f.layer is not None:
            props["layer"] = f.layer
        props.update(f.attributes)
        feats.append({"type": "Feature", "id": f.id,
                      "geometry": to_geojson_geometry(f.geometry, use_h, digits) if f.geometry else None,
                      "properties": props})
    with open(path, "w", encoding="utf-8", newline="\n") as fp:
        json.dump({"type": "FeatureCollection", "features": feats}, fp, ensure_ascii=False, indent=indent)
        fp.write("\n")
    return for_output(fs, "geojson")
