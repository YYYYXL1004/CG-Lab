import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import (
    REQUIRED_THEME_TOKENS,
    THEMES,
    TOOL_SPECS,
    bind_mousewheel_tree,
    clamp_drag_width,
    connector_endpoint_hit,
    densify_polyline,
    flow_pick_hint,
    format_status_parts,
    inspector_context_for,
    missing_theme_tokens,
    mousewheel_units,
    split_polyline_by_circle,
    tool_hint,
    update_connector_endpoint_anchor,
    viewport_center_world,
)
from core.document import Document
from core.shapes import ConnectorShape, CurveShape, FlowchartShape, LineShape, TextShape


class UiShellTests(unittest.TestCase):
    def test_themes_define_required_editor_tokens(self):
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                self.assertEqual(missing_theme_tokens(theme), [])
                self.assertTrue(REQUIRED_THEME_TOKENS.issubset(theme.keys()))

    def test_tool_specs_cover_expected_tool_rail(self):
        self.assertEqual(
            list(TOOL_SPECS.keys()),
            ["select", "line", "curve", "bezier", "eraser", "text", "connector", "region_export"],
        )
        self.assertEqual(TOOL_SPECS["select"].shortcut, "V")
        self.assertEqual(TOOL_SPECS["bezier"].shortcut, "B")
        self.assertEqual(TOOL_SPECS["eraser"].shortcut, "E")
        self.assertIn("拖拽", tool_hint("connector"))
        self.assertIn("擦除", tool_hint("eraser"))
        self.assertIn("区域", TOOL_SPECS["region_export"].label)

    def test_inspector_context_tracks_tool_and_selection(self):
        document = Document()
        flow = document.add_shape(FlowchartShape("process", 0, 0, 100, 60, "处理"))
        text = document.add_shape(TextShape(20, 20, "说明"))
        line = document.add_shape(LineShape(0, 0, 50, 50))
        curve = document.add_shape(CurveShape(points=[(0, 0), (20, 20), (40, 0)]))

        self.assertEqual(inspector_context_for(document, set(), "select"), "canvas")
        self.assertEqual(inspector_context_for(document, set(), "curve"), "pen")
        self.assertEqual(inspector_context_for(document, set(), "connector"), "connector_tool")
        self.assertEqual(inspector_context_for(document, set(), "eraser"), "eraser_tool")
        self.assertEqual(inspector_context_for(document, {flow.id}, "select"), "text_shape")
        self.assertEqual(inspector_context_for(document, {text.id}, "select"), "text_shape")
        self.assertEqual(inspector_context_for(document, {line.id}, "select"), "shape")
        self.assertEqual(inspector_context_for(document, {curve.id}, "select"), "shape")
        self.assertEqual(inspector_context_for(document, {flow.id, line.id}, "select"), "multi")

    def test_split_polyline_by_circle_breaks_at_covered_vertices(self):
        points = [(0, 0), (10, 0), (20, 0), (30, 0), (40, 0)]
        # 圆覆盖中间的 (20, 0)，应断成两段
        runs = split_polyline_by_circle(points, 20, 0, 5)
        self.assertEqual(runs, [[(0, 0), (10, 0)], [(30, 0), (40, 0)]])

    def test_split_polyline_by_circle_no_overlap_returns_single_run(self):
        points = [(0, 0), (10, 0), (20, 0)]
        runs = split_polyline_by_circle(points, 100, 100, 5)
        self.assertEqual(runs, [points])

    def test_densify_polyline_inserts_points_within_spacing(self):
        dense = densify_polyline([(0, 0), (10, 0)], max_spacing=2)
        self.assertEqual(dense[0], (0, 0))
        self.assertEqual(dense[-1], (10, 0))
        gaps = [
            ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            for a, b in zip(dense, dense[1:])
        ]
        self.assertTrue(all(g <= 2 + 1e-9 for g in gaps))

    def test_status_parts_include_tool_selection_zoom_and_hint(self):
        parts = format_status_parts(
            tool="select",
            zoom=1.25,
            shape_count=4,
            selection_count=2,
            cursor=(12.4, 98.6),
            hint="拖拽移动选中图形",
            can_undo=True,
        )

        self.assertEqual(parts[0], "工具: 选择")
        self.assertIn("选择: 2", parts)
        self.assertIn("缩放: 125%", parts)
        self.assertIn("图形: 4", parts)
        self.assertIn("坐标: (12, 99)", parts)
        self.assertIn("可撤销", parts)
        self.assertEqual(parts[-1], "拖拽移动选中图形")

    def test_viewport_center_world_accounts_for_zoom_and_pan(self):
        self.assertEqual(
            viewport_center_world(canvas_width=800, canvas_height=600, zoom=2.0, pan=(100, 50)),
            (150.0, 125.0),
        )

    def test_flow_pick_hint_names_click_and_double_click_workflow(self):
        hint = flow_pick_hint("process")

        self.assertIn("process", hint)
        self.assertIn("单击画布", hint)
        self.assertIn("双击图形库", hint)

    def test_mousewheel_units_normalizes_windows_and_x11_events(self):
        class Event:
            def __init__(self, delta=0, num=None):
                self.delta = delta
                self.num = num

        self.assertEqual(mousewheel_units(Event(delta=120)), -1)
        self.assertEqual(mousewheel_units(Event(delta=-240)), 2)
        self.assertEqual(mousewheel_units(Event(num=4)), -1)
        self.assertEqual(mousewheel_units(Event(num=5)), 1)

    def test_clamp_drag_width_applies_delta_and_bounds(self):
        self.assertEqual(clamp_drag_width(76, 24, 72, 180), 100)
        self.assertEqual(clamp_drag_width(76, -40, 72, 180), 72)
        self.assertEqual(clamp_drag_width(160, 80, 72, 180), 180)

    def test_connector_endpoint_hit_detects_selected_connector_handle(self):
        document = Document()
        start = document.add_shape(FlowchartShape("process", 0, 0, 100, 50))
        end = document.add_shape(FlowchartShape("process", 200, 0, 100, 50))
        connector = document.add_connector(ConnectorShape(start.id, end.id, "right", "left", kind="straight"))

        self.assertEqual(connector_endpoint_hit(document, {connector.id}, (100, 25), tolerance=6), (connector.id, "start"))
        self.assertEqual(connector_endpoint_hit(document, {connector.id}, (200, 25), tolerance=6), (connector.id, "end"))
        self.assertIsNone(connector_endpoint_hit(document, set(), (100, 25), tolerance=6))

    def test_update_connector_endpoint_anchor_projects_drag_point_to_target_shape_edge(self):
        document = Document()
        start = document.add_shape(FlowchartShape("process", 0, 0, 100, 50))
        end = document.add_shape(FlowchartShape("process", 200, 0, 100, 50))
        connector = document.add_connector(ConnectorShape(start.id, end.id, "right", "left", kind="straight"))

        self.assertTrue(update_connector_endpoint_anchor(document, connector.id, "end", (250, 70)))

        self.assertEqual(connector.end_anchor, "bottom:0.500")

    def test_bind_mousewheel_tree_binds_existing_children(self):
        calls = []

        class Widget:
            def __init__(self, children=None):
                self.children = children or []

            def bind(self, sequence, callback):
                calls.append((self, sequence, callback))

            def winfo_children(self):
                return self.children

        child = Widget()
        root = Widget([child])

        bind_mousewheel_tree(root, lambda _event: None)

        self.assertEqual(
            {(widget, sequence) for widget, sequence, _callback in calls},
            {
                (root, "<MouseWheel>"),
                (root, "<Button-4>"),
                (root, "<Button-5>"),
                (child, "<MouseWheel>"),
                (child, "<Button-4>"),
                (child, "<Button-5>"),
            },
        )


if __name__ == "__main__":
    unittest.main()
