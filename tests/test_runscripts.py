"""Tests for runScripts (JavaScript execution via STPyV8).

Skipped automatically when STPyV8 is not importable, so the suite stays green
on environments without the native wheel.
"""

import pytest

stpyv8 = pytest.importorskip("STPyV8")

from pydom import JSDOM
from pydom.browser.js.runtime import JSError


# ---- option validation ---------------------------------------------------

def test_invalid_run_scripts_value_raises():
    with pytest.raises(ValueError):
        JSDOM("<p>x</p>", run_scripts="nope")


def test_default_has_no_js_runtime():
    dom = JSDOM("<p>x</p>")
    assert dom.window._js_runtime is None
    with pytest.raises(RuntimeError):
        dom.window.eval("1+1")


# ---- outside-only: window.eval works, scripts not auto-run ---------------

def test_outside_only_eval_arithmetic():
    dom = JSDOM("", run_scripts="outside-only")
    assert dom.window.eval("1 + 1") == 2


def test_outside_only_create_element_from_js():
    dom = JSDOM("", run_scripts="outside-only")
    tag = dom.window.eval("document.createElement('p').tagName")
    assert tag == "P"


def test_outside_only_inner_html_setter_from_js_then_python_reads():
    dom = JSDOM("", run_scripts="outside-only")
    dom.window.eval("document.body.innerHTML = '<p>x</p>';")
    el = dom.window.document.body.first_element_child
    assert el is not None
    assert el.local_name == "p"
    assert el.text_content == "x"


def test_outside_only_append_child_then_query_selector_same_identity():
    dom = JSDOM("", run_scripts="outside-only")
    dom.window.eval(
        "var b = document.createElement('b'); document.body.appendChild(b);"
    )
    # Python observes the appended node.
    found = dom.window.document.body.query_selector("b")
    assert found is not None
    assert found.local_name == "b"
    # Identity: querying twice from JS yields the same object.
    same = dom.window.eval(
        "document.querySelector('b') === document.querySelector('b')"
    )
    assert same is True


def test_outside_only_does_not_run_script_tags():
    # An inline script in the parsed HTML must NOT execute under outside-only.
    html = "<!DOCTYPE html><body><script>window.__ran = true;</script></body>"
    dom = JSDOM(html, run_scripts="outside-only")
    ran = dom.window.eval("typeof window.__ran === 'undefined'")
    assert ran is True  # __ran was never set


# ---- dangerously: inline scripts run in document order ------------------

def test_dangerously_runs_inline_script_setting_global():
    html = "<!DOCTYPE html><body><script>window.__ran = true;</script></body>"
    dom = JSDOM(html, run_scripts="dangerously")
    ran = dom.window.eval("window.__ran === true")
    assert ran is True


def test_dangerously_appends_from_inline_script():
    html = (
        "<!DOCTYPE html><body>"
        "<script>document.body.appendChild(document.createElement('b'));</script>"
        "</body>"
    )
    dom = JSDOM(html, run_scripts="dangerously")
    assert dom.window.document.body.query_selector("b") is not None


def test_dangerously_scripts_run_in_document_order():
    html = (
        "<!DOCTYPE html><body>"
        "<script>window.__order = (window.__order||0) + 1;</script>"
        "<script>window.__order = (window.__order||0) + 10;</script>"
        "</body>"
    )
    dom = JSDOM(html, run_scripts="dangerously")
    order = dom.window.eval("window.__order")
    assert order == 11


def test_dangerously_skips_external_script_with_warning():
    html = (
        "<!DOCTYPE html><body>"
        "<script src='https://example.org/a.js'></script>"
        "</body>"
    )
    with pytest.warns(RuntimeWarning):
        dom = JSDOM(html, run_scripts="dangerously")
    # No global should have been set (script body is empty for external anyway).
    assert dom.window.document.body.query_selector("script") is not None


# ---- JS errors surface as JSError ---------------------------------------

def test_malformed_js_raises_jserro():
    dom = JSDOM("", run_scripts="outside-only")
    with pytest.raises(JSError):
        dom.window.eval("this is not valid javascript {")


def test_dangerously_propagates_inline_script_error():
    html = (
        "<!DOCTYPE html><body>"
        "<script>throw new Error('boom');</script>"
        "</body>"
    )
    with pytest.raises(JSError):
        JSDOM(html, run_scripts="dangerously")
