# VectorFlow — 矢量流程图编辑系统 设计文档

> 课程大作业：计算机图形学 · 矢量图形编辑系统
> 实用定位：**流程图绘制工具**

---

## 一、项目概述

### 1.1 项目定位

VectorFlow 是一个专注于**流程图绘制**的矢量图形编辑器。核心卖点：画布区域内所有图元（直线、圆、椭圆、矩形、曲线、流程图图元）的绘制完全由自研像素级算法完成——不调用 `Canvas.create_line` / `create_rectangle` 等系统绘图函数。

UI 控件（菜单、工具栏、属性面板）使用 tkinter 标准组件——课程要求"减少系统绘图函数"针对的是图形绘制区域，不是按钮和菜单。

### 1.2 已实现功能

| # | 课设要求 | 实现方式 |
|---|---------|---------|
| 1 | 选择、移动、复制、粘贴、删除 | 点击/框选 + 拖拽移动 + Ctrl+C/V/Delete |
| 2 | 几何变换：平移、旋转、缩放、对称 | 任意角度旋转、任意比例缩放、水平/垂直翻转，基于齐次坐标矩阵 |
| 3 | 自定义数据结构，永久保存 | Shape 类层次 + `.vflow` JSON 文件 |
| 4 | 重新加载并继续编辑 | 打开 .vflow → 反序列化 → 可继续编辑 |
| 5 | 较复杂的自定义图元 | 流程图：处理框/判断框/起止框/数据框/文档框/数据库/子程序框 + 连接线 |

### 1.3 亮点功能

| 亮点 | 说明 |
|------|------|
| 暗色主题 | 区别于传统课设的视觉风格 |
| 磁吸锚点 | 连接线自动吸附图元四周锚点 |
| 撤销/重做 | 全量状态快照，History 模式 |
| 导出 PNG | 全画布导出 + 矩形区域导出 |
| Wu 反走样 | 高质量直线渲染 |
| 画布平移缩放 | 鼠标滚轮缩放 + 中键拖拽平移 |
| 拖拽连接线 | 从起点图元拖拽至终点图元创建连接 |
| 三种连接线 | 直线 / 正交折线 / 贝塞尔曲线 |
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
│  菜单栏 │ 工具栏 │ 属性面板 │ 图元库 │ 状态栏  │
├─────────────────────────────────────────────┤
│              交互层                           │
│  工具状态机 │ 选择管理 │ 拖拽控制 │ 快捷键     │
├─────────────────────────────────────────────┤
│              业务层                           │
│  文档模型 │ 变换引擎 │ 撤销/重做 │ 剪贴板     │
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
│   │   ├── selection.py     # 选择管理：点选/框选/多选
│   │   └── command.py       # History：全量状态快照式撤销/重做
│   │
│   └── io_utils/            # 【持久化】
│       ├── serializer.py    # .vflow JSON 序列化/反序列化
│       └── exporter.py      # 导出 PNG
│
├── tests/
│   ├── test_algorithms.py   # 算法层测试
│   ├── test_document.py     # 文档模型测试
│   ├── test_renderer_command.py  # 渲染与撤销/重做测试
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
| **起止框**（椭圆近似） | Bresenham + 椭圆参数方程 | 扫描线填充 |
| **数据框**（平行四边形） | Bresenham 直线 × 4 | 扫描线填充 |
| **文档框**（波浪底矩形） | Bresenham 直线 + 正弦波 | 扫描线填充 |
| **数据库**（圆柱体） | 中点椭圆 × 2 + Bresenham 直线 × 2 | 扫描线填充 |
| **子程序框** | Bresenham 直线 × 6 | 扫描线填充 |
| **连接线** | Bresenham 直线 / 正交折线 / Bézier 曲线 | 无 |
| **箭头** | 实心三角 / 空心三角 / 菱形 / 圆点 | 扫描线填充 / 中点圆 |

---

## 四、图形数据结构

### 4.1 Shape 类型

使用 Python `dataclass` 定义，`Shape` 是联合类型：

```python
Shape = FlowchartShape | LineShape | TextShape
```

### 4.2 FlowchartShape

```python
@dataclass
class FlowchartShape:
    kind: str           # "process" / "decision" / "terminal" / "data" / "document" / "database" / "subprocess"
    x: float
    y: float
    width: float
    height: float
    text: str = ""
    style: ShapeStyle
    id: str             # uuid 唯一标识
    z_order: int
    rotation: float     # 旋转角度（度）
    flip_x: bool        # 水平翻转
    flip_y: bool        # 垂直翻转
```

每个 FlowchartShape 通过 `outline_points()` 返回轮廓点序列，由 `kind` 决定形状几何。`_apply_local_transform()` 应用旋转和翻转的齐次坐标变换。

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
    arrow_start: str = "none"        # 同上
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

Document 提供：`add_shape`、`add_connector`、`find_shape`、`shape_at`、`move_shapes`、`delete_shapes`、`copy_paste`、`connector_points`、`to_dict` / `from_dict` / `replace_from_dict`。

连接线路由在 `connector_points()` 中实现：
- **直线**：直接连两锚点
- **正交折线**：锚点方向延伸 → 水平/垂直拐弯 → 到达终点
- **贝塞尔曲线**：根据锚点方向计算控制点，调用 `cubic_bezier()` 生成曲线点序列

---

## 五、撤销/重做

采用**全量状态快照**模式（History 类），而非 Command 模式：

```python
class History:
    _states: list[dict]   # 每个状态是 document.to_dict() 的完整快照
    _index: int           # 当前状态指针

    push(state)           # 保存新状态（自动去重、截断 redo 栈）
    undo(document) → bool # 回退到上一状态
    redo(document) → bool # 前进到下一状态
    can_undo: bool
    can_redo: bool
```

每次编辑操作后调用 `history.push(document.to_dict())` 保存快照。撤销/重做通过 `document.replace_from_dict()` 恢复完整文档状态。

---

## 六、UI 界面

### 6.1 布局

```
┌───────────────────────────────────────────────────────┐
│ 菜单栏：文件(F) │ 编辑(E)                               │
├──────┬────────────────────────────────────┬───────────┤
│      │          工具栏 (tkinter Buttons)   │           │
│ 图   ├────────────────────────────────────┤ 属性面板   │
│ 元   │                                    │ ┌───────┐ │
│ 库   │       画 布 (Pillow → ImageTk)      │ │图形样式│ │
│      │         暗色背景 + 网格              │ │连接线  │ │
│(按钮 │                                    │ │文本样式│ │
│ 列表)│                                    │ └───────┘ │
├──────┴────────────────────────────────────┴───────────┤
│ 状态栏：鼠标坐标 │ 缩放 │ 图形数量 │ 操作提示             │
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
| 普通文本 | `#D0D0E0` |
| 图元描边 | `#6080A0` |
| 图元填充 | `#283850` |

### 6.3 交互方式

| 操作 | 方式 |
|------|------|
| 放置流程图图元 | 左侧图元库点击 → 画布上点击放置 |
| 连接两个图元 | 连接线工具 → 从起点图元拖拽到终点图元 |
| 选择图形 | 选择工具 → 点击图形 / 空白处拖拽框选 |
| 移动图形 | 选中后拖拽 |
| 旋转/缩放 | 右侧属性面板输入任意值 → 点击"应用样式" |
| 编辑文本 | 双击图形 → 内联编辑框 → Ctrl+Enter 确认 |
| 添加文本 | 文本工具 → 点击画布 → 内联编辑框 |
| 平移画布 | 中键拖拽 |
| 缩放画布 | Ctrl+鼠标滚轮 |
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
| `Ctrl+Y` | 重做 |
| `Ctrl+Shift+Z` | 重做（备选） |
| `Ctrl+C` | 复制 |
| `Ctrl+V` | 粘贴 |
| `Delete` | 删除 |
| `Ctrl+A` | 全选 |
| `Ctrl+E` | 导出 PNG |
| `Ctrl+滚轮` | 缩放画布 |
| `Esc` | 取消当前操作 |
| `V` | 选择工具 |
| `L` | 直线工具 |
| `T` | 文本工具 |
| `K` | 连接线工具 |

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
      "style": { "stroke": "#6080A0", "fill": "#283850", ... },
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
      "style": { "stroke": "#A7C7FF", ... }
    }
  ]
}
```

---

## 九、依赖

```
# requirements.txt
Pillow>=10.0.0
```

仅一个外部依赖。tkinter / json / uuid 均为 Python 内置。

---

## 十、交付物

1. `src/` — 完整源代码，`python src/main.py` 直接运行
2. `docs/plan.md` — 本设计文档
3. `docs/usage.md` — 使用说明
4. `tests/` — 单元测试
5. `requirements.txt` — 依赖清单
6. `README.md` — 项目说明
