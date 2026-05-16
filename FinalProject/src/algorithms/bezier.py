from __future__ import annotations


PointTuple = tuple[int | float, int | float]


def cubic_bezier(
    p0: PointTuple,
    p1: PointTuple,
    p2: PointTuple,
    p3: PointTuple,
    steps: int | None = None,
) -> list[tuple[int, int]]:
    if steps is None:
        steps = _adaptive_steps(p0, p1, p2, p3)
    steps = max(1, steps)
    pixels: list[tuple[int, int]] = []
    for index in range(steps + 1):
        t = index / steps
        point = _de_casteljau([p0, p1, p2, p3], t)
        pixel = (round(point[0]), round(point[1]))
        if not pixels or pixels[-1] != pixel:
            pixels.append(pixel)
    return pixels


def _de_casteljau(points: list[PointTuple], t: float) -> tuple[float, float]:
    current = [(float(x), float(y)) for x, y in points]
    while len(current) > 1:
        current = [
            (
                (1 - t) * current[index][0] + t * current[index + 1][0],
                (1 - t) * current[index][1] + t * current[index + 1][1],
            )
            for index in range(len(current) - 1)
        ]
    return current[0]


def _adaptive_steps(*points: PointTuple) -> int:
    length = sum(_distance(a, b) for a, b in zip(points, points[1:]))
    return max(12, min(160, round(length / 6)))


def _distance(a: PointTuple, b: PointTuple) -> float:
    return ((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2) ** 0.5
