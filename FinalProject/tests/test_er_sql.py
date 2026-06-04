import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.er_sql import ER_SQL_TEMPLATES, build_er_document, format_er_table_text, parse_create_table_sql
from core.shapes import FlowchartShape


class ErSqlTests(unittest.TestCase):
    def test_parse_create_table_extracts_columns_primary_keys_and_foreign_keys(self):
        sql = """
        CREATE TABLE users (
            id INT PRIMARY KEY,
            email VARCHAR(120) NOT NULL
        );

        CREATE TABLE orders (
            id INT PRIMARY KEY,
            user_id INT NOT NULL,
            total DECIMAL(10,2),
            CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """

        schema = parse_create_table_sql(sql)

        self.assertEqual([table.name for table in schema.tables], ["users", "orders"])
        self.assertEqual(schema.table("users").primary_keys, ["id"])
        self.assertEqual(schema.table("orders").foreign_keys[0].columns, ["user_id"])
        self.assertEqual(schema.table("orders").foreign_keys[0].ref_table, "users")
        self.assertEqual(schema.table("orders").columns[2].data_type, "DECIMAL(10,2)")

    def test_build_er_document_creates_table_shapes_and_fk_connectors(self):
        schema = parse_create_table_sql("""
        CREATE TABLE customers (
            customer_id INT,
            name VARCHAR(80),
            PRIMARY KEY (customer_id)
        );
        CREATE TABLE invoices (
            invoice_id INT PRIMARY KEY,
            customer_id INT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );
        """)

        document = build_er_document(schema, origin=(100, 120))

        er_tables = [shape for shape in document.shapes if isinstance(shape, FlowchartShape) and shape.kind == "er_table"]
        self.assertEqual(len(er_tables), 2)
        self.assertEqual(len(document.connectors), 1)
        self.assertIn("PK customer_id", er_tables[0].text)
        self.assertIn("FK customer_id", er_tables[1].text)
        self.assertEqual(document.connectors[0].arrow_end, "diamond")

    def test_build_er_document_uses_row_heights_to_avoid_overlap(self):
        schema = parse_create_table_sql("""
        CREATE TABLE tall_a (
            id INT PRIMARY KEY,
            c1 INT,
            c2 INT,
            c3 INT,
            c4 INT,
            c5 INT,
            c6 INT
        );
        CREATE TABLE tall_b (
            id INT PRIMARY KEY,
            c1 INT,
            c2 INT,
            c3 INT,
            c4 INT,
            c5 INT,
            c6 INT
        );
        CREATE TABLE short_c (
            id INT PRIMARY KEY
        );
        """)

        document = build_er_document(schema, origin=(100, 100))
        first_row_bottom = max(shape.y + shape.height for shape in document.shapes[:2])
        second_row_top = document.shapes[2].y

        self.assertGreaterEqual(second_row_top - first_row_bottom, 70)

    def test_build_er_document_uses_column_widths_to_avoid_overlap(self):
        schema = parse_create_table_sql("""
        CREATE TABLE very_long_customer_profile_table (
            customer_profile_identifier INT PRIMARY KEY,
            preferred_notification_channel VARCHAR(120),
            account_lifecycle_segment VARCHAR(120)
        );
        CREATE TABLE very_long_order_fulfillment_table (
            order_fulfillment_identifier INT PRIMARY KEY,
            customer_profile_identifier INT,
            warehouse_routing_strategy VARCHAR(120)
        );
        """)

        document = build_er_document(schema, origin=(100, 100))
        left, right = document.shapes

        self.assertGreaterEqual(right.x - (left.x + left.width), 90)

    def test_build_er_document_width_fits_long_field_content(self):
        schema = parse_create_table_sql("""
        CREATE TABLE audit_log_entries (
            id INT PRIMARY KEY,
            organization_security_policy_evaluation_result_identifier VARCHAR(255) NOT NULL
        );
        """)

        document = build_er_document(schema, origin=(100, 100))
        shape = document.shapes[0]
        longest_field_line = max(shape.text.splitlines()[1:], key=len).strip()
        estimated_text_width = len(longest_field_line) * 8.5

        self.assertGreaterEqual(shape.width - 58 - 18, estimated_text_width)

    def test_templates_are_available_for_demo_and_parse_successfully(self):
        self.assertGreaterEqual(len(ER_SQL_TEMPLATES), 3)
        for template in ER_SQL_TEMPLATES:
            with self.subTest(template=template.name):
                schema = parse_create_table_sql(template.sql)
                self.assertGreaterEqual(len(schema.tables), 2)

    def test_format_er_table_text_marks_pk_and_fk_fields(self):
        schema = parse_create_table_sql("""
        CREATE TABLE posts (
            id INT PRIMARY KEY,
            user_id INT,
            title VARCHAR(200),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)

        text = format_er_table_text(schema.table("posts"))

        self.assertEqual(text.splitlines()[0], "posts")
        self.assertIn("PK id", text)
        self.assertIn("FK user_id", text)


if __name__ == "__main__":
    unittest.main()
