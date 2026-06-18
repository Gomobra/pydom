"""Basic usage — ports jsdom's README examples to pydom.

Run with the project venv active:

    .venv\\Scripts\\python examples\\basic_usage.py
"""

from pydom import JSDOM


def main() -> None:
    # The headline example from jsdom's README.
    dom = JSDOM("<!DOCTYPE html><p>Hello world</p>")
    p = dom.window.document.query_selector("p")
    print("p.text_content =", repr(p.text_content))  # 'Hello world'

    # Customizing the environment with options.
    dom = JSDOM(
        "<p>hi</p>",
        url="https://example.org/",
        referrer="https://example.com/",
        content_type="text/html",
    )
    print("location.href =", dom.window.location.href)  # https://example.org/
    print("referrer      =", dom.referrer)              # https://example.com/

    # Implied tags: parsing adds <html>, <head>, <body>.
    dom = JSDOM("<!DOCTYPE html>hello")
    print("serialize     =", dom.serialize())
    # <!DOCTYPE html><html><head></head><body>hello</body></html>

    # Manipulating the tree from the "outside".
    dom = JSDOM('<!DOCTYPE html><body><div id="content"></div></body>')
    doc = dom.window.document
    content = doc.get_element_by_id("content")
    content.append_child(doc.create_element("hr"))
    print("content.inner_html =", content.inner_html)  # <hr>

    # outerHTML of the document element.
    print("documentElement.outer_html =",
          doc.document_element.outer_html)


if __name__ == "__main__":
    main()
