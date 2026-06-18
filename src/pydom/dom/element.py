"""The :class:`Element` interface.

Implements element-level attributes, ID/class reflection, the HTML-collection
lookups, ``innerHTML``/``outerHTML`` (delegating serialization to
:mod:`pydom.html.serializer` lazily), and CSS-selector querying (delegating to
:mod:`pydom.selectors.engine` lazily).

Reference: https://dom.spec.whatwg.org/#interface-element
           https://html.spec.whatwg.org/#htmlelement
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Iterator, List, Optional

from pydom.dom.exceptions import NamespaceError
from pydom.dom.node import ELEMENT_NODE, Node
from pydom.dom.nodelist import HTMLCollection, NodeList

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.dom.attr import Attr
    from pydom.dom.document import Document


# Void elements have no end tag and cannot contain content.
VOID_ELEMENTS = frozenset(
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
)


class DOMTokenList:
    """An ordered set of space-separated tokens (backs ``classList``)."""

    def __init__(self, element: "Element", attr: str = "class") -> None:
        self._element = element
        self._attr = attr

    def _tokens(self) -> List[str]:
        raw = self._element.get_attribute(self._attr) or ""
        # Per spec, the token list is the result of splitting on ASCII
        # whitespace and removing duplicates, preserving first-seen order.
        seen: List[str] = []
        for tok in raw.split():
            if tok not in seen:
                seen.append(tok)
        return seen

    def _commit(self, tokens: List[str]) -> None:
        if tokens:
            self._element.set_attribute(self._attr, " ".join(tokens))
        else:
            self._element.remove_attribute(self._attr)

    @property
    def length(self) -> int:
        return len(self._tokens())

    def item(self, index: int) -> Optional[str]:
        toks = self._tokens()
        if index < 0 or index >= len(toks):
            return None
        return toks[index]

    def contains(self, token: str) -> bool:
        return token in self._tokens()

    def add(self, *tokens: str) -> None:
        current = self._tokens()
        for tok in tokens:
            if tok not in current:
                current.append(tok)
        self._commit(current)

    def remove(self, *tokens: str) -> None:
        current = [t for t in self._tokens() if t not in tokens]
        self._commit(current)

    def toggle(self, token: str, force: Optional[bool] = None) -> bool:
        present = token in self._tokens()
        if force is None:
            force = not present
        if force and not present:
            self.add(token)
        elif not force and present:
            self.remove(token)
        return force

    def replace(self, old: str, new: str) -> bool:
        toks = self._tokens()
        if old not in toks:
            return False
        toks[toks.index(old)] = new
        self._commit(toks)
        return True

    def __iter__(self) -> Iterator[str]:
        return iter(self._tokens())

    def __len__(self) -> int:
        return len(self._tokens())

    def __contains__(self, token: str) -> bool:
        return self.contains(token)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"DOMTokenList({self._tokens()!r})"


class NamedNodeMap:
    """The live ``attributes`` collection of an element."""

    def __init__(self, element: "Element") -> None:
        self._element = element

    @property
    def length(self) -> int:
        return len(self._element._attrs)

    def get_named_item(self, name: str) -> Optional["Attr"]:
        return self._element._attrs.get(name.lower())

    def set_named_item(self, attr: "Attr") -> None:
        self._element._set_attr_node(attr)

    def remove_named_item(self, name: str) -> "Attr":
        return self._element._remove_attr_node(name.lower())

    def item(self, index: int) -> Optional["Attr"]:
        items = list(self._element._attrs.values())
        if index < 0 or index >= len(items):
            return None
        return items[index]

    def __iter__(self) -> Iterator["Attr"]:
        return iter(self._element._attrs.values())

    def __len__(self) -> int:
        return len(self._element._attrs)

    def __getitem__(self, name: str) -> Optional["Attr"]:
        return self.get_named_item(name)


class Element(Node):
    nodeType = ELEMENT_NODE

    def __init__(
        self,
        local_name: str,
        *,
        namespace: Optional[str] = None,
        prefix: Optional[str] = None,
        owner_document: Optional["Document"] = None,
    ) -> None:
        super().__init__(owner_document=owner_document)
        self.local_name: str = local_name
        self.namespace_uri: Optional[str] = namespace
        self.prefix: Optional[str] = prefix
        # Attribute storage keyed by lowercased qualified name.
        self._attrs: Dict[str, "Attr"] = {}

    # ---- naming -----------------------------------------------------------
    @property
    def tag_name(self) -> str:
        # HTML elements uppercase the tag name; foreign (XML/SVG) do not.
        if self.namespace_uri is None or self.namespace_uri == "http://www.w3.org/1999/xhtml":
            return self.qualified_name.upper()
        return self.qualified_name

    @property
    def node_name(self) -> str:  # type: ignore[override]
        return self.tag_name

    @property
    def qualified_name(self) -> str:
        if self.prefix:
            return f"{self.prefix}:{self.local_name}"
        return self.local_name

    @property
    def is_html_element(self) -> bool:
        return self.namespace_uri in (None, "http://www.w3.org/1999/xhtml")

    # ---- attribute access -------------------------------------------------
    @property
    def attributes(self) -> NamedNodeMap:
        return NamedNodeMap(self)

    def get_attribute(self, name: str) -> Optional[str]:
        attr = self._attrs.get(name.lower())
        return attr.value if attr is not None else None

    def get_attribute_ns(self, namespace: Optional[str], local_name: str) -> Optional[str]:
        for attr in self._attrs.values():
            if attr.namespace_uri == namespace and attr.local_name == local_name:
                return attr.value
        return None

    def set_attribute(self, name: str, value: str) -> None:
        self._validate_qualified_name(name)
        key = name.lower()
        attr = self._attrs.get(key)
        if attr is not None:
            attr.value = str(value)
        else:
            from pydom.dom.attr import Attr

            self._set_attr_node(
                Attr(name.lower(), str(value), owner_element=self, owner_document=self.ownerDocument)
            )

    def set_attribute_ns(self, namespace: Optional[str], qualified_name: str, value: str) -> None:
        prefix, local = self._split_qualified(qualified_name)
        from pydom.dom.attr import Attr

        # Remove any existing attr with the same ns+local.
        for key, attr in list(self._attrs.items()):
            if attr.namespace_uri == namespace and attr.local_name == local:
                del self._attrs[key]
        self._set_attr_node(
            Attr(
                local,
                str(value),
                namespace=namespace,
                prefix=prefix,
                owner_element=self,
                owner_document=self.ownerDocument,
            )
        )

    def remove_attribute(self, name: str) -> None:
        self._attrs.pop(name.lower(), None)

    def remove_attribute_ns(self, namespace: Optional[str], local_name: str) -> None:
        for key, attr in list(self._attrs.items()):
            if attr.namespace_uri == namespace and attr.local_name == local_name:
                del self._attrs[key]

    def has_attribute(self, name: str) -> bool:
        return name.lower() in self._attrs

    def has_attribute_ns(self, namespace: Optional[str], local_name: str) -> bool:
        return self.get_attribute_ns(namespace, local_name) is not None

    def toggle_attribute(self, name: str, force: Optional[bool] = None) -> bool:
        present = self.has_attribute(name)
        if force is None:
            force = not present
        if force and not present:
            self.set_attribute(name, "")
        elif not force and present:
            self.remove_attribute(name)
        return force

    def _set_attr_node(self, attr: "Attr") -> None:
        attr.owner_element = self
        self._attrs[attr.name.lower()] = attr

    def _remove_attr_node(self, key: str) -> "Attr":
        from pydom.dom.exceptions import NotFoundError

        attr = self._attrs.get(key)
        if attr is None:
            raise NotFoundError(f"No attribute named {key!r}")
        del self._attrs[key]
        attr.owner_element = None
        return attr

    @staticmethod
    def _validate_qualified_name(name: str) -> None:
        if not name:
            from pydom.dom.exceptions import InvalidCharacterError

            raise InvalidCharacterError("Attribute name cannot be empty.")
        if any(c.isspace() for c in name) or any(ord(c) < 0x20 for c in name):
            from pydom.dom.exceptions import InvalidCharacterError

            raise InvalidCharacterError(f"Invalid attribute name {name!r}.")

    @staticmethod
    def _split_qualified(qualified_name: str):
        if ":" in qualified_name:
            prefix, local = qualified_name.split(":", 1)
            if not prefix or not local or ":" in local:
                raise NamespaceError(f"Invalid qualified name {qualified_name!r}")
            return prefix, local
        return None, qualified_name

    # ---- reflection: id / className / classList ---------------------------
    @property
    def id(self) -> str:
        return self.get_attribute("id") or ""

    @id.setter
    def id(self, value: str) -> None:
        self.set_attribute("id", value)

    @property
    def class_name(self) -> str:
        return self.get_attribute("class") or ""

    @class_name.setter
    def class_name(self, value: str) -> None:
        self.set_attribute("class", value)

    @property
    def class_list(self) -> DOMTokenList:
        return DOMTokenList(self, "class")

    # ---- element-only children -------------------------------------------
    @property
    def children(self) -> HTMLCollection:
        return HTMLCollection(lambda: [c for c in self._children if c.nodeType == ELEMENT_NODE])

    @property
    def first_element_child(self) -> Optional["Element"]:
        for c in self._children:
            if c.nodeType == ELEMENT_NODE:
                return c  # type: ignore[return-value]
        return None

    @property
    def last_element_child(self) -> Optional["Element"]:
        for c in reversed(self._children):
            if c.nodeType == ELEMENT_NODE:
                return c  # type: ignore[return-value]
        return None

    @property
    def previous_element_sibling(self) -> Optional["Element"]:
        sib = self.previous_sibling
        while sib is not None and sib.nodeType != ELEMENT_NODE:
            sib = sib.previous_sibling
        return sib  # type: ignore[return-value]

    @property
    def next_element_sibling(self) -> Optional["Element"]:
        sib = self.next_sibling
        while sib is not None and sib.nodeType != ELEMENT_NODE:
            sib = sib.next_sibling
        return sib  # type: ignore[return-value]

    @property
    def child_element_count(self) -> int:
        return sum(1 for c in self._children if c.nodeType == ELEMENT_NODE)

    # ---- tree queries (getElementsByTagName/ClassName) --------------------
    def get_elements_by_tag_name(self, qualified_name: str) -> HTMLCollection:
        q = qualified_name.lower()
        ns_html = "http://www.w3.org/1999/xhtml"

        def provider() -> List["Element"]:
            result: List[Element] = []
            for node in self.iter_descendants():
                if node.nodeType != ELEMENT_NODE:
                    continue
                el = node  # type: ignore[assignment]
                if q == "*":
                    result.append(el)
                elif el.is_html_element:
                    if el.local_name == q:
                        result.append(el)
                else:
                    # Foreign elements match on the exact qualified name.
                    if el.qualified_name == qualified_name:
                        result.append(el)
            return result

        return HTMLCollection(provider)

    def get_elements_by_class_name(self, class_names: str) -> HTMLCollection:
        wanted = class_names.split()

        def provider() -> List["Element"]:
            if not wanted:
                return []
            result: List[Element] = []
            for node in self.iter_descendants():
                if node.nodeType != ELEMENT_NODE:
                    continue
                el = node  # type: ignore[assignment]
                classes = (el.get_attribute("class") or "").split()
                if all(w in classes for w in wanted):
                    result.append(el)
            return result

        return HTMLCollection(provider)

    def get_elements_by_tag_name_ns(
        self, namespace: Optional[str], local_name: str
    ) -> HTMLCollection:
        def provider() -> List["Element"]:
            result: List[Element] = []
            for node in self.iter_descendants():
                if node.nodeType != ELEMENT_NODE:
                    continue
                el = node  # type: ignore[assignment]
                if local_name != "*" and el.local_name != local_name:
                    continue
                if namespace != "*" and el.namespace_uri != namespace:
                    continue
                result.append(el)
            return result

        return HTMLCollection(provider)

    # ---- closest / matches ------------------------------------------------
    def closest(self, selector: str) -> Optional["Element"]:
        from pydom.selectors.engine import matches as _matches

        cur: Optional[Element] = self
        while cur is not None:
            if _matches(cur, selector):
                return cur
            cur = cur.parent_element
        return None

    def matches(self, selector: str) -> bool:
        from pydom.selectors.engine import matches as _matches

        return _matches(self, selector)

    # ---- querySelector ----------------------------------------------------
    def query_selector(self, selector: str) -> Optional["Element"]:
        from pydom.selectors.engine import query_selector

        return query_selector(self, selector)

    def query_selector_all(self, selector: str) -> NodeList:
        from pydom.selectors.engine import query_selector_all

        return query_selector_all(self, selector)

    # ---- serialization hooks (lazy import avoids cycles) -----------------
    @property
    def inner_html(self) -> str:
        from pydom.html.serializer import serialize

        return "".join(serialize(c) for c in self._children)

    @inner_html.setter
    def inner_html(self, value: str) -> None:
        # Remove existing children, then parse the fragment into this element.
        for child in list(self._children):
            self.remove_child(child)
        from pydom.html.parser import parse_fragment_into

        parse_fragment_into(value, self)

    @property
    def outer_html(self) -> str:
        from pydom.html.serializer import serialize

        return serialize(self)

    @outer_html.setter
    def outer_html(self, value: str) -> None:
        parent = self._parent
        if parent is None:
            from pydom.dom.exceptions import DOMException

            raise DOMException(
                "Cannot set outer_html on a node with no parent.",
                "NoModificationAllowedError",
            )
        from pydom.html.parser import parse_fragment

        # Parse the replacement markup into a transient fragment, then splice
        # its children in place of this element within the parent.
        owner = self.ownerDocument
        frag = parse_fragment(value, owner_document=owner, container=self.local_name or "div")
        idx = parent._children.index(self)
        parent._children.remove(self)
        self._parent = None
        for offset, child in enumerate(list(frag.child_nodes)):
            frag.remove_child(child)
            parent._children.insert(idx + offset, child)
            child._parent = parent

    # ---- cloning ----------------------------------------------------------
    def _shallow_clone(self) -> "Element":
        clone = Element(
            self.local_name,
            namespace=self.namespace_uri,
            prefix=self.prefix,
            owner_document=self.ownerDocument,
        )
        for attr in self._attrs.values():
            clone._set_attr_node(attr._shallow_clone())  # type: ignore[attr-defined]
        return clone

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        attrs = "".join(f" {a.name}={a.value!r}" for a in self._attrs.values())
        return f"<{type(self).__name__} {self.qualified_name}{attrs}>"
