from __future__ import annotations

from dataclasses import dataclass, field


Color = str | tuple[int, int, int] | tuple[int, int, int, int] | None


@dataclass
class ShapeStyle:
    stroke: Color = "#6080A0"
    fill: Color = "#283850"
    stroke_width: int = 2
    dash: list[int] = field(default_factory=list)
    font_size: int = 14
    text_color: Color = "#D0D0E0"
    text_align: str = "center"
    bold: bool = False

    def to_dict(self) -> dict:
        return {
            "stroke": _serialize_color(self.stroke),
            "fill": _serialize_color(self.fill),
            "stroke_width": self.stroke_width,
            "dash": list(self.dash),
            "font_size": self.font_size,
            "text_color": _serialize_color(self.text_color),
            "text_align": self.text_align,
            "bold": self.bold,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "ShapeStyle":
        if not payload:
            return cls()
        return cls(
            stroke=_deserialize_color(payload.get("stroke", "#6080A0")),
            fill=_deserialize_color(payload.get("fill", "#283850")),
            stroke_width=int(payload.get("stroke_width", 2)),
            dash=list(payload.get("dash", [])),
            font_size=int(payload.get("font_size", 14)),
            text_color=_deserialize_color(payload.get("text_color", "#D0D0E0")),
            text_align=str(payload.get("text_align", "center")),
            bold=bool(payload.get("bold", False)),
        )


def _serialize_color(value: Color) -> str | list[int] | None:
    if isinstance(value, tuple):
        return list(value)
    return value


def _deserialize_color(value) -> Color:
    if isinstance(value, list):
        return tuple(value)
    return value
