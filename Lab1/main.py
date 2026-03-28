import pygame
import sys
import math
from algorithms import bresenham_line, midpoint_circle

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
GRID_SIZE = 10  

BG_COLOR = (255, 255, 255)
GRID_COLOR = (220, 220, 220)
LINE_COLOR = (0, 0, 0)
TEMP_COLOR = (255, 0, 0)
TEXT_COLOR = (0, 100, 255)
REPLAY_COLOR = (255, 165, 0) # 回放时的颜色 (橙色)

def physical_to_logical(pos):
    # 将物理坐标转换为逻辑坐标（网格坐标）
    # 例如，在800*600的窗口中，GRID_SIZE为10，那么坐标(245, 135)会被转换为(24, 13)
    return pos[0] // GRID_SIZE, pos[1] // GRID_SIZE

def draw_grid(screen):
    # 画所有的网格线
    for x in range(0, WINDOW_WIDTH, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, WINDOW_HEIGHT))
    for y in range(0, WINDOW_HEIGHT, GRID_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (0, y), (WINDOW_WIDTH, y))

def draw_logical_pixels(screen, points, color):
    # 根据逻辑坐标列表绘制像素点
    for x, y in points:
        rect_x = x * GRID_SIZE
        rect_y = y * GRID_SIZE
        # 画一个填充的矩形来表示这个像素点（x, y, w, h)
        pygame.draw.rect(screen, color, (rect_x, rect_y, GRID_SIZE, GRID_SIZE))

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Lab1: 直线与圆 (含日志与回放)")
    
    font = pygame.font.Font(None, 24) 

    is_drawing = False
    start_logical_pos = None
    current_logical_pos = (0, 0)
    current_shape = 'LINE' 
    finished_shapes = [] 
    
    # --- 回放相关的状态变量 ---
    is_replaying = False
    replay_timeline = []      # 存放所有需要回放的像素点
    current_replay_index = 0  # 当前回放到的进度
    REPLAY_SPEED = 1          # 每次刷新绘制的点数（控制播放速度）

    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_l and not is_replaying:
                    current_shape = 'LINE'
                elif event.key == pygame.K_c and not is_replaying:
                    current_shape = 'CIRCLE'
                # 按下 R 键触发回放 (Replay)
                elif event.key == pygame.K_r and not is_drawing and finished_shapes:
                    is_replaying = True
                    current_replay_index = 0
                    replay_timeline = []
                    # 摊平所有图形的点，组成一条时间线
                    for shape in finished_shapes:
                        replay_timeline.extend(shape["points"])
                    print("\n>>> 开始动态回放...")

            elif event.type == pygame.MOUSEMOTION:
                current_logical_pos = physical_to_logical(event.pos)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # 回放时禁止绘画
                if not is_replaying:
                    is_drawing = True
                    start_logical_pos = physical_to_logical(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if is_drawing:
                    is_drawing = False
                    
                    # 松开鼠标时，传入 print_log=True，在终端打印计算表格 (满足选做1和2)
                    if current_shape == 'LINE':
                        pts = bresenham_line(start_logical_pos[0], start_logical_pos[1], 
                                             current_logical_pos[0], current_logical_pos[1], print_log=True)
                    else:
                        dx = current_logical_pos[0] - start_logical_pos[0]
                        dy = current_logical_pos[1] - start_logical_pos[1]
                        radius = int(math.sqrt(dx**2 + dy**2))
                        pts = midpoint_circle(start_logical_pos[0], start_logical_pos[1], radius, print_log=True)
                        
                    finished_shapes.append({"type": current_shape, "points": pts})

        # --- 渲染阶段 ---
        screen.fill(BG_COLOR)
        draw_grid(screen)

        if is_replaying:
            # 回放模式：只画到当前进度的点
            points_to_draw = replay_timeline[:current_replay_index]
            draw_logical_pixels(screen, points_to_draw, REPLAY_COLOR)
            
            # 推进播放进度
            current_replay_index += REPLAY_SPEED
            if current_replay_index >= len(replay_timeline):
                current_replay_index = len(replay_timeline)
                is_replaying = False # 播放结束
                print(">>> 回放结束。")
        else:
            # 正常模式：绘制所有已完成的图形
            for shape in finished_shapes:
                draw_logical_pixels(screen, shape["points"], LINE_COLOR)

            # 绘制橡皮筋
            if is_drawing and start_logical_pos:
                if current_shape == 'LINE':
                    temp_pts = bresenham_line(start_logical_pos[0], start_logical_pos[1], 
                                              current_logical_pos[0], current_logical_pos[1], print_log=False)
                else:
                    dx = current_logical_pos[0] - start_logical_pos[0]
                    dy = current_logical_pos[1] - start_logical_pos[1]
                    radius = int(math.sqrt(dx**2 + dy**2))
                    temp_pts = midpoint_circle(start_logical_pos[0], start_logical_pos[1], radius, print_log=False)
                
                draw_logical_pixels(screen, temp_pts, TEMP_COLOR)

        # 绘制 UI
        mode_str = "REPLAYING..." if is_replaying else current_shape
        tips = "Keys: 'L'=Line, 'C'=Circle, 'R'=Replay"
        coord_text = f"Mode: {mode_str} | Pos: {current_logical_pos} | {tips}"
        
        coord_surface = font.render(coord_text, True, TEXT_COLOR)
        screen.blit(coord_surface, (10, 10))

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()