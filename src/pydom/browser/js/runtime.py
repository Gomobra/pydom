"""JSRuntime — owns the V8 engine/isolate/context for a single pydom window.

Lifecycle: one :class:`JSRuntime` per :class:`~pydom.api.JSDOM` constructed
with ``run_scripts``. It lazily imports STPyV8 (so the core package stays
importable without the optional dependency) and wraps JS errors in a Python
:class:`JSError` carrying ``.message`` and ``.stack``.

The runtime is created on the constructing thread; all JS calls run on that
same thread (V8 isolates are not thread-affine but our usage is single-threaded
for MVP). Re-entrancy — a Python method invoked from JS that calls back into
JS (e.g. ``dispatchEvent`` invoking a JS listener) — works natively; do NOT
add :class:`STPyV8.JSLocker` around callbacks (verified by the Task 0 spike).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.browser.window import Window


# Accepted values for the ``run_scripts`` option (mirrors jsdom).
RUN_SCRIPTS_OUTSIDE_ONLY = "outside-only"
RUN_SCRIPTS_DANGEROUSLY = "dangerously"
RUN_SCRIPTS_VALID = frozenset({RUN_SCRIPTS_OUTSIDE_ONLY, RUN_SCRIPTS_DANGEROUSLY})


class JSError(Exception):
    """A Python exception wrapping a V8 :class:`STPyV8.JSError`."""

    def __init__(self, message: str, stack: str = "") -> None:
        super().__init__(message)
        self.message: str = message
        self.stack: str = stack

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        if self.stack:
            return f"{self.message}\n{self.stack}"
        return self.message


class JSRuntime:
    """A V8 execution context bound to a pydom :class:`Window`."""

    def __init__(self, window: "Window") -> None:
        try:
            import STPyV8  # local import: optional dependency
        except ImportError as exc:  # pragma: no cover - depends on install state
            raise ImportError(
                "STPyV8 is required for runScripts. Install it with "
                "`pip install pydom[js]` (or `pip install stpyv8 stpyv8-icu`)."
            ) from exc

        self._STPyV8 = STPyV8
        self._window = window
        # STPyV8 creates and enters a single default isolate at import time
        # (STPyV8.v8_default_isolate). We reuse it rather than spawning a new
        # isolate per runtime — V8 asserts/fatal-crashes when multiple isolates
        # are entered and left across many JSDOM instances in one process.
        self._engine = STPyV8.JSEngine()
        self._isolate = STPyV8.v8_default_isolate

        from pydom.browser.js.globals import bootstrap, install_globals

        self._global = install_globals(window)
        # JSContext acquires the isolate's locker on construction; we keep it
        # entered for the lifetime of this runtime so that re-entrant calls
        # (Python invoked from JS that calls back into JS) work natively.
        self._context = STPyV8.JSContext(self._global)
        self._context.enter()
        bootstrap(self._context)
        # Expose eval/Function on the window so window.eval(...) works.
        # V8's global already has eval/Function; mirror them onto our window
        # proxy by giving Window an `eval` attribute that delegates here.
        window._js_runtime = self

    # ---- evaluation ------------------------------------------------------
    def eval(self, source: str, filename: str = "<eval>") -> Any:
        """Evaluate ``source`` as JavaScript and return the result (unwrapped)."""
        from pydom.browser.js.bridge import _unwrap

        try:
            result = self._context.eval(str(source))
        except self._STPyV8.JSError as exc:
            raise JSError(str(exc), getattr(exc, "stackTrace", "")) from None
        except SyntaxError as exc:
            # STPyV8 raises Python's builtin SyntaxError for parse failures
            # (rather than JSError). Normalize to JSError for callers.
            raise JSError(str(exc)) from None
        # Unwrap any JSProxy back to its Python target so Python callers see
        # the real DOM node; primitives pass through unchanged.
        return _unwrap(result)

    def eval_wrapped(self, source: str, filename: str = "<eval>") -> Any:
        """Like :meth:`eval` but returns a JSProxy for object results.

        Used internally so callers that need to pass the result back into JS
        keep identity stable.
        """
        from pydom.browser.js.bridge import _wrap

        try:
            result = self._context.eval(str(source))
        except self._STPyV8.JSError as exc:
            raise JSError(str(exc), getattr(exc, "stackTrace", "")) from None
        return _wrap(result, self._global._pydom_cache)

    # ---- inline script execution (dangerously) ---------------------------
    def run_inline_scripts(self, document: Any) -> None:
        """Find every inline ``<script>`` in ``document`` and run it in order.

        Implements the ``dangerously`` mode: scripts without a ``src`` attribute
        are evaluated synchronously in document order. External scripts are
        skipped with a warning (the ``resources`` option is not implemented).
        """
        import warnings

        from pydom.dom.node import ELEMENT_NODE

        for node in list(document.iter_descendants()):
            if node.nodeType != ELEMENT_NODE:  # type: ignore[union-attr]
                continue
            el = node  # type: ignore[assignment]
            if el.local_name != "script":  # type: ignore[attr-defined]
                continue
            src = el.get_attribute("src")  # type: ignore[attr-defined]
            if src:
                warnings.warn(
                    "pydom: external <script src> loading is not implemented; "
                    "the `resources` option is required (and not yet supported).",
                    RuntimeWarning,
                    stacklevel=2,
                )
                continue
            # Respect classic type/language filters: only classic JS runs.
            script_type = el.get_attribute("type")  # type: ignore[attr-defined]
            if script_type and script_type.strip().lower() not in (
                "",
                "text/javascript",
                "application/javascript",
                "module",
            ):
                continue
            source = el.text_content or ""  # type: ignore[attr-defined]
            if not source.strip():
                continue
            self.eval(source, filename="<inline-script>")

    # ---- teardown --------------------------------------------------------
    def close(self) -> None:
        """Release V8 resources. Idempotent.

        We only leave (and drop) our own context — the isolate is the shared
        STPyV8 default isolate and is not entered/left here.
        """
        ctx = getattr(self, "_context", None)
        if ctx is not None:
            try:
                ctx.leave()
            except Exception:
                pass
            self._context = None
        # Drop strong refs so proxy cache entries can be collected.
        self._global = None  # type: ignore[assignment]
        self._engine = None  # type: ignore[assignment]
