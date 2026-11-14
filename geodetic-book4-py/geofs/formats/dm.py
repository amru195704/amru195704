# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""DM（国土基本図図式・拡張 DM データファイル、第4巻 10 章）→ GeoFeatureSet。入力のみ・点と線。v2 段階 C-3。

【暫定】実データでの検証前の実装。公共測量標準図式の DM ファイル（固定長テキスト）のうち、
  - インデックスレコード（先頭）の 図郭左下座標（X, Y・単位は 0.1 m か m）と 測地成果／座標系の記述
  - 要素レコード（分類コード・図形区分 1=点 2=線 3=面 …）
  - 座標レコード（X Y の並び・図郭原点からの相対値）
を読み、図郭原点を足した絶対座標（X=北・Y=東）にする。世代（測地成果）は補足ファイル必須（計画書 §0）。
系番号は params／補足ファイルで与える（DM は系番号を持たない）。
"""
from __future__ import annotations
import re
from typing import Optional, List
from ..model import Vertex, Polygon, Geometry, Feature, FeatureSet
from ._common import build_metadata, MissingInfo, read_text


def read_dm(path, sidecar: Optional[dict] = None, params: Optional[dict] = None) -> FeatureSet:
    params = dict(params or {})
    try:
        fs = build_metadata("dm", path, {"axis": {"order": "north,east", "unit": "m"}}, sidecar, params, required=("crs",))
    except MissingInfo:
        raise MissingInfo("dm: DM は系番号を持たない。補足ファイルか params で座標参照系（と測地成果の世代）を指定してください（第4巻 10 章）")
    text, used = read_text(path, fs.source.encoding or "Shift_JIS", fs.log)
    fs.source.encoding = used
    lines = text.splitlines()
    if not lines:
        raise ValueError("dm: 空のファイル")
    unit = float(params.get("unit", 0.1))        # 座標値の単位（m）。拡張 DM は 0.1 m が既定
    # インデックスレコード: 先頭行。図郭左下 (X, Y) を数字の並びから推定（最初の 2 つの符号付き整数）
    head = lines[0]
    nums = re.findall(r"[-+]?\d+", head[20:]) if len(head) > 20 else re.findall(r"[-+]?\d+", head)
    ox = oy = 0.0
    if len(nums) >= 2:
        ox, oy = float(nums[0]) * unit, float(nums[1]) * unit
    fs.log.append(f"dm（暫定）: 図郭原点 X={ox} Y={oy}（単位 {unit} m・先頭レコードから推定）")
    fs.note = (fs.note or "") + "DM の読み込みは暫定実装（実データで検証前）"
    n = 0
    i = 1
    cur = None
    while i < len(lines):
        ln = lines[i].rstrip()
        i += 1
        if not ln.strip():
            continue
        # 要素レコード: 先頭が 'E'（拡張 DM）または 分類コード 4 桁＋図形区分
        m = re.match(r"^[E ]?\s*(\d{4})\s*(\d)\s*(\d+)?", ln)
        if m and not re.match(r"^\s*[-+]?\d+\s+[-+]?\d+\s*$", ln):
            if cur:
                _flush(fs, cur, n)
            n += 1
            cur = {"code": m.group(1), "kind": m.group(2), "pts": [], "id": n}
            continue
        # 座標レコード: X Y（相対値）の並び
        vals = re.findall(r"[-+]?\d+(?:\.\d+)?", ln)
        if cur and len(vals) >= 2 and len(vals) % 2 == 0:
            for k in range(0, len(vals), 2):
                cur["pts"].append(Vertex(x=ox + float(vals[k]) * unit, y=oy + float(vals[k + 1]) * unit))
    if cur:
        _flush(fs, cur, n)
    fs.fields = ["分類コード", "図形区分"]
    return fs


def _flush(fs: FeatureSet, cur: dict, n: int):
    pts: List[Vertex] = cur["pts"]
    attrs = {"分類コード": cur["code"], "図形区分": cur["kind"]}
    if cur["kind"] == "1" and pts:
        fs.features.append(Feature(id=str(cur["id"]), name=f"{cur['code']}-{cur['id']}", geometry=Geometry("point", pts[0]), attributes=attrs, layer=cur["code"]))
    elif cur["kind"] == "3" and len(pts) >= 3:
        if (pts[0].x, pts[0].y) == (pts[-1].x, pts[-1].y):
            pts = pts[:-1]
        fs.features.append(Feature(id=str(cur["id"]), name=f"{cur['code']}-{cur['id']}", geometry=Geometry("polygon", Polygon(pts)), attributes=attrs, layer=cur["code"]))
    elif len(pts) >= 2:
        fs.features.append(Feature(id=str(cur["id"]), name=f"{cur['code']}-{cur['id']}", geometry=Geometry("line", pts), attributes=attrs, layer=cur["code"]))
    else:
        fs.skipped += 1
