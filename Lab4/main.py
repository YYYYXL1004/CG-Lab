import sys
import pygame
from algorithms import (midpoint_line, bezier_curve_pixels, de_casteljau,
                        translate_points, rotate_points, centroid)

PANEL_WIDTH   = 220                  # 左侧监控面板宽度
CANVAS_WIDTH  = 800                  # 画布宽度
WINDOW_WIDTH  = PANEL_WIDTH + CANVAS_WIDTH
WINDOW_HEIGHT = 600
GRID_SIZE     = 10

BG_COLOR      = (255, 255, 255)
GRID_COLOR    = (220, 220, 220)
CURVE_COLOR   = (30, 100, 220)      # Bezier 曲线（蓝色）
POLYGON_COLOR = (200, 200, 200)     # 控制多边形（灰色）
POINT_COLOR   = (220, 50, 50)       # 控制点（红色）
ACTIVE_COLOR  = (255, 165, 0)       # 被拖拽的控制点（橙色）
CENTER_COLOR  = (0, 180, 60)        # 旋转中心（绿色）
TEXT_COLOR    = (0, 100, 255)
LABEL_COLOR   = (80, 80, 80)        # 控制点标签

# 左侧面板配色
PANEL_BG      = (32, 36, 46)        # 深色背景
PANEL_HEADER  = (100, 180, 255)     # 标题（亮蓝）
PANEL_TEXT    = (190, 200, 210)     # 数据文本
PANEL_DIM     = (120, 130, 140)     # 次要文本
PANEL_SEP     = (55, 60, 72)        # 分隔线

DRAG_RADIUS = 2  # 拖拽检测半径（网格单位）


def physical_to_logical(pos):
    return (pos[0] - PANEL_WIDTH) // GRID_SIZE, pos[1] // GRID_SIZE


def draw_grid(screen):
    for x in range(0, CANVAS_WIDTH, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR,
                         (PANEL_WIDTH + x, 0), (PANEL_WIDTH + x, WINDOW_HEIGHT))
    for y in range(0, WINDOW_HEIGHT, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR,
                         (PANEL_WIDTH, y), (WINDOW_WIDTH, y))


def draw_pixels(screen, points, color):
    for x, y in points:
        pygame.draw.rect(screen, color,
                         (PANEL_WIDTH + x * GRID_SIZE, y * GRID_SIZE,
                          GRID_SIZE, GRID_SIZE))


def draw_control_point(screen, x, y, color, radius=6):
    """绘制控制点（小圆圈，比普通网格像素更醒目）"""
    cx = PANEL_WIDTH + round(x) * GRID_SIZE + GRID_SIZE // 2
    cy = round(y) * GRID_SIZE + GRID_SIZE // 2
    pygame.draw.circle(screen, color, (cx, cy), radius)
    pygame.draw.circle(screen, (0, 0, 0), (cx, cy), radius, 1)


def draw_hud(screen, font, lines):
    h = 8 + 22 * len(lines)
    pygame.draw.rect(screen, BG_COLOR, (PANEL_WIDTH, 0, CANVAS_WIDTH, h))
    for i, line in enumerate(lines):
        surface = font.render(line, True, TEXT_COLOR)
        screen.blit(surface, (PANEL_WIDTH + 10, 4 + i * 22))


def draw_panel(screen, font, font_small, control_points, dragging,
               rotate_step, curve_pixel_count, last_ops):
    """绘制左侧实时数据监控面板"""
    # 背景 & 右边框
    pygame.draw.rect(screen, PANEL_BG, (0, 0, PANEL_WIDTH, WINDOW_HEIGHT))
    pygame.draw.line(screen, PANEL_SEP,
                     (PANEL_WIDTH - 1, 0), (PANEL_WIDTH - 1, WINDOW_HEIGHT))

    x_pad = 10
    y = 10
    line_h = 16

    def header(text):
        nonlocal y
        if y > 15:
            y += 3
            pygame.draw.line(screen, PANEL_SEP,
                             (x_pad, y), (PANEL_WIDTH - x_pad, y))
            y += 5
        if y + line_h > WINDOW_HEIGHT:
            return
        surf = font.render(text, True, PANEL_HEADER)
        screen.blit(surf, (x_pad, y))
        y += line_h + 3

    def row(text, color=PANEL_TEXT):
        nonlocal y
        if y + line_h > WINDOW_HEIGHT:
            return
        surf = font_small.render(text, True, color)
        screen.blit(surf, (x_pad + 4, y))
        y += line_h

    # ── 曲线信息 ──
    n = len(control_points)
    order = max(0, n - 1)
    header("曲线信息")
    row(f"阶数: {order}    控制点: {n}")
    row(f"曲线像素: {curve_pixel_count}")
    row(f"旋转步长: {rotate_step}°")

    # ── 控制点坐标 ──
    header("控制点坐标")
    if n == 0:
        row("(无)", PANEL_DIM)
    else:
        show_max = 8
        for i in range(min(n, show_max)):
            px, py = control_points[i]
            tag = " ◄" if i == dragging else ""
            row(f"P{i} ({px:.1f}, {py:.1f}){tag}")
        if n > show_max:
            row(f"  ... 共 {n} 个", PANEL_DIM)

    # ── 旋转中心 ──
    header("旋转中心(质心)")
    if n >= 2:
        cx, cy = centroid(control_points)
        row(f"({cx:.1f}, {cy:.1f})")
    else:
        row("(需≥2个点)", PANEL_DIM)

    # ── De Casteljau t=0.5 ──
    header("De Casteljau t=0.5")
    if n >= 2:
        pts = [[p[0], p[1]] for p in control_points]
        max_r = min(n, 6)
        for r in range(max_r):
            if r == 0:
                items = [f"P{i}" for i in range(min(n, 5))]
                sfx = " ..." if n > 5 else ""
                row(f"r=0: {' '.join(items)}{sfx}", PANEL_DIM)
            else:
                for i in range(n - r):
                    pts[i][0] = 0.5 * pts[i][0] + 0.5 * pts[i + 1][0]
                    pts[i][1] = 0.5 * pts[i][1] + 0.5 * pts[i + 1][1]
                cnt = n - r
                if cnt <= 4:
                    items = [f"({pts[i][0]:.0f},{pts[i][1]:.0f})"
                             for i in range(cnt)]
                else:
                    items = [f"({pts[i][0]:.0f},{pts[i][1]:.0f})"
                             for i in range(3)]
                    items.append("...")
                row(f"r={r}: {' '.join(items)}")
        if n > max_r:
            for r in range(max_r, n):
                for i in range(n - r):
                    pts[i][0] = 0.5 * pts[i][0] + 0.5 * pts[i + 1][0]
                    pts[i][1] = 0.5 * pts[i][1] + 0.5 * pts[i + 1][1]
        row(f"→ ({pts[0][0]:.1f}, {pts[0][1]:.1f})", PANEL_HEADER)
    else:
        row("(需≥2个点)", PANEL_DIM)

    # ── 最近操作 ──
    header("最近操作")
    if not last_ops:
        row("(无)", PANEL_DIM)
    else:
        for op in last_ops[-5:]:
            row(op)


def find_nearest_point(pos, points, radius=DRAG_RADIUS):
    """查找距离 pos 最近的控制点，返回索引或 -1"""
    best = -1
    best_dist = float('inf')
    px, py = pos
    for i, pt in enumerate(points):
        dist = ((px - pt[0]) ** 2 + (py - pt[1]) ** 2) ** 0.5
        if dist <= radius and dist < best_dist:
            best_dist = dist
            best = i
    return best


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Lab4: Bezier 曲线绘制与变换")
    font = pygame.font.Font("C:/Windows/Fonts/msyh.ttc", 16)
    font_small = pygame.font.Font("C:/Windows/Fonts/msyh.ttc", 12)
    clock = pygame.time.Clock()

    mouse_pos = (0, 0)

    # 控制顶点列表（浮点坐标，变换后保留精度）
    control_points = []
    dragging = -1        # 正在拖拽的控制点索引，-1 表示无
    rotate_step = 5      # 旋转步长（度）
    curve_pixel_count = 0
    last_ops = []        # 最近操作日志（显示在面板）

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEMOTION:
                mouse_pos = physical_to_logical(event.pos)
                if dragging >= 0:
                    control_points[dragging] = (float(mouse_pos[0]),
                                                float(mouse_pos[1]))

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = physical_to_logical(event.pos)
                if pos[0] >= 0:  # 只响应画布区域的点击
                    idx = find_nearest_point(pos, control_points)
                    if idx >= 0:
                        dragging = idx
                    else:
                        control_points.append((float(pos[0]), float(pos[1])))
                        n = len(control_points)
                        last_ops.append(f"添加 P{n-1}({pos[0]},{pos[1]})")
                        print(f">>> 添加控制点 P{n - 1}({pos[0]},{pos[1]}), "
                              f"当前 {n} 个点, {max(0, n - 1)} 阶曲线")

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = -1

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                pos = physical_to_logical(event.pos)
                if pos[0] >= 0:
                    idx = find_nearest_point(pos, control_points, radius=3)
                    if idx >= 0:
                        removed = control_points.pop(idx)
                        last_ops.append(f"删除 P{idx}")
                        print(f">>> 删除控制点 P{idx}"
                              f"({removed[0]:.0f},{removed[1]:.0f})")
                        if dragging == idx:
                            dragging = -1
                        elif dragging > idx:
                            dragging -= 1

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    control_points = []
                    dragging = -1
                    last_ops = []
                    curve_pixel_count = 0
                    print(">>> 已重置")

                elif event.key == pygame.K_BACKSPACE and control_points:
                    control_points.pop()
                    last_ops.append("删除末点")

                # 平移（方向键）
                elif event.key == pygame.K_LEFT and control_points:
                    control_points = translate_points(
                        control_points, -1, 0, print_log=True)
                    last_ops.append("平移 Δx=-1")
                elif event.key == pygame.K_RIGHT and control_points:
                    control_points = translate_points(
                        control_points, 1, 0, print_log=True)
                    last_ops.append("平移 Δx=+1")
                elif event.key == pygame.K_UP and control_points:
                    control_points = translate_points(
                        control_points, 0, -1, print_log=True)
                    last_ops.append("平移 Δy=-1")
                elif event.key == pygame.K_DOWN and control_points:
                    control_points = translate_points(
                        control_points, 0, 1, print_log=True)
                    last_ops.append("平移 Δy=+1")

                # 旋转（Q 逆时针 / E 顺时针，绕质心旋转）
                elif event.key == pygame.K_q and len(control_points) >= 2:
                    cx, cy = centroid(control_points)
                    control_points = rotate_points(
                        control_points, -rotate_step, cx, cy, print_log=True)
                    last_ops.append(f"旋转 -{rotate_step}°")
                elif event.key == pygame.K_e and len(control_points) >= 2:
                    cx, cy = centroid(control_points)
                    control_points = rotate_points(
                        control_points, rotate_step, cx, cy, print_log=True)
                    last_ops.append(f"旋转 +{rotate_step}°")

                # 旋转步长调整（+/-）
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS,
                                   pygame.K_KP_PLUS):
                    rotate_step = min(45, rotate_step + 1)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    rotate_step = max(1, rotate_step - 1)

                # 打印一次 De Casteljau 递推过程（t=0.5）
                elif event.key == pygame.K_d and len(control_points) >= 2:
                    de_casteljau(control_points, 0.5, print_log=True)

        # ---- 渲染 ----
        screen.fill(BG_COLOR)
        draw_grid(screen)

        if len(control_points) >= 2:
            # 控制多边形（灰色连线）
            for i in range(len(control_points) - 1):
                x0 = round(control_points[i][0])
                y0 = round(control_points[i][1])
                x1 = round(control_points[i + 1][0])
                y1 = round(control_points[i + 1][1])
                seg = midpoint_line(x0, y0, x1, y1)
                draw_pixels(screen, seg, POLYGON_COLOR)

            # Bezier 曲线（蓝色像素）
            curve_pts = bezier_curve_pixels(control_points)
            curve_pixel_count = len(curve_pts)
            draw_pixels(screen, curve_pts, CURVE_COLOR)

            # 旋转中心标记（绿色十字）
            cx, cy = centroid(control_points)
            rcx = PANEL_WIDTH + round(cx) * GRID_SIZE + GRID_SIZE // 2
            rcy = round(cy) * GRID_SIZE + GRID_SIZE // 2
            pygame.draw.line(screen, CENTER_COLOR,
                             (rcx - 6, rcy), (rcx + 6, rcy), 2)
            pygame.draw.line(screen, CENTER_COLOR,
                             (rcx, rcy - 6), (rcx, rcy + 6), 2)

        # 控制点（圆圈 + 标签）
        for i, pt in enumerate(control_points):
            color = ACTIVE_COLOR if i == dragging else POINT_COLOR
            draw_control_point(screen, pt[0], pt[1], color)
            # 标签 P0, P1, ...
            lx = PANEL_WIDTH + round(pt[0]) * GRID_SIZE + GRID_SIZE + 2
            ly = round(pt[1]) * GRID_SIZE - 6
            label = font_small.render(f"P{i}", True, LABEL_COLOR)
            screen.blit(label, (lx, ly))

        # HUD
        n = len(control_points)
        order = max(0, n - 1)
        hud_lines = [
            f"控制点:{n}  阶数:{order}  坐标:{mouse_pos}  旋转步长:{rotate_step}°",
            "左键=加点/拖拽  右键=删点  方向键=平移  Q/E=旋转  +/-=步长",
            "D=打印递推  Backspace=删末点  R=重置",
        ]
        draw_hud(screen, font, hud_lines)

        # 左侧数据面板
        draw_panel(screen, font, font_small, control_points, dragging,
                   rotate_step, curve_pixel_count, last_ops)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
