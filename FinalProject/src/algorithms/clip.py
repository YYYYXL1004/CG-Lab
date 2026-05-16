from __future__ import annotations


INSIDE = 0
LEFT = 1
RIGHT = 2
TOP = 4
BOTTOM = 8


def cohen_sutherland_clip(
    start: tuple[int | float, int | float],
    end: tuple[int | float, int | float],
    rect: tuple[int | float, int | float, int | float],
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    x_min, y_min, x_max, y_max = map(float, rect)
    x0, y0 = map(float, start)
    x1, y1 = map(float, end)
    code0 = _out_code(x0, y0, x_min, y_min, x_max, y_max)
    code1 = _out_code(x1, y1, x_min, y_min, x_max, y_max)

    while True:
        if not (code0 | code1):
            return ((round(x0), round(y0)), (round(x1), round(y1)))
        if code0 & code1:
            return None

        code_out = code0 or code1
        if code_out & TOP:
            x = x0 + (x1 - x0) * (y_min - y0) / (y1 - y0)
            y = y_min
        elif code_out & BOTTOM:
            x = x0 + (x1 - x0) * (y_max - y0) / (y1 - y0)
            y = y_max
        elif code_out & RIGHT:
            y = y0 + (y1 - y0) * (x_max - x0) / (x1 - x0)
            x = x_max
        else:
            y = y0 + (y1 - y0) * (x_min - x0) / (x1 - x0)
            x = x_min

        if code_out == code0:
            x0, y0 = x, y
            code0 = _out_code(x0, y0, x_min, y_min, x_max, y_max)
        else:
            x1, y1 = x, y
            code1 = _out_code(x1, y1, x_min, y_min, x_max, y_max)


def _out_code(x: float, y: float, x_min: float, y_min: float, x_max: float, y_max: float) -> int:
    code = INSIDE
    if x < x_min:
        code |= LEFT
    elif x > x_max:
        code |= RIGHT
    if y < y_min:
        code |= TOP
    elif y > y_max:
        code |= BOTTOM
    return code
