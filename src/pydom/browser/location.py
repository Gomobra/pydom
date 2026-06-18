"""The :class:`Location` interface.

A minimal implementation of ``window.location`` for phase 1: read-only access to
href, origin, protocol, host, pathname, search, and hash. Navigation (assign,
replace, reload) is not implemented, per jsdom's phase-1 non-goal.

Reference: https://html.spec.whatwg.org/#location
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydom.url import url_record

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.browser.window import Window


class Location:
    """Read-only URL record associated with a window."""

    def __init__(self, window: "Window", url: str) -> None:
        self._window = window
        self._href = url
        self._record = url_record(url)

    def _reconfigure(self, url: str) -> None:
        self._href = url
        self._record = url_record(url)

    # ---- properties -------------------------------------------------------
    @property
    def href(self) -> str:
        return self._record.href

    @property
    def origin(self) -> str:
        return self._record.origin

    @property
    def protocol(self) -> str:
        return self._record.protocol

    @property
    def host(self) -> str:
        if self._record.port:
            return f"{self._record.host}:{self._record.port}"
        return self._record.host

    @property
    def hostname(self) -> str:
        return self._record.host

    @property
    def port(self) -> str:
        return "" if self._record.port is None else str(self._record.port)

    @property
    def pathname(self) -> str:
        return self._record.pathname

    @property
    def search(self) -> str:
        return self._record.search

    @property
    def hash(self) -> str:
        return self._record.hash

    # ---- navigation (intentionally not implemented) ------------------------
    def assign(self, url: str) -> None:
        self._window._not_implemented("Location.assign")

    def replace(self, url: str) -> None:
        self._window._not_implemented("Location.replace")

    def reload(self) -> None:
        self._window._not_implemented("Location.reload")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Location({self.href!r})"
