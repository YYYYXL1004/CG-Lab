# VectorFlow — 矢量流程图编辑系统 设计文档

> 课程大作业：计算机图形学 · 矢量图形编辑系统
> 实用定位：**流程图 / 组织结构图 / 电路图绘制工具**

---

## 一、项目概述

### 1.1 项目定位

VectorFlow 是一个矢量图形编辑器，支持流程图、组织结构图、电路图等多类图元绘制。核心卖点：画布区域内所有图元（直线、圆、椭圆、矩形、曲线、流程图图元、电路图符号）的绘制完全由自研像素级算法完成——不调用 `Canvas.create_line` / `create_rectangle` 等系统绘图函数。

UI 控件（菜单、工具栏、属性面板）使用 tkinter 标准组件——课程要求"减少系统绘图函数"针对的是图形绘制区域，不是按钮和菜单。

### 1.2 已实现功能

| # | 课设要求 | 实现方式 |
|---|---------|---------|
| 1 | 选择、移动、复制、粘贴、删除 | 点击/框选 + 拖拽移动 + Ctrl+C/V/Delete |
| 2 | 几何变换：平移、旋转、缩放、对称 | 任意角度旋转、任意比例缩放、水平/垂直翻转，基于齐次坐标矩阵 |
| 3 | 自定义数据结构，永久保存 | Shape 类层次 + `.vflow` JSON 文件 |
| 4 | 重新加载并继续编辑 | 打开 .vflow → 反序列化 → 可继续编辑 |
| 5 | 较复杂的自定义图元 | 流程图 7 种 + 通用图形 7 种 + 电路图 8 种 + 连接线 |

### 1.3 亮点功能

| 亮点 | 说明 |
|------|------|
| 暗色主题 | 区别于传统课设的视觉风格 |
| 磁吸锚点 | 连接线自动吸附图元四周锚点 |
| 撤销 | 全量状态快照，History 模式 |
| 导出 PNG | 全画布导出 + 矩形区域导出 |
| Wu 反走样 | 高质量直线渲染 |
| 画布平移缩放 | 鼠标滚轮缩放（以鼠标为中心）+ 中键/空格键拖拽平移 |
| 智能磁吸对齐 | 拖动图形时自动显示红色辅助线并吸附对齐 |
| 多图元库 | 分标签页：流程图 / 通用图形 / 电路图 |
| 拖拽连接线 | 从起点图元拖拽至终点图元创建连接 |
| 三种连接线 | 直线 / 正交折线 / 贝塞尔曲线 |
| 动态连接线 | 沿连接线路径显示流动高亮像素，可表达流程方向或电路电流 |
| 算法回放模式 | 选中图形后逐帧展示 Bresenham、中点圆/椭圆、扫描线填充等像素生成过程 |
| 多种箭头样式 | 实心箭头、空心箭头、菱形、圆点，起点/终点独立设置 |
| 内联文本编辑 | 画布上直接输入多行文本，支持对齐/加粗/颜色 |
| 任意变换 | 旋转角度 -360°~360°、缩放比例 10%~500% |

### 1.4 技术栈

| 组件 | 技术选型 | 理由 |
|------|---------|------|
| 语言 | Python 3.10+ | 课程语言 |
| GUI 框架 | tkinter (内置) | 零额外安装 |
| 像素缓冲 | Pillow (PIL) | `Image` 做像素缓冲区，`ImageTk` 显示到画布 |
| 数据持久化 | json (内置) | 人类可读 |

> **不引入 numpy**——矩阵运算量很小（3×3 矩阵乘法），纯 Python 列表足够，减少依赖。

---

## 二、系统架构

### 2.1 分层架构

```
┌─────────────────────────────────────────────┐
│            UI 层 (tkinter 标准控件)           │
│  菜单栏 │ 工具栏 │ 弹窗对话框 │ 图元库 │ 状态栏│
├─────────────────────────────────────────────┤
│              交互层                           │
│  工具状态机 │ 选择管理 │ 拖拽控制 │ 快捷键     │
│  磁吸对齐辅助线 │ 无限画布平移/缩放             │
├─────────────────────────────────────────────┤
│              业务层                           │
│  文档模型 │ 变换引擎 │ 撤销 │ 剪贴板           │
├─────────────────────────────────────────────┤
│              渲染层                           │
│  Pillow Image 像素缓冲区 → ImageTk 显示      │
├─────────────────────────────────────────────┤
│           算法层（全部自研）                    │
│  Bresenham 直线 │ 中点圆 │ 中点椭圆           │
│  Bézier 曲线 │ 扫描线填充 │ Cohen-Sutherland  │
│  Wu 反走样 │ 齐次坐标变换 │ 虚线模式          │
└─────────────────────────────────────────────┘
```

**关键渲染流程**：

```
1. 创建 Pillow Image 作为后缓冲区（RGBA 模式）
2. 遍历所有图形，按 z_order 排序
3. 每个图形调用自研算法 → 返回像素点列表 [(x, y), ...]
4. 将像素写入 Pillow Image
5. 转换为 ImageTk.PhotoImage
6. 显示到 tkinter Canvas 上
拖拽过程中：跳过填充 → 释放鼠标后全质量重绘
```

### 2.2 目录结构

```
FinalProject/
├── docs/
│   ├── plan.md              # 本文件：设计文档
│   └── usage.md             # 使用说明
│
├── src/
│   ├── main.py              # 程序入口
│   ├── app.py               # 主窗口：UI 搭建、交互逻辑、事件处理
│   │
│   ├── algorithms/          # 【算法层】全部自研，不依赖任何绘图 API
│   │   ├── line.py          # Bresenham 直线 + DDA 直线 + 虚线模式
│   │   ├── circle.py        # 中点圆算法（八分对称）
│   │   ├── ellipse.py       # 中点椭圆算法
│   │   ├── bezier.py        # de Casteljau 三次 Bézier 曲线
│   │   ├── fill.py          # 扫描线多边形填充（活性边表 AET）
│   │   ├── clip.py          # Cohen-Sutherland 直线裁剪
│   │   ├── antialias.py     # Wu 反走样直线
│   │   └── transform.py     # 3×3 齐次坐标变换（纯 Python，不用 numpy）
│   │
│   ├── core/                # 【业务层】数据模型
│   │   ├── shapes.py        # FlowchartShape / LineShape / TextShape / ConnectorShape
│   │   ├── style.py         # ShapeStyle 样式类（描边/填充/文本样式）
│   │   └── document.py      # Document 文档模型（图形列表、连接线、画布设置）
│   │
│   ├── engine/              # 【渲染层 + 交互辅助】
│   │   ├── renderer.py      # 渲染引擎：调用算法层 → 写入 Pillow Image
│   │   ├── animation.py     # 动态连接线：路径采样 + 相位高亮像素
│   │   ├── algorithm_replay.py # 算法回放：图元 → 累计像素帧
│   │   ├── selection.py     # 选择管理：点选/框选/多选
│   │   ├── guides.py        # 磁吸对齐辅助线计算
│   │   └── command.py       # History：全量状态快照式撤销
│   │
│   └── io_utils/            # 【持久化】
│       └── serializer.py    # .vflow JSON 序列化/反序列化
│
├── tests/
│   ├── test_algorithms.py   # 算法层测试
│   ├── test_animation_replay.py # 动态连接线与算法回放测试
│   ├── test_document.py     # 文档模型测试
│   ├── test_renderer_command.py  # 渲染与撤销测试
│   └── test_selection.py    # 选择管理测试
│
├── requirements.txt         # 仅 Pillow
└── README.md
```

---

## 三、自研绘图算法清单

> **所有图形绘制完全由以下自研算法完成，不调用任何系统绘图函数。**

### 3.1 直线

| 算法 | 函数签名 | 说明 |
|------|---------|------|
| Bresenham | `bresenham_line(x0, y0, x1, y1) → [(x,y), ...]` | 纯整数运算，默认使用 |
| DDA | `dda_line(x0, y0, x1, y1) → [(x,y), ...]` | 浮点运算，作为对比 |
| 虚线 | `dashed_line(x0, y0, x1, y1, pattern) → [(x,y), ...]` | 在 Bresenham 基础上按 pattern 跳过像素 |

### 3.2 圆

| 算法 | 函数签名 | 说明 |
|------|---------|------|
| 中点圆 | `midpoint_circle(cx, cy, r) → [(x,y), ...]` | 八分对称性 |

### 3.3 椭圆

| 算法 | 函数签名 | 说明 |
|------|---------|------|
| 中点椭圆 | `midpoint_ellipse(cx, cy, rx, ry) → [(x,y), ...]` | 分区域一/区域二决策 |

### 3.4 Bézier 曲线

| 算法 | 函数签名 | 说明 |
|------|---------|------|
| 三次 Bézier | `cubic_bezier(p0, p1, p2, p3, steps) → [(x,y), ...]` | de Casteljau 递归细分 |

### 3.5 填充

| 算法 | 函数签名 | 说明 |
|------|---------|------|
| 扫描线填充 | `scanline_fill(vertices) → [(x,y), ...]` | 活性边表(AET)，用于所有封闭图元 |

### 3.6 裁剪

| 算法 | 函数签名 | 说明 |
|------|---------|------|
| Cohen-Sutherland | `cohen_sutherland_clip(x0, y0, x1, y1, xmin, ymin, xmax, ymax) → tuple or None` | 直线裁剪 |

### 3.7 反走样

| 算法 | 函数签名 | 说明 |
|------|---------|------|
| Wu 反走样 | `wu_line(x0, y0, x1, y1) → [(x, y, alpha), ...]` | 返回带透明度的像素 |

### 3.8 几何变换

3×3 齐次坐标矩阵，纯 Python 实现（`Matrix3` 类）：

- `Matrix3.translation(tx, ty)` — 平移
- `Matrix3.rotation(angle, center)` — 任意中心点旋转
- `Matrix3.scaling(sx, sy, center)` — 任意中心点缩放
- `Matrix3.reflection(horizontal, vertical, center)` — 对称翻转
- `Matrix3.__matmul__` — 矩阵乘法
- `Matrix3.apply(point)` — 变换单个点

### 3.9 算法与图元的对应关系

| 图元 | 描边算法 | 填充算法 |
|------|---------|---------|
| **处理框**（矩形） | Bresenham 直线 × 4 | 扫描线填充 |
| **判断框**（菱形） | Bresenham 直线 × 4 | 扫描线填充 |
| **起止框**（椭圆近似） | 48段多边形 | 扫描线填充 |
| **数据框**（平行四边形） | Bresenham 直线 × 4 | 扫描线填充 |
| **文档框**（波浪底矩形） | Bresenham 直线 + 正弦波 | 扫描线填充 |
| **数据库**（圆柱体） | 中点椭圆 × 2 + Bresenham 直线 × 2 | 扫描线填充 |
| **子程序框** | Bresenham 直线 × 6 | 扫描线填充 |
| **圆 / 椭圆** | 48段多边形 → Bresenham | 扫描线填充 |
| **五角星** | 10顶点多边形 → Bresenham | 扫描线填充 |
| **六边形** | 6顶点多边形 → Bresenham | 扫描线填充 |
| **电路图符号** | extra_segments 线段 → Bresenham | 无填充（线稿） |
| **连接线** | Bresenham 直线 / 正交折线 / Bézier 曲线 | 无 |
| **箭头** | 实心三角 / 空心三角 / 菱形 / 圆点 | 扫描线填充 / 中点圆 |

### 3.10 算法回放与动态像素效果

算法回放不单独调用系统绘图 API，而是复用算法层返回的像素点：
- 直线：Bresenham 像素点按时间累计显示
- 圆 / 椭圆：中点圆或中点椭圆算法点逐帧显示
- 多边形图元：Bresenham 轮廓点 + 扫描线填充点分阶段显示
- 连接线流动：先把连接线路径采样为 Bresenham 像素序列，再按相位偏移选出一组高亮像素

---

## 四、图形数据结构

### 4.1 Shape 类型

使用 Python `dataclass` 定义，`Shape` 是联合类型：

```python
Shape = FlowchartShape | LineShape | TextShape
```

### 4.2 FlowchartShape — kind 完整列表

**流程图：**
- `process` — 处理框（矩形）
- `decision` — 判断框（菱形）
- `terminal` — 起止框（椭圆）
- `data` — 数据框（平行四边形）
- `document` — 文档框（波浪底矩形）
- `database` — 数据库（圆柱体）
- `subprocess` — 子程序框（内双竖线矩形）

**通用图形：**
- `circle` — 圆（48段多边形）
- `ellipse` — 椭圆（48段多边形）
- `star5` — 正五角星（10顶点交替内外径）
- `hexagon` — 正六边形
- `arrow_right` — 右箭头（7顶点多边形）
- `cloud` — 云形（5段圆弧近似）
- `org_box` — 圆角矩形（组织结构图节点）

**电路图符号（外观在 extra_segments 中）：**
- `resistor` — 电阻（矩形体 + 两侧引线）
- `capacitor` — 电容（平行竖线 + 两侧引线）
- `ground` — 接地（三条递减横线 + 竖线）
- `battery` — 电源（长短交替竖线 + 引线）
- `switch` — 开关（斜臂 + 端点）
- `led` — LED（三角体 + 阴极竖线 + 发光箭头）
- `inductor` — 电感（线圈圆弧 + 引线）
- `voltage_source` — 电压源（圆 + 正负极标注）

### 4.3 ConnectorShape

```python
@dataclass
class ConnectorShape:
    start_shape_id: str
    end_shape_id: str
    start_anchor: str = "right"      # "top" / "bottom" / "left" / "right"
    end_anchor: str = "left"
    kind: str = "elbow"              # "straight" / "elbow" / "bezier"
    arrow_end: str = "arrow"         # "arrow" / "open_arrow" / "diamond" / "dot" / "none"
    arrow_start: str = "none"
    style: ShapeStyle
```

### 4.4 ShapeStyle

```python
@dataclass
class ShapeStyle:
    stroke: Color = "#6080A0"
    fill: Color = "#283850"
    stroke_width: int = 2
    dash: list[int] = []             # 空=实线，[6,3]=虚线，[2,4]=点线
    font_size: int = 14
    text_color: Color = "#D0D0E0"
    text_align: str = "center"       # "center" / "left" / "right"
    bold: bool = False
```

### 4.5 Document

```python
@dataclass
class Document:
    title: str
    canvas_width: int
    canvas_height: int
    background: str
    grid_size: int
    snap_enabled: bool
    shapes: list[Shape]
    connectors: list[ConnectorShape]
```

---

## 五、撤销

采用**全量状态快照**模式（History 类）：

```python
class History:
    _states: list[dict]   # 每个状态是 document.to_dict() 的完整快照
    _index: int           # 当前状态指针

    push(state)           # 保存新状态（自动去重、截断 redo 栈）
    undo(document) → bool # 回退到上一状态
    can_undo: bool
```

每次编辑操作后调用 `history.push(document.to_dict())` 保存快照。撤销通过 `document.replace_from_dict()` 恢复完整文档状态。

---

## 六、UI 界面

### 6.1 布局

```
┌───────────────────────────────────────────────────────┐
│ 菜单栏：文件(F) │ 编辑(E) │ 视图(V)                    │
├──────┬─────────────────────────────────────────────────┤
│      │  工具栏：选择 直线 文本 连接线 区域导出 撤销 算法回放 清屏 │
│ 图   │  图形样式… 连接线… 文本样式… 变换… | 网格 流动线 | 保存 │
│ 元   ├─────────────────────────────────────────────────┤
│ 库   │                                                 │
│      │       画 布 (Pillow → ImageTk)                  │
│[流程图│         暗色背景 + 网格                          │
│ 通用  │                                                 │
│ 电路] │                                                 │
├──────┴─────────────────────────────────────────────────┤
│ 状态栏：工具 │ 坐标 │ 缩放 │ 图形数量 │ 可撤销           │
└───────────────────────────────────────────────────────┘
```

### 6.2 配色（暗色主题）

| 元素 | Hex |
|------|-----|
| 画布背景 | `#1E1E2E` |
| 网格线 | `#2A2A3E` |
| 面板背景 | `#252535` |
| 工具栏背景 | `#2D2D40` |
| 主强调色 | `#4690E0` |
| 选中高亮 | `#5BA8FF` |
| 对齐辅助线 | `#FF4444`（红色） |
| 普通文本 | `#D0D0E0` |
| 图元描边 | `#6080A0` |
| 图元填充 | `#283850` |

### 6.3 交互方式

| 操作 | 方式 |
|------|------|
| 放置图元 | 左侧图元库（3标签页）点击 → 画布上点击放置 |
| 连接两个图元 | 连接线工具 → 从起点图元拖拽到终点图元 |
| 动态连接线 | 顶部"流动线"开关控制连接线流动高亮 |
| 算法回放 | 选中图形 → 点击"算法回放"按钮，自动播放像素生成过程 |
| 选择图形 | 选择工具 → 点击图形 / 空白处拖拽框选 |
| 移动图形 | 选中后拖拽（自动显示磁吸对齐线） |
| 旋转/缩放 | 工具栏"变换…"弹窗 |
| 编辑文本 | 双击图形 → 内联编辑框 → Ctrl+Enter 确认 |
| 平移画布 | 中键拖拽 / 空格键 + 左键拖拽 |
| 缩放画布 | 鼠标滚轮（以鼠标位置为中心） |
| 区域导出 | 区域导出工具 → 拖拽矩形 → 保存 PNG |

---

## 七、快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+N` | 新建 |
| `Ctrl+O` | 打开 |
| `Ctrl+S` | 保存 |
| `Ctrl+Shift+S` | 另存为 |
| `Ctrl+Z` | 撤销 |
| `Ctrl+C` | 复制 |
| `Ctrl+V` | 粘贴 |
| `Delete` | 删除 |
| `Ctrl+E` | 导出 PNG |
| `Esc` | 取消当前操作 |
| `V` | 选择工具 |
| `L` | 直线工具 |
| `T` | 文本工具 |
| `K` | 连接线工具 |
| `Space + 拖拽` | 平移画布 |
| `滚轮` | 缩放画布 |

---

## 八、文件格式

**`.vflow`（JSON）**

```json
{
  "version": "1.0",
  "metadata": { "title": "流程图标题" },
  "canvas": {
    "width": 2400,
    "height": 1600,
    "background": "#1E1E2E",
    "grid_size": 20,
    "snap_enabled": true
  },
  "shapes": [
    {
      "id": "shape_a1b2c3",
      "type": "flowchart",
      "kind": "process",
      "x": 100, "y": 80,
      "width": 140, "height": 70,
      "text": "开始处理",
      "style": { "stroke": "#6080A0", "fill": "#283850" },
      "z_order": 0,
      "rotation": 0,
      "flip_x": false, "flip_y": false
    }
  ],
  "connectors": [
    {
      "id": "conn_x4y5z6",
      "type": "connector",
      "start_shape_id": "shape_a1b2c3",
      "end_shape_id": "shape_d4e5f6",
      "start_anchor": "bottom",
      "end_anchor": "top",
      "kind": "elbow",
      "arrow_end": "arrow",
      "arrow_start": "none",
      "style": { "stroke": "#A7C7FF" }
    }
  ]
}
```

---

## 九、功能扩展计划

### 阶段一：扩充图形库 ✅（已完成）

在 `core/shapes.py` 的 `outline_points()` 中添加新图形分支，`extra_segments()` 中添加电路图符号线段。左侧库面板改为 `ttk.Notebook` 三标签页。

### 阶段二：智能磁吸与对齐辅助线

**新文件** `src/engine/guides.py`：

```python
def compute_guides(
    dragging_ids: set[str],
    all_shapes: list[Shape],
    snap_threshold: float = 8.0,
) -> tuple[list[tuple[str, float]], float, float]:
    """
    返回：
      guides  — [("hline", y), ("vline", x), ...]  红色辅助线
      snap_dx — X 方向磁吸偏移量
      snap_dy — Y 方向磁吸偏移量
    """
```

逻辑：
1. 收集所有非拖动图形的 bounds → 提取 left/center_x/right, top/center_y/bottom
2. 收集拖动图形的相同6个坐标
3. 差值 < snap_threshold → 产生辅助线 + snap 偏移

**修改** `app.py`：
- `on_mouse_move` 移动拖拽分支中调用 `compute_guides()`，将 snap delta 加到移动量
- `self._guides` 列表存储当前辅助线，拖拽结束时清空

**修改** `engine/renderer.py`：
- `render()` 增加 `guides` 参数，红色画水平/垂直辅助线

### 阶段三：无限画布（滚轮缩放 + 空格平移）

当前已有 `self.zoom` / `self.pan` / `screen_to_world` / `world_to_screen`，需补充：

**滚轮缩放**（已有 `on_mouse_wheel`，需完善以鼠标为中心缩放）：
```python
def on_mouse_wheel(self, event):
    factor = 1.1 if event.delta > 0 else 1 / 1.1
    cx, cy = event.x, event.y
    self.pan = (cx - (cx - self.pan[0]) * factor,
                cy - (cy - self.pan[1]) * factor)
    self.zoom = max(0.1, min(8.0, self.zoom * factor))
    self.redraw()
```

**空格键平移**：
```python
self._space_held = False
self._pan_start = None
self._pan_origin = None

def on_space_down(self, event): self._space_held = True; self.canvas.config(cursor="fleur")
def on_space_up(self, event):   self._space_held = False; self.canvas.config(cursor="crosshair")

# on_left_down 开头：
if self._space_held:
    self._pan_start = (event.x, event.y)
    self._pan_origin = self.pan
    return

# on_mouse_move 开头：
if self._space_held and self._pan_start:
    dx = event.x - self._pan_start[0]
    dy = event.y - self._pan_start[1]
    self.pan = (self._pan_origin[0] + dx, self._pan_origin[1] + dy)
    self.redraw(draft=True)
    return
```

---

## 十、依赖

```
# requirements.txt
Pillow>=10.0.0
```

仅一个外部依赖。tkinter / json / uuid 均为 Python 内置。

---

## 十一、交付物

1. `src/` — 完整源代码，`python src/main.py` 直接运行
2. `docs/plan.md` — 本设计文档
3. `docs/usage.md` — 使用说明
4. `tests/` — 单元测试
5. `requirements.txt` — 依赖清单
6. `README.md` — 项目说明
