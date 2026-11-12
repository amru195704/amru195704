# -*- coding: utf-8 -*-
"""geofs — 第4巻の Python 例の共通土台（中間フォーマット GeoFeatureSet）。

仕様: 『日本の測地系 データフォーマット編』付録 8（中間フォーマット GeoFeatureSet）
標準ライブラリだけで動く（Python 3.9+）。
"""
from .model import (Vertex, Polygon, Geometry, Feature, CRS, Height, Epoch,
                    Source, FeatureSet)
from .io_json import to_dict, from_dict, save, load
from .sidecar import load_sidecar, save_sidecar, sidecar_path, for_output
from .convert import convert, align
from .helmert2d import Helmert2D

__all__ = ["Vertex", "Polygon", "Geometry", "Feature", "CRS", "Height", "Epoch",
           "Source", "FeatureSet", "to_dict", "from_dict", "save", "load",
           "load_sidecar", "save_sidecar", "sidecar_path", "for_output", "convert", "align", "Helmert2D"]
