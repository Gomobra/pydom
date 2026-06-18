"""The :class:`Text` and :class:`Comment` character-data nodes.

Reference: https://dom.spec.whatwg.org/#interface-text
           https://dom.spec.whatwg.org/#interface-comment
"""

from __future__ import annotations

from typing import Optional

from pydom.dom.node import CDATA_SECTION_NODE, COMMENT_NODE, TEXT_NODE, Node


class CharacterData(Node):
    """Shared base for nodes holding text (:class:`Text`, :class:`Comment`)."""

    def __init__(self, data: str = "", owner_document: Optional["Document"] = None) -> None:  # noqa: F821
        super().__init__(owner_document=owner_document)
        self.data: str = data

    @property
    def length(self) -> int:
        return len(self.data)

    @property
    def node_value(self) -> Optional[str]:
        return self.data

    @node_value.setter
    def node_value(self, value: Optional[str]) -> None:
        self.data = value if value is not None else ""

    @property
    def text_content(self) -> Optional[str]:  # type: ignore[override]
        return self.data

    def substring_data(self, offset: int, count: int) -> str:
        if offset < 0 or count < 0 or offset > len(self.data):
            from pydom.dom.exceptions import IndexSizeError

            raise IndexSizeError("substring_data offset/count out of range")
        return self.data[offset : offset + count]

    def append_data(self, data: str) -> None:
        self.data += data

    def insert_data(self, offset: int, data: str) -> None:
        self.replace_data(offset, 0, data)

    def delete_data(self, offset: int, count: int) -> None:
        self.replace_data(offset, count, "")

    def replace_data(self, offset: int, count: int, data: str) -> None:
        before = self.data[:offset]
        after = self.data[offset + count :]
        self.data = before + data + after


class Text(CharacterData):
    nodeType = TEXT_NODE

    def __init__(self, data: str = "", owner_document: Optional["Document"] = None) -> None:  # noqa: F821
        super().__init__(data, owner_document=owner_document)

    @property
    def node_name(self) -> str:  # type: ignore[override]
        return "#text"

    def split_text(self, offset: int) -> "Text":
        """Split this text node at ``offset``; return the new following node."""
        if offset < 0 or offset > len(self.data):
            from pydom.dom.exceptions import IndexSizeError

            raise IndexSizeError("split_text offset out of range")
        new_data = self.data[offset:]
        self.data = self.data[:offset]
        new_text = Text(new_data, owner_document=self.ownerDocument)
        if self._parent is not None:
            self._parent.insert_before(new_text, self.next_sibling)
        return new_text

    def whole_text(self) -> str:
        """Concatenated text of all adjacent Text siblings (spec: wholeText)."""
        parts: list[str] = []
        # Walk previous contiguous Text siblings.
        cur = self.previous_sibling
        stack: list[str] = []
        while cur is not None and cur.nodeType in (TEXT_NODE, CDATA_SECTION_NODE):
            stack.append(cur.data)  # type: ignore[attr-defined]
            cur = cur.previous_sibling
        parts.extend(reversed(stack))
        parts.append(self.data)
        cur = self.next_sibling
        while cur is not None and cur.nodeType in (TEXT_NODE, CDATA_SECTION_NODE):
            parts.append(cur.data)  # type: ignore[attr-defined]
            cur = cur.next_sibling
        return "".join(parts)

    def _shallow_clone(self) -> "Text":
        return Text(self.data, owner_document=self.ownerDocument)


class Comment(CharacterData):
    nodeType = COMMENT_NODE

    def __init__(self, data: str = "", owner_document: Optional["Document"] = None) -> None:  # noqa: F821
        super().__init__(data, owner_document=owner_document)

    @property
    def node_name(self) -> str:  # type: ignore[override]
        return "#comment"

    def _shallow_clone(self) -> "Comment":
        return Comment(self.data, owner_document=self.ownerDocument)
