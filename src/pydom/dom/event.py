"""DOM Events — :class:`EventTarget`, :class:`Event`, :class:`CustomEvent`.

Implements the WHATWG DOM event dispatch model: capture → target → bubble
phases, ``stopPropagation`` / ``stopImmediatePropagation`` / ``preventDefault``,
and listener registration/removal. ``EventTarget`` is a mixin: ``Node`` and
:class:`pydom.browser.window.Window` both inherit from it so that every part
of the tree can receive events.

Reference: https://dom.spec.whatwg.org/#events
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

if TYPE_CHECKING:  # avoid runtime import cycle
    from pydom.dom.node import Node


# A listener can be a plain callable or an object with a ``handleEvent``
# method (the latter is how JS objects are passed in from V8).
EventListener = Callable[["Event"], None]

Capture = {"capture"}
Bubble = set()


def _is_capture(options: Any) -> bool:
    if options is None:
        return False
    if options is True:  # legacy boolean form
        return True
    return bool(getattr(options, "capture", False)) or (
        isinstance(options, dict) and bool(options.get("capture", False))
    )


class Event:
    """A DOM event dispatched through the tree.

    ``type`` identifies the event (e.g. ``"click"``). ``options`` is a dict
    accepting ``bubbles`` and ``cancelable`` (both default to False).
    """

    NONE = 0
    CAPTURING_PHASE = 1
    AT_TARGET = 2
    BUBBLING_PHASE = 3

    def __init__(self, type: str, options: Optional[Dict[str, Any]] = None) -> None:
        if not isinstance(type, str):
            raise TypeError("Event type must be a string.")
        self.type: str = type
        opts = options or {}
        self.bubbles: bool = bool(opts.get("bubbles", False))
        self.cancelable: bool = bool(opts.get("cancelable", False))
        self.composed: bool = bool(opts.get("composed", False))

        # Dispatch state — populated by ``dispatch_event``.
        self.target: Optional[EventTarget] = None
        self.current_target: Optional[EventTarget] = None
        self.event_phase: int = Event.NONE
        self.time_stamp: float = time.time() * 1000.0
        self.default_prevented: bool = False
        self._stop_propagation: bool = False
        self._stop_immediate: bool = False
        self._dispatch: bool = False  # True while dispatching

    # ---- control methods -------------------------------------------------
    def prevent_default(self) -> None:
        # Only honored when the event is cancelable, per spec.
        if self.cancelable:
            self.default_prevented = True

    def stop_propagation(self) -> None:
        self._stop_propagation = True

    def stop_immediate_propagation(self) -> None:
        self._stop_propagation = True
        self._stop_immediate = True

    def _begin_dispatch(self) -> None:
        self._stop_propagation = False
        self._stop_immediate = False
        self._dispatch = True

    def _end_dispatch(self) -> None:
        self.current_target = None
        self.event_phase = Event.NONE
        self._dispatch = False


class CustomEvent(Event):
    """An :class:`Event` carrying an arbitrary ``detail`` payload."""

    def __init__(
        self,
        type: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(type, options)
        self.detail: Any = (options or {}).get("detail", None)


def _invoke(listener: Any, event: Event) -> None:
    """Call a listener, supporting both plain callables and handleEvent objects."""
    handle = getattr(listener, "handleEvent", None)
    if callable(handle):
        handle(event)
    elif callable(listener):
        listener(event)
    # else: silently ignore — mirrors browsers' tolerance of non-callable
    # listeners (they were registered but never fire).


class _Listener:
    """An internal (listener, capture-flag) pair."""

    __slots__ = ("callback", "capture")

    def __init__(self, callback: Any, capture: bool) -> None:
        self.callback = callback
        self.capture = capture


class EventTarget:
    """The DOM ``EventTarget`` mixin.

    Mix into any class that should receive events (``Node``, ``Window``).
    Listener storage is initialized lazily via :meth:`_listeners_map` so that
    subclasses' ``__init__`` need not call ``super().__init__()`` here — this
    keeps the integration with :class:`pydom.dom.node.Node` zero-touch.
    """

    # ``parent_node`` exists on Node; Window returns None (no DOM parent).
    # Subclasses may override this to participate in bubbling.

    # camelCase aliases (jsdom parity). Resolved lazily so subclasses that
    # define their own ``__getattr__`` (e.g. Node) are unaffected — those only
    # fall through to here when their own lookup misses.
    _CAMEL_ALIASES = {
        "addEventListener": "add_event_listener",
        "removeEventListener": "remove_event_listener",
        "dispatchEvent": "dispatch_event",
    }

    def __getattr__(self, name: str):
        snake = type(self)._CAMEL_ALIASES.get(name)
        if snake is not None:
            return getattr(self, snake)
        raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

    def _listeners_map(self) -> Dict[str, List[_Listener]]:
        store = self.__dict__.get("_event_listeners")
        if store is None:
            store = {}
            self.__dict__["_event_listeners"] = store
        return store

    # ---- registration ----------------------------------------------------
    def add_event_listener(
        self,
        type: str,
        listener: Any,
        options: Any = None,
    ) -> None:
        if listener is None:
            return
        capture = _is_capture(options)
        store = self._listeners_map()
        bucket = store.setdefault(type, [])
        # Per spec, adding the exact same (listener, capture) twice is a no-op.
        for existing in bucket:
            if existing.callback is listener and existing.capture == capture:
                return
        bucket.append(_Listener(listener, capture))

    def remove_event_listener(
        self,
        type: str,
        listener: Any,
        options: Any = None,
    ) -> None:
        capture = _is_capture(options)
        store = self._listeners_map()
        bucket = store.get(type)
        if not bucket:
            return
        for i, existing in enumerate(bucket):
            if existing.callback is listener and existing.capture == capture:
                del bucket[i]
                if not bucket:
                    del store[type]
                return

    # ---- dispatch --------------------------------------------------------
    def dispatch_event(self, event: Event) -> bool:
        """Dispatch ``event`` at this target. Returns False if default was prevented."""
        if event._dispatch:
            # Re-entrant dispatch of the same event instance is disallowed.
            raise Exception("InvalidStateError: event is already being dispatched.")
        target = self
        event.target = target
        event._begin_dispatch()

        path = _build_event_path(target)
        try:
            # 1) Capture phase: root -> target's parent (excluding target).
            event.event_phase = Event.CAPTURING_PHASE
            for node in reversed(path):
                if event._stop_propagation:
                    break
                _dispatch_at(node, event, capture_phase=True)
                if event._stop_immediate:
                    break

            # 2) Target phase.
            if not event._stop_propagation:
                event.event_phase = Event.AT_TARGET
                _dispatch_at(target, event, capture_phase=False)

            # 3) Bubble phase: target's parent -> root.
            if event.bubbles and not event._stop_propagation:
                event.event_phase = Event.BUBBLING_PHASE
                for node in path:
                    if event._stop_propagation:
                        break
                    _dispatch_at(node, event, capture_phase=False)
                    if event._stop_immediate:
                        break
        finally:
            event._end_dispatch()

        return not event.default_prevented


def _build_event_path(target: EventTarget) -> List[EventTarget]:
    """Return ancestors of ``target`` from target's parent up to the root.

    The list is ordered parent-first (index 0 = nearest parent). Used by both
    the capture (reversed) and bubble phases.
    """
    path: List[EventTarget] = []
    cur = getattr(target, "parent_node", None)
    while cur is not None:
        path.append(cur)
        # Walk up via the DOM parent. (Window has no DOM parent → stops.)
        cur = getattr(cur, "parent_node", None)
    return path


def _dispatch_at(target: EventTarget, event: Event, *, capture_phase: bool) -> None:
    """Invoke matching listeners on ``target`` for the current phase."""
    store = target.__dict__.get("_event_listeners")
    if not store:
        return
    bucket = store.get(event.type)
    if not bucket:
        return
    event.current_target = target
    # Iterate a snapshot so listeners may remove themselves / siblings safely.
    for entry in list(bucket):
        if entry.capture != capture_phase:
            continue
        _invoke(entry.callback, event)
        if event._stop_immediate:
            break
    event.current_target = None
