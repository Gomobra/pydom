"""Tests for the DOM Events subsystem (EventTarget, Event, CustomEvent).

Mirrors the WHATWG DOM event dispatch model: capture → target → bubble,
stopPropagation/stopImmediatePropagation, preventDefault default action,
listener removal, and that both Node and Window act as event targets.
"""

import pytest

from pydom import JSDOM
from pydom.dom.event import Event, CustomEvent


# ---- EventTarget: registration & dispatch --------------------------------

def test_add_and_dispatch_simple_listener():
    dom = JSDOM("<!DOCTYPE html><body></body>")
    body = dom.window.document.body
    received = []
    body.add_event_listener("click", lambda e: received.append(e.type))
    fired = body.dispatch_event(Event("click"))
    assert fired is True
    assert received == ["click"]


def test_multiple_listeners_dispatched_in_registration_order():
    dom = JSDOM("<!DOCTYPE html><body></body>")
    body = dom.window.document.body
    order = []
    body.add_event_listener("click", lambda e: order.append("a"))
    body.add_event_listener("click", lambda e: order.append("b"))
    body.add_event_listener("click", lambda e: order.append("c"))
    body.dispatch_event(Event("click"))
    assert order == ["a", "b", "c"]


def test_remove_event_listener():
    dom = JSDOM("<!DOCTYPE html><body></body>")
    body = dom.window.document.body

    calls = []

    def listener(e):
        calls.append(1)

    body.add_event_listener("click", listener)
    body.remove_event_listener("click", listener)
    body.dispatch_event(Event("click"))
    assert calls == []


def test_remove_only_removes_matching_type():
    dom = JSDOM("<!DOCTYPE html><body></body>")
    body = dom.window.document.body
    hits = []
    body.add_event_listener("click", lambda e: hits.append("click"))
    body.add_event_listener("focus", lambda e: hits.append("focus"))
    # Removing the click listener must not affect the focus listener.
    body.remove_event_listener("click", lambda e: hits.append("click"))
    body.dispatch_event(Event("focus"))
    assert hits == ["focus"]


# ---- Event object state --------------------------------------------------

def test_event_default_flags():
    ev = Event("click")
    assert ev.type == "click"
    assert ev.bubbles is False
    assert ev.cancelable is False
    assert ev.default_prevented is False
    assert ev.target is None


def test_event_options_bubbles_cancelable():
    ev = Event("submit", {"bubbles": True, "cancelable": True})
    assert ev.bubbles is True
    assert ev.cancelable is True


def test_prevent_default_only_when_cancelable():
    cancelable = Event("x", {"cancelable": True})
    cancelable.prevent_default()
    assert cancelable.default_prevented is True

    not_cancelable = Event("x")  # cancelable defaults to False
    not_cancelable.prevent_default()
    assert not_cancelable.default_prevented is False


def test_dispatch_returns_false_when_default_prevented():
    dom = JSDOM("<!DOCTYPE html><body></body>")
    body = dom.window.document.body

    def prevent(e):
        e.prevent_default()

    body.add_event_listener("click", prevent)
    result = body.dispatch_event(Event("click", {"cancelable": True}))
    assert result is False  # default action was "cancelled"


# ---- Propagation ---------------------------------------------------------

def test_bubbling_order_child_to_root():
    dom = JSDOM(
        """<!DOCTYPE html><body><div id="outer"><div id="inner"></div></div></body>"""
    )
    doc = dom.window.document
    inner = doc.get_element_by_id("inner")
    outer = doc.get_element_by_id("outer")
    body = doc.body
    order = []
    body.add_event_listener("click", lambda e: order.append("body"))
    outer.add_event_listener("click", lambda e: order.append("outer"))
    inner.add_event_listener("click", lambda e: order.append("inner"))
    inner.dispatch_event(Event("click", {"bubbles": True}))
    assert order == ["inner", "outer", "body"]


def test_non_bubbling_event_stops_at_target():
    dom = JSDOM(
        """<!DOCTYPE html><body><div id="outer"><div id="inner"></div></div></body>"""
    )
    doc = dom.window.document
    inner = doc.get_element_by_id("inner")
    outer = doc.get_element_by_id("outer")
    order = []
    outer.add_event_listener("click", lambda e: order.append("outer"))
    inner.add_event_listener("click", lambda e: order.append("inner"))
    # bubbles=False (default): only the target listener fires.
    inner.dispatch_event(Event("click"))
    assert order == ["inner"]


def test_capture_phase_runs_outer_to_inner():
    dom = JSDOM(
        """<!DOCTYPE html><body><div id="outer"><div id="inner"></div></div></body>"""
    )
    doc = dom.window.document
    inner = doc.get_element_by_id("inner")
    outer = doc.get_element_by_id("outer")
    order = []
    outer.add_event_listener("click", lambda e: order.append("outer-capture"), {"capture": True})
    inner.add_event_listener("click", lambda e: order.append("inner-target"))
    outer.add_event_listener("click", lambda e: order.append("outer-bubble"))
    inner.dispatch_event(Event("click", {"bubbles": True}))
    assert order == ["outer-capture", "inner-target", "outer-bubble"]


def test_stop_propagation_blocks_further_targets():
    dom = JSDOM(
        """<!DOCTYPE html><body><div id="outer"><div id="inner"></div></div></body>"""
    )
    doc = dom.window.document
    inner = doc.get_element_by_id("inner")
    outer = doc.get_element_by_id("outer")

    def stop(e):
        e.stop_propagation()

    inner.add_event_listener("click", stop)
    inner.add_event_listener("click", lambda e: None)  # still fires (same target)
    outer.add_event_listener("click", lambda e: pytest.fail("should not bubble"))
    inner.dispatch_event(Event("click", {"bubbles": True}))


def test_stop_immediate_blocks_same_target_listeners():
    dom = JSDOM("<!DOCTYPE html><body></body>")
    body = dom.window.document.body

    def stop_now(e):
        e.stop_immediate_propagation()

    body.add_event_listener("click", stop_now)
    body.add_event_listener("click", lambda e: pytest.fail("must not run"))
    body.dispatch_event(Event("click"))


# ---- currentTarget reflects the visiting node ----------------------------

def test_current_target_reflects_visiting_node():
    dom = JSDOM("""<!DOCTYPE html><body><div id="d"></div></body>""")
    doc = dom.window.document
    d = doc.get_element_by_id("d")
    body = doc.body
    seen_targets = []

    def listener(e):
        seen_targets.append((e.target is d, e.current_target is body))

    body.add_event_listener("click", listener)
    d.dispatch_event(Event("click", {"bubbles": True}))
    assert seen_targets == [(True, True)]


# ---- CustomEvent ---------------------------------------------------------

def test_custom_event_detail():
    ev = CustomEvent("my-event", {"detail": {"a": 1}})
    assert ev.detail == {"a": 1}
    assert ev.type == "my-event"


def test_custom_event_dispatch_with_detail():
    dom = JSDOM("<!DOCTYPE html><body></body>")
    body = dom.window.document.body
    captured = []
    body.add_event_listener("ping", lambda e: captured.append(e.detail))
    body.dispatch_event(CustomEvent("ping", {"detail": 42}))
    assert captured == [42]


# ---- Window is also an EventTarget --------------------------------------

def test_window_is_event_target():
    dom = JSDOM("<!DOCTYPE html><body></body>")
    w = dom.window
    seen = []
    w.add_event_listener("load", lambda e: seen.append("loaded"))
    w.dispatch_event(Event("load"))
    assert seen == ["loaded"]


def test_window_remove_listener():
    dom = JSDOM("<!DOCTYPE html><body></body>")
    w = dom.window
    calls = []

    def cb(e):
        calls.append(1)

    w.add_event_listener("resize", cb)
    w.remove_event_listener("resize", cb)
    w.dispatch_event(Event("resize"))
    assert calls == []


# ---- camelCase parity ----------------------------------------------------

def test_add_event_listener_camelcase_alias():
    """jsdom parity: camelCase addEventListener/dispatchEvent should also work."""
    dom = JSDOM("<!DOCTYPE html><body></body>")
    body = dom.window.document.body
    hits = []
    body.addEventListener("click", lambda e: hits.append("x"))
    body.dispatchEvent(Event("click"))
    assert hits == ["x"]
