from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

from algorithms.transform import Matrix3, Point
from core.style import ShapeStyle


def new_id(prefix: str = "shape") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class FlowchartShape:
    kind: str
    x: float
    y: float
    width: float
    height: float
    text: str = ""
    style: ShapeStyle = field(default_factory=ShapeStyle)
    id: str = field(default_factory=new_id)
    z_order: int = 0
    rotation: float = 0.0
    flip_x: bool = False
    flip_y: bool = False

    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)

    def outline_points(self, segments: int = 48) -> list[tuple[float, float]]:
        x, y, w, h = self.x, self.y, self.width, self.height
        if self.kind == "decision":
            points = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
        elif self.kind == "data":
            slant = min(w * 0.18, 30)
            points = [(x + slant, y), (x + w, y), (x + w - slant, y + h), (x, y + h)]
        elif self.kind == "terminal":
            cx, cy = x + w / 2, y + h / 2
            points = [
                (cx + math.cos(2 * math.pi * index / segments) * w / 2, cy + math.sin(2 * math.pi * index / segments) * h / 2)
                for index in range(segments)
            ]
        elif self.kind == "document":
            wave = []
            for index in range(12):
                t = index / 11
                wave.append((x + w * (1 - t), y + h - 8 * math.sin(math.pi * 2 * t)))
            points = [(x, y), (x + w, y), (x + w, y + h - 6)] + wave + [(x, y + h)]
        # ── General geometric shapes ──────────────────────────────────
        elif self.kind in ("circle", "ellipse"):
            cx, cy = x + w / 2, y + h / 2
            points = [
                (cx + math.cos(2 * math.pi * i / segments) * w / 2,
                 cy + math.sin(2 * math.pi * i / segments) * h / 2)
                for i in range(segments)
            ]
        elif self.kind == "star5":
            cx, cy = x + w / 2, y + h / 2
            outer_r_x, outer_r_y = w / 2, h / 2
            inner_r_x, inner_r_y = w / 4.5, h / 4.5
            pts = []
            for i in range(10):
                angle = math.pi / 2 + i * math.pi / 5  # start from top
                rx, ry = (outer_r_x, outer_r_y) if i % 2 == 0 else (inner_r_x, inner_r_y)
                pts.append((cx + math.cos(angle) * rx, cy - math.sin(angle) * ry))
            points = pts
        elif self.kind == "hexagon":
            cx, cy = x + w / 2, y + h / 2
            points = [
                (cx + math.cos(math.pi / 2 + i * math.pi / 3) * w / 2,
                 cy + math.sin(math.pi / 2 + i * math.pi / 3) * h / 2)
                for i in range(6)
            ]
        elif self.kind == "arrow_right":
            stem_y1, stem_y2 = y + h * 0.3, y + h * 0.7
            head_x = x + w * 0.6
            points = [
                (x, stem_y1), (head_x, stem_y1), (head_x, y),
                (x + w, y + h / 2),
                (head_x, y + h), (head_x, stem_y2), (x, stem_y2),
            ]
        elif self.kind == "cloud":
            # Approximate cloud with overlapping arcs via polygon
            cx, cy = x + w / 2, y + h / 2
            bumps = [
                (cx - w * 0.3, cy - h * 0.1, w * 0.22, h * 0.28),
                (cx,           cy - h * 0.2, w * 0.26, h * 0.32),
                (cx + w * 0.3, cy - h * 0.1, w * 0.22, h * 0.28),
                (cx + w * 0.42, cy + h * 0.12, w * 0.18, h * 0.24),
                (cx - w * 0.42, cy + h * 0.12, w * 0.18, h * 0.24),
            ]
            pts = []
            for bx, by, brx, bry in bumps:
                for i in range(10):
                    a = -math.pi / 2 + i * math.pi / 9
                    pts.append((bx + math.cos(a) * brx, by + math.sin(a) * bry))
            # convex hull approximation: just use the points, renderer fills via scanline
            points = pts
        # ── Org chart ────────────────────────────────────────────────
        elif self.kind == "org_box":
            r = min(w * 0.12, h * 0.25, 16)
            pts = []
            for corner_x, corner_y, a_start in [
                (x + r, y + r, math.pi), (x + w - r, y + r, -math.pi / 2),
                (x + w - r, y + h - r, 0), (x + r, y + h - r, math.pi / 2),
            ]:
                for i in range(7):
                    a = a_start + i * math.pi / 12
                    pts.append((corner_x + math.cos(a) * r, corner_y + math.sin(a) * r))
            points = pts
        # ── Circuit symbols (outline = bounding rect for hit-test; visuals in extra_segments) ──
        elif self.kind in ("resistor", "capacitor", "ground", "battery", "switch", "led", "inductor", "voltage_source"):
            points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        else:
            points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        matrix = self._local_matrix()
        return [_mat_apply(matrix, px, py) for px, py in points]

    def extra_segments(self) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        x, y, w, h = self.x, self.y, self.width, self.height
        cx, cy = x + w / 2, y + h / 2
        segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
        if self.kind == "subprocess":
            margin = min(18, w / 5)
            segs.extend([((x + margin, y), (x + margin, y + h)), ((x + w - margin, y), (x + w - margin, y + h))])
        elif self.kind == "database":
            segs.extend([((x, y + h * 0.22), (x, y + h * 0.82)), ((x + w, y + h * 0.22), (x + w, y + h * 0.82))])
        elif self.kind == "resistor":
            # Two lead wires + rectangle body
            bx1, bx2 = x + w * 0.2, x + w * 0.8
            by1, by2 = y + h * 0.25, y + h * 0.75
            segs += [
                ((x, cy), (bx1, cy)),       # left lead
                ((bx2, cy), (x + w, cy)),   # right lead
                ((bx1, by1), (bx2, by1)),   # top of body
                ((bx2, by1), (bx2, by2)),   # right of body
                ((bx2, by2), (bx1, by2)),   # bottom of body
                ((bx1, by2), (bx1, by1)),   # left of body
            ]
        elif self.kind == "capacitor":
            gap = h * 0.12
            segs += [
                ((x, cy), (cx - gap, cy)),          # left lead
                ((cx + gap, cy), (x + w, cy)),      # right lead
                ((cx - gap, y + h * 0.1), (cx - gap, y + h * 0.9)),  # left plate
                ((cx + gap, y + h * 0.1), (cx + gap, y + h * 0.9)),  # right plate
            ]
        elif self.kind == "ground":
            segs += [
                ((cx, y), (cx, cy)),                                        # vertical wire
                ((cx - w * 0.4, cy), (cx + w * 0.4, cy)),                  # top bar (widest)
                ((cx - w * 0.27, cy + h * 0.2), (cx + w * 0.27, cy + h * 0.2)),  # mid bar
                ((cx - w * 0.14, cy + h * 0.4), (cx + w * 0.14, cy + h * 0.4)),  # bottom bar
            ]
        elif self.kind == "battery":
            # alternating long/short vertical bars + leads
            bar_xs = [cx - w * 0.2, cx - w * 0.07, cx + w * 0.07, cx + w * 0.2]
            heights = [h * 0.6, h * 0.35, h * 0.6, h * 0.35]
            segs += [((x, cy), (bar_xs[0], cy)), ((bar_xs[-1], cy), (x + w, cy))]
            for bx, bh in zip(bar_xs, heights):
                segs.append(((bx, cy - bh / 2), (bx, cy + bh / 2)))
        elif self.kind == "switch":
            # two terminals + open switch arm
            segs += [
                ((x, cy), (x + w * 0.3, cy)),              # left terminal wire
                ((x + w * 0.7, cy), (x + w, cy)),          # right terminal wire
                ((x + w * 0.3, cy), (x + w * 0.7, cy - h * 0.35)),  # switch arm (open)
                # terminal dots (short cross marks)
                ((x + w * 0.3, cy - h * 0.08), (x + w * 0.3, cy + h * 0.08)),
                ((x + w * 0.7, cy - h * 0.08), (x + w * 0.7, cy + h * 0.08)),
            ]
        elif self.kind == "led":
            # triangle (diode) + vertical bar + two emission arrows
            tip_x = cx + w * 0.15
            base_x = cx - w * 0.15
            segs += [
                ((x, cy), (base_x, cy)),                    # left lead
                ((tip_x, cy), (x + w, cy)),                 # right lead
                ((base_x, y + h * 0.2), (base_x, y + h * 0.8)),  # base vertical
                ((base_x, y + h * 0.2), (tip_x, cy)),      # triangle top edge
                ((base_x, y + h * 0.8), (tip_x, cy)),      # triangle bottom edge
                ((tip_x, y + h * 0.2), (tip_x, y + h * 0.8)),    # cathode bar
                # emission arrows (diagonal lines suggesting light)
                ((tip_x + w * 0.06, y + h * 0.15), (tip_x + w * 0.18, y + h * 0.02)),
                ((tip_x + w * 0.12, y + h * 0.22), (tip_x + w * 0.24, y + h * 0.09)),
            ]
        elif self.kind == "inductor":
            # coil: sequence of semi-arc bumps as line approximations
            coils = 4
            coil_w = w * 0.6 / coils
            start_x = cx - w * 0.3
            arc_pts = []
            for i in range(coils):
                bx = start_x + i * coil_w + coil_w / 2
                for j in range(9):
                    a = math.pi - j * math.pi / 8
                    arc_pts.append((bx + math.cos(a) * coil_w / 2, cy - math.sin(a) * h * 0.3))
            for a_pt, b_pt in zip(arc_pts, arc_pts[1:]):
                segs.append((a_pt, b_pt))
            segs += [((x, cy), (start_x, cy)), ((start_x + coils * coil_w, cy), (x + w, cy))]
        elif self.kind == "voltage_source":
            # circle + plus/minus labels inside (drawn as cross lines)
            r = min(w, h) * 0.38
            # circle approximated via extra_segments not possible directly;
            # draw plus on right half and minus on left half
            segs += [
                ((x, cy), (cx - r, cy)),         # left lead
                ((cx + r, cy), (x + w, cy)),     # right lead
                # plus sign (right side)
                ((cx + r * 0.4, cy), (cx + r * 0.8, cy)),
                ((cx + r * 0.6, cy - r * 0.2), (cx + r * 0.6, cy + r * 0.2)),
                # minus sign (left side)
                ((cx - r * 0.8, cy), (cx - r * 0.4, cy)),
            ]
        matrix = self._local_matrix()
        return [(_mat_apply(matrix, *a), _mat_apply(matrix, *b)) for a, b in segs]

    def _local_matrix(self) -> "Matrix3":
        """Build the combined flip+rotation transform matrix once for this shape."""
        center = self.center()
        matrix = Matrix3.identity()
        if self.flip_x or self.flip_y:
            matrix = Matrix3.reflection(horizontal=self.flip_x, vertical=self.flip_y, center=center) @ matrix
        if self.rotation:
            matrix = Matrix3.rotation(math.radians(self.rotation), center=center) @ matrix
        return matrix

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def scale(self, factor: float) -> None:
        center = self.center()
        self.width = max(12, self.width * factor)
        self.height = max(12, self.height * factor)
        self.x = center.x - self.width / 2
        self.y = center.y - self.height / 2

    def rotate(self, angle_degrees: float) -> None:
        self.rotation = (self.rotation + angle_degrees) % 360

    def flip_horizontal(self) -> None:
        self.flip_x = not self.flip_x

    def flip_vertical(self) -> None:
        self.flip_y = not self.flip_y

    def bounds(self) -> tuple[float, float, float, float]:
        points = self.outline_points()
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        return min(xs), min(ys), max(xs), max(ys)

    def hit_test(self, x: float, y: float) -> bool:
        x1, y1, x2, y2 = self.bounds()
        return x1 <= x <= x2 and y1 <= y <= y2

    def anchors(self) -> dict[str, tuple[float, float]]:
        x1, y1, x2, y2 = self.bounds()
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        return {"top": (cx, y1), "bottom": (cx, y2), "left": (x1, cy), "right": (x2, cy)}

    def anchor(self, side: str) -> tuple[float, float]:
        a = self.anchors()
        return a.get(side, a["bottom"])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "flowchart",
            "kind": self.kind,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "text": self.text,
            "style": self.style.to_dict(),
            "z_order": self.z_order,
            "rotation": self.rotation,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "FlowchartShape":
        return cls(
            kind=payload["kind"],
            x=float(payload["x"]),
            y=float(payload["y"]),
            width=float(payload["width"]),
            height=float(payload["height"]),
            text=payload.get("text", ""),
            style=ShapeStyle.from_dict(payload.get("style")),
            id=payload.get("id", new_id()),
            z_order=int(payload.get("z_order", 0)),
            rotation=float(payload.get("rotation", 0)),
            flip_x=bool(payload.get("flip_x", False)),
            flip_y=bool(payload.get("flip_y", False)),
        )


@dataclass
class LineShape:
    x1: float
    y1: float
    x2: float
    y2: float
    style: ShapeStyle = field(default_factory=lambda: ShapeStyle(fill=None))
    id: str = field(default_factory=lambda: new_id("line"))
    z_order: int = 0

    def move(self, dx: float, dy: float) -> None:
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy

    def center(self) -> Point:
        return Point((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def scale(self, factor: float) -> None:
        center = self.center()
        self.x1 = center.x + (self.x1 - center.x) * factor
        self.y1 = center.y + (self.y1 - center.y) * factor
        self.x2 = center.x + (self.x2 - center.x) * factor
        self.y2 = center.y + (self.y2 - center.y) * factor

    def rotate(self, angle_degrees: float) -> None:
        center = self.center()
        matrix = Matrix3.rotation(math.radians(angle_degrees), center=center)
        p1 = matrix.apply(Point(self.x1, self.y1))
        p2 = matrix.apply(Point(self.x2, self.y2))
        self.x1, self.y1, self.x2, self.y2 = p1.x, p1.y, p2.x, p2.y

    def flip_horizontal(self) -> None:
        center = self.center()
        self.x1 = center.x - (self.x1 - center.x)
        self.x2 = center.x - (self.x2 - center.x)

    def flip_vertical(self) -> None:
        center = self.center()
        self.y1 = center.y - (self.y1 - center.y)
        self.y2 = center.y - (self.y2 - center.y)

    def bounds(self) -> tuple[float, float, float, float]:
        return min(self.x1, self.x2), min(self.y1, self.y2), max(self.x1, self.x2), max(self.y1, self.y2)

    def hit_test(self, x: float, y: float) -> bool:
        return _point_segment_distance(x, y, self.x1, self.y1, self.x2, self.y2) <= 7

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "line",
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "style": self.style.to_dict(),
            "z_order": self.z_order,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "LineShape":
        return cls(
            x1=float(payload["x1"]),
            y1=float(payload["y1"]),
            x2=float(payload["x2"]),
            y2=float(payload["y2"]),
            style=ShapeStyle.from_dict(payload.get("style")),
            id=payload.get("id", new_id("line")),
            z_order=int(payload.get("z_order", 0)),
        )


@dataclass
class TextShape:
    x: float
    y: float
    text: str
    style: ShapeStyle = field(default_factory=lambda: ShapeStyle(fill=None))
    id: str = field(default_factory=lambda: new_id("text"))
    z_order: int = 0

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def bounds(self) -> tuple[float, float, float, float]:
        lines = self.text.split("\n") if self.text else [""]
        width = max(24, max(len(line) for line in lines) * self.style.font_size * 0.6)
        height = len(lines) * self.style.font_size * 1.5
        return self.x, self.y, self.x + width, self.y + height

    def hit_test(self, x: float, y: float) -> bool:
        x1, y1, x2, y2 = self.bounds()
        return x1 <= x <= x2 and y1 <= y <= y2

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "text",
            "x": self.x,
            "y": self.y,
            "text": self.text,
            "style": self.style.to_dict(),
            "z_order": self.z_order,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TextShape":
        return cls(
            x=float(payload["x"]),
            y=float(payload["y"]),
            text=payload.get("text", ""),
            style=ShapeStyle.from_dict(payload.get("style")),
            id=payload.get("id", new_id("text")),
            z_order=int(payload.get("z_order", 0)),
        )


@dataclass
class ConnectorShape:
    start_shape_id: str
    end_shape_id: str
    start_anchor: str = "right"
    end_anchor: str = "left"
    kind: str = "elbow"
    arrow_end: str = "arrow"
    arrow_start: str = "none"
    style: ShapeStyle = field(default_factory=lambda: ShapeStyle(fill=None, stroke="#A7C7FF"))
    id: str = field(default_factory=lambda: new_id("conn"))
    z_order: int = 10_000

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "connector",
            "start_shape_id": self.start_shape_id,
            "end_shape_id": self.end_shape_id,
            "start_anchor": self.start_anchor,
            "end_anchor": self.end_anchor,
            "kind": self.kind,
            "arrow_end": self.arrow_end,
            "arrow_start": self.arrow_start,
            "style": self.style.to_dict(),
            "z_order": self.z_order,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ConnectorShape":
        return cls(
            start_shape_id=payload["start_shape_id"],
            end_shape_id=payload["end_shape_id"],
            start_anchor=payload.get("start_anchor", "right"),
            end_anchor=payload.get("end_anchor", "left"),
            kind=payload.get("kind", "elbow"),
            arrow_end=payload.get("arrow_end", "arrow"),
            arrow_start=payload.get("arrow_start", "none"),
            style=ShapeStyle.from_dict(payload.get("style")),
            id=payload.get("id", new_id("conn")),
            z_order=int(payload.get("z_order", 10_000)),
        )


Shape = FlowchartShape | LineShape | TextShape


def shape_from_dict(payload: dict) -> Shape:
    shape_type = payload.get("type")
    if shape_type == "flowchart":
        return FlowchartShape.from_dict(payload)
    if shape_type == "line":
        return LineShape.from_dict(payload)
    if shape_type == "text":
        return TextShape.from_dict(payload)
    raise ValueError(f"Unsupported shape type: {shape_type!r}")


def _mat_apply(matrix: "Matrix3", px: float, py: float) -> tuple[float, float]:
    transformed = matrix.apply(Point(px, py))
    return transformed.x, transformed.y


def _point_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
