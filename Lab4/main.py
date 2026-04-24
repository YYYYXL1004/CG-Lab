import sys
import pygame
from algorithms import (midpoint_line, bezier_curve_pixels, de_casteljau,
                        translate_points, rotate_points, centroid)

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
GRID_SIZE = 10

BG_COLOR      = (255, 255, 255)
GRID_COLOR    = (220, 220, 220)
CURVE_COLOR   = (30, 100, 220)      # Bezier 曲线（蓝色）
POLYGON_COLOR = (200, 200, 200)     # 控制多边形（灰色）
POINT_COLOR   = (220, 50, 50)       # 控制点（红色）
ACTIVE_COLOR  = (255, 165, 0)       # 被拖拽的控制点（橙色）
CENTER_COLOR  = (0, 180, 60)        # 旋转中心（绿色）
TEXT_COLOR    = (0, 100, 255)
LABEL_COLOR   = (80, 80, 80)        # 控制点标签

DRAG_RADIUS = 2  # 拖拽检测半径（网格单位）


def physical_to_logical(pos):
    return pos[0] // GRID_SIZE, pos[1] // GRID_SIZE


def draw_grid(screen):
    for x in range(0, WINDOW_WIDTH, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, WINDOW_HEIGHT))
    for y in range(0, WINDOW_HEIGHT, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (0, y), (WINDOW_WIDTH, y))


def draw_pixels(screen, points, color):
    for x, y in points:
        pygame.draw.rect(screen, color,
                         (x * GRID_SIZE, y * GRID_SIZE, GRID_SIZE, GRID_SIZE))


def draw_control_point(screen, x, y, color, radius=6):
    """绘制控制点（小圆圈，比普通网格像素更醒目）"""
    cx = round(x) * GRID_SIZE + GRID_SIZE // 2
    cy = round(y) * GRID_SIZE + GRID_SIZE // 2
    pygame.draw.circle(screen, color, (cx, cy), radius)
    pygame.draw.circle(screen, (0, 0, 0), (cx, cy), radius, 1)


def draw_hud(screen, font, lines):
    h = 8 + 22 * len(lines)
    pygame.draw.rect(screen, BG_COLOR, (0, 0, WINDOW_WIDTH, h))
    for i, line in enumerate(lines):
        surface = font.render(line, True, TEXT_COLOR)
        screen.blit(surface, (10, 4 + i * 22))


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
                idx = find_nearest_point(pos, control_points)
                if idx >= 0:
                    # 拖拽已有控制点
                    dragging = idx
                else:
                    # 添加新控制点
                    control_points.append((float(pos[0]), float(pos[1])))
                    n = len(control_points)
                    print(f">>> 添加控制点 P{n - 1}({pos[0]},{pos[1]}), "
                          f"当前 {n} 个点, {max(0, n - 1)} 阶曲线")

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = -1

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                # 右键删除最近的控制点
                pos = physical_to_logical(event.pos)
                idx = find_nearest_point(pos, control_points, radius=3)
                if idx >= 0:
                    removed = control_points.pop(idx)
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
                    print(">>> 已重置")

                elif event.key == pygame.K_BACKSPACE and control_points:
                    control_points.pop()

                # 平移（方向键）
                elif event.key == pygame.K_LEFT and control_points:
                    control_points = translate_points(
                        control_points, -1, 0, print_log=True)
                elif event.key == pygame.K_RIGHT and control_points:
                    control_points = translate_points(
                        control_points, 1, 0, print_log=True)
                elif event.key == pygame.K_UP and control_points:
                    control_points = translate_points(
                        control_points, 0, -1, print_log=True)
                elif event.key == pygame.K_DOWN and control_points:
                    control_points = translate_points(
                        control_points, 0, 1, print_log=True)

                # 旋转（Q 逆时针 / E 顺时针，绕质心旋转）
                elif event.key == pygame.K_q and len(control_points) >= 2:
                    cx, cy = centroid(control_points)
                    control_points = rotate_points(
                        control_points, -rotate_step, cx, cy, print_log=True)
                elif event.key == pygame.K_e and len(control_points) >= 2:
                    cx, cy = centroid(control_points)
                    control_points = rotate_points(
                        control_points, rotate_step, cx, cy, print_log=True)

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
            draw_pixels(screen, curve_pts, CURVE_COLOR)

            # 旋转中心标记（绿色十字）
            cx, cy = centroid(control_points)
            rcx = round(cx) * GRID_SIZE + GRID_SIZE // 2
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
            lx = round(pt[0]) * GRID_SIZE + GRID_SIZE + 2
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

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
