# -*- coding: utf-8 -*-
"""J-LandXML（第4巻 9 章）⇄ GeoFeatureSet。CgPoint（点）と PlanFeature の CoordGeom（線・面）。

- 座標の順序は northing（北）→ easting（東）→ elev。中間の x(北)/y(東) とそのまま対応する。
- <CoordinateSystem epsgCode= name= horizontalDatum=> から crs を推定。無ければ補足ファイルか params。
- <Alignments>・<Surfaces> は読まない（件数をログ）。
"""
from __future__ import annotations
import io
import xml.etree.ElementTree as ET
from typing import Optional, List
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet
from ..sidecar import for_output
from ..wkt import crs_from_epsg, epsg_for, ROMAN
from ._common import build_metadata, MissingInfo
from ..model import CRS

NS = "http://www.landxml.org/schema/LandXML-1.2"


def _local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find(el, name):
    for c in el.iter():
        if _local(c.tag) == name:
            return c
    return None


def _crs_from_cs(cs) -> Optional[CRS]:
    if cs is None:
        return None
    code = cs.get("epsgCode")
    if code and code.isdigit():
        c = crs_from_epsg(int(code))
        if c:
            return c
    text = " ".join(v for k, v in cs.attrib.items() if k in ("name", "desc", "horizontalDatum", "datum")).upper()
    datum = ("JGD2024" if "JGD2024" in text else "JGD2011" if "JGD2011" in text else "JGD2000" if "JGD2000" in text
             else "WGS84" if "WGS" in text else "Tokyo" if "TOKYO" in text else None)
    if datum is None:
        return None
    import re
    m = re.search(r"CS[_ ]([IVX]+)", text)
    if m and m.group(1) in ROMAN:
        z = ROMAN.index(m.group(1)) + 1
        return CRS(datum, "plane_rectangular", z, epsg_for(CRS(datum, "plane_rectangular", z)))
    m = re.search(r"(\d{1,2})\s*系", text)
    if m and 1 <= int(m.group(1)) <= 19:
        z = int(m.group(1))
        return CRS(datum, "plane_rectangular", z, epsg_for(CRS(datum, "plane_rectangular", z)))
    return None


def _nums(text: str) -> List[float]:
    return [float(t) for t in (text or "").split()]


def read_landxml(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    root = ET.parse(path).getroot()
    if _local(root.tag) != "LandXML":
        raise ValueError("landxml: ルート要素が LandXML ではない")
    cs = _find(root, "CoordinateSystem")
    held = {}
    c = _crs_from_cs(cs)
    if c:
        held["crs"] = {"datum": c.datum, "system": c.system, "zone": c.zone, "epsg": c.epsg}
    try:
        fs = build_metadata("landxml", path, held, sidecar, params, required=("crs",))
    except MissingInfo:
        raise MissingInfo("landxml: <CoordinateSystem> から座標参照系が分からない。補足ファイルか params で指定してください（第4巻 9 章）")
    if c:
        fs.log.append(f"CoordinateSystem: {c.label()}" + (f"（epsg {c.epsg}）" if c.epsg else ""))
    if cs is not None and cs.get("name"):
        fs.log.append(f"CoordinateSystem name=\"{cs.get('name')}\"")
    fs.source.axis_order = "north,east"
    fs.source.axis_unit = "m"
    geo = fs.crs.is_geographic
    use_h = fs.height.datum != "none"

    def vertex(nums: List[float]) -> Optional[Vertex]:
        if len(nums) < 2:
            return None
        v = Vertex(lat=nums[0], lon=nums[1]) if geo else Vertex(x=nums[0], y=nums[1])
        if len(nums) >= 3 and use_h:
            v.h = nums[2] + (fs.source.offset_to_TP or 0.0)
        return v

    n = 0
    by_name = {}
    for cgs in [e for e in root.iter() if _local(e.tag) == "CgPoints"]:
        layer = cgs.get("name")
        for p in cgs:
            if _local(p.tag) != "CgPoint":
                continue
            n += 1
            v = vertex(_nums(p.text))
            if v is None:
                fs.skipped += 1
                continue
            name = p.get("name") or p.get("oID") or f"P{n}"
            attrs = {k: val for k, val in p.attrib.items() if k not in ("name",)}
            f = Feature(id=str(n), name=name, geometry=Geometry("point", v), attributes=attrs, layer=layer)
            fs.features.append(f)
            by_name[name] = f
            for k in attrs:
                if k not in fs.fields:
                    fs.fields.append(k)
    # PlanFeature → 線・面
    for pf in [e for e in root.iter() if _local(e.tag) == "PlanFeature"]:
        cg = _find(pf, "CoordGeom")
        if cg is None:
            fs.skipped += 1
            continue
        pts: List[Vertex] = []
        for seg in cg:
            t = _local(seg.tag)
            if t == "Line":
                s, e = _find(seg, "Start"), _find(seg, "End")
                vs, ve = vertex(_nums(s.text)) if s is not None else None, vertex(_nums(e.text)) if e is not None else None
                if vs is None or ve is None:
                    continue
                if not pts:
                    pts.append(vs)
                pts.append(ve)
            elif t in ("Curve", "Spiral", "IrregularLine"):
                # 曲線は始点・終点だけ（折れ線化はしない）
                s, e = _find(seg, "Start"), _find(seg, "End")
                for el in (s, e):
                    v = vertex(_nums(el.text)) if el is not None else None
                    if v is not None and (not pts or (pts[-1].x, pts[-1].y, pts[-1].lat, pts[-1].lon) != (v.x, v.y, v.lat, v.lon)):
                        pts.append(v)
                fs.log.append(f"PlanFeature {pf.get('name')}: {t} は始点・終点だけ読んだ")
        n += 1
        name = pf.get("name") or f"L{n}"
        attrs = {k: val for k, val in pf.attrib.items() if k != "name"}
        closed = len(pts) >= 4 and (pts[0].x, pts[0].y, pts[0].lat, pts[0].lon) == (pts[-1].x, pts[-1].y, pts[-1].lat, pts[-1].lon)
        if closed:
            fs.features.append(Feature(id=str(n), name=name, geometry=Geometry("polygon", Polygon(pts[:-1])), attributes=attrs))
        elif len(pts) >= 2:
            fs.features.append(Feature(id=str(n), name=name, geometry=Geometry("line", pts), attributes=attrs))
        else:
            fs.skipped += 1
    for tag in ("Alignment", "Surface", "Parcel"):
        k = sum(1 for e in root.iter() if _local(e.tag) == tag)
        if k:
            fs.log.append(f"{tag} {k} 件は読まない")
    return fs


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_landxml(fs: FeatureSet, path, digits: int = 4, application: str = "GeoFeatureSet") -> dict:
    """LandXML 1.2 の最小構成（Units・CoordinateSystem・CgPoints・PlanFeatures）。"""
    if fs.crs.system == "local":
        raise ValueError("landxml: 任意座標は CoordinateSystem を書けない。先に位置合わせしてください")
    geo = fs.crs.is_geographic
    use_h = fs.height.datum != "none"
    epsg = epsg_for(fs.crs)
    if fs.crs.system == "plane_rectangular":
        csname = f"{fs.crs.datum} / Japan Plane Rectangular CS {ROMAN[fs.crs.zone - 1]}"
    elif fs.crs.system == "utm":
        csname = f"{fs.crs.datum} / UTM zone {fs.crs.zone}N"
    else:
        csname = f"{fs.crs.datum} geographic"

    def coords(v: Vertex) -> str:
        a, b = (v.lat, v.lon) if geo else (v.x, v.y)
        d = 9 if geo else digits
        s = f"{a:.{d}f} {b:.{d}f}"
        if use_h and v.h is not None:
            s += f" {v.h:.3f}"
        return s

    out = io.StringIO()
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.write(f'<LandXML xmlns="{NS}" version="1.2" language="Japanese">\n')
    out.write('<Units><Metric areaUnit="squareMeter" linearUnit="meter" volumeUnit="cubicMeter" temperatureUnit="celsius" pressureUnit="HPA" angularUnit="decimal degrees" directionUnit="decimal degrees"/></Units>\n')
    out.write(f'<CoordinateSystem name="{_esc(csname)}" horizontalDatum="{_esc(fs.crs.datum)}"' + (f' epsgCode="{epsg}"' if epsg else "") + "/>\n")
    out.write(f'<Application name="{_esc(application)}"/>\n')
    pts = [f for f in fs.features if f.geometry and f.geometry.kind in ("point", "multipoint")]
    others = [f for f in fs.features if f.geometry and f.geometry.kind not in ("point", "multipoint")]
    if pts:
        out.write("<CgPoints>\n")
        for f in pts:
            for i, v in enumerate(f.geometry.vertices()):
                nm = f.name if f.geometry.kind == "point" else f"{f.name}#{i+1}"
                extra = "".join(f' {k}="{_esc(val)}"' for k, val in f.attributes.items() if k in ("code", "desc", "pntRef", "state") and val is not None)
                out.write(f'<CgPoint name="{_esc(nm)}"{extra}>{coords(v)}</CgPoint>\n')
        out.write("</CgPoints>\n")
    if others:
        out.write("<PlanFeatures>\n")
        for f in others:
            g = f.geometry
            rings = []
            if g.kind == "line":
                rings = [(f.name, list(g.coords), False)]
            elif g.kind == "multiline":
                rings = [(f"{f.name}({i+1})", list(l), False) for i, l in enumerate(g.coords)]
            elif g.kind == "polygon":
                rings = [(f.name, list(g.coords.outer), True)] + [(f"{f.name}(穴{i+1})", list(r), True) for i, r in enumerate(g.coords.holes)]
            elif g.kind == "multipolygon":
                for i, p in enumerate(g.coords):
                    rings.append((f"{f.name}({i+1})", list(p.outer), True))
                    rings += [(f"{f.name}({i+1})(穴{j+1})", list(r), True) for j, r in enumerate(p.holes)]
            for nm, vs, closed in rings:
                seq = vs + [vs[0]] if closed else vs
                out.write(f'<PlanFeature name="{_esc(nm)}"><CoordGeom>\n')
                for a, b in zip(seq, seq[1:]):
                    out.write(f"<Line><Start>{coords(a)}</Start><End>{coords(b)}</End></Line>\n")
                out.write("</CoordGeom></PlanFeature>\n")
        out.write("</PlanFeatures>\n")
    out.write("</LandXML>\n")
    with open(path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(out.getvalue())
    return for_output(fs, "landxml")
