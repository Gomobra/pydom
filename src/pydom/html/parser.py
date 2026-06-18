"""HTML parsing — WHATWG-compliant parsing via :mod:`html5lib`.

Exposes:
* :func:`parse_html` — parse a full document string into a :class:`Document`.
* :func:`parse_fragment` — parse a fragment string into a ``DocumentFragment``.
* :func:`parse_fragment_into` — parse a fragment and append the nodes to an
  existing element (used by ``Element.innerHTML`` setter).

html5lib performs the actual tokenization and tree construction; we then hand
its etree output to :mod:`pydom.dom.tree_construction` to materialize our own
node objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import html5lib

from pydom.dom.document import Document
from pydom.dom.tree_construction import etree_list_to_fragment, etree_to_document

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.dom.element import Element

# html5lib normalizes the content type internally; we only need to know whether
# to treat the input as HTML or XHTML for our own document bookkeeping.
HTML_MIME_TYPES = frozenset({"text/html", "application/xhtml+xml"})


def parse_html(
    html: str,
    *,
    content_type: str = "text/html",
    url: str = "about:blank",
) -> Document:
    """Parse ``html`` as a full document and return a populated :class:`Document`."""
    if content_type not in HTML_MIME_TYPES:
        # Non-HTML/XML content types are rejected per jsdom semantics.
        raise ValueError(f"Unsupported content type for HTML parsing: {content_type!r}")

    document = Document(content_type=content_type, url=url)
    etree_root = html5lib.parse(html, treebuilder="etree")
    etree_to_document(etree_root, document=document)
    return document


def parse_fragment(
    html: str,
    *,
    owner_document: Document,
    container: str = "div",
):
    """Parse ``html`` as a fragment; return a ``DocumentFragment``."""
    etree_nodes = html5lib.parseFragment(html, container=container, treebuilder="etree")
    return etree_list_to_fragment(etree_nodes, owner_document=owner_document)


def parse_fragment_into(html: str, target: "Element") -> None:
    """Parse ``html`` and append the resulting nodes onto ``target``.

    Used by ``Element.innerHTML`` / ``outerHTML`` setters. The fragment is
    parsed using ``target``'s tag name as the parsing context so that the
    right insertion rules apply (e.g. parsing inside ``table``).
    """
    owner_document = target.ownerDocument or _fallback_document()
    container = target.local_name or "div"
    frag = parse_fragment(html, owner_document=owner_document, container=container)
    for child in list(frag.child_nodes):
        frag.remove_child(child)
        target.append_child(child)


def _fallback_document() -> Document:
    # A detached element (no ownerDocument) still needs somewhere to anchor
    # freshly-created nodes; a throwaway document works fine.
    return Document()
