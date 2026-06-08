import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import (
    COMMAND_BAR_GROUPS,
    FILE_MENU_ACTIONS,
    REQUIRED_THEME_TOKENS,
    THEMES,
    can_group_selection,
    can_ungroup_selection,
    TOOL_SPECS,
    bind_mousewheel_tree,
    clamp_drag_width,
    combobox_style_options,
    connector_endpoint_hit,
    densify_polyline,
    flow_pick_hint,
    format_status_parts,
    inspector_context_for,
    missing_theme_tokens,
    modern_text_editor_options,
    mousewheel_units,
    split_polyline_by_circle,
    tool_hint,
    update_connector_endpoint_anchor,
    viewport_center_world,
)
from app import VectorFlowApp
from core.document import Document
from core.style import ShapeStyle
from core.shapes import ConnectorShape, CurveShape, FlowchartShape, GroupShape, LineShape, TextShape
from engine.canvas_renderer import CanvasRenderer


class UiShellTests(unittest.TestCase):
    def test_themes_define_required_editor_tokens(self):
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                self.assertEqual(missing_theme_tokens(theme), [])
                self.assertTrue(REQUIRED_THEME_TOKENS.issubset(theme.keys()))

    def test_combobox_style_uses_readable_theme_colors(self):
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                options = combobox_style_options(theme)

                self.assertEqual(options["configure"]["fieldbackground"], theme["combobox_bg"])
                self.assertEqual(options["configure"]["selectbackground"], theme["combobox_bg"])
                self.assertEqual(options["configure"]["selectforeground"], theme["combobox_fg"])
                self.assertIn(("readonly", theme["combobox_bg"]), options["background_map"])
                self.assertIn(("readonly", theme["combobox_fg"]), options["foreground_map"])
                self.assertEqual(options["option_db"]["*TCombobox*Listbox.background"], theme["combobox_bg"])
                self.assertEqual(options["option_db"]["*TCombobox*Listbox.foreground"], theme["combobox_fg"])

    def test_modern_text_editor_uses_theme_colors_and_placeholder(self):
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                options = modern_text_editor_options(theme, 18)

                self.assertEqual(options["placeholder"], "输入文本")
                self.assertEqual(options["background"], theme["text_editor_bg"])
                self.assertEqual(options["foreground"], theme["text_editor_fg"])
                self.assertEqual(options["placeholder_foreground"], theme["text_editor_placeholder"])
                self.assertEqual(options["highlightbackground"], theme["text_editor_border"])
                self.assertEqual(options["highlightcolor"], theme["text_editor_focus"])
                self.assertEqual(options["padx"], 10)
                self.assertEqual(options["pady"], 8)

    def test_modern_text_editor_sizes_to_existing_text(self):
        theme = THEMES["dark"]
        short = modern_text_editor_options(theme, 18, "短")
        long = modern_text_editor_options(theme, 18, "这是一段明显更长的文本")
        multi = modern_text_editor_options(theme, 18, "第一行\n第二行\n第三行")

        self.assertGreater(long["width"], short["width"])
        self.assertGreater(multi["height"], short["height"])

    def test_canvas_renderer_applies_text_shape_alignment_to_anchor_and_position(self):
        cases = [
            ("left", 14.0, "nw"),
            ("center", 70.0, "n"),
            ("right", 126.0, "ne"),
        ]

        for align, expected_x, expected_anchor in cases:
            with self.subTest(align=align):
                canvas = _FakeCanvas()
                document = Document()
                document.add_shape(
                    TextShape(
                        10,
                        20,
                        "Label",
                        width=120,
                        height=40,
                        style=ShapeStyle(text_align=align),
                    )
                )

                CanvasRenderer(canvas).render(document, show_grid=False)

                text_call = next(call for call in canvas.calls if call[0] == "create_text")
                self.assertEqual(text_call[1][0], expected_x)
                self.assertEqual(text_call[1][1], 20)
                self.assertEqual(text_call[2]["anchor"], expected_anchor)
                self.assertEqual(text_call[2]["justify"], align)

    def test_canvas_renderer_applies_flowchart_text_alignment_to_anchor_and_position(self):
        cases = [
            ("left", 24.0, "w"),
            ("center", 70.0, "center"),
            ("right", 116.0, "e"),
        ]

        for align, expected_x, expected_anchor in cases:
            with self.subTest(align=align):
                canvas = _FakeCanvas()
                document = Document()
                document.add_shape(
                    FlowchartShape(
                        "process",
                        20,
                        30,
                        100,
                        50,
                        "Step",
                        ShapeStyle(text_align=align),
                    )
                )

                CanvasRenderer(canvas).render(document, show_grid=False)

                text_call = next(call for call in canvas.calls if call[0] == "create_text")
                self.assertEqual(text_call[1][0], expected_x)
                self.assertEqual(text_call[1][1], 55.0)
                self.assertEqual(text_call[2]["anchor"], expected_anchor)
                self.assertEqual(text_call[2]["justify"], align)

    def test_theme_toggle_recolors_open_text_editor_with_modern_tokens(self):
        app = VectorFlowApp.__new__(VectorFlowApp)
        app.theme_name = "dark"
        app._inline_editor = _FakeConfigurableEditor()
        app.canvas = _FakeCanvas()
        app._inspector_canvas = None
        app._sash = _FakeConfigurableEditor()
        app._tool_sash = _FakeConfigurableEditor()
        app._layers_sash = _FakeConfigurableEditor()
        app._lib_canvases = []
        app.document = Document()
        app.theme_btn_label = _Var("")
        app.text_size_var = _Var(14)
        app._configure_style = lambda: None
        app._close_pen_panel = lambda: None
        app._update_tool_button_states = lambda: None
        app._rebuild_inspector = lambda force=False: None
        app.redraw = lambda: None

        app.toggle_theme()

        light_options = modern_text_editor_options(THEMES["light"], 14)
        self.assertEqual(app._inline_editor.config["bg"], light_options["background"])
        self.assertEqual(app._inline_editor.config["fg"], light_options["foreground"])
        self.assertEqual(app._inline_editor.config["highlightbackground"], light_options["highlightbackground"])
        self.assertEqual(app._inline_editor.config["highlightcolor"], light_options["highlightcolor"])

    def test_commit_new_text_selects_shape_and_returns_to_select_tool(self):
        app = VectorFlowApp.__new__(VectorFlowApp)
        app.document = Document()
        app.selected_ids = set()
        app.current_tool = _Var("text")
        app.text_align_var = _Var("左对齐")
        app.text_bold_var = _Var(True)
        app.text_color_var = _Var("#FFCC00")
        app.text_size_var = _Var(22)
        app._inline_edit_shape = None
        app._inline_editor = _FakeEditor("新文本", (120.0, 80.0))
        app.canvas = _FakeCanvas()
        app._push_history = lambda: None
        app.redraw = lambda: None
        app._update_tool_button_states = lambda: None
        app._rebuild_inspector = lambda force=False: None

        app._commit_inline_editor()

        self.assertEqual(len(app.document.shapes), 1)
        shape = app.document.shapes[0]
        self.assertIsInstance(shape, TextShape)
        self.assertEqual(shape.text, "新文本")
        self.assertEqual(shape.style.text_align, "left")
        self.assertTrue(shape.style.bold)
        self.assertEqual(shape.style.text_color, "#FFCC00")
        self.assertEqual(shape.style.font_size, 22)
        self.assertEqual((shape.width, shape.height), TextShape(120.0, 80.0, "新文本", style=ShapeStyle(font_size=22)).auto_size())
        self.assertEqual(app.selected_ids, {shape.id})
        self.assertEqual(app.current_tool.get(), "select")

    def test_commit_blank_new_text_does_not_create_shape(self):
        app = VectorFlowApp.__new__(VectorFlowApp)
        app.document = Document()
        app.selected_ids = set()
        app.current_tool = _Var("text")
        app._inline_edit_shape = None
        app._inline_editor = _FakeEditor("   \n", (120.0, 80.0))
        app.canvas = _FakeCanvas()
        app._push_history = lambda: None
        app.redraw = lambda: None
        app._update_tool_button_states = lambda: None
        app._rebuild_inspector = lambda force=False: None

        app._commit_inline_editor()

        self.assertEqual(app.document.shapes, [])
        self.assertEqual(app.selected_ids, set())
        self.assertEqual(app.current_tool.get(), "text")

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

    def test_menu_keeps_mindmap_template_inside_mindmap_dialog(self):
        file_labels = [item["label"] for item in FILE_MENU_ACTIONS if item["kind"] == "command"]

        self.assertEqual(file_labels.count("思维导图..."), 1)
        self.assertNotIn("思维导图模板", file_labels)
        self.assertLess(file_labels.index("SQL -> ER..."), file_labels.index("思维导图..."))

    def test_command_bar_keeps_chart_and_demo_groups_compact(self):
        groups = {group["title"]: [item["label"] for item in group["items"]] for group in COMMAND_BAR_GROUPS}

        self.assertEqual(groups["图表"], ["SQL -> ER", "Mind Map"])
        self.assertEqual(groups["演示"], ["算法回放", "物理播放", "电路秀", "电路通电", "电路开关"])
        self.assertNotIn("思维模板", groups["图表"])
        self.assertNotIn("模拟故障", groups["演示"])

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

    def test_group_action_availability_requires_multiple_unlocked_top_level_shapes(self):
        document = Document()
        first = document.add_shape(FlowchartShape("process", 0, 0, 100, 60))
        second = document.add_shape(FlowchartShape("process", 140, 0, 100, 60))
        locked = document.add_shape(FlowchartShape("process", 280, 0, 100, 60, locked=True))

        self.assertTrue(can_group_selection(document, {first.id, second.id}))
        self.assertFalse(can_group_selection(document, {first.id}))
        self.assertFalse(can_group_selection(document, {first.id, locked.id}))

    def test_ungroup_action_availability_requires_single_unlocked_group(self):
        document = Document()
        child = FlowchartShape("process", 0, 0, 100, 60)
        group = document.add_shape(GroupShape("Pair", [child]))
        flow = document.add_shape(FlowchartShape("process", 140, 0, 100, 60))

        self.assertTrue(can_ungroup_selection(document, {group.id}))
        self.assertFalse(can_ungroup_selection(document, {flow.id}))
        group.locked = True
        self.assertFalse(can_ungroup_selection(document, {group.id}))

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


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeEditor:
    def __init__(self, text, world_pos):
        self.text = text
        self._world_pos = world_pos
        self.destroyed = False

    def get(self, *_args):
        return self.text

    def destroy(self):
        self.destroyed = True


class _FakeConfigurableEditor:
    def __init__(self):
        self.config = {}

    def winfo_exists(self):
        return True

    def configure(self, **kwargs):
        self.config.update(kwargs)


class _FakeCanvas:
    def __init__(self, width=500, height=360):
        self.width = width
        self.height = height
        self.calls = []
        self.deleted = []
        self.lowered = []
        self.config = {}

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def delete(self, tag):
        self.deleted.append(tag)
        self.calls.append(("delete", (tag,), {}))

    def configure(self, **kwargs):
        self.config.update(kwargs)
        self.calls.append(("configure", (), kwargs))

    def tag_lower(self, tag):
        self.lowered.append(tag)
        self.calls.append(("tag_lower", (tag,), {}))

    def create_line(self, *args, **kwargs):
        return self._record("create_line", args, kwargs)

    def create_polygon(self, *args, **kwargs):
        return self._record("create_polygon", args, kwargs)

    def create_oval(self, *args, **kwargs):
        return self._record("create_oval", args, kwargs)

    def create_rectangle(self, *args, **kwargs):
        return self._record("create_rectangle", args, kwargs)

    def create_text(self, *args, **kwargs):
        return self._record("create_text", args, kwargs)

    def create_image(self, *args, **kwargs):
        return self._record("create_image", args, kwargs)

    def _record(self, name, args, kwargs):
        self.calls.append((name, args, kwargs))
        return len(self.calls)


if __name__ == "__main__":
    unittest.main()
