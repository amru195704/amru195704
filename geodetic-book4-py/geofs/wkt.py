# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""WKT1（.prj・GeoPackage）と EPSG と CRS の対応（第4巻 付録 3）。GCVP の CRSWKT.swift と同じ対応表。"""
from __future__ import annotations
import re
from typing import Optional
from .model import CRS
from .projection import PLANE_ORIGINS

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV",
         "XVI", "XVII", "XVIII", "XIX"]


def epsg_for(crs: CRS) -> Optional[int]:
    d, s, z = crs.datum, crs.system, crs.zone
    if s == "geographic":
        return {"WGS84": 4326, "JGD2011": 6668, "JGD2000": 4612, "Tokyo": 4301}.get(d)
    if s == "plane_rectangular" and z and 1 <= z <= 19:
        return {"JGD2011": 6668 + z, "JGD2000": 2442 + z, "Tokyo": 30160 + z}.get(d)
    if s == "utm" and z and 51 <= z <= 56:
        return {"WGS84": 32600 + z}.get(d)          # JGD2000/2011 の UTM は調査課の確認待ち
    return None


def crs_from_epsg(code: int) -> Optional[CRS]:
    if code == 4326: return CRS("WGS84", "geographic", epsg=code)
    if code == 6668: return CRS("JGD2011", "geographic", epsg=code)
    if code == 4612: return CRS("JGD2000", "geographic", epsg=code)
    if code == 4301: return CRS("Tokyo", "geographic", epsg=code)
    if 6669 <= code <= 6687: return CRS("JGD2011", "plane_rectangular", code - 6668, code)
    if 2443 <= code <= 2461: return CRS("JGD2000", "plane_rectangular", code - 2442, code)
    if 30161 <= code <= 30179: return CRS("Tokyo", "plane_rectangular", code - 30160, code)
    if 32651 <= code <= 32656: return CRS("WGS84", "utm", code - 32600, code)
    if 6688 <= code <= 6692: return CRS("JGD2011", "utm", code - 6637, code)
    if 3097 <= code <= 3101: return CRS("JGD2000", "utm", code - 3046, code)
    return None


def _fmt(v: float) -> str:
    s = f"{v:.12f}".rstrip("0").rstrip(".")
    return s if "." in s else s + ".0"


def _geogcs(datum: str) -> str:
    if datum == "WGS84":
        return 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]'
    if datum == "Tokyo":
        return 'GEOGCS["Tokyo",DATUM["Tokyo",SPHEROID["Bessel 1841",6377397.155,299.1528128,AUTHORITY["EPSG","7004"]],AUTHORITY["EPSG","6301"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4301"]]'
    name = {"JGD2000": ("JGD2000", "Japanese_Geodetic_Datum_2000", 4612, 6612),
            "JGD2011": ("JGD2011", "Japanese_Geodetic_Datum_2011", 6668, 1128),
            "JGD2024": ("JGD2024", "Japanese_Geodetic_Datum_2024", None, None)}[datum]
    auth = f',AUTHORITY["EPSG","{name[2]}"]' if name[2] else ""
    dauth = f',AUTHORITY["EPSG","{name[3]}"]' if name[3] else ""
    return (f'GEOGCS["{name[0]}",DATUM["{name[1]}",SPHEROID["GRS 1980",6378137,298.257222101,AUTHORITY["EPSG","7019"]]{dauth}],'
            f'PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]]{auth}]')


def wkt_for(crs: CRS) -> str:
    """CRS → OGC WKT1（EPSG の WKT と同じ形）。"""
    g = _geogcs(crs.datum)
    epsg = epsg_for(crs)
    auth = f',AUTHORITY["EPSG","{epsg}"]' if epsg else ""
    if crs.system == "geographic":
        return g
    if crs.system == "plane_rectangular":
        lat0, lon0 = PLANE_ORIGINS[crs.zone]
        name = f"{crs.datum} / Japan Plane Rectangular CS {ROMAN[crs.zone - 1]}"
        return (f'PROJCS["{name}",{g},PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",{_fmt(lat0)}],'
                f'PARAMETER["central_meridian",{_fmt(lon0)}],PARAMETER["scale_factor",0.9999],PARAMETER["false_easting",0],'
                f'PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["X",NORTH],AXIS["Y",EAST]{auth}]')
    if crs.system == "utm":
        name = f"{crs.datum} / UTM zone {crs.zone}N"
        return (f'PROJCS["{name}",{g},PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],'
                f'PARAMETER["central_meridian",{6 * crs.zone - 183}],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],'
                f'PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH]{auth}]')
    raise ValueError("local は WKT にできない")


def _param(key: str, wkt: str) -> Optional[float]:
    m = re.search(r'PARAMETER\["' + key + r'",\s*([-+0-9.eE]+)', wkt, re.I)
    return float(m.group(1)) if m else None


def _datum_in(wkt: str) -> Optional[str]:
    u = wkt.upper()
    if "JGD2024" in u or "JAPANESE_GEODETIC_DATUM_2024" in u: return "JGD2024"
    if "JGD2011" in u or "JAPANESE_GEODETIC_DATUM_2011" in u or "JGD_2011" in u: return "JGD2011"
    if "JGD2000" in u or "JAPANESE_GEODETIC_DATUM_2000" in u or "JGD_2000" in u: return "JGD2000"
    if "WGS_1984" in u or "WGS 84" in u or "WGS84" in u: return "WGS84"
    if "TOKYO" in u: return "Tokyo"
    return None


def crs_from_wkt(wkt: str) -> Optional[CRS]:
    """WKT1 → CRS。AUTHORITY EPSG → 名前 → 投影パラメータ の順で推定。分からなければ None。"""
    if not wkt or not wkt.strip():
        return None
    # 末尾の AUTHORITY（全体の EPSG）
    m = re.findall(r'AUTHORITY\["EPSG",\s*"?(\d+)"?\]', wkt, re.I)
    if m:
        c = crs_from_epsg(int(m[-1]))
        if c:
            return c
    datum = _datum_in(wkt)
    if datum is None:
        return None
    u = wkt.upper()
    if not u.lstrip().startswith("PROJCS"):
        return CRS(datum, "geographic", epsg=epsg_for(CRS(datum, "geographic")))
    # 名前から系番号
    m = re.search(r'PLANE[_ ]RECTANGULAR[_ ]CS[_ ]([IVX]+)', u)
    if m and m.group(1) in ROMAN:
        z = ROMAN.index(m.group(1)) + 1
        return CRS(datum, "plane_rectangular", z, epsg_for(CRS(datum, "plane_rectangular", z)))
    m = re.search(r'UTM[_ ]ZONE[_ ](\d+)', u)
    if m and 51 <= int(m.group(1)) <= 56:
        z = int(m.group(1))
        return CRS(datum, "utm", z, epsg_for(CRS(datum, "utm", z)))
    # 投影パラメータから（原点経度・緯度の組）
    cm, lat0 = _param("central_meridian", wkt), _param("latitude_of_origin", wkt)
    k = _param("scale_factor", wkt)
    if cm is not None and lat0 is not None:
        for z, (la, lo) in PLANE_ORIGINS.items():
            if abs(la - lat0) < 1e-6 and abs(lo - cm) < 1e-6:
                return CRS(datum, "plane_rectangular", z, epsg_for(CRS(datum, "plane_rectangular", z)))
        if lat0 == 0 and k and abs(k - 0.9996) < 1e-9 and (cm + 183) % 6 == 0:
            z = int((cm + 183) // 6)
            if 51 <= z <= 56:
                return CRS(datum, "utm", z, epsg_for(CRS(datum, "utm", z)))
    return None
