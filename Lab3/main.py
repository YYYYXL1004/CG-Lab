import sys
import pygame
from algorithms import midpoint_line, cohen_sutherland_clip

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
GRID_SIZE = 10

BG_COLOR      = (255, 255, 255)
GRID_COLOR    = (220, 220, 220)
RECT_BORDER   = (50, 50, 200)       # 裁剪窗口边框
RECT_FILL     = (235, 240, 255)     # 裁剪窗口填充
OUTSIDE_COLOR = (220, 80, 80)       # 窗口外的直线段（红色虚线）
INSIDE_COLOR  = (30, 180, 60)       # 窗口内的直线段（绿色实线）
TEMP_COLOR    = (255, 0, 0)         # 预览橡皮筋
TEXT_COLOR    = (0, 100, 255)


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


def draw_dashed_pixels(screen, points, color, dash_len=3):
    """虚线效果：每 dash_len 个像素交替显示/隐藏"""
    for i, (x, y) in enumerate(points):
        if (i // dash_len) % 2 == 0:
            pygame.draw.rect(screen, color,
                             (x * GRID_SIZE, y * GRID_SIZE, GRID_SIZE, GRID_SIZE))


def draw_rect_border(screen, xmin, ymin, xmax, ymax, color):
    """用中点画线法绘制矩形边框"""
    edges = []
    edges.extend(midpoint_line(xmin, ymin, xmax, ymin))
    edges.extend(midpoint_line(xmax, ymin, xmax, ymax))
    edges.extend(midpoint_line(xmax, ymax, xmin, ymax))
    edges.extend(midpoint_line(xmin, ymax, xmin, ymin))
    draw_pixels(screen, edges, color)


def draw_rect_fill(screen, xmin, ymin, xmax, ymax, color):
    """填充矩形区域（半透明底色，便于区分窗口内外）"""
    for gx in range(xmin, xmax + 1):
        for gy in range(ymin, ymax + 1):
            pygame.draw.rect(screen, color,
                             (gx * GRID_SIZE, gy * GRID_SIZE,
                              GRID_SIZE, GRID_SIZE))


def draw_hud(screen, font, lines):
    h = 8 + 22 * len(lines)
    pygame.draw.rect(screen, BG_COLOR, (0, 0, WINDOW_WIDTH, h))
    for i, line in enumerate(lines):
        surface = font.render(line, True, TEXT_COLOR)
        screen.blit(surface, (10, 4 + i * 22))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Lab3: Cohen-Sutherland 直线段裁剪")
    font = pygame.font.Font("C:/Windows/Fonts/msyh.ttc", 16)
    clock = pygame.time.Clock()

    mouse_pos = (0, 0)

    # 两个阶段: RECT → LINE
    #   RECT: 点击两个角点定义裁剪窗口
    #   LINE: 点击两个点定义直线段，自动裁剪并显示结果
    mode = "RECT"
    rect_p1 = None                  # RECT 阶段的第一角
    clip_rect = None                # (xmin, ymin, xmax, ymax)
    line_start = None               # LINE 阶段的起点
    # 每条线: (x0, y0, x1, y1, accept, cx0, cy0, cx1, cy1)
    lines = []

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEMOTION:
                mouse_pos = physical_to_logical(event.pos)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    # 全部重置
                    mode = "RECT"
                    rect_p1 = None
                    clip_rect = None
                    line_start = None
                    lines = []

                elif event.key == pygame.K_ESCAPE:
                    if mode == "RECT":
                        rect_p1 = None
                    else:
                        line_start = None

                elif event.key == pygame.K_BACKSPACE and mode == "LINE" and lines:
                    lines.pop()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if mode == "RECT":
                    if rect_p1 is None:
                        rect_p1 = physical_to_logical(event.pos)
                    else:
                        p2 = physical_to_logical(event.pos)
                        xmin = min(rect_p1[0], p2[0])
                        ymin = min(rect_p1[1], p2[1])
                        xmax = max(rect_p1[0], p2[0])
                        ymax = max(rect_p1[1], p2[1])
                        if xmax > xmin and ymax > ymin:
                            clip_rect = (xmin, ymin, xmax, ymax)
                            mode = "LINE"
                            rect_p1 = None
                            print(f"\n>>> 裁剪窗口已设定: ({xmin},{ymin}) → ({xmax},{ymax})")
                        else:
                            print(">>> 窗口太小，请重新选择。")
                            rect_p1 = None

                elif mode == "LINE":
                    if line_start is None:
                        line_start = physical_to_logical(event.pos)
                    else:
                        end = physical_to_logical(event.pos)
                        x0, y0 = line_start
                        x1, y1 = end
                        xmin, ymin, xmax, ymax = clip_rect
                        accept, cx0, cy0, cx1, cy1 = cohen_sutherland_clip(
                            x0, y0, x1, y1, xmin, ymin, xmax, ymax,
                            print_log=True)
                        lines.append((x0, y0, x1, y1, accept,
                                      round(cx0), round(cy0),
                                      round(cx1), round(cy1)))
                        line_start = None

        # ---- 渲染 ----
        screen.fill(BG_COLOR)
        draw_grid(screen)

        # 裁剪窗口
        if clip_rect:
            xmin, ymin, xmax, ymax = clip_rect
            draw_rect_fill(screen, xmin, ymin, xmax, ymax, RECT_FILL)
            draw_rect_border(screen, xmin, ymin, xmax, ymax, RECT_BORDER)

        # RECT 模式的矩形预览（橡皮筋）
        if mode == "RECT" and rect_p1:
            pxmin = min(rect_p1[0], mouse_pos[0])
            pymin = min(rect_p1[1], mouse_pos[1])
            pxmax = max(rect_p1[0], mouse_pos[0])
            pymax = max(rect_p1[1], mouse_pos[1])
            draw_rect_border(screen, pxmin, pymin, pxmax, pymax, TEMP_COLOR)

        # 已裁剪的直线段
        for lx0, ly0, lx1, ly1, accept, cx0, cy0, cx1, cy1 in lines:
            # 原始直线 — 红色虚线（窗口外部分）
            orig_pts = midpoint_line(lx0, ly0, lx1, ly1)
            draw_dashed_pixels(screen, orig_pts, OUTSIDE_COLOR)
            # 裁剪后 — 绿色实线（窗口内部分）
            if accept:
                clip_pts = midpoint_line(cx0, cy0, cx1, cy1)
                draw_pixels(screen, clip_pts, INSIDE_COLOR)

        # LINE 模式的直线预览（橡皮筋）
        if mode == "LINE" and line_start:
            preview = midpoint_line(line_start[0], line_start[1],
                                    mouse_pos[0], mouse_pos[1])
            draw_pixels(screen, preview, TEMP_COLOR)

        # HUD
        if mode == "RECT":
            if rect_p1:
                hud_lines = [
                    f"模式:画裁剪窗口  坐标:{mouse_pos}  已选第一角:{rect_p1}",
                    "左键=选第二角  Esc=取消  R=重置",
                ]
            else:
                hud_lines = [
                    f"模式:画裁剪窗口  坐标:{mouse_pos}",
                    "左键=选第一角  R=重置",
                ]
        else:
            if line_start:
                hud_lines = [
                    f"模式:画直线  坐标:{mouse_pos}  起点:{line_start}  已裁剪:{len(lines)}条",
                    "左键=终点  Esc=取消  Backspace=撤销  R=重置",
                ]
            else:
                hud_lines = [
                    f"模式:画直线  坐标:{mouse_pos}  已裁剪:{len(lines)}条",
                    "左键=起点  Backspace=撤销  R=重置",
                ]

        draw_hud(screen, font, hud_lines)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
