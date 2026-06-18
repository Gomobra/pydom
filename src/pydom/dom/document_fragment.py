"""The :class:`DocumentFragment` interface.

A lightweight, minimal container usable in place of a Document for subtrees.
Reference: https://dom.spec.whatwg.org/#interface-documentfragment
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pydom.dom.node import DOCUMENT_FRAGMENT_NODE, Node

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.dom.element import Element
    from pydom.dom.nodelist import NodeList


class DocumentFragment(Node):
    nodeType = DOCUMENT_FRAGMENT_NODE

    def __init__(self, owner_document: Optional["Document"] = None) -> None:  # noqa: F821
        super().__init__(owner_document=owner_document)

    @property
    def node_name(self) -> str:  # type: ignore[override]
        return "#document-fragment"

    # ---- selectors (ParentNode mixin behavior) ----------------------------
    def query_selector(self, selector: str) -> Optional["Element"]:
        from pydom.selectors.engine import query_selector

        return query_selector(self, selector)  # type: ignore[arg-type]

    def query_selector_all(self, selector: str) -> "NodeList":
        from pydom.selectors.engine import query_selector_all

        return query_selector_all(self, selector)  # type: ignore[arg-type]

    def get_elements_by_tag_name(self, qualified_name: str):
        from pydom.dom.element import Element

        return Element.get_elements_by_tag_name(self, qualified_name)  # type: ignore[arg-type]

    def get_elements_by_class_name(self, class_names: str):
        from pydom.dom.element import Element

        return Element.get_elements_by_class_name(self, class_names)  # type: ignore[arg-type]

    def _shallow_clone(self) -> "DocumentFragment":
        return DocumentFragment(owner_document=self.ownerDocument)
