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
    "app.services.endpoint_misc",
    "app.schemas.entity",
    "app.schemas.media_analyze",
    "app.schemas.project",
    "app.schemas.episode",
    "app.schemas.scene",
    "app.schemas.shot",
    "app.schemas.asset_review",
    "app.schemas.asset",
    "app.schemas.generation",
    "app.schemas.episode_requests",
    "app.services.asset_meta_utils",
    "app.services.model_invocation_billing",
    "app.services.generation_runtime.asset_registration",
    "app.services.generation_runtime.api_capabilities",
    "app.services.generation_runtime.voice_planning",
    "app.services.generation_runtime.generation_errors",
    "app.services.generation_runtime.seedance_duration",
    "app.services.generation_runtime.generation_filename",
    "app.services.generation_runtime.media_runtime_target",
    "app.services.generation_runtime.callback_http",
    "app.services.effective_api_setting",
    "app.services.generation_runtime.video_job_billing",
    "app.services.script_mode_helpers",
    "app.services.video_submit_dedup",
    "app.services.provider_alias",
    "app.services.project_cost_estimation",
    "app.services.prompt_resolve",
    "app.services.soft_delete",
    "app.services.generation_runtime.job_store",
    "app.services.generation_runtime.media_persist",
    "app.services.generation_runtime.callbacks",
    "app.services.generation_runtime.queue_worker",
    "app.services.db_session_utils",
    "app.services.script_analysis_llm_config",
    "app.services.analyze_scene_dedup",
    "app.api.deps",
    "app.api.routers.workspace.shared",
    "app.api.routers.projects_workspace",
    "app.api.routers.generation.shared",
    "app.api.routers.generate",
    "app.api.routers.assets_pkg.shared",
    "app.api.routers.assets",
    "app.api.routers.entities_pkg.shared",
    "app.api.routers.entities",
    "app.api.routers.prompts.shared",
    "app.api.routers.prompts_analyze",
    "app.api.routers.tools_agent_pkg.shared",
    "app.api.routers.tools_agent",
    "app.api.routers.admin_ops_pkg.shared",
    "app.api.routers.admin_ops",
    "app.api.routers.billing_pkg.shared",
    "app.api.routers.billing",
    "app.api.routers.script_analysis_diagnosis",
    "app.services.auth_email",
    "app.services.media_service",
    "app.services.auth_login",
)


def bind_shared_helpers(
    globals_dict: Dict[str, Any],
    current_module_name: str,
    *,
    extra_modules: Iterable[str] = (),
    include_routers: bool = True,
) -> None:
    seen = {current_module_name}
    modules = SHARED_HELPER_MODULES
    if not include_routers:
        modules = tuple(m for m in modules if not m.startswith("app.api.routers."))
    for modname in (*modules, *tuple(extra_modules or ())):
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


def _sync_split_router_packages() -> None:
    """Keep split router section modules aligned after a global rebind."""
    for pkg_name in (
        "app.api.routers.workspace",
        "app.api.routers.generation",
        "app.api.routers.prompts",
        "app.api.routers.entities_pkg",
        "app.api.routers.assets_pkg",
        "app.api.routers.tools_agent_pkg",
        "app.api.routers.admin_ops_pkg",
        "app.api.routers.billing_pkg",
    ):
        try:
            pkg = importlib.import_module(pkg_name)
        except Exception:
            continue
        sync = getattr(pkg, "_sync_section_globals", None)
        if callable(sync):
            try:
                sync()
            except Exception:
                continue


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

    _sync_split_router_packages()
