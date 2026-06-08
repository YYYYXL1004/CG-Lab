from __future__ import annotations


PointTuple = tuple[int | float, int | float]


def de_casteljau_point(control_points: list[PointTuple], t: float) -> tuple[float, float]:
    if not control_points:
        return 0.0, 0.0
    current = [(float(x), float(y)) for x, y in control_points]
    while len(current) > 1:
        current = [
            (
                (1 - t) * current[index][0] + t * current[index + 1][0],
                (1 - t) * current[index][1] + t * current[index + 1][1],
            )
            for index in range(len(current) - 1)
        ]
    return current[0]


def bezier_polyline(
    control_points: list[PointTuple],
    steps: int | None = None,
) -> list[tuple[int, int]]:
    if len(control_points) < 2:
        return [(round(x), round(y)) for x, y in control_points]
    if steps is None:
        steps = _adaptive_steps(*control_points)
    steps = max(1, steps)
    pixels: list[tuple[int, int]] = []
    for index in range(steps + 1):
        point = de_casteljau_point(control_points, index / steps)
        pixel = (round(point[0]), round(point[1]))
        if not pixels or pixels[-1] != pixel:
            pixels.append(pixel)
    return pixels


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


def catmull_rom_polyline(
    points: list[PointTuple],
    steps_per_segment: int | None = None,
) -> list[tuple[int, int]]:
    """Smooth a polyline of sample points by piecewise Catmull-Rom → cubic Bezier.

    The curve passes through every input point. Endpoints are clamped by
    duplicating the first/last point as virtual neighbors.
    """
    n = len(points)
    if n < 2:
        return [(round(x), round(y)) for x, y in points]
    if n == 2:
        return [(round(points[0][0]), round(points[0][1])),
                (round(points[1][0]), round(points[1][1]))]
    result: list[tuple[int, int]] = []
    for i in range(n - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[i + 2] if i + 2 < n else points[i + 1]
        b1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        b2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        segment = cubic_bezier(p1, b1, b2, p2, steps=steps_per_segment)
        if result and result[-1] == segment[0]:
            result.extend(segment[1:])
        else:
            result.extend(segment)
    return result
