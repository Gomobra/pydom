"""The :class:`Document` interface — the root document node.

Mirrors the subset of jsdom's Document relevant to phase 1: element/text/attr
factories, ``getElementById`` / ``getElementsByTagName`` lookups,
``documentElement`` / ``head`` / ``body`` accessors, and CSS-selector querying.

Reference: https://dom.spec.whatwg.org/#interface-document
           https://html.spec.whatwg.org/#the-document-object
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from pydom.dom.element import ELEMENT_NODE, Element
from pydom.dom.exceptions import NotSupportedError
from pydom.dom.node import DOCUMENT_NODE, Node
from pydom.dom.nodelist import HTMLCollection, NodeList
from pydom.dom.text import Comment, Text

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.browser.window import Window

XHTML_NS = "http://www.w3.org/1999/xhtml"


class DocumentType(Node):
    """A ``<!DOCTYPE …>`` declaration."""

    nodeType = 10  # DOCUMENT_TYPE_NODE

    def __init__(
        self,
        name: str,
        public_id: str = "",
        system_id: str = "",
        owner_document: Optional["Document"] = None,
    ) -> None:
        super().__init__(owner_document=owner_document)
        self.name = name
        self.public_id = public_id
        self.system_id = system_id

    @property
    def node_name(self) -> str:  # type: ignore[override]
        return self.name

    def _shallow_clone(self) -> "DocumentType":
        return DocumentType(
            self.name, self.public_id, self.system_id, owner_document=self.ownerDocument
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<!DOCTYPE {self.name}>"


class Document(Node):
    nodeType = DOCUMENT_NODE

    def __init__(
        self,
        *,
        content_type: str = "text/html",
        url: str = "about:blank",
        default_view: Optional["Window"] = None,
    ) -> None:
        super().__init__(owner_document=None)
        # A Document is its own owner document.
        self.ownerDocument = self
        self.content_type = content_type
        self.url = url
        self.document_uri = url
        self.compat_mode = "CSS1Compat"
        self.character_set = "UTF-8"
        self.charset = "UTF-8"
        self.input_encoding = "UTF-8"
        self.default_view: Optional["Window"] = default_view

    @property
    def node_name(self) -> str:  # type: ignore[override]
        return "#document"

    @property
    def implementation(self):
        return _DOMImplementation(self)

    # ---- structural accessors --------------------------------------------
    @property
    def document_element(self) -> Optional[Element]:
        for c in self._children:
            if c.nodeType == ELEMENT_NODE:
                return c  # type: ignore[return-value]
        return None

    @property
    def doctype(self) -> Optional[DocumentType]:
        for c in self._children:
            if c.nodeType == 10:
                return c  # type: ignore[return-value]
        return None

    @property
    def head(self) -> Optional[Element]:
        root = self.document_element
        if root is None:
            return None
        for c in root._children:
            if c.nodeType == ELEMENT_NODE and c.local_name == "head":  # type: ignore[union-attr]
                return c  # type: ignore[return-value]
        return None

    @property
    def body(self) -> Optional[Element]:
        root = self.document_element
        if root is None:
            return None
        for c in root._children:
            if c.nodeType == ELEMENT_NODE and c.local_name == "body":  # type: ignore[union-attr]
                return c  # type: ignore[return-value]
        return None

    # ---- creation factories ----------------------------------------------
    def create_element(self, local_name: str) -> Element:
        self._validate_html_name(local_name)
        return _create_html_element(local_name.lower(), owner_document=self)

    def create_element_ns(self, namespace: Optional[str], qualified_name: str) -> Element:
        prefix, local = Element._split_qualified(qualified_name)
        return Element(
            local,
            namespace=namespace,
            prefix=prefix,
            owner_document=self,
        )

    def create_text_node(self, data: str = "") -> Text:
        return Text(data, owner_document=self)

    def create_comment(self, data: str = "") -> Comment:
        return Comment(data, owner_document=self)

    def create_document_fragment(self):
        from pydom.dom.document_fragment import DocumentFragment

        return DocumentFragment(owner_document=self)

    def create_attribute(self, local_name: str):
        from pydom.dom.attr import Attr

        self._validate_html_name(local_name)
        return Attr(local_name.lower(), "", owner_document=self)

    # ---- lookups ----------------------------------------------------------
    def get_element_by_id(self, element_id: str) -> Optional[Element]:
        for node in self.iter_descendants():
            if node.nodeType == ELEMENT_NODE and node.get_attribute("id") == element_id:  # type: ignore[attr-defined]
                return node  # type: ignore[return-value]
        return None

    def get_elements_by_tag_name(self, qualified_name: str) -> HTMLCollection:
        return Element.get_elements_by_tag_name(self, qualified_name)  # type: ignore[arg-type]

    def get_elements_by_class_name(self, class_names: str) -> HTMLCollection:
        return Element.get_elements_by_class_name(self, class_names)  # type: ignore[arg-type]

    def get_elements_by_tag_name_ns(
        self, namespace: Optional[str], local_name: str
    ) -> HTMLCollection:
        return Element.get_elements_by_tag_name_ns(self, namespace, local_name)  # type: ignore[arg-type]

    @property
    def child_nodes(self) -> NodeList:  # type: ignore[override]
        return NodeList(lambda: list(self._children))

    # ---- selectors --------------------------------------------------------
    def query_selector(self, selector: str) -> Optional[Element]:
        from pydom.selectors.engine import query_selector

        return query_selector(self, selector)  # type: ignore[arg-type]

    def query_selector_all(self, selector: str) -> NodeList:
        from pydom.selectors.engine import query_selector_all

        return query_selector_all(self, selector)  # type: ignore[arg-type]

    # ---- title ------------------------------------------------------------
    @property
    def title(self) -> str:
        head = self.head
        if head is None:
            return ""
        for node in head.iter_descendants():
            if node.nodeType == ELEMENT_NODE and node.local_name == "title":  # type: ignore[union-attr]
                return node.text_content or ""  # type: ignore[union-attr]
        return ""

    @title.setter
    def title(self, value: str) -> None:
        head = self.head
        if head is None:
            return
        for node in list(head.iter_descendants()):
            if node.nodeType == ELEMENT_NODE and node.local_name == "title":  # type: ignore[union-attr]
                node.text_content = value  # type: ignore[union-attr]
                return
        title_el = self.create_element("title")
        title_el.text_content = value
        head.append_child(title_el)

    # ---- naming helpers ---------------------------------------------------
    @staticmethod
    def _validate_html_name(local_name: str) -> None:
        if not local_name:
            from pydom.dom.exceptions import InvalidCharacterError

            raise InvalidCharacterError("Element local name cannot be empty.")

    def _shallow_clone(self) -> "Document":
        clone = Document(
            content_type=self.content_type,
            url=self.url,
            default_view=self.default_view,
        )
        return clone

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Document url={self.url!r}>"


class _DOMImplementation:
    """A minimal ``DOMImplementation`` facade (``hasFeature`` etc.)."""

    def __init__(self, document: Document) -> None:
        self._document = document

    def has_feature(self, feature: str = "", version: str = "") -> bool:
        # Always true per the spec (legacy method kept for completeness).
        return True

    def create_document(
        self, namespace: Optional[str], qualified_name: str, doctype=None
    ) -> Document:
        doc = Document()
        if doctype is not None:
            doc.append_child(doctype)
        root = doc.create_element_ns(namespace, qualified_name)
        doc.append_child(root)
        return doc

    def create_html_document(self, title: str = "") -> Document:
        doc = Document()
        doctype = DocumentType("html", owner_document=doc)
        doc.append_child(doctype)
        html = doc.create_element("html")
        head = doc.create_element("head")
        if title:
            title_el = doc.create_element("title")
            title_el.text_content = title
            head.append_child(title_el)
        body = doc.create_element("body")
        html.append_child(head)
        html.append_child(body)
        doc.append_child(html)
        return doc


def _create_html_element(local_name: str, *, owner_document: Document) -> Element:
    """Factory: map an HTML tag name to the right Element subclass.

    Phase 1 collapses everything to :class:`HTMLElement`/``Element`` except a
    few elements that need bespoke handling later (none yet). This mirrors
    jsdom's behavior where non-inherited tags are plain ``HTMLElement``s.
    """
    return HTMLElement(local_name, namespace=XHTML_NS, owner_document=owner_document)


class HTMLElement(Element):
    """The base class for all HTML elements (namespace = XHTML)."""

    def __init__(self, local_name: str, *, namespace: str = XHTML_NS, owner_document: Optional[Document] = None) -> None:
        super().__init__(local_name, namespace=namespace, owner_document=owner_document)
