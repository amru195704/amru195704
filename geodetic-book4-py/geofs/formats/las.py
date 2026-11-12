# -*- coding: utf-8 -*-
"""LAS（非圧縮点群・第4巻 11 章）⇄ GeoFeatureSet。v2 段階 C-2。LAZ は対象外。

読み: LAS 1.2〜1.4、点レコード形式 0〜10（X/Y/Z は先頭 12 バイト共通）。VLR 2112（OGC WKT）か 34735（GeoKey）→ crs。
      点は 1 点＝1 地物（上限 params["limit"]・既定 100 万）。属性: intensity・classification・return。
書き: LAS 1.4・点レコード形式 6（30 バイト）、VLR 2112 に WKT。座標は 1 mm 刻み（scale 0.001）。
座標の順: LAS は X=東・Y=北。中間の x(北)/y(東) と入れ替える。
"""
from __future__ import annotations
import struct
from typing import Optional
from ..model import Vertex, Geometry, Feature, FeatureSet
from ..sidecar import for_output
from ..wkt import crs_from_wkt, wkt_for, crs_from_epsg
from ._common import build_metadata, MissingInfo


def read_las(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    params = dict(params or {})
    limit = int(params.get("limit", 1_000_000))
    with open(path, "rb") as fp:
        hdr = fp.read(375)
        if hdr[:4] != b"LASF":
            raise ValueError("las: 署名が LASF ではない（LAZ は対象外）")
        vmaj, vmin = hdr[24], hdr[25]
        hsize = struct.unpack("<H", hdr[94:96])[0]
        off = struct.unpack("<I", hdr[96:100])[0]
        nvlr = struct.unpack("<I", hdr[100:104])[0]
        pfmt = hdr[104] & 0x3F
        plen = struct.unpack("<H", hdr[105:107])[0]
        npts = struct.unpack("<I", hdr[107:111])[0]
        sx, sy, sz, ox, oy, oz = struct.unpack("<6d", hdr[131:179])
        if vmin >= 4 and hsize >= 375:
            n64 = struct.unpack("<Q", hdr[247:255])[0]
            if n64:
                npts = n64
        # VLR
        fp.seek(hsize)
        wkt, geokeys = "", None
        for _ in range(nvlr):
            v = fp.read(54)
            if len(v) < 54:
                break
            uid = v[2:18].rstrip(b"\x00").decode("ascii", "replace")
            rid, ln = struct.unpack("<HH", v[18:22])
            body = fp.read(ln)
            if rid == 2112:
                wkt = body.rstrip(b"\x00").decode("utf-8", "replace")
            elif rid == 34735 and uid == "LASF_Projection":
                geokeys = list(struct.unpack("<" + "H" * (len(body) // 2), body[:len(body) // 2 * 2]))
        held = {}
        crs = crs_from_wkt(wkt) if wkt else None
        if crs is None and geokeys and len(geokeys) >= 4:
            for i in range(geokeys[3]):
                k, loc, cnt, val = geokeys[4 + 4 * i: 8 + 4 * i]
                if k in (2048, 3072) and loc == 0 and val not in (0, 32767):
                    crs = crs_from_epsg(val)
        if crs:
            held["crs"] = {"datum": crs.datum, "system": crs.system, "zone": crs.zone, "epsg": crs.epsg}
        try:
            fs = build_metadata("las", path, held, sidecar, params, required=("crs",))
        except MissingInfo:
            raise MissingInfo("las: VLR に座標参照系（WKT／GeoKey）が無い。補足ファイルか params で指定してください（第4巻 11 章）")
        if fs.height.datum == "none" and "height" not in (sidecar or {}) and "height" not in params:
            fs.height.datum = "ellipsoidal" if fs.crs.is_geographic else "TP"
            fs.log.append(f"Z の基準は宣言が無いので {fs.height.datum} とみなした（補足ファイルで上書き可）")
        geo = fs.crs.is_geographic
        fs.log.append(f"LAS {vmaj}.{vmin} 形式 {pfmt} 点 {npts}" + (f" WKT あり" if wkt else "") + (f" GeoKey あり" if geokeys else ""))
        native = "lon,lat" if geo else "east,north"
        decl = (fs.source.axis_order or "").replace(" ", "")
        x_is_north = decl in ("north,east", "lat,lon")       # 区分 B: 補足ファイルが既定と逆なら優先
        if x_is_north:
            fs.log.append(f"las: 補足ファイルの軸 {decl} を既定 {native} より優先した（区分 B。X に北を入れた点群）")
        fs.source.axis_order = decl if x_is_north else native
        fp.seek(off)
        n = min(npts, limit)
        has_int = plen >= 14
        cls_off = 15 if pfmt >= 6 else 15
        for i in range(n):
            rec = fp.read(plen)
            if len(rec) < 12:
                break
            X, Y, Z = struct.unpack("<iii", rec[:12])
            x, y, z = X * sx + ox, Y * sy + oy, Z * sz + oz
            if x_is_north:
                v = Vertex(lat=x, lon=y, h=z) if geo else Vertex(x=x, y=y, h=z)
            else:
                v = Vertex(lat=y, lon=x, h=z) if geo else Vertex(x=y, y=x, h=z)
            attrs = {}
            if has_int:
                attrs["intensity"] = struct.unpack("<H", rec[12:14])[0]
            if pfmt >= 6 and len(rec) >= 16:
                attrs["classification"] = rec[16] if len(rec) > 16 else None
                attrs["return"] = rec[14] & 0x0F
            elif len(rec) >= 16:
                attrs["classification"] = rec[15] & 0x1F
                attrs["return"] = rec[14] & 0x07
            fs.features.append(Feature(id=str(i + 1), name=str(i + 1), geometry=Geometry("point", v), attributes=attrs))
        if npts > limit:
            fs.log.append(f"点が {npts} あるので先頭 {limit} 点だけ読んだ（params['limit']）")
            fs.skipped += npts - limit
    fs.fields = ["intensity", "classification", "return"]
    return fs


def write_las(fs: FeatureSet, path, scale: float = 0.001) -> dict:
    """LAS 1.4・点レコード形式 6・VLR 2112（WKT）。全頂点を点として書く。"""
    if fs.crs.system == "local":
        raise ValueError("las: 任意座標は WKT を書けない")
    geo = fs.crs.is_geographic
    pts = [v for f in fs.features if f.geometry for v in f.geometry.vertices()]
    if not pts:
        raise ValueError("las: 点が無い")

    def XYZ(v: Vertex):
        return ((v.lon, v.lat) if geo else (v.y, v.x)) + (v.h or 0.0,)
    xyz = [XYZ(v) for v in pts]
    mins = [min(p[i] for p in xyz) for i in range(3)]
    maxs = [max(p[i] for p in xyz) for i in range(3)]
    # 原点は範囲の中央、縮尺は全点が符号付き 32 ビットに収まる最小の 10 の冪
    offs = [round((lo + hi) / 2) for lo, hi in zip(mins, maxs)]

    def fit(lo, hi, off, base):
        s = base
        while max(abs(hi - off), abs(lo - off)) / s > 2_000_000_000:
            s *= 10
        return s
    sc = tuple(fit(mins[i], maxs[i], offs[i], (1e-9 if geo and i < 2 else scale)) for i in range(3))
    wkt = wkt_for(fs.crs).encode("utf-8") + b"\x00"
    vlr = struct.pack("<H", 0) + b"LASF_Projection".ljust(16, b"\x00") + struct.pack("<HH", 2112, len(wkt)) + b"OGC WKT".ljust(32, b"\x00") + wkt
    hsize = 375
    off = hsize + len(vlr)
    plen = 30
    n = len(pts)
    hdr = bytearray(hsize)
    hdr[0:4] = b"LASF"
    hdr[24], hdr[25] = 1, 4
    hdr[26:58] = b"GeoFeatureSet".ljust(32, b"\x00")
    hdr[58:90] = b"geofs".ljust(32, b"\x00")
    struct.pack_into("<HH", hdr, 90, 1, 2026)
    struct.pack_into("<H", hdr, 94, hsize)
    struct.pack_into("<I", hdr, 96, off)
    struct.pack_into("<I", hdr, 100, 1)
    hdr[104] = 6
    struct.pack_into("<H", hdr, 105, plen)
    struct.pack_into("<I", hdr, 107, 0)                       # legacy count は 0（1.4・形式 6）
    struct.pack_into("<6d", hdr, 131, sc[0], sc[1], sc[2], offs[0], offs[1], offs[2])
    struct.pack_into("<6d", hdr, 179, maxs[0], mins[0], maxs[1], mins[1], maxs[2], mins[2])
    struct.pack_into("<Q", hdr, 247, n)
    struct.pack_into("<H", hdr, 6, 0x10)                      # global encoding: WKT
    with open(path, "wb") as fp:
        fp.write(hdr); fp.write(vlr)
        for x, y, z in xyz:
            rec = struct.pack("<iii", round((x - offs[0]) / sc[0]), round((y - offs[1]) / sc[1]), round((z - offs[2]) / sc[2]))
            rec += struct.pack("<H", 0) + bytes([0x11, 0, 1, 0]) + struct.pack("<h", 0) + struct.pack("<H", 0) + struct.pack("<d", 0.0)
            fp.write(rec)
    fs.log.append(f"las: {n} 点を LAS 1.4 形式 6 で書いた（WKT VLR）")
    return for_output(fs, "las")
