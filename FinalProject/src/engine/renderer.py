from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from algorithms.bezier import catmull_rom_polyline, cubic_bezier
from algorithms.circle import midpoint_circle
from algorithms.ellipse import midpoint_ellipse
from algorithms.fill import scanline_fill
from algorithms.line import bresenham_line, dashed_line
from core.document import Document
from core.shapes import ConnectorShape, CurveShape, FlowchartShape, LineShape, TextShape
from engine.animation import animated_flow_pixels
from engine.algorithm_replay import ReplayFrame


Color = tuple[int, int, int, int]

CIRCUIT_KINDS = {
    "resistor", "capacitor", "ground", "battery",
    "switch", "led", "inductor", "voltage_source",
}

SMOOTHNESS_STEPS = {1: 4, 2: 10, 3: 20, 4: 40, 5: 80}


class Renderer:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

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
    ) -> Image.Image:
        ch = chrome or {}
        grid_color = ch.get("grid", "#2A2A3E")
        sel_color = ch.get("selection", "#5BA8FF")
        sel_handle_fill = ch.get("selection_handle_fill", "#1E1E2E")
        guide_color = ch.get("guide", "#FF4444")
        connector_flow_color = ch.get("connector_flow", "#5BFFCF")
        replay_color = ch.get("replay", "#FFCF5A")
        image = Image.new("RGBA", (self.width, self.height), _color(document.background))
        pixels = image.load()
        if show_grid:
            self._draw_grid(pixels, document.grid_size, zoom, pan, grid_color)
        for shape in sorted(document.shapes, key=lambda item: item.z_order):
            self._draw_shape(image, pixels, shape, zoom, pan, draft=draft)
        for connector in document.connectors:
            self._draw_connector(
                pixels, document, connector, zoom, pan,
                animation_phase=connector_animation_phase,
                flow_color=connector_flow_color,
            )
        if selected_ids:
            self._draw_selection_overlay(pixels, document, selected_ids, zoom, pan, sel_color, sel_handle_fill)
        if guides:
            self._draw_guides(pixels, guides, zoom, pan, guide_color)
        if replay_frame is not None:
            self._draw_replay_frame(pixels, replay_frame, zoom, pan, replay_color)
        return image

    def _draw_grid(self, pixels, grid_size: int, zoom: float, pan: tuple[float, float], color: str = "#2A2A3E") -> None:
        spacing = max(8, round(grid_size * zoom))
        offset_x = round(pan[0] % spacing)
        offset_y = round(pan[1] % spacing)
        for x in range(offset_x, self.width, spacing):
            _draw_line(pixels, (x, 0), (x, self.height - 1), color)
        for y in range(offset_y, self.height, spacing):
            _draw_line(pixels, (0, y), (self.width - 1, y), color)

    def _draw_shape(self, image: Image.Image, pixels, shape, zoom: float, pan: tuple[float, float], draft: bool = False) -> None:
        if isinstance(shape, FlowchartShape):
            points = [self._world_to_screen(point, zoom, pan) for point in shape.outline_points()]
            is_circuit = shape.kind in CIRCUIT_KINDS
            if not draft and not is_circuit:
                _fill_polygon(pixels, points, shape.style.fill)
            if not is_circuit:
                _draw_polyline(pixels, points + [points[0]], shape.style.stroke, max(1, round(shape.style.stroke_width * zoom)), shape.style.dash)
            for a, b in shape.extra_segments():
                _draw_line(pixels, self._world_to_screen(a, zoom, pan), self._world_to_screen(b, zoom, pan), shape.style.stroke, max(1, round(shape.style.stroke_width * zoom)))
            if shape.kind == "database":
                x1, y1, x2, y2 = shape.bounds()
                cx = (x1 + x2) / 2
                rx = (x2 - x1) / 2
                ry = max(4, (y2 - y1) * 0.14)
                for cy in (y1 + ry, y2 - ry):
                    _draw_ellipse(pixels, self._world_to_screen((cx, cy), zoom, pan), rx * zoom, ry * zoom, shape.style.stroke, None, max(1, round(shape.style.stroke_width * zoom)))
            elif shape.kind == "voltage_source":
                x1, y1, x2, y2 = shape.bounds()
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                r = min(x2 - x1, y2 - y1) * 0.35
                _draw_ellipse(pixels, self._world_to_screen((cx, cy), zoom, pan), r * zoom, r * zoom, shape.style.stroke, None, max(1, round(shape.style.stroke_width * zoom)))
            if shape.text:
                text_bounds = shape.bounds()
                if shape.kind == "inductor":
                    # Coils occupy the upper half, so push the label below.
                    x1, y1, x2, y2 = text_bounds
                    text_bounds = (x1, (y1 + y2) / 2, x2, y2)
                self._draw_text(image, shape.text, text_bounds, shape.style, zoom, pan)
        elif isinstance(shape, LineShape):
            _draw_line(
                pixels,
                self._world_to_screen((shape.x1, shape.y1), zoom, pan),
                self._world_to_screen((shape.x2, shape.y2), zoom, pan),
                shape.style.stroke,
                max(1, round(shape.style.stroke_width * zoom)),
                shape.style.dash,
            )
        elif isinstance(shape, CurveShape):
            if len(shape.points) < 2:
                return
            steps = SMOOTHNESS_STEPS.get(getattr(shape.style, "smoothness", 3), 20)
            sample = catmull_rom_polyline(shape.points, steps_per_segment=steps)
            screen_pts = [self._world_to_screen(p, zoom, pan) for p in sample]
            _draw_polyline(pixels, screen_pts, shape.style.stroke,
                           max(1, round(shape.style.stroke_width * zoom)), shape.style.dash)
        elif isinstance(shape, TextShape):
            self._draw_text(image, shape.text, shape.bounds(), shape.style, zoom, pan)

    def _draw_connector(
        self,
        pixels,
        document: Document,
        connector: ConnectorShape,
        zoom: float,
        pan: tuple[float, float],
        animation_phase: int | None = None,
        flow_color: str = "#5BFFCF",
    ) -> None:
        points = [self._world_to_screen(point, zoom, pan) for point in document.connector_points(connector)]
        if len(points) < 2:
            return
        width = max(1, round(connector.style.stroke_width * zoom))
        _draw_polyline(pixels, points, connector.style.stroke, width, connector.style.dash or None)
        if animation_phase is not None:
            flow_pixels = animated_flow_pixels(
                points,
                phase=animation_phase,
                spacing=max(10, round(24 * zoom)),
                pulse_length=max(3, round(7 * zoom)),
            )
            _draw_points(pixels, flow_pixels, flow_color, max(2, width + 1))
        if connector.arrow_end != "none":
            _draw_arrowhead(pixels, points[-2], points[-1], connector.style.stroke, connector.arrow_end)
        if connector.arrow_start != "none":
            _draw_arrowhead(pixels, points[1], points[0], connector.style.stroke, connector.arrow_start)

    def _draw_replay_frame(
        self,
        pixels,
        frame: ReplayFrame,
        zoom: float,
        pan: tuple[float, float],
        color: str = "#FFCF5A",
    ) -> None:
        points = [self._world_to_screen(point, zoom, pan) for point in frame.points]
        _draw_points(pixels, points, color, 3)

    def _draw_selection(self, pixels, bounds: tuple[float, float, float, float], zoom: float, pan: tuple[float, float], color: str = "#5BA8FF", handle_fill: str = "#1E1E2E") -> None:
        x1, y1 = self._world_to_screen((bounds[0], bounds[1]), zoom, pan)
        x2, y2 = self._world_to_screen((bounds[2], bounds[3]), zoom, pan)
        _draw_polyline(pixels, [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)], color, 1, [6, 4])
        for x, y in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
            _fill_polygon(pixels, [(x - 3, y - 3), (x + 3, y - 3), (x + 3, y + 3), (x - 3, y + 3)], handle_fill)
            _draw_polyline(pixels, [(x - 3, y - 3), (x + 3, y - 3), (x + 3, y + 3), (x - 3, y + 3), (x - 3, y - 3)], color)

    def _draw_guides(self, pixels, guides: list[tuple[str, float]], zoom: float, pan: tuple[float, float], color: str = "#FF4444") -> None:
        for kind, value in guides:
            if kind == "vline":
                sx = round(value * zoom + pan[0])
                _draw_line(pixels, (sx, 0), (sx, self.height - 1), color, 1)
            elif kind == "hline":
                sy = round(value * zoom + pan[1])
                _draw_line(pixels, (0, sy), (self.width - 1, sy), color, 1)

    def _draw_selection_overlay(self, pixels, document: Document, selected_ids: set[str], zoom: float, pan: tuple[float, float], color: str = "#5BA8FF", handle_fill: str = "#1E1E2E") -> None:
        bounds = [shape.bounds() for shape in document.shapes if shape.id in selected_ids]
        if not bounds:
            return
        union = (
            min(item[0] for item in bounds),
            min(item[1] for item in bounds),
            max(item[2] for item in bounds),
            max(item[3] for item in bounds),
        )
        self._draw_selection(pixels, union, zoom, pan, color, handle_fill)

    def _draw_text(
        self,
        image: Image.Image,
        text: str,
        bounds: tuple[float, float, float, float],
        style,
        zoom: float,
        pan: tuple[float, float],
    ) -> None:
        draw = ImageDraw.Draw(image)
        font = _load_font(max(8, round(style.font_size * zoom)), bold=style.bold)
        x1, y1 = self._world_to_screen((bounds[0], bounds[1]), zoom, pan)
        x2, y2 = self._world_to_screen((bounds[2], bounds[3]), zoom, pan)
        lines = text.split("\n")
        sample_bbox = draw.textbbox((0, 0), "Ag中", font=font)
        line_height = sample_bbox[3] - sample_bbox[1] + 4
        total_height = line_height * len(lines)
        start_y = y1 + (y2 - y1 - total_height) / 2
        align = getattr(style, "text_align", "center")
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            if align == "left":
                lx = x1 + 4
            elif align == "right":
                lx = x2 - tw - 4
            else:
                lx = x1 + (x2 - x1 - tw) / 2
            ly = start_y + i * line_height
            draw.text((lx, ly), line, fill=_color(style.text_color), font=font)

    def _world_to_screen(self, point: tuple[float, float], zoom: float, pan: tuple[float, float]) -> tuple[int, int]:
        return round(point[0] * zoom + pan[0]), round(point[1] * zoom + pan[1])


def _draw_line(
    pixels,
    start: tuple[int | float, int | float],
    end: tuple[int | float, int | float],
    color,
    width: int = 1,
    dash: list[int] | None = None,
) -> None:
    if dash:
        points = dashed_line(round(start[0]), round(start[1]), round(end[0]), round(end[1]), dash)
    else:
        points = bresenham_line(round(start[0]), round(start[1]), round(end[0]), round(end[1]))
    _draw_points(pixels, points, color, width)


def _draw_polyline(
    pixels,
    points: list[tuple[int | float, int | float]],
    color,
    width: int = 1,
    dash: list[int] | None = None,
) -> None:
    if not dash:
        for a, b in zip(points, points[1:]):
            _draw_line(pixels, a, b, color, width, None)
        return
    # dash 在多段间相位连续：避免每小段重置 pattern 导致采样过密的曲线
    # 看起来都是实线（pattern 永远停在第一个 "on" 区间）。
    # 同时按笔头宽度缩放 pattern，否则粗笔头会把 gap 涂满。
    scale = max(1, width)
    clean_pattern = [max(1, int(length) * scale) for length in dash]
    period = sum(clean_pattern)
    phase = 0
    for a, b in zip(points, points[1:]):
        seg = bresenham_line(round(a[0]), round(a[1]), round(b[0]), round(b[1]))
        kept = []
        for i, point in enumerate(seg):
            cursor = (i + phase) % period
            total = 0
            draw = True
            for length in clean_pattern:
                total += length
                if cursor < total:
                    break
                draw = not draw
            if draw:
                kept.append(point)
        _draw_points(pixels, kept, color, width)
        phase = (phase + len(seg)) % period if period else 0


def _draw_points(pixels, points: list[tuple[int | float, int | float]], color, width: int = 1) -> None:
    rgba = _color(color)
    radius = max(0, width // 2)
    for x, y in points:
        if radius == 0:
            _put_pixel(pixels, x, y, rgba)
            continue
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    _put_pixel(pixels, x + dx, y + dy, rgba)


def _fill_polygon(pixels, points: list[tuple[int | float, int | float]], color) -> None:
    if color is None:
        return
    rgba = _color(color)
    for x, y in scanline_fill(points):
        _put_pixel(pixels, x, y, rgba)


def _draw_ellipse(
    pixels,
    center: tuple[int | float, int | float],
    rx: float,
    ry: float,
    stroke,
    fill=None,
    width: int = 1,
) -> None:
    cx, cy = center
    if fill is not None:
        for y in range(round(cy - ry), round(cy + ry) + 1):
            if ry == 0:
                span = rx
            else:
                dy = (y - cy) / ry
                if dy * dy > 1:
                    continue
                span = abs(rx) * math.sqrt(1 - dy * dy)
            _draw_line(pixels, (cx - span, y), (cx + span, y), fill)
    _draw_points(pixels, midpoint_ellipse(round(cx), round(cy), round(rx), round(ry)), stroke, width)


def _draw_arrowhead(pixels, start: tuple[int, int], end: tuple[int, int], color, style: str = "arrow") -> None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux = dx / length
    uy = dy / length
    size = 12
    if style in ("arrow", "open_arrow"):
        left = (end[0] - ux * size - uy * size * 0.45, end[1] - uy * size + ux * size * 0.45)
        right = (end[0] - ux * size + uy * size * 0.45, end[1] - uy * size - ux * size * 0.45)
        if style == "arrow":
            _fill_polygon(pixels, [end, left, right], color)
            _draw_polyline(pixels, [end, left, right, end], color)
        else:
            _draw_polyline(pixels, [left, end, right], color, 2)
    elif style == "diamond":
        mid = (end[0] - ux * size, end[1] - uy * size)
        back = (end[0] - ux * size * 2, end[1] - uy * size * 2)
        left = (mid[0] - uy * size * 0.4, mid[1] + ux * size * 0.4)
        right = (mid[0] + uy * size * 0.4, mid[1] - ux * size * 0.4)
        _fill_polygon(pixels, [end, left, back, right], color)
        _draw_polyline(pixels, [end, left, back, right, end], color)
    elif style == "dot":
        cx = end[0] - ux * 6
        cy = end[1] - uy * 6
        r = 5
        _draw_points(pixels, midpoint_circle(round(cx), round(cy), r), color, 1)
        for dy_off in range(-r, r + 1):
            span = round(math.sqrt(max(0, r * r - dy_off * dy_off)))
            _draw_line(pixels, (cx - span, cy + dy_off), (cx + span, cy + dy_off), color)


def _put_pixel(pixels, x: int | float, y: int | float, color: Color) -> None:
    xi = round(x)
    yi = round(y)
    if xi < 0 or yi < 0:
        return
    try:
        pixels[xi, yi] = color
    except IndexError:
        return


def _color(value) -> Color:
    if value is None:
        return (0, 0, 0, 0)
    if isinstance(value, tuple):
        if len(value) == 3:
            return value[0], value[1], value[2], 255
        return value  # type: ignore[return-value]
    text = str(value).strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 6:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), 255
    if len(text) == 8:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), int(text[6:8], 16)
    raise ValueError(f"Unsupported color value: {value!r}")


_font_cache: dict[tuple[int, bool], ImageFont.ImageFont] = {}


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    if bold:
        candidates = [
            Path("C:/Windows/Fonts/msyhbd.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ]
    else:
        candidates = [
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]
    for path in candidates:
        if path.exists():
            font = ImageFont.truetype(str(path), size=size)
            _font_cache[key] = font
            return font
    font = ImageFont.load_default()
    _font_cache[key] = font
    return font
