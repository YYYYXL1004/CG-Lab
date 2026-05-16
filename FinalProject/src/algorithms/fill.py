from __future__ import annotations

import math
from collections.abc import Iterable


PointTuple = tuple[int | float, int | float]


def scanline_fill(vertices: Iterable[PointTuple]) -> list[tuple[int, int]]:
    points = [(float(x), float(y)) for x, y in vertices]
    if len(points) < 3:
        return []

    y_min = math.ceil(min(y for _, y in points))
    y_max = math.floor(max(y for _, y in points))
    pixels: list[tuple[int, int]] = []
    edge_count = len(points)

    for y in range(y_min, y_max + 1):
        intersections: list[float] = []
        scan_y = y + 0.5
        for index in range(edge_count):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % edge_count]
            if y1 == y2:
                continue
            lower = min(y1, y2)
            upper = max(y1, y2)
            if lower <= scan_y < upper:
                t = (scan_y - y1) / (y2 - y1)
                intersections.append(x1 + t * (x2 - x1))
        intersections.sort()
        for left, right in zip(intersections[0::2], intersections[1::2]):
            for x in range(math.ceil(left), math.floor(right) + 1):
                pixels.append((x, y))
    return pixels
