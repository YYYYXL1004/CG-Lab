# VectorFlow

VectorFlow 是一个面向计算机图形学课程设计的矢量流程图编辑系统。几何图元的描边、填充、连接线、箭头均通过自研像素级算法生成像素，再写入 Pillow 后缓冲区并显示到 tkinter Canvas。

## 功能

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
│   │   ├── command.py           # History：全量快照式撤销栈
│   │   └── selection.py         # 选择框、句柄检测、群组缩放辅助函数
│   └── io_utils/
│       └── serializer.py        # load_document / save_document（.vflow JSON 格式）
├── tests/
│   ├── test_algorithms.py       # 算法单元测试
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
