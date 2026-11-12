# -*- coding: utf-8 -*-
"""中間フォーマット GeoFeatureSet のモデル（仕様書 §1）。

原則: Reader／Writer は座標を動かさない。頂点は crs.system に応じて
緯度経度（10 進度）か投影座標（X=北・Y=東・m）の「どちらか一方だけ」を持つ。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

GEOMETRY_KINDS = ("point", "multipoint", "line", "multiline", "polygon", "multipolygon")
DATUMS = ("Tokyo", "JGD2000", "JGD2011", "JGD2024", "WGS84")
SYSTEMS = ("geographic", "plane_rectangular", "utm", "local")
HEIGHT_DATUMS = ("ellipsoidal", "TP", "none")


@dataclass
class Vertex:
    lat: Optional[float] = None   # 10 進度（geographic のとき）
    lon: Optional[float] = None
    x: Optional[float] = None     # 北（m）（投影のとき。UTM も northing を x に）
    y: Optional[float] = None     # 東（m）
    h: Optional[float] = None     # 高さ（意味は FeatureSet.height.datum）
    ref: Optional[str] = None     # 同じ集合内の点地物 id への参照（SIMA の構成点）

    def copy(self) -> "Vertex":
        return Vertex(self.lat, self.lon, self.x, self.y, self.h, self.ref)

    @property
    def is_geographic(self) -> bool:
        return self.lat is not None and self.lon is not None


@dataclass
class Polygon:
    outer: List[Vertex]
    holes: List[List[Vertex]] = field(default_factory=list)


@dataclass
class Geometry:
    kind: str          # GEOMETRY_KINDS のいずれか
    coords: Any        # point: Vertex / multipoint,line: [Vertex] / multiline: [[Vertex]]
                       # polygon: Polygon / multipolygon: [Polygon]

    def vertices(self) -> List[Vertex]:
        """全頂点を平らに並べる（穴も含む）。"""
        k, c = self.kind, self.coords
        if k == "point":
            return [c]
        if k in ("multipoint", "line"):
            return list(c)
        if k == "multiline":
            return [v for line in c for v in line]
        if k == "polygon":
            return list(c.outer) + [v for ring in c.holes for v in ring]
        if k == "multipolygon":
            return [v for p in c for v in [*p.outer, *[w for r in p.holes for w in r]]]
        raise ValueError(f"unknown geometry kind: {k}")

    def map(self, fn) -> "Geometry":
        """各頂点に fn(Vertex)->Vertex を適用した新しい Geometry（構造は同じ）。"""
        k, c = self.kind, self.coords
        if k == "point":
            return Geometry(k, fn(c))
        if k in ("multipoint", "line"):
            return Geometry(k, [fn(v) for v in c])
        if k == "multiline":
            return Geometry(k, [[fn(v) for v in line] for line in c])
        if k == "polygon":
            return Geometry(k, Polygon([fn(v) for v in c.outer],
                                       [[fn(v) for v in r] for r in c.holes]))
        if k == "multipolygon":
            return Geometry(k, [Polygon([fn(v) for v in p.outer],
                                        [[fn(v) for v in r] for r in p.holes]) for p in c])
        raise ValueError(f"unknown geometry kind: {k}")

    @property
    def kind_name(self) -> str:
        return {"point": "点", "multipoint": "複数点", "line": "線", "multiline": "複数線",
                "polygon": "面", "multipolygon": "複数面"}[self.kind]


@dataclass
class Feature:
    id: str
    name: str = ""
    geometry: Optional[Geometry] = None
    attributes: Dict[str, Any] = field(default_factory=dict)   # 値は str/int/float/bool/None
    layer: Optional[str] = None


@dataclass
class CRS:
    datum: str                      # Tokyo / JGD2000 / JGD2011 / JGD2024 / WGS84
    system: str                     # geographic / plane_rectangular / utm / local
    zone: Optional[int] = None      # 1〜19 / 51〜56
    epsg: Optional[int] = None

    @property
    def is_geographic(self) -> bool:
        return self.system == "geographic"

    def label(self) -> str:
        if self.system == "geographic":
            return f"{self.datum} 緯度経度"
        if self.system == "plane_rectangular":
            return f"{self.datum} 平面直角第{self.zone}系"
        if self.system == "utm":
            return f"{self.datum} UTM{self.zone}"
        return f"{self.datum} 任意座標"


@dataclass
class Height:
    datum: str = "none"             # ellipsoidal / TP / none
    geoid: Optional[str] = None     # 2011 / 2024


@dataclass
class Epoch:
    geodetic_results: Optional[str] = None   # 2000 / 2011 / 2024
    survey_date: Optional[str] = None        # YYYY-MM-DD
    height_rev: Optional[str] = None         # before_2025-04 / after_2025-04


@dataclass
class Source:
    """元ファイルの事情（往復・ログ用。変換の入力にはしない）。"""
    format: str = ""
    file: str = ""
    encoding: Optional[str] = None
    axis_order: Optional[str] = None         # north,east / east,north / lat,lon / lon,lat
    axis_unit: Optional[str] = None          # m / deg
    axis_format: Optional[str] = None        # dd / dms / ddmm
    height_column: Optional[str] = None
    height_datum_original: Optional[str] = None   # AP・OP… を TP に直したときの元の基準
    offset_to_TP: Optional[float] = None


@dataclass
class FeatureSet:
    crs: CRS
    height: Height = field(default_factory=Height)
    epoch: Epoch = field(default_factory=Epoch)
    features: List[Feature] = field(default_factory=list)
    fields: List[str] = field(default_factory=list)   # 属性の列順
    source: Source = field(default_factory=Source)
    known_points: List[dict] = field(default_factory=list)
    skipped: int = 0
    log: List[str] = field(default_factory=list)
    note: Optional[str] = None

    # --- 便利関数 ---
    def summary(self) -> str:
        n = {"点": 0, "線": 0, "面": 0}
        verts = 0
        for f in self.features:
            if f.geometry is None:
                continue
            k = f.geometry.kind
            n["点" if k in ("point", "multipoint") else "線" if k in ("line", "multiline") else "面"] += 1
            verts += len(f.geometry.vertices())
        return f"点 {n['点']}・線 {n['線']}・面 {n['面']}（頂点 {verts}）・{self.crs.label()}・高さ {self.height.datum}"

    def points(self) -> List[Feature]:
        """点の地物だけ。"""
        return [f for f in self.features if f.geometry is not None and f.geometry.kind == "point"]

    def next_id(self) -> str:
        """数字の id の最大＋1。"""
        mx = 0
        for f in self.features:
            if f.id.isdigit():
                mx = max(mx, int(f.id))
        return str(mx + 1)

    def validate(self) -> List[str]:
        """仕様に合っているかの簡易検査。問題を文字列の列で返す（空なら OK）。"""
        errs = []
        if self.crs.datum not in DATUMS:
            errs.append(f"crs.datum が値域外: {self.crs.datum}")
        if self.crs.system not in SYSTEMS:
            errs.append(f"crs.system が値域外: {self.crs.system}")
        if self.crs.system == "plane_rectangular" and not (self.crs.zone and 1 <= self.crs.zone <= 19):
            errs.append("plane_rectangular には zone 1〜19 が要る")
        if self.crs.system == "utm" and not (self.crs.zone and 51 <= self.crs.zone <= 56):
            errs.append("utm には zone 51〜56 が要る")
        if self.height.datum not in HEIGHT_DATUMS:
            errs.append(f"height.datum が値域外: {self.height.datum}（特殊基準面は Reader で TP に直す）")
        ids = set()
        geo = self.crs.is_geographic
        for f in self.features:
            if f.id in ids:
                errs.append(f"id の重複: {f.id}")
            ids.add(f.id)
            if f.geometry is None:
                continue
            if f.geometry.kind not in GEOMETRY_KINDS:
                errs.append(f"{f.id}: geometry.kind が値域外: {f.geometry.kind}")
                continue
            for v in f.geometry.vertices():
                if geo and (v.lat is None or v.lon is None or v.x is not None or v.y is not None):
                    errs.append(f"{f.id}: geographic なのに lat/lon 以外を持つ頂点がある")
                    break
                if not geo and (v.x is None or v.y is None or v.lat is not None or v.lon is not None):
                    errs.append(f"{f.id}: 投影座標なのに x/y 以外を持つ頂点がある")
                    break
            if f.geometry.kind == "line" and len(f.geometry.coords) < 2:
                errs.append(f"{f.id}: 線は 2 点以上")
            if f.geometry.kind == "polygon" and len(f.geometry.coords.outer) < 3:
                errs.append(f"{f.id}: 面の外周は 3 点以上")
        return errs
