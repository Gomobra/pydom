"""Tests for the Node-tree mutation algorithms (DOM Living Standard)."""

import pytest

from pydom.dom import Document
from pydom.dom.exceptions import HierarchyRequestError, NotFoundError


def test_append_child_and_parent_links():
    doc = Document()
    parent = doc.create_element("div")
    child = doc.create_element("span")
    result = parent.append_child(child)
    assert result is child
    assert child.parent_node is parent
    assert parent.child_nodes.length == 1
    assert parent.first_child is child
    assert parent.last_child is child


def test_append_child_reparents_existing_node():
    doc = Document()
    a = doc.create_element("a")
    b = doc.create_element("b")
    c = doc.create_element("c")
    a.append_child(c)
    b.append_child(c)  # moves c from a to b
    assert c.parent_node is b
    assert a.child_nodes.length == 0
    assert b.child_nodes.length == 1


def test_insert_before_ordering():
    doc = Document()
    parent = doc.create_element("ul")
    first = doc.create_element("li")
    second = doc.create_element("li")
    third = doc.create_element("li")
    parent.append_child(first)
    parent.append_child(third)
    parent.insert_before(second, third)
    order = [c.tag_name for c in parent.child_nodes]
    assert order == ["LI", "LI", "LI"]
    assert parent.child_nodes[1] is second


def test_remove_child():
    doc = Document()
    parent = doc.create_element("div")
    child = doc.create_element("p")
    parent.append_child(child)
    removed = parent.remove_child(child)
    assert removed is child
    assert child.parent_node is None
    assert parent.child_nodes.length == 0


def test_replace_child():
    doc = Document()
    parent = doc.create_element("div")
    old = doc.create_element("old")
    new = doc.create_element("new")
    parent.append_child(old)
    returned = parent.replace_child(new, old)
    assert returned is old
    assert old.parent_node is None
    assert new.parent_node is parent
    assert parent.child_nodes[0] is new


def test_append_self_raises_hierarchy_request():
    doc = Document()
    a = doc.create_element("a")
    with pytest.raises(HierarchyRequestError):
        a.append_child(a)


def test_append_descendant_raises_hierarchy_request():
    doc = Document()
    a = doc.create_element("a")
    b = doc.create_element("b")
    a.append_child(b)
    with pytest.raises(HierarchyRequestError):
        b.append_child(a)  # a is an ancestor of b


def test_remove_non_child_raises_not_found():
    doc = Document()
    parent = doc.create_element("div")
    orphan = doc.create_element("p")
    with pytest.raises(NotFoundError):
        parent.remove_child(orphan)


def test_text_content_setter_replaces_children():
    doc = Document()
    el = doc.create_element("p")
    el.append_child(doc.create_element("span"))
    el.text_content = "Hello"
    assert el.text_content == "Hello"
    assert el.child_nodes.length == 1
    assert el.first_child.node_type == 3  # TEXT_NODE


def test_clone_node_shallow_vs_deep():
    doc = Document()
    parent = doc.create_element("div")
    child = doc.create_element("span")
    child.set_attribute("class", "x")
    parent.append_child(child)

    shallow = parent.clone_node(deep=False)
    assert shallow.child_nodes.length == 0
    assert shallow.tag_name == "DIV"

    deep = parent.clone_node(deep=True)
    assert deep.child_nodes.length == 1
    assert deep.first_child.get_attribute("class") == "x"
    # Clones must be detached from the original tree.
    assert deep.first_child.parent_node is deep


def test_previous_next_sibling():
    doc = Document()
    parent = doc.create_element("div")
    a = doc.create_element("a")
    b = doc.create_element("b")
    c = doc.create_element("c")
    parent.append_child(a)
    parent.append_child(b)
    parent.append_child(c)
    assert b.previous_sibling is a
    assert b.next_sibling is c
    assert a.previous_sibling is None
    assert c.next_sibling is None
