# 日本の測地系 データフォーマット編 — サンプルコード（geodetic-book4-py）

Kindle 本『日本の測地系 データフォーマット編』（シリーズ第4巻）の各章「Python で確かめる」と付録 8 で使うコードです。
第2巻のサンプル（同じリポジトリの `geodetic-book-py/`）と同じく、**標準ライブラリだけ**で動きます（Python 3.9 以上）。

## 中身

| 場所 | 内容 |
|---|---|
| `geofs/` | 中間フォーマット GeoFeatureSet と、形式ごとの Reader／Writer（付録 8） |
| `examples/` | 本文の囲みと 1 対 1 の例（`ex_<章>_<元>_to_<先>.py`） |
| `examples/data/` | 本文で使う小さな入力（`genba.csv`＋`genba.csv.acrs`、`kukaku.geojson`＋`kukaku.geojson.acrs`） |
| `tests/` | 平面直角座標の検算（国土地理院の換算値 19 系 75 点）、補足ファイル `.acrs` の軸の区分の確認 |

## 動かし方

```
cd geodetic-book4-py
python3 tests/test_projection.py        # 19 系 75 点を地理院の換算値と照合
python3 tests/test_axis.py              # 補足ファイルの軸（付録 7-1 の区分 A／B／C）
python3 examples/ex_02_csv_to_geojson.py examples/data/genba.csv /tmp/genba.geojson
python3 examples/ex_04_geojson_to_csv.py examples/data/kukaku.geojson /tmp/kukaku.csv
python3 examples/ex_13_one_point_check.py
```

`ex_05_*`（GPX・KML/KMZ）と `ex_09_sima_to_geojson.py`（SIMA）は、お手元のファイルを引数に渡して使います。

## 入っている Reader／Writer

- 読み書き: CSV・SIMA・GeoJSON・KML/KMZ・GPX・Shapefile（ZIP）・J-LandXML・DXF・ワールドファイル・LAS
- 読むだけ: 基盤地図情報 GML・地図XML・GeoTIFF（座標のみ）・PLATEAU CityGML（lod0）・DM（暫定）
- 入っていないもの: GeoPackage（6 章。本文は SQLite の標準モジュールで中を確かめる手順だけ）

## 注意

- 補足ファイル `.acrs` は本書が推奨する書式です。業界の標準規格ではなく、一般の GIS ソフトは読みません。
- 測地系をまたぐ高精度の変換（TKY2JGD・地震補正の格子）とジオイドは同梱していません。第2巻のサンプルの関数を `convert()` のフックに渡してください（付録 8-5）。渡さない場合は概略値で変換し、その旨をログに残します。
- 本書の内容とコードは執筆時点（2026 年 11 月）のものです。

## ライセンス

- コード（`geofs/`・`examples/`・`tests/` の `.py`）は **MIT ライセンス**です（`LICENSE`）。Copyright (c) 2026 Y4U。著作権表示とライセンス文を残せば、業務・商用を含めて自由に使い、変え、配れます。各 `.py` の先頭に `SPDX-License-Identifier: MIT` と著作権表示を入れてあるので、ファイル単位で持ち出しても条件が分かります。
- 同梱データ `tests/data/gsi_plane_rectangular.csv` は MIT の対象外です。出典：国土地理院「測量計算サイト」の平面直角座標への換算で求めた値（詳しくは `tests/data/README.md`）。
- 本書（Kindle 本）の本文・図はこのライセンスの対象外です。
