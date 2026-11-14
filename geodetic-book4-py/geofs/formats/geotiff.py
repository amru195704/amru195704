# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""GeoTIFF／COG（第4巻 12 章）→ GeoFeatureSet。座標のみ（TIFF は書き換えない）。v2 段階 C-1。

TIFF のタグ: 256/257（幅・高さ）, 33550 ModelPixelScale, 33922 ModelTiepoint, 34264 ModelTransformation,
34735 GeoKeyDirectory（1025 RasterType, 2048 GeographicType, 3072 ProjectedCSType）。BigTIFF（COG に多い）も読む。
出力は 4 隅＋原点＋画素ベクトルの点（write_worldfile で新しいワールドファイルにできる）。
"""
from __future__ import annotations
import struct
from typing import Optional
from ..model import Vertex, Geometry, Feature, FeatureSet
from ..wkt import crs_from_epsg
from ._common import build_metadata, MissingInfo
from .worldfile import SPAN


def _tags(data: bytes):
    bo = "<" if data[:2] == b"II" else ">" if data[:2] == b"MM" else None
    if bo is None:
        raise ValueError("geotiff: TIFF ではない")
    magic = struct.unpack(bo + "H", data[2:4])[0]
    big = magic == 43
    if big:
        off = struct.unpack(bo + "Q", data[8:16])[0]
        n = struct.unpack(bo + "Q", data[off:off + 8])[0]
        ent, pos, esz = 20, off + 8, 8
    elif magic == 42:
        off = struct.unpack(bo + "I", data[4:8])[0]
        n = struct.unpack(bo + "H", data[off:off + 2])[0]
        ent, pos, esz = 12, off + 2, 4
    else:
        raise ValueError("geotiff: TIFF ではない")
    sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 16: 8, 17: 8, 18: 8}
    fmt = {3: "H", 4: "I", 8: "h", 9: "i", 11: "f", 12: "d", 16: "Q", 17: "q"}
    tags = {}
    for i in range(n):
        e = data[pos + i * ent: pos + (i + 1) * ent]
        tag, typ = struct.unpack(bo + "HH", e[:4])
        cnt = struct.unpack(bo + ("Q" if big else "I"), e[4:4 + esz])[0]
        size = sizes.get(typ, 1) * cnt
        valoff = e[4 + esz:4 + 2 * esz]
        if size <= len(valoff):
            raw = valoff[:size]
        else:
            o = struct.unpack(bo + ("Q" if big else "I"), valoff)[0]
            raw = data[o:o + size]
        if typ in fmt:
            tags[tag] = list(struct.unpack(bo + fmt[typ] * cnt, raw))
        elif typ == 2:
            tags[tag] = raw.rstrip(b"\x00").decode("ascii", "replace")
        else:
            tags[tag] = raw
    return tags


def read_geotiff(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    data = open(path, "rb").read(16 * 1024 * 1024)      # IFD は先頭にある（COG は先頭に集約）
    tags = _tags(data)
    W, H = (tags.get(256) or [None])[0], (tags.get(257) or [None])[0]
    held = {}
    epsg = None
    raster_is_point = False
    gk = tags.get(34735)
    if gk and len(gk) >= 4:
        nkeys = gk[3]
        for i in range(nkeys):
            k, loc, cnt, val = gk[4 + 4 * i: 8 + 4 * i]
            if k == 1025 and loc == 0:
                raster_is_point = (val == 2)
            if k in (2048, 3072) and loc == 0 and val not in (0, 32767):
                epsg = val
    crs = crs_from_epsg(epsg) if epsg else None
    if crs:
        held["crs"] = {"datum": crs.datum, "system": crs.system, "zone": crs.zone, "epsg": crs.epsg}
    try:
        fs = build_metadata("geotiff", path, held, sidecar, params, required=("crs",))
    except MissingInfo:
        raise MissingInfo(f"geotiff: GeoKey の EPSG（{epsg}）を座標参照系に写せない。補足ファイルか params で指定してください（第4巻 12 章）")
    # 画素 → 座標（アフィン）
    if 34264 in tags:
        m = tags[34264]
        A, B, C, D, E, F = m[0], m[1], m[3], m[4], m[5], m[7]
    elif 33922 in tags and 33550 in tags:
        tp, sc = tags[33922], tags[33550]
        i, j, x, y = tp[0], tp[1], tp[3], tp[4]
        A, E = sc[0], -sc[1]
        B = D = 0.0
        C, F = x - i * A, y - j * E
    else:
        raise ValueError("geotiff: ModelTiepoint/ModelPixelScale も ModelTransformation も無い（位置情報の無い TIFF）")
    # PixelIsArea（既定）: 原点は左上画素の「左上隅」。ワールドファイルは画素「中心」なので半画素ずらす
    if not raster_is_point:
        C, F = C + A / 2 + B / 2, F + D / 2 + E / 2
    geo = fs.crs.is_geographic

    def v(px, py):
        X, Y = C + A * px + B * py, F + D * px + E * py
        return Vertex(lat=Y, lon=X) if geo else Vertex(x=Y, y=X)
    pts = [("原点(左上画素中心)", 0, 0), ("+1000px x", SPAN, 0), ("+1000px y", 0, SPAN)]
    if W and H:
        pts += [("右上", W - 1, 0), ("右下", W - 1, H - 1), ("左下", 0, H - 1)]
    for i, (nm, px, py) in enumerate(pts, start=1):
        fs.features.append(Feature(id=str(i), name=nm, geometry=Geometry("point", v(px, py)), attributes={"px": px, "py": py}))
    fs.fields = ["px", "py"]
    fs.log.append(f"geotiff: {W}×{H} EPSG={epsg} raster={'PixelIsPoint' if raster_is_point else 'PixelIsArea'} A={A} E={E} C={C} F={F}")
    return fs
