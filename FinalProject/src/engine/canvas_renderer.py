from __future__ import annotations

import math

from algorithms.bezier import catmull_rom_polyline
from core.document import Document
from core.shapes import ConnectorShape, CurveShape, FlowchartShape, LineShape, TextShape
from engine.algorithm_replay import ReplayFrame


CANVAS_TAG = "native_render"
BACKGROUND_TAG = "native_background"
GRID_TAG = "native_grid"
SHAPE_TAG = "native_shape"
CONNECTOR_TAG = "native_connector"
SELECTION_TAG = "native_selection"
GUIDE_TAG = "native_guides"
REPLAY_TAG = "native_replay"

CIRCUIT_KINDS = {
    "resistor", "capacitor", "ground", "battery",
    "switch", "led", "inductor", "voltage_source",
}


class CanvasRenderer:
    def __init__(self, canvas) -> None:
        self.canvas = canvas

    def render(
        self,
        document: Document,
        zoom: float = 1.0,
        pan: tuple[float, float] = (0, 0),
        selected_ids: set[str] | None = None,
        show_grid: bool = True,
        draft: bool = False,
        guides: list[tuple[str, float]] | None = None,
        chrome: dict | None = None,
        connector_animation_phase: int | None = None,
        replay_frame: ReplayFrame | None = None,
    ) -> None:
        ch = chrome or {}
        self.canvas.configure(bg=document.background)
        self.canvas.delete(CANVAS_TAG)
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        if show_grid:
            self._draw_grid(width, height, document.grid_size, zoom, pan, ch.get("grid", "#2A2A3E"))
        for connector in document.connectors:
            self._draw_connector(
                document,
                connector,
                zoom,
                pan,
                ch.get("connector_flow", "#5BFFCF"),
                connector_animation_phase,
            )
        for shape in sorted(document.shapes, key=lambda item: item.z_order):
            self._draw_shape(shape, zoom, pan, draft=draft)
        if selected_ids:
            self._draw_selection_overlay(
                document,
                selected_ids,
                zoom,
                pan,
                ch.get("selection", "#5BA8FF"),
                ch.get("selection_handle_fill", "#1E1E2E"),
            )
        if guides:
            self._draw_guides(width, height, guides, zoom, pan, ch.get("guide", "#FF4444"))
        if replay_frame is not None:
            self._draw_replay_frame(replay_frame, zoom, pan, ch.get("replay", "#FFCF5A"))
        try:
            self.canvas.tag_lower(BACKGROUND_TAG)
        except Exception:
            pass

    def _draw_grid(
        self,
        width: int,
        height: int,
        grid_size: int,
        zoom: float,
        pan: tuple[float, float],
        color: str,
    ) -> None:
        spacing = max(8, round(grid_size * zoom))
        offset_x = round(pan[0] % spacing)
        offset_y = round(pan[1] % spacing)
        tags = (CANVAS_TAG, BACKGROUND_TAG, GRID_TAG)
        for x in range(offset_x, width, spacing):
            self.canvas.create_line(x, 0, x, height, fill=color, width=1, tags=tags)
        for y in range(offset_y, height, spacing):
            self.canvas.create_line(0, y, width, y, fill=color, width=1, tags=tags)

    def _draw_shape(self, shape, zoom: float, pan: tuple[float, float], draft: bool = False) -> None:
        tags = (CANVAS_TAG, SHAPE_TAG, f"shape:{shape.id}")
        if isinstance(shape, FlowchartShape):
            self._draw_flowchart_shape(shape, zoom, pan, tags, draft)
        elif isinstance(shape, LineShape):
            self.canvas.create_line(
                *self._screen(shape.x1, shape.y1, zoom, pan),
                *self._screen(shape.x2, shape.y2, zoom, pan),
                fill=shape.style.stroke,
                width=self._stroke_width(shape.style.stroke_width, zoom),
                dash=self._dash(shape.style.dash),
                tags=tags,
            )
        elif isinstance(shape, CurveShape):
            if len(shape.points) < 2:
                return
            points = catmull_rom_polyline(shape.points, steps_per_segment=10)
            self.canvas.create_line(
                *self._flat(points, zoom, pan),
                fill=shape.style.stroke,
                width=self._stroke_width(shape.style.stroke_width, zoom),
                dash=self._dash(shape.style.dash),
                smooth=True,
                tags=tags,
            )
        elif isinstance(shape, TextShape):
            self._draw_text_shape(shape, zoom, pan, tags)

    def _draw_flowchart_shape(
        self,
        shape: FlowchartShape,
        zoom: float,
        pan: tuple[float, float],
        tags: tuple[str, ...],
        draft: bool,
    ) -> None:
        is_circuit = shape.kind in CIRCUIT_KINDS
        outline = shape.outline_points()
        stroke_width = self._stroke_width(shape.style.stroke_width, zoom)
        if not is_circuit:
            fill = shape.style.fill or ""
            self.canvas.create_polygon(
                *self._flat(outline, zoom, pan),
                fill=fill,
                outline=shape.style.stroke,
                width=stroke_width,
                dash=self._dash(shape.style.dash),
                smooth=shape.kind in {"terminal", "circle", "ellipse", "org_box", "cloud"},
                tags=tags,
            )
        for a, b in shape.extra_segments():
            self.canvas.create_line(
                *self._screen(a[0], a[1], zoom, pan),
                *self._screen(b[0], b[1], zoom, pan),
                fill=shape.style.stroke,
                width=stroke_width,
                tags=tags,
            )
        if shape.kind in {"database", "voltage_source"}:
            self._draw_special_ellipses(shape, zoom, pan, tags, stroke_width)
        if shape.text:
            self._draw_flowchart_text(shape, zoom, pan, tags)

    def _draw_special_ellipses(
        self,
        shape: FlowchartShape,
        zoom: float,
        pan: tuple[float, float],
        tags: tuple[str, ...],
        stroke_width: int,
    ) -> None:
        x1, y1, x2, y2 = shape.bounds()
        cx = (x1 + x2) / 2
        if shape.kind == "database":
            rx = (x2 - x1) / 2
            ry = max(4, (y2 - y1) * 0.14)
            for cy in (y1 + ry, y2 - ry):
                self._create_oval_world(cx - rx, cy - ry, cx + rx, cy + ry, shape.style.stroke, "", stroke_width, zoom, pan, tags)
        elif shape.kind == "voltage_source":
            cy = (y1 + y2) / 2
            r = min(x2 - x1, y2 - y1) * 0.35
            self._create_oval_world(cx - r, cy - r, cx + r, cy + r, shape.style.stroke, "", stroke_width, zoom, pan, tags)

    def _draw_flowchart_text(
        self,
        shape: FlowchartShape,
        zoom: float,
        pan: tuple[float, float],
        tags: tuple[str, ...],
    ) -> None:
        x1, y1, x2, y2 = shape.bounds()
        if shape.kind == "inductor":
            y1 = (y1 + y2) / 2
        sx, sy = self._screen((x1 + x2) / 2, (y1 + y2) / 2, zoom, pan)
        self.canvas.create_text(
            sx,
            sy,
            text=shape.text,
            fill=shape.style.text_color,
            font=self._font(shape.style.font_size, shape.style.bold, zoom),
            width=max(20, (x2 - x1 - 8) * zoom),
            justify=shape.style.text_align,
            tags=tags,
        )

    def _draw_text_shape(self, shape: TextShape, zoom: float, pan: tuple[float, float], tags: tuple[str, ...]) -> None:
        x1, y1, x2, _y2 = shape.bounds()
        sx, sy = self._screen(x1, y1, zoom, pan)
        self.canvas.create_text(
            sx,
            sy,
            text=shape.text,
            fill=shape.style.text_color,
            font=self._font(shape.style.font_size, shape.style.bold, zoom),
            width=max(20, (x2 - x1) * zoom),
            justify=shape.style.text_align,
            anchor="nw",
            tags=tags,
        )

    def _draw_connector(
        self,
        document: Document,
        connector: ConnectorShape,
        zoom: float,
        pan: tuple[float, float],
        flow_color: str,
        animation_phase: int | None,
    ) -> None:
        points = document.connector_points(connector)
        if len(points) < 2:
            return
        tags = (CANVAS_TAG, CONNECTOR_TAG, f"connector:{connector.id}")
        flat = self._flat(points, zoom, pan)
        smooth = connector.kind == "bezier"
        options = self._arrow_options(connector)
        self.canvas.create_line(
            *flat,
            fill=connector.style.stroke,
            width=self._stroke_width(connector.style.stroke_width, zoom),
            dash=self._dash(connector.style.dash),
            smooth=smooth,
            tags=tags,
            **options,
        )
        if animation_phase is not None:
            self._draw_connector_flow(points, zoom, pan, flow_color, animation_phase, tags)

    def _draw_connector_flow(
        self,
        points: list[tuple[float, float]],
        zoom: float,
        pan: tuple[float, float],
        color: str,
        phase: int,
        tags: tuple[str, ...],
    ) -> None:
        screen_points = [self._screen(x, y, zoom, pan) for x, y in points]
        spacing = max(12, round(28 * zoom))
        radius = max(2, round(2 * zoom))
        cursor = phase % spacing
        for a, b in zip(screen_points, screen_points[1:]):
            ax, ay = a
            bx, by = b
            length = math.hypot(bx - ax, by - ay)
            if length <= 0:
                continue
            dx = (bx - ax) / length
            dy = (by - ay) / length
            dist = cursor
            while dist < length:
                px = ax + dx * dist
                py = ay + dy * dist
                self.canvas.create_oval(
                    px - radius, py - radius, px + radius, py + radius,
                    fill=color,
                    outline="",
                    tags=tags + ("native_connector_flow",),
                )
                dist += spacing
            cursor = (cursor - length) % spacing

    def _draw_selection_overlay(
        self,
        document: Document,
        selected_ids: set[str],
        zoom: float,
        pan: tuple[float, float],
        color: str,
        handle_fill: str,
    ) -> None:
        bounds = [shape.bounds() for shape in document.shapes if shape.id in selected_ids]
        if not bounds:
            return
        x1 = min(item[0] for item in bounds)
        y1 = min(item[1] for item in bounds)
        x2 = max(item[2] for item in bounds)
        y2 = max(item[3] for item in bounds)
        sx1, sy1 = self._screen(x1, y1, zoom, pan)
        sx2, sy2 = self._screen(x2, y2, zoom, pan)
        tags = (CANVAS_TAG, SELECTION_TAG)
        self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline=color, dash=(6, 4), width=1, tags=tags)
        cx = (sx1 + sx2) / 2
        cy = (sy1 + sy2) / 2
        for x, y in [
            (sx1, sy1), (cx, sy1), (sx2, sy1), (sx2, cy),
            (sx2, sy2), (cx, sy2), (sx1, sy2), (sx1, cy),
        ]:
            r = 4
            self.canvas.create_rectangle(x - r, y - r, x + r, y + r, fill=handle_fill, outline=color, tags=tags)

    def _draw_guides(
        self,
        width: int,
        height: int,
        guides: list[tuple[str, float]],
        zoom: float,
        pan: tuple[float, float],
        color: str,
    ) -> None:
        tags = (CANVAS_TAG, GUIDE_TAG)
        for kind, value in guides:
            if kind == "vline":
                sx = value * zoom + pan[0]
                self.canvas.create_line(sx, 0, sx, height, fill=color, dash=(4, 4), tags=tags)
            elif kind == "hline":
                sy = value * zoom + pan[1]
                self.canvas.create_line(0, sy, width, sy, fill=color, dash=(4, 4), tags=tags)

    def _draw_replay_frame(self, frame: ReplayFrame, zoom: float, pan: tuple[float, float], color: str) -> None:
        tags = (CANVAS_TAG, REPLAY_TAG)
        r = max(2, round(2 * zoom))
        for x, y in frame.points:
            sx, sy = self._screen(x, y, zoom, pan)
            self.canvas.create_rectangle(sx - r, sy - r, sx + r, sy + r, fill=color, outline=color, tags=tags)

    def _create_oval_world(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        outline: str,
        fill: str,
        width: int,
        zoom: float,
        pan: tuple[float, float],
        tags: tuple[str, ...],
    ) -> None:
        sx1, sy1 = self._screen(x1, y1, zoom, pan)
        sx2, sy2 = self._screen(x2, y2, zoom, pan)
        self.canvas.create_oval(sx1, sy1, sx2, sy2, outline=outline, fill=fill, width=width, tags=tags)

    def _screen(self, x: float, y: float, zoom: float, pan: tuple[float, float]) -> tuple[float, float]:
        return x * zoom + pan[0], y * zoom + pan[1]

    def _flat(self, points: list[tuple[float, float]], zoom: float, pan: tuple[float, float]) -> list[float]:
        flat: list[float] = []
        for x, y in points:
            sx, sy = self._screen(x, y, zoom, pan)
            flat.extend((sx, sy))
        return flat

    def _stroke_width(self, width: int | float, zoom: float) -> int:
        return max(1, round(float(width) * zoom))

    def _dash(self, dash: list[int] | None) -> tuple[int, ...] | None:
        if not dash:
            return None
        return tuple(max(1, int(value)) for value in dash)

    def _font(self, size: int | float, bold: bool, zoom: float) -> tuple[str, int, str]:
        return ("Microsoft YaHei", max(8, round(float(size) * zoom)), "bold" if bold else "normal")

    def _arrow_options(self, connector: ConnectorShape) -> dict:
        start = connector.arrow_start != "none"
        end = connector.arrow_end != "none"
        if not start and not end:
            return {}
        arrow = "both" if start and end else ("first" if start else "last")
        return {"arrow": arrow, "arrowshape": (12, 14, 5)}
