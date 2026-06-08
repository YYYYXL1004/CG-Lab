from __future__ import annotations

import math
from html import escape
from pathlib import Path
from typing import Iterable

from algorithms.bezier import bezier_polyline, catmull_rom_polyline
from core.document import Document
from core.shapes import BezierShape, ConnectorShape, CurveShape, FlowchartShape, GroupShape, LineShape, RasterImageShape, TextShape


CIRCUIT_KINDS = {
    "resistor",
    "capacitor",
    "ground",
    "battery",
    "switch",
    "led",
    "inductor",
    "voltage_source",
}

SMOOTHNESS_STEPS = {1: 4, 2: 10, 3: 20, 4: 40, 5: 80}


class SvgRenderer:
    def __init__(self, width: int, height: int):
        self.width = max(1, int(width))
        self.height = max(1, int(height))

    def render(
        self,
        document: Document,
        zoom: float = 1.0,
        pan: tuple[float, float] = (0, 0),
        show_grid: bool = True,
    ) -> str:
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                "<svg "
                + _attrs(
                    xmlns="http://www.w3.org/2000/svg",
                    width=_num(self.width),
                    height=_num(self.height),
                    viewBox=f"0 0 {_num(self.width)} {_num(self.height)}",
                    version="1.1",
                )
                + ">"
            ),
        ]
        parts.append(
            "<rect "
            + _attrs(x="0", y="0", width=_num(self.width), height=_num(self.height), **_paint_attrs("fill", document.background))
            + " />"
        )
        if show_grid:
            parts.extend(self._grid(document.grid_size, zoom, pan))

        hidden_ids = {shape.id for shape in document.shapes if not getattr(shape, "visible", True)}
        for shape in sorted(document.shapes, key=lambda item: item.z_order):
            if not getattr(shape, "visible", True):
                continue
            parts.extend(self._shape(shape, zoom, pan))

        for connector in document.connectors:
            if connector.start_shape_id in hidden_ids or connector.end_shape_id in hidden_ids:
                continue
            parts.extend(self._connector(document, connector, zoom, pan))

        parts.append("</svg>")
        return "\n".join(parts)

    def save(
        self,
        document: Document,
        path: str | Path,
        zoom: float = 1.0,
        pan: tuple[float, float] = (0, 0),
        show_grid: bool = True,
    ) -> None:
        Path(path).write_text(self.render(document, zoom, pan, show_grid), encoding="utf-8")

    def _grid(self, grid_size: int, zoom: float, pan: tuple[float, float]) -> list[str]:
        spacing = max(8, round(grid_size * zoom))
        offset_x = round(pan[0] % spacing)
        offset_y = round(pan[1] % spacing)
        parts = ['<g id="grid" stroke="#2A2A3E" stroke-width="1" fill="none">']
        for x in range(offset_x, self.width, spacing):
            parts.append("<line " + _attrs(x1=_num(x), y1="0", x2=_num(x), y2=_num(self.height)) + " />")
        for y in range(offset_y, self.height, spacing):
            parts.append("<line " + _attrs(x1="0", y1=_num(y), x2=_num(self.width), y2=_num(y)) + " />")
        parts.append("</g>")
        return parts

    def _shape(self, shape, zoom: float, pan: tuple[float, float]) -> list[str]:
        if isinstance(shape, FlowchartShape):
            return self._flowchart(shape, zoom, pan)
        if isinstance(shape, GroupShape):
            return self._group(shape, zoom, pan)
        if isinstance(shape, LineShape):
            return [self._line((shape.x1, shape.y1), (shape.x2, shape.y2), shape.style, zoom, pan)]
        if isinstance(shape, CurveShape):
            return self._curve(shape, zoom, pan)
        if isinstance(shape, BezierShape):
            return self._bezier(shape, zoom, pan)
        if isinstance(shape, TextShape):
            return self._text_block(shape.text, shape.bounds(), shape.style, zoom, pan)
        if isinstance(shape, RasterImageShape):
            return [self._image(shape, zoom, pan)]
        return []

    def _flowchart(self, shape: FlowchartShape, zoom: float, pan: tuple[float, float]) -> list[str]:
        if shape.kind == "er_table":
            return self._er_table(shape, zoom, pan)

        parts: list[str] = []
        is_circuit = shape.kind in CIRCUIT_KINDS
        if not is_circuit:
            points = [self._world_to_screen(point, zoom, pan) for point in shape.outline_points()]
            parts.append(
                "<polygon "
                + _attrs(
                    points=_points(points),
                    **_paint_attrs("fill", shape.style.fill),
                    **_paint_attrs("stroke", shape.style.stroke),
                    **_stroke_attrs(shape.style.stroke_width, shape.style.dash, zoom),
                    **{"stroke-linejoin": "round"},
                )
                + " />"
            )

        for start, end in shape.extra_segments():
            parts.append(self._line(start, end, shape.style, zoom, pan))

        if shape.kind == "database":
            x1, y1, x2, y2 = shape.bounds()
            cx = (x1 + x2) / 2
            rx = (x2 - x1) / 2
            ry = max(4, (y2 - y1) * 0.14)
            for cy in (y1 + ry, y2 - ry):
                parts.append(self._ellipse((cx, cy), rx, ry, shape.style, zoom, pan, fill=None))
        elif shape.kind == "voltage_source":
            x1, y1, x2, y2 = shape.bounds()
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            radius = min(x2 - x1, y2 - y1) * 0.35
            parts.append(self._ellipse((cx, cy), radius, radius, shape.style, zoom, pan, fill=None))

        if shape.text:
            text_bounds = shape.bounds()
            if shape.kind == "inductor":
                x1, y1, x2, y2 = text_bounds
                text_bounds = (x1, (y1 + y2) / 2, x2, y2)
            parts.extend(self._text_block(shape.text, text_bounds, shape.style, zoom, pan))
        return parts

    def _er_table(self, shape: FlowchartShape, zoom: float, pan: tuple[float, float]) -> list[str]:
        x1, y1 = self._world_to_screen((shape.x, shape.y), zoom, pan)
        x2, y2 = self._world_to_screen((shape.x + shape.width, shape.y + shape.height), zoom, pan)
        width = x2 - x1
        height = y2 - y1
        header_h = max(18, round(34 * zoom))
        row_h = max(16, round(26 * zoom))
        lines = shape.text.splitlines() if shape.text else [""]
        parts = [
            "<rect "
            + _attrs(
                x=_num(x1),
                y=_num(y1),
                width=_num(width),
                height=_num(height),
                fill=_paint(shape.style.fill),
                stroke="#184E58",
                **{"stroke-width": _num(max(1, 2 * zoom))},
            )
            + " />",
            "<rect "
            + _attrs(x=_num(x1), y=_num(y1), width=_num(width), height=_num(header_h), fill="#2A9D8F")
            + " />",
        ]
        if lines:
            parts.append(
                _single_text(
                    lines[0],
                    x1 + 12 * zoom,
                    y1 + header_h / 2,
                    "#FFFFFF",
                    max(8, round((shape.style.font_size + 2) * zoom)),
                    "start",
                    True,
                )
            )
        for index, raw in enumerate(lines[1:]):
            top = y1 + header_h + index * row_h
            parts.append("<line " + _attrs(x1=_num(x1), y1=_num(top), x2=_num(x2), y2=_num(top), stroke="#D7E4EA") + " />")
            parts.append(
                _single_text(
                    raw.strip(),
                    x1 + 12 * zoom,
                    top + row_h / 2,
                    "#263238",
                    max(8, round(shape.style.font_size * zoom)),
                    "start",
                    False,
                )
            )
        return parts

    def _group(self, shape: GroupShape, zoom: float, pan: tuple[float, float]) -> list[str]:
        parts = ["<g " + _attrs(id=shape.id) + ">"]
        nested = Document(shapes=list(shape.children), connectors=list(shape.connectors), background="#00000000")
        for child in sorted(shape.children, key=lambda item: item.z_order):
            if getattr(child, "visible", True):
                parts.extend(self._shape(child, zoom, pan))
        for connector in shape.connectors:
            parts.extend(self._connector(nested, connector, zoom, pan))
        parts.append("</g>")
        return parts

    def _curve(self, shape: CurveShape, zoom: float, pan: tuple[float, float]) -> list[str]:
        if len(shape.points) < 2:
            return []
        steps = SMOOTHNESS_STEPS.get(getattr(shape.style, "smoothness", 3), 20)
        sample = catmull_rom_polyline(shape.points, steps_per_segment=steps)
        points = [self._world_to_screen(point, zoom, pan) for point in sample]
        return [
            "<polyline "
            + _attrs(
                points=_points(points),
                fill="none",
                **_paint_attrs("stroke", shape.style.stroke),
                **_stroke_attrs(shape.style.stroke_width, shape.style.dash, zoom),
                **{"stroke-linecap": "round", "stroke-linejoin": "round"},
            )
            + " />"
        ]

    def _bezier(self, shape: BezierShape, zoom: float, pan: tuple[float, float]) -> list[str]:
        if len(shape.points) < 2:
            return []
        if len(shape.points) == 4:
            p0, p1, p2, p3 = [self._world_to_screen(point, zoom, pan) for point in shape.points]
            d = f"M {_num(p0[0])} {_num(p0[1])} C {_num(p1[0])} {_num(p1[1])}, {_num(p2[0])} {_num(p2[1])}, {_num(p3[0])} {_num(p3[1])}"
            return [
                "<path "
                + _attrs(
                    d=d,
                    fill="none",
                    **_paint_attrs("stroke", shape.style.stroke),
                    **_stroke_attrs(shape.style.stroke_width, shape.style.dash, zoom),
                    **{"stroke-linecap": "round", "stroke-linejoin": "round"},
                )
                + " />"
            ]
        sample = bezier_polyline(shape.points)
        points = [self._world_to_screen(point, zoom, pan) for point in sample]
        return [
            "<polyline "
            + _attrs(
                points=_points(points),
                fill="none",
                **_paint_attrs("stroke", shape.style.stroke),
                **_stroke_attrs(shape.style.stroke_width, shape.style.dash, zoom),
                **{"stroke-linecap": "round", "stroke-linejoin": "round"},
            )
            + " />"
        ]

    def _connector(self, document: Document, connector: ConnectorShape, zoom: float, pan: tuple[float, float]) -> list[str]:
        world_points = document.connector_points(connector)
        if len(world_points) < 2:
            return []
        points = [self._world_to_screen(point, zoom, pan) for point in world_points]
        stroke = connector.style.stroke
        parts = [
            "<polyline "
            + _attrs(
                points=_points(points),
                fill="none",
                **_paint_attrs("stroke", stroke),
                **_stroke_attrs(connector.style.stroke_width, connector.style.dash, zoom),
                **{"stroke-linecap": "round", "stroke-linejoin": "round"},
            )
            + " />"
        ]
        if connector.arrow_end != "none":
            parts.extend(_arrowhead(points[-2], points[-1], stroke, connector.arrow_end, zoom))
        if connector.arrow_start != "none":
            parts.extend(_arrowhead(points[1], points[0], stroke, connector.arrow_start, zoom))
        return parts

    def _line(self, start: tuple[float, float], end: tuple[float, float], style, zoom: float, pan: tuple[float, float]) -> str:
        sx, sy = self._world_to_screen(start, zoom, pan)
        ex, ey = self._world_to_screen(end, zoom, pan)
        return (
            "<line "
            + _attrs(
                x1=_num(sx),
                y1=_num(sy),
                x2=_num(ex),
                y2=_num(ey),
                **_paint_attrs("stroke", style.stroke),
                **_stroke_attrs(style.stroke_width, style.dash, zoom),
                **{"stroke-linecap": "round"},
            )
            + " />"
        )

    def _ellipse(
        self,
        center: tuple[float, float],
        rx: float,
        ry: float,
        style,
        zoom: float,
        pan: tuple[float, float],
        fill,
    ) -> str:
        cx, cy = self._world_to_screen(center, zoom, pan)
        return (
            "<ellipse "
            + _attrs(
                cx=_num(cx),
                cy=_num(cy),
                rx=_num(rx * zoom),
                ry=_num(ry * zoom),
                **_paint_attrs("fill", fill),
                **_paint_attrs("stroke", style.stroke),
                **_stroke_attrs(style.stroke_width, style.dash, zoom),
            )
            + " />"
        )

    def _text_block(self, text: str, bounds: tuple[float, float, float, float], style, zoom: float, pan: tuple[float, float]) -> list[str]:
        x1, y1 = self._world_to_screen((bounds[0], bounds[1]), zoom, pan)
        x2, y2 = self._world_to_screen((bounds[2], bounds[3]), zoom, pan)
        lines = text.split("\n") if text else [""]
        font_size = max(8, round(style.font_size * zoom))
        line_height = font_size * 1.25
        total_height = line_height * len(lines)
        start_y = y1 + (y2 - y1 - total_height) / 2 + font_size * 0.9
        align = getattr(style, "text_align", "center")
        if align == "left":
            x = x1 + 4 * zoom
            anchor = "start"
        elif align == "right":
            x = x2 - 4 * zoom
            anchor = "end"
        else:
            x = (x1 + x2) / 2
            anchor = "middle"
        parts = [
            "<text "
            + _attrs(
                x=_num(x),
                y=_num(start_y),
                fill=_paint(style.text_color),
                **{
                    "font-family": "Microsoft YaHei, SimHei, Arial, sans-serif",
                    "font-size": _num(font_size),
                    "font-weight": "700" if getattr(style, "bold", False) else "400",
                    "text-anchor": anchor,
                },
            )
            + ">"
        ]
        for index, line in enumerate(lines):
            if index == 0:
                parts.append(escape(line, quote=True))
            else:
                parts.append("<tspan " + _attrs(x=_num(x), dy=_num(line_height)) + ">" + escape(line, quote=True) + "</tspan>")
        parts.append("</text>")
        return ["".join(parts)]

    def _image(self, shape: RasterImageShape, zoom: float, pan: tuple[float, float]) -> str:
        x, y = self._world_to_screen((shape.x, shape.y), zoom, pan)
        return (
            "<image "
            + _attrs(
                x=_num(x),
                y=_num(y),
                width=_num(shape.width * zoom),
                height=_num(shape.height * zoom),
                href=shape.data_url,
                preserveAspectRatio="none",
            )
            + " />"
        )

    def _world_to_screen(self, point: tuple[float, float], zoom: float, pan: tuple[float, float]) -> tuple[float, float]:
        return point[0] * zoom + pan[0], point[1] * zoom + pan[1]


def _single_text(text: str, x: float, y: float, fill, font_size: int, anchor: str, bold: bool) -> str:
    return (
        "<text "
        + _attrs(
            x=_num(x),
            y=_num(y),
            fill=_paint(fill),
            **{
                "font-family": "Microsoft YaHei, SimHei, Arial, sans-serif",
                "font-size": _num(font_size),
                "font-weight": "700" if bold else "400",
                "text-anchor": anchor,
                "dominant-baseline": "middle",
            },
        )
        + ">"
        + escape(text, quote=True)
        + "</text>"
    )


def _arrowhead(start: tuple[float, float], end: tuple[float, float], color, style: str, zoom: float) -> list[str]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return []
    ux = dx / length
    uy = dy / length
    size = 12 * zoom
    left = (end[0] - ux * size - uy * size * 0.45, end[1] - uy * size + ux * size * 0.45)
    right = (end[0] - ux * size + uy * size * 0.45, end[1] - uy * size - ux * size * 0.45)
    paint = _paint(color)
    if style == "arrow":
        return ["<polygon " + _attrs(points=_points([end, left, right]), fill=paint, stroke=paint) + " />"]
    if style == "open_arrow":
        return [
            "<polyline "
            + _attrs(points=_points([left, end, right]), fill="none", stroke=paint, **{"stroke-width": _num(max(1, 2 * zoom))})
            + " />"
        ]
    if style == "diamond":
        mid = (end[0] - ux * size, end[1] - uy * size)
        back = (end[0] - ux * size * 2, end[1] - uy * size * 2)
        dleft = (mid[0] - uy * size * 0.4, mid[1] + ux * size * 0.4)
        dright = (mid[0] + uy * size * 0.4, mid[1] - ux * size * 0.4)
        return ["<polygon " + _attrs(points=_points([end, dleft, back, dright]), fill=paint, stroke=paint) + " />"]
    if style == "dot":
        cx = end[0] - ux * 6 * zoom
        cy = end[1] - uy * 6 * zoom
        return ["<circle " + _attrs(cx=_num(cx), cy=_num(cy), r=_num(max(1, 5 * zoom)), fill=paint, stroke=paint) + " />"]
    return []


def _stroke_attrs(width: float, dash: list[int], zoom: float) -> dict[str, str]:
    attrs = {"stroke-width": _num(max(1, width * zoom))}
    if dash:
        attrs["stroke-dasharray"] = " ".join(_num(max(1, value * zoom)) for value in dash)
    return attrs


def _paint_attrs(name: str, color) -> dict[str, str]:
    paint = _paint(color)
    attrs = {name: paint}
    opacity = _opacity(color)
    if opacity is not None:
        attrs[f"{name}-opacity"] = _num(opacity)
    return attrs


def _paint(color) -> str:
    if color is None:
        return "none"
    if isinstance(color, tuple):
        if len(color) >= 3:
            return f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}"
        return "none"
    text = str(color).strip()
    if text.startswith("#") and len(text) == 9:
        return text[:7]
    return text or "none"


def _opacity(color) -> float | None:
    if isinstance(color, tuple) and len(color) == 4:
        return max(0.0, min(1.0, color[3] / 255))
    text = str(color).strip() if color is not None else ""
    if text.startswith("#") and len(text) == 9:
        return int(text[7:9], 16) / 255
    return None


def _attrs(**attrs: str) -> str:
    return " ".join(f'{key}="{escape(str(value), quote=True)}"' for key, value in attrs.items())


def _points(points: Iterable[tuple[float, float]]) -> str:
    return " ".join(f"{_num(x)},{_num(y)}" for x, y in points)


def _num(value: float | int) -> str:
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")
