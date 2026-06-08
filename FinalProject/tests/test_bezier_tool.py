import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import TOOL_SPECS, VectorFlowApp, inspector_context_for
from core.document import Document
from core.shapes import BezierShape, shape_from_dict
from core.style import ShapeStyle
from engine.renderer import Renderer
from engine.svg_renderer import SvgRenderer


SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


class BezierToolTests(unittest.TestCase):
    def test_bezier_shape_round_trips_and_transforms_control_points(self):
        shape = BezierShape(
            points=[(10, 20), (40, 5), (80, 60), (120, 30)],
            style=ShapeStyle(stroke="#123456", fill=None, stroke_width=3, dash=[5, 2]),
            name="curve-a",
        )

        restored = shape_from_dict(json.loads(json.dumps(shape.to_dict())))

        self.assertIsInstance(restored, BezierShape)
        self.assertEqual(restored.points, [(10.0, 20.0), (40.0, 5.0), (80.0, 60.0), (120.0, 30.0)])
        self.assertEqual(restored.style.stroke, "#123456")
        self.assertEqual(restored.name, "curve-a")

        restored.move(5, -10)
        self.assertEqual(restored.points[0], (15.0, 10.0))
        self.assertEqual(restored.points[-1], (125.0, 20.0))
        x1, y1, x2, y2 = restored.bounds()
        self.assertLessEqual(x1, 15.0)
        self.assertGreaterEqual(x2, 125.0)
        self.assertLessEqual(y1, 10.0)
        self.assertGreaterEqual(y2, 50.0)

    def test_bezier_shape_renders_to_pixels_and_svg_path(self):
        document = Document(background="#000000")
        document.add_shape(
            BezierShape(
                points=[(10, 80), (40, 10), (90, 130), (130, 50)],
                style=ShapeStyle(stroke="#FF0000", fill=None, stroke_width=3),
            )
        )

        image = Renderer(160, 150).render(document, show_grid=False)
        svg = SvgRenderer(160, 150).render(document, show_grid=False)

        self.assertIn((255, 0, 0, 255), image.getdata())
        root = ET.fromstring(svg)
        path = root.find("svg:path", SVG_NS)
        self.assertIsNotNone(path)
        self.assertIn("C", path.attrib["d"])
        self.assertEqual(path.attrib["stroke"], "#FF0000")
        self.assertEqual(path.attrib["fill"], "none")

    def test_ui_tool_specs_include_bezier_tool(self):
        self.assertIn("bezier", TOOL_SPECS)
        self.assertEqual(TOOL_SPECS["bezier"].shortcut, "B")
        self.assertEqual(inspector_context_for(Document(), set(), "bezier"), "bezier_tool")

    def test_app_edits_arbitrary_bezier_control_points_until_commit(self):
        app = VectorFlowApp.__new__(VectorFlowApp)
        app.document = Document()
        app._bezier_points = []
        app._bezier_drag_index = None
        app.selected_ids = set()
        app.pen_color = _Var("#AA0000")
        app.pen_width = _Var(4)
        app.pen_dash = _Var("solid")
        app._status_hint = None
        app._inspector_frame = None
        app.canvas = _Canvas()
        app.world_to_screen = lambda point: point
        app.redraw = lambda: None
        app._push_history = lambda: None
        app._update_status = lambda: None

        for point in [(10, 80), (40, 10), (90, 130), (130, 50), (150, 95)]:
            app._add_bezier_control_point(point)

        self.assertEqual(len(app.document.shapes), 0)
        self.assertEqual(len(app._bezier_points), 5)

        self.assertTrue(app._start_bezier_drag((41, 11), tolerance=4))
        app._drag_bezier_control_point((45, 15))
        self.assertEqual(app._bezier_points[1], (45, 15))

        self.assertTrue(app._delete_bezier_control_point((130, 50), tolerance=2))
        self.assertEqual(len(app._bezier_points), 4)
        app._commit_bezier_shape()

        self.assertEqual(len(app.document.shapes), 1)
        self.assertIsInstance(app.document.shapes[0], BezierShape)
        self.assertEqual(app.document.shapes[0].points, [(10, 80), (45, 15), (90, 130), (150, 95)])
        self.assertEqual(app.selected_ids, {app.document.shapes[0].id})
        self.assertEqual(app._bezier_points, [])

    def test_bezier_mouse_events_add_drag_delete_and_enter_commit(self):
        app = VectorFlowApp.__new__(VectorFlowApp)
        app.document = Document()
        app._bezier_points = []
        app._bezier_drag_index = None
        app.selected_ids = set()
        app.pen_color = _Var("#AA0000")
        app.pen_width = _Var(4)
        app.pen_dash = _Var("solid")
        app._status_hint = None
        app._inspector_frame = None
        app.current_tool = _Var("bezier")
        app.zoom = 1.0
        app.drag_start = None
        app.drag_mode = None
        app._physics_world = None
        app._inline_editor = None
        app._space_held = False
        app.canvas = _Canvas()
        app.screen_to_world = lambda x, y: (x, y)
        app.world_to_screen = lambda point: point
        app.stop_algorithm_replay = lambda redraw=False: None
        app.redraw = lambda: None
        app._push_history = lambda: None
        app._update_status = lambda: None

        app.on_left_down(_Event(10, 80))
        app.on_left_up(_Event(10, 80))
        app.on_left_down(_Event(40, 10))
        app.on_left_up(_Event(40, 10))
        app.on_left_down(_Event(90, 130))
        app.on_left_up(_Event(90, 130))
        app.on_left_down(_Event(40, 10))
        app.on_left_drag(_Event(44, 16))
        app.on_left_up(_Event(44, 16))
        app.on_right_click(_Event(90, 130))
        app.on_left_down(_Event(130, 50))
        app.on_left_up(_Event(130, 50))

        self.assertEqual(app._bezier_points, [(10, 80), (44, 16), (130, 50)])

        self.assertEqual(app.on_return_key(_Event(0, 0)), "break")

        self.assertEqual(len(app.document.shapes), 1)
        self.assertEqual(app.document.shapes[0].points, [(10, 80), (44, 16), (130, 50)])


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Canvas:
    def delete(self, *args, **kwargs):
        return None

    def create_line(self, *args, **kwargs):
        return 1

    def create_oval(self, *args, **kwargs):
        return 1

    def create_text(self, *args, **kwargs):
        return 1


class _Event:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.x_root = x
        self.y_root = y


if __name__ == "__main__":
    unittest.main()
