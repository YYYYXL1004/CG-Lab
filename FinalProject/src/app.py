from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import ImageTk

from core.document import Document
from core.shapes import ConnectorShape, FlowchartShape, LineShape, TextShape
from core.style import ShapeStyle
from engine.command import History
from engine.renderer import Renderer
from engine.selection import apply_group_resize, bounds_from_handle, handle_at, selection_bounds, shapes_in_rect
from io_utils.serializer import load_document, save_document


CANVAS_WIDTH = 980
CANVAS_HEIGHT = 680

DASH_PRESETS = {"━━ 实线": [], "╌╌ 虚线": [10, 6], "⋯⋯ 点线": [3, 4], "━╌ 点划线": [10, 4, 3, 4]}
ARROW_MAP = {"▶ 实心箭头": "arrow", "▷ 空心箭头": "open_arrow", "◆ 菱形": "diamond", "● 圆点": "dot", "  无": "none"}
CONN_KINDS = {"━━ 直线": "straight", "┘└ 折线": "elbow", "〰 曲线": "bezier"}
ALIGN_MAP = {"左对齐": "left", "居中": "center", "右对齐": "right"}


class VectorFlowApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("VectorFlow - 矢量流程图编辑系统")
        self.geometry("1280x780")
        self.minsize(980, 640)

        self.document = Document()
        self.file_path: Path | None = None
        self.renderer = Renderer(CANVAS_WIDTH, CANVAS_HEIGHT)
        self.photo = None
        self.zoom = 1.0
        self.pan = (40.0, 40.0)
        self.show_grid = tk.BooleanVar(value=True)
        self.current_tool = tk.StringVar(value="select")
        self.pending_flow_kind = "process"
        self.selected_ids: set[str] = set()
        self.clipboard_ids: list[str] = []
        self.history = History()
        self.drag_start: tuple[float, float] | None = None
        self.drag_shape_origin: tuple[float, float] | None = None
        self.drag_total_delta = (0.0, 0.0)
        self.drag_mode: str | None = None
        self.resize_handle: str | None = None
        self.resize_original_bounds: tuple[float, float, float, float] | None = None
        self.resize_original_payloads: dict[str, dict] = {}
        self.connector_start_id: str | None = None
        self.status_text = tk.StringVar(value="Ready")
        self.stroke_color = tk.StringVar(value="#6080A0")
        self.fill_color = tk.StringVar(value="#283850")
        self.stroke_width = tk.IntVar(value=2)

        self.conn_kind_var = tk.StringVar(value="┘└ 折线")
        self.conn_arrow_end_var = tk.StringVar(value="▶ 实心箭头")
        self.conn_arrow_start_var = tk.StringVar(value="  无")
        self.conn_dash_var = tk.StringVar(value="━━ 实线")
        self.text_align_var = tk.StringVar(value="居中")
        self.text_bold_var = tk.BooleanVar(value=False)
        self.text_color_var = tk.StringVar(value="#D0D0E0")
        self.rotate_deg = tk.DoubleVar(value=15)
        self.scale_pct = tk.DoubleVar(value=120)

        self._inline_editor: tk.Text | None = None
        self._inline_edit_shape: TextShape | FlowchartShape | None = None

        self._configure_style()
        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()
        self._seed_demo()
        self.history.push(self.document.to_dict())
        self.redraw()

    def _configure_style(self) -> None:
        self.configure(bg="#1E1E2E")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#252535")
        style.configure("TLabel", background="#252535", foreground="#D0D0E0")
        style.configure("TButton", background="#2D2D40", foreground="#E7ECF5", padding=5)
        style.configure("Tool.TButton", background="#2D2D40", foreground="#E7ECF5", padding=(8, 5))
        style.configure("Accent.TButton", background="#4690E0", foreground="#FFFFFF", padding=(8, 5))
        style.configure("TCheckbutton", background="#252535", foreground="#D0D0E0")
        style.configure("TCombobox", fieldbackground="#2D2D40", foreground="#D0D0E0")
        style.configure("TSpinbox", fieldbackground="#2D2D40", foreground="#D0D0E0")

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="新建", accelerator="Ctrl+N", command=self.new_document)
        file_menu.add_command(label="打开...", accelerator="Ctrl+O", command=self.open_document)
        file_menu.add_command(label="保存", accelerator="Ctrl+S", command=self.save_document)
        file_menu.add_command(label="另存为...", accelerator="Ctrl+Shift+S", command=self.save_document_as)
        file_menu.add_separator()
        file_menu.add_command(label="导出 PNG...", accelerator="Ctrl+E", command=self.export_png)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.destroy)
        menu.add_cascade(label="文件", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="撤销", accelerator="Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="重做", accelerator="Ctrl+Y", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="复制", accelerator="Ctrl+C", command=self.copy_selection)
        edit_menu.add_command(label="粘贴", accelerator="Ctrl+V", command=self.paste_selection)
        edit_menu.add_command(label="删除", accelerator="Delete", command=self.delete_selection)
        edit_menu.add_separator()
        edit_menu.add_command(label="水平翻转", command=self.flip_horizontal)
        edit_menu.add_command(label="垂直翻转", command=self.flip_vertical)
        menu.add_cascade(label="编辑", menu=edit_menu)

        view_menu = tk.Menu(menu, tearoff=False)
        view_menu.add_checkbutton(label="显示网格", variable=self.show_grid, command=self.redraw)
        view_menu.add_command(label="缩放 100%", command=self.reset_view)
        menu.add_cascade(label="视图", menu=view_menu)
        self.config(menu=menu)

    def _build_layout(self) -> None:
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X)
        for label, tool in [("选择(V)", "select"), ("直线(L)", "line"), ("文本(T)", "text"), ("连接线(K)", "connector"), ("区域导出", "region_export")]:
            ttk.Button(top, text=label, style="Tool.TButton", command=lambda t=tool: self.set_tool(t)).pack(side=tk.LEFT, padx=2, pady=4)
        self.undo_btn = ttk.Button(top, text="撤销", command=self.undo)
        self.undo_btn.pack(side=tk.LEFT, padx=2)
        self.redo_btn = ttk.Button(top, text="重做", command=self.redo)
        self.redo_btn.pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(top, text="网格", variable=self.show_grid, command=self.redraw).pack(side=tk.LEFT, padx=10)
        ttk.Button(top, text="保存", style="Accent.TButton", command=self.save_document).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="导出 PNG", command=self.export_png).pack(side=tk.RIGHT, padx=4)

        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True)

        self.library = ttk.Frame(main, width=150)
        self.library.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(self.library, text="流程图图元").pack(anchor=tk.W, padx=10, pady=(10, 6))
        for text, kind in [
            ("处理框", "process"), ("判断框", "decision"), ("起止框", "terminal"),
            ("数据框", "data"), ("文档框", "document"), ("数据库", "database"), ("子程序", "subprocess"),
        ]:
            ttk.Button(self.library, text=text, command=lambda k=kind: self.pick_flow_shape(k)).pack(fill=tk.X, padx=10, pady=3)

        canvas_frame = ttk.Frame(main)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_frame, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="#1E1E2E", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        prop = ttk.Frame(main, width=220)
        prop.pack(side=tk.RIGHT, fill=tk.Y)
        self.properties = prop

        ttk.Label(prop, text="图形样式").pack(anchor=tk.W, padx=10, pady=(10, 4))
        ttk.Label(prop, text="描边色").pack(anchor=tk.W, padx=10)
        ttk.Button(prop, textvariable=self.stroke_color, command=self.choose_stroke).pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(prop, text="填充色").pack(anchor=tk.W, padx=10)
        ttk.Button(prop, textvariable=self.fill_color, command=self.choose_fill).pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(prop, text="线宽").pack(anchor=tk.W, padx=10)
        ttk.Spinbox(prop, from_=1, to=12, textvariable=self.stroke_width, width=6).pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(prop, text="应用样式", command=self.apply_style).pack(fill=tk.X, padx=10, pady=4)

        ttk.Separator(prop, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(prop, text="变换").pack(anchor=tk.W, padx=10)
        r_frame = ttk.Frame(prop)
        r_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(r_frame, text="旋转°").pack(side=tk.LEFT)
        ttk.Spinbox(r_frame, from_=-360, to=360, textvariable=self.rotate_deg, width=5).pack(side=tk.LEFT, padx=4)
        ttk.Button(r_frame, text="旋转", command=self._do_rotate).pack(side=tk.LEFT, padx=2)
        s_frame = ttk.Frame(prop)
        s_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(s_frame, text="缩放%").pack(side=tk.LEFT)
        ttk.Spinbox(s_frame, from_=10, to=500, textvariable=self.scale_pct, width=5).pack(side=tk.LEFT, padx=4)
        ttk.Button(s_frame, text="缩放", command=self._do_scale).pack(side=tk.LEFT, padx=2)
        flip_frame = ttk.Frame(prop)
        flip_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(flip_frame, text="水平翻转", command=self.flip_horizontal).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(flip_frame, text="垂直翻转", command=self.flip_vertical).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        ttk.Separator(prop, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(prop, text="连接线样式").pack(anchor=tk.W, padx=10)
        ttk.Label(prop, text="线型").pack(anchor=tk.W, padx=10)
        ttk.Combobox(prop, textvariable=self.conn_kind_var, values=list(CONN_KINDS.keys()), state="readonly", width=14).pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(prop, text="终点").pack(anchor=tk.W, padx=10)
        ttk.Combobox(prop, textvariable=self.conn_arrow_end_var, values=list(ARROW_MAP.keys()), state="readonly", width=14).pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(prop, text="起点").pack(anchor=tk.W, padx=10)
        ttk.Combobox(prop, textvariable=self.conn_arrow_start_var, values=list(ARROW_MAP.keys()), state="readonly", width=14).pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(prop, text="线条").pack(anchor=tk.W, padx=10)
        ttk.Combobox(prop, textvariable=self.conn_dash_var, values=list(DASH_PRESETS.keys()), state="readonly", width=14).pack(fill=tk.X, padx=10, pady=2)

        ttk.Separator(prop, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(prop, text="文本样式").pack(anchor=tk.W, padx=10)
        ttk.Label(prop, text="对齐").pack(anchor=tk.W, padx=10)
        ttk.Combobox(prop, textvariable=self.text_align_var, values=list(ALIGN_MAP.keys()), state="readonly", width=14).pack(fill=tk.X, padx=10, pady=2)
        ttk.Checkbutton(prop, text="加粗", variable=self.text_bold_var).pack(anchor=tk.W, padx=10, pady=2)
        ttk.Label(prop, text="文字颜色").pack(anchor=tk.W, padx=10)
        ttk.Button(prop, textvariable=self.text_color_var, command=self.choose_text_color).pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(prop, text="应用文本样式", command=self.apply_text_style).pack(fill=tk.X, padx=10, pady=4)

        status = ttk.Frame(self)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(status, textvariable=self.status_text).pack(side=tk.LEFT, padx=8, pady=4)

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda _e: self.new_document())
        self.bind("<Control-o>", lambda _e: self.open_document())
        self.bind("<Control-s>", lambda _e: self.save_document())
        self.bind("<Control-S>", lambda _e: self.save_document_as())
        self.bind("<Control-e>", lambda _e: self.export_png())
        self.bind("<Control-z>", lambda _e: self.undo())
        self.bind("<Control-y>", lambda _e: self.redo())
        self.bind("<Control-Shift-z>", lambda _e: self.redo())
        self.bind("<Control-Shift-Z>", lambda _e: self.redo())
        self.bind("<Control-c>", lambda _e: self.copy_selection())
        self.bind("<Control-v>", lambda _e: self.paste_selection())
        self.bind("<Delete>", lambda _e: self.delete_selection())
        self.bind("<Escape>", lambda _e: self.clear_selection())
        for key, tool in [("v", "select"), ("l", "line"), ("t", "text"), ("k", "connector")]:
            self.bind(key, lambda _e, t=tool: self.set_tool(t))

    def _seed_demo(self) -> None:
        start = self.document.add_shape(FlowchartShape("terminal", 80, 80, 150, 70, "开始"))
        step = self.document.add_shape(FlowchartShape("process", 320, 80, 170, 70, "处理数据"))
        decision = self.document.add_shape(FlowchartShape("decision", 590, 65, 140, 100, "是否通过?"))
        self.document.add_connector(ConnectorShape(start.id, step.id, "right", "left"))
        self.document.add_connector(ConnectorShape(step.id, decision.id, "right", "left"))

    # ── Tool management ─────────────────────────────────────────────

    def set_tool(self, tool: str) -> None:
        self._commit_inline_editor()
        self.current_tool.set(tool)
        self.connector_start_id = None
        self.status_text.set(f"当前工具: {tool}")

    def pick_flow_shape(self, kind: str) -> None:
        self.pending_flow_kind = kind
        self.set_tool("flow")

    # ── Rendering ───────────────────────────────────────────────────

    def redraw(self, draft: bool = False) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        self.renderer = Renderer(width, height)
        image = self.renderer.render(self.document, self.zoom, self.pan, self.selected_ids, self.show_grid.get(), draft=draft)
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("render")
        self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW, tags="render")
        self.canvas.tag_lower("render")
        self._update_status()

    def _update_status(self, msg: str | None = None) -> None:
        if msg:
            self.status_text.set(msg)
            return
        parts = [f"工具: {self.current_tool.get()}", f"缩放: {round(self.zoom * 100)}%", f"图形: {len(self.document.shapes)}"]
        if self.history.can_undo:
            parts.append("可撤销")
        if self.history.can_redo:
            parts.append("可重做")
        self.status_text.set(" | ".join(parts))

    # ── Mouse events ────────────────────────────────────────────────

    def on_canvas_resize(self, _event) -> None:
        self.redraw()

    def on_mouse_move(self, event) -> None:
        x, y = self.screen_to_world(event.x, event.y)
        self.status_text.set(f"工具: {self.current_tool.get()} | ({round(x)}, {round(y)}) | 缩放: {round(self.zoom * 100)}%")

    def on_left_down(self, event) -> None:
        if self._inline_editor:
            self._commit_inline_editor()
            return
        self.drag_start = self.screen_to_world(event.x, event.y)
        self.drag_mode = None
        tool = self.current_tool.get()

        if tool == "select":
            selected_bounds = selection_bounds(self.document, self.selected_ids)
            rh = handle_at(selected_bounds, self.drag_start, tolerance=8 / self.zoom)
            if rh:
                self.drag_mode = "resize"
                self.resize_handle = rh
                self.resize_original_bounds = selected_bounds
                self.resize_original_payloads = {s.id: s.to_dict() for s in self.document.shapes if s.id in self.selected_ids}
                self.redraw()
                return
            shape = self.document.shape_at(*self.drag_start)
            if shape:
                if shape.id not in self.selected_ids:
                    self.selected_ids = {shape.id}
                self.drag_shape_origin = self.drag_start
                self.drag_total_delta = (0.0, 0.0)
                self.drag_mode = "move"
            else:
                self.selected_ids.clear()
                self.drag_mode = "box_select"
            self.redraw()

        elif tool == "flow":
            self.place_flow_shape(*self.drag_start)
            self._push_history()

        elif tool == "text":
            self._open_inline_editor(self.drag_start[0], self.drag_start[1])

        elif tool == "connector":
            shape = self.document.shape_at(*self.drag_start)
            if isinstance(shape, FlowchartShape):
                self.connector_start_id = shape.id
                self.selected_ids = {shape.id}
                self.drag_mode = "connector_drag"
                self.status_text.set("拖拽到目标图形以创建连接线")
                self.redraw()

        elif tool == "region_export":
            self.status_text.set("拖拽选择导出区域")

        elif tool == "line":
            pass

    def on_left_drag(self, event) -> None:
        if self.drag_start is None:
            return
        current = self.screen_to_world(event.x, event.y)
        tool = self.current_tool.get()

        if tool == "select" and self.drag_mode == "move" and self.drag_shape_origin and self.selected_ids:
            dx = current[0] - self.drag_shape_origin[0]
            dy = current[1] - self.drag_shape_origin[1]
            self.document.move_shapes(list(self.selected_ids), dx, dy)
            self.drag_total_delta = (self.drag_total_delta[0] + dx, self.drag_total_delta[1] + dy)
            self.drag_shape_origin = current
            self.redraw(draft=True)
        elif tool == "select" and self.drag_mode == "resize" and self.resize_handle:
            new_bounds = bounds_from_handle(self.resize_original_bounds, self.resize_handle, current)
            apply_group_resize(self.document, self.selected_ids, self.resize_original_payloads, self.resize_original_bounds, new_bounds)
            self.redraw(draft=True)
        elif tool == "select" and self.drag_mode == "box_select":
            self.canvas.delete("preview")
            x0, y0 = self.world_to_screen(self.drag_start)
            x1, y1 = self.world_to_screen(current)
            self.canvas.create_rectangle(x0, y0, x1, y1, outline="#FFCF5A", dash=(4, 3), tags="preview")
        elif tool == "connector" and self.drag_mode == "connector_drag":
            self.canvas.delete("preview")
            x0, y0 = self.world_to_screen(self.drag_start)
            x1, y1 = event.x, event.y
            self.canvas.create_line(x0, y0, x1, y1, fill="#A7C7FF", dash=(6, 3), width=2, arrow=tk.LAST, tags="preview")
        elif tool in {"line", "region_export"}:
            self.canvas.delete("preview")
            x0, y0 = self.world_to_screen(self.drag_start)
            x1, y1 = self.world_to_screen(current)
            if tool == "line":
                self.canvas.create_line(x0, y0, x1, y1, fill="#FFCF5A", dash=(4, 3), tags="preview")
            else:
                self.canvas.create_rectangle(x0, y0, x1, y1, outline="#5AFF8A", dash=(4, 3), width=2, tags="preview")

    def on_left_up(self, event) -> None:
        if self.drag_start is None:
            return
        current = self.screen_to_world(event.x, event.y)
        tool = self.current_tool.get()

        if tool == "line":
            self.document.add_shape(LineShape(self.drag_start[0], self.drag_start[1], current[0], current[1]))
            self._push_history()
            self.canvas.delete("preview")
            self.redraw()
        elif tool == "region_export":
            self.canvas.delete("preview")
            self._do_region_export(self.drag_start, current)
        elif tool == "connector" and self.drag_mode == "connector_drag":
            self.canvas.delete("preview")
            target = self.document.shape_at(*current)
            if isinstance(target, FlowchartShape) and self.connector_start_id and target.id != self.connector_start_id:
                start = self.document.find_shape(self.connector_start_id)
                if isinstance(start, FlowchartShape):
                    sa, ea = self.best_anchor_pair(start, target)
                    kind = CONN_KINDS.get(self.conn_kind_var.get(), "elbow")
                    dash = DASH_PRESETS.get(self.conn_dash_var.get(), [])
                    conn = ConnectorShape(
                        start.id, target.id, sa, ea, kind=kind,
                        arrow_end=ARROW_MAP.get(self.conn_arrow_end_var.get(), "arrow"),
                        arrow_start=ARROW_MAP.get(self.conn_arrow_start_var.get(), "none"),
                        style=ShapeStyle(fill=None, stroke=self.stroke_color.get(), stroke_width=self.stroke_width.get(), dash=dash),
                    )
                    self.document.add_connector(conn)
                    self._push_history()
            self.connector_start_id = None
            self.redraw()
        elif tool == "select":
            if self.drag_mode == "box_select":
                x1, y1 = self.drag_start
                x2, y2 = current
                self.selected_ids = set(shapes_in_rect(self.document, (x1, y1, x2, y2)))
                self.canvas.delete("preview")
            elif self.drag_mode in {"move", "resize"}:
                self._push_history()
            self.redraw()

        self.drag_start = None
        self.drag_shape_origin = None
        self.drag_total_delta = (0.0, 0.0)
        self.drag_mode = None
        self.resize_handle = None
        self.resize_original_bounds = None
        self.resize_original_payloads = {}

    def on_double_click(self, event) -> None:
        point = self.screen_to_world(event.x, event.y)
        shape = self.document.shape_at(*point)
        if isinstance(shape, (FlowchartShape, TextShape)):
            self._open_inline_editor_for_shape(shape)

    def on_pan_start(self, event) -> None:
        self.drag_start = (event.x, event.y)

    def on_pan_drag(self, event) -> None:
        if self.drag_start is None:
            return
        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]
        self.pan = (self.pan[0] + dx, self.pan[1] + dy)
        self.drag_start = (event.x, event.y)
        self.redraw(draft=True)

    def on_mouse_wheel(self, event) -> None:
        if event.state & 0x0004:
            factor = 1.1 if event.delta > 0 else 0.9
            world_before = self.screen_to_world(event.x, event.y)
            self.zoom = max(0.2, min(3.5, self.zoom * factor))
            sx, sy = self.world_to_screen(world_before)
            self.pan = (self.pan[0] + event.x - sx, self.pan[1] + event.y - sy)
            self.redraw()

    # ── Shape creation ──────────────────────────────────────────────

    def place_flow_shape(self, x: float, y: float) -> None:
        dims = {"decision": (140, 100), "terminal": (150, 70), "database": (150, 90), "document": (160, 90), "data": (160, 70)}
        labels = {"process": "处理", "decision": "判断", "terminal": "开始/结束", "data": "数据", "document": "文档", "database": "数据库", "subprocess": "子程序"}
        w, h = dims.get(self.pending_flow_kind, (160, 70))
        shape = FlowchartShape(
            self.pending_flow_kind, x - w / 2, y - h / 2, w, h,
            labels.get(self.pending_flow_kind, "图元"),
            ShapeStyle(stroke=self.stroke_color.get(), fill=self.fill_color.get(), stroke_width=self.stroke_width.get()),
        )
        self.document.add_shape(shape)
        self.selected_ids = {shape.id}
        self.redraw()

    def best_anchor_pair(self, start: FlowchartShape, end: FlowchartShape) -> tuple[str, str]:
        sx, sy = start.center().x, start.center().y
        ex, ey = end.center().x, end.center().y
        if abs(ex - sx) >= abs(ey - sy):
            return ("right", "left") if ex >= sx else ("left", "right")
        return ("bottom", "top") if ey >= sy else ("top", "bottom")

    # ── Inline text editor ──────────────────────────────────────────

    def _open_inline_editor(self, wx: float, wy: float, initial_text: str = "") -> None:
        sx, sy = self.world_to_screen((wx, wy))
        self._inline_edit_shape = None
        self._create_text_widget(int(sx), int(sy), initial_text, wx, wy)

    def _open_inline_editor_for_shape(self, shape: FlowchartShape | TextShape) -> None:
        if isinstance(shape, FlowchartShape):
            bounds = shape.bounds()
            cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
            sx, sy = self.world_to_screen((cx, cy))
            self._inline_edit_shape = shape
            self._create_text_widget(int(sx) - 60, int(sy) - 12, shape.text, cx, cy)
        elif isinstance(shape, TextShape):
            sx, sy = self.world_to_screen((shape.x, shape.y))
            self._inline_edit_shape = shape
            self._create_text_widget(int(sx), int(sy), shape.text, shape.x, shape.y)

    def _create_text_widget(self, sx: int, sy: int, text: str, wx: float, wy: float) -> None:
        if self._inline_editor:
            self._commit_inline_editor()
        editor = tk.Text(
            self.canvas, width=22, height=3, wrap=tk.WORD,
            bg="#2D2D40", fg="#E7ECF5", insertbackground="#FFFFFF",
            font=("Microsoft YaHei", 11), relief=tk.SOLID, bd=1,
            highlightbackground="#5BA8FF", highlightthickness=2,
        )
        editor.insert("1.0", text)
        editor._world_pos = (wx, wy)
        editor.bind("<Control-Return>", lambda _e: (self._commit_inline_editor(), "break")[1])
        editor.bind("<Escape>", lambda _e: self._cancel_inline_editor())
        self._inline_editor = editor
        self.canvas.create_window(sx, sy, window=editor, anchor=tk.NW, tags="inline_editor")
        editor.focus_set()

    def _commit_inline_editor(self) -> None:
        editor = self._inline_editor
        if editor is None:
            return
        text = editor.get("1.0", tk.END).rstrip("\n")
        wx, wy = editor._world_pos
        self._inline_editor = None
        self.canvas.delete("inline_editor")
        editor.destroy()
        if not text:
            self._inline_edit_shape = None
            return
        target = self._inline_edit_shape
        if isinstance(target, FlowchartShape):
            target.text = text
        elif isinstance(target, TextShape):
            target.text = text
        else:
            align = ALIGN_MAP.get(self.text_align_var.get(), "center")
            style = ShapeStyle(fill=None, text_color=self.text_color_var.get(), text_align=align, bold=self.text_bold_var.get())
            self.document.add_shape(TextShape(wx, wy, text, style=style))
        self._inline_edit_shape = None
        self._push_history()
        self.redraw()

    def _cancel_inline_editor(self) -> None:
        if self._inline_editor:
            self.canvas.delete("inline_editor")
            self._inline_editor.destroy()
            self._inline_editor = None
            self._inline_edit_shape = None

    # ── Region export ───────────────────────────────────────────────

    def _do_region_export(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        sx0, sy0 = self.world_to_screen(start)
        sx1, sy1 = self.world_to_screen(end)
        left, right = int(min(sx0, sx1)), int(max(sx0, sx1))
        top_y, bottom = int(min(sy0, sy1)), int(max(sy0, sy1))
        if right - left < 10 or bottom - top_y < 10:
            self._update_status("区域太小，请重新选择")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not path:
            return
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        r = Renderer(w, h)
        img = r.render(self.document, self.zoom, self.pan, set(), self.show_grid.get())
        img.crop((left, top_y, right, bottom)).save(path, "PNG")
        self._update_status(f"已导出区域: {path}")

    # ── Style ───────────────────────────────────────────────────────

    def choose_stroke(self) -> None:
        c = colorchooser.askcolor(color=self.stroke_color.get(), parent=self)[1]
        if c:
            self.stroke_color.set(c)

    def choose_fill(self) -> None:
        c = colorchooser.askcolor(color=self.fill_color.get(), parent=self)[1]
        if c:
            self.fill_color.set(c)

    def choose_text_color(self) -> None:
        c = colorchooser.askcolor(color=self.text_color_var.get(), parent=self)[1]
        if c:
            self.text_color_var.set(c)

    def apply_style(self) -> None:
        if not self.selected_ids:
            return
        for sid in self.selected_ids:
            shape = self.document.find_shape(sid)
            if shape:
                shape.style.stroke = self.stroke_color.get()
                shape.style.fill = self.fill_color.get()
                shape.style.stroke_width = self.stroke_width.get()
        self._push_history()
        self.redraw()

    def apply_text_style(self) -> None:
        if not self.selected_ids:
            return
        align = ALIGN_MAP.get(self.text_align_var.get(), "center")
        bold = self.text_bold_var.get()
        color = self.text_color_var.get()
        for sid in self.selected_ids:
            shape = self.document.find_shape(sid)
            if shape:
                shape.style.text_align = align
                shape.style.bold = bold
                shape.style.text_color = color
        self._push_history()
        self.redraw()

    # ── Clipboard ───────────────────────────────────────────────────

    def copy_selection(self) -> None:
        self.clipboard_ids = list(self.selected_ids)
        conn_count = sum(1 for c in self.document.connectors if c.start_shape_id in self.selected_ids and c.end_shape_id in self.selected_ids)
        self._update_status(f"已复制 {len(self.clipboard_ids)} 个图形" + (f" 和 {conn_count} 条连接线" if conn_count else ""))

    def paste_selection(self) -> None:
        if not self.clipboard_ids:
            return
        pasted = self.document.copy_paste(self.clipboard_ids, (30, 30))
        self.selected_ids = {s.id for s in pasted}
        self.clipboard_ids = list(self.selected_ids)
        self._push_history()
        self.redraw()

    def delete_selection(self) -> None:
        if not self.selected_ids:
            return
        self.document.delete_shapes(list(self.selected_ids))
        self.selected_ids.clear()
        self._push_history()
        self.redraw()

    def clear_selection(self) -> None:
        self._commit_inline_editor()
        self.selected_ids.clear()
        self.connector_start_id = None
        self.redraw()

    # ── Undo / Redo ─────────────────────────────────────────────────

    def _push_history(self) -> None:
        self.history.push(self.document.to_dict())

    def undo(self) -> None:
        if self.history.undo(self.document):
            self.selected_ids.clear()
            self.redraw()
            self._update_status("已撤销")
        else:
            self._update_status("没有可撤销的操作")

    def redo(self) -> None:
        if self.history.redo(self.document):
            self.selected_ids.clear()
            self.redraw()
            self._update_status("已重做")
        else:
            self._update_status("没有可重做的操作")

    # ── Transforms ──────────────────────────────────────────────────

    def _do_rotate(self) -> None:
        deg = self.rotate_deg.get()
        for sid in self.selected_ids:
            shape = self.document.find_shape(sid)
            if shape and hasattr(shape, "rotate"):
                shape.rotate(deg)
        if self.selected_ids:
            self._push_history()
            self.redraw()

    def _do_scale(self) -> None:
        factor = self.scale_pct.get() / 100.0
        if factor <= 0:
            return
        for sid in self.selected_ids:
            shape = self.document.find_shape(sid)
            if shape and hasattr(shape, "scale"):
                shape.scale(factor)
        if self.selected_ids:
            self._push_history()
            self.redraw()

    def flip_horizontal(self) -> None:
        for sid in self.selected_ids:
            shape = self.document.find_shape(sid)
            if shape and hasattr(shape, "flip_horizontal"):
                shape.flip_horizontal()
        if self.selected_ids:
            self._push_history()
            self.redraw()

    def flip_vertical(self) -> None:
        for sid in self.selected_ids:
            shape = self.document.find_shape(sid)
            if shape and hasattr(shape, "flip_vertical"):
                shape.flip_vertical()
        if self.selected_ids:
            self._push_history()
            self.redraw()

    # ── File I/O ────────────────────────────────────────────────────

    def new_document(self) -> None:
        self.document = Document()
        self.history = History()
        self.history.push(self.document.to_dict())
        self.file_path = None
        self.selected_ids.clear()
        self.redraw()

    def open_document(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("VectorFlow", "*.vflow"), ("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        self.document = load_document(path)
        self.history = History()
        self.history.push(self.document.to_dict())
        self.file_path = Path(path)
        self.selected_ids.clear()
        self.redraw()

    def save_document(self) -> None:
        if self.file_path is None:
            self.save_document_as()
            return
        save_document(self.document, self.file_path)
        self._update_status(f"已保存: {self.file_path}")

    def save_document_as(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".vflow", filetypes=[("VectorFlow", "*.vflow"), ("JSON", "*.json")])
        if not path:
            return
        self.file_path = Path(path)
        self.save_document()

    def export_png(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not path:
            return
        image = self.renderer.render(self.document, self.zoom, self.pan, set(), self.show_grid.get())
        image.save(path, format="PNG")
        self._update_status(f"已导出: {path}")

    def reset_view(self) -> None:
        self.zoom = 1.0
        self.pan = (40.0, 40.0)
        self.redraw()

    # ── Coordinate conversion ───────────────────────────────────────

    def screen_to_world(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.pan[0]) / self.zoom, (y - self.pan[1]) / self.zoom

    def world_to_screen(self, point: tuple[float, float]) -> tuple[float, float]:
        return point[0] * self.zoom + self.pan[0], point[1] * self.zoom + self.pan[1]


def main() -> int:
    try:
        app = VectorFlowApp()
        app.mainloop()
        return 0
    except Exception as exc:
        messagebox.showerror("VectorFlow error", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
