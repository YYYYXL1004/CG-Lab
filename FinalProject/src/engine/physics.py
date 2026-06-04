"""自研 2D 刚体物理引擎：把矢量画布变成物理沙盒。

设计目标：在不依赖任何第三方物理库的前提下，用基于冲量（impulse-based）的
方法实现刚体的重力下落、碰撞、弹跳与摩擦，并支持旋转。

刚体几何被归约为两类，便于碰撞检测：
  - 圆（circle）：圆形/椭圆图元直接作为钢球。
  - 凸多边形（polygon）：其余图元取轮廓点的凸包作为刚体外形；直线/曲线作为
    静止的"斜坡 / 障碍"。

碰撞检测算法：
  - 圆 vs 圆：解析法。
  - 圆 vs 凸多边形：Voronoi 区域最近特征法。
  - 凸多边形 vs 凸多边形：分离轴定理（SAT）+ 参考面/入射面裁剪生成接触点。

碰撞响应：基于冲量，包含法向恢复（restitution）、库仑摩擦与角动量；穿透用
Baumgarte 位置修正消除。重力按加速度施加，因此所有物体下落速度一致。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from core.shapes import CurveShape, FlowchartShape, LineShape, TextShape

EPSILON = 1e-6
CIRCLE_KINDS = {"circle", "ellipse"}


# ── 二维向量 ──────────────────────────────────────────────────────────
class Vec2:
    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __neg__(self) -> "Vec2":
        return Vec2(-self.x, -self.y)

    def dot(self, other: "Vec2") -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Vec2") -> float:
        """二维叉积的 z 分量。"""
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> "Vec2":
        n = self.length()
        if n < EPSILON:
            return Vec2(0.0, 0.0)
        return Vec2(self.x / n, self.y / n)

    def perp(self) -> "Vec2":
        """左手法向（旋转 90°）。"""
        return Vec2(self.y, -self.x)

    def rotated(self, angle: float) -> "Vec2":
        c, s = math.cos(angle), math.sin(angle)
        return Vec2(self.x * c - self.y * s, self.x * s + self.y * c)

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


def _cross_sv(scalar: float, vec: Vec2) -> Vec2:
    """标量与向量叉积：w × r ，用于由角速度求接触点线速度。"""
    return Vec2(-scalar * vec.y, scalar * vec.x)


# ── 凸包（Andrew monotone chain）────────────────────────────────────────
def convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    pts = sorted(set((round(p[0], 4), round(p[1], 4)) for p in points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _polygon_area_centroid(verts: list[Vec2]) -> tuple[float, float, float]:
    """返回有符号面积、质心 x、质心 y（顶点相对任意原点）。"""
    area = 0.0
    cx = 0.0
    cy = 0.0
    n = len(verts)
    for i in range(n):
        a = verts[i]
        b = verts[(i + 1) % n]
        crs = a.cross(b)
        area += crs
        cx += (a.x + b.x) * crs
        cy += (a.y + b.y) * crs
    area *= 0.5
    if abs(area) < EPSILON:
        return 0.0, 0.0, 0.0
    cx /= 6.0 * area
    cy /= 6.0 * area
    return area, cx, cy


# ── 刚体 ──────────────────────────────────────────────────────────────
@dataclass
class Body:
    kind: str  # "circle" | "polygon"
    pos: Vec2  # 质心（这里取图元包围盒中心，便于写回 x/y）
    static: bool = False
    radius: float = 0.0
    verts: list[Vec2] = field(default_factory=list)  # 多边形局部顶点（相对 pos，angle=0）
    vel: Vec2 = field(default_factory=Vec2)
    angle: float = 0.0  # 相对初始姿态的增量弧度
    angular_vel: float = 0.0
    inv_mass: float = 0.0
    inv_inertia: float = 0.0
    restitution: float = 0.4
    static_friction: float = 0.5
    dynamic_friction: float = 0.4
    # 写回元数据
    shape: object = None
    base_rotation_deg: float = 0.0
    width: float = 0.0
    height: float = 0.0
    writeback: str | None = None  # "flowchart" | "text" | None
    lock_rotation: bool = False

    def world_vertices(self) -> list[Vec2]:
        return [self.pos + v.rotated(self.angle) for v in self.verts]

    def world_normals(self, world_verts: list[Vec2]) -> list[Vec2]:
        normals: list[Vec2] = []
        n = len(world_verts)
        for i in range(n):
            edge = world_verts[(i + 1) % n] - world_verts[i]
            normals.append(edge.perp().normalized())
        return normals

    def apply_impulse(self, impulse: Vec2, contact_r: Vec2) -> None:
        if self.static:
            return
        self.vel = self.vel + impulse * self.inv_mass
        self.angular_vel += self.inv_inertia * contact_r.cross(impulse)


def _make_circle_body(shape: FlowchartShape, density: float) -> Body:
    x1, y1, x2, y2 = shape.bounds()
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    radius = max(4.0, (shape.width + shape.height) / 4.0)
    mass = density * math.pi * radius * radius
    inertia = 0.5 * mass * radius * radius
    return Body(
        kind="circle",
        pos=Vec2(cx, cy),
        radius=radius,
        inv_mass=1.0 / mass,
        inv_inertia=1.0 / inertia,
        restitution=0.5,
        shape=shape,
        base_rotation_deg=getattr(shape, "rotation", 0.0),
        width=shape.width,
        height=shape.height,
        writeback="flowchart",
    )


def _local_verts_from_world(world_points: list[tuple[float, float]], center: Vec2) -> list[Vec2]:
    """世界轮廓 → 相对中心、外法线朝外的局部凸多边形顶点。"""
    hull = convex_hull(world_points)
    if len(hull) < 3:
        return []
    verts = [Vec2(px - center.x, py - center.y) for px, py in hull]
    # 保证缠绕方向使 edge.perp() 朝外（远离质心）。
    _area, cx, cy = _polygon_area_centroid(verts)
    centroid = Vec2(cx, cy)
    edge = verts[1] - verts[0]
    mid = (verts[0] + verts[1]) * 0.5
    if edge.perp().normalized().dot(mid - centroid) < 0:
        verts.reverse()
    return verts


def _make_polygon_body(
    shape: object,
    world_points: list[tuple[float, float]],
    *,
    static: bool,
    density: float,
    writeback: str | None,
    lock_rotation: bool = False,
) -> Body | None:
    xs = [p[0] for p in world_points]
    ys = [p[1] for p in world_points]
    if not xs or not ys:
        return None
    center = Vec2((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    verts = _local_verts_from_world(world_points, center)
    if len(verts) < 3:
        return None

    body = Body(
        kind="polygon",
        pos=center,
        verts=verts,
        static=static,
        shape=shape,
        base_rotation_deg=getattr(shape, "rotation", 0.0),
        width=max(xs) - min(xs),
        height=max(ys) - min(ys),
        writeback=writeback,
        lock_rotation=lock_rotation,
    )
    if static:
        body.inv_mass = 0.0
        body.inv_inertia = 0.0
        body.restitution = 0.3
        body.static_friction = 0.7
        body.dynamic_friction = 0.6
        return body

    area, cx, cy = _polygon_area_centroid(verts)
    area = abs(area)
    if area < EPSILON:
        return None
    mass = density * area
    # 关于参考点（包围盒中心）的二阶矩。
    inertia_moment = 0.0
    n = len(verts)
    for i in range(n):
        a = verts[i]
        b = verts[(i + 1) % n]
        crs = abs(a.cross(b))
        inertia_moment += crs * (a.dot(a) + a.dot(b) + b.dot(b))
    inertia = density * inertia_moment / 12.0
    body.inv_mass = 1.0 / mass
    body.inv_inertia = 0.0 if (lock_rotation or inertia < EPSILON) else 1.0 / inertia
    return body


def _thin_segment_polygon(p1: tuple[float, float], p2: tuple[float, float], thickness: float) -> list[tuple[float, float]]:
    a = Vec2(*p1)
    b = Vec2(*p2)
    direction = (b - a).normalized()
    if direction.length() < EPSILON:
        direction = Vec2(1.0, 0.0)
    normal = direction.perp() * (thickness / 2.0)
    return [
        (a + normal).as_tuple(),
        (b + normal).as_tuple(),
        (b - normal).as_tuple(),
        (a - normal).as_tuple(),
    ]


# ── 碰撞流形 ────────────────────────────────────────────────────────────
@dataclass
class Manifold:
    a: Body
    b: Body
    normal: Vec2  # 由 a 指向 b
    penetration: float
    contacts: list[Vec2]


def _collide_circle_circle(a: Body, b: Body) -> Manifold | None:
    delta = b.pos - a.pos
    dist = delta.length()
    radius = a.radius + b.radius
    if dist >= radius:
        return None
    if dist < EPSILON:
        normal = Vec2(0.0, -1.0)
        penetration = radius
        contact = a.pos
    else:
        normal = delta * (1.0 / dist)
        penetration = radius - dist
        contact = a.pos + normal * a.radius
    return Manifold(a, b, normal, penetration, [contact])


def _collide_circle_polygon(circle: Body, poly: Body) -> Manifold | None:
    verts = poly.world_vertices()
    normals = poly.world_normals(verts)
    center = circle.pos
    n = len(verts)

    separation = -math.inf
    face = 0
    for i in range(n):
        s = normals[i].dot(center - verts[i])
        if s > circle.radius:
            return None
        if s > separation:
            separation = s
            face = i

    v1 = verts[face]
    v2 = verts[(face + 1) % n]

    if separation < EPSILON:
        # 圆心在多边形内部，沿该面法线推出。
        normal = -normals[face]
        return _orient(circle, poly, normal, circle.radius, [center + normals[face] * separation])

    # 判断圆心落在面的哪个 Voronoi 区域。
    if (center - v1).dot(v2 - v1) <= 0:
        d = (center - v1).length()
        if d > circle.radius:
            return None
        normal = (center - v1).normalized() if d > EPSILON else normals[face]
        return _orient(circle, poly, -normal, circle.radius - d, [v1])
    if (center - v2).dot(v1 - v2) <= 0:
        d = (center - v2).length()
        if d > circle.radius:
            return None
        normal = (center - v2).normalized() if d > EPSILON else normals[face]
        return _orient(circle, poly, -normal, circle.radius - d, [v2])
    # 最近的是面本身。
    normal = normals[face]
    penetration = circle.radius - separation
    contact = center - normal * circle.radius
    return _orient(circle, poly, -normal, penetration, [contact])


def _orient(a: Body, b: Body, normal: Vec2, penetration: float, contacts: list[Vec2]) -> Manifold:
    """统一让流形法线由 a 指向 b。"""
    if normal.dot(b.pos - a.pos) < 0:
        normal = -normal
    return Manifold(a, b, normal, penetration, contacts)


def _axis_least_penetration(a: Body, a_verts, a_normals, b_verts) -> tuple[float, int]:
    best = -math.inf
    index = 0
    for i in range(len(a_verts)):
        n = a_normals[i]
        support = min(b_verts, key=lambda v: n.dot(v))
        s = n.dot(support - a_verts[i])
        if s > best:
            best = s
            index = i
    return best, index


def _clip(n: Vec2, c: float, face: list[Vec2]) -> list[Vec2]:
    out: list[Vec2] = []
    d1 = n.dot(face[0]) - c
    d2 = n.dot(face[1]) - c
    if d1 <= 0:
        out.append(face[0])
    if d2 <= 0:
        out.append(face[1])
    if d1 * d2 < 0:
        t = d1 / (d1 - d2)
        out.append(face[0] + (face[1] - face[0]) * t)
    return out[:2]


def _collide_polygon_polygon(a: Body, b: Body) -> Manifold | None:
    av = a.world_vertices()
    an = a.world_normals(av)
    bv = b.world_vertices()
    bn = b.world_normals(bv)

    pen_a, face_a = _axis_least_penetration(a, av, an, bv)
    if pen_a >= 0:
        return None
    pen_b, face_b = _axis_least_penetration(b, bv, bn, av)
    if pen_b >= 0:
        return None

    # 选参考面（偏好 a 以减少抖动）。
    if pen_a >= pen_b * 0.95 + pen_a * 0.01:
        ref_v, ref_n, inc_v, inc_n, ref_face = av, an, bv, bn, face_a
        flip = False
    else:
        ref_v, ref_n, inc_v, inc_n, ref_face = bv, bn, av, an, face_b
        flip = True

    ref_normal = ref_n[ref_face]
    # 入射面：法线与参考面法线最反向。
    inc_face = min(range(len(inc_n)), key=lambda i: ref_normal.dot(inc_n[i]))
    incident = [inc_v[inc_face], inc_v[(inc_face + 1) % len(inc_v)]]

    v1 = ref_v[ref_face]
    v2 = ref_v[(ref_face + 1) % len(ref_v)]
    side = (v2 - v1).normalized()

    incident = _clip(-side, -side.dot(v1), incident)
    if len(incident) < 2:
        return None
    incident = _clip(side, side.dot(v2), incident)
    if len(incident) < 2:
        return None

    ref_c = ref_normal.dot(v1)
    contacts: list[Vec2] = []
    total_pen = 0.0
    for p in incident:
        sep = ref_normal.dot(p) - ref_c
        if sep <= 0:
            contacts.append(p)
            total_pen += -sep
    if not contacts:
        return None

    penetration = total_pen / len(contacts)
    normal = -ref_normal if flip else ref_normal
    return _orient(a, b, normal, penetration, contacts)


def collide(a: Body, b: Body) -> Manifold | None:
    if a.static and b.static:
        return None
    if a.kind == "circle" and b.kind == "circle":
        return _collide_circle_circle(a, b)
    if a.kind == "circle" and b.kind == "polygon":
        return _collide_circle_polygon(a, b)
    if a.kind == "polygon" and b.kind == "circle":
        m = _collide_circle_polygon(b, a)
        if m is not None:
            m.a, m.b = a, b
            m.normal = -m.normal
        return m
    return _collide_polygon_polygon(a, b)


# ── 物理世界 ────────────────────────────────────────────────────────────
class PhysicsWorld:
    def __init__(self, gravity: float = 1600.0, iterations: int = 10) -> None:
        self.bodies: list[Body] = []
        self.gravity = Vec2(0.0, gravity)
        self.iterations = iterations
        self.correction_percent = 0.4
        self.slop = 0.5
        self.linear_damping = 0.999
        self.angular_damping = 0.99

    def add(self, body: Body) -> Body:
        self.bodies.append(body)
        return body

    @property
    def dynamic_bodies(self) -> list[Body]:
        return [b for b in self.bodies if not b.static]

    def step(self, dt: float) -> None:
        # 1. 施加重力（按加速度，质量无关）。
        for body in self.bodies:
            if not body.static:
                body.vel = body.vel + self.gravity * dt

        # 2. 生成碰撞流形。
        manifolds: list[Manifold] = []
        n = len(self.bodies)
        for i in range(n):
            for j in range(i + 1, n):
                m = collide(self.bodies[i], self.bodies[j])
                if m is not None and m.contacts:
                    manifolds.append(m)

        # 3. 迭代求解速度约束。
        for _ in range(self.iterations):
            for m in manifolds:
                self._resolve(m, dt)

        # 4. 积分位置。
        for body in self.bodies:
            if body.static:
                continue
            body.pos = body.pos + body.vel * dt
            body.angle += body.angular_vel * dt
            body.vel = body.vel * self.linear_damping
            body.angular_vel *= self.angular_damping

        # 5. 位置修正，消除穿透。
        for m in manifolds:
            self._correct_position(m)

    def _resolve(self, m: Manifold, dt: float) -> None:
        a, b, n = m.a, m.b, m.normal
        inv_mass_sum = a.inv_mass + b.inv_mass
        if inv_mass_sum < EPSILON:
            return
        rest_threshold = self.gravity.length() * dt + 1.0

        for contact in m.contacts:
            ra = contact - a.pos
            rb = contact - b.pos
            rv = (b.vel + _cross_sv(b.angular_vel, rb)) - (a.vel + _cross_sv(a.angular_vel, ra))
            vel_along_normal = rv.dot(n)
            if vel_along_normal > 0:
                continue

            ra_cross_n = ra.cross(n)
            rb_cross_n = rb.cross(n)
            denom = inv_mass_sum + ra_cross_n * ra_cross_n * a.inv_inertia + rb_cross_n * rb_cross_n * b.inv_inertia
            if denom < EPSILON:
                continue

            restitution = min(a.restitution, b.restitution)
            if -vel_along_normal < rest_threshold:
                restitution = 0.0

            j = -(1.0 + restitution) * vel_along_normal / denom
            j /= len(m.contacts)
            impulse = n * j
            a.apply_impulse(-impulse, ra)
            b.apply_impulse(impulse, rb)

            # 库仑摩擦。
            rv = (b.vel + _cross_sv(b.angular_vel, rb)) - (a.vel + _cross_sv(a.angular_vel, ra))
            tangent = rv - n * rv.dot(n)
            if tangent.length() < EPSILON:
                continue
            tangent = tangent.normalized()
            ra_cross_t = ra.cross(tangent)
            rb_cross_t = rb.cross(tangent)
            denom_t = inv_mass_sum + ra_cross_t * ra_cross_t * a.inv_inertia + rb_cross_t * rb_cross_t * b.inv_inertia
            if denom_t < EPSILON:
                continue
            jt = -rv.dot(tangent) / denom_t
            jt /= len(m.contacts)
            mu = math.sqrt(a.static_friction * b.static_friction)
            if abs(jt) < j * mu:
                friction = tangent * jt
            else:
                dyn_mu = math.sqrt(a.dynamic_friction * b.dynamic_friction)
                friction = tangent * (-j * dyn_mu)
            a.apply_impulse(-friction, ra)
            b.apply_impulse(friction, rb)

    def _correct_position(self, m: Manifold) -> None:
        a, b = m.a, m.b
        inv_mass_sum = a.inv_mass + b.inv_mass
        if inv_mass_sum < EPSILON:
            return
        magnitude = max(m.penetration - self.slop, 0.0) / inv_mass_sum * self.correction_percent
        correction = m.normal * magnitude
        if not a.static:
            a.pos = a.pos - correction * a.inv_mass
        if not b.static:
            b.pos = b.pos + correction * b.inv_mass


# ── 从文档构建世界 / 写回文档 ───────────────────────────────────────────
def build_world(
    document,
    container: tuple[float, float, float, float],
    *,
    gravity: float = 1600.0,
    density: float = 1.0,
) -> PhysicsWorld:
    """根据当前文档与可视区域矩形构建物理世界。

    container = (left, top, right, bottom)，世界坐标。四周生成静止墙体，
    重力向下（+y），所有矢量图元成为刚体。
    """
    world = PhysicsWorld(gravity=gravity)

    for shape in document.shapes:
        body = _body_for_shape(shape, density)
        if body is not None:
            world.add(body)

    _add_container_walls(world, container)
    return world


def _body_for_shape(shape: object, density: float) -> Body | None:
    if isinstance(shape, FlowchartShape):
        if shape.kind in CIRCLE_KINDS:
            return _make_circle_body(shape, density)
        return _make_polygon_body(
            shape, shape.outline_points(), static=False, density=density, writeback="flowchart"
        )
    if isinstance(shape, TextShape):
        x1, y1, x2, y2 = shape.bounds()
        rect = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        return _make_polygon_body(
            shape, rect, static=False, density=density, writeback="text", lock_rotation=True
        )
    if isinstance(shape, LineShape):
        poly = _thin_segment_polygon((shape.x1, shape.y1), (shape.x2, shape.y2), thickness=8.0)
        return _make_polygon_body(shape, poly, static=True, density=density, writeback=None)
    if isinstance(shape, CurveShape):
        if len(shape.points) < 2:
            return None
        return _make_polygon_body(shape, shape.points, static=True, density=density, writeback=None)
    return None


def _add_container_walls(world: PhysicsWorld, container: tuple[float, float, float, float]) -> None:
    left, top, right, bottom = container
    thickness = max(400.0, (right - left), (bottom - top))
    walls = [
        # floor
        [(left - thickness, bottom), (right + thickness, bottom),
         (right + thickness, bottom + thickness), (left - thickness, bottom + thickness)],
        # ceiling
        [(left - thickness, top - thickness), (right + thickness, top - thickness),
         (right + thickness, top), (left - thickness, top)],
        # left
        [(left - thickness, top - thickness), (left, top - thickness),
         (left, bottom + thickness), (left - thickness, bottom + thickness)],
        # right
        [(right, top - thickness), (right + thickness, top - thickness),
         (right + thickness, bottom + thickness), (right, bottom + thickness)],
    ]
    for rect in walls:
        body = _make_polygon_body(None, rect, static=True, density=1.0, writeback=None)
        if body is not None:
            world.add(body)


def sync_to_document(world: PhysicsWorld) -> None:
    """把刚体当前位姿写回对应的图元，供渲染器绘制。"""
    for body in world.bodies:
        if body.writeback is None or body.shape is None:
            continue
        shape = body.shape
        if body.writeback == "flowchart":
            shape.x = body.pos.x - body.width / 2.0
            shape.y = body.pos.y - body.height / 2.0
            shape.rotation = (body.base_rotation_deg + math.degrees(body.angle)) % 360
        elif body.writeback == "text":
            shape.x = body.pos.x - body.width / 2.0
            shape.y = body.pos.y - body.height / 2.0
