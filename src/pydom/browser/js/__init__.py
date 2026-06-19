"""JavaScript execution support for pydom, powered by STPyV8 (Google V8).

This subpackage is only imported when a :class:`~pydom.api.JSDOM` is constructed
with ``run_scripts`` set. STPyV8 is an *optional* dependency; install it via
``pip install pydom[js]``.

Public surface:
    * :class:`JSRuntime` — owns the V8 engine/isolate/context for one window.
    * :data:`RUN_SCRIPTS_OUTSIDE_ONLY` / :data:`RUN_SCRIPTS_DANGEROUSLY` —
      accepted values for ``run_scripts``.
"""

from __future__ import annotations

from pydom.browser.js.runtime import (
    RUN_SCRIPTS_DANGEROUSLY,
    RUN_SCRIPTS_OUTSIDE_ONLY,
    RUN_SCRIPTS_VALID,
    JSError,
    JSRuntime,
)

__all__ = [
    "JSRuntime",
    "JSError",
    "RUN_SCRIPTS_OUTSIDE_ONLY",
    "RUN_SCRIPTS_DANGEROUSLY",
    "RUN_SCRIPTS_VALID",
]
