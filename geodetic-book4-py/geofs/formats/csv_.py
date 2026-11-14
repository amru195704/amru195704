# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""CSV（第4巻 2 章）⇄ GeoFeatureSet。点だけ。

CSV は自分では何も持たない形式なので、座標参照系・軸・高さ・元期・文字コード（Ⓐ〜Ⓔ）を
補足ファイルか params で補う。列の割り当ては params["columns"]（{"name","a","b","h","id"}）か、
列名からの自動判定。軸の順序（axis.order）があれば、2 つの座標列のうち左を先の軸とする。
"""
from __future__ import annotations
import csv
import io
from typing import Optional
from ..model import Vertex, Geometry, Feature, FeatureSet
from ..sidecar import for_output
from ._common import build_metadata, read_text, encoding_for_write, parse_angle, fmt_num, MissingInfo

LAT_NAMES = ("lat", "latitude", "緯度", "b", "phi", "φ")
LON_NAMES = ("lon", "lng", "long", "longitude", "経度", "l", "lambda", "λ")
X_NAMES = ("x", "北", "n", "northing", "x座標", "x(北)")
Y_NAMES = ("y", "東", "e", "easting", "y座標", "y(東)")
H_NAMES = ("h", "標高", "height", "ele", "elev", "elevation", "alt", "altitude", "z", "楕円体高", "高さ")
NAME_NAMES = ("name", "点名", "名称", "title", "label", "point", "pt")
ID_NAMES = ("id", "no", "番号", "点番号", "no.", "num")


def _find(header, names):
    low = [h.strip().lower() for h in header]
    for n in names:
        if n in low:
            return low.index(n)
    return None


def read_csv(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    params = params or {}
    fs = build_metadata("csv", path, {}, sidecar, params, required=("crs",))
    text, used = read_text(path, fs.source.encoding, fs.log)
    fs.source.encoding = used
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return fs
    header = [h.strip() for h in rows[0]]
    cols = dict(params.get("columns", {}))
    geo = fs.crs.is_geographic

    def idx(key, names):
        if key in cols:
            return header.index(cols[key]) if cols[key] in header else None
        return _find(header, names)

    ia = idx("a", LAT_NAMES if geo else X_NAMES)
    ib = idx("b", LON_NAMES if geo else Y_NAMES)
    if (ia is None or ib is None) and "a" not in cols:
        # 期待する列名が無いとき: 座標らしい列がちょうど 2 つなら、それを使う（補足ファイルの宣言が優先）
        cand = [i for i, h in enumerate(header)
                if h.strip().lower() in LAT_NAMES + LON_NAMES + X_NAMES + Y_NAMES]
        if len(cand) == 2:
            ia, ib = cand
            fs.log.append(f"列名 {header[ia]},{header[ib]} を補足ファイルの宣言（{fs.crs.label()}）の座標として読んだ")
    if ia is None or ib is None:
        raise MissingInfo(f"csv: 座標の列が分からない（列名 {header}）。params['columns']={{'a':…,'b':…}} で指定してください")
    # 軸の順序: 2 つの座標列のうち左を先の軸に割り当て直す
    order = fs.source.axis_order
    if order:
        first = order.split(",")[0].strip()
        left, right = sorted((ia, ib))
        a_is_first = first in ("lat", "north")
        ia, ib = (left, right) if a_is_first else (right, left)
    ih = idx("h", (fs.source.height_column,) if fs.source.height_column else H_NAMES)
    if ih is not None and fs.height.datum == "none":
        fs.log.append(f"高さの列 {header[ih]} があるが height.datum=none なので使わない")
        ih = None
    if ih is not None:
        fs.source.height_column = header[ih]
    iname = idx("name", NAME_NAMES)
    iid = idx("id", ID_NAMES)
    used_idx = {i for i in (ia, ib, ih, iname, iid) if i is not None}
    fs.fields = [h for i, h in enumerate(header) if i not in used_idx]
    afmt = fs.source.axis_format
    unit_scale = 1.0
    if not geo and fs.source.axis_unit and fs.source.axis_unit.lower() in ("mm",):
        unit_scale = 0.001
    elif not geo and fs.source.axis_unit and fs.source.axis_unit.lower() in ("km",):
        unit_scale = 1000.0
    for n, r in enumerate(rows[1:], start=1):
        try:
            a, b = r[ia].strip(), r[ib].strip()
            if a == "" or b == "":
                raise ValueError("空")
            if geo:
                v = Vertex(lat=parse_angle(a, afmt), lon=parse_angle(b, afmt))
            else:
                v = Vertex(x=float(a) * unit_scale, y=float(b) * unit_scale)
            if ih is not None and ih < len(r) and r[ih].strip() != "":
                v.h = float(r[ih])
                if fs.source.offset_to_TP is not None:
                    v.h += fs.source.offset_to_TP
        except (ValueError, IndexError):
            fs.skipped += 1
            fs.log.append(f"{n+1} 行目: 座標を読めない → 読み飛ばし")
            continue
        fid = r[iid].strip() if iid is not None and iid < len(r) and r[iid].strip() else str(n)
        name = r[iname].strip() if iname is not None and iname < len(r) else ""
        attrs = {h: (r[i] if i < len(r) else "") for i, h in enumerate(header) if i not in used_idx}
        fs.features.append(Feature(id=fid, name=name, geometry=Geometry("point", v), attributes=attrs))
    return fs


def write_csv(fs: FeatureSet, path, encoding: str = "UTF-8", axis_order: Optional[str] = None,
              digits: Optional[int] = None, height_column: Optional[str] = None,
              with_id: bool = True) -> dict:
    """点を CSV に書く。線・面は全頂点を点として出す（点名は「地物名#番号」）。戻り値は補足ファイル（全項目）。"""
    geo = fs.crs.is_geographic
    if axis_order is None:
        axis_order = "lat,lon" if geo else "north,east"
    first = axis_order.split(",")[0].strip()
    a_first = first in ("lat", "north")
    if digits is None:
        digits = 9 if geo else 4
    if height_column is None:
        height_column = fs.source.height_column or ("標高" if fs.height.datum == "TP" else "楕円体高" if fs.height.datum == "ellipsoidal" else "")
    ca, cb = ("lat", "lon") if geo else ("x", "y")
    head = (["id"] if with_id else []) + ["name"] + ([ca, cb] if a_first else [cb, ca])
    use_h = fs.height.datum != "none"
    if use_h:
        head.append(height_column)
    head += list(fs.fields)
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(head)
    flat = 0
    for f in fs.features:
        if f.geometry is None:
            continue
        verts = f.geometry.vertices()
        if f.geometry.kind != "point":
            flat += 1
        for i, v in enumerate(verts):
            name = f.name if f.geometry.kind == "point" else f"{f.name}#{i+1}"
            fid = f.id if f.geometry.kind == "point" else f"{f.id}#{i+1}"
            a, b = (v.lat, v.lon) if geo else (v.x, v.y)
            row = ([fid] if with_id else []) + [name]
            row += [fmt_num(a, digits), fmt_num(b, digits)] if a_first else [fmt_num(b, digits), fmt_num(a, digits)]
            if use_h:
                row.append(fmt_num(v.h, 3))
            row += ["" if f.attributes.get(k) is None else str(f.attributes.get(k)) for k in fs.fields]
            w.writerow(row)
    if flat:
        fs.log.append(f"csv: 線・面 {flat} 地物の頂点を点として書いた")
    enc = encoding_for_write(encoding)
    with open(path, "wb") as fp:
        fp.write(out.getvalue().encode(enc))
    return for_output(fs, "csv", axis_order=axis_order, height_column=height_column if use_h else None,
                      encoding=encoding)
