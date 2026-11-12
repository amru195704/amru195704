# -*- coding: utf-8 -*-
"""任意座標 → 公共座標の位置合わせ（2D ヘルマート・4 パラメータ）。第4巻 10・11 章。

X = a*x − b*y + tx
Y = b*x + a*y + ty       （a = s·cosθ, b = s·sinθ。縮尺 s と回転 θ、平行移動 tx, ty）
対応点 2 点以上で最小二乗。残差を点ごとに返す（納品前チェック）。
座標の並びはどちらも (x=北, y=東) で扱う（中間フォーマットと同じ）。
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Helmert2D:
    a: float
    b: float
    tx: float
    ty: float
    residuals: List[Tuple[str, float, float, float]] = field(default_factory=list)   # (name, dx, dy, 距離)

    @property
    def scale(self) -> float:
        return math.hypot(self.a, self.b)

    @property
    def rotation_deg(self) -> float:
        return math.degrees(math.atan2(self.b, self.a))

    @property
    def max_residual(self) -> float:
        return max((r[3] for r in self.residuals), default=0.0)

    def apply(self, x: float, y: float) -> Tuple[float, float]:
        return self.a * x - self.b * y + self.tx, self.b * x + self.a * y + self.ty

    def inverse(self, X: float, Y: float) -> Tuple[float, float]:
        d = self.a * self.a + self.b * self.b
        u, v = X - self.tx, Y - self.ty
        return (self.a * u + self.b * v) / d, (-self.b * u + self.a * v) / d

    @staticmethod
    def fit(pairs: List[Tuple[str, float, float, float, float]]) -> "Helmert2D":
        """pairs: (name, x, y, X, Y)。x,y＝図面（任意座標）、X,Y＝公共座標。2 点以上。"""
        if len(pairs) < 2:
            raise ValueError("対応点は 2 点以上必要")
        # 正規方程式（未知数 a, b, tx, ty）
        n = len(pairs)
        sx = sum(p[1] for p in pairs); sy = sum(p[2] for p in pairs)
        sX = sum(p[3] for p in pairs); sY = sum(p[4] for p in pairs)
        sxx = sum(p[1] ** 2 + p[2] ** 2 for p in pairs)
        sxX = sum(p[1] * p[3] + p[2] * p[4] for p in pairs)
        sxY = sum(p[1] * p[4] - p[2] * p[3] for p in pairs)
        # 重心まわりで解く
        mx, my, mX, mY = sx / n, sy / n, sX / n, sY / n
        cxx = sxx - n * (mx * mx + my * my)
        if cxx <= 0:
            raise ValueError("対応点が 1 か所に重なっている")
        a = (sxX - n * (mx * mX + my * mY)) / cxx
        b = (sxY - n * (mx * mY - my * mX)) / cxx
        tx = mX - (a * mx - b * my)
        ty = mY - (b * mx + a * my)
        h = Helmert2D(a, b, tx, ty)
        for name, x, y, X, Y in pairs:
            px, py = h.apply(x, y)
            h.residuals.append((name, px - X, py - Y, math.hypot(px - X, py - Y)))
        return h

    @staticmethod
    def from_known_points(known_points: List[dict]) -> "Helmert2D":
        """補足ファイルの known_points（name, x, y, X_public, Y_public）から。"""
        pairs = []
        for kp in known_points:
            x, y = kp.get("x"), kp.get("y")
            X, Y = kp.get("X_public"), kp.get("Y_public")
            if None in (x, y, X, Y):
                continue
            pairs.append((str(kp.get("name", "")), float(x), float(y), float(X), float(Y)))
        return Helmert2D.fit(pairs)
