# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""中間フォーマットの JSON 直列化 `.gfs.json`（仕様書 §2）。

GeoJSON に似せているのは幾何の入れ子だけで、GeoJSON ではない。
頂点は {"x","y","h"}／{"lat","lon","h"} のオブジェクト（軸順を推定させない）。
文字コードは UTF-8（BOM なし）固定。None の項目は省略する。
"""
from __future__ import annotations
import json
from dataclasses import asdict
from .model import (Vertex, Polygon, Geometry, Feature, CRS, Height, Epoch,
                    Source, FeatureSet)

FORMAT_NAME = "GeoFeatureSet"
VERSION = 1
EXT = ".gfs.json"


def _v(v: Vertex) -> dict:
    d = {}
    for k in ("lat", "lon", "x", "y", "h", "ref"):
        val = getattr(v, k)
        if val is not None:
            d[k] = val
    return d


def _vd(d: dict) -> Vertex:
    return Vertex(d.get("lat"), d.get("lon"), d.get("x"), d.get("y"), d.get("h"), d.get("ref"))


def _poly(p: Polygon) -> dict:
    return {"outer": [_v(v) for v in p.outer], "holes": [[_v(v) for v in r] for r in p.holes]}


def _polyd(d: dict) -> Polygon:
    return Polygon([_vd(v) for v in d["outer"]], [[_vd(v) for v in r] for r in d.get("holes", [])])


def geometry_to_dict(g: Geometry) -> dict:
    k, c = g.kind, g.coords
    if k == "point":
        coords = _v(c)
    elif k in ("multipoint", "line"):
        coords = [_v(v) for v in c]
    elif k == "multiline":
        coords = [[_v(v) for v in line] for line in c]
    elif k == "polygon":
        coords = _poly(c)
    elif k == "multipolygon":
        coords = [_poly(p) for p in c]
    else:
        raise ValueError(k)
    return {"kind": k, "coords": coords}


def geometry_from_dict(d: dict) -> Geometry:
    k, c = d["kind"], d["coords"]
    if k == "point":
        return Geometry(k, _vd(c))
    if k in ("multipoint", "line"):
        return Geometry(k, [_vd(v) for v in c])
    if k == "multiline":
        return Geometry(k, [[_vd(v) for v in line] for line in c])
    if k == "polygon":
        return Geometry(k, _polyd(c))
    if k == "multipolygon":
        return Geometry(k, [_polyd(p) for p in c])
    raise ValueError(k)


def _strip_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def to_dict(fs: FeatureSet) -> dict:
    out = {
        "format": FORMAT_NAME,
        "version": VERSION,
        "crs": _strip_none(asdict(fs.crs)),
        "height": _strip_none(asdict(fs.height)),
        "epoch": _strip_none(asdict(fs.epoch)),
        "source": _strip_none(asdict(fs.source)),
        "fields": list(fs.fields),
        "features": [],
        "known_points": list(fs.known_points),
        "skipped": fs.skipped,
        "log": list(fs.log),
    }
    if fs.note is not None:
        out["note"] = fs.note
    for f in fs.features:
        fd = {"id": f.id, "name": f.name}
        if f.layer is not None:
            fd["layer"] = f.layer
        fd["geometry"] = geometry_to_dict(f.geometry) if f.geometry is not None else None
        fd["attributes"] = dict(f.attributes)
        out["features"].append(fd)
    return out


def from_dict(d: dict) -> FeatureSet:
    if d.get("format") != FORMAT_NAME:
        raise ValueError(f"format が {FORMAT_NAME} ではない: {d.get('format')}")
    c = d["crs"]
    fs = FeatureSet(
        crs=CRS(c["datum"], c["system"], c.get("zone"), c.get("epsg")),
        height=Height(**d.get("height", {})) if d.get("height") else Height(),
        epoch=Epoch(**d.get("epoch", {})),
        source=Source(**d.get("source", {})),
        fields=list(d.get("fields", [])),
        known_points=list(d.get("known_points", [])),
        skipped=int(d.get("skipped", 0)),
        log=list(d.get("log", [])),
        note=d.get("note"),
    )
    for fd in d.get("features", []):
        g = fd.get("geometry")
        fs.features.append(Feature(
            id=str(fd["id"]), name=fd.get("name", ""),
            geometry=geometry_from_dict(g) if g else None,
            attributes=dict(fd.get("attributes", {})), layer=fd.get("layer")))
    return fs


def dumps(fs: FeatureSet, indent=1) -> str:
    return json.dumps(to_dict(fs), ensure_ascii=False, indent=indent)


def save(fs: FeatureSet, path) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(fs))
        f.write("\n")


def load(path) -> FeatureSet:
    with open(path, "r", encoding="utf-8") as f:
        return from_dict(json.load(f))
