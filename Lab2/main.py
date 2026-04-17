import sys
import pygame
from algorithms import build_polygon_edges, scanline_seed_fill, point_in_polygon

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
GRID_SIZE = 10

BG_COLOR = (255, 255, 255)
GRID_COLOR = (220, 220, 220)
EDGE_COLOR = (0, 0, 0)
TEMP_COLOR = (255, 0, 0)
TEXT_COLOR = (0, 100, 255)
VERTEX_COLOR = (0, 120, 0)

FILL_COLORS = [
    ("Orange", (255, 140, 0)),
    ("Blue",   (66, 133, 244)),
    ("Green",  (15, 157, 88)),
    ("Red",    (219, 68, 55)),
]


def physical_to_logical(pos):
    return pos[0] // GRID_SIZE, pos[1] // GRID_SIZE


def draw_grid(screen):
    for x in range(0, WINDOW_WIDTH, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, WINDOW_HEIGHT))
    for y in range(0, WINDOW_HEIGHT, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (0, y), (WINDOW_WIDTH, y))


def draw_pixels(screen, points, color):
    for x, y in points:
        pygame.draw.rect(screen, color, (x * GRID_SIZE, y * GRID_SIZE, GRID_SIZE, GRID_SIZE))


def draw_hud(screen, font, lines):
    h = 8 + 22 * len(lines)
    pygame.draw.rect(screen, BG_COLOR, (0, 0, WINDOW_WIDTH, h))
    for i, line in enumerate(lines):
        surface = font.render(line, True, TEXT_COLOR)
        screen.blit(surface, (10, 4 + i * 22))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Lab2: 扫描线种子填充")
    font = pygame.font.Font("C:/Windows/Fonts/msyh.ttc", 16)
    clock = pygame.time.Clock()

    mouse_pos = (0, 0)

    # 三个阶段: DRAW → SEED → FILLING → 回到 DRAW
    #   DRAW:    点击放置顶点，Enter 闭合多边形
    #   SEED:    点击选择种子点
    #   FILLING: 动画播放填充过程
    draft_vertices = []       # DRAW 阶段的顶点
    polygon_vertices = None   # 闭合后的顶点
    polygon_edges = []        # 闭合后的边界像素
    edge_set = set()
    fill_points = []          # 填充顺序
    filling = False
    fill_index = 0
    fill_speed = 3

    finished = []             # 已完成的多边形
    color_index = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEMOTION:
                mouse_pos = physical_to_logical(event.pos)

            elif event.type == pygame.KEYDOWN:
                can_draw = not filling and polygon_vertices is None

                if event.key == pygame.K_RETURN and can_draw and len(draft_vertices) >= 3:
                    polygon_vertices = draft_vertices[:]
                    polygon_edges = build_polygon_edges(polygon_vertices, print_log=True)
                    edge_set = set(polygon_edges)
                    draft_vertices = []

                elif event.key == pygame.K_BACKSPACE and can_draw and draft_vertices:
                    draft_vertices.pop()

                elif event.key == pygame.K_ESCAPE and can_draw:
                    draft_vertices = []

                elif event.key == pygame.K_c and not filling:
                    color_index = (color_index + 1) % len(FILL_COLORS)

                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4) and not filling:
                    color_index = event.key - pygame.K_1

                elif event.key == pygame.K_UP:
                    fill_speed = min(30, fill_speed + 1)
                elif event.key == pygame.K_DOWN:
                    fill_speed = max(1, fill_speed - 1)

                elif event.key == pygame.K_r and not filling:
                    draft_vertices = []
                    polygon_vertices = None
                    polygon_edges = []
                    edge_set = set()
                    fill_points = []
                    finished = []

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not filling and polygon_vertices is None:
                    # DRAW: 添加顶点
                    draft_vertices.append(physical_to_logical(event.pos))

                elif not filling and polygon_vertices is not None:
                    # SEED: 选择种子点
                    seed = physical_to_logical(event.pos)
                    inside = point_in_polygon(seed[0] + 0.5, seed[1] + 0.5, polygon_vertices)

                    if inside and seed not in edge_set:
                        fill_points = scanline_seed_fill(polygon_vertices, seed, print_log=True)
                        filling = True
                        fill_index = 0
                    else:
                        print(">>> 种子点无效，请点击多边形内部。")

        # 动画推进
        if filling:
            fill_index += fill_speed
            if fill_index >= len(fill_points):
                fill_index = len(fill_points)
                filling = False
                _, color = FILL_COLORS[color_index]
                finished.append({
                    "edges": polygon_edges,
                    "fill": fill_points,
                    "color": color,
                })
                polygon_vertices = None
                polygon_edges = []
                edge_set = set()
                fill_points = []

        # 渲染
        screen.fill(BG_COLOR)
        draw_grid(screen)

        for poly in finished:
            draw_pixels(screen, poly["fill"], poly["color"])
            draw_pixels(screen, poly["edges"], EDGE_COLOR)

        if draft_vertices:
            draw_pixels(screen, draft_vertices, VERTEX_COLOR)
            if len(draft_vertices) >= 2:
                preview = build_polygon_edges(draft_vertices, print_log=False)
                draw_pixels(screen, preview, TEMP_COLOR)
            last = draft_vertices[-1]
            from algorithms import midpoint_line
            rubber = midpoint_line(last[0], last[1], mouse_pos[0], mouse_pos[1])
            draw_pixels(screen, rubber, TEMP_COLOR)

        if polygon_vertices is not None:
            _, c = FILL_COLORS[color_index]
            draw_pixels(screen, polygon_edges, EDGE_COLOR)
            draw_pixels(screen, fill_points[:fill_index], c)

        mode = "填充中" if filling else ("选种子" if polygon_vertices else "画多边形")
        cname, _ = FILL_COLORS[color_index]
        draw_hud(screen, font, [
            f"模式:{mode}  坐标:{mouse_pos}  速度:{fill_speed}  颜色:{cname}",
            "左键=加点/选种子  Enter=闭合  1-4=颜色  C=换色  上下=速度  R=重置",
        ])

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
