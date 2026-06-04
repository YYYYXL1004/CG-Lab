from __future__ import annotations

import math
import re
from dataclasses import dataclass

from core.document import Document
from core.shapes import ConnectorShape, FlowchartShape
from core.style import ShapeStyle


@dataclass(frozen=True)
class SqlColumn:
    name: str
    data_type: str
    nullable: bool = True


@dataclass(frozen=True)
class SqlForeignKey:
    columns: list[str]
    ref_table: str
    ref_columns: list[str]
    name: str = ""


@dataclass
class SqlTable:
    name: str
    columns: list[SqlColumn]
    primary_keys: list[str]
    foreign_keys: list[SqlForeignKey]


@dataclass
class SqlSchema:
    tables: list[SqlTable]

    def table(self, name: str) -> SqlTable:
        wanted = _normalize_identifier(name)
        for table in self.tables:
            if _normalize_identifier(table.name) == wanted:
                return table
        raise KeyError(name)


@dataclass(frozen=True)
class ErSqlTemplate:
    name: str
    sql: str


ER_SQL_TEMPLATES: list[ErSqlTemplate] = [
    ErSqlTemplate(
        "电商订单系统",
        """
CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    email VARCHAR(120) UNIQUE,
    created_at DATETIME
);

CREATE TABLE products (
    product_id INT PRIMARY KEY,
    sku VARCHAR(40) NOT NULL,
    title VARCHAR(120) NOT NULL,
    price DECIMAL(10,2) NOT NULL
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_no VARCHAR(40) NOT NULL,
    status VARCHAR(20),
    total DECIMAL(10,2),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    item_id INT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
""".strip(),
    ),
    ErSqlTemplate(
        "博客内容系统",
        """
CREATE TABLE users (
    id INT PRIMARY KEY,
    username VARCHAR(60) NOT NULL,
    email VARCHAR(120),
    role VARCHAR(30)
);

CREATE TABLE posts (
    id INT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200),
    published_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE comments (
    id INT PRIMARY KEY,
    post_id INT NOT NULL,
    user_id INT NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME,
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
""".strip(),
    ),
    ErSqlTemplate(
        "学校选课系统",
        """
CREATE TABLE students (
    student_id INT PRIMARY KEY,
    student_no VARCHAR(40) NOT NULL,
    name VARCHAR(80) NOT NULL,
    grade VARCHAR(20)
);

CREATE TABLE teachers (
    teacher_id INT PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    department VARCHAR(80)
);

CREATE TABLE courses (
    course_id INT PRIMARY KEY,
    teacher_id INT NOT NULL,
    code VARCHAR(40) NOT NULL,
    title VARCHAR(120) NOT NULL,
    credits INT,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
);

CREATE TABLE enrollments (
    enrollment_id INT PRIMARY KEY,
    student_id INT NOT NULL,
    course_id INT NOT NULL,
    semester VARCHAR(30),
    score DECIMAL(5,2),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);
""".strip(),
    ),
]


def parse_create_table_sql(sql: str) -> SqlSchema:
    tables: list[SqlTable] = []
    for table_name, body in _create_table_blocks(sql):
        columns: list[SqlColumn] = []
        primary_keys: list[str] = []
        foreign_keys: list[SqlForeignKey] = []
        for clause in _split_top_level(body, ","):
            clause = clause.strip()
            if not clause:
                continue
            upper = clause.upper()
            if upper.startswith("CONSTRAINT "):
                clause = _strip_constraint_name(clause)
                upper = clause.upper()
            if upper.startswith("PRIMARY KEY"):
                primary_keys.extend(_identifier_list_from_parentheses(clause))
            elif upper.startswith("FOREIGN KEY"):
                fk = _parse_foreign_key_clause(clause)
                if fk is not None:
                    foreign_keys.append(fk)
            elif not upper.startswith(("UNIQUE", "KEY ", "INDEX ", "CHECK ", "EXCLUDE ")):
                column = _parse_column_clause(clause)
                if column is None:
                    continue
                columns.append(column[0])
                if column[1]:
                    primary_keys.append(column[0].name)
                if column[2] is not None:
                    foreign_keys.append(column[2])
        primary_keys = _dedupe(primary_keys)
        tables.append(SqlTable(table_name, columns, primary_keys, foreign_keys))
    if not tables:
        raise ValueError("没有找到 CREATE TABLE 语句")
    return SqlSchema(tables)


def format_er_table_text(table: SqlTable) -> str:
    fk_columns = {column for fk in table.foreign_keys for column in fk.columns}
    lines = [table.name]
    for column in table.columns:
        markers: list[str] = []
        if column.name in table.primary_keys:
            markers.append("PK")
        if column.name in fk_columns:
            markers.append("FK")
        prefix = f"{'/'.join(markers)} " if markers else "   "
        null_mark = "" if column.nullable else " NOT NULL"
        lines.append(f"{prefix}{column.name} : {column.data_type}{null_mark}")
    return "\n".join(lines)


def build_er_document(schema: SqlSchema, origin: tuple[float, float] = (120, 120)) -> Document:
    document = Document(title="SQL ER 图", background="#101820", grid_size=20, snap_enabled=True)
    table_to_shape: dict[str, FlowchartShape] = {}
    cols = max(1, math.ceil(math.sqrt(len(schema.tables))))
    gap_x = 90
    gap_y = 70
    x0, y0 = origin
    table_sizes = [(_table_width(table), 52 + max(1, len(table.columns)) * 26) for table in schema.tables]
    col_lefts: list[float] = []
    current_x = x0
    for col in range(cols):
        col_lefts.append(current_x)
        col_widths = [table_sizes[index][0] for index in range(col, len(table_sizes), cols)]
        current_x += max(col_widths, default=260) + gap_x
    row_tops: list[float] = []
    current_y = y0
    for row_start in range(0, len(schema.tables), cols):
        row_tops.append(current_y)
        row_heights = [height for _width, height in table_sizes[row_start : row_start + cols]]
        current_y += max(row_heights, default=0) + gap_y
    for index, table in enumerate(schema.tables):
        row = index // cols
        col = index % cols
        width, height = table_sizes[index]
        x = col_lefts[col]
        y = row_tops[row]
        shape = FlowchartShape(
            "er_table",
            x,
            y,
            width,
            height,
            format_er_table_text(table),
            ShapeStyle(stroke="#2A9D8F", fill="#F8FBFD", stroke_width=2, text_color="#263238", font_size=13, text_align="left"),
        )
        document.add_shape(shape)
        table_to_shape[_normalize_identifier(table.name)] = shape

    connector_style = ShapeStyle(stroke="#E76F51", fill=None, stroke_width=2)
    for table in schema.tables:
        source = table_to_shape.get(_normalize_identifier(table.name))
        if source is None:
            continue
        for fk in table.foreign_keys:
            target = table_to_shape.get(_normalize_identifier(fk.ref_table))
            if target is None:
                continue
            start_anchor, end_anchor = _best_anchor_pair(source, target)
            document.add_connector(
                ConnectorShape(
                    source.id,
                    target.id,
                    start_anchor=start_anchor,
                    end_anchor=end_anchor,
                    kind="elbow",
                    arrow_start="none",
                    arrow_end="diamond",
                    style=connector_style,
                )
            )
    return document


def _create_table_blocks(sql: str) -> list[tuple[str, str]]:
    cleaned = _strip_sql_comments(sql)
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>(?:[`\"\[][^`\"\]]+[`\"\]]|[\w.]+))\s*\(",
        re.IGNORECASE,
    )
    blocks: list[tuple[str, str]] = []
    pos = 0
    while True:
        match = pattern.search(cleaned, pos)
        if match is None:
            break
        open_index = match.end() - 1
        close_index = _matching_paren(cleaned, open_index)
        if close_index < 0:
            raise ValueError(f"表 {match.group('name')} 的括号没有闭合")
        blocks.append((_clean_identifier(match.group("name").split(".")[-1]), cleaned[open_index + 1 : close_index]))
        pos = close_index + 1
    return blocks


def _parse_column_clause(clause: str) -> tuple[SqlColumn, bool, SqlForeignKey | None] | None:
    tokens = clause.split(None, 1)
    if not tokens:
        return None
    name = _clean_identifier(tokens[0])
    if not name:
        return None
    rest = tokens[1].strip() if len(tokens) > 1 else ""
    data_type = _column_type(rest)
    upper = rest.upper()
    inline_primary = bool(re.search(r"\bPRIMARY\s+KEY\b", upper))
    nullable = not bool(re.search(r"\bNOT\s+NULL\b", upper))
    fk: SqlForeignKey | None = None
    ref_match = re.search(
        r"\bREFERENCES\s+([`\"\[]?[\w.]+[`\"\]]?)\s*\(([^)]*)\)",
        rest,
        re.IGNORECASE,
    )
    if ref_match:
        fk = SqlForeignKey([name], _clean_identifier(ref_match.group(1).split(".")[-1]), _clean_identifier_list(ref_match.group(2)))
    return SqlColumn(name, data_type or "UNKNOWN", nullable), inline_primary, fk


def _parse_foreign_key_clause(clause: str) -> SqlForeignKey | None:
    match = re.search(
        r"FOREIGN\s+KEY\s*\((?P<cols>[^)]*)\)\s+REFERENCES\s+(?P<table>[`\"\[]?[\w.]+[`\"\]]?)\s*\((?P<ref>[^)]*)\)",
        clause,
        re.IGNORECASE,
    )
    if not match:
        return None
    return SqlForeignKey(
        _clean_identifier_list(match.group("cols")),
        _clean_identifier(match.group("table").split(".")[-1]),
        _clean_identifier_list(match.group("ref")),
    )


def _strip_constraint_name(clause: str) -> str:
    parts = clause.split(None, 2)
    if len(parts) < 3:
        return clause
    return parts[2].strip()


def _column_type(rest: str) -> str:
    constraint_words = {
        "PRIMARY",
        "NOT",
        "NULL",
        "UNIQUE",
        "DEFAULT",
        "CHECK",
        "REFERENCES",
        "COLLATE",
        "GENERATED",
        "IDENTITY",
        "AUTO_INCREMENT",
        "COMMENT",
    }
    pieces: list[str] = []
    for token in _split_type_tokens(rest):
        if token.upper() in constraint_words:
            break
        pieces.append(token)
    return " ".join(pieces).strip()


def _split_type_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


def _identifier_list_from_parentheses(text: str) -> list[str]:
    start = text.find("(")
    end = text.rfind(")")
    if start < 0 or end < start:
        return []
    return _clean_identifier_list(text[start + 1 : end])


def _clean_identifier_list(text: str) -> list[str]:
    return [_clean_identifier(item) for item in _split_top_level(text, ",") if _clean_identifier(item)]


def _clean_identifier(value: str) -> str:
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        return text[1:-1].strip()
    if len(text) >= 2 and text[0] in {'`', '"'} and text[-1] == text[0]:
        return text[1:-1].strip()
    return text.strip("`\"[] ")


def _normalize_identifier(value: str) -> str:
    return _clean_identifier(value).lower()


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n\r]*", " ", sql)


def _matching_paren(text: str, open_index: int) -> int:
    depth = 0
    quote: str | None = None
    for index in range(open_index, len(text)):
        char = text[index]
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _split_top_level(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == separator and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _normalize_identifier(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _table_width(table: SqlTable) -> int:
    lines = format_er_table_text(table).splitlines()
    title_width = len(lines[0]) * 9 + 28 if lines else 230
    field_width = max((len(line.strip()) * 8.5 + 58 + 18 for line in lines[1:]), default=230)
    return math.ceil(max(230, title_width, field_width))


def _best_anchor_pair(start: FlowchartShape, end: FlowchartShape) -> tuple[str, str]:
    sx, sy = start.center().x, start.center().y
    ex, ey = end.center().x, end.center().y
    if abs(ex - sx) >= abs(ey - sy):
        return ("right", "left") if ex >= sx else ("left", "right")
    return ("bottom", "top") if ey >= sy else ("top", "bottom")
