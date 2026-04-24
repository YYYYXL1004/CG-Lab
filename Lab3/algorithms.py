"""
Cohen-Sutherland 直线段裁剪算法

核心思想：
    将二维平面按裁剪窗口的四条边延伸，划分为 9 个区域，
    每个区域用 4 位编码（上、下、右、左）表示。
    对直线段两端点分别编码后：
    - 两端编码均为 0000           → 完全可见，直接接受（简取）
    - 两端编码按位与 ≠ 0         → 完全不可见，直接拒绝（简弃）
    - 否则                        → 需要逐步裁剪，求与窗口边的交点替换端点

区域编码示意图（屏幕坐标系，y 向下为正）：

        左上 1001 | 正上 1000 | 右上 1010
        ---------+-----------+---------
        正左 0001 | 内部 0000 | 正右 0010
        ---------+-----------+---------
        左下 0101 | 正下 0100 | 右下 0110

算法步骤：
    1. 计算两端点的区域编码 code0、code1
    2. code0 == 0 且 code1 == 0        → 简取，返回
    3. (code0 & code1) != 0            → 简弃，返回
    4. 选取一个在窗口外的端点，根据其编码求与对应窗口边的交点，
       用交点替换该端点，重新编码
    5. 回到步骤 2，循环直到简取或简弃
"""

# 区域编码常量
INSIDE = 0   # 0000
LEFT   = 1   # 0001
RIGHT  = 2   # 0010
BOTTOM = 4   # 0100  (屏幕坐标 y > ymax)
TOP    = 8   # 1000  (屏幕坐标 y < ymin)


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


def compute_code(x, y, xmin, ymin, xmax, ymax):
    """
    计算点 (x, y) 相对于裁剪窗口 [xmin, xmax] × [ymin, ymax] 的区域编码。
    屏幕坐标系中 y 向下为正，因此 y < ymin 为"上"，y > ymax 为"下"。
    """
    code = INSIDE
    if x < xmin:
        code |= LEFT
    elif x > xmax:
        code |= RIGHT
    if y < ymin:
        code |= TOP
    elif y > ymax:
        code |= BOTTOM
    return code


def _code_label(code):
    """将区域编码转为可读标签"""
    if code == INSIDE:
        return "内部"
    parts = []
    if code & TOP:    parts.append("上")
    if code & BOTTOM: parts.append("下")
    if code & LEFT:   parts.append("左")
    if code & RIGHT:  parts.append("右")
    return "".join(parts)


def cohen_sutherland_clip(x0, y0, x1, y1, xmin, ymin, xmax, ymax, print_log=False):
    """
    Cohen-Sutherland 直线段裁剪算法

    参数:
        x0, y0, x1, y1          — 直线段端点
        xmin, ymin, xmax, ymax  — 裁剪窗口边界
        print_log               — 是否打印裁剪过程

    返回:
        (accept, cx0, cy0, cx1, cy1)
        accept  — 是否有可见部分
        cx0~cy1 — 裁剪后的端点坐标（浮点数）
    """
    code0 = compute_code(x0, y0, xmin, ymin, xmax, ymax)
    code1 = compute_code(x1, y1, xmin, ymin, xmax, ymax)

    if print_log:
        print(f"\n[Cohen-Sutherland 裁剪]")
        print(f"  直线段: ({x0}, {y0}) → ({x1}, {y1})")
        print(f"  裁剪窗口: x∈[{xmin}, {xmax}], y∈[{ymin}, {ymax}]")
        print(f"| {'步骤':^4} | {'P0 编码':^12} | {'P1 编码':^12} | {'操作':^34} |")
        print("-" * 74)

    step = 0

    while True:
        if code0 == 0 and code1 == 0:
            # 简取：两端点都在窗口内
            if print_log:
                print(f"| {step:^4} | {code0:04b} {'内部':>6} | {code1:04b} {'内部':>6} | {'简取: 完全可见':^34} |")
                print(f"  裁剪结果: ({x0:.1f}, {y0:.1f}) → ({x1:.1f}, {y1:.1f})")
            return True, x0, y0, x1, y1

        if (code0 & code1) != 0:
            # 简弃：两端点在窗口同一侧外
            if print_log:
                c0l = _code_label(code0)
                c1l = _code_label(code1)
                print(f"| {step:^4} | {code0:04b} {c0l:>6} | {code1:04b} {c1l:>6} | {'简弃: 完全不可见':^34} |")
            return False, x0, y0, x1, y1

        # 选择在窗口外的端点进行裁剪
        code_out = code0 if code0 != 0 else code1
        dx = x1 - x0
        dy = y1 - y0

        if code_out & TOP:
            x = x0 + dx * (ymin - y0) / dy
            y = ymin
            edge = "上边(TOP)"
        elif code_out & BOTTOM:
            x = x0 + dx * (ymax - y0) / dy
            y = ymax
            edge = "下边(BOTTOM)"
        elif code_out & RIGHT:
            y = y0 + dy * (xmax - x0) / dx
            x = xmax
            edge = "右边(RIGHT)"
        else:  # LEFT
            y = y0 + dy * (xmin - x0) / dx
            x = xmin
            edge = "左边(LEFT)"

        which = "P0" if code_out == code0 else "P1"

        if print_log:
            c0l = _code_label(code0)
            c1l = _code_label(code1)
            action = f"{which}与{edge}交于({x:.1f},{y:.1f})"
            print(f"| {step:^4} | {code0:04b} {c0l:>6} | {code1:04b} {c1l:>6} | {action:<34} |")

        if code_out == code0:
            x0, y0 = x, y
            code0 = compute_code(x0, y0, xmin, ymin, xmax, ymax)
        else:
            x1, y1 = x, y
            code1 = compute_code(x1, y1, xmin, ymin, xmax, ymax)

        step += 1
