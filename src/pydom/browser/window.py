"""The :class:`Window` interface — a minimal browser window for the DOM.

jsdom phase 1 supports only the non-layout, non-scripting subset of window
functionality: document, location, navigator, history stubs, timer stubs, and a
console. Layout and navigation are out of scope.

Reference: https://html.spec.whatwg.org/#window
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydom.browser.location import Location
from pydom.dom.document import Document
from pydom.dom.event import EventTarget
from pydom.url import resolve_url

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.api import JSDOM


class Navigator:
    """Minimal navigator stub."""

    user_agent: str = "Mozilla/5.0 (compatible; pydom/0.1.0)"
    language: str = "en-US"
    languages: list[str] = ["en-US", "en"]
    on_line: bool = True
    cookie_enabled: bool = True

    @property
    def product(self) -> str:
        return "Gecko"

    @property
    def vendor(self) -> str:
        return ""

    @property
    def platform(self) -> str:
        import sys

        return sys.platform


class Console:
    """A console that forwards to the host Python ``print``."""

    def log(self, *args: Any) -> None:
        print(*args)

    def error(self, *args: Any) -> None:
        print(*args, file=__import__("sys").stderr)

    def warn(self, *args: Any) -> None:
        print(*args, file=__import__("sys").stderr)

    def info(self, *args: Any) -> None:
        print(*args)

    def debug(self, *args: Any) -> None:
        print(*args)


class Window(EventTarget):
    """The global object associated with a :class:`~pydom.api.JSDOM` instance."""

    def __init__(self, jsdom: "JSDOM") -> None:
        self._jsdom = jsdom
        self._document = Document(
            content_type=jsdom.content_type,
            url=jsdom.url,
            default_view=self,
        )
        self._document.default_view = self
        self._location = Location(self, jsdom.url)
        self._navigator = Navigator()
        self._console = Console()
        self._closed = False
        self.name = ""
        self.status = ""
        self._inner_width = 1024
        self._inner_height = 768
        # Set by JSRuntime when run_scripts is enabled; None otherwise.
        self._js_runtime = None

    # ---- core accessors ---------------------------------------------------
    @property
    def document(self) -> Document:
        return self._document

    @property
    def location(self) -> Location:
        return self._location

    @property
    def navigator(self) -> Navigator:
        return self._navigator

    @property
    def console(self) -> Console:
        return self._console

    @property
    def window(self) -> "Window":
        return self

    @property
    def self(self) -> "Window":
        return self

    @property
    def top(self) -> "Window":
        return self

    @property
    def parent(self) -> "Window":
        return self

    @property
    def opener(self) -> None:
        return None

    @property
    def closed(self) -> bool:
        return self._closed

    # ---- document visibility (headless by default) -------------------------
    @property
    def hidden(self) -> bool:
        return not self._jsdom.pretend_to_be_visual

    @property
    def inner_width(self) -> int:
        return self._inner_width

    @property
    def inner_height(self) -> int:
        return self._inner_height

    # ---- timers (stubs) ---------------------------------------------------
    def setTimeout(self, handler: Any, timeout: int = 0, *args: Any) -> int:
        # No scheduling without a running event loop; just return a dummy id.
        return 0

    def clearTimeout(self, handle: Optional[int] = None) -> None:
        return None

    def setInterval(self, handler: Any, timeout: int = 0, *args: Any) -> int:
        return 0

    def clearInterval(self, handle: Optional[int] = None) -> None:
        return None

    def requestAnimationFrame(self, callback: Any) -> int:
        if not self._jsdom.pretend_to_be_visual:
            return 0
        return 0

    def cancelAnimationFrame(self, handle: int) -> None:
        return None

    # ---- lifecycle --------------------------------------------------------
    def close(self) -> None:
        """Shut down the window (clear timers, listeners, etc.)."""
        self._closed = True
        if self._js_runtime is not None:
            self._js_runtime.close()
            self._js_runtime = None

    # ---- JavaScript execution (only when run_scripts is set) -------------
    def eval(self, source: str):
        """Evaluate ``source`` as JavaScript in this window's V8 context.

        Requires the JSDOM to have been constructed with ``run_scripts``
        (``outside-only`` or ``dangerously``). Raises ``RuntimeError`` if no
        JS runtime is attached.
        """
        if self._js_runtime is None:
            raise RuntimeError(
                "window.eval requires run_scripts. Construct the JSDOM with "
                "run_scripts='outside-only' or 'dangerously'."
            )
        return self._js_runtime.eval(source)

    def _not_implemented(self, method: str) -> None:
        # Mirror jsdom's behavior: emit an error to the virtual console and
        # otherwise no-op. We use Python's warnings here for simplicity.
        import warnings

        warnings.warn(f"pydom: {method} is not implemented", RuntimeWarning, stacklevel=3)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Window(url={self._location.href!r})"
