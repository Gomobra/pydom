"""The :class:`Attr` interface — an element attribute.

Represents one attribute on an :class:`~pydom.dom.element.Element`. Attributes
have a namespace, local name, prefix, and value, plus the convenience
``name``/``value`` pair.

Reference: https://dom.spec.whatwg.org/#interface-attr
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pydom.dom.node import ATTRIBUTE_NODE, Node

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.dom.element import Element


class Attr(Node):
    nodeType = ATTRIBUTE_NODE

    def __init__(
        self,
        local_name: str,
        value: Optional[str] = None,
        *,
        namespace: Optional[str] = None,
        prefix: Optional[str] = None,
        owner_element: Optional["Element"] = None,
        owner_document: Optional["Document"] = None,  # noqa: F821 - forward ref
    ) -> None:
        super().__init__(owner_document=owner_document)
        self._local_name = local_name
        self._namespace = namespace
        self._prefix = prefix
        self._value: Optional[str] = value if value is not None else ""
        self.owner_element: Optional["Element"] = owner_element

    # ---- name properties --------------------------------------------------
    @property
    def local_name(self) -> str:
        return self._local_name

    @property
    def name(self) -> str:
        if self._prefix:
            return f"{self._prefix}:{self._local_name}"
        return self._local_name

    @property
    def namespace_uri(self) -> Optional[str]:
        return self._namespace

    @property
    def prefix(self) -> Optional[str]:
        return self._prefix

    @property
    def node_name(self) -> str:  # type: ignore[override]
        return self.name

    # ---- value ------------------------------------------------------------
    @property
    def value(self) -> Optional[str]:
        return self._value

    @value.setter
    def value(self, new_value: Optional[str]) -> None:
        self._value = new_value if new_value is not None else ""

    def _shallow_clone(self) -> "Attr":
        return Attr(
            self._local_name,
            self._value,
            namespace=self._namespace,
            prefix=self._prefix,
            owner_document=self.ownerDocument,
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Attr {self.name!r}={self._value!r}>"
