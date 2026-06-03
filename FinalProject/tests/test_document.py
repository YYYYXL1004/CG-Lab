import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.document import Document
from core.shapes import ConnectorShape, FlowchartShape, LineShape
from core.style import ShapeStyle


class DocumentTests(unittest.TestCase):
    def test_document_serialization_round_trips_editable_shapes(self):
        document = Document(title="demo")
        process = FlowchartShape(
            kind="process",
            x=100,
            y=80,
            width=140,
            height=70,
            text="Start",
            style=ShapeStyle(fill="#2b405f", stroke="#79a7ff"),
        )
        decision = FlowchartShape(kind="decision", x=320, y=80, width=120, height=90, text="OK?")
        document.add_shape(process)
        document.add_shape(decision)
        document.add_connector(ConnectorShape(start_shape_id=process.id, end_shape_id=decision.id))

        payload = document.to_dict()
        restored = Document.from_dict(json.loads(json.dumps(payload)))

        self.assertEqual(restored.title, "demo")
        self.assertEqual(len(restored.shapes), 2)
        self.assertEqual(len(restored.connectors), 1)
        self.assertEqual(restored.shapes[0].text, "Start")
        self.assertEqual(restored.connectors[0].start_shape_id, process.id)

    def test_copy_paste_duplicates_selected_shapes_with_offset(self):
        document = Document()
        shape = FlowchartShape(kind="terminal", x=20, y=30, width=100, height=50, text="End")
        document.add_shape(shape)

        pasted = document.copy_paste([shape.id], offset=(30, 40))

        self.assertEqual(len(pasted), 1)
        self.assertEqual(pasted[0].text, "End")
        self.assertNotEqual(pasted[0].id, shape.id)
        self.assertEqual((pasted[0].x, pasted[0].y), (50, 70))
        self.assertEqual(len(document.shapes), 2)

    def test_connector_endpoints_follow_moved_shapes(self):
        document = Document()
        left = FlowchartShape(kind="process", x=0, y=0, width=100, height=50)
        right = FlowchartShape(kind="process", x=200, y=0, width=100, height=50)
        connector = ConnectorShape(start_shape_id=left.id, end_shape_id=right.id)
        document.add_shape(left)
        document.add_shape(right)
        document.add_connector(connector)

        before = document.connector_points(connector)
        document.move_shapes([right.id], 50, 25)
        after = document.connector_points(connector)

        self.assertNotEqual(before[-1], after[-1])
        self.assertEqual(after[-1], (250, 50))

    def test_delete_shape_removes_attached_connectors(self):
        document = Document()
        a = FlowchartShape(kind="process", x=0, y=0, width=100, height=50)
        b = FlowchartShape(kind="process", x=200, y=0, width=100, height=50)
        document.add_shape(a)
        document.add_shape(b)
        document.add_connector(ConnectorShape(start_shape_id=a.id, end_shape_id=b.id))

        document.delete_shapes([a.id])

        self.assertEqual([shape.id for shape in document.shapes], [b.id])
        self.assertEqual(document.connectors, [])

    def test_connector_points_uses_shape_index_instead_of_repeated_shape_scans(self):
        class CountingList(list):
            iterations = 0

            def __iter__(self):
                self.iterations += 1
                return super().__iter__()

        document = Document()
        document.shapes = CountingList()
        start = document.add_shape(FlowchartShape("process", 0, 0, 80, 40))
        end = document.add_shape(FlowchartShape("process", 120, 0, 80, 40))
        connector = ConnectorShape(start.id, end.id, "right", "left", kind="straight")
        document.shapes.iterations = 0

        points = document.connector_points(connector)

        self.assertEqual(points, [start.anchor("right"), end.anchor("left")])
        self.assertLessEqual(document.shapes.iterations, 1)

    def test_shape_index_drops_ids_after_direct_shape_list_clear(self):
        document = Document()
        old_shape = document.add_shape(FlowchartShape("process", 0, 0, 80, 40))
        self.assertIs(document.find_shape(old_shape.id), old_shape)

        document.shapes.clear()
        new_shape = document.add_shape(FlowchartShape("process", 120, 0, 80, 40))

        self.assertIsNone(document.find_shape(old_shape.id))
        self.assertIs(document.find_shape(new_shape.id), new_shape)


if __name__ == "__main__":
    unittest.main()
