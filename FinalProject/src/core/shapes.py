from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from PIL import Image

from algorithms.bezier import bezier_polyline
from algorithms.transform import Matrix3, Point
from core.style import ShapeStyle


def new_id(prefix: str = "shape") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# 图元 kind -> 中文名（图形库标签与图层面板共用的单一真源）
KIND_LABELS: dict[str, str] = {
    # 流程图
    "process": "处理框", "decision": "判断框", "terminal": "起止框",
    "data": "数据框", "document": "文档框", "database": "数据库", "subprocess": "子程序",
    # 通用图形
    "circle": "圆形", "ellipse": "椭圆", "triangle": "三角形",
    "trapezoid": "梯形", "parallelogram": "平行四边形", "org_box": "圆角矩形",
    "star5": "五角星", "hexagon": "六边形", "plus": "加号",
    "arrow_right": "右箭头", "arrow_left": "左箭头", "cloud": "云形",
    # 电路图
    "resistor": "电阻", "capacitor": "电容", "ground": "接地",
    "battery": "电池", "switch": "开关", "led": "LED",
    "inductor": "电感", "voltage_source": "电压源",
}


def _layer_dict(shape) -> dict:
    """图层公共字段序列化（可见性 / 锁定 / 自定义名称）。"""
    return {"visible": shape.visible, "locked": shape.locked, "name": shape.name}


def _layer_kwargs(payload: dict) -> dict:
    """从 payload 读取图层公共字段，缺省向后兼容旧存档。"""
    return {
        "visible": bool(payload.get("visible", True)),
        "locked": bool(payload.get("locked", False)),
        "name": str(payload.get("name", "")),
    }


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
    visible: bool = True
    locked: bool = False
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

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
        elif self.kind == "arrow_left":
            stem_y1, stem_y2 = y + h * 0.3, y + h * 0.7
            head_x = x + w * 0.4
            points = [
                (x + w, stem_y1), (head_x, stem_y1), (head_x, y),
                (x, y + h / 2),
                (head_x, y + h), (head_x, stem_y2), (x + w, stem_y2),
            ]
        elif self.kind == "triangle":
            points = [(x + w / 2, y), (x + w, y + h), (x, y + h)]
        elif self.kind == "trapezoid":
            inset = min(w * 0.18, 30)
            points = [(x + inset, y), (x + w - inset, y), (x + w, y + h), (x, y + h)]
        elif self.kind == "parallelogram":
            slant = min(w * 0.22, 36)
            points = [(x + slant, y), (x + w, y), (x + w - slant, y + h), (x, y + h)]
        elif self.kind == "plus":
            arm_w = w / 3
            arm_h = h / 3
            cx, cy = x + w / 2, y + h / 2
            points = [
                (cx - arm_w / 2, y),
                (cx + arm_w / 2, y),
                (cx + arm_w / 2, cy - arm_h / 2),
                (x + w, cy - arm_h / 2),
                (x + w, cy + arm_h / 2),
                (cx + arm_w / 2, cy + arm_h / 2),
                (cx + arm_w / 2, y + h),
                (cx - arm_w / 2, y + h),
                (cx - arm_w / 2, cy + arm_h / 2),
                (x, cy + arm_h / 2),
                (x, cy - arm_h / 2),
                (cx - arm_w / 2, cy - arm_h / 2),
            ]
        elif self.kind == "cloud":
            # Scalloped boundary: bumps walk clockwise around the cloud, each
            # contributing its outward-facing arc so the polygon is closed.
            cx, cy = x + w / 2, y + h / 2
            bumps = [
                (-0.30, -0.20, 0.22, 0.26),
                (-0.05, -0.32, 0.22, 0.28),
                ( 0.22, -0.26, 0.22, 0.26),
                ( 0.38,  0.00, 0.16, 0.22),
                ( 0.22,  0.26, 0.20, 0.22),
                (-0.05,  0.30, 0.22, 0.22),
                (-0.28,  0.24, 0.20, 0.22),
                (-0.40, -0.02, 0.16, 0.22),
            ]
            arc_sweep = math.pi * 1.15
            arc_steps = 9
            pts = []
            for ox, oy, rx_ratio, ry_ratio in bumps:
                bx = cx + ox * w
                by = cy + oy * h
                brx = rx_ratio * w
                bry = ry_ratio * h
                outward = math.atan2(oy, ox)
                for i in range(arc_steps + 1):
                    a = outward - arc_sweep / 2 + i * arc_sweep / arc_steps
                    pts.append((bx + math.cos(a) * brx, by + math.sin(a) * bry))
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
            # Rectangular body in the middle 70%, short leads to bbox edges so
            # left/right anchors land at the lead tips.
            bx1, bx2 = x + w * 0.15, x + w * 0.85
            by1, by2 = y + h * 0.25, y + h * 0.75
            segs += [
                ((x, cy), (bx1, cy)),
                ((bx2, cy), (x + w, cy)),
                ((bx1, by1), (bx2, by1)),
                ((bx2, by1), (bx2, by2)),
                ((bx2, by2), (bx1, by2)),
                ((bx1, by2), (bx1, by1)),
            ]
        elif self.kind == "capacitor":
            # Two tight plates near the middle with leads extending to bbox.
            plate1_x = x + w * 0.4
            plate2_x = x + w * 0.6
            segs += [
                ((x, cy), (plate1_x, cy)),
                ((plate2_x, cy), (x + w, cy)),
                ((plate1_x, y + h * 0.15), (plate1_x, y + h * 0.85)),
                ((plate2_x, y + h * 0.15), (plate2_x, y + h * 0.85)),
            ]
        elif self.kind == "ground":
            segs += [
                ((cx, y), (cx, cy)),                                        # vertical wire
                ((cx - w * 0.4, cy), (cx + w * 0.4, cy)),                  # top bar (widest)
                ((cx - w * 0.27, cy + h * 0.2), (cx + w * 0.27, cy + h * 0.2)),  # mid bar
                ((cx - w * 0.14, cy + h * 0.4), (cx + w * 0.14, cy + h * 0.4)),  # bottom bar
            ]
        elif self.kind == "battery":
            # Single cell: long anode plate + short cathode plate in the
            # middle, leads to bbox edges.
            plate1_x = x + w * 0.4
            plate2_x = x + w * 0.6
            segs += [
                ((x, cy), (plate1_x, cy)),
                ((plate2_x, cy), (x + w, cy)),
                ((plate1_x, cy - h * 0.4), (plate1_x, cy + h * 0.4)),
                ((plate2_x, cy - h * 0.2), (plate2_x, cy + h * 0.2)),
            ]
        elif self.kind == "switch":
            # Two terminals inset from bbox edges with leads; arm pivots open
            # at the left terminal.
            t1_x = x + w * 0.2
            t2_x = x + w * 0.8
            segs += [
                ((x, cy), (t1_x, cy)),
                ((t2_x, cy), (x + w, cy)),
                ((t1_x, cy - h * 0.1), (t1_x, cy + h * 0.1)),  # left terminal dot
                ((t2_x, cy - h * 0.1), (t2_x, cy + h * 0.1)),  # right terminal dot
                ((t1_x, cy), (t2_x, cy - h * 0.5)),            # open arm
            ]
        elif self.kind == "led":
            # Diode body in the middle 60%; emission arrows tucked above the
            # cathode but inside the bbox.
            base_x = x + w * 0.3
            tip_x = x + w * 0.7
            segs += [
                ((x, cy), (base_x, cy)),                              # anode lead
                ((tip_x, cy), (x + w, cy)),                           # cathode lead
                ((base_x, y + h * 0.2), (base_x, y + h * 0.8)),       # anode vertical
                ((base_x, y + h * 0.2), (tip_x, cy)),                  # triangle upper edge
                ((base_x, y + h * 0.8), (tip_x, cy)),                  # triangle lower edge
                ((tip_x, y + h * 0.2), (tip_x, y + h * 0.8)),          # cathode bar
                ((x + w * 0.72, y + h * 0.25), (x + w * 0.88, y + h * 0.05)),
                ((x + w * 0.82, y + h * 0.32), (x + w * 0.98, y + h * 0.12)),
            ]
        elif self.kind == "inductor":
            # Coils occupy the middle 70%, short leads on each side.
            coil_start = x + w * 0.15
            coil_end = x + w * 0.85
            coils = 4
            coil_w = (coil_end - coil_start) / coils
            arc_pts = []
            for i in range(coils):
                bx = coil_start + i * coil_w + coil_w / 2
                for j in range(9):
                    a = math.pi - j * math.pi / 8
                    arc_pts.append((bx + math.cos(a) * coil_w / 2, cy - math.sin(a) * h * 0.35))
            for a_pt, b_pt in zip(arc_pts, arc_pts[1:]):
                segs.append((a_pt, b_pt))
            segs += [((x, cy), (coil_start, cy)), ((coil_end, cy), (x + w, cy))]
        elif self.kind == "voltage_source":
            # Circle in the middle with leads to bbox edges; +/- inside.
            r = min(w, h) * 0.35
            segs += [
                ((x, cy), (cx - r, cy)),
                ((cx + r, cy), (x + w, cy)),
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
        parsed = _parse_edge_anchor(side)
        if parsed:
            edge, ratio = parsed
            x1, y1, x2, y2 = self.bounds()
            ratio = max(0.0, min(1.0, ratio))
            if edge == "top":
                return x1 + (x2 - x1) * ratio, y1
            if edge == "bottom":
                return x1 + (x2 - x1) * ratio, y2
            if edge == "left":
                return x1, y1 + (y2 - y1) * ratio
            if edge == "right":
                return x2, y1 + (y2 - y1) * ratio
        a = self.anchors()
        return a.get(side, a["bottom"])

    def edge_anchor_for_point(self, x: float, y: float) -> str:
        x1, y1, x2, y2 = self.bounds()
        width = max(1e-6, x2 - x1)
        height = max(1e-6, y2 - y1)
        candidates = [
            ("top", _point_segment_distance(x, y, x1, y1, x2, y1), (x - x1) / width),
            ("bottom", _point_segment_distance(x, y, x1, y2, x2, y2), (x - x1) / width),
            ("left", _point_segment_distance(x, y, x1, y1, x1, y2), (y - y1) / height),
            ("right", _point_segment_distance(x, y, x2, y1, x2, y2), (y - y1) / height),
        ]
        edge, _distance, ratio = min(candidates, key=lambda item: item[1])
        return f"{edge}:{max(0.0, min(1.0, ratio)):.3f}"

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
            "metadata": dict(self.metadata),
            **_layer_dict(self),
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
            metadata=dict(payload.get("metadata", {})),
            **_layer_kwargs(payload),
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
    visible: bool = True
    locked: bool = False
    name: str = ""

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
            **_layer_dict(self),
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
            **_layer_kwargs(payload),
        )


@dataclass
class CurveShape:
    points: list[tuple[float, float]] = field(default_factory=list)
    style: ShapeStyle = field(default_factory=lambda: ShapeStyle(fill=None))
    id: str = field(default_factory=lambda: new_id("curve"))
    z_order: int = 0
    visible: bool = True
    locked: bool = False
    name: str = ""

    def move(self, dx: float, dy: float) -> None:
        self.points = [(x + dx, y + dy) for x, y in self.points]

    def center(self) -> Point:
        x1, y1, x2, y2 = self.bounds()
        return Point((x1 + x2) / 2, (y1 + y2) / 2)

    def scale(self, factor: float) -> None:
        c = self.center()
        self.points = [(c.x + (x - c.x) * factor, c.y + (y - c.y) * factor) for x, y in self.points]

    def rotate(self, angle_degrees: float) -> None:
        c = self.center()
        m = Matrix3.rotation(math.radians(angle_degrees), center=c)
        new_pts = []
        for x, y in self.points:
            p = m.apply(Point(x, y))
            new_pts.append((p.x, p.y))
        self.points = new_pts

    def flip_horizontal(self) -> None:
        c = self.center()
        self.points = [(c.x - (x - c.x), y) for x, y in self.points]

    def flip_vertical(self) -> None:
        c = self.center()
        self.points = [(x, c.y - (y - c.y)) for x, y in self.points]

    def bounds(self) -> tuple[float, float, float, float]:
        if not self.points:
            return 0.0, 0.0, 0.0, 0.0
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def hit_test(self, x: float, y: float) -> bool:
        from algorithms.bezier import catmull_rom_polyline
        if len(self.points) < 2:
            return False
        sampled = catmull_rom_polyline(self.points, steps_per_segment=10)
        for a, b in zip(sampled, sampled[1:]):
            if _point_segment_distance(x, y, a[0], a[1], b[0], b[1]) <= 7:
                return True
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "curve",
            "points": [[p[0], p[1]] for p in self.points],
            "style": self.style.to_dict(),
            "z_order": self.z_order,
            **_layer_dict(self),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "CurveShape":
        raw = payload.get("points")
        if raw is None:
            # Backward compat with the previous 4-control-point format.
            raw = [
                [payload["x0"], payload["y0"]],
                [payload["x1"], payload["y1"]],
                [payload["x2"], payload["y2"]],
                [payload["x3"], payload["y3"]],
            ]
        return cls(
            points=[(float(p[0]), float(p[1])) for p in raw],
            style=ShapeStyle.from_dict(payload.get("style")),
            id=payload.get("id", new_id("curve")),
            z_order=int(payload.get("z_order", 0)),
            **_layer_kwargs(payload),
        )


@dataclass
class BezierShape:
    points: list[tuple[float, float]]
    style: ShapeStyle = field(default_factory=lambda: ShapeStyle(fill=None))
    id: str = field(default_factory=lambda: new_id("bezier"))
    z_order: int = 0
    visible: bool = True
    locked: bool = False
    name: str = ""

    def move(self, dx: float, dy: float) -> None:
        self.points = [(x + dx, y + dy) for x, y in self.points]

    def center(self) -> Point:
        x1, y1, x2, y2 = self.bounds()
        return Point((x1 + x2) / 2, (y1 + y2) / 2)

    def scale(self, factor: float) -> None:
        center = self.center()
        self.points = [(center.x + (x - center.x) * factor, center.y + (y - center.y) * factor) for x, y in self.points]

    def rotate(self, angle_degrees: float) -> None:
        center = self.center()
        matrix = Matrix3.rotation(math.radians(angle_degrees), center=center)
        rotated = []
        for x, y in self.points:
            point = matrix.apply(Point(x, y))
            rotated.append((point.x, point.y))
        self.points = rotated

    def flip_horizontal(self) -> None:
        center = self.center()
        self.points = [(center.x - (x - center.x), y) for x, y in self.points]

    def flip_vertical(self) -> None:
        center = self.center()
        self.points = [(x, center.y - (y - center.y)) for x, y in self.points]

    def bounds(self) -> tuple[float, float, float, float]:
        if not self.points:
            return 0.0, 0.0, 0.0, 0.0
        sampled = [(float(x), float(y)) for x, y in bezier_polyline(self.points)]
        all_points = list(self.points) + sampled
        xs = [point[0] for point in all_points]
        ys = [point[1] for point in all_points]
        return min(xs), min(ys), max(xs), max(ys)

    def hit_test(self, x: float, y: float) -> bool:
        sampled = bezier_polyline(self.points)
        for a, b in zip(sampled, sampled[1:]):
            if _point_segment_distance(x, y, a[0], a[1], b[0], b[1]) <= 7:
                return True
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "bezier",
            "points": [[p[0], p[1]] for p in self.points],
            "style": self.style.to_dict(),
            "z_order": self.z_order,
            **_layer_dict(self),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "BezierShape":
        return cls(
            points=[(float(p[0]), float(p[1])) for p in payload.get("points", [])],
            style=ShapeStyle.from_dict(payload.get("style")),
            id=payload.get("id", new_id("bezier")),
            z_order=int(payload.get("z_order", 0)),
            **_layer_kwargs(payload),
        )


@dataclass
class TextShape:
    x: float
    y: float
    text: str
    style: ShapeStyle = field(default_factory=lambda: ShapeStyle(fill=None))
    id: str = field(default_factory=lambda: new_id("text"))
    z_order: int = 0
    visible: bool = True
    locked: bool = False
    name: str = ""

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
            **_layer_dict(self),
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
            **_layer_kwargs(payload),
        )


@dataclass
class RasterImageShape:
    x: float
    y: float
    width: float
    height: float
    data_url: str
    source_name: str = ""
    style: ShapeStyle = field(default_factory=lambda: ShapeStyle(fill=None))
    id: str = field(default_factory=lambda: new_id("image"))
    z_order: int = 0
    visible: bool = True
    locked: bool = False
    name: str = ""
    _image_cache: Image.Image | None = field(default=None, init=False, repr=False, compare=False)
    _resize_cache: dict[tuple[int, int], Image.Image] = field(default_factory=dict, init=False, repr=False, compare=False)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)

    def scale(self, factor: float) -> None:
        center = self.center()
        self.width = max(12, self.width * factor)
        self.height = max(12, self.height * factor)
        self.x = center.x - self.width / 2
        self.y = center.y - self.height / 2

    def rotate(self, angle_degrees: float) -> None:
        return None

    def flip_horizontal(self) -> None:
        return None

    def flip_vertical(self) -> None:
        return None

    def bounds(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.x + self.width, self.y + self.height

    def outline_points(self) -> list[tuple[float, float]]:
        x1, y1, x2, y2 = self.bounds()
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    def hit_test(self, x: float, y: float) -> bool:
        x1, y1, x2, y2 = self.bounds()
        return x1 <= x <= x2 and y1 <= y <= y2

    def image(self) -> Image.Image:
        if self._image_cache is None:
            self._image_cache = Image.open(BytesIO(_decode_data_url(self.data_url))).convert("RGBA")
        return self._image_cache

    def resized_image(self, width: int, height: int, *, resample: Any = Image.Resampling.LANCZOS) -> Image.Image:
        size = (max(1, int(width)), max(1, int(height)))
        cached = self._resize_cache.get(size)
        if cached is None:
            cached = self.image().resize(size, resample)
            self._resize_cache[size] = cached
        return cached

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "raster_image",
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "data_url": self.data_url,
            "source_name": self.source_name,
            "style": self.style.to_dict(),
            "z_order": self.z_order,
            **_layer_dict(self),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "RasterImageShape":
        return cls(
            x=float(payload["x"]),
            y=float(payload["y"]),
            width=float(payload["width"]),
            height=float(payload["height"]),
            data_url=str(payload["data_url"]),
            source_name=str(payload.get("source_name", "")),
            style=ShapeStyle.from_dict(payload.get("style")),
            id=payload.get("id", new_id("image")),
            z_order=int(payload.get("z_order", 0)),
            **_layer_kwargs(payload),
        )


@dataclass
class GroupShape:
    name: str
    children: list["Shape"]
    connectors: list["ConnectorShape"] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("group"))
    z_order: int = 0
    visible: bool = True
    locked: bool = False

    def move(self, dx: float, dy: float) -> None:
        for child in self.children:
            child.move(dx, dy)

    def center(self) -> Point:
        x1, y1, x2, y2 = self.bounds()
        return Point((x1 + x2) / 2, (y1 + y2) / 2)

    def scale(self, factor: float) -> None:
        x1, y1, x2, y2 = self.bounds()
        center = Point((x1 + x2) / 2, (y1 + y2) / 2)
        for child in self.children:
            cx, cy = child.center() if hasattr(child, "center") else Point((child.bounds()[0] + child.bounds()[2]) / 2, (child.bounds()[1] + child.bounds()[3]) / 2)
            child.move((cx - center.x) * (factor - 1), (cy - center.y) * (factor - 1))
            if hasattr(child, "scale"):
                child.scale(factor)

    def scale_from_bounds(
        self,
        old_bounds: tuple[float, float, float, float],
        new_bounds: tuple[float, float, float, float],
    ) -> None:
        ox1, oy1, ox2, oy2 = old_bounds
        nx1, ny1, nx2, ny2 = new_bounds
        old_w = max(1e-6, ox2 - ox1)
        old_h = max(1e-6, oy2 - oy1)
        sx = (nx2 - nx1) / old_w
        sy = (ny2 - ny1) / old_h
        for child in self.children:
            self._scale_child_from_bounds(child, (ox1, oy1), (nx1, ny1), sx, sy)

    def rotate(self, angle_degrees: float) -> None:
        center = self.center()
        self.rotate_around(center, angle_degrees)

    def rotate_around(self, center: Point, angle_degrees: float) -> None:
        matrix = Matrix3.rotation(math.radians(angle_degrees), center=center)
        for child in self.children:
            child_center = child.center() if hasattr(child, "center") else Point((child.bounds()[0] + child.bounds()[2]) / 2, (child.bounds()[1] + child.bounds()[3]) / 2)
            new_center = matrix.apply(child_center)
            child.move(new_center.x - child_center.x, new_center.y - child_center.y)
            if hasattr(child, "rotate"):
                child.rotate(angle_degrees)

    def flip_horizontal(self) -> None:
        center = self.center()
        for child in self.children:
            child_center = child.center() if hasattr(child, "center") else Point((child.bounds()[0] + child.bounds()[2]) / 2, (child.bounds()[1] + child.bounds()[3]) / 2)
            child.move((center.x - child_center.x) * 2, 0)
            if hasattr(child, "flip_horizontal"):
                child.flip_horizontal()

    def flip_vertical(self) -> None:
        center = self.center()
        for child in self.children:
            child_center = child.center() if hasattr(child, "center") else Point((child.bounds()[0] + child.bounds()[2]) / 2, (child.bounds()[1] + child.bounds()[3]) / 2)
            child.move(0, (center.y - child_center.y) * 2)
            if hasattr(child, "flip_vertical"):
                child.flip_vertical()

    def bounds(self) -> tuple[float, float, float, float]:
        if not self.children:
            return 0.0, 0.0, 0.0, 0.0
        bounds = [child.bounds() for child in self.children]
        return (
            min(item[0] for item in bounds),
            min(item[1] for item in bounds),
            max(item[2] for item in bounds),
            max(item[3] for item in bounds),
        )

    def outline_points(self) -> list[tuple[float, float]]:
        x1, y1, x2, y2 = self.bounds()
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    def hit_test(self, x: float, y: float) -> bool:
        return any(child.hit_test(x, y) for child in self.children)

    def _scale_child_from_bounds(
        self,
        child: "Shape",
        old_origin: tuple[float, float],
        new_origin: tuple[float, float],
        sx: float,
        sy: float,
    ) -> None:
        def map_point(point: tuple[float, float]) -> tuple[float, float]:
            return new_origin[0] + (point[0] - old_origin[0]) * sx, new_origin[1] + (point[1] - old_origin[1]) * sy

        if isinstance(child, FlowchartShape):
            left, top = map_point((child.x, child.y))
            right, bottom = map_point((child.x + child.width, child.y + child.height))
            child.x = left
            child.y = top
            child.width = max(12, right - left)
            child.height = max(12, bottom - top)
        elif isinstance(child, LineShape):
            child.x1, child.y1 = map_point((child.x1, child.y1))
            child.x2, child.y2 = map_point((child.x2, child.y2))
        elif isinstance(child, CurveShape):
            child.points = [map_point(point) for point in child.points]
        elif isinstance(child, BezierShape):
            child.points = [map_point(point) for point in child.points]
        elif isinstance(child, TextShape):
            child.x, child.y = map_point((child.x, child.y))
        elif isinstance(child, RasterImageShape):
            left, top = map_point((child.x, child.y))
            right, bottom = map_point((child.x + child.width, child.y + child.height))
            child.x = left
            child.y = top
            child.width = max(12, right - left)
            child.height = max(12, bottom - top)
        elif isinstance(child, GroupShape):
            cx1, cy1, cx2, cy2 = child.bounds()
            child.scale_from_bounds(child.bounds(), (*map_point((cx1, cy1)), *map_point((cx2, cy2))))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "group",
            "name": self.name,
            "children": [child.to_dict() for child in self.children],
            "connectors": [connector.to_dict() for connector in self.connectors],
            "metadata": dict(self.metadata),
            "z_order": self.z_order,
            "visible": self.visible,
            "locked": self.locked,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "GroupShape":
        return cls(
            name=str(payload.get("name", "组件")),
            children=[shape_from_dict(child) for child in payload.get("children", [])],
            connectors=[ConnectorShape.from_dict(connector) for connector in payload.get("connectors", [])],
            metadata={str(key): str(value) for key, value in payload.get("metadata", {}).items()},
            id=payload.get("id", new_id("group")),
            z_order=int(payload.get("z_order", 0)),
            visible=bool(payload.get("visible", True)),
            locked=bool(payload.get("locked", False)),
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
    metadata: dict[str, Any] = field(default_factory=dict)

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
            "metadata": dict(self.metadata),
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
            metadata=dict(payload.get("metadata", {})),
        )


Shape = FlowchartShape | LineShape | CurveShape | BezierShape | TextShape | RasterImageShape | GroupShape


def shape_from_dict(payload: dict) -> Shape:
    shape_type = payload.get("type")
    if shape_type == "flowchart":
        return FlowchartShape.from_dict(payload)
    if shape_type == "line":
        return LineShape.from_dict(payload)
    if shape_type == "curve":
        return CurveShape.from_dict(payload)
    if shape_type == "bezier":
        return BezierShape.from_dict(payload)
    if shape_type == "text":
        return TextShape.from_dict(payload)
    if shape_type == "raster_image":
        return RasterImageShape.from_dict(payload)
    if shape_type == "group":
        return GroupShape.from_dict(payload)
    raise ValueError(f"Unsupported shape type: {shape_type!r}")


def shape_display_name(shape: "Shape") -> str:
    """图层面板显示名：优先自定义 name，否则按类型派生一个可读标签。"""
    name = getattr(shape, "name", "")
    if name:
        return name
    if isinstance(shape, GroupShape):
        return shape.name or "组件"
    if isinstance(shape, FlowchartShape):
        return KIND_LABELS.get(shape.kind, shape.kind or "图形")
    if isinstance(shape, TextShape):
        first = (shape.text or "").splitlines()[0] if shape.text else ""
        first = first.strip()
        if not first:
            return "文本"
        return first if len(first) <= 12 else first[:12] + "…"
    if isinstance(shape, LineShape):
        return "直线"
    if isinstance(shape, CurveShape):
        return "曲线"
    if isinstance(shape, BezierShape):
        return "Bezier"
    if isinstance(shape, RasterImageShape):
        return shape.source_name or "图片"
    return "图形"


def _decode_data_url(data_url: str) -> bytes:
    import base64

    marker = ";base64,"
    if marker in data_url:
        return base64.b64decode(data_url.split(marker, 1)[1])
    return base64.b64decode(data_url)


def _mat_apply(matrix: "Matrix3", px: float, py: float) -> tuple[float, float]:
    transformed = matrix.apply(Point(px, py))
    return transformed.x, transformed.y


def _parse_edge_anchor(value: str) -> tuple[str, float] | None:
    if ":" not in value:
        return None
    edge, raw_ratio = value.split(":", 1)
    if edge not in {"top", "right", "bottom", "left"}:
        return None
    try:
        return edge, float(raw_ratio)
    except ValueError:
        return None


def _point_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
