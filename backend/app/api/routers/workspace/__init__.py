# -*- coding: utf-8 -*-
"""Workspace routers package (projects/episodes/scenes/shots)."""
from __future__ import annotations

from app.api.routers.workspace.shared import router
from app.api.routers.workspace import shared as _shared

# Register section routes onto shared.router
from app.api.routers.workspace import episodes as _episodes  # noqa: F401,E402
from app.api.routers.workspace import scenes as _scenes  # noqa: F401,E402
from app.api.routers.workspace import shots as _shots  # noqa: F401,E402
from app.api.routers.workspace import admin_residual as _admin_residual  # noqa: F401,E402

_SECTION_MODULES = (_episodes, _scenes, _shots, _admin_residual)
_SKIP = {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__doc__", "__builtins__"}


def _publish_section_symbols_to_shared() -> None:
    """Schemas/helpers defined in section modules must be visible via shared/facade bind."""
    for mod in _SECTION_MODULES:
        for key, value in vars(mod).items():
            if key in _SKIP:
                continue
            if key == "router":
                continue
            # Prefer first definition; allow overwrite for same object identity refreshes
            if key not in vars(_shared) or getattr(_shared, key, None) is not value:
                setattr(_shared, key, value)


def _sync_section_globals() -> None:
    """Route functions live in section modules; keep their globals aligned with shared helpers."""
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
