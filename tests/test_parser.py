"""Tests for the html5lib-backed HTML parser."""

from pydom.html.parser import parse_html


def test_parses_doctype_and_structure():
    doc = parse_html("<!DOCTYPE html><html><body><p>hi</p></body></html>")
    assert doc.doctype is not None
    assert doc.doctype.name == "html"
    assert doc.document_element.tag_name == "HTML"
    assert doc.body.tag_name == "BODY"


def test_implied_tags_added():
    doc = parse_html("<p>x</p>")
    assert doc.head is not None
    assert doc.body is not None
    assert doc.body.query_selector("p").text_content == "x"


def test_attributes_preserved():
    doc = parse_html('<a id="l" href="/x" class="c">go</a>')
    a = doc.body.query_selector("a")
    assert a.get_attribute("id") == "l"
    assert a.get_attribute("href") == "/x"
    assert a.get_attribute("class") == "c"


def test_comments_preserved():
    doc = parse_html("<p>x</p><!-- a comment -->")
    # Find the comment among body children.
    from pydom.dom.node import COMMENT_NODE

    comments = [c for c in doc.body.child_nodes if c.node_type == COMMENT_NODE]
    assert comments
    # Browsers preserve the inner whitespace of comments verbatim.
    assert comments[0].data == " a comment "


def test_unsupported_content_type_raises():
    import pytest

    with pytest.raises(ValueError):
        parse_html("<p>x</p>", content_type="text/plain")
