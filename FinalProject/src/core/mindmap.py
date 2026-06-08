from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from core.document import Document
from core.shapes import ConnectorShape, FlowchartShape
from core.style import ShapeStyle


class MindMapParseError(ValueError):
    pass


@dataclass
class MindMapTreeNode:
    title: str
    level: int
    children: list["MindMapTreeNode"] = field(default_factory=list)


_HEADING_RE = re.compile(r"^(#+)\s*(.*)$")

MINDMAP_ID = "mindmap_id"
MINDMAP_PARENT_ID = "mindmap_parent_id"
MINDMAP_COLLAPSED = "mindmap_collapsed"
MINDMAP_SIDE = "mindmap_side"
MINDMAP_CHILD_ID = "mindmap_child_id"


def parse_heading_text(text: str) -> MindMapTreeNode:
    stack: list[MindMapTreeNode] = []
    root: MindMapTreeNode | None = None
    saw_nonempty = False
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        saw_nonempty = True
        match = _HEADING_RE.match(line)
        if not match:
            raise MindMapParseError(f"line {line_number}: expected heading syntax like '# Topic'")
        level = len(match.group(1))
        title = match.group(2).strip()
        if not title:
            raise MindMapParseError(f"line {line_number}: heading text cannot be empty")
        if root is None and level != 1:
            raise MindMapParseError(f"line {line_number}: first heading must be level 1")
        if stack and level > stack[-1].level + 1:
            raise MindMapParseError(f"line {line_number}: cannot jump from level {stack[-1].level} to {level}")
        node = MindMapTreeNode(title=title, level=level)
        if level == 1:
            if root is not None:
                raise MindMapParseError(f"line {line_number}: only one level 1 root heading is supported")
            root = node
            stack = [node]
            continue
        while stack and stack[-1].level >= level:
            stack.pop()
        if not stack:
            raise MindMapParseError(f"line {line_number}: missing parent heading")
        stack[-1].children.append(node)
        stack.append(node)
    if root is None:
        if saw_nonempty:
            raise MindMapParseError("no valid root heading found")
        raise MindMapParseError("no heading content provided")
    return root


def new_mindmap_id() -> str:
    return f"mindmap_{uuid.uuid4().hex[:10]}"


def is_mindmap_node(shape: object) -> bool:
    return bool(getattr(shape, "metadata", {}).get(MINDMAP_ID))


def mindmap_children(document: Document, parent_id: str) -> list[FlowchartShape]:
    result = []
    for shape in document.shapes:
        if isinstance(shape, FlowchartShape) and shape.metadata.get(MINDMAP_PARENT_ID) == parent_id:
            result.append(shape)
    return result


def mindmap_descendants(document: Document, parent_id: str) -> list[FlowchartShape]:
    result: list[FlowchartShape] = []
    pending = list(mindmap_children(document, parent_id))
    while pending:
        child = pending.pop(0)
        result.append(child)
        pending[0:0] = mindmap_children(document, child.id)
    return result


def collapsed_hidden_ids(document: Document) -> tuple[set[str], set[str]]:
    hidden_shapes: set[str] = set()
    for shape in document.shapes:
        if isinstance(shape, FlowchartShape) and shape.metadata.get(MINDMAP_COLLAPSED):
            hidden_shapes.update(child.id for child in mindmap_descendants(document, shape.id))
    hidden_connectors = {
        connector.id
        for connector in document.connectors
        if connector.metadata.get(MINDMAP_CHILD_ID) in hidden_shapes
        or connector.metadata.get(MINDMAP_PARENT_ID) in hidden_shapes
    }
    return hidden_shapes, hidden_connectors


def add_mindmap_child(document: Document, parent_id: str, *, title: str = "New Topic") -> FlowchartShape:
    parent = document.find_shape(parent_id)
    if not isinstance(parent, FlowchartShape) or not is_mindmap_node(parent):
        raise ValueError("parent is not a mind map node")
    side = str(parent.metadata.get(MINDMAP_SIDE, "right"))
    if side == "root":
        side = "right"
    mindmap_id = str(parent.metadata[MINDMAP_ID])
    existing_children = mindmap_children(document, parent.id)
    offset_x = 230 if side == "right" else -230
    offset_y = (len(existing_children) - 0.5) * 72
    child_center_x = parent.x + parent.width / 2 + offset_x
    child_center_y = parent.y + parent.height / 2 + offset_y
    width, height = _node_size(title, 2)
    child = FlowchartShape(
        "org_box",
        child_center_x - width / 2,
        child_center_y - height / 2,
        width,
        height,
        title,
        style=_node_style(2),
        metadata={
            MINDMAP_ID: mindmap_id,
            MINDMAP_PARENT_ID: parent.id,
            MINDMAP_COLLAPSED: False,
            MINDMAP_SIDE: side,
        },
    )
    document.add_shape(child)
    document.add_connector(_make_connector(parent, child, mindmap_id))
    parent.metadata[MINDMAP_COLLAPSED] = False
    return child


def build_mindmap_fragment(
    root: MindMapTreeNode,
    *,
    center: tuple[float, float],
    mindmap_id: str | None = None,
) -> tuple[list[FlowchartShape], list[ConnectorShape]]:
    mindmap_id = mindmap_id or new_mindmap_id()
    nodes: list[FlowchartShape] = []
    connectors: list[ConnectorShape] = []
    root_w, root_h = _node_size(root.title, root.level)
    root_shape = FlowchartShape(
        "org_box",
        center[0] - root_w / 2,
        center[1] - root_h / 2,
        root_w,
        root_h,
        root.title,
        style=_node_style(root.level),
        metadata={
            MINDMAP_ID: mindmap_id,
            MINDMAP_PARENT_ID: "",
            MINDMAP_COLLAPSED: False,
            MINDMAP_SIDE: "root",
        },
    )
    nodes.append(root_shape)
    _place_side(root.children[::2], "right", root_shape, center[0] + 260, center[1], mindmap_id, nodes, connectors)
    _place_side(root.children[1::2], "left", root_shape, center[0] - 260, center[1], mindmap_id, nodes, connectors)
    return nodes, connectors


def _place_side(
    children: Iterable[MindMapTreeNode],
    side: str,
    parent_shape: FlowchartShape,
    x: float,
    center_y: float,
    mindmap_id: str,
    nodes: list[FlowchartShape],
    connectors: list[ConnectorShape],
) -> None:
    child_list = list(children)
    if not child_list:
        return
    unit = 82
    total_units = sum(_subtree_size(child) for child in child_list)
    cursor_y = center_y - (total_units - 1) * unit / 2
    for child in child_list:
        span = _subtree_size(child)
        child_y = cursor_y + (span - 1) * unit / 2
        shape = _make_node(child, x, child_y, side, parent_shape.id, mindmap_id)
        nodes.append(shape)
        connectors.append(_make_connector(parent_shape, shape, mindmap_id))
        next_x = x + (230 if side == "right" else -230)
        _place_side(child.children, side, shape, next_x, child_y, mindmap_id, nodes, connectors)
        cursor_y += span * unit


def _subtree_size(node: MindMapTreeNode) -> int:
    return max(1, sum(_subtree_size(child) for child in node.children))


def _make_node(
    node: MindMapTreeNode,
    center_x: float,
    center_y: float,
    side: str,
    parent_id: str,
    mindmap_id: str,
) -> FlowchartShape:
    width, height = _node_size(node.title, node.level)
    return FlowchartShape(
        "org_box",
        center_x - width / 2,
        center_y - height / 2,
        width,
        height,
        node.title,
        style=_node_style(node.level),
        metadata={
            MINDMAP_ID: mindmap_id,
            MINDMAP_PARENT_ID: parent_id,
            MINDMAP_COLLAPSED: False,
            MINDMAP_SIDE: side,
        },
    )


def _make_connector(parent: FlowchartShape, child: FlowchartShape, mindmap_id: str) -> ConnectorShape:
    side = child.metadata.get(MINDMAP_SIDE, "right")
    return ConnectorShape(
        parent.id,
        child.id,
        start_anchor="left" if side == "left" else "right",
        end_anchor="right" if side == "left" else "left",
        kind="bezier",
        arrow_end="none",
        style=ShapeStyle(fill=None, stroke="#93C5FD", stroke_width=2),
        metadata={
            MINDMAP_ID: mindmap_id,
            MINDMAP_PARENT_ID: parent.id,
            MINDMAP_CHILD_ID: child.id,
        },
    )


def _node_style(level: int) -> ShapeStyle:
    if level == 1:
        return ShapeStyle(
            fill="#3B82F6",
            stroke="#BFDBFE",
            stroke_width=2,
            text_color="#FFFFFF",
            font_size=16,
            bold=True,
        )
    return ShapeStyle(fill="#1F2937", stroke="#93C5FD", stroke_width=2, text_color="#E5E7EB", font_size=13)


def _node_size(title: str, level: int) -> tuple[float, float]:
    width = max(110, min(220, 32 + len(title) * 9))
    if level == 1:
        width = max(width, 160)
    return float(width), 54.0 if level == 1 else 46.0
