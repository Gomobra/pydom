"""CSS selector engine — adapter from pydom to :mod:`soupsieve` via BeautifulSoup.

Because soupsieve is tightly coupled to BeautifulSoup's ``Tag`` API, we bridge
by:
1. Serializing the pydom subtree under ``root`` to a standalone HTML string.
2. Parsing that string with BeautifulSoup.
3. Running soupsieve on the resulting soup.
4. Mapping each matched BeautifulSoup tag back to the original pydom node by
   following the child indices reported by the soup (``path``).

This is a pragmatic, robust approach for phase 1. A faster direct adapter can
replace it later without changing the public API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import bs4
import soupsieve as sv

from pydom.html.serializer import serialize

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.dom.document import Document
    from pydom.dom.element import Element
    from pydom.dom.node import Node
    from pydom.dom.nodelist import NodeList


HTML_NS = "http://www.w3.org/1999/xhtml"


def _root_for(root: "Node") -> bs4.BeautifulSoup:
    """Serialize ``root`` and parse it into a BeautifulSoup tree."""
    markup = serialize(root)
    return bs4.BeautifulSoup(markup, "html.parser")


def _path_to_node(soup_node: bs4.Tag, root: "Node") -> List[int]:
    """Return the child-index path from ``root`` to the equivalent soup node.

    When ``root`` is an Element, ``serialize(root)`` produces a soup whose
    top-level tag is the root itself. We therefore skip that wrapper level
    because the path is resolved starting from the pydom ``root`` element, not
    from its parent.
    """
    path: List[int] = []
    cur = soup_node
    while cur.parent is not None and isinstance(cur.parent, bs4.Tag):
        siblings = [c for c in cur.parent.contents if isinstance(c, bs4.Tag)]
        try:
            path.append(siblings.index(cur))
        except ValueError:  # pragma: no cover - should never happen
            path.append(0)
        cur = cur.parent
    path.reverse()
    # If the root is an Element, the soup wraps it with one extra top-level tag.
    if root.nodeType == 1 and path:
        path = path[1:]
    return path


def _resolve_path(root: "Node", path: List[int]) -> Optional["Node"]:
    """Walk the pydom tree from ``root`` following ``path`` to the matching node."""
    cur: "Node" = root
    for idx in path:
        candidates = [c for c in cur._children if c.nodeType == 1]
        if idx < 0 or idx >= len(candidates):
            return None
        cur = candidates[idx]
    return cur


def _soup_tag_for(soup: bs4.BeautifulSoup, root: "Node", target: "Node") -> Optional[bs4.Tag]:
    """Locate the soup tag that corresponds to pydom ``target`` under ``root``."""
    # Build path from pydom root to target.
    path: List[int] = []
    cur = target
    while cur.parent_node is not None and cur is not root:
        siblings = [c for c in cur.parent_node._children if c.nodeType == 1]
        try:
            path.append(siblings.index(cur))
        except ValueError:  # pragma: no cover
            path.append(0)
        cur = cur.parent_node
    path.reverse()
    # Soup wraps an Element root with a top-level tag; add that wrapper step.
    if root.nodeType == 1:
        path = [0] + path
    cur = soup
    for idx in path:
        if not isinstance(cur, bs4.Tag):
            return None
        kids = [c for c in cur.contents if isinstance(c, bs4.Tag)]
        if idx >= len(kids):
            return None
        cur = kids[idx]
    return cur  # type: ignore[return-value]


def _matches_node(root: "Node", target: "Node", selector: str) -> bool:
    """Check whether ``target`` matches ``selector`` in the context of ``root``."""
    soup = _root_for(root)
    soup_tag = _soup_tag_for(soup, root, target)
    return soup_tag is not None and sv.match(selector, soup_tag)


def query_selector(root: "Node", selector: str) -> Optional["Element"]:
    """Return the first element under ``root`` matching ``selector``."""
    if root.nodeType not in (1, 9, 11):  # Element, Document, DocumentFragment
        return None
    soup = _root_for(root)
    tag = soup.select_one(selector)
    if tag is None or not isinstance(tag, bs4.Tag):
        return None
    node = _resolve_path(root, _path_to_node(tag, root))
    if node is None or node.nodeType != 1:
        return None
    return node  # type: ignore[return-value]


def query_selector_all(root: "Node", selector: str) -> "NodeList":
    """Return all elements under ``root`` matching ``selector``."""
    from pydom.dom.nodelist import NodeList

    if root.nodeType not in (1, 9, 11):
        return NodeList(lambda: [])
    soup = _root_for(root)
    tags = soup.select(selector)
    nodes: List["Node"] = []
    for tag in tags:
        if not isinstance(tag, bs4.Tag):
            continue
        node = _resolve_path(root, _path_to_node(tag, root))
        if node is not None and node.nodeType == 1:
            nodes.append(node)
    return NodeList(lambda: nodes)


def matches(element: "Element", selector: str) -> bool:
    """Return True if ``element`` itself matches ``selector``."""
    root = element.parent_node
    if root is None:
        # Detached element: test against a tiny soup containing just it.
        soup = bs4.BeautifulSoup(f"<div>{serialize(element)}</div>", "html.parser")
        tag = soup.div
        if tag is None:
            return False
        return sv.match(selector, tag)
    return _matches_node(root, element, selector)
