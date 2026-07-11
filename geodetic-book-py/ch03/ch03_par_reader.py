#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-1: パラメータファイル（.par）の読み込み。

ヘッダ2行を飛ばし、「メッシュコード dB dL」を dict にする。
入力は P3-0 が生成したテスト par（架空値）。まず P3-0 を実行しておくこと。

★ 読み込む値は「誇張した架空のテストデータ」です。実際の変位量ではありません。
"""
from pathlib import Path

PAR = Path(__file__).resolve().parents[1] / "testdata" / "test_tokyo.par"
HEADER_LINES = 2               # TKY2JGD形式のヘッダ行数


def read_par(path, header_lines=HEADER_LINES, encoding="utf-8"):
    """.par を {メッシュコード: (dB, dL)} で返す。"""
    table = {}
    with open(path, encoding=encoding) as f:
        for i, line in enumerate(f):
            if i < header_lines:       # ヘッダを飛ばす
                continue
            cols = line.split()
            if len(cols) < 3:
                continue
            table[cols[0]] = (float(cols[1]), float(cols[2]))
    return table


if __name__ == "__main__":
    table = read_par(PAR)
    print(f"読み込み: {len(table)} メッシュ")
    # 東京駅を含むメッシュの4隅（南西・南東・北西・北東）
    corners = [
        ("SW 53394611", "53394611"), ("SE 53394612", "53394612"),
        ("NW 53394621", "53394621"), ("NE 53394622", "53394622"),
    ]
    for label, code in corners:
        d_b, d_l = table[code]
        print(f"  {label}: Δ緯度 {d_b:.5f} 秒   Δ経度 {d_l:.5f} 秒")
