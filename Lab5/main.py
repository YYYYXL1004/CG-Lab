import sys
import math
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from algorithms import (Camera, build_house_model, camera_basis,
                        render_model, transformed_vertices)


WINDOW_WIDTH = 800
WINDOW_HEIGHT = 520
PANEL_WIDTH = 220
CANVAS_WIDTH = WINDOW_WIDTH - PANEL_WIDTH
FOCAL_LENGTH = 430

BG_COLOR = (245, 247, 250)
TEXT_COLOR = (40, 95, 170)
PANEL_BG = (32, 36, 46)
PANEL_HEADER = (115, 190, 255)
PANEL_TEXT = (205, 214, 224)
PANEL_DIM = (130, 140, 152)
PANEL_SEP = (58, 64, 76)


def draw_pixels(screen, pixels):
    canvas = screen.subsurface((PANEL_WIDTH, 0, CANVAS_WIDTH, WINDOW_HEIGHT))
    pixel_array = pygame.PixelArray(canvas)
    mapped_cache = {}
    for (x, y), color in pixels.items():
        if 0 <= x < CANVAS_WIDTH and 0 <= y < WINDOW_HEIGHT:
            mapped = mapped_cache.get(color)
            if mapped is None:
                mapped = canvas.map_rgb(color)
                mapped_cache[color] = mapped
            pixel_array[x, y] = mapped
    del pixel_array


def move_camera(camera, forward_step, right_step, up_step):
    right, up, forward = camera_basis(camera)
    px, py, pz = camera.position
    px += forward[0] * forward_step + right[0] * right_step + up[0] * up_step
    py += forward[1] * forward_step + right[1] * right_step + up[1] * up_step
    pz += forward[2] * forward_step + right[2] * right_step + up[2] * up_step
    camera.position = (px, py, pz)


def draw_panel(screen, font, font_small, camera, auto_spin,
               tri_count, vertex_count, model_angle_x, model_angle_y):
    pygame.draw.rect(screen, PANEL_BG, (0, 0, PANEL_WIDTH, WINDOW_HEIGHT))
    pygame.draw.rect(screen, PANEL_SEP,
                     (PANEL_WIDTH - 1, 0, 1, WINDOW_HEIGHT))

    x = 12
    y = 12
    line_h = 20

    def header(text):
        nonlocal y
        if y > 18:
            y += 4
            pygame.draw.rect(screen, PANEL_SEP,
                             (x, y, PANEL_WIDTH - 2 * x, 1))
            y += 8
        surf = font.render(text, True, PANEL_HEADER)
        screen.blit(surf, (x, y))
        y += 24

    def row(text, color=PANEL_TEXT):
        nonlocal y
        surf = font_small.render(text, True, color)
        screen.blit(surf, (x + 4, y))
        y += line_h

    px, py, pz = camera.position
    header("Lab5 三维消隐")
    row("形体: 小建筑(墙体/屋顶/烟囱)")
    row(f"顶点数: {vertex_count}")
    row(f"可见三角面: {tri_count}")
    row("消隐算法: Z-buffer")
    row("光照模型: Phong 顶点光照")

    header("观察点")
    row(f"x={px:.2f}")
    row(f"y={py:.2f}")
    row(f"z={pz:.2f}")
    row(f"yaw={math.degrees(camera.yaw):.1f} 度")
    row(f"pitch={math.degrees(camera.pitch):.1f} 度")

    header("物体旋转")
    row(f"X轴={math.degrees(model_angle_x):.1f} 度")
    row(f"Y轴={math.degrees(model_angle_y):.1f} 度")
    row(f"自动旋转: {'开启' if auto_spin else '关闭'}")

    header("控制")
    row("左键拖动: 旋转物体")
    row("右键拖动: 旋转视角")
    row("方向键: 旋转视角")
    row("W/S: 前进/后退")
    row("A/D: 左移/右移")
    row("Q/E: 上移/下移")
    row("空格: 自动旋转")
    row("R: 重置", PANEL_DIM)


def draw_hud(screen, font):
    lines = [
        "左键拖动=旋转物体 | 右键/方向键=旋转视角 | W/S/A/D/Q/E=漫游 | 空格=自动旋转 | R=重置",
        "三维边线和面均为手写光栅化；消隐使用 Z-buffer；顶点颜色使用 Phong 光照模型",
    ]
    h = 8 + 24 * len(lines)
    pygame.draw.rect(screen, BG_COLOR,
                     (PANEL_WIDTH, 0, CANVAS_WIDTH, h))
    for i, text in enumerate(lines):
        surface = font.render(text, True, TEXT_COLOR)
        screen.blit(surface, (PANEL_WIDTH + 12, 5 + i * 24))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(
        "Lab5: 三维形体漫游、Z-buffer消隐与Phong光照")
    font = pygame.font.Font("C:/Windows/Fonts/msyh.ttc", 15)
    font_small = pygame.font.Font("C:/Windows/Fonts/msyh.ttc", 12)
    clock = pygame.time.Clock()

    base_vertices, triangles = build_house_model()
    camera = Camera(position=(0.0, 0.35, -6.2), yaw=0.0, pitch=0.0)
    model_angle_y = 0.0
    model_angle_x = 0.0
    auto_spin = False
    dragging = None
    last_mouse = None
    pixels = {}
    tri_count = 0
    vertex_count = len(base_vertices)
    dirty = True

    while True:
        dt = clock.tick(30) / 1000.0
        move_speed = 3.0 * dt
        turn_speed = 1.8 * dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    camera = Camera(position=(0.0, 0.35, -6.2),
                                    yaw=0.0, pitch=0.0)
                    model_angle_y = 0.0
                    model_angle_x = 0.0
                    dirty = True
                elif event.key == pygame.K_SPACE:
                    auto_spin = not auto_spin
                    dirty = True

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                dragging = "MODEL"
                last_mouse = event.pos

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                dragging = "CAMERA"
                last_mouse = event.pos

            elif event.type == pygame.MOUSEBUTTONUP and event.button in (1, 3):
                dragging = None
                last_mouse = None

            elif event.type == pygame.MOUSEMOTION and dragging:
                dx = event.pos[0] - last_mouse[0]
                dy = event.pos[1] - last_mouse[1]
                if dragging == "MODEL":
                    model_angle_y += dx * 0.01
                    model_angle_x += dy * 0.01
                    model_angle_x = max(-1.35, min(1.35, model_angle_x))
                else:
                    camera.yaw += dx * 0.006
                    camera.pitch -= dy * 0.006
                    camera.pitch = max(-1.2, min(1.2, camera.pitch))
                last_mouse = event.pos
                dirty = True

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            move_camera(camera, move_speed, 0, 0)
            dirty = True
        if keys[pygame.K_s]:
            move_camera(camera, -move_speed, 0, 0)
            dirty = True
        if keys[pygame.K_a]:
            move_camera(camera, 0, -move_speed, 0)
            dirty = True
        if keys[pygame.K_d]:
            move_camera(camera, 0, move_speed, 0)
            dirty = True
        if keys[pygame.K_q]:
            move_camera(camera, 0, 0, move_speed)
            dirty = True
        if keys[pygame.K_e]:
            move_camera(camera, 0, 0, -move_speed)
            dirty = True
        if keys[pygame.K_LEFT]:
            camera.yaw -= turn_speed
            dirty = True
        if keys[pygame.K_RIGHT]:
            camera.yaw += turn_speed
            dirty = True
        if keys[pygame.K_UP]:
            camera.pitch = min(1.2, camera.pitch + turn_speed)
            dirty = True
        if keys[pygame.K_DOWN]:
            camera.pitch = max(-1.2, camera.pitch - turn_speed)
            dirty = True

        if auto_spin:
            model_angle_y += 0.45 * dt
            dirty = True

        if not dirty:
            continue

        world_vertices = transformed_vertices(
            base_vertices, angle_y=model_angle_y,
            offset=(0.0, 0.0, 4.0), angle_x=model_angle_x)
        pixels, tri_count, vertex_count = render_model(
            world_vertices, triangles, camera,
            CANVAS_WIDTH, WINDOW_HEIGHT, FOCAL_LENGTH)

        screen.fill(BG_COLOR)
        draw_pixels(screen, pixels)
        draw_hud(screen, font)
        draw_panel(screen, font, font_small, camera, auto_spin,
                   tri_count, vertex_count, model_angle_x, model_angle_y)

        pygame.display.flip()
        dirty = False


if __name__ == "__main__":
    main()
