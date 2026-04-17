import sys

import pygame
import math
from algorithms import midpoint_line, midpoint_circle, midpoint_ellipse

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
GRID_SIZE = 10

BG_COLOR = (255, 255, 255)
GRID_COLOR = (220, 220, 220)
LINE_COLOR = (0, 0, 0)
TEMP_COLOR = (255, 0, 0)
TEXT_COLOR = (0, 100, 255)
REPLAY_COLOR = (255, 165, 0)


def physical_to_logical(pos):
    """物理像素坐标 → 网格逻辑坐标"""
    return pos[0] // GRID_SIZE, pos[1] // GRID_SIZE


def draw_grid(screen):
    for x in range(0, WINDOW_WIDTH, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, WINDOW_HEIGHT))
    for y in range(0, WINDOW_HEIGHT, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (0, y), (WINDOW_WIDTH, y))


def draw_pixels(screen, points, color):
    for x, y in points:
        pygame.draw.rect(screen, color, (x * GRID_SIZE, y * GRID_SIZE, GRID_SIZE, GRID_SIZE))


def build_shape(shape, start, end, print_log=False):
    """根据图形类型调用对应的中点法算法，返回像素点列表"""
    x0, y0 = start
    x1, y1 = end

    if shape == 'LINE':
        return midpoint_line(x0, y0, x1, y1, print_log)

    if shape == 'CIRCLE':
        radius = int(math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2))
        return midpoint_circle(x0, y0, radius, print_log)

    if shape == 'ELLIPSE':
        rx = abs(x1 - x0)
        ry = abs(y1 - y0)
        return midpoint_ellipse(x0, y0, rx, ry, print_log)

    return []


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Lab1: 中点法 — 直线、圆、椭圆")
    font = pygame.font.Font("C:/Windows/Fonts/msyh.ttc", 18)
    clock = pygame.time.Clock()

    # 绘图状态
    drawing = False
    start_pos = None
    mouse_pos = (0, 0)
    shape = 'LINE'
    shapes = []  # 已完成的图形列表

    # 回放状态
    replaying = False
    replay_points = []
    replay_index = 0

    while True:
        # --- 事件处理 ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_l and not replaying:
                    shape = 'LINE'
                elif event.key == pygame.K_c and not replaying:
                    shape = 'CIRCLE'
                elif event.key == pygame.K_e and not replaying:
                    shape = 'ELLIPSE'
                elif event.key == pygame.K_r and not drawing and shapes:
                    # 开始回放
                    replaying = True
                    replay_index = 0
                    replay_points = []
                    for s in shapes:
                        replay_points.extend(s["points"])
                    print("\n>>> 开始回放...")

            elif event.type == pygame.MOUSEMOTION:
                mouse_pos = physical_to_logical(event.pos)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not replaying:
                drawing = True
                start_pos = physical_to_logical(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and drawing:
                drawing = False
                pts = build_shape(shape, start_pos, mouse_pos, print_log=True)
                shapes.append({"type": shape, "points": pts})

        # --- 回放推进 ---
        if replaying:
            replay_index += 1
            if replay_index >= len(replay_points):
                replay_index = len(replay_points)
                replaying = False
                print(">>> 回放结束。")

        # --- 渲染 ---
        screen.fill(BG_COLOR)
        draw_grid(screen)

        if replaying:
            draw_pixels(screen, replay_points[:replay_index], REPLAY_COLOR)
        else:
            for s in shapes:
                draw_pixels(screen, s["points"], LINE_COLOR)
            if drawing and start_pos:
                temp = build_shape(shape, start_pos, mouse_pos)
                draw_pixels(screen, temp, TEMP_COLOR)

        # UI 提示
        mode = "REPLAYING..." if replaying else shape
        tip = "L=直线  C=圆  E=椭圆  R=回放"
        screen.blit(font.render(f"{mode} | {mouse_pos} | {tip}", True, TEXT_COLOR), (10, 10))

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
