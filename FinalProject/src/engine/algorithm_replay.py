from __future__ import annotations

from dataclasses import dataclass

from algorithms.circle import midpoint_circle
from algorithms.ellipse import midpoint_ellipse
from algorithms.fill import scanline_fill
from algorithms.line import bresenham_line
from core.shapes import CurveShape, FlowchartShape, LineShape, Shape
from engine.animation import sampled_polyline_pixels


Point = tuple[int | float, int | float]
Pixel = tuple[int, int]

CIRCUIT_KINDS = {
    "resistor", "capacitor", "ground", "battery",
    "switch", "led", "inductor", "voltage_source",
}


@dataclass(frozen=True)
class ReplayFrame:
    label: str
    points: list[Pixel]


@dataclass(frozen=True)
class ReplaySequence:
    title: str
    frames: list[ReplayFrame]


def build_shape_replay(shape: Shape, frame_count: int = 36) -> ReplaySequence:
    """Build cumulative algorithm frames for one editable shape."""
    frame_count = max(1, int(frame_count))
    if isinstance(shape, LineShape):
        pixels = bresenham_line(round(shape.x1), round(shape.y1), round(shape.x2), round(shape.y2))
        return ReplaySequence("Bresenham 直线生成", _cumulative_frames("Bresenham 逐点描线", pixels, frame_count))
    if isinstance(shape, CurveShape):
        pixels = sampled_polyline_pixels(shape.points)
        return ReplaySequence("Catmull-Rom / Bezier 曲线采样", _cumulative_frames("曲线采样点描线", pixels, frame_count))
    if isinstance(shape, FlowchartShape):
        title, outline = _flowchart_outline_pixels(shape)
        frames = _cumulative_frames(title, outline, frame_count)
        if shape.kind not in CIRCUIT_KINDS and shape.style.fill is not None:
            fill_points = [(round(x), round(y)) for x, y in scanline_fill(shape.outline_points())]
            frames.extend(_cumulative_frames("扫描线填充 AET", fill_points, frame_count))
        return ReplaySequence(title, frames)
    return ReplaySequence("暂不支持该图元回放", [ReplayFrame("无像素", [])])


def _flowchart_outline_pixels(shape: FlowchartShape) -> tuple[str, list[Pixel]]:
    if shape.kind in CIRCUIT_KINDS:
        pixels: list[Pixel] = []
        for start, end in shape.extra_segments():
            pixels.extend(sampled_polyline_pixels([start, end]))
        return "Bresenham 电路符号线段", _dedupe_pixels(pixels)

    if not shape.rotation and not shape.flip_x and not shape.flip_y:
        cx = round(shape.x + shape.width / 2)
        cy = round(shape.y + shape.height / 2)
        rx = round(abs(shape.width) / 2)
        ry = round(abs(shape.height) / 2)
        if shape.kind == "circle" and abs(shape.width - shape.height) < 1:
            return "中点圆八分对称生成", midpoint_circle(cx, cy, max(1, rx))
        if shape.kind in {"circle", "ellipse", "terminal"}:
            return "中点椭圆分区生成", midpoint_ellipse(cx, cy, max(1, rx), max(1, ry))

    outline = shape.outline_points()
    pixels = sampled_polyline_pixels(outline + [outline[0]]) if outline else []
    for start, end in shape.extra_segments():
        pixels.extend(sampled_polyline_pixels([start, end]))
    return "Bresenham 多边形轮廓生成", _dedupe_pixels(pixels)


def _cumulative_frames(label: str, pixels: list[Pixel], frame_count: int) -> list[ReplayFrame]:
    if not pixels:
        return [ReplayFrame(label, [])]
    count = min(max(1, frame_count), len(pixels))
    frames: list[ReplayFrame] = []
    for index in range(1, count + 1):
        end = max(1, round(len(pixels) * index / count))
        frames.append(ReplayFrame(label, pixels[:end]))
    if frames[-1].points != pixels:
        frames.append(ReplayFrame(label, pixels))
    return frames


def _dedupe_pixels(pixels: list[Pixel]) -> list[Pixel]:
    result: list[Pixel] = []
    seen: set[Pixel] = set()
    for point in pixels:
        if point in seen:
            continue
        seen.add(point)
        result.append(point)
    return result
