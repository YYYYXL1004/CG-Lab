import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.document import Document
from core.shapes import ConnectorShape, CurveShape, FlowchartShape, LineShape, TextShape
from core.style import ShapeStyle
from engine.algorithm_replay import ReplayFrame
from engine.canvas_renderer import CanvasRenderer


class FakeCanvas:
    def __init__(self, width: int = 500, height: int = 360) -> None:
        self.width = width
        self.height = height
        self.calls: list[tuple[str, tuple, dict]] = []
        self.deleted: list[str] = []
        self.configured: dict = {}
        self.lowered: list[str] = []

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height

    def configure(self, **kwargs) -> None:
        self.configured.update(kwargs)
        self.calls.append(("configure", (), kwargs))

    def delete(self, tag) -> None:
        self.deleted.append(tag)
        self.calls.append(("delete", (tag,), {}))

    def tag_lower(self, tag) -> None:
        self.lowered.append(tag)
        self.calls.append(("tag_lower", (tag,), {}))

    def create_line(self, *args, **kwargs) -> int:
        return self._record("create_line", args, kwargs)

    def create_polygon(self, *args, **kwargs) -> int:
        return self._record("create_polygon", args, kwargs)

    def create_oval(self, *args, **kwargs) -> int:
        return self._record("create_oval", args, kwargs)

    def create_rectangle(self, *args, **kwargs) -> int:
        return self._record("create_rectangle", args, kwargs)

    def create_text(self, *args, **kwargs) -> int:
        return self._record("create_text", args, kwargs)

    def _record(self, name: str, args: tuple, kwargs: dict) -> int:
        self.calls.append((name, args, kwargs))
        return len(self.calls)


class CanvasRendererTests(unittest.TestCase):
    def test_renders_shapes_connectors_grid_and_selection_with_canvas_items(self):
        canvas = FakeCanvas()
        document = Document(background="#111111")
        start = document.add_shape(
            FlowchartShape("process", 20, 30, 100, 50, "Start", ShapeStyle(fill="#223344"))
        )
        end = document.add_shape(FlowchartShape("decision", 180, 30, 90, 60, "OK?"))
        document.add_shape(LineShape(20, 120, 150, 140))
        document.add_shape(CurveShape(points=[(180, 120), (210, 150), (260, 115)]))
        document.add_shape(TextShape(40, 190, "Note"))
        document.add_connector(ConnectorShape(start.id, end.id, "right", "left", kind="straight"))

        CanvasRenderer(canvas).render(
            document,
            zoom=1.0,
            pan=(10, 15),
            selected_ids={start.id},
            show_grid=True,
            guides=[("vline", 120), ("hline", 90)],
            chrome={
                "grid": "#333333",
                "selection": "#00AAFF",
                "selection_handle_fill": "#FFFFFF",
                "guide": "#FF0000",
            },
        )

        call_names = [call[0] for call in canvas.calls]
        self.assertIn("native_render", canvas.deleted)
        self.assertEqual(canvas.configured["bg"], "#111111")
        self.assertGreaterEqual(call_names.count("create_line"), 5)
        self.assertIn("create_polygon", call_names)
        self.assertIn("create_text", call_names)
        self.assertIn("native_background", canvas.lowered)
        rendered_tags = [call[2].get("tags", ()) for call in canvas.calls]
        self.assertTrue(any("shape:" + start.id in tags for tags in rendered_tags))
        self.assertTrue(any("native_selection" in tags for tags in rendered_tags))
        self.assertTrue(any("native_guides" in tags for tags in rendered_tags))

    def test_replay_frame_is_drawn_as_overlay_points(self):
        canvas = FakeCanvas()
        document = Document()

        CanvasRenderer(canvas).render(
            document,
            replay_frame=ReplayFrame("line", [(10, 10), (11, 10)]),
            chrome={"replay": "#FFCC00"},
        )

        replay_calls = [
            call for call in canvas.calls
            if "native_replay" in call[2].get("tags", ())
        ]
        self.assertEqual(len(replay_calls), 2)
        self.assertTrue(all(call[0] == "create_rectangle" for call in replay_calls))

    def test_draft_render_keeps_shape_fill_for_native_canvas(self):
        canvas = FakeCanvas()
        document = Document()
        document.add_shape(
            FlowchartShape("process", 20, 30, 100, 50, "Start", ShapeStyle(fill="#AA3344"))
        )

        CanvasRenderer(canvas).render(document, draft=True)

        polygon_calls = [call for call in canvas.calls if call[0] == "create_polygon"]
        self.assertEqual(polygon_calls[0][2]["fill"], "#AA3344")


if __name__ == "__main__":
    unittest.main()
