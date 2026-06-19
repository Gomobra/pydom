"""Install DOM/browser globals into the V8 context.

Mirrors the "outside-only" surface of jsdom: the window, document, console,
navigator, and timer functions are exposed so that ``window.eval`` can drive
the DOM, but no ``<script>`` tags are auto-executed here (that's the
``dangerously`` path in :mod:`pydom.browser.js.runtime`).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

import STPyV8

from pydom.browser.js.bridge import JSProxy, _unwrap, _wrap

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.browser.window import Window


# A small JS shim that establishes the ``window``/``self``/``globalThis``
# aliases expected by web scripts, plus minimal ``Object.defineProperty``
# helpers. V8 provides built-ins (JSON, Promise, Math, Array, etc.) itself.
_BOOTSTRAP_JS = r"""
// `this` inside the context is the JSGlobal we constructed; expose its
// window/document under the conventional aliases. We treat the global object
// itself as `window`.
var window = this;
this.window = this;
this.self = this;
this.globalThis = this;
"""


class JSGlobal(STPyV8.JSClass):
    """The V8 global object for a pydom window.

    Holds a strong reference to the proxy cache so proxy identity is stable
    across all JS calls within this context.
    """

    def __init__(self, window: "Window") -> None:
        object.__setattr__(self, "_pydom_window", window)
        object.__setattr__(self, "_pydom_cache", {})  # id(target) -> JSProxy
        # Pre-wrap window so JS `window`/`document` share the cache.
        doc_proxy = _wrap(window.document, self._pydom_cache)
        object.__setattr__(self, "_pydom_doc_proxy", doc_proxy)
        window_proxy = _wrap(window, self._pydom_cache)
        object.__setattr__(self, "_pydom_window_proxy", window_proxy)

    @property
    def document(self) -> JSProxy:
        return object.__getattribute__(self, "_pydom_doc_proxy")

    @property
    def window(self) -> JSProxy:
        return object.__getattribute__(self, "_pydom_window_proxy")

    @property
    def self(self) -> JSProxy:
        return object.__getattribute__(self, "_pydom_window_proxy")

    @property
    def console(self) -> Any:
        return _wrap(object.__getattribute__(self, "_pydom_window").console,
                     object.__getattribute__(self, "_pydom_cache"))

    @property
    def navigator(self) -> Any:
        return _wrap(object.__getattribute__(self, "_pydom_window").navigator,
                     object.__getattribute__(self, "_pydom_cache"))

    # ---- timer functions (delegated to the Python stubs) ----
    def setTimeout(self, handler: Any, timeout: int = 0, *args: Any) -> int:
        window = object.__getattribute__(self, "_pydom_window")
        return window.setTimeout(_unwrap(handler), timeout, *[_unwrap(a) for a in args])

    def clearTimeout(self, handle: Any = None) -> None:
        object.__getattribute__(self, "_pydom_window").clearTimeout(_unwrap(handle))

    def setInterval(self, handler: Any, timeout: int = 0, *args: Any) -> int:
        window = object.__getattribute__(self, "_pydom_window")
        return window.setInterval(_unwrap(handler), timeout, *[_unwrap(a) for a in args])

    def clearInterval(self, handle: Any = None) -> None:
        object.__getattribute__(self, "_pydom_window").clearInterval(_unwrap(handle))


def install_globals(window: "Window") -> "JSGlobal":
    """Construct the JSGlobal root and return it for use as the context global."""
    return JSGlobal(window)


def bootstrap(context: STPyV8.JSContext) -> None:
    """Run the alias shim inside ``context``."""
    context.eval(_BOOTSTRAP_JS)
