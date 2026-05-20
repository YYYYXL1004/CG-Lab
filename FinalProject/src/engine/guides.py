from __future__ import annotations

from core.shapes import Shape


def _bounds(shape: Shape) -> tuple[float, float, float, float] | None:
    """Return (x_min, y_min, x_max, y_max) for a shape, or None."""
    try:
        pts = shape.outline_points()  # type: ignore[attr-defined]
    except AttributeError:
        return None
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _key_coords(x0: float, y0: float, x1: float, y1: float) -> dict[str, float]:
    return {
        "left": x0,
        "center_x": (x0 + x1) / 2,
        "right": x1,
        "top": y0,
        "center_y": (y0 + y1) / 2,
        "bottom": y1,
    }


def compute_guides(
    dragging_ids: set[str],
    all_shapes: list[Shape],
    snap_threshold: float = 8.0,
) -> tuple[list[tuple[str, float]], float, float]:
    """Compute snap guides for shapes being dragged.

    Returns:
        guides  — list of ("hline", y) or ("vline", x) guide lines
        snap_dx — X correction to apply to dragged shapes
        snap_dy — Y correction to apply to dragged shapes
    """
    static_coords: list[dict[str, float]] = []
    drag_coords: list[dict[str, float]] = []

    for shape in all_shapes:
        b = _bounds(shape)
        if b is None:
            continue
        kc = _key_coords(*b)
        if shape.id in dragging_ids:  # type: ignore[attr-defined]
            drag_coords.append(kc)
        else:
            static_coords.append(kc)

    if not static_coords or not drag_coords:
        return [], 0.0, 0.0

    guides: list[tuple[str, float]] = []
    best_dx: float = snap_threshold + 1
    best_dy: float = snap_threshold + 1
    snap_dx = 0.0
    snap_dy = 0.0

    x_pairs = [("left", "left"), ("left", "center_x"), ("left", "right"),
                ("center_x", "left"), ("center_x", "center_x"), ("center_x", "right"),
                ("right", "left"), ("right", "center_x"), ("right", "right")]
    y_pairs = [("top", "top"), ("top", "center_y"), ("top", "bottom"),
                ("center_y", "top"), ("center_y", "center_y"), ("center_y", "bottom"),
                ("bottom", "top"), ("bottom", "center_y"), ("bottom", "bottom")]

    for s_kc in static_coords:
        for d_kc in drag_coords:
            # Vertical alignment (X direction)
            for s_key, d_key in x_pairs:
                delta = s_kc[s_key] - d_kc[d_key]
                if abs(delta) < snap_threshold:
                    if abs(delta) < abs(best_dx):
                        best_dx = delta
                        snap_dx = delta
                    guides.append(("vline", s_kc[s_key]))

            # Horizontal alignment (Y direction)
            for s_key, d_key in y_pairs:
                delta = s_kc[s_key] - d_kc[d_key]
                if abs(delta) < snap_threshold:
                    if abs(delta) < abs(best_dy):
                        best_dy = delta
                        snap_dy = delta
                    guides.append(("hline", s_kc[s_key]))

    # Deduplicate guides
    seen: set[tuple[str, float]] = set()
    unique: list[tuple[str, float]] = []
    for g in guides:
        key = (g[0], round(g[1], 1))
        if key not in seen:
            seen.add(key)
            unique.append(g)

    return unique, snap_dx, snap_dy
