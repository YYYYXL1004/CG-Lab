import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import (
    REQUIRED_THEME_TOKENS,
    THEMES,
    TOOL_SPECS,
    bind_mousewheel_tree,
    flow_pick_hint,
    format_status_parts,
    inspector_context_for,
    missing_theme_tokens,
    mousewheel_units,
    tool_hint,
    viewport_center_world,
)
from core.document import Document
from core.shapes import CurveShape, FlowchartShape, LineShape, TextShape


class UiShellTests(unittest.TestCase):
    def test_themes_define_required_editor_tokens(self):
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                self.assertEqual(missing_theme_tokens(theme), [])
                self.assertTrue(REQUIRED_THEME_TOKENS.issubset(theme.keys()))

    def test_tool_specs_cover_expected_tool_rail(self):
        self.assertEqual(
            list(TOOL_SPECS.keys()),
            ["select", "line", "curve", "text", "connector", "region_export"],
        )
        self.assertEqual(TOOL_SPECS["select"].shortcut, "V")
        self.assertIn("拖拽", tool_hint("connector"))
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
        self.assertEqual(inspector_context_for(document, {flow.id}, "select"), "text_shape")
        self.assertEqual(inspector_context_for(document, {text.id}, "select"), "text_shape")
        self.assertEqual(inspector_context_for(document, {line.id}, "select"), "shape")
        self.assertEqual(inspector_context_for(document, {curve.id}, "select"), "shape")
        self.assertEqual(inspector_context_for(document, {flow.id, line.id}, "select"), "multi")

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
