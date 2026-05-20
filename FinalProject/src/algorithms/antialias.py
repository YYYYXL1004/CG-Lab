from __future__ import annotations

import math


def wu_line(x0: float, y0: float, x1: float, y1: float) -> list[tuple[int, int, float]]:
    """Return Xiaolin Wu antialiased line samples as (x, y, alpha)."""
    steep = abs(y1 - y0) > abs(x1 - x0)
    if steep:
        x0, y0 = y0, x0
        x1, y1 = y1, x1
    if x0 > x1:
        x0, x1 = x1, x0
        y0, y1 = y1, y0

    dx = x1 - x0
    dy = y1 - y0
    gradient = dy / dx if dx else 1.0
    pixels: list[tuple[int, int, float]] = []

    x_end = round(x0)
    y_end = y0 + gradient * (x_end - x0)
    x_gap = _rfpart(x0 + 0.5)
    xpxl1 = x_end
    ypxl1 = math.floor(y_end)
    _plot(pixels, steep, xpxl1, ypxl1, _rfpart(y_end) * x_gap)
    _plot(pixels, steep, xpxl1, ypxl1 + 1, _fpart(y_end) * x_gap)
    intery = y_end + gradient

    x_end = round(x1)
    y_end = y1 + gradient * (x_end - x1)
    x_gap = _fpart(x1 + 0.5)
    xpxl2 = x_end
    ypxl2 = math.floor(y_end)

    for x in range(xpxl1 + 1, xpxl2):
        _plot(pixels, steep, x, math.floor(intery), _rfpart(intery))
        _plot(pixels, steep, x, math.floor(intery) + 1, _fpart(intery))
        intery += gradient

    _plot(pixels, steep, xpxl2, ypxl2, _rfpart(y_end) * x_gap)
    _plot(pixels, steep, xpxl2, ypxl2 + 1, _fpart(y_end) * x_gap)  # noqa: match opening endpoint
    return [(x, y, alpha) for x, y, alpha in pixels if alpha > 0]


def _plot(pixels: list[tuple[int, int, float]], steep: bool, x: int, y: int, alpha: float) -> None:
    if steep:
        pixels.append((y, x, max(0.0, min(1.0, alpha))))
    else:
        pixels.append((x, y, max(0.0, min(1.0, alpha))))


def _fpart(value: float) -> float:
    return value - math.floor(value)


def _rfpart(value: float) -> float:
    return 1 - _fpart(value)
