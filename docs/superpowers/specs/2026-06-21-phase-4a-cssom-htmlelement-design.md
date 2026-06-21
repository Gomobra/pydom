# Phase 4a — CSSOM (`element.style`) + HTMLElement subclass reflection

**Status:** Approved (design phase)
**Date:** 2026-06-21
**Depends on:** Phase 1–3 (DOM core, HTML parse/serialize, events, JS bridge, Storage/History/Location)
**Blocks:** Phase 4c (form submission needs `HTMLFormElement`/`FormData`), Phase 4b (MutationObserver hooks into attribute mutation), Phase 4f (custom elements needs the HTMLElement hierarchy)

---

## 1. Goal

Bring pydom's HTML element model up to jsdom parity for the most-used surface:

1. **Element factory dispatch** — `document.createElement("input")` and every
   element produced by the HTML parser instantiate the correct subclass
   (`HTMLInputElement`, `HTMLAnchorElement`, …), not the catch-all
   `HTMLElement`. Even tags with no special behaviour map to a thin subclass
   so that `el.constructor.name === "HTMLDivElement"` holds (testing
   frameworks assert this).
2. **IDL reflection** — content attributes are reflected onto element
   properties (`input.value`, `a.href`, `img.src`, `button.disabled`, …) with
   three reflection flavours: string, boolean, and URL.
3. **CSSOM** — `el.style` returns a `CSSStyleDeclaration` backed by the
   inline `style="..."` attribute, with camelCase get/set, `cssText`,
   `getPropertyValue`/`setProperty`/`removeProperty`, `length`/`item()`.

## 2. Non-goals (deferred)

- `getComputedStyle()` cascade, stylesheet parsing, selector-to-style
  matching. Layout is a permanent out-of-scope (same as jsdom). Inline styles
  only.
- `form.submit()` / form-encoded network submission — Phase 4c.
- `<img src>` / `<script src>` / `<link>` actual fetching — out of scope
  (no subresource loader), same as jsdom.
- Custom element lifecycle (`connectedCallback`, registry) — Phase 4f.
- IDL event-handler attributes (`el.onclick = …`) — separate events-layer
  phase; the events model itself already exists.
- `window.getComputedStyle()` — returns nothing useful without a cascade; not
  implemented.

## 3. Architecture

### 3.1 New package layout

```
src/pydom/dom/
  elements/                  # NEW package — all HTML element subclasses
    __init__.py              #   _create_html_element() factory + registry
    base.py                  #   HTMLElement (moved out of document.py)
    form.py                  #   input/textarea/select/option/button/form/...
    links.py                 #   a/area/link
    media.py                 #   img/source/embed/object/audio/video
    table.py                 #   table + rows/cells
    sections.py              #   body/head/html/div/span/p/h1-h6
    text.py                  #   pre/blockquote/ol/ul/li/br/hr
    metadata.py              #   style/script/title/meta/base
  style/
    cssom.py                 # NEW — CSSStyleDeclaration
```

`document.py` keeps a re-export (`from pydom.dom.elements.base import HTMLElement`)
so existing callers (`tree_construction`, tests) that `import HTMLElement from
pydom.dom.document` keep working.

### 3.2 Element factory & registry

A single source of truth for "tag name → subclass":

```python
# src/pydom/dom/elements/__init__.py
_TAG_REGISTRY = {
    "input": HTMLInputElement,
    "form": HTMLFormElement,
    "a": HTMLAnchorElement,
    "img": HTMLImageElement,
    # … every HTML tag, mapping to a thin subclass when no behaviour …
}

def _create_html_element(local_name: str, *, owner_document) -> HTMLElement:
    cls = _TAG_REGISTRY.get(local_name, HTMLElement)
    return cls(local_name, namespace=XHTML_NS, owner_document=owner_document)
```

**Three creation sites converge on this factory:**

| Site | Current (Phase 3) | After Phase 4a |
|---|---|---|
| `Document.create_element` (`document.py:123`) | calls `_create_html_element` | unchanged — already routes through factory |
| `tree_construction._convert_element` (`tree_construction.py:92`) | `HTMLElement(local, ...)` directly | **changed** → `_create_html_element(local, ...)` |
| `HTMLElement.__init__` direct calls (internal) | ad-hoc | kept for subclasses; not a public creation path |

### 3.3 Subclass shape

Thin subclasses (no behaviour, just typing):

```python
class HTMLDivElement(HTMLElement): pass
class HTMLSpanElement(HTMLElement): pass
class HTMLParagraphElement(HTMLElement): pass
```

Reflection-bearing subclasses override `__init__` only when they need
instance state beyond attributes (e.g. `HTMLSelectElement` caches its
`options` `HTMLOptionsCollection`). Most reflection is pure
`@property` delegating to `get_attribute` / `set_attribute`.

### 3.4 Cloning parity

`Node.clone_node` calls `_shallow_clone`. Today `Element._shallow_clone`
hardcodes `Element(...)`. To keep clones the same subclass:

- Override `_shallow_clone` in `HTMLElement` (the base for all HTML
  subclasses) to rebuild via the factory: `_create_html_element(self.local_name, owner_document=self.ownerDocument)`.
- Copy attributes as today.
- Subclasses with extra instance state override `_shallow_clone`, call
  `super()._shallow_clone()`, then copy their own fields.

This means **no subclass needs to override `_shallow_clone` unless it has
non-attribute instance state** — keeping the surface small.

## 4. HTMLElement reflection

### 4.1 Three reflection flavours

**String reflection** (most common):

```python
@property
def value(self) -> str:
    return self.get_attribute("value") or ""

@value.setter
def value(self, v: str) -> None:
    self.set_attribute("value", str(v))
```

**Boolean reflection** (`disabled`, `checked`, `readOnly`, `required`, …):

```python
@property
def disabled(self) -> bool:
    return self.has_attribute("disabled")

@disabled.setter
def disabled(self, v: bool) -> None:
    self.toggle_attribute("disabled", bool(v))
```

**URL reflection** (`a.href`, `a.protocol`, `img.src`, `form.action`, …):

Uses `pydom.url.url_record` to parse the (possibly relative) attribute
against `self.ownerDocument.url`. Each URL component is its own property:

```python
@property
def href(self) -> str:
    raw = self.get_attribute("href") or ""
    if not raw:
        return ""
    return resolve_url(raw, self.ownerDocument.url)

@href.setter
def href(self, v: str) -> None:
    self.set_attribute("href", str(v))

@property
def protocol(self) -> str:
    return url_record(self.href).protocol
# … host, hostname, port, pathname, search, hash, origin …
```

Setting `a.protocol` mutates the `href` attribute (re-serialize the record
with the new scheme); same for the other components. Matches the
`Location` interface already implemented in Phase 3.

### 4.2 Property table (Phase 4a surface)

| Subclass | String props | Boolean props | URL props | Methods/other |
|---|---|---|---|---|
| `HTMLInputElement` | value, defaultValue, type, name, placeholder, size, src, min, max, step, pattern, accept, alt, formAction, formEnctype, formMethod, formTarget, width, height | checked, defaultChecked, disabled, readOnly, required, autofocus, multiple | src, formAction | `form` (read-only ref) |
| `HTMLTextAreaElement` | value, defaultValue, name, placeholder, cols, rows, wrap, maxLength, minLength | disabled, readOnly, required, autofocus | — | `form`, `type="textarea"` |
| `HTMLSelectElement` | value, name, size | disabled, required, autofocus, multiple | — | `form`, `selectedIndex`, `selectedOptions`, `options` (HTMLOptionsCollection), `length`, `add()`/`remove()`/`item()` |
| `HTMLOptionElement` | value, text, label, defaultSelected-as-string | defaultSelected, selected, disabled | — | `index`, `form` |
| `HTMLButtonElement` | value, name, type, formAction, formEnctype, formMethod, formTarget | disabled, autofocus | formAction | `form` |
| `HTMLLabelElement` | htmlFor (`for`) | — | — | `control` (first labelable descendant) |
| `HTMLFormElement` | action, method, name, target, enctype, encoding, autocomplete, acceptCharset | noValidate | action | `elements`, `length`, `reset()`, `submit()` stub (raises "Phase 4c") |
| `HTMLAnchorElement` / `HTMLAreaElement` | target, rel, download, hreflang, type, referrerPolicy, text | — | href, protocol, host, hostname, port, pathname, search, hash, origin, username, password | — |
| `HTMLImageElement` | src, alt, srcset, sizes, loading, decoding, referrerPolicy, width, height | — | src, currentSrc | `naturalWidth`, `naturalHeight`, `complete` (static: `naturalWidth=0`, `complete=False`) |
| `HTMLLinkElement` | rel, media, type, hreflang, crossOrigin, referrerPolicy, as | disabled | href | `sheet` (None) |
| `HTMLScriptElement` | src, type, event, htmlFor, crossOrigin, referrerPolicy, nonce | async, defer | src | `text` (= textContent) |
| `HTMLStyleElement` | media, type, nonce | disabled | — | `sheet` (None) |
| `HTMLMetaElement` | content, name, httpEquiv, scheme | — | — | — |
| `HTMLBaseElement` | target | — | href | — |
| `HTMLTitleElement` | — | — | — | `text` (= textContent) |
| `HTMLTableElement` | — | — | — | `rows`, `tBodies`, `caption`, `tHead`, `tFoot`, `createTHead`/`deleteTHead`/`createTBody`/`createCaption`/`deleteCaption`/`insertRow`/`deleteRow` |
| `HTMLTableSectionElement` | — | — | — | `rows`, `insertRow`/`deleteRow` |
| `HTMLTableRowElement` | — | — | — | `cells`, `rowIndex`, `sectionRowIndex`, `insertCell`/`deleteCell` |
| `HTMLTableCellElement` | — | — | — | `colSpan`, `rowSpan`, `headers`, `cellIndex` |
| Thin subclasses (div, span, p, h1–h6, ul, ol, li, br, hr, pre, blockquote, body, head, html, …) | — | — | — | none |

`HTMLSelectElement.options` / `.selectedOptions` and `HTMLFormElement.elements`
return **live** `HTMLCollection`-style views (lazy providers, same pattern as
`Element.get_elements_by_tag_name`).

`<form>` submission: `submit()` is a **named stub that raises**
`NotSupportedError("form.submit() requires Phase 4c (form submission)")`.
This keeps the method present on the prototype (jsdom parity for the shape)
while signalling it is not yet wired.

## 5. CSSOM — `CSSStyleDeclaration`

Backed by the element's inline `style` attribute. No cascade, no stylesheets.

### 5.1 State

```python
class CSSStyleDeclaration:
    def __init__(self, element):
        self._element = element           # back-ref for attr sync
        self._props: Dict[str, str] = {}  # kebab-case -> value
        self._priorities: Dict[str, str] = {}  # kebab-case -> "" or "important"
        self._reparse()                   # parse current style attr
```

### 5.2 Spec methods

```python
def get_property_value(self, prop: str) -> str
def set_property(self, prop: str, value: str, priority: str = "") -> None
def remove_property(self, prop: str) -> str
def get_property_priority(self, prop: str) -> str
@property
def length(self) -> int
def item(self, index: int) -> str          # property name at index, or ""
@property
def css_text(self) -> str                  # serialized form
@css_text.setter
def css_text(self, value: str) -> None     # full reparse
@property
def css_float(self) -> str                 # "float" is reserved in JS
```

### 5.3 camelCase access (JS ergonomics)

JS writes `el.style.fontSize = "14px"`. We bridge camelCase ↔ kebab via
`__getattr__` / `__setattr__`:

```python
def __getattr__(self, name):
    if name.startswith("_"):
        raise AttributeError(name)
    return self.get_property_value(_camel_to_kebab(name))

def __setattr__(self, name, value):
    if name.startswith("_") or name in _RESERVED_ATTRS:
        object.__setattr__(self, name, value)
    else:
        self.set_property(_camel_to_kebab(name), str(value))
```

`_camel_to_kebab("fontSize") == "font-size"`. `_RESERVED_ATTRS` includes
the spec method names so they are not mistaken for CSS properties.

### 5.4 Attribute synchronisation

Every mutating spec method / `__setattr__` calls `_commit()` after changing
`_props`, which re-serializes the declaration into the `style` attribute:

```python
def _commit(self):
    parts = []
    for prop, val in self._props.items():
        prio = self._priorities.get(prop)
        parts.append(f"{prop}: {val}" + (" !important" if prio == "important" else ""))
    text = "; ".join(parts)
    if text:
        self._element.set_attribute("style", text)
    else:
        self._element.remove_attribute("style")
```

`el.style` on `HTMLElement` is a `@property` returning a **cached**
`CSSStyleDeclaration` per element (stored on `self._style_cache`) so identity
holds (`el.style is el.style`), matching browsers. The property lives on
`HTMLElement` only — foreign (XML/SVG) elements do not get a `style`
property in Phase 4a (matches the spec, which scopes `style` to HTML
elements). The cache is invalidated on direct `style` attribute writes
through `set_attribute("style", ...)` — done by overriding `set_attribute`
in `HTMLElement` to clear `_style_cache` when the `style` key changes.

### 5.5 Parsing

Inline style grammar (simplified, WHATWG CSSOM § 6.7):

```
declaration-list := declaration ( ";" declaration )* ";"?
declaration      := ws property ws ":" ws value ws ( "!important" )?
```

We accept: split on `;`, drop empties, split each on first `:`, strip ws,
detect trailing `!important`. Invalid declarations (no `:`) are silently
dropped, matching browsers.

## 6. Integration: JS bridge

The existing `JSProxy` (`browser/js/bridge.py`) already bridges `@property`
getters/setters and method calls transparently. The new surface needs **one
verified path**:

- `el.style` → `JSProxy.__getattr__("style")` → returns wrapped
  `CSSStyleDeclaration`. ✓ (returns a non-primitive object → auto-wrapped)
- `el.style.color = "red"` → `JSProxy.__setattr__("style", ...)` is **not**
  what happens; JS first does a `[[Get]]` of `el.style` (returns the wrapped
  decl), then `[[Set]]` `color` on *that* object → `JSProxy.__setattr__("color", "red")`
  → `_resolve_setattr_name(target, "color")`.

  **Risk:** `_resolve_setattr_name` only resolves names that are real
  descriptors on the type, else falls back to storing a plain instance
  attribute (which would shadow nothing here, but `setattr(target, "color", "red")`
  would hit `CSSStyleDeclaration.__setattr__` correctly because that method
  *is* defined on the type — so `_has_real_descriptor` returns True for
  `__setattr__`? **No** — `__setattr__` is a dunder, not a named descriptor.
  This needs a **Task 0 spike** in the implementation plan: write a 5-line
  V8 repro before building the full surface. If the bridge mishandles it,
  add `style` properties to a per-class `_CAMEL_ALIASES` map or special-case
  `CSSStyleDeclaration` in the bridge.

This is the single highest-risk integration point; it is explicitly a spike
task, not assumed.

Reflection properties (`input.value`, `a.href`) bridge for free — they are
ordinary `@property` pairs, exactly the pattern the bridge already handles
(verified by Phase 2's `innerHTML` setter test).

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Import cycle: `HTMLElement` moves to `elements/base.py`, imported by `document.py` & `tree_construction.py` which are imported by the parser | `elements/__init__.py` factory does lazy imports of subclass modules inside the registry build (module-level `from pydom.dom.elements.form import ...` is fine since `form.py` only imports `base`). `document.py` re-exports `HTMLElement` via `from pydom.dom.elements.base import HTMLElement`. Confirmed acyclic by drawing the import graph before coding. |
| Parser regression: `tree_construction._convert_element` switches to factory | Existing `test_parser.py` + `test_serializer.py` must stay green; factory returns a subclass of `HTMLElement` so `isinstance` checks in those tests still hold. Verified at plan-time. |
| `_shallow_clone` subclass parity | Centralize in `HTMLElement._shallow_clone` via factory; no per-subclass override unless extra instance state. |
| `CSSStyleDeclaration.__setattr__` under V8 bridge | Task 0 spike (see §6). |
| `style` attr cache staleness when user calls `set_attribute("style", ...)` directly | Override `HTMLElement.set_attribute` to invalidate `_style_cache` on `"style"` key. |
| Boolean reflection on `toggle_attribute(force=None)` edge cases | Reuse existing tested `toggle_attribute`; add focused tests. |

## 8. Testing

Two new files:

### `tests/test_elements.py`
- Factory dispatch: `createElement("input")` is `HTMLInputElement`;
  `createElement("div")` is `HTMLDivElement`; unknown tag → `HTMLElement`.
- **Parser dispatch**: parse `"<input><a href></a><form>"`, assert
  subclasses on the resulting nodes (this is the critical new path).
- `constructor.name` / `type(el).__name__` for representative tags.
- String reflection round-trip (`input.value = "x"; assert input.get_attribute("value") == "x"`).
- Boolean reflection (`input.disabled = True; assert input.has_attribute("disabled")`).
- URL reflection on `<a>` (`a.href` resolves relative to `document.URL`;
  setting `a.pathname` updates `href`).
- `<select>`/`<option>` value & selectedIndex.
- `<form>.elements` is live.
- `clone_node` preserves subclass (`input.clone_node()` is `HTMLInputElement`).
- `form.submit()` raises `NotSupportedError` (Phase 4c marker).

### `tests/test_cssom.py`
- Parse `"color: red; font-size: 14px"` → `length == 2`, `item(0)`/`item(1)`.
- camelCase get/set round-trip via `__setattr__`/`__getattr__`.
- `cssText` round-trip (set then get).
- `!important` priority: `set_property("color","red","important")`,
  `get_property_priority("color") == "important"`, serialized as
  `"color: red !important"`.
- Attribute sync: after `el.style.color = "red"`,
  `el.get_attribute("style")` contains `color: red`.
- Cache invalidation: `el.set_attribute("style", "opacity: 0.5")` then
  `el.style.opacity == "0.5"`.
- Empty style: setting all props removed → `style` attribute is absent
  (`has_attribute("style") is False`).
- Identity: `el.style is el.style`.

### JS bridge tests
- A new `tests/test_cssom_js.py` with one V8-backed case:
  `dom.window.eval("document.body.style.color = 'red'")` then assert via
  Python. **Gated on `[js]` extra** (skip if STPyV8 unavailable, matching the
  existing `runscripts` test convention).

## 9. Acceptance criteria

1. `pytest` is fully green (existing 104 tests + new element/CSSOM tests).
2. `document.createElement("input")` returns `HTMLInputElement`; same for
   every tag in the registry; parser path produces identical subclass types.
3. `el.style.color = "red"` works from both Python and JS (when `[js]`
   installed).
4. No import cycle; `python -c "import pydom"` still works.
5. `clone_node` preserves subclass.
6. README "What is implemented" table gains rows for
   `element.style (CSSOM, inline)` and `HTMLElement reflection`.

## 10. Out of scope — explicit reminders

- Cascade / computed style / stylesheets → never (layout out of scope).
- `form.submit()` network behaviour → Phase 4c.
- Subresource fetching (`img.src`, `script.src`) → out of scope.
- Custom elements → Phase 4f.
- IDL event-handler attributes (`onclick`) → separate events phase.
