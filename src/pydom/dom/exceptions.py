"""DOM exceptions — :class:`DOMException` and its named error family.

The DOM Standard models exceptions through ``DOMException``, which carries a
``name`` string (e.g. ``"HierarchyRequestError"``) rather than a distinct
subclass per error. We expose both: a single ``DOMException`` whose ``name``
attribute is set, and convenience subclasses named after each error so callers
can ``except`` them idiomatically.

Reference: https://dom.spec.whatwg.org/#domexception
"""

from __future__ import annotations

from typing import Optional


class DOMError(Exception):
    """Base class for the DOM error hierarchy (the ``DOMException`` interface)."""


class DOMException(DOMError):
    """Raised when a DOM operation cannot be completed.

    Mirrors the WebIDL ``DOMException`` interface. The ``name`` attribute holds
    the spec-defined error name; ``code`` holds the legacy integer code (0 when
    there is no legacy code).
    """

    # Legacy error code constants (kept for parity with the Web IDL interface).
    INDEX_SIZE_ERR = 1
    DOMSTRING_SIZE_ERR = 2
    HIERARCHY_REQUEST_ERR = 3
    WRONG_DOCUMENT_ERR = 4
    INVALID_CHARACTER_ERR = 5
    NO_DATA_ALLOWED_ERR = 6
    NO_MODIFICATION_ALLOWED_ERR = 7
    NOT_FOUND_ERR = 8
    NOT_SUPPORTED_ERR = 9
    INUSE_ATTRIBUTE_ERR = 10
    INVALID_STATE_ERR = 11
    SYNTAX_ERR = 12
    INVALID_MODIFICATION_ERR = 13
    NAMESPACE_ERR = 14
    INVALID_ACCESS_ERR = 15
    VALIDATION_ERR = 16
    TYPE_MISMATCH_ERR = 17
    SECURITY_ERR = 18
    NETWORK_ERR = 19
    ABORT_ERR = 20
    URL_MISMATCH_ERR = 21
    QUOTA_EXCEEDED_ERR = 22
    TIMEOUT_ERR = 23
    INVALID_NODE_TYPE_ERR = 24
    DATA_CLONE_ERR = 25

    # Map of spec error name -> legacy integer code (0 if none).
    _NAME_TO_CODE = {
        "IndexSizeError": INDEX_SIZE_ERR,
        "HierarchyRequestError": HIERARCHY_REQUEST_ERR,
        "WrongDocumentError": WRONG_DOCUMENT_ERR,
        "InvalidCharacterError": INVALID_CHARACTER_ERR,
        "NoModificationAllowedError": NO_MODIFICATION_ALLOWED_ERR,
        "NotFoundError": NOT_FOUND_ERR,
        "NotSupportedError": NOT_SUPPORTED_ERR,
        "InUseAttributeError": INUSE_ATTRIBUTE_ERR,
        "InvalidStateError": INVALID_STATE_ERR,
        "SyntaxError": SYNTAX_ERR,
        "InvalidModificationError": INVALID_MODIFICATION_ERR,
        "NamespaceError": NAMESPACE_ERR,
        "InvalidAccessError": INVALID_ACCESS_ERR,
        "SecurityError": SECURITY_ERR,
        "NetworkError": NETWORK_ERR,
        "AbortError": ABORT_ERR,
        "URLMismatchError": URL_MISMATCH_ERR,
        "QuotaExceededError": QUOTA_EXCEEDED_ERR,
        "TimeoutError": TIMEOUT_ERR,
        "InvalidNodeTypeError": INVALID_NODE_TYPE_ERR,
        "DataCloneError": DATA_CLONE_ERR,
    }

    def __init__(self, message: str = "", name: str = "Error") -> None:
        super().__init__(message)
        self.name: str = name
        self.code: int = self._NAME_TO_CODE.get(name, 0)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"DOMException(name={self.name!r}, message={self.args[0]!r})"


def _make(name: str, legacy: int) -> type:
    """Create a convenience subclass bound to a specific spec error name."""

    class _Named(DOMException):
        def __init__(self, message: str = "") -> None:
            super().__init__(message, name)

    _Named.__name__ = name
    _Named.__qualname__ = name
    _Named.legacy_code = legacy
    return _Named


# Named subclasses for ergonomic ``except`` clauses.
IndexSizeError = _make("IndexSizeError", DOMException.INDEX_SIZE_ERR)
HierarchyRequestError = _make("HierarchyRequestError", DOMException.HIERARCHY_REQUEST_ERR)
WrongDocumentError = _make("WrongDocumentError", DOMException.WRONG_DOCUMENT_ERR)
InvalidCharacterError = _make("InvalidCharacterError", DOMException.INVALID_CHARACTER_ERR)
NoModificationAllowedError = _make(
    "NoModificationAllowedError", DOMException.NO_MODIFICATION_ALLOWED_ERR
)
NotFoundError = _make("NotFoundError", DOMException.NOT_FOUND_ERR)
NotSupportedError = _make("NotSupportedError", DOMException.NOT_SUPPORTED_ERR)
SyntaxError = _make("SyntaxError", DOMException.SYNTAX_ERR)
NamespaceError = _make("NamespaceError", DOMException.NAMESPACE_ERR)
InvalidAccessError = _make("InvalidAccessError", DOMException.INVALID_ACCESS_ERR)
InvalidStateError = _make("InvalidStateError", DOMException.INVALID_STATE_ERR)
SecurityError = _make("SecurityError", DOMException.SECURITY_ERR)
QuotaExceededError = _make("QuotaExceededError", DOMException.QUOTA_EXCEEDED_ERR)


def create_dom_exception(name: str, message: Optional[str] = None) -> DOMException:
    """Construct a :class:`DOMException` for the given spec error ``name``."""

    msg = message if message is not None else name
    return DOMException(msg, name)
