from __future__ import annotations

from core.document import Document
from core.shapes import CurveShape, FlowchartShape, LineShape, TextShape, shape_from_dict


Bounds = tuple[float, float, float, float]
Point = tuple[float, float]


def selection_bounds(document: Document, shape_ids: list[str] | set[str]) -> Bounds | None:
    selected = set(shape_ids)
    bounds = [shape.bounds() for shape in document.shapes if shape.id in selected]
    if not bounds:
        return None
    return (
        min(item[0] for item in bounds),
        min(item[1] for item in bounds),
        max(item[2] for item in bounds),
        max(item[3] for item in bounds),
    )


def shapes_in_rect(document: Document, rect: Bounds) -> list[str]:
    normalized = normalize_bounds(rect)
    return [shape.id for shape in document.shapes if bounds_intersect(shape.bounds(), normalized)]


def bounds_intersect(a: Bounds, b: Bounds) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def handle_at(bounds: Bounds | None, point: Point, tolerance: float = 7) -> str | None:
    if bounds is None:
        return None
    x1, y1, x2, y2 = bounds
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    handles = {
        "nw": (x1, y1),
        "n": (cx, y1),
        "ne": (x2, y1),
        "e": (x2, cy),
        "se": (x2, y2),
        "s": (cx, y2),
        "sw": (x1, y2),
        "w": (x1, cy),
    }
    px, py = point
    for name, (hx, hy) in handles.items():
        if abs(px - hx) <= tolerance and abs(py - hy) <= tolerance:
            return name
    return None


def bounds_from_handle(original: Bounds, handle: str, current: Point, min_size: float = 12) -> Bounds:
    x1, y1, x2, y2 = original
    cx, cy = current
    left, top, right, bottom = x1, y1, x2, y2
    if "w" in handle:
        left = min(cx, right - min_size)
    if "e" in handle:
        right = max(cx, left + min_size)
    if "n" in handle:
        top = min(cy, bottom - min_size)
    if "s" in handle:
        bottom = max(cy, top + min_size)
    return normalize_bounds((left, top, right, bottom))


def apply_group_resize(
    document: Document,
    shape_ids: list[str] | set[str],
    original_payloads: dict[str, dict],
    original_bounds: Bounds | None,
    new_bounds: Bounds,
) -> None:
    if original_bounds is None:
        return
    selected = set(shape_ids)
    ox1, oy1, ox2, oy2 = original_bounds
    nx1, ny1, nx2, ny2 = normalize_bounds(new_bounds)
    old_w = max(1e-6, ox2 - ox1)
    old_h = max(1e-6, oy2 - oy1)
    sx = (nx2 - nx1) / old_w
    sy = (ny2 - ny1) / old_h

    for shape in document.shapes:
        if shape.id not in selected or shape.id not in original_payloads:
            continue
        original = shape_from_dict(original_payloads[shape.id])
        if isinstance(shape, FlowchartShape) and isinstance(original, FlowchartShape):
            left, top = _map_point((original.x, original.y), (ox1, oy1), (nx1, ny1), sx, sy)
            right, bottom = _map_point((original.x + original.width, original.y + original.height), (ox1, oy1), (nx1, ny1), sx, sy)
            shape.x = left
            shape.y = top
            shape.width = max(12, right - left)
            shape.height = max(12, bottom - top)
            shape.rotation = original.rotation
            shape.flip_x = original.flip_x
            shape.flip_y = original.flip_y
        elif isinstance(shape, LineShape) and isinstance(original, LineShape):
            shape.x1, shape.y1 = _map_point((original.x1, original.y1), (ox1, oy1), (nx1, ny1), sx, sy)
            shape.x2, shape.y2 = _map_point((original.x2, original.y2), (ox1, oy1), (nx1, ny1), sx, sy)
        elif isinstance(shape, CurveShape) and isinstance(original, CurveShape):
            shape.points = [
                _map_point(p, (ox1, oy1), (nx1, ny1), sx, sy)
                for p in original.points
            ]
        elif isinstance(shape, TextShape) and isinstance(original, TextShape):
            shape.x, shape.y = _map_point((original.x, original.y), (ox1, oy1), (nx1, ny1), sx, sy)


def normalize_bounds(bounds: Bounds) -> Bounds:
    x1, y1, x2, y2 = bounds
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def _map_point(point: Point, old_origin: Point, new_origin: Point, sx: float, sy: float) -> Point:
    return new_origin[0] + (point[0] - old_origin[0]) * sx, new_origin[1] + (point[1] - old_origin[1]) * sy
