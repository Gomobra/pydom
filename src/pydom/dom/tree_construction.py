"""Build a pydom :class:`~pydom.dom.node.Node` tree from an html5lib etree.

html5lib's ``etree`` treebuilder emits ``xml.etree.ElementTree.Element`` nodes
whose tags carry the namespace as a Clark notation prefix
(``{http://www.w3.org/1999/xhtml}p``) and whose text content is split across
``.text`` (leading text) and ``.tail`` (text following each element). This
module flattens that representation into our flat child-list node model.

Reference: https://html.spec.whatwg.org/#parsing
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Optional

from pydom.dom.attr import Attr
from pydom.dom.document import XHTML_NS, Document, DocumentType, HTMLElement
from pydom.dom.element import Element
from pydom.dom.node import COMMENT_NODE, Node
from pydom.dom.text import Comment, Text

XHTML = "{http://www.w3.org/1999/xhtml}"

# html5lib represents comment and doctype nodes in the etree using special
# sentinels/objects rather than string tags.
_HTML5LIB_COMMENT_FACTORY = None  # resolved lazily


def _is_comment(el) -> bool:
    """True if ``el`` is an html5lib etree comment node."""
    tag = el.tag
    if isinstance(tag, str):
        return False
    # html5lib comments use ET.Comment as the tag, which is a function object.
    return callable(tag) and getattr(tag, "__name__", "") == "Comment"


def _parse_namespaced_tag(tag: str) -> tuple[Optional[str], str, Optional[str]]:
    """Split a Clark-notation tag into (namespace, local_name, prefix).

    html5lib etree tags never carry an XML prefix (only the namespace URI), so
    ``prefix`` is always None for parsed markup; we return it for symmetry.
    """
    if tag.startswith("{"):
        ns, local = tag[1:].split("}", 1)
        return ns, local, None
    return None, tag, None


def etree_to_document(etree_root, *, document: Document) -> None:
    """Populate ``document`` from an html5lib etree document root.

    ``etree_root`` is the ``<html>`` element produced by html5lib's etree
    treebuilder. We synthesize a ``<!DOCTYPE html>`` when the input document
    looked like HTML (html5lib's etree treebuilder drops the doctype).
    """
    # A real HTML document parsed by html5lib always has an html root; we
    # always emit the html doctype for text/html content.
    document.append_child(DocumentType("html", owner_document=document))
    root_el = _convert_element(etree_root, owner_document=document)
    document.append_child(root_el)


def etree_list_to_fragment(etree_nodes, *, owner_document: Document):
    """Convert a list of etree nodes into a fresh DocumentFragment."""
    from pydom.dom.document_fragment import DocumentFragment

    frag = DocumentFragment(owner_document=owner_document)
    for node in etree_nodes:
        _append_converted(node, parent=frag, owner_document=owner_document)
    return frag


def _append_converted(etree_node, *, parent: Node, owner_document: Document) -> None:
    """Convert one etree node (element/comment/text) and attach to ``parent``."""
    if isinstance(etree_node, str):
        if etree_node:
            parent.append_child(Text(etree_node, owner_document=owner_document))
        return
    if _is_comment(etree_node):
        parent.append_child(Comment(etree_node.text or "", owner_document=owner_document))
        return
    if etree_node.tag is None:
        # Pure text element from html5lib (rare); treat its text as text.
        if etree_node.text:
            parent.append_child(Text(etree_node.text, owner_document=owner_document))
        return
    parent.append_child(_convert_element(etree_node, owner_document=owner_document))


def _convert_element(el, *, owner_document: Document) -> Element:
    namespace, local, prefix = _parse_namespaced_tag(el.tag)
    if namespace == XHTML_NS:
        node = HTMLElement(local, namespace=XHTML_NS, owner_document=owner_document)
    else:
        node = Element(local, namespace=namespace, prefix=prefix, owner_document=owner_document)

    for name, value in el.attrib.items():
        # html5lib may namespace some attributes with Clark notation too.
        attr_ns, attr_local, attr_prefix = _parse_namespaced_tag(name)
        node._set_attr_node(
            Attr(
                attr_local,
                value,
                namespace=attr_ns,
                prefix=attr_prefix,
                owner_element=node,
                owner_document=owner_document,
            )
        )

    # Leading text (.text) becomes the first child if present.
    if el.text:
        node.append_child(Text(el.text, owner_document=owner_document))

    # Children, then each child's trailing text (.tail).
    for child in el:
        _append_converted(child, parent=node, owner_document=owner_document)
        if child.tail:
            node.append_child(Text(child.tail, owner_document=owner_document))

    return node
