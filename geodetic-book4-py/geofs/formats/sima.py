# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""SIMA（第4巻 9 章）⇄ GeoFeatureSet。点（A01）と区画（D00〜D99・B01）。

SIMA は X=北・Y=東の投影座標で、測地系・系番号・高さの基準・元期は持たない（補足ファイルで補う）。
文字コードは Shift_JIS が既定。
区画は 3 点以上なら面（始点＝終点の繰り返しは 1 つにまとめる）、2 点なら線、1 点以下は読み飛ばす。
"""
from __future__ import annotations
from typing import Optional
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet
from ..sidecar import for_output
from ._common import build_metadata, read_text, encoding_for_write, fmt_num, MissingInfo


def _f(s):
    s = s.strip()
    return float(s) if s != "" else None


def read_sima(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    held = {"axis": {"order": "north,east", "unit": "m"}}
    fs = build_metadata("sima", path, held, sidecar, params, required=("crs",))
    if fs.crs.is_geographic:
        raise MissingInfo("sima: SIMA は平面直角（X=北・Y=東）の形式。crs.system が geographic になっている")
    swap = (fs.source.axis_order or "north,east").replace(" ", "") == "east,north"   # 区分 B: 補足ファイルが east,north なら入れ替えて読む
    text, used = read_text(path, fs.source.encoding or "Shift_JIS", fs.log)
    fs.source.encoding = used
    by_no = {}
    parcels = []      # (no, name, kind, [(pno, pname)])
    cur = None
    has_z = False
    unresolved = 0
    for ln, line in enumerate(text.splitlines(), start=1):
        c = [s.strip() for s in line.split(",")]
        tag = c[0] if c else ""
        if tag == "G00":
            fs.log.append(f"G00: {','.join(c[1:])}")
        elif tag == "Z00":
            fs.log.append(f"Z00: {','.join(c[1:])}")
        elif tag == "A01" and len(c) >= 5:
            try:
                no, name, x, y = c[1], c[2], float(c[3]), float(c[4])
            except ValueError:
                fs.skipped += 1
                fs.log.append(f"{ln} 行目: A01 の座標を読めない → 読み飛ばし")
                continue
            z = _f(c[5]) if len(c) > 5 else None
            if z is not None:
                has_z = True
                if fs.source.offset_to_TP is not None:
                    z += fs.source.offset_to_TP
            v = Vertex(x=y, y=x, h=z) if swap else Vertex(x=x, y=y, h=z)
            fid = no or str(len(by_no) + 1)
            f = Feature(id=fid, name=name, geometry=Geometry("point", v))
            by_no[fid] = f
            fs.features.append(f)
        elif tag == "D00" and len(c) >= 3:
            cur = (c[1], c[2], c[3] if len(c) > 3 else "", [])
        elif tag in ("B01", "B02") and len(c) >= 2:
            if cur is None:
                fs.skipped += 1
                continue
            cur[3].append((c[1], c[2] if len(c) > 2 else ""))
        elif tag == "D99":
            if cur is not None:
                parcels.append(cur)
            cur = None
        # C01〜C09（辺データ）・その他は読み飛ばす（座標から再計算できる）
    if has_z and fs.height.datum == "none" and not (sidecar or {}).get("height") and not (params or {}).get("height"):
        raise MissingInfo("sima: Z（高さ）があるのに高さの基準（Ⓒ height.datum）が分からない。補足ファイルか params で指定してください")
    for no, name, kubun, pts in parcels:
        verts = []
        for pno, pname in pts:
            p = by_no.get(pno)
            if p is None:
                unresolved += 1
                continue
            v = p.geometry.coords.copy()
            v.ref = p.id
            verts.append(v)
        if len(verts) >= 2 and _same(verts[0], verts[-1]):
            verts = verts[:-1]
        if len(verts) >= 3:
            g = Geometry("polygon", Polygon(verts))
        elif len(verts) == 2:
            g = Geometry("line", verts)
        else:
            fs.skipped += 1
            fs.log.append(f"区画 {no} {name}: 構成点が足りない → 読み飛ばし")
            continue
        fs.features.append(Feature(id=f"D{no}", name=name, geometry=g,
                                   attributes={"区画番号": no, "区画区分": kubun,
                                               "構成点": " ".join(p for p, _ in pts)}))
    if unresolved:
        fs.skipped += unresolved
        fs.log.append(f"区画の構成点で A01 に無い点番号: {unresolved} 件")
    fs.fields = []
    return fs


def _same(a: Vertex, b: Vertex) -> bool:
    return round(a.x, 3) == round(b.x, 3) and round(a.y, 3) == round(b.y, 3)


def write_sima(fs: FeatureSet, path, encoding: str = "Shift_JIS", title: str = "GeoFeatureSet",
               digits: int = 3) -> dict:
    """点は A01、線・面は画地データ（D00/B01/D99）。穴は別の区画「名前(穴n)」。"""
    if fs.crs.is_geographic:
        raise ValueError("sima: SIMA は平面直角の形式。先に convert() で投影座標にしてください")
    lines = [f"G00,03,{title},", f"Z00,{fs.crs.label()},", "A00,"]
    # 点番号の割り当て
    pts = []                 # (no, name, Vertex)
    no_by_id = {}
    key_by_xy = {}
    next_no = 1
    for f in fs.features:
        if f.geometry is not None and f.geometry.kind == "point":
            no = f.id if f.id.isdigit() else None
            if no is None or no in no_by_id.values():
                while str(next_no) in no_by_id.values():
                    next_no += 1
                no = str(next_no)
            v = f.geometry.coords
            pts.append((no, f.name, v))
            no_by_id[f.id] = no
            key_by_xy.setdefault((round(v.x, 3), round(v.y, 3)), no)
    use_h = fs.height.datum != "none"

    def ensure_point(v: Vertex, name: str) -> str:
        nonlocal next_no
        if v.ref is not None and v.ref in no_by_id:
            return no_by_id[v.ref]
        key = (round(v.x, 3), round(v.y, 3))
        if key in key_by_xy:
            return key_by_xy[key]
        mx = max((int(n) for n, _, _ in pts if n.isdigit()), default=0)
        no = str(mx + 1)
        pts.append((no, name, v))
        key_by_xy[key] = no
        return no

    parcels = []            # (name, kubun, [no])
    for f in fs.features:
        g = f.geometry
        if g is None or g.kind == "point":
            continue
        rings = []          # (label, [Vertex])
        if g.kind == "multipoint":
            for i, v in enumerate(g.coords):
                ensure_point(v, f"{f.name}#{i+1}")
            continue
        if g.kind == "line":
            rings.append((f.name, g.coords))
        elif g.kind == "multiline":
            rings += [(f"{f.name}({i+1})", l) for i, l in enumerate(g.coords)]
        elif g.kind == "polygon":
            rings.append((f.name, g.coords.outer))
            rings += [(f"{f.name}(穴{i+1})", r) for i, r in enumerate(g.coords.holes)]
        elif g.kind == "multipolygon":
            for i, p in enumerate(g.coords):
                rings.append((f"{f.name}({i+1})", p.outer))
                rings += [(f"{f.name}({i+1})(穴{j+1})", r) for j, r in enumerate(p.holes)]
        kubun = str(f.attributes.get("区画区分", "1") or "1")
        for label, ring in rings:
            nos = [ensure_point(v, f"{label}#{k+1}") for k, v in enumerate(ring)]
            parcels.append((label, kubun, nos))
    name_by_no = {n: nm for n, nm, _ in pts}
    for no, name, v in sorted(pts, key=lambda t: (not t[0].isdigit(), int(t[0]) if t[0].isdigit() else 0, t[0])):
        z = fmt_num(v.h, digits) if use_h else ""
        lines.append(f"A01,{no},{name},{fmt_num(v.x, digits)},{fmt_num(v.y, digits)},{z},")
    lines.append("A99,")
    if parcels:
        lines.append("Z00,画地データ,")
        for i, (label, kubun, nos) in enumerate(parcels, start=1):
            lines.append(f"D00,{i},{label},{kubun},")
            for no in nos:
                lines.append(f"B01,{no},{name_by_no.get(no, '')},")
            lines.append("D99,")
    enc = encoding_for_write(encoding)
    with open(path, "wb") as fp:
        fp.write(("\r\n".join(lines) + "\r\n").encode(enc, errors="replace"))
    return for_output(fs, "sima", encoding=encoding)
