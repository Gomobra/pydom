"""Tests for the CSS selector engine (soupsieve adapter)."""

from pydom.html.parser import parse_html


def test_id_selector(rich_dom):
    doc = rich_dom.window.document
    el = doc.query_selector("#p1")
    assert el is not None
    assert el.text_content.startswith("Hello")


def test_class_selector_count(rich_dom):
    doc = rich_dom.window.document
    matches = doc.query_selector_all(".a")
    assert matches.length == 2


def test_descendant_combinator(rich_dom):
    body = rich_dom.window.document.body
    b = body.query_selector("p b")
    assert b is not None
    assert b.text_content == "world"


def test_child_combinator(rich_dom):
    body = rich_dom.window.document.body
    span = body.query_selector("div > p")
    assert span is not None
    assert span.get_attribute("id") == "p1"


def test_attribute_selector(rich_dom):
    doc = rich_dom.window.document
    items = doc.query_selector_all("li[data-x]")
    assert items.length == 3
    second = doc.query_selector('li[data-x="2"]')
    assert second is not None
    assert second.text_content == "two"


def test_matches_method(rich_dom):
    p1 = rich_dom.window.document.query_selector("#p1")
    assert p1.matches("p.a") is True
    assert p1.matches("p#p2") is False


def test_closest(rich_dom):
    b = rich_dom.window.document.query_selector("b")
    closest_p = b.closest("p")
    assert closest_p is not None
    assert closest_p.get_attribute("id") == "p1"


def test_nth_of_type(rich_dom):
    doc = rich_dom.window.document
    items = doc.query_selector_all("li:nth-of-type(2)")
    assert items.length == 1
    assert items[0].text_content == "two"


def test_pseudo_class_not(rich_dom):
    doc = rich_dom.window.document
    paragraphs = doc.query_selector_all("p:not(#p2)")
    assert paragraphs.length == 1
    assert paragraphs[0].get_attribute("id") == "p1"


def test_query_selector_returns_first_in_document_order(rich_dom):
    doc = rich_dom.window.document
    first_li = doc.query_selector("li")
    assert first_li is not None
    assert first_li.text_content == "one"
