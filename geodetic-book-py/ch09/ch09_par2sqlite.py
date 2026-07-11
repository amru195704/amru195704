#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P9-1: パラメータファイル(.par) → SQLite DB 化。

第9章「補正DBを作る」の教材。国土地理院と同形式の .par（P3-0 が生成した
テスト par）を読み、メッシュコードを主キーにした SQLite テーブルに格納する。
格納後に4隅を引き直し、元の par と一致することを確かめる。

前提: 先に ch03/ch03_make_test_par.py（P3-0）を実行して testdata/test_tokyo.par
を作っておくこと。★ 値は誇張した架空のテストデータです。
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PAR = BASE / "testdata" / "test_tokyo.par"
DB = BASE / "testdata" / "test_tokyo.sqlite"
HEADER_LINES = 2


def read_par(path, header_lines=HEADER_LINES):
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < header_lines:
                continue
            c = line.split()
            if len(c) >= 3:
                rows.append((c[0], float(c[1]), float(c[2])))
    return rows


def build_db(rows, db_path):
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE mesh_param ("
                "code TEXT PRIMARY KEY, d_b REAL, d_l REAL)")
    con.executemany("INSERT INTO mesh_param VALUES (?,?,?)", rows)
    con.commit()
    return con


if __name__ == "__main__":
    print("=== P9-1 .par → SQLite ===")
    rows = read_par(PAR)
    con = build_db(rows, DB)
    print(f"格納: {len(rows)} メッシュ → {DB.name}")

    # 主キー検索で4隅を引き直し、par と一致するか確認
    corners = ["53394611", "53394612", "53394621", "53394622"]
    print("メッシュ主キー検索:")
    for code in corners:
        r = con.execute("SELECT d_b, d_l FROM mesh_param WHERE code=?",
                        (code,)).fetchone()
        print(f"  {code}: Δ緯度 {r[0]:.5f} 秒  Δ経度 {r[1]:.5f} 秒")

    # par の生値と突き合わせ
    src = {c: (b, l) for c, b, l in rows}
    ok = all(con.execute(
        "SELECT d_b,d_l FROM mesh_param WHERE code=?", (c,)
    ).fetchone() == src[c] for c in corners)
    print(f"par とDBの一致（4隅）: {'一致' if ok else '不一致'}")
    con.close()
