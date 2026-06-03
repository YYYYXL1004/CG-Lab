# Vector Editor UI Redesign Design

Date: 2026-06-03

## Goal

Refactor VectorFlow into a modern professional desktop vector editor while preserving the existing renderer, document model, graphics algorithms, file format, and editing behavior.

The selected direction is a Figma / diagrams.net style editor shell:

- A compact command bar for global actions.
- A left vertical tool rail plus the existing shape library.
- The canvas as the primary workspace.
- A context-aware right inspector for routine editing.
- A richer status bar for current tool, selection, zoom, and operation hints.

The redesign emphasizes two kinds of "smart" behavior:

- Contextual controls: the editor shows relevant properties for the active tool or current selection.
- Clear feedback: the editor makes the active tool, selection state, and next expected action visible.

## Current Context

The application is a Python/tkinter desktop app. `src/app.py` currently owns the main window, menu, toolbar, left library, canvas, dialogs, event bindings, status text, theme setup, and most UI mutation methods.

Core behavior is already separated:

- `core/*`: document and shape model.
- `engine/*`: renderer, history, selection, animation, replay, guides.
- `algorithms/*`: pixel-level graphics algorithms.
- `io_utils/*`: `.vflow` serialization.

The UI refactor should stay primarily in `src/app.py`. Core modules should not change unless a small helper is required to keep the UI correct.

## Approach Considered

Three approaches were considered:

1. Keep tkinter and modernize the editor shell.
   - Recommended and selected.
   - Keeps risk low and preserves the existing course-project constraints.
   - Allows meaningful workflow improvements without rewriting the app.

2. Split the UI into a new `src/ui/` package.
   - Cleaner long-term structure.
   - Higher implementation risk because the current event flow is concentrated in `VectorFlowApp`.
   - Better as a follow-up after the first shell refactor is stable.

3. Only refresh visual styling.
   - Fastest.
   - Does not solve the modal-dialog-heavy workflow or weak active-state feedback.
   - Not enough for the requested modern and intelligent feel.

## Layout

The redesigned editor uses five persistent regions.

### Command Bar

The command bar replaces the older grouped top toolbar with a cleaner, denser global action row.

It contains:

- File actions: new, open, save, export PNG.
- Edit actions: undo, clear, copy, paste, delete where appropriate.
- Replay action: algorithm replay.
- View actions: theme toggle, grid toggle, animated connector toggle, reset view.

Primary actions use restrained accent styling. Destructive actions use a danger style where tkinter styling supports it.

### Left Tool Rail And Shape Library

The left side is split into two parts:

- A narrow vertical rail for editing tools: select, line, pen, text, connector, region export.
- The existing shape library, kept in tabs for flowchart, general shapes, and circuit symbols.

The rail gives each tool a persistent active state. Tool selection still calls the existing `set_tool()` path so keyboard shortcuts and event handlers keep working.

The shape library remains resizable and scrollable. It should not become a decorative card layout; it should stay compact and task-focused.

### Canvas Workspace

The canvas remains the center of the application.

Existing behavior stays unchanged:

- Grid rendering.
- Zoom and pan.
- Selection handles.
- Smart guides.
- Connector animation.
- Algorithm replay overlay.
- Inline text editing.
- Region export selection.

The visual frame around the canvas can be improved with cleaner spacing and panel separators, but the renderer remains the source of the actual document image.

### Context Inspector

The right inspector is the main workflow upgrade. It rebuilds based on active context:

- No selection: canvas and view controls.
- Pen tool active: pen color, width, dash preset, and smoothness.
- Single ordinary shape selected: fill, stroke, line width, rotate, scale, flip, copy, delete.
- Text-capable shape selected: text color, font size, bold, and alignment in addition to shape controls.
- Connector selected: route kind, start arrow, end arrow, dash preset, stroke, width.
- Multiple shapes selected: batch style actions, transform actions, copy, delete.

Routine edits should not require pressing a separate "Apply" button when the change can safely be applied immediately. Existing mutation methods should be reused or factored into helpers so history snapshots are still pushed correctly.

Existing dialogs can remain as fallback advanced commands during the first implementation, but the primary path should move into the inspector.

### Status Bar

The status bar shows:

- Active tool.
- Selection count.
- Zoom level.
- Shape count.
- Cursor world position during movement.
- Short operation hint.

Examples:

- `Tool: Select | Selection: 2 | Zoom: 100% | Drag to move or use handles to resize`
- `Tool: Connector | Selection: none | Drag from one shape to another`
- `Tool: Pen | Samples: 18 | Release to create a smoothed curve`

Status updates should be centralized so handlers do not produce inconsistent phrasing.

## Visual System

The existing `THEMES` dictionary remains the source of truth and should be expanded rather than replaced.

Required tokens:

- application background
- panel background
- elevated panel background
- button background
- button hover background
- button pressed background
- selected tool background
- selected tool foreground
- accent background
- accent foreground
- danger background
- danger foreground
- primary text
- secondary text
- separator
- border
- field background
- canvas background
- grid
- selection
- selection handle fill
- guide

The target visual direction is a compact professional editor interface: neutral surfaces, clear state, restrained accent color, and predictable controls. It should avoid decorative landing-page styling, oversized headers, gradients, and card-heavy composition.

## Component Boundaries

The first pass keeps the implementation inside `VectorFlowApp` but splits large UI construction into focused methods:

- `_build_command_bar()`
- `_build_left_panel()`
- `_build_tool_rail()`
- `_build_shape_library()`
- `_build_workspace()`
- `_build_inspector()`
- `_build_status_bar()`
- `_rebuild_inspector()`
- `_inspector_context()`
- `_update_tool_button_states()`
- `_format_status()`

This is a contained refactor. A later pass can extract reusable widgets into `src/ui/` after behavior is stable.

## Data Flow

Tool selection flow:

1. User clicks a tool rail button or presses a shortcut.
2. `set_tool(tool)` updates `current_tool`.
3. Tool button selected states refresh.
4. Inspector rebuilds if the tool changes the editing context.
5. Status text updates with the active tool and hint.

Selection flow:

1. Mouse interaction updates `selected_ids`.
2. `redraw()` refreshes the canvas.
3. Inspector rebuilds based on selection type.
4. Status text reports selection count and active context.

Inspector mutation flow:

1. User edits a property control.
2. The relevant existing style, text, connector, or transform method mutates selected shapes.
3. The history snapshot is pushed once per committed change.
4. Canvas redraws.
5. Inspector values stay in sync with the selected object.

## Error Handling

The refactor should preserve existing dialog-based error behavior for file operations and export failures.

Inspector actions should fail quietly but visibly when no target is available:

- Disabled controls are preferred for impossible actions.
- If a user-triggered action cannot run, status text should explain why.
- Invalid numeric values should be clamped using existing helpers where available, such as text size clamping.

The UI must not mutate document state when an inspector control has no valid selection target.

## Testing

Existing tests must continue to pass:

```powershell
python -m unittest discover -s tests -v
```

New tests should focus on pure or low-UI helper behavior:

- Theme token completeness for both light and dark themes.
- Inspector context classification for no selection, single shape, multiple shapes, connector, and pen tool.
- Tool metadata contains labels, shortcuts, and status hints.
- Status formatting includes tool, selection count, zoom, and hint.

Tkinter rendering and widget layout will be verified with a local application smoke check where a display is available:

```powershell
python src/main.py
```

## Risks

- `src/app.py` is large, so the refactor should be incremental and scoped.
- Tkinter has limited styling capabilities, so the improvement should come mostly from layout, density, state clarity, and workflow.
- Immediate inspector edits can accidentally push too many history snapshots if every intermediate widget update commits state. Spinboxes and comboboxes should commit on explicit selection/change events, not uncontrolled variable traces.
- Rebuilding the inspector during selection changes must not interfere with inline text editing or drag operations.

## Out Of Scope

- Rewriting the renderer.
- Rewriting the app in Qt, web, or another toolkit.
- Changing `.vflow` serialization.
- Adding AI-generated diagram content.
- Changing graphics algorithms.
- Redesigning shape geometry or connector routing.
- Moving the whole UI to `src/ui/` in the first pass.

## Spec Self-Review

- Placeholder scan: no TBD, TODO, or unfinished sections remain.
- Consistency check: the selected approach, layout, component boundaries, and testing strategy all target a tkinter shell refactor.
- Scope check: this is a single implementation plan focused on UI shell, inspector, and status feedback.
- Ambiguity check: "modern and intelligent" is defined as professional editor layout, contextual controls, and clearer feedback.
