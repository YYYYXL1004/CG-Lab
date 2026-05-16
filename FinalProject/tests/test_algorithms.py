import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from algorithms.clip import cohen_sutherland_clip
from algorithms.bezier import cubic_bezier
from algorithms.ellipse import midpoint_ellipse
from algorithms.fill import scanline_fill
from algorithms.line import bresenham_line, dashed_line
from algorithms.transform import Matrix3, Point


class AlgorithmTests(unittest.TestCase):
    def test_bresenham_line_includes_endpoints_and_diagonal_pixels(self):
        pixels = bresenham_line(0, 0, 4, 4)
        self.assertEqual(pixels[0], (0, 0))
        self.assertEqual(pixels[-1], (4, 4))
        self.assertEqual(pixels, [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)])

    def test_dashed_line_skips_gap_pixels(self):
        pixels = dashed_line(0, 0, 7, 0, [2, 2])
        self.assertEqual(pixels, [(0, 0), (1, 0), (4, 0), (5, 0)])

    def test_ellipse_points_include_cardinal_extents(self):
        pixels = set(midpoint_ellipse(10, 12, 4, 2))
        self.assertIn((6, 12), pixels)
        self.assertIn((14, 12), pixels)
        self.assertIn((10, 10), pixels)
        self.assertIn((10, 14), pixels)

    def test_scanline_fill_returns_interior_pixels(self):
        filled = set(scanline_fill([(1, 1), (5, 1), (5, 4), (1, 4)]))
        self.assertIn((3, 2), filled)
        self.assertIn((4, 3), filled)
        self.assertNotIn((0, 0), filled)

    def test_cubic_bezier_starts_and_ends_at_control_points(self):
        points = cubic_bezier((0, 0), (10, 0), (10, 10), (20, 10), steps=10)
        self.assertEqual(points[0], (0, 0))
        self.assertEqual(points[-1], (20, 10))
        self.assertGreater(len(points), 5)

    def test_cohen_sutherland_clips_line_to_rectangle(self):
        clipped = cohen_sutherland_clip((-10, 5), (20, 5), (0, 0, 10, 10))
        self.assertEqual(clipped, ((0, 5), (10, 5)))

    def test_transform_composition_applies_in_order(self):
        point = Point(2, 3)
        matrix = Matrix3.translation(5, -1) @ Matrix3.scale(2, 3)
        transformed = matrix.apply(point)
        self.assertEqual((transformed.x, transformed.y), (9, 8))

    def test_rotation_around_center_preserves_distance(self):
        point = Point(12, 10)
        matrix = Matrix3.rotation(math.pi / 2, center=Point(10, 10))
        transformed = matrix.apply(point)
        self.assertAlmostEqual(transformed.x, 10, places=6)
        self.assertAlmostEqual(transformed.y, 12, places=6)


if __name__ == "__main__":
    unittest.main()
