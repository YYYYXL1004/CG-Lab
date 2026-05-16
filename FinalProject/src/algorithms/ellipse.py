from __future__ import annotations


def midpoint_ellipse(cx: int, cy: int, rx: int, ry: int) -> list[tuple[int, int]]:
    cx = round(cx)
    cy = round(cy)
    rx = abs(round(rx))
    ry = abs(round(ry))
    if rx == 0 and ry == 0:
        return [(cx, cy)]
    if rx == 0:
        return [(cx, y) for y in range(cy - ry, cy + ry + 1)]
    if ry == 0:
        return [(x, cy) for x in range(cx - rx, cx + rx + 1)]

    x = 0
    y = ry
    rx_sq = rx * rx
    ry_sq = ry * ry
    dx = 2 * ry_sq * x
    dy = 2 * rx_sq * y
    decision1 = ry_sq - rx_sq * ry + 0.25 * rx_sq
    pixels: list[tuple[int, int]] = []

    while dx < dy:
        pixels.extend(_four_way(cx, cy, x, y))
        if decision1 < 0:
            x += 1
            dx += 2 * ry_sq
            decision1 += dx + ry_sq
        else:
            x += 1
            y -= 1
            dx += 2 * ry_sq
            dy -= 2 * rx_sq
            decision1 += dx - dy + ry_sq

    decision2 = (
        ry_sq * (x + 0.5) * (x + 0.5)
        + rx_sq * (y - 1) * (y - 1)
        - rx_sq * ry_sq
    )
    while y >= 0:
        pixels.extend(_four_way(cx, cy, x, y))
        if decision2 > 0:
            y -= 1
            dy -= 2 * rx_sq
            decision2 += rx_sq - dy
        else:
            y -= 1
            x += 1
            dx += 2 * ry_sq
            dy -= 2 * rx_sq
            decision2 += dx - dy + rx_sq
    return list(dict.fromkeys(pixels))


def _four_way(cx: int, cy: int, x: int, y: int) -> list[tuple[int, int]]:
    return [
        (cx + x, cy + y),
        (cx - x, cy + y),
        (cx + x, cy - y),
        (cx - x, cy - y),
    ]
