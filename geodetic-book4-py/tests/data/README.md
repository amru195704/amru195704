# tests/data について

## gsi_plane_rectangular.csv

出典：国土地理院「測量計算サイト」の平面直角座標への換算（`bl2xy`・`xy2bl`）で求めた値
（https://vldb.gsi.go.jp/sokuchi/surveycalc/main.html 。2026 年 11 月 2 日に取得）。

- 地点（都道府県庁所在地などの 75 点、19 系すべて）と緯度経度は著者が選んだもの。
- `gsi_bessel_x`・`gsi_bessel_y`・`gsi_grs80_x`・`gsi_grs80_y`・`gsi_inv_lat`・`gsi_inv_lon` の列が、上のサイトが返した値。
- 検算用の参照値として同梱しています。国土地理院のコンテンツ利用規約に従い、利用するときは出典を表示してください。
- このファイルは MIT ライセンスの対象外です（コードだけが MIT）。
