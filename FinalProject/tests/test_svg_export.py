import base64
import sys
import unittest
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.document import Document
from core.shapes import ConnectorShape, FlowchartShape, LineShape, RasterImageShape, TextShape
from core.style import ShapeStyle
from engine.svg_renderer import SvgRenderer


SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


def _png_data_url() -> str:
    image = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class SvgExportTests(unittest.TestCase):
    def test_svg_renderer_exports_vector_shapes_text_connectors_and_images(self):
        document = Document(background="#112233")
        start = document.add_shape(
            FlowchartShape(
                kind="process",
                x=10,
                y=15,
                width=80,
                height=40,
                text="Start",
                style=ShapeStyle(fill="#AA3344", stroke="#335577", stroke_width=3),
            )
        )
        end = document.add_shape(
            FlowchartShape(kind="decision", x=150, y=15, width=80, height=40, text="A < B")
        )
        document.add_shape(
            LineShape(
                x1=12,
                y1=90,
                x2=100,
                y2=90,
                style=ShapeStyle(stroke="#00FF00", fill=None, stroke_width=2, dash=[4, 2]),
            )
        )
        document.add_shape(
            TextShape(
                x=10,
                y=110,
                text='5 < 7 & "ok"',
                style=ShapeStyle(fill=None, text_color="#FFFFFF", font_size=18, bold=True),
            )
        )
        document.add_shape(RasterImageShape(x=120, y=90, width=20, height=20, data_url=_png_data_url()))
        document.add_connector(ConnectorShape(start.id, end.id, "right", "left", kind="straight"))

        svg = SvgRenderer(260, 160).render(document, show_grid=False)

        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)
        self.assertIn("5 &lt; 7 &amp; &quot;ok&quot;", svg)
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(root.attrib["width"], "260")
        self.assertEqual(root.attrib["height"], "160")
        self.assertEqual(root.attrib["viewBox"], "0 0 260 160")
        self.assertEqual(root.find("svg:rect", SVG_NS).attrib["fill"], "#112233")
        self.assertIsNotNone(root.find("svg:polygon", SVG_NS))
        self.assertIsNotNone(root.find("svg:polyline", SVG_NS))
        self.assertIsNotNone(root.find("svg:text", SVG_NS))
        image = root.find("svg:image", SVG_NS)
        self.assertIsNotNone(image)
        self.assertEqual(image.attrib["href"], _png_data_url())


if __name__ == "__main__":
    unittest.main()
