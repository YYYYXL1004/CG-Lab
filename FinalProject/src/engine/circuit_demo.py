from __future__ import annotations

from dataclasses import dataclass

from core.document import Document
from core.shapes import ConnectorShape, FlowchartShape
from core.style import ShapeStyle


@dataclass(frozen=True)
class CircuitDemo:
    document: Document
    connector_ids: tuple[str, ...]
    main_connector_ids: tuple[str, ...]
    upper_branch_connector_ids: tuple[str, ...]
    lower_branch_connector_ids: tuple[str, ...]
    normal_connector_ids: tuple[str, ...]
    fault_connector_ids: tuple[str, ...]
    main_shape_ids: tuple[str, ...]
    upper_branch_shape_ids: tuple[str, ...]
    lower_branch_shape_ids: tuple[str, ...]
    led_ids: tuple[str, ...]
    safe_led_id: str
    fault_led_id: str
    switch_id: str
    main_resistor_id: str
    fault_shape_id: str


def build_circuit_demo_document() -> CircuitDemo:
    document = Document(title="一键通电电路演示", background="#101820", grid_size=20, snap_enabled=True)
    wire_style = ShapeStyle(stroke="#5F6F7A", fill=None, stroke_width=3)

    def style(stroke: str = "#D7E4EA", fill: str | None = None, text: str = "#D7E4EA") -> ShapeStyle:
        return ShapeStyle(stroke=stroke, fill=fill, stroke_width=3, text_color=text, font_size=14, text_align="center", bold=True)

    battery = _add(document, FlowchartShape("battery", 110, 300, 80, 60, "", style("#F4D35E")))
    switch = _add(document, FlowchartShape("switch", 240, 300, 100, 60, "S1", style("#D7E4EA")))
    r1 = _add(document, FlowchartShape("resistor", 390, 300, 120, 60, "R1", style("#F4A261")))
    node_in = _add(document, FlowchartShape("circle", 560, 320, 20, 20, "", style("#5BFFCF", "#5BFFCF")))

    capacitor = _add(document, FlowchartShape("capacitor", 650, 185, 80, 70, "C1", style("#A7C7FF")))
    safe_led = _add(document, FlowchartShape("led", 810, 185, 120, 70, "LED1", style("#92E6A7")))
    node_out = _add(document, FlowchartShape("circle", 1130, 320, 20, 20, "", style("#5BFFCF", "#5BFFCF")))

    r2 = _add(document, FlowchartShape("resistor", 650, 430, 120, 60, "R2", style("#F4A261")))
    inductor = _add(document, FlowchartShape("inductor", 820, 430, 130, 60, "L1", style("#B8A1FF")))
    fault_led = _add(document, FlowchartShape("led", 990, 430, 110, 70, "LED2", style("#92E6A7")))
    ground = _add(document, FlowchartShape("ground", 560, 650, 80, 70, "", style("#D7E4EA")))
    source = _add(document, FlowchartShape("voltage_source", 1210, 275, 90, 90, "V", style("#F4D35E")))

    def wire(a: FlowchartShape, b: FlowchartShape, start: str, end: str, kind: str = "straight") -> ConnectorShape:
        connector = ConnectorShape(a.id, b.id, start, end, kind=kind, arrow_start="none", arrow_end="none", style=wire_style)
        document.add_connector(connector)
        return connector

    c1 = wire(battery, switch, "right", "left")
    c2 = wire(switch, r1, "right", "left")
    c3 = wire(r1, node_in, "right", "left")
    c4 = wire(node_in, capacitor, "top", "left", "elbow")
    c5 = wire(capacitor, safe_led, "right", "left")
    c6 = wire(safe_led, node_out, "right", "top", "elbow")
    c7 = wire(node_in, r2, "bottom", "left", "elbow")
    c8 = wire(r2, inductor, "right", "left")
    c9 = wire(inductor, fault_led, "right", "left")
    c10 = wire(fault_led, node_out, "right", "bottom", "elbow")
    c11 = wire(node_out, source, "top", "top", "elbow")
    c12 = wire(source, ground, "bottom", "right", "elbow")
    c13 = wire(ground, battery, "left", "bottom", "elbow")

    all_ids = tuple(connector.id for connector in document.connectors)
    main_connector_ids = tuple(connector.id for connector in (c1, c2, c3, c11, c12, c13))
    upper_branch_connector_ids = tuple(connector.id for connector in (c4, c5, c6))
    lower_branch_connector_ids = tuple(connector.id for connector in (c7, c8, c9, c10))
    normal_connector_ids = main_connector_ids + upper_branch_connector_ids
    return CircuitDemo(
        document=document,
        connector_ids=all_ids,
        main_connector_ids=main_connector_ids,
        upper_branch_connector_ids=upper_branch_connector_ids,
        lower_branch_connector_ids=lower_branch_connector_ids,
        normal_connector_ids=normal_connector_ids,
        fault_connector_ids=lower_branch_connector_ids,
        main_shape_ids=(battery.id, switch.id, r1.id, node_in.id, node_out.id, source.id, ground.id),
        upper_branch_shape_ids=(capacitor.id, safe_led.id),
        lower_branch_shape_ids=(r2.id, inductor.id, fault_led.id),
        led_ids=(safe_led.id, fault_led.id),
        safe_led_id=safe_led.id,
        fault_led_id=fault_led.id,
        switch_id=switch.id,
        main_resistor_id=r1.id,
        fault_shape_id=r2.id,
    )


def circuit_visual_state(
    demo: CircuitDemo,
    *,
    powered: bool,
    switch_closed: bool,
    fault_active: bool,
    phase: int,
) -> dict:
    circuit = _inspect_circuit(demo)
    shape_ids = circuit["shape_ids"]
    connector_ids = circuit["connector_ids"]
    main_ready = circuit["main_ready"]
    upper_ready = circuit["upper_ready"]
    lower_ready_without_fault = circuit["lower_ready"]
    lower_ready = lower_ready_without_fault and not fault_active
    route_ready = main_ready and (upper_ready or lower_ready)

    if not powered or not switch_closed or not route_ready:
        fault_ids = set(circuit["missing_shape_ids"])
        return {
            "powered": False,
            "phase": phase,
            "energized_connector_ids": set(),
            "glowing_shape_ids": set(),
            "fault_shape_ids": fault_ids,
            "fault_shape_id": None,
            "open_switch_ids": {demo.switch_id} & shape_ids if powered else set(),
            "closed_switch_ids": set(),
            "message": _off_message(powered, switch_closed, main_ready, upper_ready, lower_ready_without_fault),
        }

    energized = set(demo.main_connector_ids)
    glowing = set()
    if upper_ready:
        energized.update(demo.upper_branch_connector_ids)
        glowing.add(demo.safe_led_id)
    if lower_ready:
        energized.update(demo.lower_branch_connector_ids)
        glowing.add(demo.fault_led_id)
    energized &= connector_ids
    glowing &= shape_ids

    if fault_active:
        fault_ids = ({demo.fault_shape_id} & shape_ids) | set(circuit["missing_shape_ids"])
        return {
            "powered": True,
            "phase": phase,
            "energized_connector_ids": energized,
            "glowing_shape_ids": glowing,
            "fault_shape_ids": fault_ids,
            "fault_shape_id": demo.fault_shape_id if demo.fault_shape_id in shape_ids else None,
            "open_switch_ids": set(),
            "closed_switch_ids": {demo.switch_id} & shape_ids,
            "message": "检测到断路：R2 分支停止，LED2 熄灭",
        }

    return {
        "powered": True,
        "phase": phase,
        "energized_connector_ids": energized,
        "glowing_shape_ids": glowing,
        "fault_shape_ids": set(circuit["missing_shape_ids"]),
        "fault_shape_id": None,
        "open_switch_ids": set(),
        "closed_switch_ids": {demo.switch_id} & shape_ids,
        "message": _powered_message(upper_ready, lower_ready),
    }


def _inspect_circuit(demo: CircuitDemo) -> dict:
    shape_ids = {shape.id for shape in demo.document.shapes}
    connector_ids = {connector.id for connector in demo.document.connectors}
    valid_connector_ids = {
        connector.id
        for connector in demo.document.connectors
        if connector.start_shape_id in shape_ids and connector.end_shape_id in shape_ids
    }

    def path_ready(shape_ids_required: tuple[str, ...], connector_ids_required: tuple[str, ...]) -> bool:
        return set(shape_ids_required).issubset(shape_ids) and set(connector_ids_required).issubset(valid_connector_ids)

    all_required_shapes = demo.main_shape_ids + demo.upper_branch_shape_ids + demo.lower_branch_shape_ids
    return {
        "shape_ids": shape_ids,
        "connector_ids": connector_ids,
        "valid_connector_ids": valid_connector_ids,
        "missing_shape_ids": set(all_required_shapes) - shape_ids,
        "main_ready": path_ready(demo.main_shape_ids, demo.main_connector_ids),
        "upper_ready": path_ready(demo.main_shape_ids + demo.upper_branch_shape_ids, demo.main_connector_ids + demo.upper_branch_connector_ids),
        "lower_ready": path_ready(demo.main_shape_ids + demo.lower_branch_shape_ids, demo.main_connector_ids + demo.lower_branch_connector_ids),
    }


def _off_message(powered: bool, switch_closed: bool, main_ready: bool, upper_ready: bool, lower_ready: bool) -> str:
    if not powered:
        return "电路演示待机"
    if not switch_closed:
        return "开关断开，电路未通电"
    if not main_ready:
        return "主干电路不完整，电流无法形成回路"
    if not upper_ready and not lower_ready:
        return "上下分支都不完整，LED 不会发光"
    return "电路未形成完整回路"


def _powered_message(upper_ready: bool, lower_ready: bool) -> str:
    if upper_ready and lower_ready:
        return "电路已通电：电流沿双分支流动，两个 LED 发光"
    if upper_ready:
        return "电路已通电：上分支完整，LED1 发光"
    return "电路已通电：下分支完整，LED2 发光"


def _add(document: Document, shape: FlowchartShape) -> FlowchartShape:
    return document.add_shape(shape)  # type: ignore[return-value]
