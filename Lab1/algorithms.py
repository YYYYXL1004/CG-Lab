# 中点法绘制直线、圆、椭圆  核心思想（三个算法通用）：
#     每一步有两个候选像素，将它们的"中点"代入曲线的隐式方程 F(x,y)，
#     根据 F 的符号（正/负）判断中点在曲线的哪一侧，从而选择更近的那个像素。
#     为了避免浮点运算，对判别式做递推，只用整数加减。

# ============================================================
#  1. 中点画线法 (Midpoint Line Algorithm)
# ============================================================
#
#  直线隐式方程: F(x,y) = dy·x - dx·y + dx·b = 0
#  其中 dx = x1-x0, dy = y1-y0
#
#  以 |斜率| <= 1 且 x0 < x1 为例（第一象限右偏直线）：
#    每步 x+1，候选点为 (x+1, y) 和 (x+1, y+1)
#    中点 M = (x+1, y+0.5)
#    d = F(M) < 0  → 中点在直线下方 → 真实直线更靠上 → 选 (x+1, y+1)
#    d = F(M) >= 0 → 中点在直线上方 → 真实直线更靠下 → 选 (x+1, y)
#
#  为了处理所有方向的直线，代码用 step_x/step_y 做符号翻转，
#  并在 |斜率|>1 时交换 x/y 的主从角色。

def midpoint_line(x0, y0, x1, y1, print_log=False):
    points = []

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    step_x = 1 if x0 < x1 else -1   # 主轴步进方向, 向右画还是向左画
    step_y = 1 if y0 < y1 else -1   # 副轴步进方向，向下画还是向上画

    # steep: 斜率绝对值 > 1 时，交换 x/y 角色，永远让变化更快的那个轴每步走 1，保证相邻像素不断开
    steep = dy > dx
    if steep:
        dx, dy = dy, dx

    # 初始判别式 d = 2dy - dx （乘2消去0.5）
    d = 2 * dy - dx

    x, y = x0, y0

    if print_log:
        print(f"\n[中点画线法] ({x0},{y0}) -> ({x1},{y1})  |  steep={steep}")
        print(f"| {'步骤':^4} | {'坐标 (x,y)':^12} | {'判别式 d':^8} | {'策略':^20} |")
        print("-" * 56)

    for k in range(dx + 1):
        points.append((x, y))

        if print_log and k < dx:
            if d < 0:
                strategy = "d<0: 副轴不动"
            else:
                strategy = "d>=0: 副轴步进"
            print(f"| {k:^4} | ({x:>3},{y:>3})     | {d:^8} | {strategy:^20} |")

        if d < 0:  # 中点在直线下方，选 (x+1, y)，d 更新只加 2dy
            d += 2 * dy            # 副轴不动
        else:  # 中点在直线上方，选 (x+1, y+1)，d 更新加 2(dy-dx)
            d += 2 * (dy - dx)     # 副轴步进
            if steep:
                x += step_x
            else:
                y += step_y

        # 主轴始终步进
        if steep:
            y += step_y
        else:
            x += step_x

    if print_log:
        print(f"| {'END':^4} | ({points[-1][0]:>3},{points[-1][1]:>3})     | {'—':^8} | {'到达终点':^20} |")

    return points


# ============================================================
#  2. 中点画圆法 (Midpoint Circle Algorithm)
# ============================================================
#
#  圆的隐式方程: F(x,y) = x² + y² - R² = 0
#
#  只需计算第一象限 45° 弧段 (x: 0→R/√2, y: R→R/√2)，
#  然后利用八对称性映射出完整的圆。
#
#  每步 x+1，候选点为 (x+1, y) 和 (x+1, y-1)
#  中点 M = (x+1, y-0.5)
#  d = F(M) < 0  → 中点在圆内 → 选 (x+1, y)     → d 更新: d += 2x + 3
#  d = F(M) >= 0 → 中点在圆外 → 选 (x+1, y-1)   → d 更新: d += 2(x-y) + 5
#
#  初始: x=0, y=R, d = 1 - R （由 F(1, R-0.5) 化简得到）

def midpoint_circle(xc, yc, r, print_log=False):
    points = []
    if r <= 0:
        return points

    x, y = 0, r
    d = 1 - r  # 初始判别式（算出来其实是1.25-R, 但0.25不影响初始符号判断

    if print_log:
        print(f"\n[中点画圆法] 圆心:({xc},{yc}), 半径:{r}")
        print(f"| {'基础点 (x,y)':^12} | {'判别式 d':^8} | {'策略':^24} |")
        print("-" * 52)

    def add_eight(cx, cy, x, y):
        """八对称: 一个点映射出圆上的8个点"""
        points.extend([
            (cx+x, cy+y), (cx-x, cy+y),
            (cx+x, cy-y), (cx-x, cy-y),
            (cx+y, cy+x), (cx-y, cy+x),
            (cx+y, cy-x), (cx-y, cy-x),
        ])

    add_eight(xc, yc, x, y)

    while x < y:  # 只计算到45°，即 x<y 的区域
        if print_log:
            if d < 0:
                strategy = "d<0: 选 (x+1, y)"
            else:
                strategy = "d>=0: 选 (x+1, y-1)"
            print(f"| ({x:>3},{y:>3})     | {d:^8} | {strategy:^24} |")

        if d < 0:  # 中点在圆内，选 (x+1, y)，d 更新只加 2x+3
            d += 2 * x + 3
        else:  # 中点在圆外，选 (x+1, y-1)，d 更新加 2(x-y)+5
            d += 2 * (x - y) + 5
            y -= 1

        x += 1
        add_eight(xc, yc, x, y)

    # 去重但保留顺序（对称点会重复）
    seen = set()
    unique = []
    for p in points:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


# ============================================================
#  3. 中点画椭圆法 (Midpoint Ellipse Algorithm)
# ============================================================
#
#  椭圆隐式方程: F(x,y) = ry²·x² + rx²·y² - rx²·ry² = 0
#
#  椭圆没有八对称，只有四对称，且需要分两个区域：
#
#  区域1（上半弧，斜率|dy/dx| < 1）: x 为主步进轴
#    每步 x+1，候选 (x+1, y) 或 (x+1, y-1)
#    边界条件: ry²·x < rx²·y （切线斜率绝对值 < 1）
#
#  区域2（侧半弧，斜率|dy/dx| >= 1）: y 为主步进轴
#    每步 y-1，候选 (x, y-1) 或 (x+1, y-1)
#
#  初始判别式:
#    区域1: d1 = ry² - rx²·ry + rx²/4
#    区域2: d2 = ry²·(x+0.5)² + rx²·(y-1)² - rx²·ry²

def midpoint_ellipse(xc, yc, rx, ry, print_log=False):
    points = []
    if rx <= 0 or ry <= 0:
        return points

    rx2 = rx * rx
    ry2 = ry * ry

    x, y = 0, ry

    # --- 区域1: x 为主步进轴 ---
    d1 = ry2 - rx2 * ry + 0.25 * rx2

    if print_log:
        print(f"\n[中点画椭圆法] 圆心:({xc},{yc}), rx={rx}, ry={ry}")
        print(f"--- 区域1 (x 为主步进轴, ry²·x < rx²·y) ---")
        print(f"| {'基础点 (x,y)':^12} | {'判别式 d':^10} | {'策略':^26} |")
        print("-" * 58)

    def add_four(cx, cy, x, y):
        """四对称: 一个点映射出椭圆上的4个点"""
        points.extend([
            (cx+x, cy+y), (cx-x, cy+y),
            (cx+x, cy-y), (cx-x, cy-y),
        ])

    add_four(xc, yc, x, y)

    while ry2 * x < rx2 * y:
        if print_log:
            if d1 < 0:
                strategy = "d1<0: 选 (x+1, y)"
            else:
                strategy = "d1>=0: 选 (x+1, y-1)"
            print(f"| ({x:>3},{y:>3})     | {d1:^10.1f} | {strategy:^26} |")

        if d1 < 0:
            d1 += ry2 * (2 * x + 3)
        else:
            d1 += ry2 * (2 * x + 3) + rx2 * (-2 * y + 2)
            y -= 1

        x += 1
        add_four(xc, yc, x, y)

    # --- 区域2: y 为主步进轴 ---
    d2 = ry2 * (x + 0.5) ** 2 + rx2 * (y - 1) ** 2 - rx2 * ry2

    if print_log:
        print(f"\n--- 区域2 (y 为主步进轴, ry²·x >= rx²·y) ---")
        print(f"| {'基础点 (x,y)':^12} | {'判别式 d':^10} | {'策略':^26} |")
        print("-" * 58)

    while y >= 0:
        if print_log:
            if d2 > 0:
                strategy = "d2>0: 选 (x, y-1)"
            else:
                strategy = "d2<=0: 选 (x+1, y-1)"
            print(f"| ({x:>3},{y:>3})     | {d2:^10.1f} | {strategy:^26} |")

        if d2 > 0:
            d2 += rx2 * (-2 * y + 3)
        else:
            d2 += ry2 * (2 * x + 2) + rx2 * (-2 * y + 3)
            x += 1

        y -= 1
        add_four(xc, yc, x, y)

    seen = set()
    unique = []
    for p in points:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique
