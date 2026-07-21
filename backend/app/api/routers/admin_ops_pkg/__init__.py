# -*- coding: utf-8 -*-
"""Admin ops routers package (logs/storage/configs)."""
from __future__ import annotations

from app.api.routers.admin_ops_pkg.shared import router
from app.api.routers.admin_ops_pkg import shared as _shared

from app.api.routers.admin_ops_pkg import storage as _storage  # noqa: F401,E402
from app.api.routers.admin_ops_pkg import configs as _configs  # noqa: F401,E402

_SECTION_MODULES = (_storage, _configs)
_SKIP = {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__doc__", "__builtins__"}


def _publish_section_symbols_to_shared() -> None:
    for mod in _SECTION_MODULES:
        for key, value in vars(mod).items():
            if key in _SKIP or key == "router":
                continue
            setattr(_shared, key, value)


def _sync_section_globals() -> None:
    _publish_section_symbols_to_shared()
    helpers = {k: v for k, v in vars(_shared).items() if k not in _SKIP}
    for mod in _SECTION_MODULES:
        mod.__dict__.update(helpers)
        mod.router = router


_sync_section_globals()

__all__ = ["router"]
