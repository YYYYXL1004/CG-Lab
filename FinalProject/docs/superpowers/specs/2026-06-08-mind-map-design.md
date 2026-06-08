# Mind Map Feature Design

Date: 2026-06-08

## Goal

Add a mind map workflow to VectorFlow that can generate an editable mind map from heading-style text and then let the user continue editing it on the canvas with add-child controls, manual dragging, and subtree collapse.

The selected direction is to reuse the existing vector editor model:

- Each mind map node is a normal `FlowchartShape`.
- Each parent-child edge is a normal `ConnectorShape`.
- Mind map behavior is stored as optional metadata on nodes and connectors.
- Existing selection, dragging, text editing, styling, undo, save/load, PNG export, and SVG export continue to work.

## Current Context

VectorFlow is a Python/tkinter desktop vector editor. `src/app.py` owns the UI, command bar, canvas events, dialogs, inspector, layer panel, and most interaction state.

Reusable foundations already exist:

- `core.shapes.FlowchartShape` for editable node boxes.
- `core.shapes.ConnectorShape` for routed parent-child edges.
- `core.document.Document` for shape storage, connector lookup, copy/paste, z-order, grouping, and serialization.
- `engine.canvas_renderer.CanvasRenderer` for live canvas drawing.
- `io_utils.serializer` for `.vflow` persistence.
- `engine.command.History` for snapshot undo.

The feature should avoid adding a separate mind map canvas or a monolithic mind map shape. That would duplicate editing behavior and make export/save integration weaker.

## Approach Considered

Three approaches were considered.

1. Reuse existing shapes and connectors with light mind map metadata.
   - Selected.
   - Keeps nodes fully editable and movable.
   - Preserves existing save, load, export, selection, dragging, and style workflows.
   - Requires a small metadata extension and visibility handling for collapsed subtrees.

2. Add a dedicated `MindMapShape` that owns an internal tree.
   - Centralizes layout and collapse logic.
   - Makes individual node editing, connectors, layer ordering, export, grouping, and undo harder to integrate.
   - Too much parallel behavior for this project.

3. Generate plain flowchart nodes without storing parent-child relationships.
   - Fastest for import.
   - Cannot reliably support add-child controls or subtree collapse after generation.
   - Not enough for the requested interactive workflow.

## Feature Scope

The first version includes:

- A command bar action named "Mind Map".
- A dialog for heading-style input.
- Heading syntax parsing where `#` is the root, `##` is a child, `###` is a deeper child, and so on.
- A generated radial left/right layout with the root at the viewport center.
- Mind map nodes that remain normal editable shapes after generation.
- A visible plus control for selected or hovered mind map nodes to add a child node.
- A fold control for mind map nodes that have children.
- Subtree collapse and expand.
- Undo support for generate, add child, collapse, and expand.
- Save/load support through existing `.vflow` JSON.

The first version does not include automatic relayout after manual dragging. Once the user moves nodes, positions are respected.

## Input Format

The import dialog accepts heading-style text:

```text
# Center Topic
## Branch One
### Child Topic
## Branch Two
```

Parsing rules:

- Empty lines are ignored.
- A heading line must start with one or more `#` characters followed by at least one space and text.
- The first valid line must be level 1 and becomes the root.
- A child may increase by only one level from its parent path. For example, `#`, then `###` is invalid because `##` is missing.
- Duplicate titles are allowed because identity is stored by shape ID, not title.
- Invalid input is rejected with a dialog message and no document mutation.

## Layout

The generated layout is center-out:

- The root node is placed at the current viewport center.
- First-level branches are split evenly between the right and left sides.
- Each side stacks its branches vertically.
- Deeper descendants extend outward from their parent side.
- Sibling spacing grows with subtree size to reduce overlap.

Default sizing:

- Root node: wider and stronger fill.
- Child nodes: compact rounded rectangles.
- Connectors: light curved or elbow connectors with arrow disabled or subdued.

The layout output is only an initial placement. After generation, users can drag nodes normally.

## Data Model

Each mind map node is a `FlowchartShape` with optional metadata:

```python
metadata = {
    "mindmap_id": "mindmap_xxx",
    "mindmap_parent_id": "shape_xxx",
    "mindmap_collapsed": False,
    "mindmap_side": "left" | "right" | "root",
}
```

The root uses an empty parent ID and side `root`.

Each mind map connector uses optional metadata:

```python
metadata = {
    "mindmap_id": "mindmap_xxx",
    "mindmap_parent_id": "shape_xxx",
    "mindmap_child_id": "shape_yyy",
}
```

`FlowchartShape` and `ConnectorShape` need `metadata: dict[str, str | bool]` or a small normalized equivalent in serialization. Missing metadata means the shape is a normal non-mind-map object.

## Interaction

### Generate

The user clicks "Mind Map", enters heading text, and confirms. The app parses the text, builds nodes/connectors, adds them to the document, selects the root, pushes history, and redraws.

### Add Child

When a mind map node is selected or hovered, a small plus control appears near the outward side of the node:

- Root: plus appears on the right by default.
- Left-side node: plus appears to the left.
- Right-side node: plus appears to the right.

Clicking plus adds a child node with default text "New Topic". The new node is placed near the clicked parent on the same side, connected to the parent, selected for immediate editing, and recorded in undo history.

### Collapse

A fold control appears on mind map nodes that have children:

- `-` means expanded.
- `+` means collapsed.

Clicking it toggles `mindmap_collapsed` on that node. All descendant nodes and descendant connectors are hidden when collapsed. The node itself remains visible.

Collapse is visual state, not deletion. Expanding restores the same descendant positions.

## Rendering And Hit Testing

The live canvas should draw mind map controls after document rendering:

- Plus control: small circle with `+`.
- Fold control: small square or circle with `+` / `-`.

Control hit testing should happen before normal shape hit testing so clicking a control does not start a drag.

Collapsed descendants should be skipped by renderers and selection hit testing. The safest first implementation is to toggle existing `visible` flags on descendant shapes and maintain a small internal map to restore visibility on expand. If this conflicts with user-controlled layer visibility, implement render-time hidden ID filtering instead.

Because user visibility is already a layer feature, the implementation should avoid permanently overwriting non-mind-map visibility where practical.

## Component Boundaries

Add a focused core module:

- `src/core/mindmap.py`
  - Parse heading text.
  - Represent parsed tree nodes.
  - Create a `Document` fragment or shape/connector lists.
  - Compute initial positions.
  - Query children and descendants from metadata.
  - Compute collapsed hidden IDs.

Keep UI-specific behavior in `VectorFlowApp`:

- Dialog construction.
- Button wiring.
- Canvas overlay control drawing.
- Overlay hit testing.
- Selection/editing integration.
- Status text.

Minimal model changes:

- Add `metadata` serialization to `FlowchartShape`.
- Add `metadata` serialization to `ConnectorShape`.

## Error Handling

Invalid import input should show a concise dialog:

- No root heading.
- First heading is not level 1.
- Heading level jumps by more than one.
- Empty heading text.

Add-child should fail visibly in the status bar if the selected shape is not a mind map node.

Collapse should do nothing if the node has no children.

Loading older `.vflow` files must keep working because missing metadata defaults to `{}`.

## Testing

Use focused unit tests for pure behavior:

```powershell
python -m unittest discover -s tests -v
```

New tests should cover:

- Heading parser accepts valid `#` / `##` / `###` input.
- Heading parser rejects missing roots and skipped levels.
- Generated mind map creates expected node count, connector count, root metadata, child metadata, and side assignment.
- Collapse hidden-ID calculation hides descendants but not the collapsed node.
- Shape and connector metadata round-trips through `Document.to_dict()` and `Document.from_dict()`.

Manual smoke check:

```powershell
python src/main.py
```

Verify:

- "Mind Map" opens the dialog.
- Heading input generates nodes around the viewport center.
- Nodes can be dragged after generation.
- Plus adds a child node.
- Fold hides and restores descendants.
- Save and reopen keeps mind map behavior.

## Risks

- `src/app.py` is large, so UI changes should be tightly scoped.
- Existing layer visibility can conflict with collapse visibility if collapse directly mutates `visible`.
- Canvas overlay controls must not interfere with drag, resize, connector creation, or inline text editing.
- Automatic layout is only initial placement; users may expect full relayout after add-child. The first version should make manual dragging the supported adjustment path.

## Out Of Scope

- AI-generated mind map content.
- Markdown list import.
- Top-down or left-to-right layout options.
- Full automatic relayout after manual edits.
- Dragging entire subtrees as a special operation.
- Rich node templates, icons, progress markers, or priority tags.
- A separate mind map editing surface.

## Spec Self-Review

- Placeholder scan: no TBD, TODO, or unfinished sections remain.
- Consistency check: the selected approach, data model, interaction, and testing strategy all rely on reusable shapes/connectors plus metadata.
- Scope check: this is a single implementation plan covering parser, generation, controls, collapse, persistence, tests, and UI wiring.
- Ambiguity check: input format, layout direction, add-child behavior, collapse semantics, and first-version exclusions are explicit.
