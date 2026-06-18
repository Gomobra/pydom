"""Mirror jsdom's basic-usage tests against the pydom API."""

import pytest

from pydom import JSDOM, DOMException


def test_basic_query_selector_text_content():
    dom = JSDOM("<!DOCTYPE html><p>Hello world</p>")
    p = dom.window.document.query_selector("p")
    assert p is not None
    assert p.text_content == "Hello world"


def test_implied_html_head_body_tags_present():
    # jsdom parses implied <html>/<head>/<body> tags.
    dom = JSDOM("<!DOCTYPE html>hello")
    doc = dom.window.document
    assert doc.document_element is not None
    assert doc.document_element.tag_name == "HTML"
    assert doc.head is not None
    assert doc.body is not None
    assert doc.body.text_content == "hello"


def test_serialize_includes_doctype():
    dom = JSDOM("<!DOCTYPE html>hello")
    assert dom.serialize() == "<!DOCTYPE html><html><head></head><body>hello</body></html>"


def test_outer_html_matches_serialize_body():
    dom = JSDOM("<!DOCTYPE html><p>x</p>")
    doc = dom.window.document
    # outerHTML of the document element includes the closing </html> tag.
    assert doc.document_element.outer_html == "<html><head></head><body><p>x</p></body></html>"


def test_fragment_query_selector():
    frag = JSDOM.fragment("<p>Hello</p><p><strong>Hi!</strong></p>")
    assert frag.child_nodes.length == 2
    assert frag.query_selector("strong").text_content == "Hi!"


def test_fragment_single_element_outer_html():
    frag = JSDOM.fragment("<p>Hello</p>")
    assert frag.first_child.outer_html == "<p>Hello</p>"


def test_options_url_referrer_content_type():
    dom = JSDOM(
        "<p>hi</p>",
        url="https://example.org/",
        referrer="https://example.com/",
        content_type="text/html",
    )
    assert dom.window.location.href == "https://example.org/"
    assert dom.referrer == "https://example.com/"
    assert dom.content_type == "text/html"


def test_invalid_content_type_raises():
    with pytest.raises(ValueError):
        JSDOM("<p>x</p>", content_type="text/plain")


def test_reconfigure_changes_url():
    dom = JSDOM("<p>x</p>")
    assert dom.window.location.href == "about:blank"
    dom.reconfigure(url="https://example.com/")
    assert dom.window.location.href == "https://example.com/"
    assert dom.window.document.url == "https://example.com/"


def test_dom_exception_is_exported():
    assert DOMException is not None
    err = DOMException("boom", "NotFoundError")
    assert err.name == "NotFoundError"
