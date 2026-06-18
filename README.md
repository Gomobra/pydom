# pydom

> A pure-Python implementation of many web standards, notably the WHATWG **DOM** and **HTML** Standards — inspired by [jsdom](https://github.com/jsdom/jsdom), but for Python.

`pydom` emulates enough of a subset of a web browser to be useful for **testing** and **scraping** real-world web applications, without launching a real browser. It parses HTML the way a browser does, builds a spec-compliant DOM tree, and lets you query and manipulate it with the familiar DOM API.

## Status

**Pre-Alpha.** Phase 1 implements the core DOM (Document, Node, Element, Text, Attr), WHATWG HTML parsing via [html5lib](https://github.com/html5lib/html5lib-python), HTML serialization, and CSS selectors via [soupsieve](https://github.com/facelessuser/soupsieve). Script execution, subresource loading, and layout are **not** implemented (and are out of scope, same as jsdom's non-goal of layout).

## Installation

Use a virtual environment (never install globally):

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Unix
source .venv/bin/activate

pip install -e .
```

## Basic usage

```python
from pydom import JSDOM

dom = JSDOM("<!DOCTYPE html><p>Hello world</p>")
print(dom.window.document.query_selector("p").text_content)  # "Hello world"
```

```python
# Customizing the environment
dom = JSDOM(
    "<p>hi</p>",
    url="https://example.org/",
    referrer="https://example.com/",
    content_type="text/html",
)
```

### `fragment()`

For the simplest cases where you don't need a full `Window`/`Document`:

```python
from pydom import JSDOM

frag = JSDOM.fragment("<p>Hello</p><p><strong>Hi!</strong>")
print(frag.query_selector("strong").text_content)  # "Hi!"
```

### Serializing

```python
dom = JSDOM("<!DOCTYPE html>hello")
print(dom.serialize())  # "<!DOCTYPE html><html><head></head><body>hello</body></html>"
```

## What is implemented

| Area | Status |
| --- | --- |
| `JSDOM` constructor + `Window` | ✅ basic |
| `Document` (`create_element`, `get_element_by_id`, …) | ✅ |
| `Node` tree (`append_child`, `insert_before`, `remove_child`, …) | ✅ |
| `Element` (`get_attribute`, `set_attribute`, `class_list`, …) | ✅ |
| HTML parsing (WHATWG via html5lib) | ✅ |
| HTML serialization | ✅ |
| CSS selectors (`query_selector` / `query_selector_all`) | ✅ via soupsieve |
| Script execution (`run_scripts`) | ❌ out of scope (phase 1) |
| Subresource loading | ❌ out of scope (phase 1) |
| Layout / rendering | ❌ (permanent, like jsdom) |

## License

MIT
