from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.document import Document
from core.shapes import ConnectorShape, GroupShape, Shape, new_id, shape_from_dict


@dataclass
class ComponentTemplate:
    name: str
    children: list[dict]
    connectors: list[dict]
    metadata: dict[str, str]

    @classmethod
    def from_group(cls, group: GroupShape) -> "ComponentTemplate":
        return cls(
            name=group.name,
            children=[child.to_dict() for child in group.children],
            connectors=[connector.to_dict() for connector in group.connectors],
            metadata=dict(group.metadata),
        )

    def instantiate_at(self, x: float, y: float) -> GroupShape:
        children = [shape_from_dict(payload) for payload in self.children]
        connectors = [ConnectorShape.from_dict(payload) for payload in self.connectors]
        old_to_new: dict[str, str] = {}
        for child in children:
            old_id = child.id
            child.id = _new_like_id(child)
            old_to_new[old_id] = child.id
        for connector in connectors:
            connector.id = new_id("conn")
            connector.start_shape_id = old_to_new.get(connector.start_shape_id, connector.start_shape_id)
            connector.end_shape_id = old_to_new.get(connector.end_shape_id, connector.end_shape_id)
        group = GroupShape(self.name, children, connectors, dict(self.metadata))
        left, top, _right, _bottom = group.bounds()
        group.move(x - left, y - top)
        return group

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "children": self.children,
            "connectors": self.connectors,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ComponentTemplate":
        return cls(
            name=str(payload.get("name", "组件")),
            children=list(payload.get("children", [])),
            connectors=list(payload.get("connectors", [])),
            metadata={str(key): str(value) for key, value in payload.get("metadata", {}).items()},
        )


class ComponentLibrary:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.templates: list[ComponentTemplate] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.templates = []
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.templates = [ComponentTemplate.from_dict(item) for item in payload.get("templates", [])]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": "1.0", "templates": [template.to_dict() for template in self.templates]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_from_group(self, group: GroupShape) -> ComponentTemplate:
        template = ComponentTemplate.from_group(group)
        self.templates.append(template)
        self.save()
        return template

    def delete(self, index: int) -> bool:
        if index < 0 or index >= len(self.templates):
            return False
        del self.templates[index]
        self.save()
        return True


def build_group_from_selection(
    document: Document,
    selected_ids: set[str] | list[str],
    *,
    name: str = "自定义组件",
    metadata: dict[str, str] | None = None,
) -> GroupShape:
    selected = set(selected_ids)
    children: list[Shape] = []
    for shape in document.shapes:
        if shape.id in selected:
            children.append(shape_from_dict(shape.to_dict()))
    connectors = [
        ConnectorShape.from_dict(connector.to_dict())
        for connector in document.connectors
        if connector.start_shape_id in selected and connector.end_shape_id in selected
    ]
    return GroupShape(name=name, children=children, connectors=connectors, metadata=dict(metadata or {}))


def _new_like_id(shape: Shape) -> str:
    if shape.__class__.__name__ == "LineShape":
        return new_id("line")
    if shape.__class__.__name__ == "CurveShape":
        return new_id("curve")
    if shape.__class__.__name__ == "RasterImageShape":
        return new_id("image")
    if shape.__class__.__name__ == "GroupShape":
        return new_id("group")
    return new_id("shape")
