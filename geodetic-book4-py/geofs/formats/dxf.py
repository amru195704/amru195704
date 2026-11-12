# -*- coding: utf-8 -*-
"""DXF（ASCII・第4巻 10 章）⇄ GeoFeatureSet。

- 読む要素: POINT／TEXT・MTEXT（最近接の POINT の点名）／LINE／LWPOLYLINE／POLYLINE+VERTEX（閉じフラグで線か面）／
  CIRCLE（中心点）／INSERT（挿入点）。他はスキップして件数。レイヤ（8）→ layer。
- 座標の向き: DXF の (X, Y) は数学座標＝X 東・Y 北だが、測量 CAD は X=北 で書く流儀がある。
  params["x_axis"]: "north"（既定・測量 CAD 流儀: DXF の X を x(北) に）／"east"（数学座標: DXF の X を y(東) に）。
- 座標参照系: OBJECTS の GEODATA（CoordinateSystemDefinition の WKT、303/301）があれば crs に。無ければ補足ファイル／params。
  どちらも無ければ local（任意座標）として読み、既知点で位置合わせ（helmert2d）する。
- 文字コード: $DWGCODEPAGE が ANSI_932 なら Shift_JIS、無ければ UTF-8 → Shift_JIS の順。
- 書き: HEADER（$ACADVER AC1015・$INSUNITS 6・$EXTMIN/MAX）・TABLES（LAYER）・ENTITIES（POINT＋TEXT、LWPOLYLINE）・
  OBJECTS（GEODATA に WKT）。
"""
from __future__ import annotations
import io
import math
from typing import Optional, List, Tuple, Dict
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet, CRS
from ..sidecar import for_output
from ..wkt import crs_from_wkt, wkt_for
from ._common import build_metadata, MissingInfo


# ---------- 低水準: グループコードの組 ----------
def _pairs(text: str):
    lines = text.splitlines()
    out = []
    i = 0
    while i + 1 < len(lines):
        try:
            code = int(lines[i].strip())
        except ValueError:
            i += 1
            continue
        out.append((code, lines[i + 1].rstrip("\r")))
        i += 2
    return out


def _decode(path: str, log: list) -> str:
    data = open(path, "rb").read()
    # $DWGCODEPAGE を ASCII の範囲で探す
    head = data[:20000].decode("ascii", errors="ignore")
    enc = None
    if "$DWGCODEPAGE" in head:
        i = head.index("$DWGCODEPAGE")
        seg = head[i:i + 200].split("\n")
        for k, s in enumerate(seg):
            if s.strip() == "3" and k + 1 < len(seg):
                cp = seg[k + 1].strip().upper()
                enc = "cp932" if "932" in cp else "utf-8" if "UTF" in cp else None
                break
    for e in ([enc] if enc else []) + ["utf-8", "cp932"]:
        try:
            s = data.decode(e)
            log.append(f"文字コード: {'Shift_JIS' if e == 'cp932' else 'UTF-8'}" + ("（$DWGCODEPAGE）" if e == enc else "（自動判定）"))
            return s
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


# ---------- 読み ----------
def read_dxf(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    params = dict(params or {})
    log: List[str] = []
    text = _decode(path, log)
    pairs = _pairs(text)

    # セクションに分ける
    sections: Dict[str, List[Tuple[int, str]]] = {}
    cur = None
    buf: List[Tuple[int, str]] = []
    for code, val in pairs:
        if code == 0 and val == "SECTION":
            buf = []
            cur = None
        elif code == 2 and cur is None and buf == []:
            cur = val
            sections[cur] = buf
        elif code == 0 and val == "ENDSEC":
            cur = None
            buf = []
        else:
            buf.append((code, val))

    # GEODATA（OBJECTS）の WKT
    held = {}
    wkt = ""
    geod = {}
    objs = sections.get("OBJECTS", [])
    in_geo = False
    for code, val in objs:
        if code == 0:
            in_geo = (val == "GEODATA")
            continue
        if in_geo:
            if code in (303, 301):
                wkt += val
            elif code in (10, 20, 11, 21, 40, 41, 12, 22):
                geod[code] = float(val)
    geo_crs = crs_from_wkt(wkt) if wkt else None
    if geo_crs:
        held["crs"] = {"datum": geo_crs.datum, "system": geo_crs.system, "zone": geo_crs.zone, "epsg": geo_crs.epsg}
    try:
        fs = build_metadata("dxf", path, held, sidecar, params, required=("crs",))
    except MissingInfo:
        # 宣言が無ければ任意座標として読む（位置合わせへ誘導）
        p2 = dict(params); p2["crs"] = {"datum": (sidecar or {}).get("crs", {}).get("datum") or "JGD2011", "system": "local"}
        fs = build_metadata("dxf", path, held, sidecar, p2, required=())
        fs.log.append("座標参照系の宣言が無いので任意座標（local）として読んだ。公共座標に合わせるには 2 点以上の対応点が必要（第4巻 10 章）")
    fs.log = log + fs.log
    if geo_crs:
        fs.log.append(f"GEODATA: {geo_crs.label()}")
    # 軸（区分 A）: 補足ファイル・params の axis → params の x_axis → 既定 north（GCVP の設定「X 方向」の既定と同じ）
    decl = (fs.source.axis_order or "").replace(" ", "")
    if decl:
        x_axis = "north" if decl.split(",")[0] in ("north", "lat") else "east"
        fs.log.append(f"dxf: 補足ファイルの軸 {decl} を使う（X＝{'北' if x_axis == 'north' else '東'}）")
    else:
        x_axis = (params.get("x_axis") or "north").lower()
    fs.source.axis_order = "north,east" if x_axis == "north" else "east,north"
    fs.source.axis_unit = "m"
    geo = fs.crs.is_geographic
    use_h = fs.height.datum != "none"
    # GEODATA の設計点→参照点の平行移動（回転は扱わない）
    dx = dy = 0.0
    if geod and 10 in geod and 11 in geod:
        dx, dy = geod[11] - geod[10], geod[21] - geod[20]
        if dx or dy:
            fs.log.append(f"GEODATA の参照点で平行移動 ({dx:+.3f}, {dy:+.3f})")

    def vertex(X: float, Y: float, Z: Optional[float]) -> Vertex:
        X, Y = X + dx, Y + dy
        if geo:
            v = Vertex(lat=Y, lon=X)
        elif x_axis == "north":
            v = Vertex(x=X, y=Y)
        else:
            v = Vertex(x=Y, y=X)
        if Z is not None and use_h:
            v.h = Z + (fs.source.offset_to_TP or 0.0)
        return v

    # ENTITIES
    ents = sections.get("ENTITIES", [])
    entities: List[Tuple[str, Dict[int, List[str]]]] = []
    cur_e = None
    for code, val in ents:
        if code == 0:
            cur_e = (val, {})
            entities.append(cur_e)
        elif cur_e is not None:
            cur_e[1].setdefault(code, []).append(val)

    def f(d, code, i=0, default=None):
        try:
            return float(d[code][i])
        except (KeyError, IndexError, ValueError):
            return default

    points: List[Feature] = []
    texts: List[Tuple[Vertex, str, str]] = []     # (位置, 文字, layer)
    n = 0
    skipped_types: Dict[str, int] = {}
    i = 0
    while i < len(entities):
        t, d = entities[i]
        layer = d.get(8, [None])[0]
        i += 1
        if t == "POINT" or t == "CIRCLE" or t == "INSERT":
            n += 1
            v = vertex(f(d, 10, 0, 0.0), f(d, 20, 0, 0.0), f(d, 30))
            attrs = {"entity": t}
            if t == "INSERT":
                attrs["block"] = d.get(2, [""])[0]
            points.append(Feature(id=str(n), name="", geometry=Geometry("point", v), attributes=attrs, layer=layer))
        elif t in ("TEXT", "MTEXT"):
            s = "".join(d.get(3, [])) + d.get(1, [""])[0]
            texts.append((vertex(f(d, 10, 0, 0.0), f(d, 20, 0, 0.0), None), s.strip(), layer))
        elif t == "LINE":
            n += 1
            vs = [vertex(f(d, 10, 0, 0.0), f(d, 20, 0, 0.0), f(d, 30)), vertex(f(d, 11, 0, 0.0), f(d, 21, 0, 0.0), f(d, 31))]
            fs.features.append(Feature(id=str(n), name=f"L{n}", geometry=Geometry("line", vs), attributes={"entity": t}, layer=layer))
        elif t == "LWPOLYLINE":
            n += 1
            xs, ys = d.get(10, []), d.get(20, [])
            elev = f(d, 38)
            closed = (int(f(d, 70, 0, 0)) & 1) == 1
            vs = [vertex(float(x), float(y), elev) for x, y in zip(xs, ys)]
            if any(abs(float(b)) > 1e-9 for b in d.get(42, [])):
                fs.log.append(f"LWPOLYLINE {n}: 円弧（bulge）は折れ線の頂点だけ読んだ")
            _add_poly(fs, n, vs, closed, layer, t)
        elif t == "POLYLINE":
            n += 1
            closed = (int(f(d, 70, 0, 0)) & 1) == 1
            vs = []
            while i < len(entities) and entities[i][0] == "VERTEX":
                vd = entities[i][1]
                vs.append(vertex(f(vd, 10, 0, 0.0), f(vd, 20, 0, 0.0), f(vd, 30)))
                i += 1
            if i < len(entities) and entities[i][0] == "SEQEND":
                i += 1
            _add_poly(fs, n, vs, closed, layer, t)
        else:
            skipped_types[t] = skipped_types.get(t, 0) + 1
    # TEXT を最近接の POINT に結びつける
    thr = float(params.get("text_threshold", 0.5))
    for pos, s, _layer in texts:
        best, bd = None, None
        for p in points:
            v = p.geometry.coords
            if geo:
                dd = math.hypot((v.lat - pos.lat) * 111000, (v.lon - pos.lon) * 91000)
            else:
                dd = math.hypot(v.x - pos.x, v.y - pos.y)
            if bd is None or dd < bd:
                best, bd = p, dd
        if best is not None and bd is not None and bd <= thr and not best.name:
            best.name = s
        else:
            fs.skipped += 1
    for p in points:
        if not p.name:
            p.name = f"P{p.id}"
    fs.features = points + fs.features
    fs.features.sort(key=lambda ft: int(ft.id))
    if skipped_types:
        fs.skipped += sum(skipped_types.values())
        fs.log.append("読まない要素: " + ", ".join(f"{k} {v}" for k, v in sorted(skipped_types.items())))
    fs.fields = ["entity", "block"]
    return fs


def _add_poly(fs: FeatureSet, n: int, vs: List[Vertex], closed: bool, layer, t: str):
    if len(vs) >= 2 and _same(vs[0], vs[-1]):
        vs = vs[:-1]
        closed = True
    if closed and len(vs) >= 3:
        fs.features.append(Feature(id=str(n), name=f"A{n}", geometry=Geometry("polygon", Polygon(vs)), attributes={"entity": t}, layer=layer))
    elif len(vs) >= 2:
        fs.features.append(Feature(id=str(n), name=f"L{n}", geometry=Geometry("line", vs), attributes={"entity": t}, layer=layer))
    else:
        fs.skipped += 1


def _same(a: Vertex, b: Vertex) -> bool:
    return (a.x, a.y, a.lat, a.lon) == (b.x, b.y, b.lat, b.lon)


# ---------- 書き ----------
def write_dxf(fs: FeatureSet, path, x_axis: str = "north", encoding: str = "UTF-8", digits: int = 4,
              text_height: float = 0.5, write_geodata: bool = True) -> dict:
    """DXF R2000（AC1015）の ASCII。点は POINT＋TEXT（点名）、線は LWPOLYLINE、面は閉じた LWPOLYLINE。"""
    geo = fs.crs.is_geographic
    use_h = fs.height.datum != "none"
    enc = "cp932" if encoding.upper().replace("-", "_") in ("SHIFT_JIS", "SJIS", "CP932") else "utf-8"
    handle = [0x100]

    def nh():
        handle[0] += 1
        return f"{handle[0]:X}"

    def XY(v: Vertex):
        if geo:
            return v.lon, v.lat
        return (v.x, v.y) if x_axis == "north" else (v.y, v.x)

    out = []
    def g(code, val):
        out.append(f"{code:3d}" if code < 100 else str(code)); out.append(str(val))

    def num(v):
        return f"{v:.{9 if geo else digits}f}"

    # 範囲
    allv = [v for f in fs.features if f.geometry for v in f.geometry.vertices()]
    xs = [XY(v)[0] for v in allv] or [0.0]; ys = [XY(v)[1] for v in allv] or [0.0]
    layers = []
    for f in fs.features:
        l = f.layer or "0"
        if l not in layers:
            layers.append(l)
    for l in ("0", "TEXT"):
        if l not in layers:
            layers.append(l)

    # HEADER
    g(0, "SECTION"); g(2, "HEADER")
    g(9, "$ACADVER"); g(1, "AC1015")
    g(9, "$DWGCODEPAGE"); g(3, "ANSI_932" if enc == "cp932" else "UTF-8")
    g(9, "$INSUNITS"); g(70, 6)
    g(9, "$EXTMIN"); g(10, num(min(xs))); g(20, num(min(ys))); g(30, "0.0")
    g(9, "$EXTMAX"); g(10, num(max(xs))); g(20, num(max(ys))); g(30, "0.0")
    g(9, "$HANDSEED"); g(5, "FFFF")
    g(0, "ENDSEC")
    # TABLES（LAYER）
    g(0, "SECTION"); g(2, "TABLES")
    g(0, "TABLE"); g(2, "LAYER"); g(5, nh()); g(100, "AcDbSymbolTable"); g(70, len(layers))
    for l in layers:
        g(0, "LAYER"); g(5, nh()); g(100, "AcDbSymbolTableRecord"); g(100, "AcDbLayerTableRecord")
        g(2, l); g(70, 0); g(62, 7); g(6, "Continuous")
    g(0, "ENDTAB")
    # BLOCK_RECORD（*Model_Space に GEODATA の拡張辞書をぶら下げる＝AutoCAD／ezdxf が GEODATA を見つける場所）
    geo_dict = nh() if (write_geodata and fs.crs.system != "local") else None
    gd_handle = nh() if geo_dict else None
    ms, ps = nh(), nh()
    g(0, "TABLE"); g(2, "BLOCK_RECORD"); g(5, nh()); g(100, "AcDbSymbolTable"); g(70, 2)
    g(0, "BLOCK_RECORD"); g(5, ms)
    if geo_dict:
        g(102, "{ACAD_XDICTIONARY"); g(360, geo_dict); g(102, "}")
    g(100, "AcDbSymbolTableRecord"); g(100, "AcDbBlockTableRecord"); g(2, "*Model_Space")
    g(0, "BLOCK_RECORD"); g(5, ps); g(100, "AcDbSymbolTableRecord"); g(100, "AcDbBlockTableRecord"); g(2, "*Paper_Space")
    g(0, "ENDTAB")
    g(0, "ENDSEC")
    # BLOCKS
    g(0, "SECTION"); g(2, "BLOCKS")
    for name, owner in (("*Model_Space", ms), ("*Paper_Space", ps)):
        g(0, "BLOCK"); g(5, nh()); g(330, owner); g(100, "AcDbEntity"); g(8, "0"); g(100, "AcDbBlockBegin")
        g(2, name); g(70, 0); g(10, "0.0"); g(20, "0.0"); g(30, "0.0"); g(3, name); g(1, "")
        g(0, "ENDBLK"); g(5, nh()); g(330, owner); g(100, "AcDbEntity"); g(8, "0"); g(100, "AcDbBlockEnd")
    g(0, "ENDSEC")
    # ENTITIES
    g(0, "SECTION"); g(2, "ENTITIES")
    npt = nln = npl = 0
    for f in fs.features:
        geom = f.geometry
        if geom is None:
            continue
        layer = f.layer or "0"
        if geom.kind in ("point", "multipoint"):
            vs = geom.vertices()
            for i, v in enumerate(vs):
                X, Y = XY(v)
                g(0, "POINT"); g(5, nh()); g(100, "AcDbEntity"); g(8, layer); g(100, "AcDbPoint")
                g(10, num(X)); g(20, num(Y)); g(30, f"{v.h:.3f}" if use_h and v.h is not None else "0.0")
                nm = f.name if geom.kind == "point" else f"{f.name}#{i+1}"
                if nm:
                    g(0, "TEXT"); g(5, nh()); g(100, "AcDbEntity"); g(8, "TEXT"); g(100, "AcDbText")
                    g(10, num(X)); g(20, num(Y)); g(30, "0.0"); g(40, text_height); g(1, nm); g(100, "AcDbText")
                npt += 1
            continue
        rings = []
        if geom.kind == "line":
            rings = [(list(geom.coords), False)]
        elif geom.kind == "multiline":
            rings = [(list(l), False) for l in geom.coords]
        elif geom.kind == "polygon":
            rings = [(list(geom.coords.outer), True)] + [(list(r), True) for r in geom.coords.holes]
        elif geom.kind == "multipolygon":
            for p in geom.coords:
                rings.append((list(p.outer), True)); rings += [(list(r), True) for r in p.holes]
        for vs, closed in rings:
            g(0, "LWPOLYLINE"); g(5, nh()); g(100, "AcDbEntity"); g(8, layer); g(100, "AcDbPolyline")
            g(90, len(vs)); g(70, 1 if closed else 0)
            if use_h and all(v.h is not None for v in vs) and len({round(v.h, 3) for v in vs}) == 1:
                g(38, f"{vs[0].h:.3f}")
            for v in vs:
                X, Y = XY(v); g(10, num(X)); g(20, num(Y))
            if closed: npl += 1
            else: nln += 1
    g(0, "ENDSEC")
    # OBJECTS（GEODATA）
    g(0, "SECTION"); g(2, "OBJECTS")
    root = nh()
    g(0, "DICTIONARY"); g(5, root); g(330, "0"); g(100, "AcDbDictionary"); g(281, 1)
    if geo_dict:
        gd = gd_handle
        # *Model_Space の拡張辞書: ACAD_GEOGRAPHICDATA → GEODATA
        g(0, "DICTIONARY"); g(5, geo_dict); g(330, ms); g(100, "AcDbDictionary"); g(281, 1)
        g(3, "ACAD_GEOGRAPHICDATA"); g(360, gd)
        wkt = wkt_for(fs.crs)
        g(0, "GEODATA"); g(5, gd); g(330, geo_dict); g(100, "AcDbGeoData"); g(90, 3); g(330, ms)
        g(70, 3 if geo else 2)                       # 1=ローカルグリッド 2=投影グリッド 3=地理
        g(10, "0.0"); g(20, "0.0"); g(30, "0.0")     # 設計点
        g(11, "0.0"); g(21, "0.0"); g(31, "0.0")     # 参照点（同じ＝平行移動なし）
        g(40, 1.0); g(91, 6); g(41, 1.0); g(92, 6)
        g(210, 0.0); g(220, 0.0); g(230, 1.0)        # 上方向
        g(12, 0.0 if x_axis == "east" or geo else 1.0); g(22, 1.0 if x_axis == "east" or geo else 0.0)   # 北方向ベクトル
        g(95, 3)
        for i in range(0, len(wkt), 250):
            chunk = wkt[i:i + 250]
            g(303 if i + 250 < len(wkt) else 301, chunk)
    g(0, "ENDSEC")
    g(0, "EOF")
    with open(path, "wb") as fp:
        fp.write(("\r\n".join(out) + "\r\n").encode(enc, errors="replace"))
    fs.log.append(f"dxf: POINT {npt}・LWPOLYLINE 線 {nln}・面 {npl}（X 方向＝{'北' if x_axis == 'north' else '東'}）")
    # 地理座標は XY() が常に (経度, 緯度) で書くので補足ファイルも lon,lat 固定（x_axis は投影座標のときだけ効く）
    order = "lon,lat" if geo else ("north,east" if x_axis == "north" else "east,north")
    sc = for_output(fs, "dxf", encoding="Shift_JIS" if enc == "cp932" else "UTF-8", axis_order=order)
    if write_geodata and fs.crs.system != "local":
        sc.pop("crs", None)       # GEODATA に書いたので補足ファイルには不要（読まないソフト向けに note に残す）
        sc["note"] = (sc.get("note") or "") + f"座標参照系は GEODATA に WKT で書いた（{fs.crs.label()}）。X 方向＝{'北' if x_axis == 'north' else '東'}"
    return sc
