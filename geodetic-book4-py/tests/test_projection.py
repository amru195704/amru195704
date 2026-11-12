#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""平面直角座標の検算: tests/data/gsi_plane_rectangular.csv（地理院の値・19 系 75 点）。
往復（緯度経度→XY→緯度経度）と地理院の GRS80 の XY を比べる。"""
import csv, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from geofs import projection as P

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "data", "gsi_plane_rectangular.csv")      # 配布物に同梱（地理院の換算値 19 系 75 点）
if not os.path.exists(CSV):
    sys.exit("tests/data/gsi_plane_rectangular.csv がありません")


def main():
    worst = 0.0
    worst_rt = 0.0
    n = 0
    with open(CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            zone = int(r["zone"])
            lat, lon = float(r["lat"]), float(r["lon"])
            tm = P.plane_rectangular(zone, "JGD2011")
            x, y = tm.forward(lat, lon)
            dx, dy = x - float(r["gsi_grs80_x"]), y - float(r["gsi_grs80_y"])
            d = max(abs(dx), abs(dy))
            worst = max(worst, d)
            la, lo = tm.inverse(x, y)
            rt = max(abs(la - lat), abs(lo - lon)) * 111000
            worst_rt = max(worst_rt, rt)
            n += 1
            if d > 0.0015:
                print(f"NG 第{zone}系 {r['name']}: dx={dx:+.4f} dy={dy:+.4f}")
    print(f"{n} 点: 地理院 GRS80 との最大差 {worst*1000:.2f} mm / 往復の最大差 {worst_rt*1000:.3f} mm")
    return 0 if worst <= 0.0015 else 1


if __name__ == "__main__":
    sys.exit(main())
