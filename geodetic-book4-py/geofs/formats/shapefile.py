# -*- coding: utf-8 -*-
"""Shapefile（第4巻 3 章）⇄ GeoFeatureSet。.shp/.shx/.dbf/.prj/.cpg を ZIP 1 つで扱う（.shp 単体も可）。

- 座標は .shp の中では常に (X=東, Y=北) の順。平面直角の「X=北」とは逆なので、読みで x(北)/y(東) に入れ替え、書きで戻す
  （第4巻 1 章・3 章の最大の事故点）。
- 1 つの .shp は 1 つの幾何型。種類が混ざる集合は <名前>_point / _line / _polygon の 3 つの .shp に分けて ZIP に入れる。
- 面: 外周＝時計回り・穴＝反時計回り（Shapefile の規約）。穴は直前の外周に付ける。
- .prj（WKT1）→ crs。.cpg → 文字コード（無ければ .dbf の LDID、無ければ UTF-8 → Shift_JIS の順に試す）。
- 高さ: PointZ 等（型 +10）の Z。補足ファイルで基準（TP/ellipsoidal）を補う。
"""
from __future__ import annotations
import io
import os
import struct
import zipfile
import datetime
from typing import Optional, List, Tuple
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet
from ..sidecar import for_output
from ..wkt import crs_from_wkt, wkt_for
from ._common import build_metadata, MissingInfo, name_from

NAME_KEYS = ("name", "NAME", "Name", "点名", "名称", "title", "label", "id", "ID")
LDID = {0x13: "cp932", 0x57: "cp1252", 0x03: "cp1252", 0x4D: "cp936", 0x4E: "cp949", 0x4F: "cp950"}


# ---------- 低水準 ----------
def _ring_area2(ring: List[Tuple[float, float]]) -> float:
    """符号付き面積の 2 倍（x=東, y=北）。負＝時計回り。"""
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a


def _read_shp(data: bytes):
    """.shp → (shape_type, [(type, parts:[[(x,y,z)]])])。各レコードは parts（点列の並び）で返す。"""
    if len(data) < 100 or struct.unpack(">i", data[:4])[0] != 9994:
        raise ValueError("shp: ファイルコードが 9994 ではない")
    shape_type = struct.unpack("<i", data[32:36])[0]
    recs = []
    pos = 100
    while pos + 8 <= len(data):
        _num, clen = struct.unpack(">ii", data[pos:pos + 8])
        pos += 8
        body = data[pos:pos + clen * 2]
        pos += clen * 2
        if len(body) < 4:
            continue
        t = struct.unpack("<i", body[:4])[0]
        if t == 0:
            recs.append((0, []))
            continue
        base = t % 10 if t >= 10 else t          # 11→1, 13→3, 15→5, 18→8 / 21→1, 23→3, 25→5, 28→8
        has_z = 10 < t < 20
        if base == 1:
            x, y = struct.unpack("<dd", body[4:20])
            z = struct.unpack("<d", body[20:28])[0] if has_z else None
            recs.append((t, [[(x, y, z)]]))
        elif base in (3, 5, 8):
            if base == 8:
                n = struct.unpack("<i", body[36:40])[0]
                off = 40
                parts_idx = [0]
            else:
                nparts, n = struct.unpack("<ii", body[36:44])
                parts_idx = list(struct.unpack("<" + "i" * nparts, body[44:44 + 4 * nparts]))
                off = 44 + 4 * nparts
            xy = struct.unpack("<" + "d" * (2 * n), body[off:off + 16 * n])
            off += 16 * n
            zs = [None] * n
            if has_z and off + 16 + 8 * n <= len(body):
                zs = list(struct.unpack("<" + "d" * n, body[off + 16:off + 16 + 8 * n]))
            pts = [(xy[2 * i], xy[2 * i + 1], zs[i]) for i in range(n)]
            parts = []
            for pi, s in enumerate(parts_idx):
                e = parts_idx[pi + 1] if pi + 1 < len(parts_idx) else n
                parts.append(pts[s:e])
            recs.append((t, parts))
        else:
            recs.append((t, None))              # MultiPatch など
    return shape_type, recs


def _read_dbf(data: bytes, encoding: Optional[str], log: list):
    """.dbf → (fields:[name], rows:[dict], encoding)。"""
    if len(data) < 32:
        return [], [], encoding or "utf-8"
    nrec = struct.unpack("<i", data[4:8])[0]
    hlen, rlen = struct.unpack("<hh", data[8:12])
    ldid = data[29]
    if not encoding:
        encoding = LDID.get(ldid)
    cands = [encoding] if encoding else []
    cands += ["utf-8", "cp932"]
    fields = []
    pos = 32
    while pos + 32 <= hlen and data[pos] != 0x0D:
        raw = data[pos:pos + 11].split(b"\x00")[0]
        ftype = chr(data[pos + 11])
        flen = data[pos + 16]
        fdec = data[pos + 17]
        fields.append((raw, ftype, flen, fdec))
        pos += 32
    # 列名の文字コードを決める（最初に全列名が読めたもの）
    used = None
    for enc in cands:
        try:
            [f[0].decode(enc) for f in fields]
            used = enc
            break
        except UnicodeDecodeError:
            continue
    used = used or "latin-1"
    names = []
    for raw, *_ in fields:
        n = raw.decode(used, errors="replace")
        while n in names:
            n += "_"
        names.append(n)
    rows = []
    pos = hlen
    for _ in range(nrec):
        rec = data[pos:pos + rlen]
        pos += rlen
        if len(rec) < rlen or rec[0:1] == b"*":
            continue
        row = {}
        off = 1
        for (raw, ftype, flen, fdec), name in zip(fields, names):
            cell = rec[off:off + flen]
            off += flen
            if ftype in ("N", "F"):
                s = cell.strip().decode("ascii", errors="ignore")
                if s == "" or s == "*" * len(s):
                    row[name] = None
                else:
                    try:
                        row[name] = int(s) if fdec == 0 and "." not in s and "e" not in s.lower() else float(s)
                    except ValueError:
                        row[name] = s
            elif ftype == "L":
                c = cell[:1].decode("ascii", errors="ignore").upper()
                row[name] = True if c in "TY" else False if c in "FN" else None
            else:
                try:
                    row[name] = cell.decode(used).rstrip("\x00 ").strip()
                except UnicodeDecodeError:
                    row[name] = cell.decode("latin-1").strip()
        rows.append(row)
    return names, rows, used


def _parts_to_geometry(t: int, parts, swap: bool, fs: FeatureSet) -> Optional[Geometry]:
    base = t % 10 if t >= 10 else t

    def v(p):
        x, y, z = p
        if fs.crs.is_geographic:
            vv = Vertex(lat=y, lon=x)
        else:
            vv = Vertex(x=y, y=x) if swap else Vertex(x=x, y=y)
        if z is not None and fs.height.datum != "none":
            vv.h = z + (fs.source.offset_to_TP or 0.0)
        return vv

    if base == 1:
        return Geometry("point", v(parts[0][0]))
    if base == 8:
        pts = [v(p) for p in parts[0]]
        return Geometry("point", pts[0]) if len(pts) == 1 else Geometry("multipoint", pts)
    if base == 3:
        lines = [[v(p) for p in part] for part in parts if len(part) >= 2]
        if not lines:
            return None
        return Geometry("line", lines[0]) if len(lines) == 1 else Geometry("multiline", lines)
    if base == 5:
        polys: List[Polygon] = []
        for part in parts:
            ring = [(p[0], p[1]) for p in part]
            if len(ring) >= 2 and ring[0] == ring[-1]:
                part = part[:-1]
                ring = ring[:-1]
            if len(part) < 3:
                continue
            vs = [v(p) for p in part]
            if _ring_area2(ring) < 0 or not polys:    # 時計回り＝外周（最初の輪は向きに関わらず外周）
                polys.append(Polygon(vs))
            else:
                polys[-1].holes.append(vs)
        if not polys:
            return None
        return Geometry("polygon", polys[0]) if len(polys) == 1 else Geometry("multipolygon", polys)
    return None


# ---------- 読み ----------
def _collect(path: str) -> List[dict]:
    """ZIP か .shp のパスから、{name, shp, shx, dbf, prj, cpg} の組を集める。"""
    sets = {}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                base = os.path.basename(n)
                if base.startswith("._") or "__MACOSX" in n or not base:
                    continue
                stem, ext = os.path.splitext(base)
                ext = ext.lower()
                if ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
                    sets.setdefault(stem, {"name": stem})[ext[1:]] = z.read(n)
    else:
        stem, ext = os.path.splitext(path)
        for e in ("shp", "shx", "dbf", "prj", "cpg"):
            p = stem + "." + e
            if os.path.exists(p):
                sets.setdefault(os.path.basename(stem), {"name": os.path.basename(stem)})[e] = open(p, "rb").read()
    return [s for s in sets.values() if "shp" in s]


def read_shapefile(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    groups = _collect(path)
    if not groups:
        raise ValueError("shapefile: .shp が見つからない（ZIP の中か、同名の .shp）")
    held = {}
    g0 = groups[0]
    prj_crs = crs_from_wkt(g0["prj"].decode("utf-8", errors="replace")) if "prj" in g0 else None
    if prj_crs:
        held["crs"] = {"datum": prj_crs.datum, "system": prj_crs.system, "zone": prj_crs.zone, "epsg": prj_crs.epsg}
    if "cpg" in g0:
        cpg = g0["cpg"].decode("ascii", errors="ignore").strip().upper().replace("-", "_")
        held["encoding"] = {"UTF_8": "UTF-8", "UTF8": "UTF-8", "SHIFT_JIS": "Shift_JIS", "SJIS": "Shift_JIS",
                            "CP932": "Shift_JIS", "932": "Shift_JIS"}.get(cpg, cpg)
    try:
        fs = build_metadata("shapefile", path, held, sidecar, params, required=("crs",))
    except MissingInfo:
        raise MissingInfo("shapefile: .prj が無い（または読めない）ので座標参照系が分からない。補足ファイルか params で指定してください（第4巻 3 章）")
    if prj_crs:
        fs.log.append(f".prj: {prj_crs.label()}")
    if len(groups) > 1:
        fs.log.append(f"ZIP に .shp が {len(groups)} 個: {', '.join(g['name'] for g in groups)}（全部読む。layer=名前）")
    swap = not fs.crs.is_geographic
    fs.source.axis_order = "lon,lat" if fs.crs.is_geographic else "east,north"
    fs.source.axis_unit = "deg" if fs.crs.is_geographic else "m"
    all_fields: List[str] = []
    n = 0
    for g in groups:
        shape_type, recs = _read_shp(g["shp"])
        enc_in = {"UTF-8": "utf-8", "Shift_JIS": "cp932", "UTF-8-BOM": "utf-8-sig"}.get(fs.source.encoding or "", fs.source.encoding)
        names, rows, used = _read_dbf(g["dbf"], enc_in, fs.log) if "dbf" in g else ([], [], None)
        if used and not fs.source.encoding:
            fs.source.encoding = {"cp932": "Shift_JIS", "utf-8": "UTF-8"}.get(used, used)
        for nm in names:
            if nm not in all_fields:
                all_fields.append(nm)
        if shape_type == 31:
            fs.log.append(f"{g['name']}: MultiPatch（31）は対象外 → 読み飛ばし")
        for i, (t, parts) in enumerate(recs):
            n += 1
            attrs = rows[i] if i < len(rows) else {}
            if parts is None or t == 0:
                fs.skipped += 1
                continue
            geom = _parts_to_geometry(t, parts, swap, fs)
            if geom is None:
                fs.skipped += 1
                continue
            fs.features.append(Feature(id=str(n), name=name_from(attrs, *NAME_KEYS), geometry=geom,
                                       attributes=attrs, layer=g["name"] if len(groups) > 1 else None))
    fs.fields = all_fields
    return fs


# ---------- 書き ----------
def _dbf_fields(fs: FeatureSet, feats: List[Feature], encoding: str):
    """列定義 [(name10bytes, type, length, decimals, key)]。"""
    keys = list(fs.fields)
    for f in feats:
        for k in f.attributes:
            if k not in keys:
                keys.append(k)
    if "name" not in [k.lower() for k in keys]:
        keys.insert(0, "name")
    defs = []
    used = set()
    for k in keys:
        raw = k.encode(encoding, errors="replace")
        while len(raw) > 10:
            k2 = k[:-1]
            raw = k2.encode(encoding, errors="replace")
            k = k2
        base = raw
        i = 2
        while raw.upper() in used:
            suf = str(i).encode()
            raw = base[:10 - len(suf)] + suf
            i += 1
        used.add(raw.upper())
        vals = [f.attributes.get(k) if k != "name" or "name" in f.attributes else f.name for f in feats]
        vals = [v for v in vals if v is not None and v != ""]
        if vals and all(isinstance(v, bool) for v in vals):
            defs.append((raw, "L", 1, 0, k))
        elif vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            dec = 0 if all(isinstance(v, int) for v in vals) else max(min(len(repr(float(v)).split(".")[1]), 10) for v in vals)
            width = max(len(f"{v:.{dec}f}") for v in vals) if dec else max(len(str(v)) for v in vals)
            defs.append((raw, "N", min(max(width, 1), 20), dec, k))
        else:
            width = max([len(str(v).encode(encoding, errors="replace")) for v in vals] + [1])
            defs.append((raw, "C", min(width, 254), 0, k))
    return defs


def _write_dbf(fs: FeatureSet, feats: List[Feature], encoding: str, ldid: int) -> bytes:
    defs = _dbf_fields(fs, feats, encoding)
    rlen = 1 + sum(d[2] for d in defs)
    hlen = 32 + 32 * len(defs) + 1
    out = io.BytesIO()
    today = datetime.date.today()
    out.write(struct.pack("<BBBBihh", 0x03, today.year - 1900, today.month, today.day, len(feats), hlen, rlen))
    out.write(b"\x00" * 17 + bytes([ldid]) + b"\x00\x00")
    for raw, t, ln, dec, _ in defs:
        out.write(raw.ljust(11, b"\x00") + t.encode() + b"\x00" * 4 + bytes([ln, dec]) + b"\x00" * 14)
    out.write(b"\x0D")
    for f in feats:
        out.write(b" ")
        for raw, t, ln, dec, k in defs:
            v = f.name if (k == "name" and "name" not in f.attributes) else f.attributes.get(k)
            if t == "N":
                s = "" if v is None or v == "" else (f"{v:.{dec}f}" if dec else str(int(v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v))
                cell = s.encode("ascii", errors="replace")[:ln].rjust(ln)
            elif t == "L":
                cell = (b"T" if v is True else b"F" if v is False else b"?")
            else:
                s = "" if v is None else str(v)
                b = s.encode(encoding, errors="replace")
                while len(b) > ln:
                    s = s[:-1]
                    b = s.encode(encoding, errors="replace")
                cell = b.ljust(ln)
            out.write(cell)
    out.write(b"\x1A")
    return out.getvalue()


def _shape_records(fs: FeatureSet, feats: List[Feature], kind: str, use_h: bool):
    """地物 → (shape_type, [record bytes], bbox)。kind: point/line/polygon。"""
    geo = fs.crs.is_geographic

    def xy(v: Vertex):
        return (v.lon, v.lat) if geo else (v.y, v.x)       # (東, 北)

    def z(v: Vertex):
        return v.h if v.h is not None else 0.0

    base = {"point": 1, "line": 3, "polygon": 5}[kind]
    stype = base + 10 if use_h else base
    recs = []
    bb = [float("inf"), float("inf"), float("-inf"), float("-inf")]
    zb = [float("inf"), float("-inf")]

    def upd(pts):
        for x, y, zz in pts:
            bb[0] = min(bb[0], x); bb[1] = min(bb[1], y); bb[2] = max(bb[2], x); bb[3] = max(bb[3], y)
            zb[0] = min(zb[0], zz); zb[1] = max(zb[1], zz)

    for f in feats:
        g = f.geometry
        if kind == "point":
            vs = g.vertices()
            if g.kind == "point":
                x, y = xy(vs[0]); zz = z(vs[0])
                upd([(x, y, zz)])
                body = struct.pack("<idd", stype, x, y) + (struct.pack("<dd", zz, 0.0) if use_h else b"")
            else:                                   # multipoint → 8/18
                st = 18 if use_h else 8
                pts = [(*xy(v), z(v)) for v in vs]
                upd(pts)
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                body = struct.pack("<idddd", st, min(xs), min(ys), max(xs), max(ys)) + struct.pack("<i", len(pts))
                body += b"".join(struct.pack("<dd", p[0], p[1]) for p in pts)
                if use_h:
                    zs = [p[2] for p in pts]
                    body += struct.pack("<dd", min(zs), max(zs)) + b"".join(struct.pack("<d", v) for v in zs)
                    body += struct.pack("<dd", 0.0, 0.0) + b"".join(struct.pack("<d", 0.0) for _ in zs)
            recs.append(body)
            continue
        if kind == "line":
            parts = [g.coords] if g.kind == "line" else list(g.coords)
            parts = [[(*xy(v), z(v)) for v in p] for p in parts]
        else:
            polys = [g.coords] if g.kind == "polygon" else list(g.coords)
            parts = []
            for p in polys:
                outer = [(*xy(v), z(v)) for v in p.outer]
                if _ring_area2([(a, b) for a, b, _ in outer]) > 0:
                    outer = outer[::-1]             # 外周は時計回り
                parts.append(outer + [outer[0]])
                for h in p.holes:
                    ring = [(*xy(v), z(v)) for v in h]
                    if _ring_area2([(a, b) for a, b, _ in ring]) < 0:
                        ring = ring[::-1]           # 穴は反時計回り
                    parts.append(ring + [ring[0]])
        pts = [q for p in parts for q in p]
        upd(pts)
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        body = struct.pack("<idddd", stype, min(xs), min(ys), max(xs), max(ys)) + struct.pack("<ii", len(parts), len(pts))
        idx = 0
        for p in parts:
            body += struct.pack("<i", idx); idx += len(p)
        body += b"".join(struct.pack("<dd", p[0], p[1]) for p in pts)
        if use_h:
            zs = [p[2] for p in pts]
            body += struct.pack("<dd", min(zs), max(zs)) + b"".join(struct.pack("<d", v) for v in zs)
            body += struct.pack("<dd", 0.0, 0.0) + b"".join(struct.pack("<d", 0.0) for _ in zs)
        recs.append(body)
    if not recs:
        bb = [0, 0, 0, 0]; zb = [0, 0]
    return stype, recs, bb, zb


def _pack_shp_shx(stype: int, recs: List[bytes], bb, zb):
    shp = io.BytesIO(); shx = io.BytesIO()
    body_len = sum(8 + len(r) for r in recs)
    def header(total_bytes):
        return (struct.pack(">i", 9994) + b"\x00" * 20 + struct.pack(">i", total_bytes // 2)
                + struct.pack("<ii", 1000, stype) + struct.pack("<dddddddd", bb[0], bb[1], bb[2], bb[3], zb[0], zb[1], 0.0, 0.0))
    shp.write(header(100 + body_len))
    shx.write(header(100 + 8 * len(recs)))
    off = 100
    for i, r in enumerate(recs):
        shp.write(struct.pack(">ii", i + 1, len(r) // 2) + r)
        shx.write(struct.pack(">ii", off // 2, len(r) // 2))
        off += 8 + len(r)
    return shp.getvalue(), shx.getvalue()


def write_shapefile(fs: FeatureSet, path, encoding: str = "UTF-8", name: Optional[str] = None) -> dict:
    """ZIP（.shp/.shx/.dbf/.prj/.cpg）に書く。種類が混ざれば _point/_line/_polygon に分ける。"""
    if fs.crs.system == "local":
        raise ValueError("shapefile: 任意座標（local）は .prj を書けない。先に公共座標へ位置合わせしてください（第4巻 10・11 章）")
    enc = "cp932" if encoding.upper().replace("-", "_") in ("SHIFT_JIS", "SJIS", "CP932") else "utf-8"
    cpg = "SHIFT_JIS" if enc == "cp932" else "UTF-8"
    ldid = 0x13 if enc == "cp932" else 0x00
    stem = name or os.path.splitext(os.path.basename(path))[0]
    if stem.lower().endswith(".zip"):
        stem = stem[:-4]
    groups = {"point": [], "line": [], "polygon": []}
    for f in fs.features:
        if f.geometry is None:
            continue
        k = f.geometry.kind
        groups["point" if k in ("point", "multipoint") else "line" if k in ("line", "multiline") else "polygon"].append(f)
    present = [k for k, v in groups.items() if v]
    if not present:
        raise ValueError("shapefile: 書き出せる地物が無い")
    use_h = fs.height.datum != "none" and any(v.h is not None for f in fs.features if f.geometry for v in f.geometry.vertices())
    prj = wkt_for(fs.crs)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for kind in present:
            feats = groups[kind]
            nm = stem if len(present) == 1 else f"{stem}_{kind}"
            stype, recs, bb, zb = _shape_records(fs, feats, kind, use_h)
            shp, shx = _pack_shp_shx(stype, recs, bb, zb)
            z.writestr(nm + ".shp", shp)
            z.writestr(nm + ".shx", shx)
            z.writestr(nm + ".dbf", _write_dbf(fs, feats, enc, ldid))
            z.writestr(nm + ".prj", prj)
            z.writestr(nm + ".cpg", cpg)
    if len(present) > 1:
        fs.log.append(f"shapefile: 種類が混ざるので {', '.join(stem + '_' + k for k in present)} に分けた")
    return for_output(fs, "shapefile", encoding=cpg)
