"""
Bezier 曲线绘制与变换算法

核心算法 — De Casteljau 递推法：
    给定 n+1 个控制顶点 P0, P1, ..., Pn 和参数 t ∈ [0, 1]，
    通过逐层线性插值递推计算 Bezier 曲线上的点。

    递推公式：
        P_i^(0) = P_i                                     （第 0 层 = 原始控制顶点）
        P_i^(r) = (1-t)·P_i^(r-1) + t·P_{i+1}^(r-1)      （r = 1..n, i = 0..n-r）

    最终 P_0^(n) 即为 n 阶 Bezier 曲线在参数 t 处的点。

    优点：
    - 数值稳定，不需要计算高阶组合数或阶乘
    - 天然支持任意阶数
    - 几何直观：每一层都是对前一层相邻点的线性插值
"""

import math


def midpoint_line(x0, y0, x1, y1):
    """中点画线法 — 将两点之间的直线离散为像素点列表"""
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    step_x = 1 if x0 < x1 else -1
    step_y = 1 if y0 < y1 else -1

    steep = dy > dx
    if steep:
        dx, dy = dy, dx

    d = 2 * dy - dx
    x, y = x0, y0

    for _ in range(dx + 1):
        points.append((x, y))
        if d < 0:
            d += 2 * dy
        else:
            d += 2 * (dy - dx)
            if steep:
                x += step_x
            else:
                y += step_y
        if steep:
            y += step_y
        else:
            x += step_x

    return points


def de_casteljau(control_points, t, print_log=False):
    """
    De Casteljau 递推算法

    参数:
        control_points — 控制顶点列表 [(x0,y0), (x1,y1), ...]
        t              — 参数值 ∈ [0, 1]
        print_log      — 是否打印递推过程
    返回:
        (x, y) — Bezier 曲线在参数 t 处的点（浮点坐标）
    """
    n = len(control_points)
    if n == 0:
        return (0, 0)
    if n == 1:
        return (control_points[0][0], control_points[0][1])

    # 创建工作副本（就地递推）
    pts = [[p[0], p[1]] for p in control_points]

    if print_log:
        print(f"\n[De Casteljau] t={t:.4f}, {n} 个控制点, {n - 1} 阶曲线")
        labels = "  ".join(f"P{i}({p[0]:.1f},{p[1]:.1f})" for i, p in enumerate(pts))
        print(f"  r=0: {labels}")

    for r in range(1, n):
        for i in range(n - r):
            pts[i][0] = (1 - t) * pts[i][0] + t * pts[i + 1][0]
            pts[i][1] = (1 - t) * pts[i][1] + t * pts[i + 1][1]

        if print_log:
            labels = "  ".join(
                f"P{i}^{r}({pts[i][0]:.1f},{pts[i][1]:.1f})"
                for i in range(n - r)
            )
            print(f"  r={r}: {labels}")

    return (pts[0][0], pts[0][1])


def bezier_curve(control_points, num_steps=300):
    """
    生成 Bezier 曲线的采样点列表

    参数:
        control_points — 控制顶点列表
        num_steps      — 采样步数（越大越平滑）
    返回:
        采样点列表（浮点坐标）
    """
    if len(control_points) < 2:
        return list(control_points)

    curve = []
    for i in range(num_steps + 1):
        t = i / num_steps
        curve.append(de_casteljau(control_points, t))
    return curve


def bezier_curve_pixels(control_points, num_steps=300):
    """
    生成 Bezier 曲线的像素点列表（四舍五入到整数坐标，自动去重）
    """
    curve = bezier_curve(control_points, num_steps)
    pixels = []
    seen = set()
    for x, y in curve:
        px, py = round(x), round(y)
        if (px, py) not in seen:
            seen.add((px, py))
            pixels.append((px, py))
    return pixels


def translate_points(points, dx, dy, print_log=False):
    """
    平移变换：将所有点沿 (dx, dy) 方向平移

    参数:
        points — 点列表 [(x, y), ...]
        dx, dy — 平移量
    返回:
        平移后的新列表
    """
    result = [(p[0] + dx, p[1] + dy) for p in points]

    if print_log:
        print(f"\n[平移变换] Δx={dx}, Δy={dy}")
        for i, (old, new) in enumerate(zip(points, result)):
            print(f"  P{i}: ({old[0]:.1f},{old[1]:.1f}) → ({new[0]:.1f},{new[1]:.1f})")

    return result


def rotate_points(points, angle_deg, cx, cy, print_log=False):
    """
    旋转变换：将所有点绕中心 (cx, cy) 旋转 angle_deg 度

    参数:
        points    — 点列表
        angle_deg — 旋转角度（正值为顺时针，屏幕坐标系）
        cx, cy    — 旋转中心
    返回:
        旋转后的新列表
    """
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    result = []
    for x, y in points:
        nx = cx + (x - cx) * cos_a - (y - cy) * sin_a
        ny = cy + (x - cx) * sin_a + (y - cy) * cos_a
        result.append((nx, ny))

    if print_log:
        print(f"\n[旋转变换] 角度={angle_deg}°, 中心=({cx:.1f},{cy:.1f})")
        for i, (old, new) in enumerate(zip(points, result)):
            print(f"  P{i}: ({old[0]:.1f},{old[1]:.1f}) → ({new[0]:.1f},{new[1]:.1f})")

    return result


def centroid(points):
    """计算点集的质心（几何中心），作为默认旋转参考点"""
    n = len(points)
    if n == 0:
        return (0, 0)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    return (cx, cy)
