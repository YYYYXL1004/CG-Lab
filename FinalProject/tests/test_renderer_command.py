import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.document import Document
from core.shapes import FlowchartShape, LineShape
from engine.command import History
from engine.renderer import Renderer


class RendererCommandTests(unittest.TestCase):
    def test_renderer_uses_pixel_buffer_to_draw_shape(self):
        document = Document()
        document.add_shape(FlowchartShape(kind="process", x=10, y=10, width=80, height=40, text="A"))

        image = Renderer(140, 100).render(document)

        self.assertEqual(image.mode, "RGBA")
        self.assertNotEqual(image.getpixel((10, 10)), image.getpixel((0, 0)))

    def test_export_png_writes_file(self):
        document = Document()
        document.add_shape(LineShape(x1=5, y1=5, x2=40, y2=5))
        image = Renderer(60, 40).render(document)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.png"
            image.save(target, format="PNG")
            self.assertGreater(target.stat().st_size, 50)

    def test_history_undo_redo(self):
        document = Document()
        history = History()
        history.push(document.to_dict())

        document.add_shape(FlowchartShape(kind="process", x=10, y=20, width=80, height=40))
        history.push(document.to_dict())
        self.assertEqual(len(document.shapes), 1)

        history.undo(document)
        self.assertEqual(len(document.shapes), 0)

        history.redo(document)
        self.assertEqual(len(document.shapes), 1)

    def test_history_new_action_clears_redo(self):
        document = Document()
        history = History()
        history.push(document.to_dict())

        document.add_shape(FlowchartShape(kind="process", x=10, y=20, width=80, height=40))
        history.push(document.to_dict())

        history.undo(document)
        self.assertTrue(history.can_redo)

        document.add_shape(FlowchartShape(kind="terminal", x=100, y=100, width=80, height=40))
        history.push(document.to_dict())
        self.assertFalse(history.can_redo)

    def test_history_no_duplicate_states(self):
        document = Document()
        history = History()
        history.push(document.to_dict())
        history.push(document.to_dict())
        self.assertFalse(history.can_undo)


if __name__ == "__main__":
    unittest.main()
