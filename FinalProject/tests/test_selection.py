import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.document import Document
from core.shapes import FlowchartShape, LineShape
from engine.selection import apply_group_resize, bounds_from_handle, handle_at, selection_bounds, shapes_in_rect


class SelectionTests(unittest.TestCase):
    def test_shapes_in_rect_selects_multiple_intersecting_shapes(self):
        document = Document()
        first = document.add_shape(FlowchartShape("process", 10, 10, 60, 40))
        second = document.add_shape(FlowchartShape("decision", 100, 20, 60, 60))
        outside = document.add_shape(FlowchartShape("terminal", 240, 200, 80, 40))

        selected = shapes_in_rect(document, (0, 0, 190, 100))

        self.assertEqual(set(selected), {first.id, second.id})
        self.assertNotIn(outside.id, selected)

    def test_handle_at_detects_corner_resize_handle(self):
        self.assertEqual(handle_at((10, 20, 110, 90), (11, 21), tolerance=6), "nw")
        self.assertEqual(handle_at((10, 20, 110, 90), (60, 90), tolerance=6), "s")
        self.assertIsNone(handle_at((10, 20, 110, 90), (60, 60), tolerance=6))

    def test_bounds_from_handle_keeps_opposite_corner_fixed(self):
        bounds = bounds_from_handle((10, 20, 110, 90), "se", (160, 130))
        self.assertEqual(bounds, (10, 20, 160, 130))

    def test_apply_group_resize_scales_multiple_shapes_from_original_snapshot(self):
        document = Document()
        first = document.add_shape(FlowchartShape("process", 10, 10, 40, 20))
        second = document.add_shape(FlowchartShape("process", 70, 10, 40, 20))
        line = document.add_shape(LineShape(10, 40, 110, 40))
        original = {shape.id: shape.to_dict() for shape in document.shapes}
        old_bounds = selection_bounds(document, [first.id, second.id, line.id])

        apply_group_resize(document, [first.id, second.id, line.id], original, old_bounds, (10, 10, 210, 70))

        self.assertEqual((first.x, first.y, first.width, first.height), (10, 10, 80, 40))
        self.assertEqual((second.x, second.y, second.width, second.height), (130, 10, 80, 40))
        self.assertEqual((line.x1, line.y1, line.x2, line.y2), (10, 70, 210, 70))


if __name__ == "__main__":
    unittest.main()
