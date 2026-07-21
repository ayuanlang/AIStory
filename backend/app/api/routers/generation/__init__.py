# -*- coding: utf-8 -*-
"""Generation routers package (image/video/jobs/batch/montage)."""
from __future__ import annotations

from app.api.routers.generation.shared import router
from app.api.routers.generation import shared as _shared

from app.api.routers.generation import users_admin as _users_admin  # noqa: F401,E402
from app.api.routers.generation import video_jobs as _video_jobs  # noqa: F401,E402
from app.api.routers.generation import batch_media as _batch_media  # noqa: F401,E402
from app.api.routers.generation import montage as _montage  # noqa: F401,E402

_SECTION_MODULES = (_users_admin, _video_jobs, _batch_media, _montage)
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
