"""Python ↔ JavaScript bridge.

A single cached :class:`JSProxy` class wraps any Python object (DOM node,
window, document, …) so that JavaScript sees it as a JS object whose attribute
access, method calls, and property assignment transparently delegate to the
underlying Python object.

Design notes (verified by Task 0 spikes):
    * Identity stability — the same Python object always yields the same proxy
      via a per-target cache, so ``document.body === document.body`` holds and
      nodes round-tripped through ``appendChild`` stay referentially equal.
    * ``@property`` getters and setters on Python objects bridge transparently:
      JS reading ``el.tagName`` calls the Python getter; JS assigning
      ``el.innerHTML = "…"`` calls the Python setter.
    * Re-entrancy works natively — a Python method invoked from JS may call a
      JS function (e.g. dispatching an event to a JS listener) with no extra
      locking. Do NOT add :class:`STPyV8.JSLocker` (it raises "Lock should be
      acquired before entering the context" under re-entry).
    * Known limitation: bracket-index access (``arr[i]``) is not bridged — JS
      callers must use ``.item(i)`` / ``.length`` on collections. Documented in
      the runScripts README section.
"""

from __future__ import annotations

import re
from typing import Any, Dict

import STPyV8


# Per-target proxy cache. A WeakValueDictionary keyed by id() would let proxies
# die with their targets, but id() reuse makes that unsafe; instead we keep a
# plain dict cleared when the runtime is torn down. The cache lives on the
# runtime, so it is per-context — see JSRuntime._proxy_cache.
_PROXY_SENTINEL = object()

_CAMEL_TO_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


def _resolve_name(target: Any, name: str) -> Any:
    """Resolve a JS camelCase ``name`` against the Python ``target``.

    Tries, in order: the exact name, the target's ``_CAMEL_ALIASES`` map
    (Node/EventTarget parity), and a generic camelCase→snake_case fallback.
    Raises :class:`AttributeError` if none match.
    """
    # 1) Exact attribute (covers real camelCase props like tagName via @property,
    #    and snake_case callers passing through).
    try:
        return getattr(target, name)
    except AttributeError:
        pass

    # 2) Explicit alias map (Node/EventTarget keep one for parity).
    aliases = getattr(type(target), "_CAMEL_ALIASES", None)
    if aliases and name in aliases:
        return getattr(target, aliases[name])

    # 3) Generic camelCase → snake_case (createElement → create_element,
    #    getElementById → get_element_by_id, firstElementChild already covered
    #    by the alias map but this is the general backstop).
    snake = _CAMEL_TO_SNAKE.sub("_", name).lower()
    if snake != name:
        try:
            return getattr(target, snake)
        except AttributeError:
            pass

    raise AttributeError(
        f"{type(target).__name__!r} has no attribute {name!r}"
    )


def _has_real_descriptor(target: Any, name: str) -> bool:
    """True if ``name`` is a real attribute/property on ``type(target)``
    (found via the normal MRO, NOT via ``__getattr__``).

    This distinguishes genuine properties (which have setters) from names that
    only resolve through a camelCase ``__getattr__`` alias map (which have no
    setter under the camelCase spelling).
    """
    for cls in type(target).__mro__:
        if name in cls.__dict__:
            return True
    return False


def _resolve_setattr_name(target: Any, name: str) -> str:
    """Resolve a JS camelCase ``name`` to the Python attribute name to SET.

    Prefers real descriptors on the type; falls back to the camelCase alias
    map and generic snake_case conversion. Never relies on ``__getattr__``
    (which would make every camelCase name look "settable" and store a stray
    instance attribute, shadowing the real snake_case property setter).
    """
    if _has_real_descriptor(target, name):
        return name
    aliases = getattr(type(target), "_CAMEL_ALIASES", None)
    if aliases and name in aliases:
        resolved = aliases[name]
        if _has_real_descriptor(target, resolved):
            return resolved
    snake = _CAMEL_TO_SNAKE.sub("_", name).lower()
    if snake != name and _has_real_descriptor(target, snake):
        return snake
    return name  # no real descriptor; let setattr store/raise naturally


def _unwrap(value: Any) -> Any:
    """If ``value`` is a JSProxy, return the wrapped Python object; else ``value``."""
    target = getattr(value, "__pydom_target__", _PROXY_SENTINEL)
    return target if target is not _PROXY_SENTINEL else value


def _wrap(value: Any, cache: Dict[int, "JSProxy"]) -> Any:
    """Wrap a Python value for JS consumption, using ``cache`` for identity."""
    # Pass through primitives, None, and already-wrapped/proxied values.
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, JSProxy):
        return value
    # Wrap anything else that "feels like" an object. Functions/callables that
    # live on the Python side (listeners, callbacks) are wrapped too so JS can
    # invoke them — but plain functions should pass through so JS can call them.
    # We wrap any non-callable object; callables are handled by the JSContext
    # global installer for named callbacks.
    if callable(value):
        return value
    cached = cache.get(id(value))
    if cached is not None and getattr(cached, "__pydom_target__", None) is value:
        return cached
    proxy = JSProxy(value, cache)
    cache[id(value)] = proxy
    return proxy


class JSProxy(STPyV8.JSClass):
    """A transparent proxy that exposes a Python object to JavaScript.

    Attribute reads on the proxy return:
      * wrapped sub-objects (as JSProxy, identity-cached) for non-callable,
        non-primitive attributes;
      * a delegating shim for bound methods, which unwraps JS-proxy arguments
        back to their Python targets and wraps the return value;
      * primitives/None unchanged.

    Attribute writes (``el.innerHTML = "…"``) delegate to ``setattr`` on the
    target, so Python ``@property`` setters run as expected.
    """

    def __init__(self, target: Any, cache: Dict[int, "JSProxy"]) -> None:
        # JSClass routes __setattr__ through __properties__; bypass it.
        object.__setattr__(self, "__pydom_target__", target)
        object.__setattr__(self, "__pydom_cache__", cache)

    # ---- reads ----
    def __getattr__(self, name: str) -> Any:
        target = object.__getattribute__(self, "__pydom_target__")
        cache = object.__getattribute__(self, "__pydom_cache__")
        attr = _resolve_name(target, name)
        if callable(attr):
            # Return a native closure (V8 invokes it like any callable).
            # An earlier adapter-class approach failed because V8 does not
            # treat arbitrary Python objects with __call__ as JS functions;
            # closures / bound methods work, so we use a closure here that
            # unwraps proxy arguments and wraps object results for identity.
            def shim(*args: Any) -> Any:
                unwrapped = tuple(_unwrap(a) for a in args)
                result = attr(*unwrapped)
                return _wrap(result, cache)

            return shim
        return _wrap(attr, cache)

    def __setattr__(self, name: str, value: Any) -> None:
        target = object.__getattribute__(self, "__pydom_target__")
        unwrapped = _unwrap(value)
        # Resolve the JS camelCase name to the Python attribute that actually
        # has a setter. We CANNOT just try setattr(target, name, ...) first:
        # Python objects without a __setattr__ will happily store any name as
        # a plain instance attribute, shadowing the real (snake_case) property
        # setter we want to invoke. So resolve explicitly via the type's MRO.
        resolved = _resolve_setattr_name(target, name)
        setattr(target, resolved, unwrapped)
