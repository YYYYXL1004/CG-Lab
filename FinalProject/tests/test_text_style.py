import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.shapes import FlowchartShape, LineShape, TextShape
from core.style import ShapeStyle
from engine.text_style import apply_text_style, clamp_font_size


class TextStyleTests(unittest.TestCase):
    def test_clamp_font_size_stays_in_editor_range(self):
        self.assertEqual(clamp_font_size(3), 8)
        self.assertEqual(clamp_font_size(24), 24)
        self.assertEqual(clamp_font_size(200), 72)

    def test_apply_text_style_updates_selected_text_capable_shapes(self):
        flow = FlowchartShape("process", 0, 0, 100, 50, "流程")
        text = TextShape(10, 10, "说明")
        line = LineShape(0, 0, 20, 20, style=ShapeStyle(text_color="#111111", font_size=12))

        changed = apply_text_style(
            [flow, text, line],
            {flow.id, text.id, line.id},
            align="left",
            bold=True,
            color="#FF0000",
            font_size=28,
        )

        self.assertEqual(changed, 2)
        for shape in (flow, text):
            self.assertEqual(shape.style.text_align, "left")
            self.assertTrue(shape.style.bold)
            self.assertEqual(shape.style.text_color, "#FF0000")
            self.assertEqual(shape.style.font_size, 28)
        self.assertEqual(line.style.font_size, 12)


if __name__ == "__main__":
    unittest.main()
