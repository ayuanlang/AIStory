# -*- coding: utf-8 -*-
"""Compatibility facade for assets routes (split into app.api.routers.assets_pkg)."""
from __future__ import annotations

import app.api.routers.assets_pkg as _assets_pkg  # noqa: F401
from app.api.routers.assets_pkg import router
from app.api.routers.assets_pkg import shared as _shared

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
    _assets_pkg._sync_section_globals()
    globals().update({k: v for k, v in vars(_shared).items() if k not in _skip})
except Exception:
    pass

from app.api.routers.assets_pkg.shared import router as router  # noqa: E402,F811

__all__ = ["router"]
