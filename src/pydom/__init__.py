"""pydom — a pure-Python implementation of the WHATWG DOM and HTML Standards.

Inspired by jsdom. Public API surface is re-exported here.
"""

__version__ = "0.1.0"

from pydom.api import JSDOM
from pydom.dom.exceptions import DOMException

__all__ = ["JSDOM", "DOMException", "__version__"]
