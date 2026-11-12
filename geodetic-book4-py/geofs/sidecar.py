# -*- coding: utf-8 -*-
"""補足ファイル `.acrs`（第4巻 付録 7-1）の読み書き。

- 項目名は英語・日本語のどちらでも読める（読み込みで英語に正規化）。
- 同じ階層に英語名と日本語名の両方があれば英語名を採り、日本語名は無視して警告
  （GCVP v2 と同じ規則）。
- 書き出しは英語名のみ。
- for_output(): 出力形式が自分で持っていない項目だけに絞る。
"""
from __future__ import annotations
import json
import os
from typing import Optional, List, Tuple
from .model import FeatureSet

SUFFIX = ".acrs"

JA2EN = {
    "ファイル": "file", "座標参照系": "crs", "測地系": "datum", "座標系": "system",
    "系番号": "zone", "EPSG": "epsg", "軸": "axis", "順序": "order", "単位": "unit",
    "表記": "format", "高さ": "height", "基準": "datum", "ジオイド": "geoid",
    "列名": "column", "TP差": "offset_to_TP", "元期": "epoch", "測地成果": "geodetic_results",
    "観測日": "survey_date", "標高成果": "height_rev", "文字コード": "encoding",
    "既知点": "known_points", "点名": "name", "緯度": "lat", "経度": "lon",
    "X": "x", "Y": "y", "公共X": "X_public", "公共Y": "Y_public", "備考": "note",
}


def normalize_keys(obj, path="", warnings: Optional[List[str]] = None):
    """日本語の項目名を英語に直す。英語名が同じ階層にあれば英語名を優先し警告。"""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():            # まず英語名
            if k not in JA2EN:
                out[k] = normalize_keys(v, f"{path}{k}.", warnings)
        for k, v in obj.items():            # 次に日本語名（英語名が無いときだけ）
            if k in JA2EN:
                en = JA2EN[k]
                if en in out:
                    if warnings is not None:
                        warnings.append(f"補足ファイルの項目名が英語・日本語で重複: {path}{en}（英語名を採用・「{k}」は無視）")
                    continue
                out[en] = normalize_keys(v, f"{path}{en}.", warnings)
        return out
    if isinstance(obj, list):
        return [normalize_keys(x, path, warnings) for x in obj]
    return obj


def sidecar_path(data_path: str) -> Optional[str]:
    """`genba.csv.acrs` → `genba.acrs` の順に探し、あるものを返す。"""
    c1 = data_path + SUFFIX
    if os.path.exists(c1):
        return c1
    base, _ = os.path.splitext(data_path)
    c2 = base + SUFFIX
    if os.path.exists(c2):
        return c2
    return None


def load_sidecar(data_or_sidecar_path: str, warnings: Optional[List[str]] = None) -> Optional[dict]:
    """データのパス（隣を探す）か補足ファイルのパスを渡す。無ければ None。"""
    p = data_or_sidecar_path
    if not p.endswith(SUFFIX):
        p = sidecar_path(p)
        if p is None:
            return None
    with open(p, "r", encoding="utf-8-sig") as f:
        raw = json.load(f)
    return normalize_keys(raw, "", warnings)


def save_sidecar(sidecar: dict, path: str) -> None:
    """書き出し（英語名）。path はデータのパスでも補足ファイルのパスでもよい。"""
    if not path.endswith(SUFFIX):
        path = path + SUFFIX
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(sidecar, f, ensure_ascii=False, indent=1)
        f.write("\n")


# 形式が自分で持つ項目（仕様書 §2・GCVP v2 CRSSidecar.forOutput と同じ）
# 補足ファイルの `axis` の扱い（第4巻 付録 7-1・8-4。調査課 2026-11-07 の調査票）。GCVP v2 の GeoFileFormat.axisPolicy と同じ表
#   A: 形式に軸の決まりが無い → 補足ファイルの axis が必須。出力の補足ファイルには実際の並びを必ず書く
#   B: 仕様で決まっているが逆の並びで作る運用がある → 補足ファイルにあれば既定より優先（警告をログに）。出力は既定の並びで書くので axis は書かない
#   C: 仕様で決まっていて逆の運用が見当たらない → 補足ファイルの axis は無視（警告をログに）。出力にも書かない
#   `.gfs.json` は内部形式で軸は固定（axis の項目を持たない）
AXIS_CLASS = {
    "csv": "A", "tsv": "A", "dxf": "A", "sxf": "A", "worldfile": "A",
    "sima": "B", "geojson": "B", "las": "B", "laz": "B", "gml": "B",
    # それ以外（kml・kmz・gpx・shapefile・gpkg・landxml・fgd・citygml・chizuxml・dm・geotiff・flatgeobuf・geoparquet …）は C
}

_FORMAT_HOLDS = {
    "csv":     set(),
    "sima":    {"axis"},                       # X=北・Y=東。文字コードは Shift_JIS のとき持つ
    "geojson": {"crs", "axis", "epoch", "encoding"},   # crs は WGS84 のときだけ「持つ」
    "kml":     {"crs", "axis", "epoch", "encoding"},
    "kmz":     {"crs", "axis", "epoch", "encoding"},
    "gpx":     {"crs", "axis", "epoch", "encoding"},
    "shapefile": {"crs", "axis", "encoding"},     # .prj・.cpg が持つ。高さ＋元期だけ付ける（7-2）
    "gpkg":    {"crs", "axis", "encoding"},
    "dxf":     {"axis", "encoding"},                # GEODATA があれば crs も（Writer が判断）
    "landxml": {"crs", "axis", "encoding"},
    "worldfile": {"axis"},
    "geotiff": {"crs", "axis"},
    "las": {"crs", "axis"},
}


def full_sidecar(fs: FeatureSet, axis_order: Optional[str] = None, height_column: Optional[str] = None,
                 encoding: Optional[str] = None, file: Optional[str] = None) -> dict:
    """FeatureSet の「ものさし」を補足ファイルの全項目に写す。"""
    d = {}
    if file:
        d["file"] = file
    crs = {"datum": fs.crs.datum, "system": fs.crs.system}
    if fs.crs.zone is not None:
        crs["zone"] = fs.crs.zone
    if fs.crs.epsg is not None:
        crs["epsg"] = fs.crs.epsg
    d["crs"] = crs
    if axis_order is None:
        axis_order = "lat,lon" if fs.crs.is_geographic else "north,east"
    d["axis"] = {"order": axis_order, "unit": "deg" if fs.crs.is_geographic else "m"}
    if fs.crs.is_geographic:
        d["axis"]["format"] = "dd"
    if fs.height.datum != "none":
        h = {"datum": fs.height.datum}
        if fs.height.geoid:
            h["geoid"] = fs.height.geoid
        if height_column:
            h["column"] = height_column
        d["height"] = h
    e = {k: v for k, v in (("geodetic_results", fs.epoch.geodetic_results),
                           ("survey_date", fs.epoch.survey_date),
                           ("height_rev", fs.epoch.height_rev)) if v}
    if e:
        d["epoch"] = e
    if encoding:
        d["encoding"] = encoding
    if fs.known_points:
        d["known_points"] = list(fs.known_points)
    if fs.note:
        d["note"] = fs.note
    return d


def for_output(fs: FeatureSet, fmt: str, **kw) -> dict:
    """出力形式が持っていない項目だけの補足ファイル（Writer の戻り値に使う）。"""
    d = full_sidecar(fs, **kw)
    holds = set(_FORMAT_HOLDS.get(fmt, set()))
    if fmt in ("geojson", "kml", "kmz", "gpx") and fs.crs.datum != "WGS84":
        holds.discard("crs")       # 「実際の測地系」を補足ファイルで補う（第4巻 6 章）
        holds.discard("epoch")
    if fmt == "sima" and (kw.get("encoding") or "Shift_JIS") == "Shift_JIS":
        holds.add("encoding")
    for k in holds:
        d.pop(k, None)
    # 軸: 区分 A だけ書く（呼び出し側が実際に書いた並びを axis_order で渡す）。B・C は書かない
    if AXIS_CLASS.get(fmt, "C") == "A":
        if kw.get("axis_order") is None:
            raise ValueError(f"for_output: 区分 A の {fmt} は実際の軸の並び（axis_order）を渡すこと")
        o = kw["axis_order"]
        geo = o.startswith("lat") or o.startswith("lon")
        d["axis"] = {"order": o, "unit": "deg" if geo else "m"}
        if geo:
            d["axis"]["format"] = "dd"
    else:
        d.pop("axis", None)
    return d
