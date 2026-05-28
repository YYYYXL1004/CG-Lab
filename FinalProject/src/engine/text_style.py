from __future__ import annotations

from core.shapes import FlowchartShape, Shape, TextShape


TEXT_SIZE_MIN = 8
TEXT_SIZE_MAX = 72


def clamp_font_size(value: int | float) -> int:
    size = round(float(value))
    return max(TEXT_SIZE_MIN, min(TEXT_SIZE_MAX, size))


def apply_text_style(
    shapes: list[Shape],
    selected_ids: set[str],
    align: str,
    bold: bool,
    color,
    font_size: int | float,
) -> int:
    """Apply text styling to selected shapes that actually render text."""
    size = clamp_font_size(font_size)
    changed = 0
    for shape in shapes:
        if shape.id not in selected_ids or not isinstance(shape, (FlowchartShape, TextShape)):
            continue
        shape.style.text_align = align
        shape.style.bold = bold
        shape.style.text_color = color
        shape.style.font_size = size
        changed += 1
    return changed
