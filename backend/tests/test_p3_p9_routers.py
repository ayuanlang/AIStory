# -*- coding: utf-8 -*-
import importlib


def _paths(modname: str):
    mod = importlib.import_module(modname)
    return {getattr(r, "path", None) for r in mod.router.routes}


def test_billing_router_paths():
    paths = _paths("app.api.routers.billing")
    assert "/billing/recharge/plans" in paths
    assert "/billing/transactions" in paths
    assert "/billing/users/{user_id}/credits" in paths


def test_tools_agent_router_paths():
    paths = _paths("app.api.routers.tools_agent")
    assert "/tools/translate" in paths
    assert "/agent/command" in paths
    assert "/agent/command/stream" in paths


def test_prompts_analyze_router_paths():
    paths = _paths("app.api.routers.prompts_analyze")
    assert "/prompts/skills" in paths
    assert "/analyze_scene" in paths
    assert "/prompts/scene-analysis/flow/run-node" in paths


def test_projects_workspace_router_paths():
    paths = _paths("app.api.routers.projects_workspace")
    assert "/projects/" in paths
    assert "/episodes/{episode_id}" in paths
    assert "/scenes/{scene_id}" in paths
    assert "/shots/{shot_id}" in paths


def test_entities_assets_generate_paths():
    e = _paths("app.api.routers.entities")
    a = _paths("app.api.routers.assets")
    g = _paths("app.api.routers.generate")
    assert "/projects/{project_id}/entities" in e
    assert "/assets/" in a
    assert "/generate/image" in g
    assert "/generate/video" in g


def test_endpoints_shrunk_to_runtime_core():
    paths = _paths("app.api.endpoints")
    assert "/admin/queue/tasks" in paths
    assert "/tasks/{task_id}" in paths
    # billing/tools should not remain on endpoints
    assert "/billing/recharge/plans" not in paths
    assert "/tools/translate" not in paths


def test_wechat_pay_config_service():
    from app.services.wechat_pay_config import _wechat_config_to_dict
    d = _wechat_config_to_dict(None)
    assert d["use_mock"] is True


def test_main_app_has_critical_routes():
    from app.main import app
    paths = {getattr(r, "path", None) for r in app.routes}
    for p in [
        "/api/v1/billing/recharge/plans",
        "/api/v1/tools/translate",
        "/api/v1/analyze_scene",
        "/api/v1/projects/",
        "/api/v1/generate/image",
        "/api/v1/assets/",
        "/api/v1/users/me",
    ]:
        assert p in paths
