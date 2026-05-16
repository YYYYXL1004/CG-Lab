from __future__ import annotations

from core.document import Document


class History:
    def __init__(self) -> None:
        self._states: list[dict] = []
        self._index: int = -1

    def push(self, state: dict) -> None:
        if self._states and self._index >= 0 and state == self._states[self._index]:
            return
        self._states = self._states[: self._index + 1]
        self._states.append(state)
        self._index = len(self._states) - 1

    def undo(self, document: Document) -> bool:
        if self._index <= 0:
            return False
        self._index -= 1
        document.replace_from_dict(self._states[self._index])
        return True

    def redo(self, document: Document) -> bool:
        if self._index >= len(self._states) - 1:
            return False
        self._index += 1
        document.replace_from_dict(self._states[self._index])
        return True

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return self._index < len(self._states) - 1
