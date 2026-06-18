"""The public :class:`JSDOM` API — the entry point for pydom.

Modeled closely on jsdom's ``JSDOM`` constructor and convenience methods:

* ``new JSDOM(html, options)``
* ``JSDOM.fromURL(url, options)``
* ``JSDOM.fromFile(filename, options)``
* ``JSDOM.fragment(html)``

Reference: https://github.com/jsdom/jsdom/blob/main/README.md
"""

from __future__ import annotations

import io
import os
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

import httpx

from pydom.browser.window import Window
from pydom.dom.document import Document
from pydom.dom.document_fragment import DocumentFragment
from pydom.html.parser import parse_fragment, parse_html
from pydom.html.serializer import serialize
from pydom.url import resolve_url


class JSDOM:
    """A Python jsdom environment.

    Construct with an HTML string plus options, or use one of the convenience
    factory methods.
    """

    # MIME type constants mirrored from jsdom.
    _HTML_MIME_TYPES = frozenset({"text/html", "application/xhtml+xml"})
    _XML_MIME_TYPES = frozenset(
        {
            "text/xml",
            "application/xml",
            "application/xhtml+xml",
        }
    )

    def __init__(
        self,
        html: str = "",
        *,
        url: str = "about:blank",
        referrer: str = "",
        content_type: str = "text/html",
        include_node_locations: bool = False,
        storage_quota: int = 5_000_000,
        pretend_to_be_visual: bool = False,
        before_parse: Optional[Callable[[Window], None]] = None,
    ) -> None:
        if content_type not in self._HTML_MIME_TYPES and content_type not in self._XML_MIME_TYPES:
            raise ValueError(f"Invalid content type: {content_type!r}")

        self._url = resolve_url(url)
        self._referrer = referrer
        self.content_type = content_type
        self.include_node_locations = include_node_locations
        self.storage_quota = storage_quota
        self.pretend_to_be_visual = pretend_to_be_visual

        self._window = Window(self)
        self._document = self._window.document

        if before_parse is not None:
            before_parse(self._window)

        if html:
            doc = parse_html(html, content_type=content_type, url=self._url)
            self._adopt_parsed_document(doc)
        else:
            # Empty input still yields a minimal HTML document.
            doc = parse_html("", content_type=content_type, url=self._url)
            self._adopt_parsed_document(doc)

        self._document.document_uri = self._url
        self._document.url = self._url
        self._document.default_view = self._window

    def _adopt_parsed_document(self, parsed: Document) -> None:
        """Move the parsed node tree into ``self._document``."""
        # Replace self._document's children with parsed document's children.
        for child in list(self._document.child_nodes):
            self._document.remove_child(child)
        for child in list(parsed.child_nodes):
            parsed.remove_child(child)
            self._document.append_child(child)

    # ---- properties -------------------------------------------------------
    @property
    def window(self) -> Window:
        return self._window

    @property
    def url(self) -> str:
        return self._url

    @property
    def referrer(self) -> str:
        return self._referrer

    # ---- serialization ----------------------------------------------------
    def serialize(self) -> str:
        """Return the HTML serialization of the document, including the doctype."""
        return serialize(self._document)

    def node_location(self, node) -> Optional[Dict[str, Any]]:
        """Return the parser-source location of ``node``.

        Phase 1: ``include_node_locations`` is accepted for compatibility but
        always returns ``None``; preserving parse locations is not implemented.
        """
        if not self.include_node_locations:
            return None
        return None

    # ---- reconfigure ------------------------------------------------------
    def reconfigure(self, *, url: Optional[str] = None, window_top: Optional[Any] = None) -> None:
        """Reconfigure the jsdom from the outside.

        ``window_top`` is accepted for compatibility but is a no-op in phase 1.
        ``url`` changes location.href and document URL resolution.
        """
        if url is not None:
            self._url = resolve_url(url)
            self._window._location._reconfigure(self._url)
            self._document.url = self._url
            self._document.document_uri = self._url

    # ---- convenience factories --------------------------------------------
    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        referrer: str = "",
        content_type: str = "text/html",
        include_node_locations: bool = False,
        pretend_to_be_visual: bool = False,
        before_parse: Optional[Callable[[Window], None]] = None,
    ) -> "JSDOM":
        """Fetch ``url`` and construct a :class:`JSDOM` from the response."""
        headers = {}
        if referrer:
            headers["Referer"] = referrer
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            body = response.text
            # Use the final URL and server content-type when available.
            final_url = str(response.url)
            ct = response.headers.get("content-type", content_type).split(";")[0].strip()
        return cls(
            body,
            url=final_url,
            referrer=referrer,
            content_type=ct,
            include_node_locations=include_node_locations,
            pretend_to_be_visual=pretend_to_be_visual,
            before_parse=before_parse,
        )

    @classmethod
    def from_url_sync(
        cls,
        url: str,
        *,
        referrer: str = "",
        content_type: str = "text/html",
        include_node_locations: bool = False,
        pretend_to_be_visual: bool = False,
        before_parse: Optional[Callable[[Window], None]] = None,
    ) -> "JSDOM":
        """Synchronous variant of :meth:`from_url`."""
        import asyncio

        return asyncio.run(
            cls.from_url(
                url,
                referrer=referrer,
                content_type=content_type,
                include_node_locations=include_node_locations,
                pretend_to_be_visual=pretend_to_be_visual,
                before_parse=before_parse,
            )
        )

    @classmethod
    def from_file(
        cls,
        filename: Union[str, os.PathLike],
        *,
        url: Optional[str] = None,
        referrer: str = "",
        content_type: Optional[str] = None,
        include_node_locations: bool = False,
        pretend_to_be_visual: bool = False,
        before_parse: Optional[Callable[[Window], None]] = None,
    ) -> "JSDOM":
        """Read ``filename`` and construct a :class:`JSDOM`."""
        path = Path(filename)
        text = path.read_text(encoding="utf-8")
        if content_type is None:
            suffix = path.suffix.lower()
            if suffix in {".xht", ".xhtml", ".xml"}:
                content_type = "application/xhtml+xml"
            else:
                content_type = "text/html"
        file_url = url if url is not None else path.resolve().as_uri()
        return cls(
            text,
            url=file_url,
            referrer=referrer,
            content_type=content_type,
            include_node_locations=include_node_locations,
            pretend_to_be_visual=pretend_to_be_visual,
            before_parse=before_parse,
        )

    @classmethod
    def fragment(
        cls,
        html: str,
        *,
        content_type: str = "text/html",
    ) -> DocumentFragment:
        """Parse ``html`` as a fragment without creating a full :class:`JSDOM`."""
        doc = Document(content_type=content_type)
        return parse_fragment(html, owner_document=doc)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"JSDOM(url={self._url!r})"
