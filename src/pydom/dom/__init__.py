"""DOM core (Document Object Model) — Node tree, elements, documents."""

from pydom.dom.attr import Attr
from pydom.dom.document import Document, DocumentType, HTMLElement
from pydom.dom.document_fragment import DocumentFragment
from pydom.dom.element import DOMTokenList, Element, NamedNodeMap
from pydom.dom.exceptions import DOMException
from pydom.dom.node import (
    ATTRIBUTE_NODE,
    CDATA_SECTION_NODE,
    COMMENT_NODE,
    DOCUMENT_FRAGMENT_NODE,
    DOCUMENT_NODE,
    DOCUMENT_TYPE_NODE,
    ELEMENT_NODE,
    Node,
    PROCESSING_INSTRUCTION_NODE,
    TEXT_NODE,
)
from pydom.dom.nodelist import HTMLCollection, NodeList
from pydom.dom.text import CharacterData, Comment, Text

__all__ = [
    # Core classes
    "Node",
    "Element",
    "HTMLElement",
    "Attr",
    "Text",
    "Comment",
    "CharacterData",
    "Document",
    "DocumentType",
    "DocumentFragment",
    "DOMException",
    # Collections
    "NodeList",
    "HTMLCollection",
    "NamedNodeMap",
    "DOMTokenList",
    # nodeType constants
    "ELEMENT_NODE",
    "ATTRIBUTE_NODE",
    "TEXT_NODE",
    "CDATA_SECTION_NODE",
    "PROCESSING_INSTRUCTION_NODE",
    "COMMENT_NODE",
    "DOCUMENT_NODE",
    "DOCUMENT_TYPE_NODE",
    "DOCUMENT_FRAGMENT_NODE",
]
