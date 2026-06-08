from __future__ import annotations

from dataclasses import dataclass, field

from algorithms.bezier import cubic_bezier
from core.shapes import BezierShape, ConnectorShape, CurveShape, FlowchartShape, GroupShape, LineShape, RasterImageShape, Shape, new_id, shape_from_dict


@dataclass
class Document:
    title: str = "未命名流程图"
    canvas_width: int = 2400
    canvas_height: int = 1600
    background: str = "#1E1E2E"
    grid_size: int = 20
    snap_enabled: bool = True
    shapes: list[Shape] = field(default_factory=list)
    connectors: list[ConnectorShape] = field(default_factory=list)
    _shape_index: dict[str, Shape] = field(default_factory=dict, init=False, repr=False)
    _shape_index_signature: tuple[int, int] = field(default=(0, -1), init=False, repr=False)

    def add_shape(self, shape: Shape) -> Shape:
        if self._current_shape_index_signature() != self._shape_index_signature:
            self._rebuild_shape_index()
        shape.z_order = len(self.shapes)
        self.shapes.append(shape)
        self._shape_index[shape.id] = shape
        self._shape_index_signature = self._current_shape_index_signature()
        return shape

    def add_connector(self, connector: ConnectorShape) -> ConnectorShape:
        self.connectors.append(connector)
        return connector

    def find_shape(self, shape_id: str) -> Shape | None:
        return self._shapes_by_id().get(shape_id)

    def shape_at(self, x: float, y: float) -> Shape | None:
        for shape in sorted(self.shapes, key=lambda item: item.z_order, reverse=True):
            if not getattr(shape, "visible", True) or getattr(shape, "locked", False):
                continue
            if shape.hit_test(x, y):
                return shape
        return None

    def connector_at(self, x: float, y: float, tolerance: float = 7) -> ConnectorShape | None:
        for connector in sorted(self.connectors, key=lambda item: item.z_order, reverse=True):
            points = self.connector_points(connector)
            if any(
                _point_segment_distance(x, y, a[0], a[1], b[0], b[1]) <= tolerance
                for a, b in zip(points, points[1:])
            ):
                return connector
        return None

    def connector_endpoint_at(self, connector: ConnectorShape, point: tuple[float, float], tolerance: float = 7) -> str | None:
        points = self.connector_points(connector)
        if len(points) < 2:
            return None
        px, py = point
        if _point_distance(px, py, *points[0]) <= tolerance:
            return "start"
        if _point_distance(px, py, *points[-1]) <= tolerance:
            return "end"
        return None

    def move_shapes(self, shape_ids: list[str], dx: float, dy: float) -> None:
        selected = set(shape_ids)
        for shape in self.shapes:
            if shape.id in selected and not getattr(shape, "locked", False):
                shape.move(dx, dy)

    # ── 图层 / z-order ───────────────────────────────────────────────
    def _renormalize_z(self) -> None:
        """按 self.shapes 当前顺序（底->顶）赋连续 z_order 0..N-1，消除重复与空洞。

        调用方负责先把 self.shapes 排成期望的叠放顺序。
        """
        for index, shape in enumerate(self.shapes):
            shape.z_order = index
        self._rebuild_shape_index()

    def bring_to_front(self, shape_ids: set[str] | list[str]) -> bool:
        selected = set(shape_ids)
        ordered = sorted(self.shapes, key=lambda item: item.z_order)
        keep = [s for s in ordered if s.id not in selected]
        move = [s for s in ordered if s.id in selected]
        new_order = keep + move
        if not move or ordered == new_order:
            return False
        self.shapes = new_order
        self._renormalize_z()
        return True

    def send_to_back(self, shape_ids: set[str] | list[str]) -> bool:
        selected = set(shape_ids)
        ordered = sorted(self.shapes, key=lambda item: item.z_order)
        move = [s for s in ordered if s.id in selected]
        keep = [s for s in ordered if s.id not in selected]
        new_order = move + keep
        if not move or ordered == new_order:
            return False
        self.shapes = new_order
        self._renormalize_z()
        return True

    def raise_shapes(self, shape_ids: set[str] | list[str]) -> bool:
        """选中图形整体上移一层（与上方相邻的未选中图形交换）。"""
        selected = set(shape_ids)
        ordered = sorted(self.shapes, key=lambda item: item.z_order)
        changed = False
        for i in range(len(ordered) - 2, -1, -1):
            if ordered[i].id in selected and ordered[i + 1].id not in selected:
                ordered[i], ordered[i + 1] = ordered[i + 1], ordered[i]
                changed = True
        if changed:
            self.shapes = ordered
            self._renormalize_z()
        return changed

    def lower_shapes(self, shape_ids: set[str] | list[str]) -> bool:
        """选中图形整体下移一层（与下方相邻的未选中图形交换）。"""
        selected = set(shape_ids)
        ordered = sorted(self.shapes, key=lambda item: item.z_order)
        changed = False
        for i in range(1, len(ordered)):
            if ordered[i].id in selected and ordered[i - 1].id not in selected:
                ordered[i], ordered[i - 1] = ordered[i - 1], ordered[i]
                changed = True
        if changed:
            self.shapes = ordered
            self._renormalize_z()
        return changed

    def move_shape_to_index(self, shape_id: str, index: int) -> bool:
        """把某图形移动到 z 排序列表中的指定下标（0=最底层）。"""
        ordered = sorted(self.shapes, key=lambda item: item.z_order)
        src = next((i for i, s in enumerate(ordered) if s.id == shape_id), None)
        if src is None:
            return False
        index = max(0, min(index, len(ordered) - 1))
        if index == src:
            return False
        shape = ordered.pop(src)
        ordered.insert(index, shape)
        self.shapes = ordered
        self._renormalize_z()
        return True

    def delete_shapes(self, shape_ids: list[str]) -> None:
        selected = set(shape_ids)
        self.shapes = [shape for shape in self.shapes if shape.id not in selected]
        self.connectors = [
            connector
            for connector in self.connectors
            if connector.id not in selected
            and connector.start_shape_id not in selected
            and connector.end_shape_id not in selected
        ]
        self._rebuild_shape_index()

    def replace_selection_with_group(self, shape_ids: set[str] | list[str], group: GroupShape) -> GroupShape:
        selected = set(shape_ids)
        internal_connector_ids = {item.id for item in group.connectors}
        insert_at = min(
            (index for index, shape in enumerate(self.shapes) if shape.id in selected),
            default=len(self.shapes),
        )
        self.shapes = [shape for shape in self.shapes if shape.id not in selected]
        self.connectors = [
            connector
            for connector in self.connectors
            if connector.start_shape_id not in selected
            and connector.end_shape_id not in selected
            and connector.id not in internal_connector_ids
        ]
        self.shapes.insert(insert_at, group)
        for index, shape in enumerate(self.shapes):
            shape.z_order = index
        self._rebuild_shape_index()
        return group

    def ungroup_shape(self, group_id: str) -> list[Shape]:
        group_index = next(
            (index for index, shape in enumerate(self.shapes) if shape.id == group_id and isinstance(shape, GroupShape)),
            None,
        )
        if group_index is None:
            return []
        group = self.shapes[group_index]
        assert isinstance(group, GroupShape)
        children = [shape_from_dict(child.to_dict()) for child in group.children]
        connectors = [ConnectorShape.from_dict(connector.to_dict()) for connector in group.connectors]
        self.shapes = self.shapes[:group_index] + children + self.shapes[group_index + 1 :]
        self.connectors.extend(connectors)
        self._renormalize_z()
        return children

    def set_shapes_locked(self, shape_ids: set[str] | list[str], locked: bool) -> bool:
        selected = set(shape_ids)
        changed = False
        for shape in self.shapes:
            if shape.id in selected and getattr(shape, "locked", False) != locked:
                shape.locked = locked
                changed = True
        if changed:
            self._rebuild_shape_index()
        return changed

    def copy_paste(self, shape_ids: list[str], offset: tuple[float, float] = (28, 28)) -> list[Shape]:
        selected = set(shape_ids)
        old_to_new: dict[str, str] = {}
        pasted: list[Shape] = []
        for shape in self.shapes:
            if shape.id not in selected:
                continue
            clone = _clone_shape_with_new_ids(shape)
            clone.move(offset[0], offset[1])
            old_to_new[shape.id] = clone.id
            pasted.append(self.add_shape(clone))

        for connector in self.connectors:
            if connector.start_shape_id in selected and connector.end_shape_id in selected:
                clone = ConnectorShape.from_dict(connector.to_dict())
                clone.id = new_id("conn")
                clone.start_shape_id = old_to_new[connector.start_shape_id]
                clone.end_shape_id = old_to_new[connector.end_shape_id]
                self.add_connector(clone)
        return pasted

    def connector_points(self, connector: ConnectorShape) -> list[tuple[float, float]]:
        start_shape = self.find_shape(connector.start_shape_id)
        end_shape = self.find_shape(connector.end_shape_id)
        if not isinstance(start_shape, FlowchartShape) or not isinstance(end_shape, FlowchartShape):
            return []
        start = start_shape.anchor(connector.start_anchor)
        end = end_shape.anchor(connector.end_anchor)
        if connector.kind == "straight":
            return [start, end]
        if connector.kind == "bezier":
            return _bezier_route(start, connector.start_anchor, end, connector.end_anchor)
        return _elbow_route(start, connector.start_anchor, end, connector.end_anchor)

    def to_dict(self) -> dict:
        return {
            "version": "1.0",
            "metadata": {"title": self.title},
            "canvas": {
                "width": self.canvas_width,
                "height": self.canvas_height,
                "background": self.background,
                "grid_size": self.grid_size,
                "snap_enabled": self.snap_enabled,
            },
            "shapes": [shape.to_dict() for shape in self.shapes],
            "connectors": [connector.to_dict() for connector in self.connectors],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Document":
        metadata = payload.get("metadata", {})
        canvas = payload.get("canvas", {})
        document = cls(
            title=metadata.get("title", "未命名流程图"),
            canvas_width=int(canvas.get("width", 2400)),
            canvas_height=int(canvas.get("height", 1600)),
            background=canvas.get("background", "#1E1E2E"),
            grid_size=int(canvas.get("grid_size", 20)),
            snap_enabled=bool(canvas.get("snap_enabled", True)),
        )
        for shape_payload in payload.get("shapes", []):
            document.shapes.append(shape_from_dict(shape_payload))
        for connector_payload in payload.get("connectors", []):
            document.connectors.append(ConnectorShape.from_dict(connector_payload))
        return document

    def replace_from_dict(self, payload: dict) -> None:
        replacement = Document.from_dict(payload)
        self.title = replacement.title
        self.canvas_width = replacement.canvas_width
        self.canvas_height = replacement.canvas_height
        self.background = replacement.background
        self.grid_size = replacement.grid_size
        self.snap_enabled = replacement.snap_enabled
        self.shapes = replacement.shapes
        self.connectors = replacement.connectors
        self._rebuild_shape_index()

    def _shapes_by_id(self) -> dict[str, Shape]:
        signature = self._current_shape_index_signature()
        if signature != self._shape_index_signature:
            self._rebuild_shape_index()
        return self._shape_index

    def _rebuild_shape_index(self) -> None:
        self._shape_index = {shape.id: shape for shape in self.shapes}
        self._shape_index_signature = self._current_shape_index_signature()

    def _current_shape_index_signature(self) -> tuple[int, int]:
        return id(self.shapes), len(self.shapes)


def _new_like_id(shape: Shape) -> str:
    if isinstance(shape, LineShape):
        return new_id("line")
    if isinstance(shape, CurveShape):
        return new_id("curve")
    if isinstance(shape, BezierShape):
        return new_id("bezier")
    if isinstance(shape, RasterImageShape):
        return new_id("image")
    if isinstance(shape, GroupShape):
        return new_id("group")
    return new_id("shape")


def _clone_shape_with_new_ids(shape: Shape) -> Shape:
    clone = shape_from_dict(shape.to_dict())
    clone.id = _new_like_id(clone)
    if isinstance(clone, GroupShape):
        _remap_group_shape_ids(clone)
    return clone


def _remap_group_shape_ids(group: GroupShape) -> None:
    old_to_new: dict[str, str] = {}
    for child in group.children:
        old_id = child.id
        child.id = _new_like_id(child)
        old_to_new[old_id] = child.id
        if isinstance(child, GroupShape):
            _remap_group_shape_ids(child)
    for connector in group.connectors:
        connector.id = new_id("conn")
        connector.start_shape_id = old_to_new.get(connector.start_shape_id, connector.start_shape_id)
        connector.end_shape_id = old_to_new.get(connector.end_shape_id, connector.end_shape_id)


def _elbow_route(
    start: tuple[float, float],
    start_anchor: str,
    end: tuple[float, float],
    end_anchor: str,
    gap: float = 30,
) -> list[tuple[float, float]]:
    p1 = _extend(start, start_anchor, gap)
    p2 = _extend(end, end_anchor, gap)
    if start_anchor in {"left", "right"}:
        mid = ((p1[0] + p2[0]) / 2, p1[1])
        mid2 = (mid[0], p2[1])
    else:
        mid = (p1[0], (p1[1] + p2[1]) / 2)
        mid2 = (p2[0], mid[1])
    return _dedupe([start, p1, mid, mid2, p2, end])


def _extend(point: tuple[float, float], direction: str, gap: float) -> tuple[float, float]:
    x, y = point
    if direction == "left":
        return x - gap, y
    if direction == "right":
        return x + gap, y
    if direction == "top":
        return x, y - gap
    return x, y + gap


def _dedupe(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for point in points:
        if not result or result[-1] != point:
            result.append(point)
    return result


def _point_distance(px: float, py: float, x: float, y: float) -> float:
    return ((px - x) ** 2 + (py - y) ** 2) ** 0.5


def _point_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return _point_distance(px, py, x1, y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    return _point_distance(px, py, x1 + t * dx, y1 + t * dy)


def _bezier_route(
    start: tuple[float, float],
    start_anchor: str,
    end: tuple[float, float],
    end_anchor: str,
) -> list[tuple[float, float]]:
    dist = max(60, abs(end[0] - start[0]) * 0.4, abs(end[1] - start[1]) * 0.4)
    cp1 = _extend(start, start_anchor, dist)
    cp2 = _extend(end, end_anchor, dist)
    return [(float(x), float(y)) for x, y in cubic_bezier(start, cp1, cp2, end)]
