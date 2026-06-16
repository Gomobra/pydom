# pydom

`pydom` is a small, jsdom-inspired DOM environment for Python. Version 0.1 focuses
on HTML parsing, DOM traversal, selectors, DOM mutation, serialization, and a
basic event system.

It intentionally does not implement JavaScript execution, subresource loading,
CSS layout, canvas, or visual rendering.

## Development

Use a virtual environment; do not install dependencies globally.

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
```

## Example

```python
from pydom import JSDOM

dom = JSDOM("<!DOCTYPE html><p>Hello</p>")
document = dom.window.document

print(document.query_selector("p").text_content)
document.body.append_child(document.create_element("hr"))
print(dom.serialize())
```
