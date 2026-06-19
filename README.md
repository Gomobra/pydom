# pydom

> A pure-Python implementation of many web standards, notably the WHATWG **DOM** and **HTML** Standards — inspired by [jsdom](https://github.com/jsdom/jsdom), but for Python.

`pydom` emulates enough of a subset of a web browser to be useful for **testing** and **scraping** real-world web applications, without launching a real browser. It parses HTML the way a browser does, builds a spec-compliant DOM tree, and lets you query and manipulate it with the familiar DOM API.

## Status

**Pre-Alpha.** Phase 1 implements the core DOM (Document, Node, Element, Text, Attr), WHATWG HTML parsing via [html5lib](https://github.com/html5lib/html5lib-python), HTML serialization, and CSS selectors via [soupsieve](https://github.com/facelessuser/soupsieve). Phase 2 adds the DOM Events model (`EventTarget`/`Event`/`CustomEvent`) and JavaScript execution via [STPyV8](https://github.com/cloudflare/stpyv8) (Google V8) behind the `run_scripts` option. Subresource loading and layout are **not** implemented (and are out of scope, same as jsdom's non-goal of layout).

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

For JavaScript execution (the `run_scripts` option), install the optional `[js]` extra, which pulls in STPyV8 and its ICU data:

```bash
pip install -e ".[js]"
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

### JavaScript execution (`run_scripts`)

`pydom` can execute JavaScript inside the page using the same modes as jsdom:

* `run_scripts="outside-only"` — installs JS globals on `window` and lets you
  call `window.eval()`, but does **not** auto-run `<script>` tags.
* `run_scripts="dangerously"` — same as `outside-only`, plus it executes inline
  `<script>` tags in document order when the `JSDOM` is constructed.

Requires the optional `[js]` extra (`pip install pydom[js]`) which bundles
Google V8 via [STPyV8](https://github.com/cloudflare/stpyv8).

```python
# outside-only: drive the DOM from JS manually
dom = JSDOM("<!DOCTYPE html>", run_scripts="outside-only")
dom.window.eval("document.body.innerHTML = '<p>x</p>';")
print(dom.window.document.query_selector("p").text_content)  # "x"
```

```python
# dangerously: inline scripts run automatically during construction
dom = JSDOM(
    "<!DOCTYPE html><body><script>window.__loaded = true;</script></body></body>",
    run_scripts="dangerously",
)
print(dom.window.eval("window.__loaded"))  # True
```

Known limitations of the current JS bridge:

* External `<script src="...">` tags are **not** loaded (subresource loading is not implemented).
* `NodeList` / `HTMLCollection` are iterable via `for…of` and `.item(i)`, but **bracket-index access** (`collection[0]`) does not bridge yet.
* `setTimeout`/`setInterval` are stubs and do not schedule real callbacks.

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
| `EventTarget` / `Event` / `CustomEvent` | ✅ DOM events, capture/bubble |
| Script execution (`run_scripts`) | ✅ via STPyV8 (optional) |
| Subresource loading | ❌ out of scope (phase 2) |
| Layout / rendering | ❌ (permanent, like jsdom) |

## License

MIT
