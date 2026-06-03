# Vector Editor UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn VectorFlow into a professional desktop vector editor shell with a command bar, left tool rail, context-aware inspector, and clearer status feedback.

**Architecture:** Keep the first implementation scoped to `src/app.py` and add pure helper functions that can be unit tested without creating a tkinter window. The existing renderer, document model, algorithms, serializer, and editing handlers remain the behavioral source of truth.

**Tech Stack:** Python 3, tkinter/ttk, Pillow, unittest.

---

## File Structure

- Modify: `src/app.py`
  - Add UI metadata helpers: theme token checks, tool specs, inspector context classification, status formatting.
  - Expand `THEMES` and ttk style names.
  - Split `_build_layout()` into command bar, left panel, workspace, inspector, and status bar builders.
  - Add right inspector rebuild and action helpers.
  - Update `set_tool()`, `redraw()`, selection-changing handlers, and status calls to keep tool state and inspector state current.
- Create: `tests/test_ui_shell.py`
  - Test pure UI metadata and context helpers.
  - Avoid constructing `VectorFlowApp`, because tkinter windows are display-dependent.
- No planned changes:
  - `core/*`
  - `engine/*`
  - `algorithms/*`
  - `io_utils/*`

---

### Task 1: Add Failing UI Shell Tests

**Files:**
- Create: `tests/test_ui_shell.py`

- [ ] **Step 1: Write the failing test**

Add this file:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import (
    REQUIRED_THEME_TOKENS,
    THEMES,
    TOOL_SPECS,
    format_status_parts,
    inspector_context_for,
    missing_theme_tokens,
    tool_hint,
)
from core.document import Document
from core.shapes import CurveShape, FlowchartShape, LineShape, TextShape


class UiShellTests(unittest.TestCase):
    def test_themes_define_required_editor_tokens(self):
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                self.assertEqual(missing_theme_tokens(theme), [])
                self.assertTrue(REQUIRED_THEME_TOKENS.issubset(theme.keys()))

    def test_tool_specs_cover_expected_tool_rail(self):
        self.assertEqual(
            list(TOOL_SPECS.keys()),
            ["select", "line", "curve", "text", "connector", "region_export"],
        )
        self.assertEqual(TOOL_SPECS["select"].shortcut, "V")
        self.assertIn("拖拽", tool_hint("connector"))
        self.assertIn("区域", TOOL_SPECS["region_export"].label)

    def test_inspector_context_tracks_tool_and_selection(self):
        document = Document()
        flow = document.add_shape(FlowchartShape("process", 0, 0, 100, 60, "处理"))
        text = document.add_shape(TextShape(20, 20, "说明"))
        line = document.add_shape(LineShape(0, 0, 50, 50))
        curve = document.add_shape(CurveShape(points=[(0, 0), (20, 20), (40, 0)]))

        self.assertEqual(inspector_context_for(document, set(), "select"), "canvas")
        self.assertEqual(inspector_context_for(document, set(), "curve"), "pen")
        self.assertEqual(inspector_context_for(document, set(), "connector"), "connector_tool")
        self.assertEqual(inspector_context_for(document, {flow.id}, "select"), "text_shape")
        self.assertEqual(inspector_context_for(document, {text.id}, "select"), "text_shape")
        self.assertEqual(inspector_context_for(document, {line.id}, "select"), "shape")
        self.assertEqual(inspector_context_for(document, {curve.id}, "select"), "shape")
        self.assertEqual(inspector_context_for(document, {flow.id, line.id}, "select"), "multi")

    def test_status_parts_include_tool_selection_zoom_and_hint(self):
        parts = format_status_parts(
            tool="select",
            zoom=1.25,
            shape_count=4,
            selection_count=2,
            cursor=(12.4, 98.6),
            hint="拖拽移动选中图形",
            can_undo=True,
        )

        self.assertEqual(parts[0], "工具: 选择")
        self.assertIn("选择: 2", parts)
        self.assertIn("缩放: 125%", parts)
        self.assertIn("图形: 4", parts)
        self.assertIn("坐标: (12, 99)", parts)
        self.assertIn("可撤销", parts)
        self.assertEqual(parts[-1], "拖拽移动选中图形")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m unittest tests.test_ui_shell -v
```

Expected: FAIL or ERROR because `REQUIRED_THEME_TOKENS`, `TOOL_SPECS`, `format_status_parts`, `inspector_context_for`, `missing_theme_tokens`, and `tool_hint` are not defined in `app.py`.

- [ ] **Step 3: Commit**

Do not commit the failing test alone unless pausing the work. Continue directly to Task 2.

---

### Task 2: Implement Testable UI Metadata Helpers

**Files:**
- Modify: `src/app.py`
- Test: `tests/test_ui_shell.py`

- [ ] **Step 1: Add imports and helper definitions near the constants in `src/app.py`**

Add `dataclass` to imports:

```python
from dataclasses import dataclass
```

Add these definitions after `ALIGN_MAP`:

```python
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


def _selected_shapes(document: Document, selected_ids: set[str]) -> list[Shape]:
    return [shape for shape in document.shapes if shape.id in selected_ids]


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
```

- [ ] **Step 2: Expand both theme dictionaries**

For the dark theme, add:

```python
"panel_elevated": "#25283A",
"tool_selected_bg": "#7AA2F7",
"tool_selected_fg": "#16161E",
"danger_bg": "#F7768E",
"danger_fg": "#16161E",
"border": "#343853",
```

For the light theme, add:

```python
"panel_elevated": "#FFFFFF",
"tool_selected_bg": "#0969DA",
"tool_selected_fg": "#FFFFFF",
"danger_bg": "#CF222E",
"danger_fg": "#FFFFFF",
"border": "#D0D7DE",
```

- [ ] **Step 3: Run the focused test**

Run:

```powershell
python -m unittest tests.test_ui_shell -v
```

Expected: PASS, 4 tests.

- [ ] **Step 4: Run the full test suite**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: PASS for all existing and new tests.

- [ ] **Step 5: Commit**

```powershell
git add src\app.py tests\test_ui_shell.py
git commit -m "test: cover editor shell metadata"
```

---

### Task 3: Expand ttk Styles And Active Tool State

**Files:**
- Modify: `src/app.py`
- Test: `tests/test_ui_shell.py`

- [ ] **Step 1: Add style configuration in `_configure_style()`**

Extend `_configure_style()` with these style names:

```python
style.configure("App.TFrame", background=th["root_bg"])
style.configure("Panel.TFrame", background=th["panel_bg"])
style.configure("Elevated.TFrame", background=th["panel_elevated"])
style.configure("SelectedTool.TButton", background=th["tool_selected_bg"], foreground=th["tool_selected_fg"],
                padding=(10, 6), borderwidth=0, focusthickness=0)
style.configure("Danger.TButton", background=th["danger_bg"], foreground=th["danger_fg"],
                padding=(10, 6), borderwidth=0, focusthickness=0)
style.map("SelectedTool.TButton",
          background=[("active", th["tool_selected_bg"]), ("pressed", th["tool_selected_bg"])],
          foreground=[("active", th["tool_selected_fg"])])
style.map("Danger.TButton",
          background=[("active", th["danger_bg"]), ("pressed", th["danger_bg"])],
          foreground=[("active", th["danger_fg"])])
```

- [ ] **Step 2: Add active tool button tracking in `__init__()`**

Add after `_lib_canvases`:

```python
self._tool_buttons: dict[str, ttk.Button] = {}
self._inspector_frame: ttk.Frame | None = None
self._status_hint: str | None = None
```

- [ ] **Step 3: Add `_update_tool_button_states()`**

Add near tool management methods:

```python
def _update_tool_button_states(self) -> None:
    active = self.current_tool.get()
    for tool, button in self._tool_buttons.items():
        if button.winfo_exists():
            button.configure(style="SelectedTool.TButton" if tool == active else "Tool.TButton")
```

- [ ] **Step 4: Update `set_tool()`**

After `self.current_tool.set(tool)`, call:

```python
self._status_hint = tool_hint(tool)
```

Before returning from `set_tool()`, call:

```python
self._update_tool_button_states()
self._rebuild_inspector()
self._update_status()
```

Remove the direct `self.status_text.set(f"当前工具: {tool}")` line.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m unittest tests.test_ui_shell -v
```

Expected: PASS, 4 tests.

- [ ] **Step 6: Commit**

```powershell
git add src\app.py
git commit -m "feat: add editor tool state metadata"
```

---

### Task 4: Refactor Main Layout Into Professional Editor Regions

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Replace `_build_layout()` with region orchestration**

Change `_build_layout()` to:

```python
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
```

- [ ] **Step 2: Add `_build_command_bar()`**

Use the existing command callbacks and group them into one compact top row:

```python
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
    ttk.Button(bar, text="算法回放", style="Tool.TButton", command=self.play_algorithm_replay).pack(side=tk.LEFT, padx=2, pady=4)
    ttk.Button(bar, text="清屏", style="Danger.TButton", command=self.clear_canvas).pack(side=tk.LEFT, padx=2, pady=4)
    ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=5)

    ttk.Button(bar, textvariable=self.theme_btn_label, style="Tool.TButton", command=self.toggle_theme).pack(side=tk.LEFT, padx=2, pady=4)
    ttk.Checkbutton(bar, text="网格", variable=self.show_grid, command=self.redraw).pack(side=tk.LEFT, padx=6, pady=4)
    ttk.Checkbutton(bar, text="流动线", variable=self.animate_connectors,
                    command=self._on_connector_animation_toggle).pack(side=tk.LEFT, padx=6, pady=4)
    ttk.Button(bar, text="100%", style="Tool.TButton", command=self.reset_view).pack(side=tk.LEFT, padx=2, pady=4)
```

- [ ] **Step 3: Add `_build_left_panel()` and `_build_tool_rail()`**

Move the existing sidebar sash and notebook creation into `_build_left_panel(parent)`. Add a tool rail before the library:

```python
def _build_tool_rail(self, parent: tk.Widget) -> None:
    rail = ttk.Frame(parent, style="Panel.TFrame", width=72)
    rail.pack(side=tk.LEFT, fill=tk.Y)
    rail.pack_propagate(False)
    for tool, spec in TOOL_SPECS.items():
        label = spec.label if not spec.shortcut else f"{spec.label}\n{spec.shortcut}"
        button = ttk.Button(rail, text=label, style="Tool.TButton", command=lambda t=tool: self.set_tool(t))
        button.pack(fill=tk.X, padx=6, pady=4)
        self._tool_buttons[tool] = button
```

Inside `_build_left_panel(parent)`, call `_build_tool_rail(parent)` first, then create the existing resizable library container and move the current `_lib_tab()` implementation into `_build_shape_library(lib_container)`.

- [ ] **Step 4: Add `_build_workspace()`**

Move the existing canvas creation and bindings into:

```python
def _build_workspace(self, parent: tk.Widget) -> None:
    canvas_frame = ttk.Frame(parent, style="App.TFrame")
    canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    self.canvas = tk.Canvas(canvas_frame, width=CANVAS_WIDTH, height=CANVAS_HEIGHT,
                            bg=self._theme()["canvas_bg"], highlightthickness=0)
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
```

- [ ] **Step 5: Add `_build_status_bar()`**

Move existing status creation into:

```python
def _build_status_bar(self) -> None:
    status = ttk.Frame(self, style="Panel.TFrame")
    status.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Label(status, textvariable=self.status_text).pack(side=tk.LEFT, padx=10, pady=5)
```

- [ ] **Step 6: Run full tests**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src\app.py
git commit -m "feat: refactor editor shell layout"
```

---

### Task 5: Add Context Inspector UI

**Files:**
- Modify: `src/app.py`
- Test: `tests/test_ui_shell.py`

- [ ] **Step 1: Add `_build_inspector()`**

```python
def _build_inspector(self, parent: tk.Widget) -> None:
    self._inspector_frame = ttk.Frame(parent, style="Panel.TFrame", width=260)
    self._inspector_frame.pack(side=tk.RIGHT, fill=tk.Y)
    self._inspector_frame.pack_propagate(False)
```

- [ ] **Step 2: Add inspector widget helpers**

```python
def _clear_inspector(self) -> ttk.Frame | None:
    frame = self._inspector_frame
    if frame is None or not frame.winfo_exists():
        return None
    for child in frame.winfo_children():
        child.destroy()
    return frame

def _inspector_title(self, parent: tk.Widget, title: str, caption: str) -> None:
    ttk.Label(parent, text=title, font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 2))
    ttk.Label(parent, text=caption, style="Group.TLabel").pack(anchor=tk.W, padx=12, pady=(0, 8))

def _inspector_button(self, parent: tk.Widget, text: str, command, style: str = "Tool.TButton") -> None:
    ttk.Button(parent, text=text, style=style, command=command).pack(fill=tk.X, padx=12, pady=3)
```

- [ ] **Step 3: Add `_rebuild_inspector()` dispatcher**

```python
def _rebuild_inspector(self) -> None:
    frame = self._clear_inspector()
    if frame is None:
        return
    context = inspector_context_for(self.document, self.selected_ids, self.current_tool.get())
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
```

- [ ] **Step 4: Add canvas and pen inspector sections**

```python
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
    ttk.Label(parent, text="线宽").pack(anchor=tk.W, padx=12, pady=(8, 2))
    ttk.Spinbox(parent, from_=1, to=12, textvariable=self.pen_width, width=8).pack(anchor=tk.W, padx=12, pady=3)
    ttk.Label(parent, text="笔型").pack(anchor=tk.W, padx=12, pady=(8, 2))
    ttk.Combobox(parent, textvariable=self.pen_dash, values=list(DASH_PRESETS.keys()),
                 state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
    ttk.Label(parent, text="平滑度").pack(anchor=tk.W, padx=12, pady=(8, 2))
    ttk.Scale(parent, from_=1, to=5, variable=self.pen_smoothness,
              orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=3)
```

- [ ] **Step 5: Add connector and shape inspector sections**

Add connector controls for active connector settings:

```python
def _build_connector_inspector(self, parent: tk.Widget) -> None:
    self._inspector_title(parent, "连接线", "设置新连接线样式")
    ttk.Combobox(parent, textvariable=self.conn_kind_var, values=list(CONN_KINDS.keys()),
                 state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
    ttk.Combobox(parent, textvariable=self.conn_arrow_start_var, values=list(ARROW_MAP.keys()),
                 state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
    ttk.Combobox(parent, textvariable=self.conn_arrow_end_var, values=list(ARROW_MAP.keys()),
                 state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
    ttk.Combobox(parent, textvariable=self.conn_dash_var, values=list(DASH_PRESETS.keys()),
                 state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
```

Add shape controls:

```python
def _build_shape_inspector(self, parent: tk.Widget, *, include_text: bool) -> None:
    self._sync_text_vars_from_selection()
    self._inspector_title(parent, "属性", "编辑当前选中图形")
    ttk.Button(parent, textvariable=self.fill_color, command=self.choose_fill).pack(fill=tk.X, padx=12, pady=3)
    ttk.Button(parent, textvariable=self.stroke_color, command=self.choose_stroke).pack(fill=tk.X, padx=12, pady=3)
    ttk.Label(parent, text="线宽").pack(anchor=tk.W, padx=12, pady=(8, 2))
    ttk.Spinbox(parent, from_=1, to=12, textvariable=self.stroke_width, width=8).pack(anchor=tk.W, padx=12, pady=3)
    self._inspector_button(parent, "应用图形样式", self.apply_style)
    if include_text:
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=10)
        ttk.Combobox(parent, textvariable=self.text_align_var, values=list(ALIGN_MAP.keys()),
                     state="readonly", width=18).pack(fill=tk.X, padx=12, pady=3)
        ttk.Checkbutton(parent, text="加粗", variable=self.text_bold_var).pack(anchor=tk.W, padx=12, pady=3)
        ttk.Button(parent, textvariable=self.text_color_var, command=self.choose_text_color).pack(fill=tk.X, padx=12, pady=3)
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
```

- [ ] **Step 6: Add multi-selection inspector**

```python
def _build_multi_inspector(self, parent: tk.Widget) -> None:
    self._inspector_title(parent, "多选", f"已选择 {len(self.selected_ids)} 个图形")
    self._inspector_button(parent, "应用图形样式", self.apply_style)
    self._inspector_button(parent, "旋转", self._do_rotate)
    self._inspector_button(parent, "缩放", self._do_scale)
    self._inspector_button(parent, "复制", self.copy_selection)
    self._inspector_button(parent, "删除", self.delete_selection, "Danger.TButton")
```

- [ ] **Step 7: Rebuild inspector after selection changes**

Call `_rebuild_inspector()` after code paths that change `selected_ids`, including:

- `clear_selection()`
- `paste_selection()`
- `delete_selection()`
- `new_document()`
- `open_document()`
- `load_circuit_template()`
- mouse handlers after single selection, empty selection, region selection, connector selection start, and drag release.

The safe pattern is:

```python
self._rebuild_inspector()
self.redraw()
```

Use the existing order when a method already pushes history before redraw.

- [ ] **Step 8: Run tests**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add src\app.py
git commit -m "feat: add context inspector"
```

---

### Task 6: Centralize Status Feedback

**Files:**
- Modify: `src/app.py`
- Test: `tests/test_ui_shell.py`

- [ ] **Step 1: Update `_update_status()`**

Replace its computed branch with:

```python
parts = format_status_parts(
    tool=self.current_tool.get(),
    zoom=self.zoom,
    shape_count=len(self.document.shapes),
    selection_count=len(self.selected_ids),
    hint=self._status_hint or tool_hint(self.current_tool.get()),
    can_undo=self.history.can_undo,
)
self.status_text.set(" | ".join(parts))
```

Keep this early return:

```python
if msg:
    self.status_text.set(msg)
    return
```

- [ ] **Step 2: Update `on_mouse_move()`**

Replace the direct status string with:

```python
self.status_text.set(" | ".join(format_status_parts(
    tool=self.current_tool.get(),
    zoom=self.zoom,
    shape_count=len(self.document.shapes),
    selection_count=len(self.selected_ids),
    cursor=(x, y),
    hint=self._status_hint or tool_hint(self.current_tool.get()),
    can_undo=self.history.can_undo,
)))
```

- [ ] **Step 3: Set contextual hints in mouse handlers**

Before the existing direct messages, set `_status_hint` so the next redraw keeps useful guidance:

```python
self._status_hint = "拖拽到目标图形以创建连接线"
self._status_hint = "拖拽选择导出区域"
self._status_hint = f"画笔轨迹已创建（{len(pts)} 个采样点）"
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m unittest tests.test_ui_shell -v
python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src\app.py
git commit -m "feat: improve editor status feedback"
```

---

### Task 7: Smoke Check And Polish

**Files:**
- Modify only if smoke check finds a concrete issue.

- [ ] **Step 1: Run full tests**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 2: Launch the app**

Run:

```powershell
python src/main.py
```

Expected:

- Window opens with command bar, left tool rail, shape library, canvas, right inspector, and status bar.
- Selecting tools updates button state and inspector context.
- Selecting a shape shows shape controls.
- Selecting text-capable shapes shows text controls.
- Pen tool shows pen controls.
- Connector tool shows connector controls.
- Existing shortcuts still work: `V`, `L`, `C`, `T`, `K`, `Ctrl+S`, `Ctrl+Z`, `Delete`.

- [ ] **Step 3: Fix smoke issues using TDD where possible**

If a smoke issue is in pure helper behavior, add or update a test in `tests/test_ui_shell.py`, run it red, then fix.

If a smoke issue is display-only tkinter layout behavior, make the smallest UI-only correction and rerun:

```powershell
python src/main.py
```

- [ ] **Step 4: Run final verification**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit final polish if anything changed**

```powershell
git add src\app.py tests\test_ui_shell.py
git commit -m "fix: polish editor shell smoke issues"
```

---

## Self-Review

- Spec coverage: command bar is Task 4; left tool rail and library are Task 4; canvas preservation is Task 4; inspector is Task 5; status bar is Task 6; theme tokens are Task 2 and Task 3; testing is Tasks 1, 2, 6, and 7.
- Placeholder scan: no unresolved placeholder entries are present.
- Type consistency: helper names used in tests match helper names defined in Task 2. Inspector context names are `canvas`, `pen`, `connector_tool`, `shape`, `text_shape`, and `multi`.
- Scope check: connector controls cover the active connector tool. Selecting existing connectors is not added because current selection state only tracks shape IDs; adding connector hit-testing is a separate behavior change.
