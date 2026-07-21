# -*- coding: utf-8 -*-
"""Entity CRUD / analyze / history-llm routers package."""
from __future__ import annotations

from app.api.routers.entities_pkg.shared import router
from app.api.routers.entities_pkg import shared as _shared

from app.api.routers.entities_pkg import analyze as _analyze  # noqa: F401,E402
from app.api.routers.entities_pkg import history_llm as _history_llm  # noqa: F401,E402

_SECTION_MODULES = (_analyze, _history_llm)
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


try:
    _shared._bind_endpoint_helpers()
except Exception:
    pass
_sync_section_globals()

__all__ = ["router"]
