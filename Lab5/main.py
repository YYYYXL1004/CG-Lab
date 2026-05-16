import sys
import math
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from algorithms import (Camera, LIGHT_POSITION, build_house_model,
                        build_floor_grid_segments, build_light_gizmo_segments,
                        camera_basis, model_center, project_point,
                        render_model,
                        transformed_vertices)


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

RENDER_MODES = ("solid_wireframe", "solid", "wireframe")
RENDER_MODE_LABELS = {
    "solid_wireframe": "实体+线框",
    "solid": "实体",
    "wireframe": "线框",
}


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


def draw_floor_grid(screen, camera, world_vertices):
    segments = build_floor_grid_segments(
        camera, CANVAS_WIDTH, WINDOW_HEIGHT, FOCAL_LENGTH,
        model_vertices=world_vertices)
    canvas = screen.subsurface((PANEL_WIDTH, 0, CANVAS_WIDTH, WINDOW_HEIGHT))
    for seg in segments:
        a = (int(round(seg["a"][0])), int(round(seg["a"][1])))
        b = (int(round(seg["b"][0])), int(round(seg["b"][1])))
        pygame.draw.line(canvas, seg["color"], a, b, seg["width"])


def draw_light_gizmo(screen, camera, light_position, target, ground_y):
    segments = build_light_gizmo_segments(
        camera, light_position, target, CANVAS_WIDTH, WINDOW_HEIGHT,
        FOCAL_LENGTH, ground_y=ground_y)
    canvas = screen.subsurface((PANEL_WIDTH, 0, CANVAS_WIDTH, WINDOW_HEIGHT))
    ground_projection = None
    for seg in segments:
        a = (int(round(seg["a"][0])), int(round(seg["a"][1])))
        b = (int(round(seg["b"][0])), int(round(seg["b"][1])))
        pygame.draw.line(canvas, seg["color"], a, b, seg["width"])
        if seg["kind"] == "light_drop":
            ground_projection = b
    if ground_projection is not None:
        pygame.draw.circle(canvas, (245, 206, 90), ground_projection, 4)
        pygame.draw.circle(canvas, (145, 100, 30), ground_projection, 4, 1)


def draw_light_marker(screen, camera, light_position):
    projected = project_point(light_position, camera, CANVAS_WIDTH,
                              WINDOW_HEIGHT, FOCAL_LENGTH)
    if projected is None:
        return

    x = int(round(PANEL_WIDTH + projected[0]))
    y = int(round(projected[1]))
    pygame.draw.circle(screen, (255, 244, 120), (x, y), 8)
    pygame.draw.circle(screen, (180, 128, 30), (x, y), 8, 2)
    pygame.draw.line(screen, (180, 128, 30), (x - 12, y), (x + 12, y), 1)
    pygame.draw.line(screen, (180, 128, 30), (x, y - 12), (x, y + 12), 1)


def move_camera(camera, forward_step, right_step, up_step):
    right, up, forward = camera_basis(camera)
    px, py, pz = camera.position
    px += forward[0] * forward_step + right[0] * right_step + up[0] * up_step
    py += forward[1] * forward_step + right[1] * right_step + up[1] * up_step
    pz += forward[2] * forward_step + right[2] * right_step + up[2] * up_step
    camera.position = (px, py, pz)


def dolly_camera(camera, amount):
    move_camera(camera, amount, 0.0, 0.0)


def move_light(light_position, dx, dy, dz):
    return (light_position[0] + dx,
            light_position[1] + dy,
            light_position[2] + dz)


def move_light_by_mouse_drag(light_position, camera, screen_dx, screen_dy,
                             scale=0.018):
    right, up, _ = camera_basis(camera)
    dx = screen_dx * scale
    dy = -screen_dy * scale
    return (
        light_position[0] + right[0] * dx + up[0] * dy,
        light_position[1] + right[1] * dx + up[1] * dy,
        light_position[2] + right[2] * dx + up[2] * dy,
    )


def is_near_projected_light(mouse_pos, camera, light_position, canvas_width,
                            height, focal, panel_width=PANEL_WIDTH,
                            radius=18):
    projected = project_point(light_position, camera, canvas_width,
                              height, focal)
    if projected is None:
        return False
    sx = panel_width + projected[0]
    sy = projected[1]
    dx = mouse_pos[0] - sx
    dy = mouse_pos[1] - sy
    return dx * dx + dy * dy <= radius * radius


def build_panel_items(camera, auto_spin, tri_count, vertex_count,
                      model_angle_x, model_angle_y, light_position,
                      render_mode, use_z_buffer):
    px, py, pz = camera.position
    lx, ly, lz = light_position
    return [
        ("header", "Lab5 三维消隐", None),
        ("row", f"形体: 小建筑  面: {tri_count}  点: {vertex_count}", PANEL_TEXT),
        ("row", f"模式: {RENDER_MODE_LABELS[render_mode]}  Z-buffer: {'开' if use_z_buffer else '关'}", PANEL_TEXT),
        ("row", f"观察点: ({px:.2f}, {py:.2f}, {pz:.2f})", PANEL_TEXT),
        ("row", f"视角: yaw={math.degrees(camera.yaw):.1f}  pitch={math.degrees(camera.pitch):.1f}", PANEL_TEXT),
        ("row", f"旋转: X={math.degrees(model_angle_x):.1f}  Y={math.degrees(model_angle_y):.1f}  自动={'开' if auto_spin else '关'}", PANEL_TEXT),
        ("row", f"光源: ({lx:.2f}, {ly:.2f}, {lz:.2f})", PANEL_TEXT),
        ("header", "控制", None),
        ("row", "左拖=物体  拖黄点=光源", PANEL_TEXT),
        ("row", "右拖/方向键=视角  滚轮=远近", PANEL_TEXT),
        ("row", "WASD/QE=漫游  J/L/U/O/I/K=移光", PANEL_TEXT),
        ("row", "M: 模式  Z-buffer: 开/关", PANEL_TEXT),
        ("row", "空格: 自动旋转  R: 重置", PANEL_DIM),
    ]


def draw_panel(screen, font, font_small, camera, auto_spin,
               tri_count, vertex_count, model_angle_x, model_angle_y,
               light_position, render_mode, use_z_buffer):
    pygame.draw.rect(screen, PANEL_BG, (0, 0, PANEL_WIDTH, WINDOW_HEIGHT))
    pygame.draw.rect(screen, PANEL_SEP,
                     (PANEL_WIDTH - 1, 0, 1, WINDOW_HEIGHT))

    items = build_panel_items(
        camera, auto_spin, tri_count, vertex_count,
        model_angle_x, model_angle_y, light_position, render_mode,
        use_z_buffer)
    x = 12
    y = 10
    header_h = 16
    line_h = 14

    def header(text):
        nonlocal y
        if y > 18:
            y += 2
            pygame.draw.rect(screen, PANEL_SEP,
                              (x, y, PANEL_WIDTH - 2 * x, 1))
            y += 4
        surf = font.render(text, True, PANEL_HEADER)
        screen.blit(surf, (x, y))
        y += header_h

    def row(text, color=PANEL_TEXT):
        nonlocal y
        surf = font_small.render(text, True, color)
        screen.blit(surf, (x + 4, y))
        y += line_h

    for kind, text, color in items:
        if kind == "header":
            header(text)
        else:
            row(text, color)


def draw_hud(screen, font):
    lines = [
        "左拖房子=旋转 | 左拖黄点=移动光源 | 右拖/方向键=观察方向 | 滚轮=拉近/拉远",
        "WASD/QE=漫游 | J/L/U/O/I/K=键盘移光 | M=模式 | Z=Z-buffer | R=重置",
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
    light_position = LIGHT_POSITION
    render_mode = "solid_wireframe"
    use_z_buffer = True
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
                    light_position = LIGHT_POSITION
                    render_mode = "solid_wireframe"
                    use_z_buffer = True
                    dirty = True
                elif event.key == pygame.K_SPACE:
                    auto_spin = not auto_spin
                    dirty = True
                elif event.key == pygame.K_m:
                    idx = RENDER_MODES.index(render_mode)
                    render_mode = RENDER_MODES[(idx + 1) % len(RENDER_MODES)]
                    dirty = True
                elif event.key == pygame.K_z:
                    use_z_buffer = not use_z_buffer
                    dirty = True

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if is_near_projected_light(
                        event.pos, camera, light_position, CANVAS_WIDTH,
                        WINDOW_HEIGHT, FOCAL_LENGTH):
                    dragging = "LIGHT"
                else:
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
                elif dragging == "LIGHT":
                    light_position = move_light_by_mouse_drag(
                        light_position, camera, dx, dy)
                else:
                    camera.yaw += dx * 0.006
                    camera.pitch -= dy * 0.006
                    camera.pitch = max(-1.2, min(1.2, camera.pitch))
                last_mouse = event.pos
                dirty = True

            elif event.type == pygame.MOUSEWHEEL:
                dolly_camera(camera, event.y * 0.45)
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
        if keys[pygame.K_j]:
            light_position = move_light(light_position, -move_speed, 0, 0)
            dirty = True
        if keys[pygame.K_l]:
            light_position = move_light(light_position, move_speed, 0, 0)
            dirty = True
        if keys[pygame.K_u]:
            light_position = move_light(light_position, 0, move_speed, 0)
            dirty = True
        if keys[pygame.K_o]:
            light_position = move_light(light_position, 0, -move_speed, 0)
            dirty = True
        if keys[pygame.K_i]:
            light_position = move_light(light_position, 0, 0, -move_speed)
            dirty = True
        if keys[pygame.K_k]:
            light_position = move_light(light_position, 0, 0, move_speed)
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
            CANVAS_WIDTH, WINDOW_HEIGHT, FOCAL_LENGTH,
            light_pos=light_position, use_z_buffer=use_z_buffer,
            render_mode=render_mode)
        target = model_center(world_vertices)
        ground_y = min(point[1] for point in world_vertices) - 0.02

        screen.fill(BG_COLOR)
        draw_floor_grid(screen, camera, world_vertices)
        draw_pixels(screen, pixels)
        draw_light_gizmo(screen, camera, light_position, target, ground_y)
        draw_light_marker(screen, camera, light_position)
        draw_hud(screen, font)
        draw_panel(screen, font, font_small, camera, auto_spin,
                   tri_count, vertex_count, model_angle_x, model_angle_y,
                   light_position, render_mode, use_z_buffer)

        pygame.display.flip()
        dirty = False


if __name__ == "__main__":
    main()
