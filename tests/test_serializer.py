"""Tests for the HTML serializer (fragment serialization algorithm)."""

from pydom.html.parser import parse_html
from pydom.html.serializer import serialize


def test_serialize_full_document_with_doctype():
    doc = parse_html("<!DOCTYPE html>hello")
    assert serialize(doc) == "<!DOCTYPE html><html><head></head><body>hello</body></html>"


def test_void_elements_have_no_end_tag():
    doc = parse_html("<!DOCTYPE html><body><br><img src=x><hr></body>")
    out = serialize(doc)
    assert "<br>" in out
    assert "</br>" not in out
    assert "<img src=\"x\">" in out
    assert "<hr>" in out


def test_attribute_values_are_quoted_and_escaped():
    doc = parse_html('<!DOCTYPE html><body></body>')
    a = doc.create_element("a")
    a.set_attribute("title", 'He said "hi" & <bye>')
    doc.body.append_child(a)
    out = serialize(doc)
    assert 'title="He said &quot;hi&quot; &amp; &lt;bye&gt;"' in out


def test_text_is_escaped_in_normal_context():
    doc = parse_html("<!DOCTYPE html><body></body>")
    p = doc.create_element("p")
    p.text_content = "a < b & c > d"
    doc.body.append_child(p)
    out = serialize(doc)
    assert "a &lt; b &amp; c &gt; d" in out


def test_script_content_is_not_escaped():
    doc = parse_html("<!DOCTYPE html><body></body>")
    s = doc.create_element("script")
    s.text_content = "if (a < b && c > d) {}"
    doc.body.append_child(s)
    out = serialize(doc)
    assert "if (a < b && c > d) {}" in out
    assert "&lt;" not in out


def test_inner_html_round_trip():
    doc = parse_html('<!DOCTYPE html><body><div id="c"></div></body>')
    div = doc.get_element_by_id("c")
    div.inner_html = "<p>hi <strong>there</strong></p><span>x</span>"
    assert div.inner_html == "<p>hi <strong>there</strong></p><span>x</span>"


def test_outer_html_replaces_element():
    doc = parse_html('<!DOCTYPE html><body><div id="c">old</div></body>')
    div = doc.get_element_by_id("c")
    div.outer_html = "<p>new</p>"
    assert doc.body.inner_html == "<p>new</p>"


def test_comment_serialization():
    doc = parse_html("<!DOCTYPE html><body><!-- hi --></body>")
    assert serialize(doc).count("<!-- hi -->") == 1
