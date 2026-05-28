# VectorFlow

VectorFlow 是一个面向计算机图形学课程设计的矢量流程图编辑系统。几何图元的描边、填充、连接线、箭头均通过自研像素级算法生成像素，再写入 Pillow 后缓冲区并显示到 tkinter Canvas。

## 基础功能

这些功能对应作业对“具有编辑能力的矢量图形编辑系统”的基础要求。

- **流程图图元**：处理框、判断框、起止框、数据框、文档框、数据库、子程序框
- **通用图形**：圆形、椭圆、三角形、梯形、平行四边形、圆角矩形、五角星、六边形、左/右箭头、加号
- **电路图符号**：电阻、电容、接地、电池、开关、LED、电感、电压源（仅绘制器件轮廓，无外侧包围框）
- **连接线**：直线 / 正交折线 / 贝塞尔曲线三种线型，拖拽方式创建，支持实线 / 虚线 / 点线
- **箭头样式**：实心箭头、空心箭头、菱形、圆点，起点终点可独立设置
- **直线与文本**：独立直线绘制、内联文本编辑（支持多行、居中/左对齐/右对齐、加粗、颜色）
- **手绘曲线**：按住鼠标自由勾画，采样点经 Catmull-Rom → 三次 Bezier 平滑后写入画布，可被选中、变换、撤销
- **编辑操作**：选择、框选、移动、复制粘贴、删除，连接线自动跟随
- **几何变换**：任意角度旋转、任意比例缩放、水平/垂直翻转，基于 3×3 齐次坐标矩阵
- **撤销**：全量状态快照，支持 Ctrl+Z，撤销按钮状态实时同步
- **一键清屏**：清除所有图形（可撤销）
- **文件持久化**：`.vflow` JSON 格式保存/打开，支持继续编辑
- **导出**：全画布导出 PNG、矩形区域导出 PNG
- **自研算法**：Bresenham 直线、DDA、中点圆、中点椭圆、de Casteljau 三次 Bezier、Catmull-Rom 样条、扫描线填充（AET）、Cohen-Sutherland 裁剪、Wu 反走样、齐次坐标矩阵变换

## 作业要求对应

| 作业要求 | 本项目实现 |
|---|---|
| 选择、移动、复制、粘贴、删除 | 支持单选、框选、多选、拖拽移动、Ctrl+C/V、Delete 删除 |
| 几何变换 | 支持平移、任意角度旋转、任意比例缩放、水平/垂直对称翻转 |
| 部分图形裁剪 | 实现 Cohen-Sutherland 线段裁剪算法，并支持矩形区域导出 |
| 自定义数据结构与永久保存 | 使用 Document / Shape / ConnectorShape 数据模型，保存为 `.vflow` JSON 文件 |
| 重新显示保存文件 | 支持打开 `.vflow` 文件并恢复画布、图形、连接线、样式和文本 |
| 重新显示后继续编辑 | 打开文件后仍可继续选择、移动、变换、编辑文本、增删图元和保存 |
| 复杂图元 | 支持流程图、组织结构图、通用几何图形、电路图符号和多风格连接线 |
| 减少系统绘图函数 | 几何图形绘制由自研像素级算法完成，tkinter Canvas 只负责显示最终图像和 UI 交互 |
| 程序实用性 | 可用于绘制流程图、组织结构图、电路图，并支持 PNG 导出 |
| 简洁快捷的操作 | 顶部工具栏、左侧图元库、内联文本编辑、快捷键、网格、撤销和一键导出 |

## 创新点

- **自研像素级渲染管线**：所有几何图元先由算法生成像素点，再写入 Pillow 后缓冲区显示，避免直接依赖系统图形 API。
- **算法回放模式**：选中图形后点击"算法回放"，逐帧展示 Bresenham 描线、中点圆/椭圆、扫描线填充等像素生成过程，便于答辩展示图形学原理。
- **动态连接线**：连接线显示沿路径流动的高亮像素，可用于表达流程方向或电路电流方向，底层基于 Bresenham 路径采样和相位偏移。
- **多领域图元库**：同一套编辑器支持流程图、组织结构图、电路图和通用图形，不只是单一几何绘图演示。
- **手绘曲线平滑**：鼠标自由采样后通过 Catmull-Rom / 三次 Bezier 平滑，兼顾自由绘制和矢量编辑。
- **暗色/浅色主题与现代化界面**：提供更接近实际绘图软件的操作体验，工具栏、图元库、属性弹窗和画布交互保持简洁。

## 运行

```powershell
conda activate CGLab
pip install -r requirements.txt
python src/main.py
```

## 测试

```powershell
conda activate CGLab
python -m unittest discover -s tests -v
```

## 项目架构

```
FinalProject/
├── src/
│   ├── main.py                  # 入口：启动 VectorFlowApp
│   ├── app.py                   # 主窗口、UI 布局、事件处理、弹窗对话框
│   ├── algorithms/              # 自研图形算法层（纯像素操作）
│   │   ├── line.py              # Bresenham 直线 / DDA 算法
│   │   ├── circle.py            # 中点圆算法
│   │   ├── ellipse.py           # 中点椭圆算法
│   │   ├── bezier.py            # de Casteljau 三次 Bézier 曲线
│   │   ├── fill.py              # 扫描线填充（AET 活性边表）
│   │   ├── clip.py              # Cohen-Sutherland 线段裁剪
│   │   ├── antialias.py         # Wu 反走样算法
│   │   └── transform.py        # 3×3 齐次坐标矩阵变换
│   ├── core/                    # 数据模型层
│   │   ├── document.py          # Document：图形/连接线集合，序列化/反序列化
│   │   ├── shapes.py            # Shape 基类及各图元（FlowchartShape、LineShape、TextShape、ConnectorShape）
│   │   └── style.py             # ShapeStyle：描边、填充、线宽、字体等样式属性
│   ├── engine/                  # 渲染与交互引擎
│   │   ├── renderer.py          # Renderer：调用 algorithms 将 Document 渲染到 PIL 图像
│   │   ├── animation.py         # 动态连接线：沿 Bresenham 路径生成流动高亮像素
│   │   ├── algorithm_replay.py  # 算法回放：把图元拆成可逐帧播放的像素序列
│   │   ├── command.py           # History：全量快照式撤销栈
│   │   └── selection.py         # 选择框、句柄检测、群组缩放辅助函数
│   └── io_utils/
│       └── serializer.py        # load_document / save_document（.vflow JSON 格式）
├── tests/
│   ├── test_algorithms.py       # 算法单元测试
│   ├── test_animation_replay.py # 动态连接线与算法回放测试
│   ├── test_document.py         # Document 模型测试
│   ├── test_renderer_command.py # 渲染与撤销栈测试
│   └── test_selection.py        # 选择逻辑测试
├── assets/
│   └── templates/demo.vflow     # 示例流程图文件
├── docs/
│   ├── plan.md                  # 开发规划文档
│   └── usage.md                 # 使用说明
└── requirements.txt             # 依赖：Pillow
```

## 说明

Pillow 只用于像素缓冲区、文本渲染和 PNG 保存。核心几何图形没有使用 `Canvas.create_line`、`Canvas.create_rectangle`、`ImageDraw.line`、`ImageDraw.rectangle`、`ImageDraw.ellipse` 等系统绘图函数。
