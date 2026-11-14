# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Y4U
"""形式ごとの Reader／Writer。どれも read_xxx(path, sidecar, params) -> FeatureSet、
write_xxx(fs, path, **options) -> dict（出力側の補足ファイル）の形。"""
from .csv_ import read_csv, write_csv
from .sima import read_sima, write_sima
from .geojson import read_geojson, write_geojson
from .kml import read_kml, write_kml, read_kmz, write_kmz
from .gpx import read_gpx, write_gpx
from .shapefile import read_shapefile, write_shapefile
from .landxml import read_landxml, write_landxml
from .dxf import read_dxf, write_dxf
from .fgd import read_fgd
from .chizuxml import read_chizuxml
from .worldfile import read_worldfile, write_worldfile
from .geotiff import read_geotiff
from .las import read_las, write_las
from .citygml import read_citygml
from .dm import read_dm

READERS = {"csv": read_csv, "sima": read_sima, "geojson": read_geojson,
           "kml": read_kml, "kmz": read_kmz, "gpx": read_gpx, "shapefile": read_shapefile, "landxml": read_landxml, "dxf": read_dxf, "fgd": read_fgd, "chizuxml": read_chizuxml, "worldfile": read_worldfile, "geotiff": read_geotiff, "las": read_las, "citygml": read_citygml, "dm": read_dm}
WRITERS = {"csv": write_csv, "sima": write_sima, "geojson": write_geojson,
           "kml": write_kml, "kmz": write_kmz, "gpx": write_gpx, "shapefile": write_shapefile, "landxml": write_landxml, "dxf": write_dxf, "worldfile": write_worldfile, "las": write_las}
