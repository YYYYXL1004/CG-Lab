import unittest

from Lab3 import algorithms
from Lab3.algorithms import midpoint_line


class RenderingClipTests(unittest.TestCase):
    def test_splits_original_line_points_into_inside_and_outside_window(self):
        split_points = getattr(algorithms, "split_points_by_clip_rect", None)
        self.assertIsNotNone(split_points, "split_points_by_clip_rect should exist")

        points = midpoint_line(0, 5, 10, 5)
        outside, inside = split_points(points, (3, 3, 7, 7))

        self.assertEqual(outside, [(0, 5), (1, 5), (2, 5), (8, 5), (9, 5), (10, 5)])
        self.assertEqual(inside, [(3, 5), (4, 5), (5, 5), (6, 5), (7, 5)])


if __name__ == "__main__":
    unittest.main()
