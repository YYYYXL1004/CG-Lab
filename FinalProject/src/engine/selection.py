from __future__ import annotations

import math

from algorithms.transform import Matrix3, Point as MatrixPoint
from core.document import Document
from core.shapes import CurveShape, FlowchartShape, GroupShape, LineShape, RasterImageShape, TextShape, shape_from_dict


Bounds = tuple[float, float, float, float]
Point = tuple[float, float]
ROTATION_HANDLE_OFFSET = 30.0


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
    return [
        shape.id
        for shape in document.shapes
        if getattr(shape, "visible", True)
        and not getattr(shape, "locked", False)
        and bounds_intersect(shape.bounds(), normalized)
    ]


def bounds_intersect(a: Bounds, b: Bounds) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def handle_at(bounds: Bounds | None, point: Point, tolerance: float = 7, rotation_offset: float = ROTATION_HANDLE_OFFSET) -> str | None:
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
    rx, ry = rotation_handle_point(bounds, rotation_offset)
    if abs(px - rx) <= tolerance and abs(py - ry) <= tolerance:
        return "rotate"
    for name, (hx, hy) in handles.items():
        if abs(px - hx) <= tolerance and abs(py - hy) <= tolerance:
            return name
    if y1 - tolerance <= py <= y2 + tolerance:
        if abs(px - x2) <= tolerance:
            return "e"
        if abs(px - x1) <= tolerance:
            return "w"
    if x1 - tolerance <= px <= x2 + tolerance:
        if abs(py - y1) <= tolerance:
            return "n"
        if abs(py - y2) <= tolerance:
            return "s"
    return None


def rotation_handle_point(bounds: Bounds, offset: float = ROTATION_HANDLE_OFFSET) -> Point:
    x1, y1, x2, _y2 = bounds
    return ((x1 + x2) / 2, y1 - offset)


def rotation_delta(bounds: Bounds | None, start: Point, current: Point) -> float:
    if bounds is None:
        return 0.0
    x1, y1, x2, y2 = bounds
    center = ((x1 + x2) / 2, (y1 + y2) / 2)
    start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
    current_angle = math.atan2(current[1] - center[1], current[0] - center[0])
    delta = math.degrees(current_angle - start_angle)
    return (delta + 180) % 360 - 180


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
            ix1, iy1, ix2, iy2 = original.bounds()
            tx1, ty1 = _map_point((ix1, iy1), (ox1, oy1), (nx1, ny1), sx, sy)
            tx2, ty2 = _map_point((ix2, iy2), (ox1, oy1), (nx1, ny1), sx, sy)
            shape.scale_from_bounds(original.bounds(), (tx1, ty1, tx2, ty2))
        elif isinstance(shape, RasterImageShape) and isinstance(original, RasterImageShape):
            left, top = _map_point((original.x, original.y), (ox1, oy1), (nx1, ny1), sx, sy)
            right, bottom = _map_point((original.x + original.width, original.y + original.height), (ox1, oy1), (nx1, ny1), sx, sy)
            shape.x = left
            shape.y = top
            shape.width = max(12, right - left)
            shape.height = max(12, bottom - top)
        elif isinstance(shape, GroupShape) and isinstance(original, GroupShape):
            updated = shape_from_dict(original.to_dict())
            assert isinstance(updated, GroupShape)
            updated.scale_from_bounds(original_bounds, (nx1, ny1, nx2, ny2))
            shape.children = updated.children
            shape.connectors = updated.connectors


def apply_group_rotation(
    document: Document,
    shape_ids: list[str] | set[str],
    original_payloads: dict[str, dict],
    original_bounds: Bounds | None,
    angle_degrees: float,
) -> None:
    if original_bounds is None:
        return
    selected = set(shape_ids)
    x1, y1, x2, y2 = original_bounds
    center = MatrixPoint((x1 + x2) / 2, (y1 + y2) / 2)
    matrix = Matrix3.rotation(math.radians(angle_degrees), center=center)

    for shape in document.shapes:
        if shape.id not in selected or shape.id not in original_payloads:
            continue
        original = shape_from_dict(original_payloads[shape.id])
        if isinstance(shape, FlowchartShape) and isinstance(original, FlowchartShape):
            new_center = matrix.apply(original.center())
            shape.x = new_center.x - original.width / 2
            shape.y = new_center.y - original.height / 2
            shape.width = original.width
            shape.height = original.height
            shape.rotation = (original.rotation + angle_degrees) % 360
            shape.flip_x = original.flip_x
            shape.flip_y = original.flip_y
        elif isinstance(shape, LineShape) and isinstance(original, LineShape):
            p1 = matrix.apply(MatrixPoint(original.x1, original.y1))
            p2 = matrix.apply(MatrixPoint(original.x2, original.y2))
            shape.x1, shape.y1, shape.x2, shape.y2 = p1.x, p1.y, p2.x, p2.y
        elif isinstance(shape, CurveShape) and isinstance(original, CurveShape):
            shape.points = [
                (p.x, p.y)
                for p in (matrix.apply(MatrixPoint(x, y)) for x, y in original.points)
            ]
        elif isinstance(shape, TextShape) and isinstance(original, TextShape):
            p = matrix.apply(MatrixPoint(original.x, original.y))
            shape.x, shape.y = p.x, p.y
        elif isinstance(shape, RasterImageShape) and isinstance(original, RasterImageShape):
            new_center = matrix.apply(original.center())
            shape.x = new_center.x - original.width / 2
            shape.y = new_center.y - original.height / 2
            shape.width = original.width
            shape.height = original.height
        elif isinstance(shape, GroupShape) and isinstance(original, GroupShape):
            updated = shape_from_dict(original.to_dict())
            assert isinstance(updated, GroupShape)
            updated.rotate_around(center, angle_degrees)
            shape.children = updated.children
            shape.connectors = updated.connectors


def normalize_bounds(bounds: Bounds) -> Bounds:
    x1, y1, x2, y2 = bounds
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def _map_point(point: Point, old_origin: Point, new_origin: Point, sx: float, sy: float) -> Point:
    return new_origin[0] + (point[0] - old_origin[0]) * sx, new_origin[1] + (point[1] - old_origin[1]) * sy
