import os
import sys
import unittest
import math

sys.path.insert(0, os.path.dirname(__file__))

from algorithms import (Camera, midpoint_line, project_point, render_triangles,
                        transformed_vertices)


class Lab5AlgorithmTests(unittest.TestCase):
    def test_midpoint_line_draws_diagonal_without_library_line(self):
        self.assertEqual(midpoint_line(0, 0, 3, 3),
                         [(0, 0), (1, 1), (2, 2), (3, 3)])

    def test_project_point_rejects_points_behind_camera(self):
        camera = Camera(position=(0, 0, 0), yaw=0.0, pitch=0.0)
        self.assertIsNone(project_point((0, 0, -1), camera, 800, 600, 500))

    def test_z_buffer_keeps_nearer_triangle_pixel(self):
        far = {
            "points": [(1, 1, 5), (5, 1, 5), (1, 5, 5)],
            "colors": [(20, 20, 200), (20, 20, 200), (20, 20, 200)],
        }
        near = {
            "points": [(1, 1, 2), (5, 1, 2), (1, 5, 2)],
            "colors": [(200, 30, 30), (200, 30, 30), (200, 30, 30)],
        }

        pixels = render_triangles([far, near], 8, 8)

        self.assertEqual(pixels[(2, 2)], (200, 30, 30))

    def test_transformed_vertices_support_x_axis_rotation(self):
        result = transformed_vertices(
            [(0.0, 1.0, 0.0)], angle_y=0.0,
            offset=(0.0, 0.0, 0.0), angle_x=math.pi / 2)

        self.assertAlmostEqual(result[0][1], 0.0, places=6)
        self.assertAlmostEqual(result[0][2], 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
