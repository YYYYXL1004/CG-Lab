from __future__ import annotations

import json
from pathlib import Path

from core.document import Document


def save_document(document: Document, path: str | Path) -> None:
    Path(path).write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_document(path: str | Path) -> Document:
    return Document.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
