import base64
import sys
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app
from core.document import Document
from core.shapes import RasterImageShape, shape_from_dict
from engine.canvas_renderer import CanvasRenderer
from engine.renderer import Renderer


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

    def create_image(self, *args, **kwargs) -> int:
        return self._record("create_image", args, kwargs)

    def _record(self, name: str, args: tuple, kwargs: dict) -> int:
        self.calls.append((name, args, kwargs))
        return len(self.calls)


def _png_data_url(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class BitmapImportTests(unittest.TestCase):
    def test_app_does_not_expose_cutout_entry_points(self):
        self.assertFalse(hasattr(app.VectorFlowApp, "cutout_selected_bitmap"))
        self.assertNotIn("cutout", Path(app.__file__).read_text(encoding="utf-8"))
        self.assertNotIn("抠图", Path(app.__file__).read_text(encoding="utf-8"))

    def test_raster_image_shape_round_trips_and_moves(self):
        image = Image.new("RGB", (8, 6), "white")
        shape = RasterImageShape(10, 20, 80, 60, _png_data_url(image), source_name="scene.png")

        restored = shape_from_dict(shape.to_dict())
        restored.move(5, -3)

        self.assertIsInstance(restored, RasterImageShape)
        self.assertEqual(restored.bounds(), (15, 17, 95, 77))
        self.assertEqual(restored.source_name, "scene.png")
        self.assertTrue(restored.hit_test(40, 40))

    def test_large_imported_bitmap_is_encoded_at_display_size(self):
        image = Image.new("RGB", (2000, 1000), "white")

        data_url, width, height = app.bitmap_data_url_for_display(image, max_display=520)
        decoded = Image.open(BytesIO(base64.b64decode(data_url.split(",", 1)[1])))

        self.assertEqual((width, height), (520, 260))
        self.assertEqual(decoded.size, (520, 260))
        self.assertLess(len(data_url), 100_000)

    def test_raster_image_shape_caches_decoded_and_resized_images(self):
        image = Image.new("RGB", (20, 10), "white")
        shape = RasterImageShape(0, 0, 20, 10, _png_data_url(image))

        self.assertIs(shape.image(), shape.image())
        self.assertIs(shape.resized_image(40, 20), shape.resized_image(40, 20))
        self.assertIsNot(shape.resized_image(40, 20), shape.resized_image(20, 10))

    def test_document_serializes_raster_image_shapes(self):
        image = Image.new("RGB", (4, 4), "white")
        document = Document()
        document.add_shape(RasterImageShape(0, 0, 40, 40, _png_data_url(image)))

        restored = Document.from_dict(document.to_dict())

        self.assertIsInstance(restored.shapes[0], RasterImageShape)
        self.assertEqual(restored.shapes[0].width, 40)

    def test_pillow_renderer_draws_imported_bitmap(self):
        image = Image.new("RGB", (10, 10), "white")
        image.putpixel((4, 4), (255, 0, 0))
        document = Document(background="#000000")
        document.add_shape(RasterImageShape(0, 0, 10, 10, _png_data_url(image)))

        rendered = Renderer(20, 20).render(document, show_grid=False)

        self.assertEqual(rendered.getpixel((4, 4)), (255, 0, 0, 255))

    def test_canvas_renderer_creates_photo_image_for_imported_bitmap(self):
        image = Image.new("RGB", (10, 10), "white")
        canvas = FakeCanvas()
        document = Document()
        bitmap = document.add_shape(RasterImageShape(5, 6, 20, 20, _png_data_url(image)))

        CanvasRenderer(canvas).render(document, zoom=2.0, pan=(1, 2), show_grid=False)

        image_calls = [call for call in canvas.calls if call[0] == "create_image"]
        self.assertEqual(len(image_calls), 1)
        self.assertEqual(image_calls[0][1][:2], (11.0, 14.0))
        self.assertIn("shape:" + bitmap.id, image_calls[0][2]["tags"])


if __name__ == "__main__":
    unittest.main()
