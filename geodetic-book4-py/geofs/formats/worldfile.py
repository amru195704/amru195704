# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""ワールドファイル（.tfw/.jgw/.pgw/.wld・第4巻 12 章）⇄ GeoFeatureSet。座標のみ（画像は触らない）。v2 段階 C-1。

6 行: A（x 方向の画素サイズ）, D, B（回転）, E（y 方向の画素サイズ・通常は負）, C（左上画素中心の X=東）, F（同 Y=北）。
測地系は書かれていないので補足ファイル／params で補う。
読み: 「原点（左上画素中心）」「+1000px x」「+1000px y」の 3 点（＋画像サイズが分かれば 4 隅）にする。
書き: 変換後の 3 点から A〜F を作り直す（局所的にはアフィンとみなす）。
"""
from __future__ import annotations
from typing import Optional
from ..model import Vertex, Geometry, Feature, FeatureSet
from ..sidecar import for_output
from ._common import build_metadata, MissingInfo

SPAN = 1000.0     # 画素ベクトルを取る間隔（px）


def read_worldfile(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    params = dict(params or {})
    try:
        fs = build_metadata("worldfile", path, {}, sidecar, params, required=("crs", "axis"))
    except MissingInfo as e:
        if "軸" in str(e):
            raise MissingInfo("worldfile: ワールドファイルは座標の並びの決まりが無い（区分 A）。補足ファイルか params で軸（axis.order。ふつうは east,north）を指定してください（第4巻 12 章・付録 7）")
        raise MissingInfo("worldfile: ワールドファイルは測地系を持たない。補足ファイルか params で座標参照系を指定してください（第4巻 12 章）")
    vals = [float(l.strip()) for l in open(path, encoding="utf-8-sig") if l.strip()][:6]
    if len(vals) != 6:
        raise ValueError("worldfile: 6 行の数値ではない")
    A, D, B, E, C, F = vals
    geo = fs.crs.is_geographic
    W, H = params.get("width"), params.get("height")
    # C・F（1 つめ・2 つめの座標）の並び。補足ファイルが north,east／lat,lon なら C が北
    first = (fs.source.axis_order or "").replace(" ", "").split(",")[0]
    c_is_north = first in ("north", "lat")

    def v(px, py):
        P, Q = C + A * px + B * py, F + D * px + E * py      # P＝1 つめの軸・Q＝2 つめの軸
        north, east = (P, Q) if c_is_north else (Q, P)
        return Vertex(lat=north, lon=east) if geo else Vertex(x=north, y=east)

    pts = [("原点(左上画素中心)", 0, 0), ("+1000px x", SPAN, 0), ("+1000px y", 0, SPAN)]
    if W and H:
        pts += [("右上", W - 1, 0), ("右下", W - 1, H - 1), ("左下", 0, H - 1)]
    for i, (nm, px, py) in enumerate(pts, start=1):
        fs.features.append(Feature(id=str(i), name=nm, geometry=Geometry("point", v(px, py)), attributes={"px": px, "py": py}))
    fs.fields = ["px", "py"]
    fs.log.append(f"worldfile: A={A} D={D} B={B} E={E} C={C} F={F}" + (f"（画像 {W}×{H}）" if W and H else "（画像サイズ不明＝原点と画素ベクトルだけ）"))
    return fs


def write_worldfile(fs: FeatureSet, path, digits: int = 10) -> dict:
    """「原点」「+1000px x」「+1000px y」の 3 点（px/py 属性）から A〜F を作る。"""
    by = {}
    for f in fs.features:
        if f.geometry and f.geometry.kind == "point" and "px" in f.attributes:
            by[(float(f.attributes["px"]), float(f.attributes["py"]))] = f.geometry.coords
    o, px, py = by.get((0.0, 0.0)), by.get((SPAN, 0.0)), by.get((0.0, SPAN))
    if not (o and px and py):
        raise ValueError("worldfile: 原点・+1000px x・+1000px y の 3 点が要る（read_worldfile／read_geotiff の出力を変換したもの）")
    geo = fs.crs.is_geographic

    def XY(v: Vertex):
        return (v.lon, v.lat) if geo else (v.y, v.x)
    C, F = XY(o)
    A, D = (XY(px)[0] - C) / SPAN, (XY(px)[1] - F) / SPAN
    B, E = (XY(py)[0] - C) / SPAN, (XY(py)[1] - F) / SPAN
    with open(path, "w", encoding="utf-8", newline="\n") as fp:
        for val in (A, D, B, E, C, F):
            fp.write(f"{val:.{digits}f}\n")
    fs.log.append("worldfile: 変換後の 3 点からアフィンを作り直した（回転・縮尺は局所近似）")
    return for_output(fs, "worldfile", axis_order="lon,lat" if geo else "east,north")
