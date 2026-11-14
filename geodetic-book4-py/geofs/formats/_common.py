# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""Reader／Writer 共通の小道具。

優先順は「形式が持つ情報 → 補足ファイル → params」。足りない追加情報（付録 7 の Ⓐ〜Ⓕ）は
ValueError で知らせる。
"""
from __future__ import annotations
import os
import re
from typing import Optional, Tuple
from ..model import CRS, Height, Epoch, Source, FeatureSet, Vertex


# 補足ファイルの `axis` の区分（A／B／C）は sidecar.AXIS_CLASS（Writer の for_output も同じ表を使う）
from ..sidecar import AXIS_CLASS  # noqa: E402


class MissingInfo(ValueError):
    """変換に必要な追加情報が無い（どの項目かをメッセージに書く）。"""


def _get(d: Optional[dict], *keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def pick(*values):
    """最初の None でない値。"""
    for v in values:
        if v is not None:
            return v
    return None


def build_metadata(fmt: str, path: str, held: dict, sidecar: Optional[dict], params: Optional[dict],
                   required: Tuple[str, ...]) -> FeatureSet:
    """形式が持つ情報 held、補足ファイル、params を重ねて FeatureSet（地物なし）を作る。

    held / sidecar / params はどれも補足ファイルと同じ入れ子の dict（英語名）。
    required: その形式で必須の項目（"crs", "axis", "height", "encoding" …）。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    sc = sidecar or {}
    pr = params or {}
    log = []

    def g(*keys):
        return pick(_get(held, *keys), _get(sc, *keys), _get(pr, *keys))

    # 軸（付録 7-1 の区分 A／B／C）。区分 B は補足ファイル→既定、C は補足ファイルを無視、A は補足ファイル／params が必要
    axis_class = AXIS_CLASS.get(fmt, "C")
    ax_held = _get(held, "axis") or {}
    ax_decl = pick(_get(sc, "axis"), _get(pr, "axis"))
    if axis_class == "B" and ax_decl:
        axis = dict(ax_held); axis.update({k: v for k, v in ax_decl.items() if v is not None})
        if ax_held.get("order") and axis.get("order") != ax_held.get("order"):
            log.append(f"{fmt}: 補足ファイルの軸 {axis.get('order')} を既定 {ax_held.get('order')} より優先した（区分 B）")
    elif axis_class == "C":
        axis = dict(ax_held)
        if ax_decl:
            log.append(f"{fmt}: この形式では補足ファイルの軸（{ax_decl}）は無視する（区分 C。仕様で軸が決まっている）")
    else:  # A
        axis = dict(ax_decl or {})
        if "axis" in required and not axis.get("order"):
            raise MissingInfo(f"{fmt}: 軸の順序と単位（Ⓑ axis.order / axis.unit）が分からない。補足ファイルか params で指定してください")

    datum, system = g("crs", "datum"), g("crs", "system")
    if "crs" in required and (datum is None or system is None):
        raise MissingInfo(f"{fmt}: 座標参照系（Ⓐ crs.datum / crs.system）が分からない。補足ファイルか params で指定してください")
    if datum is None:
        datum, system = "WGS84", "geographic"
    zone = g("crs", "zone")
    if system in ("plane_rectangular", "utm") and zone is None:
        raise MissingInfo(f"{fmt}: {system} の系番号（crs.zone）が無い")
    crs = CRS(str(datum), str(system), int(zone) if zone is not None else None, g("crs", "epsg"))

    # 高さ: 特殊基準面は TP に直す（仕様書 §1）。
    hd = g("height", "datum")
    src = Source(format=fmt, file=os.path.basename(path),
                 encoding=g("encoding"),
                 axis_order=axis.get("order"), axis_unit=axis.get("unit"), axis_format=axis.get("format"),
                 height_column=g("height", "column"))
    height = Height()
    if hd is None:
        if "height" in required:
            raise MissingInfo(f"{fmt}: 高さの基準（Ⓒ height.datum）が分からない。ellipsoidal／TP／none を補足ファイルか params で指定してください")
        height = Height("none")
    elif hd in ("ellipsoidal", "TP", "none"):
        height = Height(hd, g("height", "geoid"))
    else:
        off = g("height", "offset_to_TP")
        if off is None:
            raise MissingInfo(f"{fmt}: 特殊基準面 {hd} の T.P. との差（height.offset_to_TP）が無い")
        height = Height("TP", g("height", "geoid"))
        src.height_datum_original = str(hd)
        src.offset_to_TP = float(off)
        log.append(f"高さの基準 {hd} を offset_to_TP={off} で T.P. に直した")
    epoch = Epoch(g("epoch", "geodetic_results"), g("epoch", "survey_date"), g("epoch", "height_rev"))
    if epoch.geodetic_results is not None:
        epoch.geodetic_results = str(epoch.geodetic_results)
    fs = FeatureSet(crs=crs, height=height, epoch=epoch, source=src,
                    known_points=list(g("known_points") or []), note=g("note"), log=log)
    return fs


def apply_height_offset(v: Vertex, fs: FeatureSet) -> Vertex:
    """Reader が特殊基準面の高さを T.P. に直すときに呼ぶ。"""
    if v.h is not None and fs.source.offset_to_TP is not None:
        v.h = v.h + fs.source.offset_to_TP
    return v


# ---- 文字コード ----
_ENC_ALIAS = {"shift_jis": "cp932", "shift-jis": "cp932", "sjis": "cp932", "cp932": "cp932",
              "utf-8": "utf-8", "utf8": "utf-8", "utf-8-bom": "utf-8-sig", "utf-8-sig": "utf-8-sig"}


def read_text(path: str, encoding: Optional[str], log: list) -> Tuple[str, str]:
    """指定の文字コード（無ければ自動判定: UTF-8 → Shift_JIS）で読む。(text, 使った名前)。"""
    data = open(path, "rb").read()
    if encoding:
        enc = _ENC_ALIAS.get(encoding.lower(), encoding)
        try:
            return data.decode(enc), encoding
        except UnicodeDecodeError:
            log.append(f"文字コード {encoding} で読めないので自動判定にした")
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "UTF-8-BOM"
    try:
        return data.decode("utf-8"), "UTF-8"
    except UnicodeDecodeError:
        return data.decode("cp932"), "Shift_JIS"


def encoding_for_write(name: Optional[str]) -> str:
    return _ENC_ALIAS.get((name or "UTF-8").lower(), name or "utf-8")


# ---- 角度の表記 ----
_DMS_RE = re.compile(r"^\s*([-+NSEWnsew]?)\s*(\d+)[°:\s]+(\d+)['′:\s]+(\d+(?:\.\d+)?)[\"″]?\s*([NSEWnsew]?)\s*$")


def parse_angle(text, fmt: Optional[str]) -> float:
    """文字列（または数値）を 10 進度にする。fmt: dd / dms / ddmm / None（自動）。"""
    if isinstance(text, (int, float)):
        val = float(text)
    else:
        s = str(text).strip()
        m = _DMS_RE.match(s)
        if m and (fmt in (None, "dms")) and ("°" in s or "'" in s or ":" in s or " " in s.strip()):
            sign = -1.0 if (m.group(1) in "-SWsw" and m.group(1)) or (m.group(5) in "SWsw" and m.group(5)) else 1.0
            return sign * (int(m.group(2)) + int(m.group(3)) / 60 + float(m.group(4)) / 3600)
        val = float(s)
    if fmt == "dms":            # DDDMMSS.ss の数値
        sign = -1 if val < 0 else 1
        val = abs(val)
        d = int(val // 10000)
        mi = int((val - d * 10000) // 100)
        sec = val - d * 10000 - mi * 100
        return sign * (d + mi / 60 + sec / 3600)
    if fmt == "ddmm":           # DDDMM.mmmm の数値（NMEA）
        sign = -1 if val < 0 else 1
        val = abs(val)
        d = int(val // 100)
        return sign * (d + (val - d * 100) / 60)
    return val


def fmt_num(v: Optional[float], digits: int) -> str:
    if v is None:
        return ""
    s = f"{v:.{digits}f}"
    return s


def name_from(attrs: dict, *keys, default="") -> str:
    for k in keys:
        if k in attrs and attrs[k] not in (None, ""):
            return str(attrs[k])
    return default
