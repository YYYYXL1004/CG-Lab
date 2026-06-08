import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.document import Document
from core.shapes import ConnectorShape, FlowchartShape


class MindMapTests(unittest.TestCase):
    def test_flowchart_and_connector_metadata_round_trip(self):
        document = Document()
        root = document.add_shape(
            FlowchartShape(
                "org_box",
                100,
                100,
                150,
                56,
                "Root",
                metadata={
                    "mindmap_id": "mindmap_1",
                    "mindmap_parent_id": "",
                    "mindmap_collapsed": False,
                    "mindmap_side": "root",
                },
            )
        )
        child = document.add_shape(
            FlowchartShape(
                "org_box",
                300,
                100,
                130,
                48,
                "Child",
                metadata={
                    "mindmap_id": "mindmap_1",
                    "mindmap_parent_id": root.id,
                    "mindmap_collapsed": True,
                    "mindmap_side": "right",
                },
            )
        )
        document.add_connector(
            ConnectorShape(
                root.id,
                child.id,
                metadata={
                    "mindmap_id": "mindmap_1",
                    "mindmap_parent_id": root.id,
                    "mindmap_child_id": child.id,
                },
            )
        )

        restored = Document.from_dict(document.to_dict())

        restored_root = restored.find_shape(root.id)
        restored_child = restored.find_shape(child.id)
        self.assertEqual(restored_root.metadata["mindmap_side"], "root")
        self.assertFalse(restored_root.metadata["mindmap_collapsed"])
        self.assertEqual(restored_child.metadata["mindmap_parent_id"], root.id)
        self.assertTrue(restored_child.metadata["mindmap_collapsed"])
        self.assertEqual(restored.connectors[0].metadata["mindmap_child_id"], child.id)

    def test_parse_heading_text_builds_tree(self):
        from core.mindmap import parse_heading_text

        root = parse_heading_text(
            """
            # Project
            ## Research
            ### Papers
            ## Build
            """
        )

        self.assertEqual(root.title, "Project")
        self.assertEqual([child.title for child in root.children], ["Research", "Build"])
        self.assertEqual(root.children[0].children[0].title, "Papers")

    def test_parse_heading_text_rejects_missing_root_and_skipped_levels(self):
        from core.mindmap import MindMapParseError, parse_heading_text

        with self.assertRaisesRegex(MindMapParseError, "first heading must be level 1"):
            parse_heading_text("## Missing root")

        with self.assertRaisesRegex(MindMapParseError, "cannot jump"):
            parse_heading_text("# Root\n### Skipped")

        with self.assertRaisesRegex(MindMapParseError, "heading text cannot be empty"):
            parse_heading_text("# ")

    def test_build_mindmap_fragment_creates_nodes_connectors_and_sides(self):
        from core.mindmap import build_mindmap_fragment, parse_heading_text

        root = parse_heading_text(
            "# Root\n"
            "## Right A\n"
            "### Right A Child\n"
            "## Left B\n"
            "## Right C\n"
        )

        nodes, connectors = build_mindmap_fragment(root, center=(500, 400), mindmap_id="mindmap_test")

        self.assertEqual(len(nodes), 5)
        self.assertEqual(len(connectors), 4)
        root_node = nodes[0]
        self.assertEqual(root_node.text, "Root")
        self.assertEqual(root_node.metadata["mindmap_side"], "root")
        self.assertEqual(root_node.metadata["mindmap_parent_id"], "")
        first_level_sides = [
            node.metadata["mindmap_side"]
            for node in nodes[1:]
            if node.metadata["mindmap_parent_id"] == root_node.id
        ]
        self.assertIn("right", first_level_sides)
        self.assertIn("left", first_level_sides)
        self.assertTrue(all(connector.metadata["mindmap_id"] == "mindmap_test" for connector in connectors))

    def test_collapsed_hidden_ids_include_descendants_and_connectors(self):
        from core.mindmap import build_mindmap_fragment, collapsed_hidden_ids, parse_heading_text

        document = Document()
        tree = parse_heading_text("# Root\n## Branch\n### Leaf\n## Other")
        nodes, connectors = build_mindmap_fragment(tree, center=(0, 0), mindmap_id="mindmap_test")
        for node in nodes:
            document.add_shape(node)
        for connector in connectors:
            document.add_connector(connector)
        branch = next(node for node in nodes if node.text == "Branch")
        leaf = next(node for node in nodes if node.text == "Leaf")
        branch.metadata["mindmap_collapsed"] = True

        hidden_shapes, hidden_connectors = collapsed_hidden_ids(document)

        self.assertNotIn(branch.id, hidden_shapes)
        self.assertIn(leaf.id, hidden_shapes)
        self.assertTrue(hidden_connectors)

    def test_add_mindmap_child_places_child_on_parent_side(self):
        from core.mindmap import add_mindmap_child, build_mindmap_fragment, parse_heading_text

        document = Document()
        tree = parse_heading_text("# Root\n## Branch")
        nodes, connectors = build_mindmap_fragment(tree, center=(500, 400), mindmap_id="mindmap_test")
        for node in nodes:
            document.add_shape(node)
        for connector in connectors:
            document.add_connector(connector)
        branch = next(
            node
            for node in document.shapes
            if isinstance(node, FlowchartShape) and node.text == "Branch"
        )

        child = add_mindmap_child(document, branch.id, title="New Topic")

        self.assertEqual(child.metadata["mindmap_parent_id"], branch.id)
        self.assertEqual(child.metadata["mindmap_side"], branch.metadata["mindmap_side"])
        self.assertEqual(len(document.connectors), 2)
        self.assertGreater(child.x, branch.x)

    def test_copy_paste_remaps_mindmap_metadata_ids(self):
        from core.mindmap import build_mindmap_fragment, parse_heading_text

        document = Document()
        tree = parse_heading_text("# Root\n## Branch")
        nodes, connectors = build_mindmap_fragment(tree, center=(500, 400), mindmap_id="mindmap_test")
        for node in nodes:
            document.add_shape(node)
        for connector in connectors:
            document.add_connector(connector)

        pasted = document.copy_paste([node.id for node in nodes], (30, 30))

        pasted_root = next(node for node in pasted if node.text == "Root")
        pasted_branch = next(node for node in pasted if node.text == "Branch")
        pasted_connector = document.connectors[-1]
        self.assertEqual(pasted_root.metadata["mindmap_parent_id"], "")
        self.assertEqual(pasted_branch.metadata["mindmap_parent_id"], pasted_root.id)
        self.assertEqual(pasted_connector.metadata["mindmap_parent_id"], pasted_root.id)
        self.assertEqual(pasted_connector.metadata["mindmap_child_id"], pasted_branch.id)

    def test_app_creates_mindmap_from_heading_text(self):
        from app import VectorFlowApp

        app = VectorFlowApp.__new__(VectorFlowApp)
        app.document = Document()
        app.canvas = _Canvas()
        app.zoom = 1.0
        app.pan = (0.0, 0.0)
        app.selected_ids = set()
        app.current_tool = _Var("select")
        app._mindmap_hidden_original_visibility = {}
        app._push_history = lambda: None
        app.redraw = lambda: None
        app._update_tool_button_states = lambda: None
        app._update_status = lambda _message=None: None

        app._create_mindmap_from_text("# Root\n## Branch", None)

        self.assertEqual(len(app.document.shapes), 2)
        self.assertEqual(len(app.document.connectors), 1)
        self.assertEqual(app.document.shapes[0].text, "Root")
        self.assertEqual(app.selected_ids, {app.document.shapes[0].id})

    def test_app_history_snapshot_preserves_visibility_when_collapsed(self):
        from app import VectorFlowApp
        from core.mindmap import MINDMAP_COLLAPSED, build_mindmap_fragment, parse_heading_text

        app = VectorFlowApp.__new__(VectorFlowApp)
        app.document = Document()
        app._mindmap_hidden_original_visibility = {}
        tree = parse_heading_text("# Root\n## Branch\n### Leaf")
        nodes, connectors = build_mindmap_fragment(tree, center=(500, 400), mindmap_id="mindmap_test")
        for node in nodes:
            app.document.add_shape(node)
        for connector in connectors:
            app.document.add_connector(connector)
        branch = next(node for node in app.document.shapes if isinstance(node, FlowchartShape) and node.text == "Branch")
        leaf = next(node for node in app.document.shapes if isinstance(node, FlowchartShape) and node.text == "Leaf")
        branch.metadata[MINDMAP_COLLAPSED] = True

        app._apply_mindmap_visibility()
        snapshot = app._document_dict_for_history()

        leaf_payload = next(shape for shape in snapshot["shapes"] if shape["id"] == leaf.id)
        self.assertFalse(leaf.visible)
        self.assertTrue(leaf_payload["visible"])


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Canvas:
    def winfo_width(self):
        return 800

    def winfo_height(self):
        return 600
