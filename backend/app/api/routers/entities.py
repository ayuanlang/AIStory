# -*- coding: utf-8 -*-
"""Compatibility facade for entities routes (split into app.api.routers.entities_pkg)."""
from __future__ import annotations

import app.api.routers.entities_pkg as _entities_pkg  # noqa: F401
from app.api.routers.entities_pkg import router
from app.api.routers.entities_pkg import shared as _shared

_skip = {
    "__name__",
    "__file__",
    "__package__",
    "__loader__",
    "__spec__",
    "__doc__",
    "__builtins__",
    "router",
}
globals().update({k: v for k, v in vars(_shared).items() if k not in _skip})

try:
    _entities_pkg._sync_section_globals()
    globals().update({k: v for k, v in vars(_shared).items() if k not in _skip})
except Exception:
    pass

from app.api.routers.entities_pkg.shared import router as router  # noqa: E402,F811

__all__ = ["router"]
