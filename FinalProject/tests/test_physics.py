import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.document import Document
from core.shapes import FlowchartShape, LineShape
from engine.physics import (
    Body,
    PhysicsWorld,
    Vec2,
    build_world,
    collide,
    convex_hull,
    sync_to_document,
)


def _circle(cx, cy, r, **kwargs):
    mass = math.pi * r * r
    return Body(
        kind="circle",
        pos=Vec2(cx, cy),
        radius=r,
        inv_mass=1.0 / mass,
        inv_inertia=1.0 / (0.5 * mass * r * r),
        **kwargs,
    )


class Vec2Tests(unittest.TestCase):
    def test_dot_cross_and_normalize(self):
        a = Vec2(3, 4)
        self.assertAlmostEqual(a.length(), 5.0)
        self.assertAlmostEqual(a.normalized().length(), 1.0)
        self.assertAlmostEqual(Vec2(1, 0).cross(Vec2(0, 1)), 1.0)
        self.assertAlmostEqual(Vec2(1, 0).dot(Vec2(0, 1)), 0.0)


class ConvexHullTests(unittest.TestCase):
    def test_hull_of_square_with_interior_point(self):
        pts = [(0, 0), (10, 0), (10, 10), (0, 10), (5, 5)]
        hull = convex_hull(pts)
        self.assertEqual(len(hull), 4)
        self.assertNotIn((5, 5), hull)


class GravityTests(unittest.TestCase):
    def test_circle_falls_under_gravity(self):
        world = PhysicsWorld(gravity=1000.0)
        ball = world.add(_circle(0, 0, 10))
        start_y = ball.pos.y
        for _ in range(30):
            world.step(1 / 60)
        self.assertGreater(ball.pos.y, start_y)
        self.assertGreater(ball.vel.y, 0)

    def test_all_bodies_fall_at_same_rate_regardless_of_mass(self):
        world = PhysicsWorld(gravity=1000.0)
        small = world.add(_circle(0, 0, 5))
        big = world.add(_circle(500, 0, 50))
        for _ in range(20):
            world.step(1 / 60)
        self.assertAlmostEqual(small.pos.y, big.pos.y, places=3)


class CollisionTests(unittest.TestCase):
    def test_circle_circle_overlap_produces_manifold(self):
        a = _circle(0, 0, 10)
        b = _circle(15, 0, 10)
        m = collide(a, b)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(m.penetration, 5.0, places=5)
        # 法线由 a 指向 b（+x 方向）。
        self.assertGreater(m.normal.x, 0.9)

    def test_separated_circles_do_not_collide(self):
        self.assertIsNone(collide(_circle(0, 0, 10), _circle(100, 0, 10)))

    def test_two_circles_bounce_apart(self):
        world = PhysicsWorld(gravity=0.0)
        a = world.add(_circle(0, 0, 10, restitution=1.0))
        b = world.add(_circle(15, 0, 10, restitution=1.0))
        a.vel = Vec2(50, 0)
        for _ in range(60):
            world.step(1 / 60)
        # 弹开后 b 在 a 右侧且二者分离。
        self.assertGreater(b.pos.x - a.pos.x, 20)
        self.assertGreater(b.vel.x, a.vel.x)


class RestingTests(unittest.TestCase):
    def test_ball_settles_on_floor_without_exploding(self):
        # 容器底部 y=200，球从上方落下应停在底面附近。
        document = Document()
        document.add_shape(FlowchartShape(kind="circle", x=90, y=0, width=20, height=20))
        world = build_world(document, (0, -100, 200, 200), gravity=1600.0)
        ball = world.dynamic_bodies[0]
        for _ in range(240):
            world.step(1 / 60)
        # 球心稳定在底面上方约一个半径处，且竖直速度趋近 0。
        self.assertLess(ball.pos.y, 200)
        self.assertGreater(ball.pos.y, 150)
        self.assertLess(abs(ball.vel.y), 30)
        self.assertTrue(math.isfinite(ball.pos.x))
        self.assertTrue(math.isfinite(ball.pos.y))

    def test_box_rests_on_floor(self):
        document = Document()
        document.add_shape(FlowchartShape(kind="process", x=70, y=0, width=60, height=40))
        world = build_world(document, (0, -100, 200, 300), gravity=1600.0)
        box = world.dynamic_bodies[0]
        for _ in range(300):
            world.step(1 / 60)
        self.assertGreater(box.pos.y, 200)
        self.assertLess(box.pos.y, 300)
        self.assertLess(abs(box.vel.y), 30)


class SlopeTests(unittest.TestCase):
    def test_static_line_does_not_move(self):
        document = Document()
        line = LineShape(x1=0, y1=100, x2=200, y2=160)
        document.add_shape(line)
        world = build_world(document, (-50, -200, 250, 400))
        # 直线对应的是静止刚体。
        static_count = sum(1 for b in world.bodies if b.static)
        self.assertGreaterEqual(static_count, 5)  # 4 walls + 1 slope

    def test_ball_on_slope_slides_sideways(self):
        document = Document()
        document.add_shape(LineShape(x1=0, y1=120, x2=240, y2=240))  # 向右下倾斜的斜坡
        document.add_shape(FlowchartShape(kind="circle", x=40, y=0, width=24, height=24))
        world = build_world(document, (-50, -200, 300, 500), gravity=1600.0)
        ball = next(b for b in world.dynamic_bodies if b.kind == "circle")
        start_x = ball.pos.x
        for _ in range(180):
            world.step(1 / 60)
        # 沿斜坡下滑，x 应增大。
        self.assertGreater(ball.pos.x, start_x)


class WritebackTests(unittest.TestCase):
    def test_sync_writes_position_back_to_shape(self):
        document = Document()
        shape = FlowchartShape(kind="process", x=100, y=50, width=60, height=40)
        document.add_shape(shape)
        world = build_world(document, (0, -100, 400, 400), gravity=1600.0)
        for _ in range(60):
            world.step(1 / 60)
        sync_to_document(world)
        # 图元应已下落（y 增大）。
        self.assertGreater(shape.y, 50)


if __name__ == "__main__":
    unittest.main()
