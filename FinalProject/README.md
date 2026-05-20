# VectorFlow

VectorFlow 是一个面向计算机图形学课程设计的矢量流程图编辑系统。几何图元的描边、填充、连接线、箭头均通过自研像素级算法生成像素，再写入 Pillow 后缓冲区并显示到 tkinter Canvas。

## 功能

- **流程图图元**：处理框、判断框、起止框、数据框、文档框、数据库、子程序框
- **连接线**：直线 / 正交折线 / 贝塞尔曲线三种线型，拖拽方式创建，支持实线 / 虚线 / 点线
- **箭头样式**：实心箭头、空心箭头、菱形、圆点，起点终点可独立设置
- **直线与文本**：独立直线绘制、内联文本编辑（支持多行、居中/左对齐/右对齐、加粗、颜色）
- **编辑操作**：选择、框选、移动、复制粘贴、删除，连接线自动跟随
- **几何变换**：任意角度旋转、任意比例缩放、水平/垂直翻转，基于 3×3 齐次坐标矩阵
- **撤销**：全量状态快照，支持 Ctrl+Z，撤销按钮状态实时同步
- **一键清屏**：清除所有图形（可撤销）
- **文件持久化**：`.vflow` JSON 格式保存/打开，支持继续编辑
- **导出**：全画布导出 PNG、矩形区域导出 PNG
- **自研算法**：Bresenham 直线、DDA、中点圆、中点椭圆、de Casteljau 三次 Bezier、扫描线填充（AET）、Cohen-Sutherland 裁剪、Wu 反走样、齐次坐标矩阵变换

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

## 说明

Pillow 只用于像素缓冲区、文本渲染和 PNG 保存。核心几何图形没有使用 `Canvas.create_line`、`Canvas.create_rectangle`、`ImageDraw.line`、`ImageDraw.rectangle`、`ImageDraw.ellipse` 等系统绘图函数。
