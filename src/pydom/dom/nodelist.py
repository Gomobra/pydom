""":class:`NodeList` and :class:`HTMLCollection` — live ordered collections.

Both are *live* per the DOM Standard: they reflect the current state of the
tree rather than a snapshot. We achieve liveness by computing membership on
demand from a callable that returns the current underlying list of nodes.

Reference: https://dom.spec.whatwg.org/#interface-nodelist
           https://dom.spec.whatwg.org/#htmlcollection
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterator, List, Optional

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.dom.node import Node
    from pydom.dom.element import Element


class NodeList:
    """An ordered collection of nodes.

    Live: ``length`` and indexing reflect the tree at access time.
    """

    def __init__(self, provider: Callable[[], List["Node"]]) -> None:
        # ``provider`` returns the current backing list. Storing the callable
        # (rather than the list) is what makes the collection live.
        self._provider = provider

    @property
    def length(self) -> int:
        return len(self._provider())

    def item(self, index: int) -> Optional["Node"]:
        items = self._provider()
        if index < 0 or index >= len(items):
            return None
        return items[index]

    def __getitem__(self, index: int) -> "Node":
        items = self._provider()
        return items[index]

    def __iter__(self) -> Iterator["Node"]:
        return iter(self._provider())

    def __len__(self) -> int:
        return len(self._provider())

    def __contains__(self, node: object) -> bool:
        return node in self._provider()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"NodeList({self._provider()!r})"


class HTMLCollection:
    """An ordered, named-keyed collection of elements.

    Live, like :class:`NodeList`. ``namedItem`` looks up by ``id`` then by
    ``name`` attribute, per the HTML Standard.
    """

    def __init__(self, provider: Callable[[], List["Element"]]) -> None:
        self._provider = provider

    @property
    def length(self) -> int:
        return len(self._provider())

    def item(self, index: int) -> Optional["Element"]:
        items = self._provider()
        if index < 0 or index >= len(items):
            return None
        return items[index]

    def named_item(self, name: str) -> Optional["Element"]:
        # Per spec: first match by id, then by name attribute.
        items = self._provider()
        for el in items:
            if el.get_attribute("id") == name:
                return el
        for el in items:
            if el.get_attribute("name") == name:
                return el
        return None

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.item(key)
        return self.named_item(key)

    def __iter__(self) -> Iterator["Element"]:
        return iter(self._provider())

    def __len__(self) -> int:
        return len(self._provider())

    def __contains__(self, el: object) -> bool:
        return el in self._provider()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"HTMLCollection({self._provider()!r})"
