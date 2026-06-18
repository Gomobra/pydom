"""HTML serialization — the "HTML fragment serialization algorithm".

Converts a pydom :class:`~pydom.dom.node.Node` tree back into an HTML string,
following the WHATWG HTML serialization rules: void elements have no end tag,
text inside raw-text elements (script/style) is emitted verbatim, attribute
values are quoted and escaped, and text is escaped per context.

Reference: https://html.spec.whatwg.org/#html-fragment-serialisation-algorithm
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from pydom.dom.element import VOID_ELEMENTS
from pydom.dom.node import (
    CDATA_SECTION_NODE,
    COMMENT_NODE,
    DOCUMENT_TYPE_NODE,
    TEXT_NODE,
    Node,
)

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.dom.document import Document

# Elements whose content is not parsed as HTML (raw text / escapable raw text).
RAW_TEXT_ELEMENTS = frozenset({"script", "style"})
ESCAPABLE_RAW_TEXT_ELEMENTS = frozenset({"textarea", "title"})

# Minimal, spec-correct text escaping per context.
_TEXT_ESCAPE = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})
_ATTR_ESCAPE = str.maketrans(
    {"&": "&amp;", '"': "&quot;", "<": "&lt;", ">": "&gt;"}
)


def serialize(node: Node) -> str:
    """Serialize any node (Document, Element, Text, …) to an HTML string."""
    out: list[str] = []
    for chunk in _iter_serialize(node, raw=False):
        out.append(chunk)
    return "".join(out)


def serialize_children(node: Node) -> Iterator[str]:
    """Yield serialized HTML for the children of ``node`` only.

    Used by ``Element.inner_html`` so it can render a fragment without the
    element's own tags.
    """
    raw = _is_raw_text(node)
    for child in node.child_nodes:
        yield from _iter_serialize(child, raw=raw)


def _iter_serialize(node: Node, *, raw: bool) -> Iterator[str]:
    nt = node.nodeType

    if nt == DOCUMENT_TYPE_NODE:
        # Spec: if the doctype is for html, emit "<!DOCTYPE html>".
        yield _serialize_doctype(node)  # type: ignore[arg-type]
        return

    if nt == TEXT_NODE or nt == CDATA_SECTION_NODE:
        yield _serialize_text(node, raw=raw)  # type: ignore[arg-type]
        return

    if nt == COMMENT_NODE:
        yield f"<!--{node.data}-->"  # type: ignore[attr-defined]
        return

    if nt == 9:  # DOCUMENT_NODE
        for child in node.child_nodes:
            yield from _iter_serialize(child, raw=False)
        return

    if nt == 11:  # DOCUMENT_FRAGMENT_NODE
        for child in node.child_nodes:
            yield from _iter_serialize(child, raw=False)
        return

    if nt == 7:  # PROCESSING_INSTRUCTION_NODE
        yield f"<?{node.target} {node.data}>"  # type: ignore[attr-defined]
        return

    if nt == 1:  # ELEMENT_NODE
        yield from _serialize_element(node)  # type: ignore[arg-type]
        return

    # Unknown node types contribute nothing.
    return


def _serialize_element(el) -> Iterator[str]:
    name = el.qualified_name
    # Opening tag: "<name" + each attribute + ">".
    yield f"<{name}"
    yield from _serialize_attributes(el)
    yield ">"

    if el.local_name in VOID_ELEMENTS:
        return  # void elements never have children or an end tag

    child_raw = _is_raw_text(el)
    for child in el.child_nodes:
        yield from _iter_serialize(child, raw=child_raw)

    yield f"</{name}>"


def _serialize_attributes(el) -> Iterator[str]:
    for attr in el._attrs.values():  # type: ignore[attr-defined]
        name = attr.name
        value = attr.value
        if value is None:
            yield f" {name}"
            continue
        yield f' {name}="{_escape_attr(value)}"'


def _serialize_text(node, *, raw: bool) -> str:
    data = node.data
    if raw:
        # Inside script/style: emit verbatim (no escaping).
        return data
    # Escapable raw text (textarea/title) escapes & only; but to be safe and
    # spec-aligned for normal text we use the full text escaping table.
    return data.translate(_TEXT_ESCAPE)


def _serialize_doctype(doctype) -> str:
    # Spec serialization of the doctype.
    if doctype.name and not doctype.public_id and not doctype.system_id:
        return f"<!DOCTYPE {doctype.name}>"
    parts = [f"<!DOCTYPE {doctype.name}"]
    if doctype.public_id:
        parts.append(f' PUBLIC "{doctype.public_id}"')
        if doctype.system_id:
            parts.append(f' "{doctype.system_id}"')
    elif doctype.system_id:
        parts.append(f' SYSTEM "{doctype.system_id}"')
    parts.append(">")
    return "".join(parts)


def _escape_attr(value: str) -> str:
    return value.translate(_ATTR_ESCAPE)


def _is_raw_text(node) -> bool:
    return (
        node.nodeType == 1
        and getattr(node, "local_name", None) in RAW_TEXT_ELEMENTS
    )
