"""
计算机图形学 Lab2 — 扫描线种子填充算法

核心思想：
    给定一个多边形和其内部的一个种子点，用"扫描线"的方式逐行填满整个多边形。

    与简单的递归洪水填充（Flood Fill）不同，扫描线种子填充不是一个像素一个像素地递归，
    而是每次处理一整行（扫描线），大幅减少栈深度和重复访问。

算法步骤：
    1. 从种子点出发，沿当前扫描线向左、向右扩展，找到这一行能填的最大区间 [left, right]
    2. 把 [left, right] 整段填上色
    3. 检查上下相邻两行：在 [left, right] 范围内，找到所有"连续可填"的小段，
       每段取一个点作为新种子压入栈
    4. 从栈中弹出下一个种子，重复步骤 1-3，直到栈空
"""


# ============================================================
#  辅助函数
# ============================================================

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


def build_polygon_edges(vertices, print_log=False):
    """把多边形顶点列表转成边界像素点列表（首尾自动闭合）"""
    if len(vertices) < 2:
        return []

    edge_points = []
    n = len(vertices)

    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        line = midpoint_line(x0, y0, x1, y1)
        # 去掉每条边的终点，避免与下一条边的起点重复
        if i < n - 1 and len(line) > 1:
            line = line[:-1]
        edge_points.extend(line)

    # 去重但保留顺序
    seen = set()
    unique = []
    for p in edge_points:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    if print_log:
        print(f"\n[多边形边界] 顶点数:{n}, 边界像素数:{len(unique)}")

    return unique


def point_in_polygon(px, py, vertices):
    """
    射线法判断点 (px, py) 是否在多边形内部。
    从该点向右发射一条水平射线，数它穿过多少条边：
      奇数次 → 在内部
      偶数次 → 在外部
    """
    inside = False
    n = len(vertices)

    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]

        # 跳过水平边（不会与水平射线产生有意义的交点）
        if y1 == y2:
            continue

        # 检查射线的 y 坐标是否穿过这条边的 y 范围
        if (y1 > py) != (y2 > py):
            # 计算射线与边的交点的 x 坐标
            x_cross = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if x_cross > px:
                inside = not inside

    return inside


# ============================================================
#  扫描线种子填充
# ============================================================

def scanline_seed_fill(vertices, seed, print_log=False):
    """
    扫描线种子填充算法（非递归，基于栈）

    参数:
        vertices  — 多边形顶点列表
        seed      — 种子点坐标 (x, y)，必须在多边形内部
    返回:
        fill_order — 按填充顺序排列的像素点列表（用于动画回放）
    """
    if len(vertices) < 3:
        return []

    # --- 准备工作 ---
    boundary = set(build_polygon_edges(vertices))  # 边界像素集合（用于快速查询）
    filled = set()       # 已填充的像素
    fill_order = []      # 填充顺序记录（用于动画）
    stack = [seed]       # 种子栈

    # 包围盒，用于快速排除明显在外面的点
    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)

    def can_fill(x, y):
        """判断像素 (x, y) 是否可以被填充"""
        if x < min_x or x > max_x or y < min_y or y > max_y:
            return False
        if (x, y) in boundary or (x, y) in filled:
            return False
        # 用像素中心 (x+0.5, y+0.5) 做内部判断，比整数坐标更准确
        return point_in_polygon(x + 0.5, y + 0.5, vertices)

    # 验证种子点
    sx, sy = seed
    if (sx, sy) in boundary or not point_in_polygon(sx + 0.5, sy + 0.5, vertices):
        if print_log:
            print("[扫描线种子填充] 种子点无效，取消填充。")
        return []

    if print_log:
        print(f"\n[扫描线种子填充] 种子点:({sx},{sy})")
        print(f"| {'步骤':^4} | {'扫描线 y':^8} | {'填充区间':^14} | {'新种子数':^8} | {'累计填充':^8} |")
        print("-" * 54)

    step = 0

    # --- 主循环 ---
    while stack:
        x, y = stack.pop()

        if not can_fill(x, y):
            continue

        # 第1步：向左扩展，找到这一行最左边能填的位置
        left = x
        while can_fill(left - 1, y):
            left -= 1

        # 第2步：向右扩展，找到这一行最右边能填的位置
        right = x
        while can_fill(right + 1, y):
            right += 1

        # 第3步：填充整段 [left, right]
        for fx in range(left, right + 1):
            if (fx, y) not in filled:
                filled.add((fx, y))
                fill_order.append((fx, y))

        # 第4步：检查上下两行，为每段连续可填区域压入一个新种子
        new_seeds = 0
        for neighbor_y in (y - 1, y + 1):
            in_run = False  # 是否正处于一段连续可填区域中
            for fx in range(left, right + 1):
                if can_fill(fx, neighbor_y):
                    if not in_run:
                        # 进入新的一段，取第一个点作为种子
                        stack.append((fx, neighbor_y))
                        new_seeds += 1
                        in_run = True
                else:
                    in_run = False  # 这段结束了

        if print_log:
            print(f"| {step:^4} | {y:^8} | [{left:>3}, {right:>3}]      | {new_seeds:^8} | {len(fill_order):^8} |")

        step += 1

    if print_log:
        print(f"\n填充完成，共 {len(fill_order)} 个像素。")

    return fill_order
