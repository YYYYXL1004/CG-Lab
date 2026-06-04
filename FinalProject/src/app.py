from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from algorithms.bezier import catmull_rom_polyline
from core.document import Document
from core.shapes import ConnectorShape, CurveShape, FlowchartShape, LineShape, Shape, TextShape
from core.style import ShapeStyle
from engine.algorithm_replay import ReplayFrame, ReplaySequence, build_shape_replay
from engine.canvas_renderer import CanvasRenderer
from engine.command import History
from engine.guides import compute_guides
from engine.renderer import Renderer
from engine.selection import apply_group_resize, apply_group_rotation, bounds_from_handle, handle_at, rotation_delta, selection_bounds, shapes_in_rect
from engine.text_style import TEXT_SIZE_MAX, TEXT_SIZE_MIN, apply_text_style as apply_text_style_to_shapes, clamp_font_size
from io_utils.serializer import load_document, save_document


CANVAS_WIDTH = 980
CANVAS_HEIGHT = 680

DASH_PRESETS = {"━━ 实线": [], "╌╌ 虚线": [10, 6], "⋯⋯ 点线": [3, 4], "━╌ 点划线": [10, 4, 3, 4]}
ARROW_MAP = {"▶ 实心箭头": "arrow", "▷ 空心箭头": "open_arrow", "◆ 菱形": "diamond", "● 圆点": "dot", "  无": "none"}
CONN_KINDS = {"━━ 直线": "straight", "┘└ 折线": "elbow", "〰 曲线": "bezier"}
ALIGN_MAP = {"左对齐": "left", "居中": "center", "右对齐": "right"}


@dataclass(frozen=True)
class ToolSpec:
    label: str
    shortcut: str
    hint: str


TOOL_SPECS: dict[str, ToolSpec] = {
    "select": ToolSpec("选择", "V", "拖拽移动选中图形，或框选多个图形"),
    "line": ToolSpec("直线", "L", "拖拽绘制一条直线"),
    "curve": ToolSpec("画笔", "C", "按住并拖拽绘制平滑曲线"),
    "text": ToolSpec("文本", "T", "点击画布添加文本，双击已有文本可编辑"),
    "connector": ToolSpec("连接", "K", "从一个图形拖拽到另一个图形以创建连接线"),
    "region_export": ToolSpec("区域导出", "", "拖拽选择要导出的画布区域"),
}


REQUIRED_THEME_TOKENS: set[str] = {
    "root_bg",
    "panel_bg",
    "panel_elevated",
    "button_bg",
    "button_hover",
    "button_pressed",
    "tool_selected_bg",
    "tool_selected_fg",
    "accent_bg",
    "accent_hover",
    "accent_pressed",
    "accent_fg",
    "danger_bg",
    "danger_fg",
    "fg",
    "fg_active",
    "caption",
    "separator",
    "border",
    "field_bg",
    "canvas_bg",
    "grid",
    "selection",
    "selection_handle_fill",
    "guide",
    "editor_bg",
    "editor_fg",
    "editor_caret",
    "editor_highlight",
    "sash_hover",
    "toggle_label",
}


def missing_theme_tokens(theme: dict[str, str]) -> list[str]:
    return sorted(REQUIRED_THEME_TOKENS.difference(theme.keys()))


def tool_hint(tool: str) -> str:
    return TOOL_SPECS.get(tool, TOOL_SPECS["select"]).hint


def tool_label(tool: str) -> str:
    return TOOL_SPECS.get(tool, TOOL_SPECS["select"]).label


def flow_pick_hint(kind: str) -> str:
    return f"已选择图形: {kind}，单击画布放置；双击图形库可直接放到视口中心"


def viewport_center_world(
    *,
    canvas_width: int,
    canvas_height: int,
    zoom: float,
    pan: tuple[float, float],
) -> tuple[float, float]:
    return (canvas_width / 2 - pan[0]) / zoom, (canvas_height / 2 - pan[1]) / zoom


def mousewheel_units(event) -> int:
    if getattr(event, "num", None) == 4:
        return -1
    if getattr(event, "num", None) == 5:
        return 1
    delta = getattr(event, "delta", 0)
    if delta:
        return int(-1 * (delta / 120))
    return 0


def bind_mousewheel_tree(widget: tk.Widget, callback) -> None:
    widget.bind("<MouseWheel>", callback)
    widget.bind("<Button-4>", callback)
    widget.bind("<Button-5>", callback)
    for child in widget.winfo_children():
        bind_mousewheel_tree(child, callback)


def _selected_shapes(document: Document, selected_ids: set[str]) -> list[Shape]:
    return [shape for shape in document.shapes if shape.id in selected_ids]


def _selected_connectors(document: Document, selected_ids: set[str]) -> list[ConnectorShape]:
    return [connector for connector in document.connectors if connector.id in selected_ids]


def connector_endpoint_hit(
    document: Document,
    selected_ids: set[str],
    point: tuple[float, float],
    tolerance: float = 7,
) -> tuple[str, str] | None:
    for connector in _selected_connectors(document, selected_ids):
        endpoint = document.connector_endpoint_at(connector, point, tolerance)
        if endpoint:
            return connector.id, endpoint
    return None


def update_connector_endpoint_anchor(
    document: Document,
    connector_id: str,
    endpoint: str,
    point: tuple[float, float],
) -> bool:
    connector = next((item for item in document.connectors if item.id == connector_id), None)
    if connector is None:
        return False
    target = nearest_flow_shape_for_connector_point(document, point)
    if target is None:
        return False
    anchor = target.edge_anchor_for_point(*point)
    if endpoint == "start":
        connector.start_shape_id = target.id
        connector.start_anchor = anchor
        return True
    if endpoint == "end":
        connector.end_shape_id = target.id
        connector.end_anchor = anchor
        return True
    return False


def nearest_flow_shape_for_connector_point(
    document: Document,
    point: tuple[float, float],
    tolerance: float = 36,
) -> FlowchartShape | None:
    px, py = point
    best: tuple[float, FlowchartShape] | None = None
    for shape in document.shapes:
        if not isinstance(shape, FlowchartShape):
            continue
        x1, y1, x2, y2 = shape.bounds()
        clamped_x = max(x1, min(x2, px))
        clamped_y = max(y1, min(y2, py))
        distance = math.hypot(px - clamped_x, py - clamped_y)
        if best is None or distance < best[0]:
            best = (distance, shape)
    if best and best[0] <= tolerance:
        return best[1]
    return None


def _is_text_capable(shape: Shape) -> bool:
    return isinstance(shape, (FlowchartShape, TextShape))


def inspector_context_for(document: Document, selected_ids: set[str], current_tool: str) -> str:
    if current_tool == "curve" and not selected_ids:
        return "pen"
    if current_tool == "connector" and not selected_ids:
        return "connector_tool"
    selected = _selected_shapes(document, selected_ids)
    if not selected:
        return "canvas"
    if len(selected) > 1:
        return "multi"
    if _is_text_capable(selected[0]):
        return "text_shape"
    return "shape"


def format_status_parts(
    *,
    tool: str,
    zoom: float,
    shape_count: int,
    selection_count: int = 0,
    cursor: tuple[float, float] | None = None,
    hint: str | None = None,
    can_undo: bool = False,
) -> list[str]:
    parts = [
        f"工具: {tool_label(tool)}",
        f"选择: {selection_count if selection_count else '无'}",
        f"缩放: {round(zoom * 100)}%",
        f"图形: {shape_count}",
    ]
    if cursor is not None:
        parts.append(f"坐标: ({round(cursor[0])}, {round(cursor[1])})")
    if can_undo:
        parts.append("可撤销")
    if hint:
        parts.append(hint)
    return parts

# 主题色板：dark 沿用 Tokyo Night Storm，light 用 GitHub Light 风格
THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "root_bg": "#16161E",
        "panel_bg": "#1F2030",
        "panel_elevated": "#25283A",
        "button_bg": "#2A2D3F",
        "button_hover": "#3A3F58",
        "button_pressed": "#414868",
        "tool_selected_bg": "#7AA2F7",
        "tool_selected_fg": "#16161E",
        "accent_bg": "#7AA2F7",
        "accent_hover": "#9AB8F8",
        "accent_pressed": "#5C7BD9",
        "accent_fg": "#16161E",
        "danger_bg": "#F7768E",
        "danger_fg": "#16161E",
        "fg": "#C0CAF5",
        "fg_active": "#FFFFFF",
        "caption": "#565F89",
        "separator": "#414868",
        "border": "#343853",
        "field_bg": "#2A2D3F",
        "canvas_bg": "#16161E",
        "grid": "#2A2A3E",
        "selection": "#5BA8FF",
        "selection_handle_fill": "#1E1E2E",
        "guide": "#FF4444",
        "editor_bg": "#2A2D3F",
        "editor_fg": "#C0CAF5",
        "editor_caret": "#FFFFFF",
        "editor_highlight": "#5BA8FF",
        "sash_hover": "#5BA8FF",
        "toggle_label": "☀ 浅色",
    },
    "light": {
        "root_bg": "#FFFFFF",
        "panel_bg": "#F6F8FA",
        "panel_elevated": "#FFFFFF",
        "button_bg": "#EAEEF2",
        "button_hover": "#D6DCE2",
        "button_pressed": "#B6BFC9",
        "tool_selected_bg": "#0969DA",
        "tool_selected_fg": "#FFFFFF",
        "accent_bg": "#0969DA",
        "accent_hover": "#1F7AED",
        "accent_pressed": "#0851B0",
        "accent_fg": "#FFFFFF",
        "danger_bg": "#CF222E",
        "danger_fg": "#FFFFFF",
        "fg": "#1F2328",
        "fg_active": "#000000",
        "caption": "#656D76",
        "separator": "#D0D7DE",
        "border": "#D0D7DE",
        "field_bg": "#FFFFFF",
        "canvas_bg": "#FCFCFD",
        "grid": "#E5E7EB",
        "selection": "#0969DA",
        "selection_handle_fill": "#FFFFFF",
        "guide": "#E11D48",
        "editor_bg": "#FFFFFF",
        "editor_fg": "#1F2328",
        "editor_caret": "#000000",
        "editor_highlight": "#0969DA",
        "sash_hover": "#0969DA",
        "toggle_label": "☾ 暗色",
    },
}


class VectorFlowApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("VectorFlow - 矢量流程图编辑系统")
        self.geometry("1280x780")
        self.minsize(980, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.document = Document()
        self.file_path: Path | None = None
        self.canvas_renderer: CanvasRenderer | None = None
        self.zoom = 1.0
        self.pan = (40.0, 40.0)
        self.show_grid = tk.BooleanVar(value=True)
        self.animate_connectors = tk.BooleanVar(value=False)
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
        self.rotate_original_bounds: tuple[float, float, float, float] | None = None
        self.rotate_original_payloads: dict[str, dict] = {}
        self.rotate_total_delta = 0.0
        self.connector_endpoint_drag: tuple[str, str] | None = None
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
        self.text_color_var = tk.StringVar(value="#C0CAF5")
        self.text_size_var = tk.IntVar(value=14)
        self.rotate_deg = tk.DoubleVar(value=15)
        self.scale_pct = tk.DoubleVar(value=120)

        # 画笔（曲线工具）独立属性：与图形描边色/线宽完全解耦
        self.pen_color = tk.StringVar(value="#7AA2F7")
        self.pen_width = tk.IntVar(value=2)
        self.pen_dash = tk.StringVar(value="━━ 实线")
        self.pen_smoothness = tk.IntVar(value=3)
        self._pen_panel: tk.Toplevel | None = None

        # 主题：暗色/浅色切换，session 内有效，不持久化
        self.theme_name: str = "dark"
        self.theme_btn_label = tk.StringVar(value=THEMES[self.theme_name]["toggle_label"])
        self._lib_canvases: list[tk.Canvas] = []  # 侧边栏内 tk.Canvas 引用（toggle 时需 reconfigure bg）
        self._tool_buttons: dict[str, ttk.Button] = {}
        self._inspector_frame: ttk.Frame | None = None
        self._inspector_canvas: tk.Canvas | None = None
        self._inspector_context_key: tuple[str, tuple[str, ...], str] | None = None
        self._status_hint: str | None = None

        self._inline_editor: tk.Text | None = None
        self._inline_edit_shape: TextShape | FlowchartShape | None = None
        self._guides: list[tuple[str, float]] = []
        self._space_held: bool = False
        self._space_pan_start: tuple[int, int] | None = None
        self._space_pan_origin: tuple[float, float] | None = None
        self._freehand_points: list[tuple[float, float]] = []
        self._connector_animation_phase: int = 0
        self._connector_animation_after_id: str | None = None
        self._pending_redraw_after_id: str | None = None
        self._pending_redraw_draft: bool = False
        self._replay_sequence: ReplaySequence | None = None
        self._replay_frame: ReplayFrame | None = None
        self._replay_index: int = 0
        self._replay_after_id: str | None = None

        self._configure_style()
        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()
        self._seed_demo()
        # 同步文档背景到当前主题（新会话以暗色启动）
        self.document.background = self._theme()["canvas_bg"]
        self.history.push(self.document.to_dict())
        self.redraw()
        self._schedule_connector_animation()

    def _theme(self) -> dict[str, str]:
        return THEMES[self.theme_name]

    def toggle_theme(self) -> None:
        """在暗色/浅色主题间切换，刷新 ttk Style 和所有直接 reconfigure 的部件。"""
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        th = self._theme()
        self._configure_style()
        self.canvas.configure(bg=th["canvas_bg"])
        if self._inspector_canvas is not None and self._inspector_canvas.winfo_exists():
            self._inspector_canvas.configure(bg=th["panel_bg"])
        if hasattr(self, "_sash") and self._sash.winfo_exists():
            self._sash.configure(bg=th["separator"])
        for cv in self._lib_canvases:
            try:
                cv.configure(bg=th["panel_bg"])
            except tk.TclError:
                pass
        # 文档背景跟随主题；旧文件打开会被覆盖，符合"切到浅色立刻看到白画布"的用户预期
        self.document.background = th["canvas_bg"]
        # inline editor 如果开着也需要换色
        if self._inline_editor is not None and self._inline_editor.winfo_exists():
            self._inline_editor.configure(
                bg=th["editor_bg"], fg=th["editor_fg"],
                insertbackground=th["editor_caret"],
                highlightbackground=th["editor_highlight"],
            )
        # pen panel 颜色硬编码在创建时，关掉让用户重新打开即可
        self._close_pen_panel()
        self.theme_btn_label.set(th["toggle_label"])
        self._update_tool_button_states()
        self._rebuild_inspector(force=True)
        self.redraw()

    def _configure_style(self) -> None:
        # 从主题字典读取所有颜色；toggle_theme 时会重新调用此方法刷新 ttk Style
        th = self._theme()
        self.configure(bg=th["root_bg"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=th["panel_bg"])
        style.configure("App.TFrame", background=th["root_bg"])
        style.configure("Panel.TFrame", background=th["panel_bg"])
        style.configure("Elevated.TFrame", background=th["panel_elevated"])
        style.configure("TLabel", background=th["panel_bg"], foreground=th["fg"])
        style.configure("TButton", background=th["button_bg"], foreground=th["fg"],
                        padding=5, borderwidth=0, focusthickness=0)
        style.configure("Tool.TButton", background=th["button_bg"], foreground=th["fg"],
                        padding=(10, 6), borderwidth=0, focusthickness=0)
        style.configure("SelectedTool.TButton", background=th["tool_selected_bg"], foreground=th["tool_selected_fg"],
                        padding=(10, 6), borderwidth=0, focusthickness=0)
        style.configure("Accent.TButton", background=th["accent_bg"], foreground=th["accent_fg"],
                        padding=(10, 6), borderwidth=0, focusthickness=0)
        style.configure("Danger.TButton", background=th["danger_bg"], foreground=th["danger_fg"],
                        padding=(10, 6), borderwidth=0, focusthickness=0)
        style.configure("TCheckbutton", background=th["panel_bg"], foreground=th["fg"])
        style.configure("TCombobox", fieldbackground=th["field_bg"], foreground=th["fg"])
        style.configure("TSpinbox", fieldbackground=th["field_bg"], foreground=th["fg"])
        style.configure("TSeparator", background=th["separator"])
        style.configure("Group.TLabel", background=th["panel_bg"], foreground=th["caption"],
                        font=("Microsoft YaHei", 8))
        style.map("TButton",
                  background=[("active", th["button_hover"]), ("pressed", th["button_pressed"])],
                  foreground=[("active", th["fg_active"])])
        style.map("Tool.TButton",
                  background=[("active", th["button_hover"]), ("pressed", th["button_pressed"])],
                  foreground=[("active", th["fg_active"])])
        style.map("SelectedTool.TButton",
                  background=[("active", th["tool_selected_bg"]), ("pressed", th["tool_selected_bg"])],
                  foreground=[("active", th["tool_selected_fg"])])
        style.map("Accent.TButton",
                  background=[("active", th["accent_hover"]), ("pressed", th["accent_pressed"])],
                  foreground=[("active", th["accent_fg"])])
        style.map("Danger.TButton",
                  background=[("active", th["danger_bg"]), ("pressed", th["danger_bg"])],
                  foreground=[("active", th["danger_fg"])])

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
        edit_menu.add_command(label="清屏", command=self.clear_canvas)
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
        self._build_command_bar()
        main = ttk.Frame(self, style="App.TFrame")
        main.pack(fill=tk.BOTH, expand=True)
        self._build_left_panel(main)
        self._build_workspace(main)
        self._build_inspector(main)
        self._build_status_bar()
        self._update_tool_button_states()
        self._rebuild_inspector()

    def _build_command_bar(self) -> None:
        bar = ttk.Frame(self, style="Panel.TFrame")
        bar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 3))

        ttk.Button(bar, text="新建", style="Tool.TButton", command=self.new_document).pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Button(bar, text="打开", style="Tool.TButton", command=self.open_document).pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Button(bar, text="保存", style="Accent.TButton", command=self.save_document).pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Button(bar, text="导出 PNG", style="Tool.TButton", command=self.export_png).pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=5)

        self.undo_btn = ttk.Button(bar, text="撤销", style="Tool.TButton", command=self.undo)
        self.undo_btn.pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Button(bar, text="复制", style="Tool.TButton", command=self.copy_selection).pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Button(bar, text="粘贴", style="Tool.TButton", command=self.paste_selection).pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Button(bar, text="算法回放", style="Tool.TButton", command=self.play_algorithm_replay).pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Button(bar, text="清屏", style="Danger.TButton", command=self.clear_canvas).pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=5)

        ttk.Button(bar, textvariable=self.theme_btn_label, style="Tool.TButton", command=self.toggle_theme).pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Checkbutton(bar, text="网格", variable=self.show_grid, command=self.redraw).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Checkbutton(bar, text="流动线", variable=self.animate_connectors,
                        command=self._on_connector_animation_toggle).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(bar, text="100%", style="Tool.TButton", command=self.reset_view).pack(side=tk.LEFT, padx=2, pady=4)

    def _build_left_panel(self, parent: tk.Widget) -> None:
        self._build_tool_rail(parent)
        self._sidebar_width = 180
        lib_container = ttk.Frame(parent, style="Panel.TFrame", width=self._sidebar_width)
        lib_container.pack(side=tk.LEFT, fill=tk.Y)
        lib_container.pack_propagate(False)

        th = self._theme()
        sash = tk.Frame(parent, width=5, bg=th["separator"], cursor="sb_h_double_arrow")
        sash.pack(side=tk.LEFT, fill=tk.Y)
        self._sash = sash

        def _sash_press(event):
            sash._drag_x = event.x_root
            sash._drag_w = lib_container.winfo_width()

        def _sash_drag(event):
            delta = event.x_root - sash._drag_x
            new_w = max(120, min(400, sash._drag_w + delta))
            lib_container.configure(width=new_w)

        sash.bind("<ButtonPress-1>", _sash_press)
        sash.bind("<B1-Motion>", _sash_drag)
        sash.bind("<Enter>", lambda e: sash.configure(bg=self._theme()["sash_hover"]))
        sash.bind("<Leave>", lambda e: sash.configure(bg=self._theme()["separator"]))

        self._build_shape_library(lib_container)

    def _build_tool_rail(self, parent: tk.Widget) -> None:
        rail = ttk.Frame(parent, style="Panel.TFrame", width=76)
        rail.pack(side=tk.LEFT, fill=tk.Y)
        rail.pack_propagate(False)
        for tool, spec in TOOL_SPECS.items():
            label = spec.label if not spec.shortcut else f"{spec.label}\n{spec.shortcut}"
            command = self._on_curve_button if tool == "curve" else (lambda t=tool: self.set_tool(t))
            button = ttk.Button(rail, text=label, style="Tool.TButton", command=command)
            button.pack(fill=tk.X, padx=6, pady=4)
            self._tool_buttons[tool] = button
            if tool == "curve":
                self.curve_btn = button

    def _build_shape_library(self, lib_container: tk.Widget) -> None:
        self.library = ttk.Notebook(lib_container)
        self.library.pack(fill=tk.BOTH, expand=True)

        def _lib_tab(title: str, items: list[tuple[str, str]], extras: list[tuple[str, "callable"]] | None = None) -> None:
            frame = ttk.Frame(self.library)
            self.library.add(frame, text=title)
            canvas_inner = tk.Canvas(frame, bg=self._theme()["panel_bg"], highlightthickness=0)
            self._lib_canvases.append(canvas_inner)
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas_inner.yview)
            canvas_inner.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas_inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            inner = ttk.Frame(canvas_inner)
            win_id = canvas_inner.create_window((0, 0), window=inner, anchor=tk.NW)
            if extras:
                for text, callback in extras:
                    ttk.Button(inner, text=text, style="Accent.TButton", command=callback).pack(fill=tk.X, padx=4, pady=(4, 6))
                ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=4, pady=2)
            for text, kind in items:
                btn = ttk.Button(inner, text=text, command=lambda k=kind: self.pick_flow_shape(k))
                btn.bind("<Double-ButtonRelease-1>", lambda _e, k=kind: (self.place_flow_shape_at_view_center(k), "break")[1])
                btn.pack(fill=tk.X, padx=4, pady=2)
            inner.update_idletasks()
            canvas_inner.configure(scrollregion=canvas_inner.bbox("all"))

            def _on_inner_configure(e):
                canvas_inner.configure(scrollregion=canvas_inner.bbox("all"))
                canvas_inner.itemconfigure(win_id, width=canvas_inner.winfo_width())

            def _on_canvas_configure(e):
                canvas_inner.itemconfigure(win_id, width=e.width)

            inner.bind("<Configure>", _on_inner_configure)
            canvas_inner.bind("<Configure>", _on_canvas_configure)

            # 鼠标滚轮支持
            def _on_mousewheel(e):
                units = mousewheel_units(e)
                if units:
                    canvas_inner.yview_scroll(units, "units")
                return "break"

            canvas_inner.bind("<MouseWheel>", _on_mousewheel)
            canvas_inner.bind("<Button-4>", _on_mousewheel)
            canvas_inner.bind("<Button-5>", _on_mousewheel)
            bind_mousewheel_tree(inner, _on_mousewheel)

        _lib_tab("流程图", [
            ("处理框", "process"), ("判断框", "decision"), ("起止框", "terminal"),
            ("数据框", "data"), ("文档框", "document"), ("数据库", "database"), ("子程序", "subprocess"),
        ])
        _lib_tab("通用图形", [
            ("圆形", "circle"), ("椭圆", "ellipse"), ("三角形", "triangle"),
            ("梯形", "trapezoid"), ("平行四边形", "parallelogram"), ("圆角矩形", "org_box"),
            ("五角星", "star5"), ("六边形", "hexagon"),
            ("右箭头", "arrow_right"), ("左箭头", "arrow_left"), ("加号", "plus"),
        ])
        _lib_tab("电路图", [
            ("电阻", "resistor"), ("电容", "capacitor"), ("接地", "ground"),
            ("电池", "battery"), ("开关", "switch"), ("LED", "led"),
            ("电感", "inductor"), ("电压源", "voltage_source"),
        ], extras=[("📋 加载默认电路", self.load_circuit_template)])

    def _build_workspace(self, parent: tk.Widget) -> None:
        canvas_frame = ttk.Frame(parent, style="App.TFrame")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_frame, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg=self._theme()["canvas_bg"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas_renderer = CanvasRenderer(self.canvas)

    def _build_inspector(self, parent: tk.Widget) -> None:
        container = ttk.Frame(parent, style="Panel.TFrame", width=260)
        container.pack(side=tk.RIGHT, fill=tk.Y)
        container.pack_propagate(False)
        canvas = tk.Canvas(container, bg=self._theme()["panel_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        frame = ttk.Frame(canvas, style="Panel.TFrame")
        win_id = canvas.create_window((0, 0), window=frame, anchor=tk.NW)

        def _on_inner_configure(_event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win_id, width=canvas.winfo_width())

        def _on_canvas_configure(event) -> None:
            canvas.itemconfigure(win_id, width=event.width)

        def _on_mousewheel(event):
            units = mousewheel_units(event)
            if units:
                canvas.yview_scroll(units, "units")
            return "break"

        frame.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", _on_mousewheel)
        canvas.bind("<Button-5>", _on_mousewheel)
        bind_mousewheel_tree(frame, _on_mousewheel)
        self._inspector_canvas = canvas
        self._inspector_frame = frame

    def _build_status_bar(self) -> None:
        status = ttk.Frame(self, style="Panel.TFrame")
        status.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(status, textvariable=self.status_text).pack(side=tk.LEFT, padx=10, pady=5)

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda _e: self.new_document())
        self.bind("<Control-o>", lambda _e: self.open_document())
        self.bind("<Control-s>", lambda _e: self.save_document())
        self.bind("<Control-S>", lambda _e: self.save_document_as())
        self.bind("<Control-e>", lambda _e: self.export_png())
        self.bind("<Control-z>", lambda _e: self.undo())
        self.bind("<Control-c>", lambda _e: self.copy_selection())
        self.bind("<Control-v>", lambda _e: self.paste_selection())
        self.bind("<Delete>", lambda _e: self.delete_selection())
        self.bind("<Escape>", lambda _e: self.clear_selection())
        for key, tool in [("v", "select"), ("l", "line"), ("c", "curve"), ("t", "text"), ("k", "connector")]:
            self.bind(key, lambda _e, t=tool: self.set_tool(t))
        self.bind("<KeyPress-space>", self.on_space_down)
        self.bind("<KeyRelease-space>", self.on_space_up)

    def _seed_demo(self) -> None:
        start = self.document.add_shape(FlowchartShape("terminal", 80, 80, 150, 70, "开始"))
        step = self.document.add_shape(FlowchartShape("process", 320, 80, 170, 70, "处理数据"))
        decision = self.document.add_shape(FlowchartShape("decision", 590, 65, 140, 100, "是否通过?"))
        self.document.add_connector(ConnectorShape(start.id, step.id, "right", "left"))
        self.document.add_connector(ConnectorShape(step.id, decision.id, "right", "left"))

    def load_circuit_template(self) -> None:
        """Replace the canvas with a battery → switch → resistor → LED loop."""
        if self.document.shapes or self.document.connectors:
            if not messagebox.askyesno("加载默认电路", "当前画布将被替换为默认电路模板，是否继续？"):
                return
        self.document.shapes.clear()
        self.document.connectors.clear()
        self.selected_ids.clear()

        style = ShapeStyle(stroke=self.stroke_color.get(), fill=self.fill_color.get(),
                           stroke_width=self.stroke_width.get())
        wire = ShapeStyle(stroke=self.stroke_color.get(), fill=None,
                          stroke_width=self.stroke_width.get())

        # Uniform height (50) + uniform 40px gaps → top-row wires stay flat and
        # the bottom-bottom elbow degenerates into a clean U (no backtracks).
        battery = FlowchartShape("battery", 150, 200, 70, 50, "", style)
        switch = FlowchartShape("switch", 260, 200, 90, 50, "", style)
        resistor = FlowchartShape("resistor", 390, 200, 100, 50, "R", style)
        led = FlowchartShape("led", 530, 200, 110, 50, "", style)
        for shape in (battery, switch, resistor, led):
            self.document.add_shape(shape)

        # Wires carry no arrowheads — circuit diagrams use plain lines.
        def _wire(a, b, sa, ea, kind="straight"):
            return ConnectorShape(a.id, b.id, sa, ea, kind=kind,
                                  arrow_end="none", arrow_start="none", style=wire)

        self.document.add_connector(_wire(battery, switch, "right", "left"))
        self.document.add_connector(_wire(switch, resistor, "right", "left"))
        self.document.add_connector(_wire(resistor, led, "right", "left"))
        self.document.add_connector(_wire(led, battery, "bottom", "bottom", kind="elbow"))

        self._push_history()
        self.redraw()
        self._update_status("已加载默认电路模板（电池 → 开关 → 电阻 → LED）")

    # ── Tool management ─────────────────────────────────────────────

    def _update_tool_button_states(self) -> None:
        active = self.current_tool.get()
        for tool, button in self._tool_buttons.items():
            if button.winfo_exists():
                button.configure(style="SelectedTool.TButton" if tool == active else "Tool.TButton")

    def _rebuild_inspector(self, *, force: bool = False) -> None:
        frame = self._inspector_frame
        if frame is None or not frame.winfo_exists():
            return
        context = inspector_context_for(self.document, self.selected_ids, self.current_tool.get())
        key = (context, tuple(sorted(self.selected_ids)), self.current_tool.get())
        if not force and key == self._inspector_context_key:
            return
        self._inspector_context_key = key
        for child in frame.winfo_children():
            child.destroy()
        if context == "pen":
            self._build_pen_inspector(frame)
        elif context == "connector_tool":
            self._build_connector_inspector(frame)
        elif context == "text_shape":
            self._build_shape_inspector(frame, include_text=True)
        elif context == "shape":
            self._build_shape_inspector(frame, include_text=False)
        elif context == "multi":
            self._build_multi_inspector(frame)
        else:
            self._build_canvas_inspector(frame)
        self._refresh_inspector_scroll_bindings()

    def _refresh_inspector_scroll_bindings(self) -> None:
        if self._inspector_frame is None or self._inspector_canvas is None:
            return

        def _on_mousewheel(event):
            units = mousewheel_units(event)
            if units:
                self._inspector_canvas.yview_scroll(units, "units")
            return "break"

        bind_mousewheel_tree(self._inspector_frame, _on_mousewheel)
        self._inspector_frame.update_idletasks()
        self._inspector_canvas.configure(scrollregion=self._inspector_canvas.bbox("all"))

    def _inspector_title(self, parent: tk.Widget, title: str, caption: str) -> None:
        ttk.Label(parent, text=title, font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 2))
        ttk.Label(parent, text=caption, style="Group.TLabel").pack(anchor=tk.W, padx=12, pady=(0, 8))

    def _inspector_button(self, parent: tk.Widget, text: str, command, style: str = "Tool.TButton") -> None:
        ttk.Button(parent, text=text, style=style, command=command).pack(fill=tk.X, padx=12, pady=3)

    def _inspector_label(self, parent: tk.Widget, text: str) -> None:
        ttk.Label(parent, text=text).pack(anchor=tk.W, padx=12, pady=(8, 2))

    def _sync_style_vars_from_selection(self) -> None:
        for sid in self.selected_ids:
            shape = self.document.find_shape(sid)
            if shape is not None:
                self.stroke_color.set(str(shape.style.stroke or ""))
                self.fill_color.set(str(shape.style.fill or ""))
                self.stroke_width.set(int(shape.style.stroke_width))
                return

    def _build_canvas_inspector(self, parent: tk.Widget) -> None:
        self._inspector_title(parent, "画布", "未选择对象")
        ttk.Checkbutton(parent, text="显示网格", variable=self.show_grid, command=self.redraw).pack(anchor=tk.W, padx=12, pady=3)
        ttk.Checkbutton(parent, text="流动连接线", variable=self.animate_connectors,
                        command=self._on_connector_animation_toggle).pack(anchor=tk.W, padx=12, pady=3)
        self._inspector_button(parent, "重置视图 100%", self.reset_view)
        self._inspector_button(parent, "导出 PNG", self.export_png, "Accent.TButton")

    def _build_pen_inspector(self, parent: tk.Widget) -> None:
        self._inspector_title(parent, "画笔", "仅作用于新绘制曲线")
        ttk.Button(parent, textvariable=self.pen_color, command=self._choose_pen_color).pack(fill=tk.X, padx=12, pady=3)
        self._inspector_label(parent, "线宽")
        ttk.Spinbox(parent, from_=1, to=12, textvariable=self.pen_width, width=8).pack(anchor=tk.W, padx=12, pady=3)
        self._inspector_label(parent, "笔型")
        ttk.Combobox(parent, textvariable=self.pen_dash, values=list(DASH_PRESETS.keys()),
                     state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
        self._inspector_label(parent, "平滑度")
        ttk.Scale(parent, from_=1, to=5, variable=self.pen_smoothness,
                  orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=3)

    def _build_connector_inspector(self, parent: tk.Widget) -> None:
        self._inspector_title(parent, "连接线", "设置新连接线样式")
        self._inspector_label(parent, "线型")
        ttk.Combobox(parent, textvariable=self.conn_kind_var, values=list(CONN_KINDS.keys()),
                     state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
        self._inspector_label(parent, "起点箭头")
        ttk.Combobox(parent, textvariable=self.conn_arrow_start_var, values=list(ARROW_MAP.keys()),
                     state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
        self._inspector_label(parent, "终点箭头")
        ttk.Combobox(parent, textvariable=self.conn_arrow_end_var, values=list(ARROW_MAP.keys()),
                     state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
        self._inspector_label(parent, "线条样式")
        ttk.Combobox(parent, textvariable=self.conn_dash_var, values=list(DASH_PRESETS.keys()),
                     state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)

    def _build_shape_inspector(self, parent: tk.Widget, *, include_text: bool) -> None:
        self._sync_style_vars_from_selection()
        if include_text:
            self._sync_text_vars_from_selection()
        self._inspector_title(parent, "属性", "编辑当前选中图形")
        self._inspector_label(parent, "填充")
        ttk.Button(parent, textvariable=self.fill_color, command=self.choose_fill).pack(fill=tk.X, padx=12, pady=3)
        self._inspector_label(parent, "描边")
        ttk.Button(parent, textvariable=self.stroke_color, command=self.choose_stroke).pack(fill=tk.X, padx=12, pady=3)
        self._inspector_label(parent, "线宽")
        ttk.Spinbox(parent, from_=1, to=12, textvariable=self.stroke_width, width=8).pack(anchor=tk.W, padx=12, pady=3)
        self._inspector_button(parent, "应用图形样式", self.apply_style)
        if include_text:
            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=10)
            self._inspector_label(parent, "文字对齐")
            ttk.Combobox(parent, textvariable=self.text_align_var, values=list(ALIGN_MAP.keys()),
                         state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
            ttk.Checkbutton(parent, text="加粗", variable=self.text_bold_var).pack(anchor=tk.W, padx=12, pady=3)
            self._inspector_label(parent, "文字颜色")
            ttk.Button(parent, textvariable=self.text_color_var, command=self.choose_text_color).pack(fill=tk.X, padx=12, pady=3)
            self._inspector_label(parent, "字号")
            ttk.Spinbox(parent, from_=TEXT_SIZE_MIN, to=TEXT_SIZE_MAX,
                        textvariable=self.text_size_var, width=8).pack(anchor=tk.W, padx=12, pady=3)
            self._inspector_button(parent, "应用文本样式", self.apply_text_style)
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=10)
        self._inspector_button(parent, "旋转", self._do_rotate)
        self._inspector_button(parent, "缩放", self._do_scale)
        self._inspector_button(parent, "水平翻转", self.flip_horizontal)
        self._inspector_button(parent, "垂直翻转", self.flip_vertical)
        self._inspector_button(parent, "复制", self.copy_selection)
        self._inspector_button(parent, "删除", self.delete_selection, "Danger.TButton")

    def _build_multi_inspector(self, parent: tk.Widget) -> None:
        self._sync_style_vars_from_selection()
        self._inspector_title(parent, "多选", f"已选择 {len(self.selected_ids)} 个图形")
        self._inspector_button(parent, "应用图形样式", self.apply_style)
        self._inspector_button(parent, "旋转", self._do_rotate)
        self._inspector_button(parent, "缩放", self._do_scale)
        self._inspector_button(parent, "复制", self.copy_selection)
        self._inspector_button(parent, "删除", self.delete_selection, "Danger.TButton")

    def set_tool(self, tool: str) -> None:
        self._commit_inline_editor()
        self.current_tool.set(tool)
        self._status_hint = tool_hint(tool)
        self.connector_start_id = None
        if self._freehand_points:
            self._freehand_points = []
            self.canvas.delete("preview")
        # 切到非曲线工具时自动收起画笔属性面板
        if tool != "curve":
            self._close_pen_panel()
        self._update_tool_button_states()
        self._rebuild_inspector()
        self._update_status()

    def pick_flow_shape(self, kind: str) -> None:
        self.pending_flow_kind = kind
        self.set_tool("flow")
        self._status_hint = flow_pick_hint(kind)
        self._update_status()

    def place_flow_shape_at_view_center(self, kind: str | None = None) -> None:
        if kind is not None:
            self.pending_flow_kind = kind
        wx, wy = viewport_center_world(
            canvas_width=max(1, self.canvas.winfo_width()),
            canvas_height=max(1, self.canvas.winfo_height()),
            zoom=self.zoom,
            pan=self.pan,
        )
        self.place_flow_shape(wx, wy)
        self._push_history()
        self.set_tool("select")

    # ── Pen panel (curve tool's floating property popup) ────────────

    def _on_curve_button(self) -> None:
        """点曲线按钮：选中曲线工具，同时切换属性面板的开/关状态。"""
        if self._pen_panel is not None and self._pen_panel.winfo_exists():
            self._close_pen_panel()
            return
        self.set_tool("curve")
        self._open_pen_panel(self.curve_btn)

    def _open_pen_panel(self, anchor_btn: tk.Widget) -> None:
        self._close_pen_panel()
        th = self._theme()
        panel = tk.Toplevel(self)
        panel.overrideredirect(True)
        panel.configure(bg=th["panel_bg"], bd=1, relief=tk.SOLID)
        anchor_btn.update_idletasks()
        x = anchor_btn.winfo_rootx()
        y = anchor_btn.winfo_rooty() + anchor_btn.winfo_height() + 2
        panel.geometry(f"320x210+{x}+{y}")

        # 行 0: 颜色
        ttk.Label(panel, text="颜色").grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))
        self._pen_color_btn = tk.Button(
            panel, textvariable=self.pen_color, bg=self.pen_color.get(),
            fg=th["accent_fg"], activebackground=self.pen_color.get(), bd=0,
            font=("Consolas", 9), command=self._choose_pen_color, width=12,
        )
        self._pen_color_btn.grid(row=0, column=1, columnspan=5, sticky=tk.W, padx=4, pady=(10, 4))

        # 行 1: 粗细预设
        ttk.Label(panel, text="粗细").grid(row=1, column=0, sticky=tk.W, padx=10, pady=4)
        for i, w in enumerate([1, 2, 3, 5, 8]):
            ttk.Button(panel, text=str(w), width=3, style="Tool.TButton",
                       command=lambda v=w: self.pen_width.set(v)).grid(row=1, column=1 + i, padx=2)

        # 行 2: 笔型
        ttk.Label(panel, text="笔型").grid(row=2, column=0, sticky=tk.W, padx=10, pady=4)
        ttk.Combobox(panel, textvariable=self.pen_dash,
                     values=list(DASH_PRESETS.keys()),
                     state="readonly", width=14).grid(row=2, column=1, columnspan=5, sticky=tk.W, padx=4)

        # 行 3: 平滑度
        ttk.Label(panel, text="平滑").grid(row=3, column=0, sticky=tk.W, padx=10, pady=4)
        ttk.Scale(panel, from_=1, to=5, variable=self.pen_smoothness,
                  orient=tk.HORIZONTAL, length=200).grid(row=3, column=1, columnspan=5,
                                                         sticky=tk.W, padx=4)
        ttk.Label(panel, text="(硬笔 ←→ 丝滑)",
                  background=th["panel_bg"], foreground=th["caption"],
                  font=("Microsoft YaHei", 8)).grid(row=4, column=1, columnspan=5, sticky=tk.W, padx=4)

        # 行 5: 说明
        ttk.Label(panel, text="画笔属性仅作用于画笔工具",
                  background=th["panel_bg"], foreground=th["caption"],
                  font=("Microsoft YaHei", 8)).grid(row=5, column=0, columnspan=6, pady=(8, 4))

        panel.bind("<Escape>", lambda _e: self._close_pen_panel())
        # 注意：避免 <FocusOut> 关闭面板 —— colorchooser/Combobox 弹出会失焦
        panel.focus_force()
        self._pen_panel = panel

    def _close_pen_panel(self) -> None:
        if self._pen_panel is not None:
            try:
                self._pen_panel.destroy()
            except tk.TclError:
                pass
            self._pen_panel = None

    def _choose_pen_color(self) -> None:
        c = colorchooser.askcolor(color=self.pen_color.get(), parent=self._pen_panel or self)[1]
        if c:
            self.pen_color.set(c)
            if hasattr(self, "_pen_color_btn") and self._pen_color_btn.winfo_exists():
                self._pen_color_btn.configure(bg=c, activebackground=c)

    # ── Rendering ───────────────────────────────────────────────────

    def request_redraw(self, draft: bool = False) -> None:
        self._pending_redraw_draft = self._pending_redraw_draft or draft
        if self._pending_redraw_after_id is not None:
            return
        self._pending_redraw_after_id = self.after_idle(self._flush_pending_redraw)

    def _flush_pending_redraw(self) -> None:
        draft = self._pending_redraw_draft
        self._pending_redraw_after_id = None
        self._pending_redraw_draft = False
        self.redraw(draft=draft)

    def redraw(self, draft: bool = False) -> None:
        if self._pending_redraw_after_id is not None:
            try:
                self.after_cancel(self._pending_redraw_after_id)
            except tk.TclError:
                pass
            self._pending_redraw_after_id = None
            self._pending_redraw_draft = False
        if self.canvas_renderer is None:
            self.canvas_renderer = CanvasRenderer(self.canvas)
        th = self._theme()
        chrome = {
            "grid": th["grid"],
            "selection": th["selection"],
            "selection_handle_fill": th["selection_handle_fill"],
            "guide": th["guide"],
            "connector_flow": "#5BFFCF",
            "replay": "#FFCF5A",
        }
        phase = self._connector_animation_phase if self.animate_connectors.get() else None
        self.canvas_renderer.render(
            self.document,
            self.zoom,
            self.pan,
            self.selected_ids,
            self.show_grid.get(),
            draft=draft,
            guides=self._guides or None,
            chrome=chrome,
            connector_animation_phase=phase,
            replay_frame=self._replay_frame,
        )
        self.canvas.tag_raise("preview")
        self.canvas.tag_raise("inline_editor")
        self._rebuild_inspector()
        self._update_status()

    def _on_connector_animation_toggle(self) -> None:
        if self.animate_connectors.get():
            self._schedule_connector_animation()
        elif self._connector_animation_after_id is not None:
            try:
                self.after_cancel(self._connector_animation_after_id)
            except tk.TclError:
                pass
            self._connector_animation_after_id = None
        self.redraw(draft=True)

    def _schedule_connector_animation(self) -> None:
        if not self.animate_connectors.get():
            return
        if self._connector_animation_after_id is not None:
            return
        self._connector_animation_after_id = self.after(90, self._tick_connector_animation)

    def _tick_connector_animation(self) -> None:
        self._connector_animation_after_id = None
        if self.animate_connectors.get() and self.document.connectors and self._replay_sequence is None:
            self._connector_animation_phase = (self._connector_animation_phase + 2) % 100_000
            self.request_redraw(draft=True)
        self._schedule_connector_animation()

    def play_algorithm_replay(self) -> None:
        if self._replay_sequence is not None:
            self.stop_algorithm_replay()
            return
        shape = self._selected_shape_for_replay()
        if shape is None:
            self._update_status("请先选中一个图形，再点击算法回放")
            return
        self._replay_sequence = build_shape_replay(shape)
        self._replay_index = 0
        self._advance_algorithm_replay()

    def _selected_shape_for_replay(self) -> Shape | None:
        for shape_id in self.selected_ids:
            shape = self.document.find_shape(shape_id)
            if shape is not None:
                return shape
        return None

    def _advance_algorithm_replay(self) -> None:
        self._replay_after_id = None
        sequence = self._replay_sequence
        if sequence is None:
            return
        if self._replay_index >= len(sequence.frames):
            self._replay_after_id = self.after(650, self.stop_algorithm_replay)
            return
        self._replay_frame = sequence.frames[self._replay_index]
        current = self._replay_index + 1
        total = len(sequence.frames)
        self._replay_index += 1
        self.request_redraw(draft=True)
        self.status_text.set(f"算法回放: {sequence.title} | {self._replay_frame.label} {current}/{total}")
        self._replay_after_id = self.after(70, self._advance_algorithm_replay)

    def stop_algorithm_replay(self, redraw: bool = True) -> None:
        if self._replay_after_id is not None:
            try:
                self.after_cancel(self._replay_after_id)
            except tk.TclError:
                pass
        had_replay = self._replay_sequence is not None or self._replay_frame is not None
        self._replay_after_id = None
        self._replay_sequence = None
        self._replay_frame = None
        self._replay_index = 0
        if redraw and had_replay:
            self.redraw(draft=True)

    def _on_close(self) -> None:
        self.stop_algorithm_replay(redraw=False)
        if self._connector_animation_after_id is not None:
            try:
                self.after_cancel(self._connector_animation_after_id)
            except tk.TclError:
                pass
            self._connector_animation_after_id = None
        if self._pending_redraw_after_id is not None:
            try:
                self.after_cancel(self._pending_redraw_after_id)
            except tk.TclError:
                pass
            self._pending_redraw_after_id = None
        self.destroy()

    def _update_status(self, msg: str | None = None) -> None:
        self.undo_btn.config(state=tk.NORMAL if self.history.can_undo else tk.DISABLED)
        if msg:
            self.status_text.set(msg)
            return
        parts = format_status_parts(
            tool=self.current_tool.get(),
            zoom=self.zoom,
            shape_count=len(self.document.shapes),
            selection_count=len(self.selected_ids),
            hint=self._status_hint or tool_hint(self.current_tool.get()),
            can_undo=self.history.can_undo,
        )
        self.status_text.set(" | ".join(parts))

    # ── Mouse events ────────────────────────────────────────────────

    def on_canvas_resize(self, _event) -> None:
        self.request_redraw(draft=True)

    def on_mouse_move(self, event) -> None:
        if self._space_held and self._space_pan_start is not None and self._space_pan_origin is not None:
            dx = event.x - self._space_pan_start[0]
            dy = event.y - self._space_pan_start[1]
            self.pan = (self._space_pan_origin[0] + dx, self._space_pan_origin[1] + dy)
            self.request_redraw(draft=True)
            return
        x, y = self.screen_to_world(event.x, event.y)
        self.status_text.set(" | ".join(format_status_parts(
            tool=self.current_tool.get(),
            zoom=self.zoom,
            shape_count=len(self.document.shapes),
            selection_count=len(self.selected_ids),
            cursor=(x, y),
            hint=self._status_hint or tool_hint(self.current_tool.get()),
            can_undo=self.history.can_undo,
        )))

    def on_left_down(self, event) -> None:
        if self._inline_editor:
            self._commit_inline_editor()
            return
        self.stop_algorithm_replay(redraw=False)
        if self._space_held:
            self._space_pan_start = (event.x, event.y)
            self._space_pan_origin = self.pan
            return
        self.drag_start = self.screen_to_world(event.x, event.y)
        self.drag_mode = None
        tool = self.current_tool.get()

        if tool == "select":
            endpoint_hit = connector_endpoint_hit(self.document, self.selected_ids, self.drag_start, tolerance=8 / self.zoom)
            if endpoint_hit:
                self.drag_mode = "connector_endpoint"
                self.connector_endpoint_drag = endpoint_hit
                self.redraw()
                return

            selected_bounds = selection_bounds(self.document, self.selected_ids)
            rh = handle_at(selected_bounds, self.drag_start, tolerance=8 / self.zoom, rotation_offset=30 / self.zoom)
            if rh:
                if rh == "rotate":
                    self.drag_mode = "rotate"
                    self.rotate_original_bounds = selected_bounds
                    self.rotate_original_payloads = {s.id: s.to_dict() for s in self.document.shapes if s.id in self.selected_ids}
                    self.rotate_total_delta = 0.0
                else:
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
                connector = self.document.connector_at(*self.drag_start, tolerance=8 / self.zoom)
                if connector:
                    self.selected_ids = {connector.id}
                    self.drag_mode = "connector_select"
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
                self._status_hint = "拖拽到目标图形以创建连接线"
                self.redraw()

        elif tool == "region_export":
            self._status_hint = "拖拽选择导出区域"
            self._update_status()

        elif tool == "line":
            # Snap the start point to a nearby anchor if there is one.
            self.drag_start = self._snap_to_anchor(*self.drag_start)

        elif tool == "curve":
            self._freehand_points = [self.drag_start]
            self.drag_mode = "curve_trace"

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
            guides, snap_dx, snap_dy = compute_guides(self.selected_ids, self.document.shapes)
            if snap_dx or snap_dy:
                self.document.move_shapes(list(self.selected_ids), snap_dx, snap_dy)
                self.drag_shape_origin = (current[0] + snap_dx, current[1] + snap_dy)
                self.drag_total_delta = (self.drag_total_delta[0] + snap_dx, self.drag_total_delta[1] + snap_dy)
            self._guides = guides
            self.request_redraw(draft=True)
        elif tool == "select" and self.drag_mode == "resize" and self.resize_handle:
            new_bounds = bounds_from_handle(self.resize_original_bounds, self.resize_handle, current)
            apply_group_resize(self.document, self.selected_ids, self.resize_original_payloads, self.resize_original_bounds, new_bounds)
            self.request_redraw(draft=True)
        elif tool == "select" and self.drag_mode == "rotate":
            self.rotate_total_delta = rotation_delta(self.rotate_original_bounds, self.drag_start, current)
            apply_group_rotation(
                self.document,
                self.selected_ids,
                self.rotate_original_payloads,
                self.rotate_original_bounds,
                self.rotate_total_delta,
            )
            self.request_redraw(draft=True)
        elif tool == "select" and self.drag_mode == "connector_endpoint" and self.connector_endpoint_drag:
            connector_id, endpoint = self.connector_endpoint_drag
            update_connector_endpoint_anchor(self.document, connector_id, endpoint, current)
            self.request_redraw(draft=True)
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
        elif tool in {"line", "region_export", "curve"}:
            if tool == "curve":
                last = self._freehand_points[-1] if self._freehand_points else self.drag_start
                if (current[0] - last[0]) ** 2 + (current[1] - last[1]) ** 2 >= 9:
                    self._freehand_points.append(current)
                self._render_freehand_preview()
                return
            self.canvas.delete("preview")
            x0, y0 = self.world_to_screen(self.drag_start)
            if tool == "line":
                snapped = self._snap_to_anchor(*current)
                sx, sy = self.world_to_screen(snapped)
                self.canvas.create_line(x0, y0, sx, sy, fill="#FFCF5A", dash=(4, 3), tags="preview")
                if snapped != current:
                    # Indicate the snapped endpoint with a small dot.
                    self.canvas.create_oval(sx - 4, sy - 4, sx + 4, sy + 4,
                                            outline="#5BFFCF", width=2, tags="preview")
            else:
                x1, y1 = self.world_to_screen(current)
                self.canvas.create_rectangle(x0, y0, x1, y1, outline="#5AFF8A", dash=(4, 3), width=2, tags="preview")

    def on_left_up(self, event) -> None:
        if self.drag_start is None:
            return
        current = self.screen_to_world(event.x, event.y)
        tool = self.current_tool.get()
        self._guides = []  # clear alignment guides on mouse release

        if tool == "line":
            ex, ey = self._snap_to_anchor(*current)
            style = ShapeStyle(stroke=self.stroke_color.get(), fill=None, stroke_width=self.stroke_width.get())
            self.document.add_shape(LineShape(self.drag_start[0], self.drag_start[1], ex, ey, style=style))
            self._push_history()
            self.canvas.delete("preview")
            self.redraw()
        elif tool == "curve":
            pts = list(self._freehand_points)
            if pts and pts[-1] != current:
                pts.append(current)
            self._freehand_points = []
            self.canvas.delete("preview")
            if len(pts) >= 2:
                dash = DASH_PRESETS.get(self.pen_dash.get(), [])
                style = ShapeStyle(
                    stroke=self.pen_color.get(),
                    fill=None,
                    stroke_width=self.pen_width.get(),
                    dash=dash,
                    smoothness=self.pen_smoothness.get(),
                )
                self.document.add_shape(CurveShape(points=pts, style=style))
                self._push_history()
                self._status_hint = f"画笔轨迹已创建（{len(pts)} 个采样点）"
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
            elif self.drag_mode in {"move", "resize", "rotate", "connector_endpoint"}:
                self._push_history()
            self.redraw()

        self.drag_start = None
        self.drag_shape_origin = None
        self.drag_total_delta = (0.0, 0.0)
        self.drag_mode = None
        self.resize_handle = None
        self.resize_original_bounds = None
        self.resize_original_payloads = {}
        self.rotate_original_bounds = None
        self.rotate_original_payloads = {}
        self.rotate_total_delta = 0.0
        self.connector_endpoint_drag = None

    def on_double_click(self, event) -> None:
        point = self.screen_to_world(event.x, event.y)
        shape = self.document.shape_at(*point)
        if isinstance(shape, (FlowchartShape, TextShape)):
            self._open_inline_editor_for_shape(shape)

    def on_space_down(self, event) -> None:
        if not self._space_held:
            self._space_held = True
            self.canvas.config(cursor="fleur")

    def on_space_up(self, event) -> None:
        self._space_held = False
        self._space_pan_start = None
        self._space_pan_origin = None
        self.canvas.config(cursor="crosshair")

    def on_pan_start(self, event) -> None:
        self.drag_start = (event.x, event.y)

    def on_pan_drag(self, event) -> None:
        if self.drag_start is None:
            return
        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]
        self.pan = (self.pan[0] + dx, self.pan[1] + dy)
        self.drag_start = (event.x, event.y)
        self.request_redraw(draft=True)

    def on_mouse_wheel(self, event) -> None:
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        world_before = self.screen_to_world(event.x, event.y)
        self.zoom = max(0.1, min(8.0, self.zoom * factor))
        sx, sy = self.world_to_screen(world_before)
        self.pan = (self.pan[0] + event.x - sx, self.pan[1] + event.y - sy)
        self.redraw()

    # ── Shape creation ──────────────────────────────────────────────

    def place_flow_shape(self, x: float, y: float) -> None:
        dims = {
            "decision": (140, 100), "terminal": (150, 70), "database": (150, 90),
            "document": (160, 90), "data": (160, 70),
            # General shapes
            "circle": (100, 100), "ellipse": (140, 90), "star5": (100, 100),
            "hexagon": (110, 100), "arrow_right": (140, 80),
            "arrow_left": (140, 80),
            "triangle": (110, 100), "trapezoid": (140, 90),
            "parallelogram": (150, 80), "plus": (100, 100),
            # Org chart
            "org_box": (160, 70),
            # Circuit symbols (bbox includes short leads on each side)
            "resistor": (100, 40), "capacitor": (60, 60), "ground": (70, 60),
            "battery": (70, 50), "switch": (90, 40), "led": (110, 60),
            "inductor": (120, 50), "voltage_source": (80, 80),
        }
        labels = {
            "process": "处理", "decision": "判断", "terminal": "开始/结束",
            "data": "数据", "document": "文档", "database": "数据库", "subprocess": "子程序",
            "circle": "", "ellipse": "", "star5": "", "hexagon": "", "arrow_right": "",
            "arrow_left": "",
            "triangle": "", "trapezoid": "", "parallelogram": "", "plus": "",
            "org_box": "",
            "resistor": "R", "capacitor": "C", "ground": "", "battery": "",
            "switch": "", "led": "", "inductor": "L", "voltage_source": "V",
        }
        w, h = dims.get(self.pending_flow_kind, (160, 70))
        shape = FlowchartShape(
            self.pending_flow_kind, x - w / 2, y - h / 2, w, h,
            labels.get(self.pending_flow_kind, "图元"),
            ShapeStyle(stroke=self.stroke_color.get(), fill=self.fill_color.get(), stroke_width=self.stroke_width.get()),
        )
        self.document.add_shape(shape)
        self.selected_ids = {shape.id}
        self.redraw()

    def _render_freehand_preview(self) -> None:
        if len(self._freehand_points) < 2:
            return
        smoothed = catmull_rom_polyline(self._freehand_points)
        flat: list[float] = []
        for px, py in smoothed:
            sx, sy = self.world_to_screen((px, py))
            flat.extend((sx, sy))
        self.canvas.delete("preview")
        if len(flat) >= 4:
            self.canvas.create_line(*flat, fill="#5BFFCF", width=2, tags="preview")

    def _snap_to_anchor(self, x: float, y: float, threshold: float = 16.0) -> tuple[float, float]:
        """Return the closest FlowchartShape anchor within threshold (world units), or (x, y) unchanged."""
        best: tuple[float, float] | None = None
        best_dist = threshold
        for shape in self.document.shapes:
            if not isinstance(shape, FlowchartShape):
                continue
            for ax, ay in shape.anchors().values():
                d = math.hypot(ax - x, ay - y)
                if d < best_dist:
                    best_dist = d
                    best = (ax, ay)
        return best if best is not None else (x, y)

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
        self._create_text_widget(int(sx), int(sy), initial_text, wx, wy, self.text_size_var.get())

    def _open_inline_editor_for_shape(self, shape: FlowchartShape | TextShape) -> None:
        self._sync_text_vars_from_shape(shape)
        if isinstance(shape, FlowchartShape):
            bounds = shape.bounds()
            cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
            sx, sy = self.world_to_screen((cx, cy))
            self._inline_edit_shape = shape
            self._create_text_widget(int(sx) - 60, int(sy) - 12, shape.text, cx, cy, shape.style.font_size)
        elif isinstance(shape, TextShape):
            sx, sy = self.world_to_screen((shape.x, shape.y))
            self._inline_edit_shape = shape
            self._create_text_widget(int(sx), int(sy), shape.text, shape.x, shape.y, shape.style.font_size)

    def _create_text_widget(self, sx: int, sy: int, text: str, wx: float, wy: float, font_size: int | float | None = None) -> None:
        if self._inline_editor:
            self._commit_inline_editor()
        th = self._theme()
        editor_size = clamp_font_size(font_size if font_size is not None else self.text_size_var.get())
        editor_size = clamp_font_size(editor_size * self.zoom)
        editor = tk.Text(
            self.canvas, width=22, height=3, wrap=tk.WORD,
            bg=th["editor_bg"], fg=th["editor_fg"], insertbackground=th["editor_caret"],
            font=("Microsoft YaHei", editor_size), relief=tk.SOLID, bd=1,
            highlightbackground=th["editor_highlight"], highlightthickness=2,
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
            style = ShapeStyle(
                fill=None,
                text_color=self.text_color_var.get(),
                text_align=align,
                bold=self.text_bold_var.get(),
                font_size=clamp_font_size(self.text_size_var.get()),
            )
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
        renderer = Renderer(w, h)
        img = renderer.render(self.document, self.zoom, self.pan, set(), self.show_grid.get())
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
        changed = apply_text_style_to_shapes(
            self.document.shapes,
            self.selected_ids,
            align=align,
            bold=self.text_bold_var.get(),
            color=self.text_color_var.get(),
            font_size=self.text_size_var.get(),
        )
        if changed:
            self.text_size_var.set(clamp_font_size(self.text_size_var.get()))
            self._push_history()
            self.redraw()

    def _adjust_text_size(self, delta: int) -> None:
        self.text_size_var.set(clamp_font_size(self.text_size_var.get() + delta))
        if self.selected_ids:
            self.apply_text_style()

    def _sync_text_vars_from_shape(self, shape: FlowchartShape | TextShape) -> None:
        inverse_align = {value: key for key, value in ALIGN_MAP.items()}
        self.text_align_var.set(inverse_align.get(shape.style.text_align, "居中"))
        self.text_bold_var.set(bool(shape.style.bold))
        self.text_color_var.set(str(shape.style.text_color or "#C0CAF5"))
        self.text_size_var.set(clamp_font_size(shape.style.font_size))

    def _sync_text_vars_from_selection(self) -> None:
        for sid in self.selected_ids:
            shape = self.document.find_shape(sid)
            if isinstance(shape, (FlowchartShape, TextShape)):
                self._sync_text_vars_from_shape(shape)
                return

    # ── Property Dialogs ────────────────────────────────────────────

    def open_style_dialog(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("图形样式")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        pad = dict(padx=12, pady=4)
        ttk.Label(dlg, text="描边色").grid(row=0, column=0, sticky=tk.W, **pad)
        ttk.Button(dlg, textvariable=self.stroke_color, command=self.choose_stroke, width=14).grid(row=0, column=1, **pad)
        ttk.Label(dlg, text="填充色").grid(row=1, column=0, sticky=tk.W, **pad)
        ttk.Button(dlg, textvariable=self.fill_color, command=self.choose_fill, width=14).grid(row=1, column=1, **pad)
        ttk.Label(dlg, text="线宽").grid(row=2, column=0, sticky=tk.W, **pad)
        ttk.Spinbox(dlg, from_=1, to=12, textvariable=self.stroke_width, width=6).grid(row=2, column=1, sticky=tk.W, **pad)
        ttk.Button(dlg, text="应用样式", command=lambda: (self.apply_style(), dlg.destroy())).grid(row=3, column=0, columnspan=2, pady=8)

    def open_connector_dialog(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("连接线样式")
        dlg.resizable(False, False)
        dlg.lift()
        dlg.focus_force()

        def make_radio_group(parent, label: str, var: tk.StringVar, options: list[str], row: int) -> None:
            ttk.Label(parent, text=label, font=("", 9, "bold")).grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(8, 2))
            for i, opt in enumerate(options):
                ttk.Radiobutton(parent, text=opt, variable=var, value=opt).grid(
                    row=row + 1 + i // 2, column=i % 2, sticky=tk.W, padx=16, pady=1
                )

        r = 0
        make_radio_group(dlg, "线型", self.conn_kind_var, list(CONN_KINDS.keys()), r)
        r += 1 + (len(CONN_KINDS) + 1) // 2
        make_radio_group(dlg, "终点箭头", self.conn_arrow_end_var, list(ARROW_MAP.keys()), r)
        r += 1 + (len(ARROW_MAP) + 1) // 2
        make_radio_group(dlg, "起点箭头", self.conn_arrow_start_var, list(ARROW_MAP.keys()), r)
        r += 1 + (len(ARROW_MAP) + 1) // 2
        make_radio_group(dlg, "线条样式", self.conn_dash_var, list(DASH_PRESETS.keys()), r)
        r += 1 + (len(DASH_PRESETS) + 1) // 2
        ttk.Button(dlg, text="关闭", command=dlg.destroy).grid(row=r, column=0, columnspan=2, pady=10)

    def open_text_dialog(self) -> None:
        self._sync_text_vars_from_selection()
        dlg = tk.Toplevel(self)
        dlg.title("文本样式")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        pad = dict(padx=12, pady=5)
        ttk.Label(dlg, text="对齐").grid(row=0, column=0, sticky=tk.W, **pad)
        ttk.Combobox(dlg, textvariable=self.text_align_var, values=list(ALIGN_MAP.keys()), state="readonly", width=14).grid(row=0, column=1, **pad)
        ttk.Label(dlg, text="加粗").grid(row=1, column=0, sticky=tk.W, **pad)
        ttk.Checkbutton(dlg, variable=self.text_bold_var).grid(row=1, column=1, sticky=tk.W, **pad)
        ttk.Label(dlg, text="文字颜色").grid(row=2, column=0, sticky=tk.W, **pad)
        ttk.Button(dlg, textvariable=self.text_color_var, command=self.choose_text_color, width=14).grid(row=2, column=1, **pad)
        ttk.Label(dlg, text="字号").grid(row=3, column=0, sticky=tk.W, **pad)
        size_row = ttk.Frame(dlg)
        size_row.grid(row=3, column=1, sticky=tk.W, **pad)
        ttk.Button(size_row, text="A-", width=3, command=lambda: self._adjust_text_size(-2)).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Spinbox(
            size_row,
            from_=TEXT_SIZE_MIN,
            to=TEXT_SIZE_MAX,
            textvariable=self.text_size_var,
            width=5,
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(size_row, text="A+", width=3, command=lambda: self._adjust_text_size(2)).pack(side=tk.LEFT)
        ttk.Button(dlg, text="应用文本样式", command=lambda: (self.apply_text_style(), dlg.destroy())).grid(row=4, column=0, columnspan=2, pady=8)

    def open_transform_dialog(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("变换")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        pad = dict(padx=12, pady=5)
        ttk.Label(dlg, text="旋转角度°").grid(row=0, column=0, sticky=tk.W, **pad)
        ttk.Spinbox(dlg, from_=-360, to=360, textvariable=self.rotate_deg, width=7).grid(row=0, column=1, sticky=tk.W, **pad)
        ttk.Button(dlg, text="旋转", command=self._do_rotate).grid(row=0, column=2, padx=4, pady=5)
        ttk.Label(dlg, text="缩放比例%").grid(row=1, column=0, sticky=tk.W, **pad)
        ttk.Spinbox(dlg, from_=10, to=500, textvariable=self.scale_pct, width=7).grid(row=1, column=1, sticky=tk.W, **pad)
        ttk.Button(dlg, text="缩放", command=self._do_scale).grid(row=1, column=2, padx=4, pady=5)
        flip_frame = ttk.Frame(dlg)
        flip_frame.grid(row=2, column=0, columnspan=3, pady=6, padx=12)
        ttk.Button(flip_frame, text="水平翻转", command=self.flip_horizontal).pack(side=tk.LEFT, padx=4)
        ttk.Button(flip_frame, text="垂直翻转", command=self.flip_vertical).pack(side=tk.LEFT, padx=4)
        ttk.Button(dlg, text="关闭", command=dlg.destroy).grid(row=3, column=0, columnspan=3, pady=8)

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
        self.stop_algorithm_replay(redraw=False)
        self.selected_ids.clear()
        self.connector_start_id = None
        if self._freehand_points:
            self._freehand_points = []
            self.canvas.delete("preview")
            self._status_hint = "已取消画笔绘制"
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

    def clear_canvas(self) -> None:
        if not messagebox.askyesno("清屏确认", "确定要清除所有图形吗？此操作可撤销。"):
            return
        self.document.shapes.clear()
        self.document.connectors.clear()
        self.selected_ids.clear()
        self._push_history()
        self.redraw()
        self._update_status("已清屏")

    # ── Transforms ──────────────────────────────────────────────────

    def _do_rotate(self) -> None:
        deg = self.rotate_deg.get()
        self._rotate_selected_by(deg)
        if self.selected_ids:
            self._push_history()
            self.redraw()

    def _rotate_selected_by(self, deg: float) -> None:
        for sid in self.selected_ids:
            shape = self.document.find_shape(sid)
            if shape and hasattr(shape, "rotate"):
                shape.rotate(deg)

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
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        image = Renderer(width, height).render(self.document, self.zoom, self.pan, set(), self.show_grid.get())
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
