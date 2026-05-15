"""
Lab5 三维形体、观察变换、消隐与光照算法。

本文件只提供计算和光栅化算法，窗口事件和 pygame 像素输出放在 main.py。
直线、三角形填充、深度缓存都在这里手写完成，不使用 pygame 的画线/画面函数。
"""

from dataclasses import dataclass
import math


NEAR_PLANE = 0.1


@dataclass
class Camera:
    position: tuple
    yaw: float
    pitch: float


def clamp(value, low=0, high=255):
    return max(low, min(high, int(round(value))))


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(v):
    return math.sqrt(dot(v, v))


def normalize(v):
    l = length(v)
    if l < 1e-8:
        return (0.0, 1.0, 0.0)
    return (v[0] / l, v[1] / l, v[2] / l)


def midpoint_line(x0, y0, x1, y1):
    """Bresenham/中点思想直线离散化，返回屏幕像素坐标列表。"""
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0

    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy

    return points


def camera_basis(camera):
    cp = math.cos(camera.pitch)
    forward = normalize((
        math.sin(camera.yaw) * cp,
        math.sin(camera.pitch),
        math.cos(camera.yaw) * cp,
    ))
    right = normalize((math.cos(camera.yaw), 0.0, -math.sin(camera.yaw)))
    up = normalize(cross(forward, right))
    return right, up, forward


def world_to_camera(point, camera):
    right, up, forward = camera_basis(camera)
    rel = sub(point, camera.position)
    return (dot(rel, right), dot(rel, up), dot(rel, forward))


def project_point(point, camera, width, height, focal):
    x, y, z = world_to_camera(point, camera)
    if z <= NEAR_PLANE:
        return None
    sx = width * 0.5 + focal * x / z
    sy = height * 0.5 - focal * y / z
    return (sx, sy, z)


def rotate_y(point, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    x, y, z = point
    return (x * c + z * s, y, -x * s + z * c)


def rotate_x(point, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    x, y, z = point
    return (x, y * c - z * s, y * s + z * c)


def transformed_vertices(vertices, angle_y=0.0, offset=(0.0, 0.0, 0.0),
                         angle_x=0.0):
    result = []
    for point in vertices:
        rotated = rotate_x(rotate_y(point, angle_y), angle_x)
        result.append(add(rotated, offset))
    return result


def _quad(a, b, c, d, color):
    return [
        {"indices": (a, b, c), "color": color},
        {"indices": (a, c, d), "color": color},
    ]


def build_house_model():
    """自定义三维形体：带屋顶和烟囱的小建筑。"""
    vertices = [
        (-1.6, -1.0, -1.1), (1.6, -1.0, -1.1),
        (1.6, 1.0, -1.1), (-1.6, 1.0, -1.1),
        (-1.6, -1.0, 1.1), (1.6, -1.0, 1.1),
        (1.6, 1.0, 1.1), (-1.6, 1.0, 1.1),
        (-1.8, 1.0, -1.25), (1.8, 1.0, -1.25),
        (0.0, 1.8, -1.25), (-1.8, 1.0, 1.25),
        (1.8, 1.0, 1.25), (0.0, 1.8, 1.25),
        (0.65, 1.1, 0.35), (1.0, 1.1, 0.35),
        (1.0, 2.0, 0.35), (0.65, 2.0, 0.35),
        (0.65, 1.1, 0.7), (1.0, 1.1, 0.7),
        (1.0, 2.0, 0.7), (0.65, 2.0, 0.7),
    ]

    wall = (170, 190, 210)
    side = (145, 165, 185)
    roof = (170, 70, 60)
    chimney = (130, 90, 75)
    floor = (110, 120, 130)

    tris = []
    tris += _quad(0, 1, 2, 3, wall)
    tris += _quad(5, 4, 7, 6, wall)
    tris += _quad(4, 0, 3, 7, side)
    tris += _quad(1, 5, 6, 2, side)
    tris += _quad(4, 5, 1, 0, floor)
    tris += _quad(3, 2, 6, 7, (155, 175, 195))
    tris += _quad(8, 9, 12, 11, roof)
    tris += _quad(8, 11, 13, 10, roof)
    tris += _quad(9, 10, 13, 12, roof)
    tris.append({"indices": (8, 10, 9), "color": roof})
    tris.append({"indices": (11, 12, 13), "color": roof})
    tris += _quad(14, 15, 16, 17, chimney)
    tris += _quad(19, 18, 21, 20, chimney)
    tris += _quad(18, 14, 17, 21, chimney)
    tris += _quad(15, 19, 20, 16, chimney)
    tris += _quad(17, 16, 20, 21, (150, 105, 85))
    return vertices, tris


def model_center(vertices):
    n = len(vertices)
    return (
        sum(p[0] for p in vertices) / n,
        sum(p[1] for p in vertices) / n,
        sum(p[2] for p in vertices) / n,
    )


def triangle_normal(vertices, tri, center_hint=None):
    i0, i1, i2 = tri["indices"]
    a, b, c = vertices[i0], vertices[i1], vertices[i2]
    n = normalize(cross(sub(b, a), sub(c, a)))
    center = mul(add(add(a, b), c), 1.0 / 3.0)
    hint = center_hint if center_hint is not None else (0.0, 0.0, 0.0)
    if dot(n, sub(center, hint)) < 0:
        n = mul(n, -1.0)
    return n


def vertex_normals(vertices, triangles):
    center_hint = model_center(vertices)
    normals = [(0.0, 0.0, 0.0) for _ in vertices]
    for tri in triangles:
        n = triangle_normal(vertices, tri, center_hint)
        for idx in tri["indices"]:
            normals[idx] = add(normals[idx], n)
    return [normalize(n) for n in normals]


def phong_color(base_color, normal, point, camera_pos,
                light_pos=(3.0, 5.0, -2.0)):
    n = normalize(normal)
    l = normalize(sub(light_pos, point))
    v = normalize(sub(camera_pos, point))
    diff = max(0.0, dot(n, l))
    reflect = normalize(sub(mul(n, 2.0 * dot(n, l)), l))
    spec = max(0.0, dot(reflect, v)) ** 28

    result = []
    for channel in base_color:
        ambient = 0.22 * channel
        diffuse = 0.62 * diff * channel
        specular = 85.0 * spec
        result.append(clamp(ambient + diffuse + specular))
    return tuple(result)


def edge_function(a, b, p):
    return ((p[0] - a[0]) * (b[1] - a[1]) -
            (p[1] - a[1]) * (b[0] - a[0]))


def render_triangles(triangles, width, height):
    pixels = {}
    z_buffer = [float("inf")] * (width * height)

    for tri in triangles:
        rasterize_triangle_into(tri, width, height, z_buffer, pixels)

    return pixels


def _rasterize_depth_line(a, b, color, pixels, z_buffer, width, height):
    x0, y0 = int(round(a[0])), int(round(a[1]))
    x1, y1 = int(round(b[0])), int(round(b[1]))
    line = midpoint_line(x0, y0, x1, y1)
    count = max(1, len(line) - 1)
    for i, (x, y) in enumerate(line):
        if x < 0 or x >= width or y < 0 or y >= height:
            continue
        t = i / count
        z = a[2] * (1.0 - t) + b[2] * t
        if z <= z_buffer[y * width + x] + 0.03:
            pixels[(x, y)] = color


def render_model(vertices, triangles, camera, width, height, focal):
    normals = vertex_normals(vertices, triangles)
    projected = [project_point(p, camera, width, height, focal)
                 for p in vertices]
    shaded = [phong_color((190, 190, 190), normals[i], p, camera.position)
              for i, p in enumerate(vertices)]

    render_tris = []
    center_hint = model_center(vertices)
    for tri in triangles:
        idx = tri["indices"]
        if any(projected[i] is None for i in idx):
            continue
        tri_center = mul(add(add(vertices[idx[0]], vertices[idx[1]]),
                             vertices[idx[2]]), 1.0 / 3.0)
        face_normal = triangle_normal(vertices, tri, center_hint)
        if dot(face_normal, sub(camera.position, tri_center)) <= 0:
            continue
        tri_colors = [
            phong_color(tri["color"], normals[i], vertices[i], camera.position)
            for i in idx
        ]
        render_tris.append({
            "points": [projected[i] for i in idx],
            "colors": tri_colors,
        })

    pixels = {}
    z_buffer = [float("inf")] * (width * height)
    for tri in render_tris:
        rasterize_triangle_into(tri, width, height, z_buffer, pixels)

    drawn_edges = set()
    for tri in triangles:
        ids = tri["indices"]
        for a, b in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0])):
            edge = tuple(sorted((a, b)))
            if edge in drawn_edges:
                continue
            drawn_edges.add(edge)
            if projected[a] is not None and projected[b] is not None:
                _rasterize_depth_line(projected[a], projected[b],
                                      (35, 45, 55), pixels, z_buffer,
                                      width, height)

    return pixels, len(render_tris), len(shaded)


def rasterize_triangle_into(tri, width, height, z_buffer, pixels):
    pts = tri["points"]
    colors = tri["colors"]
    min_x = max(0, int(math.floor(min(p[0] for p in pts))))
    max_x = min(width - 1, int(math.ceil(max(p[0] for p in pts))))
    min_y = max(0, int(math.floor(min(p[1] for p in pts))))
    max_y = min(height - 1, int(math.ceil(max(p[1] for p in pts))))
    area = edge_function(pts[0], pts[1], pts[2])
    if abs(area) < 1e-6:
        return

    inv_area = 1.0 / area
    positive = area > 0
    e0_dx = pts[2][1] - pts[1][1]
    e0_dy = -(pts[2][0] - pts[1][0])
    e1_dx = pts[0][1] - pts[2][1]
    e1_dy = -(pts[0][0] - pts[2][0])
    e2_dx = pts[1][1] - pts[0][1]
    e2_dy = -(pts[1][0] - pts[0][0])

    row_p = (min_x + 0.5, min_y + 0.5)
    row_e0 = edge_function(pts[1], pts[2], row_p)
    row_e1 = edge_function(pts[2], pts[0], row_p)
    row_e2 = edge_function(pts[0], pts[1], row_p)

    c0, c1, c2 = colors
    for y in range(min_y, max_y + 1):
        e0, e1, e2 = row_e0, row_e1, row_e2
        base = y * width
        for x in range(min_x, max_x + 1):
            inside = (e0 >= -1e-6 and e1 >= -1e-6 and e2 >= -1e-6)
            if not positive:
                inside = (e0 <= 1e-6 and e1 <= 1e-6 and e2 <= 1e-6)
            if inside:
                w0 = e0 * inv_area
                w1 = e1 * inv_area
                w2 = e2 * inv_area
                z = w0 * pts[0][2] + w1 * pts[1][2] + w2 * pts[2][2]
                idx = base + x
                if z < z_buffer[idx]:
                    z_buffer[idx] = z
                    pixels[(x, y)] = (
                        int(w0 * c0[0] + w1 * c1[0] + w2 * c2[0]),
                        int(w0 * c0[1] + w1 * c1[1] + w2 * c2[1]),
                        int(w0 * c0[2] + w1 * c1[2] + w2 * c2[2]),
                    )
            e0 += e0_dx
            e1 += e1_dx
            e2 += e2_dx
        row_e0 += e0_dy
        row_e1 += e1_dy
        row_e2 += e2_dy


def rasterize_triangle_with_depth(tri, width, height, z_buffer):
    pixels = {}
    rasterize_triangle_into(tri, width, height, z_buffer, pixels)
    return pixels, z_buffer
