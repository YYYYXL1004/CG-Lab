from __future__ import annotations

import math


def midpoint_circle(cx: int, cy: int, radius: int) -> list[tuple[int, int]]:
    radius = abs(round(radius))
    x = 0
    y = radius
    decision = 1 - radius
    pixels: list[tuple[int, int]] = []

    while x <= y:
        pixels.extend(_eight_way(round(cx), round(cy), x, y))
        if decision < 0:
            decision += 2 * x + 3
        else:
            decision += 2 * (x - y) + 5
            y -= 1
        x += 1
    return list(dict.fromkeys(pixels))


def midpoint_arc(
    cx: int,
    cy: int,
    radius: int,
    start_angle: float,
    end_angle: float,
) -> list[tuple[int, int]]:
    start = start_angle % 360
    end = end_angle % 360
    result: list[tuple[int, int]] = []
    for x, y in midpoint_circle(cx, cy, radius):
        angle = math.degrees(math.atan2(y - cy, x - cx)) % 360
        if _angle_between(angle, start, end):
            result.append((x, y))
    return result


def _eight_way(cx: int, cy: int, x: int, y: int) -> list[tuple[int, int]]:
    return [
        (cx + x, cy + y),
        (cx - x, cy + y),
        (cx + x, cy - y),
        (cx - x, cy - y),
        (cx + y, cy + x),
        (cx - y, cy + x),
        (cx + y, cy - x),
        (cx - y, cy - x),
    ]


def _angle_between(angle: float, start: float, end: float) -> bool:
    if start <= end:
        return start <= angle <= end
    return angle >= start or angle <= end
