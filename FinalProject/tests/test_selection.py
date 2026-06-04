import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.document import Document
from core.shapes import FlowchartShape, LineShape
from engine.selection import (
    apply_group_resize,
    apply_group_rotation,
    bounds_from_handle,
    handle_at,
    rotation_delta,
    rotation_handle_point,
    selection_bounds,
    shapes_in_rect,
)


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

    def test_handle_at_detects_resize_edges_between_handles(self):
        self.assertEqual(handle_at((10, 20, 110, 90), (110, 36), tolerance=6), "e")
        self.assertEqual(handle_at((10, 20, 110, 90), (36, 20), tolerance=6), "n")
        self.assertIsNone(handle_at((10, 20, 110, 90), (60, 55), tolerance=6))

    def test_handle_at_detects_top_rotation_handle(self):
        bounds = (10, 20, 110, 90)
        self.assertEqual(rotation_handle_point(bounds), (60, -10))
        self.assertEqual(handle_at(bounds, (60, -10), tolerance=6), "rotate")
        self.assertIsNone(handle_at(bounds, (60, 2), tolerance=6))

    def test_rotation_delta_uses_angle_change_around_selection_center(self):
        bounds = (10, 20, 110, 90)
        self.assertAlmostEqual(rotation_delta(bounds, (60, -10), (125, 55)), 90)
        self.assertAlmostEqual(rotation_delta(bounds, (60, -10), (-5, 55)), -90)

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

    def test_apply_group_rotation_rotates_shapes_around_selection_center_from_original_snapshot(self):
        document = Document()
        first = document.add_shape(FlowchartShape("process", 0, 0, 20, 20))
        second = document.add_shape(FlowchartShape("process", 80, 0, 20, 20))
        line = document.add_shape(LineShape(0, 30, 100, 30))
        original = {shape.id: shape.to_dict() for shape in document.shapes}
        old_bounds = selection_bounds(document, [first.id, second.id, line.id])

        apply_group_rotation(document, [first.id, second.id, line.id], original, old_bounds, 90)

        self.assertAlmostEqual(first.x, 45)
        self.assertAlmostEqual(first.y, -35)
        self.assertAlmostEqual(first.rotation, 90)
        self.assertAlmostEqual(second.x, 45)
        self.assertAlmostEqual(second.y, 45)
        self.assertAlmostEqual(second.rotation, 90)
        self.assertAlmostEqual(line.x1, 35)
        self.assertAlmostEqual(line.y1, -35)
        self.assertAlmostEqual(line.x2, 35)
        self.assertAlmostEqual(line.y2, 65)


if __name__ == "__main__":
    unittest.main()
