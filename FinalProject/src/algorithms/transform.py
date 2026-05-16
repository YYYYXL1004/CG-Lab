from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Matrix3:
    rows: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

    @staticmethod
    def identity() -> "Matrix3":
        return Matrix3(((1, 0, 0), (0, 1, 0), (0, 0, 1)))

    @staticmethod
    def translation(tx: float, ty: float) -> "Matrix3":
        return Matrix3(((1, 0, tx), (0, 1, ty), (0, 0, 1)))

    @staticmethod
    def scale(sx: float, sy: float | None = None, center: Point | None = None) -> "Matrix3":
        if sy is None:
            sy = sx
        base = Matrix3(((sx, 0, 0), (0, sy, 0), (0, 0, 1)))
        if center is None:
            return base
        return Matrix3.translation(center.x, center.y) @ base @ Matrix3.translation(-center.x, -center.y)

    @staticmethod
    def rotation(angle_radians: float, center: Point | None = None) -> "Matrix3":
        cos_a = math.cos(angle_radians)
        sin_a = math.sin(angle_radians)
        base = Matrix3(((cos_a, -sin_a, 0), (sin_a, cos_a, 0), (0, 0, 1)))
        if center is None:
            return base
        return Matrix3.translation(center.x, center.y) @ base @ Matrix3.translation(-center.x, -center.y)

    @staticmethod
    def reflection(horizontal: bool = False, vertical: bool = False, center: Point | None = None) -> "Matrix3":
        sx = -1 if horizontal else 1
        sy = -1 if vertical else 1
        return Matrix3.scale(sx, sy, center=center)

    def __matmul__(self, other: "Matrix3") -> "Matrix3":
        result = []
        for row in range(3):
            result_row = []
            for col in range(3):
                result_row.append(sum(self.rows[row][index] * other.rows[index][col] for index in range(3)))
            result.append(tuple(result_row))
        return Matrix3(tuple(result))  # type: ignore[arg-type]

    def apply(self, point: Point) -> Point:
        x = self.rows[0][0] * point.x + self.rows[0][1] * point.y + self.rows[0][2]
        y = self.rows[1][0] * point.x + self.rows[1][1] * point.y + self.rows[1][2]
        w = self.rows[2][0] * point.x + self.rows[2][1] * point.y + self.rows[2][2]
        if w and w != 1:
            x /= w
            y /= w
        return Point(x, y)
