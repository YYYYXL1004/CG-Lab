import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.shapes import FlowchartShape, LineShape
from engine.algorithm_replay import build_shape_replay
from engine.animation import animated_flow_pixels


class AnimationReplayTests(unittest.TestCase):
    def test_animated_flow_pixels_shift_along_sampled_path(self):
        route = [(0, 0), (12, 0)]

        first = animated_flow_pixels(route, phase=0, spacing=6, pulse_length=2)
        shifted = animated_flow_pixels(route, phase=1, spacing=6, pulse_length=2)

        self.assertNotEqual(first, shifted)
        self.assertTrue(first)
        self.assertTrue(all(y == 0 for _, y in first))
        self.assertTrue(all(0 <= x <= 12 for x, _ in first))

    def test_line_replay_builds_cumulative_bresenham_frames(self):
        sequence = build_shape_replay(LineShape(0, 0, 4, 0), frame_count=3)

        self.assertIn("Bresenham", sequence.title)
        self.assertGreaterEqual(len(sequence.frames), 3)
        self.assertEqual(sequence.frames[-1].points, [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)])
        lengths = [len(frame.points) for frame in sequence.frames]
        self.assertEqual(lengths, sorted(lengths))

    def test_flowchart_replay_includes_scanline_fill_points(self):
        shape = FlowchartShape("process", 1, 1, 6, 4)

        sequence = build_shape_replay(shape, frame_count=4)
        fill_frames = [frame for frame in sequence.frames if "扫描线填充" in frame.label]

        self.assertTrue(fill_frames)
        self.assertIn((3, 3), fill_frames[-1].points)


if __name__ == "__main__":
    unittest.main()
