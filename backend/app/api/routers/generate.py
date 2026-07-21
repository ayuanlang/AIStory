# -*- coding: utf-8 -*-
"""Compatibility facade for generate routes (split into app.api.routers.generation)."""
from __future__ import annotations

import app.api.routers.generation as _generation_pkg  # noqa: F401
from app.api.routers.generation import router
from app.api.routers.generation import shared as _shared

_skip = {
    "__name__",
    "__file__",
    "__package__",
    "__loader__",
    "__spec__",
    "__doc__",
    "__builtins__",
    "router",  # never clobber the package router via helper re-exports
}
globals().update({k: v for k, v in vars(_shared).items() if k not in _skip})

try:
    _generation_pkg._sync_section_globals()
    globals().update({k: v for k, v in vars(_shared).items() if k not in _skip})
except Exception:
    pass

# Pin router after sync/re-exports
from app.api.routers.generation.shared import router as router  # noqa: E402,F811

__all__ = ["router"]
