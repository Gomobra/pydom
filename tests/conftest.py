"""Shared pytest fixtures for the pydom test suite."""

import pytest

from pydom import JSDOM


@pytest.fixture
def dom() -> JSDOM:
    """A minimal JSDOM populated from a small HTML document."""
    return JSDOM("<!DOCTYPE html><p>Hello world</p>")


@pytest.fixture
def rich_dom() -> JSDOM:
    """A JSDOM with a more varied document for selector/serialization tests."""
    html = """<!DOCTYPE html>
<html>
  <head><title>Test</title></head>
  <body>
    <div id="container" class="main">
      <p class="a" id="p1">Hello <b>world</b></p>
      <p class="a" id="p2">Hi</p>
      <ul>
        <li data-x="1">one</li>
        <li data-x="2">two</li>
        <li data-x="3">three</li>
      </ul>
    </div>
    <img src="x.png">
    <br>
  </body>
</html>"""
    return JSDOM(html)
