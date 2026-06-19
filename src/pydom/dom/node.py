"""The :class:`Node` interface — the root of the DOM node hierarchy.

Implements the node-tree mutation algorithms from the DOM Living Standard
(insertion, removal, replacement, cloning) plus the read-only navigation
properties (``parentNode``, ``childNodes``, ``nextSibling``, …).

Reference: https://dom.spec.whatwg.org/#interface-node
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, List, Optional

from pydom.dom.event import EventTarget
from pydom.dom.exceptions import DOMException, HierarchyRequestError, NotFoundError
from pydom.dom.nodelist import NodeList

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.dom.document import Document
    from pydom.dom.element import Element

# ---- nodeType constants ---------------------------------------------------
ELEMENT_NODE = 1
ATTRIBUTE_NODE = 2
TEXT_NODE = 3
CDATA_SECTION_NODE = 4
PROCESSING_INSTRUCTION_NODE = 7
COMMENT_NODE = 8
DOCUMENT_NODE = 9
DOCUMENT_TYPE_NODE = 10
DOCUMENT_FRAGMENT_NODE = 11


class Node(EventTarget):
    """Base class for every node in the DOM tree."""

    nodeType: int = 0
    # ``nodeName`` is exposed as a property (see below) delegating to the
    # snake_case ``node_name``; subclasses override ``node_name``.

    # Document-position constants (used by ``compareDocumentPosition``).
    DOCUMENT_POSITION_DISCONNECTED = 0x01
    DOCUMENT_POSITION_PRECEDING = 0x02
    DOCUMENT_POSITION_FOLLOWING = 0x04
    DOCUMENT_POSITION_CONTAINS = 0x08
    DOCUMENT_POSITION_CONTAINED_BY = 0x10
    DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC = 0x20


    def __init__(self, owner_document: Optional["Document"] = None) -> None:
        # Internal tree pointers. ``_parent`` is private so that the spec
        # property ``parentNode`` can be a normal attribute.
        self._parent: Optional[Node] = None
        self._children: List[Node] = []
        self.ownerDocument: Optional["Document"] = owner_document

    # ---- node identity (snake_case + camelCase aliases) ------------------
    # Subclasses set the camelCase class attribute (``nodeType``); the
    # snake_case property reads it so both styles are available.
    @property
    def node_type(self) -> int:
        return self.nodeType

    @property
    def node_name(self) -> str:
        # Overridden by subclasses; the base default is the empty string.
        return ""

    @property
    def nodeName(self) -> str:
        # camelCase alias for jsdom parity (delegates to snake_case property).
        return self.node_name

    @property
    def node_value(self) -> Optional[str]:
        return None

    @node_value.setter
    def node_value(self, value: Optional[str]) -> None:
        # Default nodes have no node value; CharacterData overrides this.
        pass

    # CamelCase <-> snake_case aliases for the common DOM attribute pairs.
    # ``__getattr__`` is only called when normal attribute lookup fails, so
    # explicit properties/attributes always win; this catches camelCase names
    # (e.g. ``textContent``, ``parentNode``) that we expose for jsdom parity.
    _CAMEL_ALIASES = {
        "parentNode": "parent_node",
        "childNodes": "child_nodes",
        "firstChild": "first_child",
        "lastChild": "last_child",
        "previousSibling": "previous_sibling",
        "nextSibling": "next_sibling",
        "parentElement": "parent_element",
        "firstElementChild": "first_element_child",
        "lastElementChild": "last_element_child",
        "previousElementSibling": "previous_element_sibling",
        "nextElementSibling": "next_element_sibling",
        "childElementCount": "child_element_count",
        "textContent": "text_content",
        "ownerDocument": "owner_document",
        "namespaceURI": "namespace_uri",
        "localName": "local_name",
        "tagName": "tag_name",
        "qualifiedName": "qualified_name",
        "innerHTML": "inner_html",
        "outerHTML": "outer_html",
        "className": "class_name",
        "classList": "class_list",
        "nodeName": "node_name",
        "nodeValue": "node_value",
        "nodeType": "node_type",
        # Events (EventTarget) — jsdom parity. Node keeps its own alias dict,
        # so it must mirror EventTarget's camelCase event names explicitly.
        "addEventListener": "add_event_listener",
        "removeEventListener": "remove_event_listener",
        "dispatchEvent": "dispatch_event",
    }

    def __getattr__(self, name: str):
        # Note: only invoked when normal lookup fails.
        snake = self._CAMEL_ALIASES.get(name)
        if snake is not None:
            return getattr(self, snake)
        raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

    # ---- navigation -------------------------------------------------------
    @property
    def parent_node(self) -> Optional["Node"]:
        return self._parent

    @property
    def child_nodes(self) -> NodeList:
        return NodeList(lambda: list(self._children))

    @property
    def first_child(self) -> Optional[Node]:
        return self._children[0] if self._children else None

    @property
    def last_child(self) -> Optional[Node]:
        return self._children[-1] if self._children else None

    @property
    def previous_sibling(self) -> Optional[Node]:
        if self._parent is None:
            return None
        siblings = self._parent._children
        idx = siblings.index(self)
        return siblings[idx - 1] if idx > 0 else None

    @property
    def next_sibling(self) -> Optional[Node]:
        if self._parent is None:
            return None
        siblings = self._parent._children
        idx = siblings.index(self)
        return siblings[idx + 1] if idx + 1 < len(siblings) else None

    @property
    def parent_element(self) -> Optional["Element"]:
        p = self._parent
        if p is not None and p.nodeType == ELEMENT_NODE:
            return p  # type: ignore[return-value]
        return None

    # ---- convenience hierarchy helpers -----------------------------------
    def _is_ancestor_of(self, node: "Node") -> bool:
        """True if ``self`` is an ancestor of (or equal to) ``node``."""
        cur: Optional[Node] = node
        while cur is not None:
            if cur is self:
                return True
            cur = cur._parent
        return False

    # ---- mutation ---------------------------------------------------------
    def append_child(self, node: "Node") -> "Node":
        """Append ``node`` as the last child of this node."""
        self._pre_insert_validation(node)
        return self._do_insert(node, None)

    def insert_before(self, node: "Node", child: Optional["Node"]) -> "Node":
        """Insert ``node`` immediately before ``child`` (or at the end)."""
        self._pre_insert_validation(node)
        if child is not None and child._parent is not self:
            raise NotFoundError("The node before which to insert is not a child of this node.")
        reference = child
        return self._do_insert(node, reference)

    def replace_child(self, new_child: "Node", old_child: "Node") -> "Node":
        """Replace ``old_child`` with ``new_child``; return ``old_child``."""
        if old_child._parent is not self:
            raise NotFoundError("The node to replace is not a child of this node.")
        self._pre_insert_validation(new_child)
        # Adopt / remove new_child from its current parent first.
        if new_child._parent is not None:
            new_child._parent.remove_child(new_child)
        idx = self._children.index(old_child)
        old_child._parent = None
        new_child._parent = self
        self._children[idx] = new_child
        return old_child

    def remove_child(self, node: "Node") -> "Node":
        """Remove ``node`` from this node's children; return it."""
        if node._parent is not self:
            raise NotFoundError("The node to remove is not a child of this node.")
        self._children.remove(node)
        node._parent = None
        return node

    def _pre_insert_validation(self, node: "Node") -> None:
        """The "pre-insert" validity checks from the spec."""
        if node.nodeType == DOCUMENT_NODE:
            raise HierarchyRequestError("Cannot insert a Document as a child.")
        if node is self:
            raise HierarchyRequestError("Cannot insert a node as a child of itself.")
        if node._is_ancestor_of(self):
            raise HierarchyRequestError("The new child is an ancestor of this node.")

    def _do_insert(self, node: "Node", reference: Optional["Node"]) -> "Node":
        # Detach from any previous parent (handles the "adopt" step implicitly
        # since our nodes are not bound to a separate document registry).
        if node._parent is not None:
            node._parent.remove_child(node)
        node._parent = self
        if reference is None:
            self._children.append(node)
        else:
            idx = self._children.index(reference)
            self._children.insert(idx, node)
        return node

    # ---- cloning ----------------------------------------------------------
    def _shallow_clone(self) -> "Node":
        raise NotImplementedError

    def clone_node(self, deep: bool = False) -> "Node":
        """Clone this node; when ``deep`` is true, also clone descendants."""
        clone = self._shallow_clone()
        if deep:
            for child in self._children:
                clone.append_child(child.clone_node(True))
        return clone

    # ---- text -------------------------------------------------------------
    @property
    def text_content(self) -> Optional[str]:
        """Concatenated descendant text, or None for nodes without text."""
        parts: List[str] = []
        for node in self._iter_descendants_inclusive():
            if node.nodeType in (TEXT_NODE, CDATA_SECTION_NODE):
                parts.append(node.data)  # type: ignore[attr-defined]
        if not parts:
            # Per spec, text_content is null on nodes with no text descendants
            # only for Document/DocumentType; we keep it as "" for ergonomics
            # except where the spec demands null. Use "" by default.
            return ""
        return "".join(parts)

    @text_content.setter
    def text_content(self, value: Optional[str]) -> None:
        # Replace all children with a single Text node (spec behavior).
        for child in list(self._children):
            self.remove_child(child)
        if value:
            from pydom.dom.text import Text  # local import: avoid cycle

            self.append_child(Text(value, owner_document=self.ownerDocument))

    # ---- traversal helpers -----------------------------------------------
    def iter_descendants(self) -> Iterator["Node"]:
        """Yield all descendants of this node (not including self), in document order."""
        for child in list(self._children):
            yield child
            yield from child.iter_descendants()

    def _iter_descendants_inclusive(self) -> Iterator["Node"]:
        yield self
        yield from self.iter_descendants()

    # ---- comparison -------------------------------------------------------
    def contains(self, other: Optional["Node"]) -> bool:
        if other is None:
            return False
        return self is other or self._is_ancestor_of(other)

    def compare_document_position(self, other: "Node") -> int:
        if self is other:
            return 0
        # If they share no root, they are disconnected.
        if self._root() is not other._root():
            return (
                Node.DOCUMENT_POSITION_DISCONNECTED
                | Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC
            )
        # Depth-first preorder indexes let us order any two nodes.
        self_chain = list(self._ancestor_chain())
        other_chain = list(other._ancestor_chain())
        # Find the common ancestor.
        common = None
        for anc in self_chain:
            if anc in other_chain:
                common = anc
                break
        if common is None:  # pragma: no cover - guarded by root check above
            return Node.DOCUMENT_POSITION_DISCONNECTED
        if common is self:
            return Node.DOCUMENT_POSITION_CONTAINS | Node.DOCUMENT_POSITION_PRECEDING
        if common is other:
            return Node.DOCUMENT_POSITION_CONTAINED_BY | Node.DOCUMENT_POSITION_FOLLOWING
        # Otherwise, order by child index under the common ancestor.
        kids = common._children
        self_idx = kids.index(self_chain[self_chain.index(common) + 1])
        other_idx = kids.index(other_chain[other_chain.index(common) + 1])
        if self_idx < other_idx:
            return Node.DOCUMENT_POSITION_PRECEDING
        return Node.DOCUMENT_POSITION_FOLLOWING

    def _root(self) -> "Node":
        cur: Node = self
        while cur._parent is not None:
            cur = cur._parent
        return cur

    def _ancestor_chain(self) -> Iterator["Node"]:
        """Self, then ancestors up to the root (self first)."""
        cur: Optional[Node] = self
        while cur is not None:
            yield cur
            cur = cur._parent

    # ---- normalization ----------------------------------------------------
    def normalize(self) -> None:
        """Merge adjacent Text nodes and drop empty ones (spec: normalize)."""
        merged: List[Node] = []
        for child in list(self._children):
            child.normalize()
            if child.nodeType == TEXT_NODE and child.data == "":  # type: ignore[attr-defined]
                self.remove_child(child)
                continue
            if (
                child.nodeType == TEXT_NODE
                and merged
                and merged[-1].nodeType == TEXT_NODE
            ):
                merged[-1].data += child.data  # type: ignore[attr-defined]
                self.remove_child(child)
                continue
            merged.append(child)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.nodeName!r}>"
