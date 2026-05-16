from __future__ import annotations


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    x0, y0, x1, y1 = map(round, (x0, y0, x1, y1))
    pixels: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        pixels.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return pixels


def dda_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        return [(round(x0), round(y0))]
    x_inc = dx / steps
    y_inc = dy / steps
    x = float(x0)
    y = float(y0)
    pixels: list[tuple[int, int]] = []
    for _ in range(steps + 1):
        point = (round(x), round(y))
        if not pixels or pixels[-1] != point:
            pixels.append(point)
        x += x_inc
        y += y_inc
    return pixels


def dashed_line(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    pattern: list[int] | tuple[int, ...] | None = None,
) -> list[tuple[int, int]]:
    pixels = bresenham_line(x0, y0, x1, y1)
    if not pattern:
        return pixels
    clean_pattern = [max(1, int(length)) for length in pattern]
    period = sum(clean_pattern)
    result: list[tuple[int, int]] = []
    for index, point in enumerate(pixels):
        cursor = index % period
        total = 0
        draw = True
        for length in clean_pattern:
            total += length
            if cursor < total:
                break
            draw = not draw
        if draw:
            result.append(point)
    return result
