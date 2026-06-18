"""Tiny URL helpers used by :class:`JSDOM` and :class:`Location`.

A full WHATWG URL Standard implementation is out of scope for phase 1; we rely
on Python's standard library :mod:`urllib.parse` and treat malformed URLs as
about:blank, matching jsdom's basic behavior for the options we support.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse


_ABOUT_BLANK = ("about", "", "", "", "", "")


def resolve_url(input_url: str, base: str = "about:blank") -> str:
    """Canonicalize ``input_url`` against ``base``, falling back to about:blank."""
    if not input_url:
        return "about:blank"
    try:
        parsed = urlparse(input_url)
        if parsed.scheme:
            return urlunparse(parsed)
        return urljoin(base, input_url)
    except ValueError:
        return "about:blank"


def url_record(url: str) -> "URL":
    """Parse ``url`` and return a simple URL record object."""
    try:
        p = urlparse(url)
        return URL(
            href=urlunparse(p),
            protocol=p.scheme + ":",
            host=(p.hostname or ""),
            port=p.port,
            pathname=p.path or "/",
            search="" if p.query is None else "?" + p.query,
            hash="" if p.fragment is None else "#" + p.fragment,
            origin=urlunparse((p.scheme, p.netloc, "", "", "", "")),
        )
    except ValueError:
        return URL(href="about:blank", protocol="about:")


class URL:
    """Minimal URL record exposing the handful of properties DOM code needs."""

    def __init__(
        self,
        *,
        href: str,
        protocol: str = "",
        host: str = "",
        port: Optional[int] = None,
        pathname: str = "/",
        search: str = "",
        hash: str = "",
        origin: str = "",
    ) -> None:
        self.href = href
        self.protocol = protocol
        self.host = host
        self.port = port
        self.pathname = pathname
        self.search = search
        self.hash = hash
        self.origin = origin

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"URL({self.href!r})"
