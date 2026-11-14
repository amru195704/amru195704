# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""GeoFeatureSet → GeoFeatureSet の座標変換（仕様書 §3 の convert()）。

Reader／Writer から切り離した独立の 1 段。頂点ごとに変換し、1 頂点でも失敗した地物は落として
skipped と log に残す。

できること（標準ライブラリだけ・この層で完結）:
  - 同じ測地系の中での 緯度経度 ⇄ 平面直角（1〜19 系） ⇄ UTM（51〜56）
  - Tokyo ⇄ JGD2000 の概略変換（3 パラメータ。精密には第2巻 3 章の TKY2JGD 格子）
  - 高さの基準の変更（ellipsoidal ⇄ TP は geoid(lat, lon) -> N のフックが要る。none は落とす）
フックで足すこと（第2巻の章のコードを渡す）:
  - datum_shift(lat, lon, h, from_datum, to_datum) -> (lat, lon, h)
      JGD2000 ⇄ JGD2011 ⇄ JGD2024 などパラメータファイルが要る変換（第2巻 3・6 章）
  - geoid(lat, lon) -> N（第2巻 5 章）
"""
from __future__ import annotations
import copy
from typing import Callable, Optional
from .model import CRS, Height, Epoch, Source, Vertex, Feature, FeatureSet
from . import projection as P
from .helmert2d import Helmert2D


def align(fs: FeatureSet, helmert: Helmert2D, crs: CRS) -> FeatureSet:
    """任意座標（local）の集合を、2D ヘルマートで公共座標 crs（投影座標）の集合にする（第4巻 10・11 章）。
    位置合わせの残差は helmert.residuals にあり、GeoCore の CCQ とは混ぜない。"""
    if crs.is_geographic:
        raise ValueError("位置合わせ先は投影座標（平面直角・UTM）にしてください")
    out = copy.deepcopy(fs)
    out.crs = copy.deepcopy(crs)
    out.source = Source(format="aligned", file=fs.source.file)
    for f in out.features:
        if f.geometry is None:
            continue
        def one(v: Vertex) -> Vertex:
            if v.x is None or v.y is None:
                raise ValueError("任意座標の頂点に x/y が無い")
            X, Y = helmert.apply(v.x, v.y)
            return Vertex(x=X, y=Y, h=v.h, ref=v.ref)
        f.geometry = f.geometry.map(one)
    out.log.append(f"位置合わせ（2D ヘルマート）: 縮尺 {helmert.scale:.6f}・回転 {helmert.rotation_deg:.4f}°・平行移動 ({helmert.tx:.3f}, {helmert.ty:.3f})・最大残差 {helmert.max_residual:.3f} m（対応点 {len(helmert.residuals)}）→ {crs.label()}")
    return out

_RESULTS = {"Tokyo": "2000", "JGD2000": "2000", "JGD2011": "2011", "JGD2024": "2024", "WGS84": "2024"}


def _to_geographic(v: Vertex, crs: CRS, tm):
    if crs.is_geographic:
        return v.lat, v.lon
    if crs.system == "local":
        raise ValueError("任意座標（local）は先に align()（2D ヘルマート・既知点 2 点以上）で公共座標にしてください")
    return tm.inverse(v.x, v.y)


def _tm(crs: CRS):
    if crs.system == "plane_rectangular":
        return P.plane_rectangular(crs.zone, crs.datum)
    if crs.system == "utm":
        return P.utm(crs.zone, crs.datum)
    return None


def convert(fs: FeatureSet, to: CRS, height_datum: Optional[str] = None,
            geoid: Optional[Callable[[float, float], float]] = None,
            datum_shift: Optional[Callable] = None) -> FeatureSet:
    """fs を座標参照系 to（と高さの基準 height_datum）へ変換した新しい FeatureSet を返す。"""
    src, dst = fs.crs, to
    if height_datum is None:
        height_datum = fs.height.datum
    tm_src, tm_dst = _tm(src), _tm(dst)
    out = FeatureSet(crs=copy.deepcopy(dst),
                     height=Height(height_datum, fs.height.geoid if height_datum == "TP" else None),
                     epoch=Epoch(_RESULTS.get(dst.datum), fs.epoch.survey_date, fs.epoch.height_rev),
                     fields=list(fs.fields), source=Source(format="converted", file=fs.source.file),
                     known_points=list(fs.known_points), note=fs.note, log=list(fs.log))
    out.log.append(f"変換: {src.label()}（高さ {fs.height.datum}）→ {dst.label()}（高さ {height_datum}）")
    if src.datum == "Tokyo" and dst.datum != "Tokyo" or dst.datum == "Tokyo" and src.datum != "Tokyo":
        if datum_shift is None:
            out.log.append("Tokyo の測地系変換は 3 パラメータの概略値（第2巻 2 章）。精密には TKY2JGD の格子を datum_shift で渡す")
    elif src.datum != dst.datum and datum_shift is None:
        same = {"JGD2000", "JGD2011", "JGD2024", "WGS84"}
        if src.datum in same and dst.datum in same:
            out.log.append(f"{src.datum} → {dst.datum} の測地系変換は datum_shift が無いので座標をそのまま扱った（地殻変動補正・パラメータは第2巻 3・6 章）")
        else:
            raise ValueError(f"{src.datum} → {dst.datum} の変換には datum_shift が要る")
    if fs.height.datum != height_datum and {fs.height.datum, height_datum} == {"ellipsoidal", "TP"} and geoid is None:
        raise ValueError("ellipsoidal ⇄ TP の換算には geoid(lat, lon) -> N が要る（第2巻 5 章）")

    def one(v: Vertex) -> Vertex:
        lat, lon = _to_geographic(v, src, tm_src)
        h = v.h
        if src.datum != dst.datum:
            if datum_shift is not None:
                lat, lon, h2 = datum_shift(lat, lon, h, src.datum, dst.datum)
                h = h2 if h is not None else None
            elif src.datum == "Tokyo":
                lat, lon, h2 = P.tokyo_shift(lat, lon, h or 0.0, True)
                h = h2 if h is not None else None
            elif dst.datum == "Tokyo":
                lat, lon, h2 = P.tokyo_shift(lat, lon, h or 0.0, False)
                h = h2 if h is not None else None
        # 高さの基準
        if height_datum == "none":
            h = None
        elif h is not None and fs.height.datum != height_datum:
            if fs.height.datum == "ellipsoidal" and height_datum == "TP":
                h = h - geoid(lat, lon)
            elif fs.height.datum == "TP" and height_datum == "ellipsoidal":
                h = h + geoid(lat, lon)
            elif fs.height.datum == "none":
                h = None
        if dst.is_geographic:
            return Vertex(lat=lat, lon=lon, h=h, ref=v.ref)
        if dst.system == "local":
            raise ValueError("任意座標への変換は未実装")
        x, y = tm_dst.forward(lat, lon)
        return Vertex(x=x, y=y, h=h, ref=v.ref)

    for f in fs.features:
        if f.geometry is None:
            out.features.append(copy.deepcopy(f))
            continue
        try:
            g = f.geometry.map(one)
        except (ValueError, ZeroDivisionError, OverflowError, KeyError) as e:
            out.skipped += 1
            out.log.append(f"{f.id} {f.name}: 変換できない（{e}）→ 落とした")
            continue
        out.features.append(Feature(f.id, f.name, g, dict(f.attributes), f.layer))
    return out
