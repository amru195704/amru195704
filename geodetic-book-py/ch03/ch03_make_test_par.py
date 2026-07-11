#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-0: テスト用パラメータファイル（.par）生成（架空・誇張値）。

国土地理院の TKY2JGD.par と同じ体裁で、東京駅を含む親メッシュ 533946 の
3×3 = 9 メッシュ分の補正量を出力する。実データは同梱しない方針のため、
このスクリプトが後続（P3-1 読み込み・P9 SQLite化）の入力を自作する。

★ 出力値は「誇張した架空のテストデータ」です。実際の変位量ではありません。
   （東京駅メッシュ 53394611 の4隅は P3-2 の内蔵値と一致するよう設計）
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "testdata" / "test_tokyo.par"
PARENT = "533946"              # 東京駅を含む親メッシュ（p=53,u=39,q=4,v=6）


def make_value(ml, mn):
    """3次メッシュ (m3lat=ml, m3lon=mn) の架空補正量 [秒] を返す。
    隅ごとに差が見えるよう誇張。(dB=緯度補正, dL=経度補正)。"""
    d_b = 12.0 + 0.4 * (ml - 1) + 0.2 * (mn - 1) + 0.2 * (ml - 1) * (mn - 1)
    d_l = -8.0 - 0.6 * (ml - 1) - 0.2 * (mn - 1) - 0.2 * (ml - 1) * (mn - 1)
    return d_b, d_l


def main():
    lines = [
        "JGD2000-TokyoDatum Ver.TEST (架空テストデータ・実値ではない)",
        "MeshCode   dB(sec)   dL(sec)",
    ]
    for ml in range(1, 4):     # m3lat（南→北）
        for mn in range(1, 4):  # m3lon（西→東）
            code = f"{PARENT}{ml}{mn}"
            d_b, d_l = make_value(ml, mn)
            lines.append(f"{code}  {d_b:8.5f}  {d_l:8.5f}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"生成: {OUT}  （{len(lines) - 2} メッシュ・架空値）")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
