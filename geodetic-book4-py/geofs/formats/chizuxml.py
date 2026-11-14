# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""法務省 登記所備付地図データ（地図XML・第4巻 11 章）→ GeoFeatureSet。入力のみ。

- ヘッダ: <座標系>（「公共座標N系」か「任意座標系」）・<測地系判別>（測地成果2000／2011／任意）・<地図名>・<市区町村名>。
- 空間属性: zmn:GM_Point（X=北・Y=東）、GM_Curve（GM_Position.direct の X/Y か GM_PointRef.point の idref）、
  GM_Surface（exterior/interior の GM_Ring → GM_CompositeCurve.generator idref）。
- 主題属性: 筆界点（点番号 → 点）、筆界線（線）、筆（大字名・地番 → 面）。主題が無ければ空間属性をそのまま出す。
- 公共座標なら crs＝JGD2000/2011 × 系番号。任意座標なら local（位置合わせへ）。
- ZIP（複数 XML）対応。文字コードは XML 宣言に従う（Shift_JIS が多い）。
"""
from __future__ import annotations
import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet
from ._common import build_metadata, MissingInfo


def _local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def _text(el, name):
    for c in el.iter():
        if _local(c.tag) == name and c.text:
            return c.text.strip()
    return None


def _sources(path: str):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith(".xml") and not os.path.basename(n).startswith("._"):
                    yield n, z.read(n)
    else:
        yield os.path.basename(path), open(path, "rb").read()


def _parse_header(root):
    zahyo = _text(root, "座標系") or ""
    sokuchi = _text(root, "測地系判別") or ""
    m = re.search(r"(\d{1,2})", zahyo)
    zone = int(m.group(1)) if m and "公共" in zahyo else None
    local = "任意" in zahyo or zone is None
    datum = "JGD2011" if "2011" in sokuchi else "JGD2000" if "2000" in sokuchi else "JGD2011"
    return zahyo, sokuchi, zone, local, datum


def read_chizuxml(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    docs = []
    for name, data in _sources(path):
        try:
            root = ET.fromstring(data)
        except ET.ParseError as e:
            continue
        if _local(root.tag) != "地図":
            continue
        docs.append((name, root))
    if not docs:
        raise ValueError("chizuxml: ルート要素が <地図> の XML が無い")
    zahyo, sokuchi, zone, local, datum = _parse_header(docs[0][1])
    held = {"axis": {"order": "north,east", "unit": "m"}}
    if not local:
        held["crs"] = {"datum": datum, "system": "plane_rectangular", "zone": zone}
        held["epoch"] = {"geodetic_results": "2011" if datum == "JGD2011" else "2000"}
    else:
        held["crs"] = {"datum": datum, "system": "local"}
    fs = build_metadata("chizuxml", path, held, sidecar, params, required=())
    fs.log.append(f"座標系: {zahyo or '記載なし'} / 測地系判別: {sokuchi or '記載なし'} → {fs.crs.label()}")
    if local:
        fs.log.append("任意座標系の地図です。公共座標に合わせるには 2 点以上の対応点が必要です（第4巻 11 章）")
    for k in ("地図名", "市区町村名", "版番号", "市区町村コード"):
        v = _text(docs[0][1], k)
        if v:
            fs.log.append(f"{k}: {v}")
    n = 0
    for name, root in docs:
        points: Dict[str, Vertex] = {}
        curves: Dict[str, List[Vertex]] = {}
        surfaces: Dict[str, Polygon] = {}

        def position(el) -> Optional[Vertex]:
            x, y = _text(el, "X"), _text(el, "Y")
            if x is None or y is None:
                return None
            return Vertex(x=float(x), y=float(y))

        for el in root.iter():
            t = _local(el.tag)
            if t == "GM_Point" and el.get("id"):
                v = position(el)
                if v:
                    points[el.get("id")] = v
        for el in root.iter():
            if _local(el.tag) == "GM_Curve" and el.get("id"):
                pts: List[Vertex] = []
                for col in el.iter():
                    lt = _local(col.tag)
                    if lt == "GM_Position.direct":
                        v = position(col)
                        if v:
                            pts.append(v.copy())
                    elif lt == "GM_PointRef.point":
                        ref = col.get("idref")
                        if ref in points:
                            v = points[ref].copy(); v.ref = ref
                            pts.append(v)
                curves[el.get("id")] = pts

        def ring_from(ring_el) -> List[Vertex]:
            out: List[Vertex] = []
            for g in ring_el.iter():
                if _local(g.tag) == "GM_CompositeCurve.generator":
                    seg = [v.copy() for v in curves.get(g.get("idref"), [])]
                    if out and seg and (out[-1].x, out[-1].y) != (seg[0].x, seg[0].y) and (out[-1].x, out[-1].y) == (seg[-1].x, seg[-1].y):
                        seg = seg[::-1]
                    if out and seg and (out[-1].x, out[-1].y) == (seg[0].x, seg[0].y):
                        seg = seg[1:]
                    out += seg
            if len(out) >= 2 and (out[0].x, out[0].y) == (out[-1].x, out[-1].y):
                out = out[:-1]
            return out

        for el in root.iter():
            if _local(el.tag) == "GM_Surface" and el.get("id"):
                outer, holes = None, []
                for g in el.iter():
                    lt = _local(g.tag)
                    if lt == "GM_SurfaceBoundary.exterior":
                        outer = ring_from(g)
                    elif lt == "GM_SurfaceBoundary.interior":
                        holes.append(ring_from(g))
                if outer and len(outer) >= 3:
                    surfaces[el.get("id")] = Polygon(outer, [h for h in holes if len(h) >= 3])
        # 主題属性
        used_p, used_c, used_s = set(), set(), set()
        for el in root.iter():
            t = _local(el.tag)
            if t == "筆界点":
                ref = None
                for g in el.iter():
                    if _local(g.tag) == "GM_Point.idref":
                        ref = g.get("idref")
                if ref in points:
                    n += 1
                    used_p.add(ref)
                    attrs = {k: v for k, v in ((_local(c.tag), (c.text or "").strip()) for c in el) if v and k != "形状"}
                    attrs["種別"] = "筆界点"
                    fs.features.append(Feature(id=ref, name=attrs.get("点番号") or ref, geometry=Geometry("point", points[ref].copy()), attributes=attrs, layer="筆界点"))
            elif t == "筆界線":
                ref = None
                for g in el.iter():
                    if _local(g.tag) == "GM_Curve.idref":
                        ref = g.get("idref")
                if ref in curves and len(curves[ref]) >= 2:
                    n += 1
                    used_c.add(ref)
                    attrs = {k: v for k, v in ((_local(c.tag), (c.text or "").strip()) for c in el) if v and k != "形状"}
                    attrs["種別"] = "筆界線"
                    fs.features.append(Feature(id=f"C{n}", name=attrs.get("線種別", "筆界線"), geometry=Geometry("line", [v.copy() for v in curves[ref]]), attributes=attrs, layer="筆界線"))
            elif t == "筆":
                ref = None
                for g in el.iter():
                    if _local(g.tag) == "GM_Surface.idref":
                        ref = g.get("idref")
                if ref in surfaces:
                    n += 1
                    used_s.add(ref)
                    attrs = {k: v for k, v in ((_local(c.tag), (c.text or "").strip()) for c in el) if v and k != "形状"}
                    attrs["種別"] = "筆"
                    nm = " ".join(x for x in (attrs.get("大字名"), attrs.get("丁目名"), attrs.get("小字名"), attrs.get("地番")) if x) or ref
                    fs.features.append(Feature(id=f"S{n}", name=nm, geometry=Geometry("polygon", surfaces[ref]), attributes=attrs, layer="筆"))
        # 主題が無い空間属性はそのまま
        for pid, v in points.items():
            if pid not in used_p:
                n += 1
                fs.features.append(Feature(id=pid, name=pid, geometry=Geometry("point", v.copy()), attributes={"種別": "GM_Point"}, layer="空間属性"))
        for sid, poly in surfaces.items():
            if sid not in used_s:
                n += 1
                fs.features.append(Feature(id=f"S{n}", name=sid, geometry=Geometry("polygon", poly), attributes={"種別": "GM_Surface"}, layer="空間属性"))
        fs.log.append(f"{name}: GM_Point {len(points)}・GM_Curve {len(curves)}・GM_Surface {len(surfaces)}")
    keys = []
    for f in fs.features:
        for k in f.attributes:
            if k not in keys:
                keys.append(k)
    fs.fields = keys
    return fs
