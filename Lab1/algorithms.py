def bresenham_line(x0, y0, x1, y1, print_log=False):
    """
    通用 Bresenham 直线算法
    带有计算过程记录 (Logging) 功能
    """
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    
    step_x = 1 if x0 < x1 else -1
    step_y = 1 if y0 < y1 else -1
    
    err = dx - dy
    x, y = x0, y0
    
    if print_log:
        print(f"\n[{'Bresenham 直线'}] 起点:({x0},{y0}) -> 终点:({x1},{y1})")
        print(f"| {'步骤 (k)':<6} | {'当前坐标 (x, y)':<15} | {'决策变量 (err)':<14} | {'下一点选择策略 (Strategy)':<25} |")
        print("-" * 70)
        
    k = 0
    while True:
        points.append((x, y))
        
        if x == x1 and y == y1:
            if print_log:
                print(f"| {k:<8} | ({x:<3}, {y:<3}){'':<5} | {'到达终点, 结束':<14} | {'-':<25} |")
            break
            
        e2 = 2 * err
        strategy = []
        
        # 记录原始的 err 用于打印
        current_err = err 
        
        if e2 > -dy:
            err -= dy
            x += step_x
            strategy.append(f"x步进({'+1' if step_x>0 else '-1'})")
        if e2 < dx:
            err += dx
            y += step_y
            strategy.append(f"y步进({'+1' if step_y>0 else '-1'})")
            
        if print_log:
            strategy_str = ", ".join(strategy)
            print(f"| {k:<8} | ({x:<3}, {y:<3}){'':<5} | {current_err:<14} | {strategy_str:<25} |")
            
        k += 1
            
    return points


def midpoint_circle(xc, yc, radius, print_log=False):
    """
    中点画圆法 (Midpoint Circle Algorithm)
    带有计算过程记录 (Logging) 功能
    """
    # 这里我们不用 set 了，改用 list，为了在回放时能体现出生成顺序
    points = [] 
    
    x = 0
    y = radius
    d = 1 - radius 
    
    if print_log:
        print(f"\n[{'中点画圆法'}] 圆心:({xc},{yc}), 半径:{radius}")
        print(f"| {'当前基础点 (x, y)':<18} | {'判别式 (d)':<12} | {'下一点选择策略 (Strategy)':<25} |")
        print("-" * 65)

    def add_eight_points(cx, cy, x, y):
        # 依次加入8个对称点
        pts = [
            (cx + x, cy + y), (cx - x, cy + y),
            (cx + x, cy - y), (cx - x, cy - y),
            (cx + y, cy + x), (cx - y, cy + x),
            (cx + y, cy - x), (cx - y, cy - x)
        ]
        points.extend(pts)

    add_eight_points(xc, yc, x, y)
    
    while x < y:
        current_d = d
        if d < 0:
            d += 2 * x + 3
            strategy = "d<0: 选正右方点 (x+1, y)"
        else:
            d += 2 * (x - y) + 5
            y -= 1
            strategy = "d>=0: 选右下方点 (x+1, y-1)"
            
        if print_log:
            print(f"| ({x:<3}, {y:<3}){'':<8} | {current_d:<12} | {strategy:<25} |")
            
        x += 1
        add_eight_points(xc, yc, x, y)
        
    # 由于加入了许多重复点（特别是横竖轴上的点），这里简单去重但保留大致顺序
    unique_points = []
    for p in points:
        if p not in unique_points:
            unique_points.append(p)
            
    return unique_points