import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.components import ComponentLibrary, ComponentTemplate, build_group_from_selection
from core.document import Document
from core.shapes import ConnectorShape, FlowchartShape, GroupShape, LineShape


class ComponentTests(unittest.TestCase):
    def test_group_from_selection_captures_shapes_connectors_and_metadata(self):
        document = Document()
        server = document.add_shape(FlowchartShape("process", 100, 80, 120, 60, "Server"))
        port = document.add_shape(FlowchartShape("circle", 250, 95, 40, 40, ""))
        external = document.add_shape(FlowchartShape("process", 400, 80, 100, 50, "External"))
        kept_connector = document.add_connector(ConnectorShape(server.id, port.id, "right", "left", kind="straight"))
        document.add_connector(ConnectorShape(port.id, external.id, "right", "left", kind="straight"))

        group = build_group_from_selection(document, {server.id, port.id}, name="Server Component", metadata={"IP": "10.0.0.8"})

        self.assertIsInstance(group, GroupShape)
        self.assertEqual(group.metadata["IP"], "10.0.0.8")
        self.assertEqual(len(group.children), 2)
        self.assertEqual(len(group.connectors), 1)
        self.assertEqual(group.connectors[0].id, kept_connector.id)
        self.assertEqual(group.bounds(), (100, 80, 290, 140))

    def test_group_shape_round_trips_and_moves_children(self):
        group = GroupShape(
            name="Gate",
            children=[FlowchartShape("process", 20, 30, 80, 40), LineShape(30, 90, 100, 90)],
            connectors=[],
            metadata={"R": "10k"},
        )

        restored = GroupShape.from_dict(group.to_dict())
        restored.move(10, 15)

        self.assertEqual(restored.metadata["R"], "10k")
        self.assertEqual(restored.children[0].bounds(), (30, 45, 110, 85))
        self.assertEqual(restored.children[1].bounds(), (40, 105, 110, 105))

    def test_component_template_instantiates_with_new_ids_at_target_position(self):
        group = GroupShape(
            name="Server",
            children=[
                FlowchartShape("process", 100, 80, 120, 60, "Server"),
                FlowchartShape("circle", 250, 95, 40, 40),
            ],
            connectors=[],
            metadata={"IP": "10.0.0.8"},
        )
        template = ComponentTemplate.from_group(group)

        instance = template.instantiate_at(400, 300)

        self.assertIsInstance(instance, GroupShape)
        self.assertNotEqual(instance.id, group.id)
        self.assertNotEqual(instance.children[0].id, group.children[0].id)
        self.assertEqual(instance.metadata["IP"], "10.0.0.8")
        self.assertEqual(instance.bounds(), (400, 300, 590, 360))

    def test_component_library_persists_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "components.json"
            library = ComponentLibrary(path)
            group = GroupShape(
                name="Server",
                children=[FlowchartShape("process", 100, 80, 120, 60, "Server")],
                connectors=[],
                metadata={"IP": "10.0.0.8"},
            )

            library.add_from_group(group)
            reloaded = ComponentLibrary(path)

            self.assertEqual(len(reloaded.templates), 1)
            self.assertEqual(reloaded.templates[0].name, "Server")
            self.assertEqual(reloaded.templates[0].metadata["IP"], "10.0.0.8")

    def test_component_library_deletes_template_and_persists_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "components.json"
            library = ComponentLibrary(path)
            server = GroupShape(
                name="Server",
                children=[FlowchartShape("process", 100, 80, 120, 60, "Server")],
                connectors=[],
                metadata={"IP": "10.0.0.8"},
            )
            resistor = GroupShape(
                name="Resistor",
                children=[FlowchartShape("process", 20, 20, 80, 40, "R1")],
                connectors=[],
                metadata={"R": "10k"},
            )

            library.add_from_group(server)
            library.add_from_group(resistor)

            self.assertTrue(library.delete(0))
            self.assertFalse(library.delete(9))
            reloaded = ComponentLibrary(path)

            self.assertEqual(len(reloaded.templates), 1)
            self.assertEqual(reloaded.templates[0].name, "Resistor")
            self.assertEqual(reloaded.templates[0].metadata["R"], "10k")

    def test_document_replace_selection_with_group_removes_original_parts(self):
        document = Document()
        a = document.add_shape(FlowchartShape("process", 10, 10, 80, 40, "A"))
        b = document.add_shape(FlowchartShape("process", 120, 10, 80, 40, "B"))
        connector = document.add_connector(ConnectorShape(a.id, b.id, "right", "left", kind="straight"))
        group = build_group_from_selection(document, {a.id, b.id}, name="Pair")

        document.replace_selection_with_group({a.id, b.id}, group)

        self.assertEqual(len(document.shapes), 1)
        self.assertIsInstance(document.shapes[0], GroupShape)
        self.assertEqual(document.shapes[0].connectors[0].id, connector.id)
        self.assertEqual(document.connectors, [])


if __name__ == "__main__":
    unittest.main()
