"""Fragment parsing — the simplest case where you don't need a full JSDOM.

Run with the project venv active:

    .venv\\Scripts\\python examples\\fragment.py
"""

from pydom import JSDOM


def main() -> None:
    frag = JSDOM.fragment("<p>Hello</p><p><strong>Hi!</strong></p>")
    print("child count   =", frag.child_nodes.length)            # 2
    print("strong text   =", frag.query_selector("strong").text_content)  # Hi!

    # Fragments support the usual traversal/query APIs.
    paragraphs = frag.query_selector_all("p")
    for i, p in enumerate(paragraphs):
        print(f"  p[{i}].text_content = {p.text_content!r}")


if __name__ == "__main__":
    main()
