# -*- coding: utf-8 -*-
"""Cross-router helper binding after the endpoints megamodule split.

Helpers that used to live in ``endpoints.py`` were moved into sibling routers.
Each router fills missing names from peers (and a few non-router modules) so
``NameError`` does not surface at request time. Safe under circular imports:
only keys absent from the target globals are copied.
"""
from __future__ import annotations

import importlib
from typing import Any, Dict, Iterable, Tuple

# Order matters little; import_module is idempotent. Keep endpoints first.
SHARED_HELPER_MODULES: Tuple[str, ...] = (
    "app.api.endpoints",
    "app.api.deps",
    "app.api.routers.projects_workspace",
    "app.api.routers.generate",
    "app.api.routers.assets",
    "app.api.routers.entities",
    "app.api.routers.prompts_analyze",
    "app.api.routers.script_analysis_diagnosis",
    "app.api.routers.workspace_residual",
    "app.api.routers.tools_agent",
    "app.services.auth_email",
    "app.services.media_service",
    "app.services.auth_login",
)


def bind_shared_helpers(
    globals_dict: Dict[str, Any],
    current_module_name: str,
    *,
    extra_modules: Iterable[str] = (),
) -> None:
    seen = {current_module_name}
    for modname in (*SHARED_HELPER_MODULES, *tuple(extra_modules or ())):
        if not modname or modname in seen:
            continue
        seen.add(modname)
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for key, value in vars(mod).items():
            if key not in globals_dict:
                globals_dict[key] = value


def rebind_all_router_helpers() -> None:
    """Refresh binds after every router has been imported (call from app startup)."""
    for modname in SHARED_HELPER_MODULES:
        if not modname.startswith("app.api.routers."):
            continue
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        binder = getattr(mod, "_bind_endpoint_helpers", None)
        if callable(binder):
            try:
                binder()
            except Exception:
                continue

    # endpoints.py still hosts residual routes that call helpers moved into routers.
    try:
        endpoints = importlib.import_module("app.api.endpoints")
        bind_shared_helpers(vars(endpoints), "app.api.endpoints")
    except Exception:
        pass
