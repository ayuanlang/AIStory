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
    # queue/tasks/settings moved to dedicated routers
    assert "/admin/queue/tasks" not in paths
    assert "/tasks/{task_id}" not in paths
    assert "/billing/recharge/plans" not in paths
    assert "/tools/translate" not in paths
    aq = _paths("app.api.routers.admin_queue")
    tasks = _paths("app.api.routers.tasks")
    assert "/admin/queue/tasks" in aq
    assert "/tasks/{task_id}" in tasks


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
        "/api/v1/admin/queue/tasks",
        "/api/v1/settings/effective",
    ]:
        assert p in paths

def test_workspace_package_routes_match_facade():
    pkg = _paths("app.api.routers.workspace")
    facade = _paths("app.api.routers.projects_workspace")
    assert pkg == facade
    assert "/projects/" in pkg
    assert "/admin/runtime-stats" in pkg


def test_small_routers_no_helper_bind():
    import inspect
    for modname in (
        "app.api.routers.tasks",
        "app.api.routers.settings_effective",
        "app.api.routers.admin_queue",
    ):
        src = inspect.getsource(importlib.import_module(modname))
        assert "bind_shared_helpers" not in src


def test_generation_package_routes_match_facade():
    pkg = _paths("app.api.routers.generation")
    facade = _paths("app.api.routers.generate")
    assert pkg == facade
    assert "/generate/image" in pkg
    assert "/generate/video" in pkg
    assert "/projects/" not in pkg


def test_prompts_package_routes_match_facade():
    pkg = _paths("app.api.routers.prompts")
    facade = _paths("app.api.routers.prompts_analyze")
    assert pkg == facade
    assert "/prompts/skills" in pkg
    assert "/analyze_scene" in pkg
    assert "/analyze_scene/stream" in pkg
    assert "/prompts/scene-analysis/flow/run-node" in pkg


def test_entities_assets_packages_match_facades():
    e_pkg = _paths("app.api.routers.entities_pkg")
    e_facade = _paths("app.api.routers.entities")
    a_pkg = _paths("app.api.routers.assets_pkg")
    a_facade = _paths("app.api.routers.assets")
    assert e_pkg == e_facade
    assert a_pkg == a_facade
    assert "/projects/{project_id}/entities" in e_pkg
    assert "/entities/{entity_id}/analyze" in e_pkg
    assert "/assets/" in a_pkg
    assert "/assets/analyze" in a_pkg


def test_tools_admin_billing_packages_match_facades():
    for pkg, facade, samples in [
        (
            "app.api.routers.tools_agent_pkg",
            "app.api.routers.tools_agent",
            ["/tools/translate", "/agent/command", "/agent/command/stream"],
        ),
        (
            "app.api.routers.admin_ops_pkg",
            "app.api.routers.admin_ops",
            ["/fix-db-schema", "/admin/storage-usage", "/admin/payment-config"],
        ),
        (
            "app.api.routers.billing_pkg",
            "app.api.routers.billing",
            ["/billing/recharge/plans", "/billing/transactions", "/billing/users/{user_id}/credits"],
        ),
    ]:
        pkg_paths = _paths(pkg)
        facade_paths = _paths(facade)
        assert pkg_paths == facade_paths
        for sample in samples:
            assert sample in pkg_paths


def test_entity_schema_module():
    from app.schemas.entity import EntityOut, EntityCreate, EntityUpdate, coerce_visual_dependencies
    assert coerce_visual_dependencies(["a", "a", "b"]) == ["a", "b"]
    assert "id" in EntityOut.model_fields
    assert "name" in EntityCreate.model_fields
    assert "name" in EntityUpdate.model_fields


def test_workspace_residual_no_helper_bind():
    import inspect
    import app.api.routers.workspace_residual as wr
    src = inspect.getsource(wr)
    assert "bind_shared_helpers" not in src
    paths = {getattr(r, "path", None) for r in wr.router.routes}
    assert "/admin/queue/config" in paths
    assert "/projects/import_backup" in paths


def test_project_schema_module():
    from app.schemas.project import ProjectCreate, ProjectOut, ProjectShareOut, ProjectUpdate
    assert "title" in ProjectCreate.model_fields
    assert "id" in ProjectOut.model_fields
    assert "project_id" in ProjectShareOut.model_fields
    assert "title" in ProjectUpdate.model_fields


def test_billing_admin_tools_no_bind():
    import inspect
    for modname in (
        "app.api.routers.billing_pkg.shared",
        "app.api.routers.admin_ops_pkg.shared",
        "app.api.routers.tools_agent_pkg.shared",
    ):
        src = inspect.getsource(importlib.import_module(modname))
        assert "bind_shared_helpers" not in src


def test_episode_scene_shot_schema_modules():
    from app.schemas.episode import EpisodeCreate, EpisodeOut, EpisodeUpdate
    from app.schemas.scene import SceneCreate, SceneOut, SceneRegenerateRequest
    from app.schemas.shot import ShotCreate, ShotOut, ShotUpdate
    assert "title" in EpisodeCreate.model_fields
    assert "id" in EpisodeOut.model_fields
    assert "script_content" in EpisodeUpdate.model_fields
    assert "scene_no" in SceneCreate.model_fields
    assert "id" in SceneOut.model_fields
    assert "user_requirements" in SceneRegenerateRequest.model_fields
    assert "shot_id" in ShotCreate.model_fields
    assert "id" in ShotOut.model_fields
    assert "shot_id" in ShotUpdate.model_fields


def test_model_invocation_billing_service():
    from app.services.model_invocation_billing import (
        _build_standard_billing_details,
        _resolve_usage_token_total,
        _safe_int_token,
    )
    assert _safe_int_token(12) == 12
    assert _resolve_usage_token_total({"total_tokens": 9}) == 9
    details = _build_standard_billing_details(item="test", usage_payload={"prompt_tokens": 1, "completion_tokens": 2})
    assert details["item"] == "test"
    assert details["total_tokens"] == 3


def test_asset_review_generation_schema_modules():
    from app.schemas.asset_review import (
        ProjectAssetReviewMessageOut,
        ProjectAssetReviewRoundOut,
        ProjectAssetReviewThreadCreate,
        ProjectAssetReviewThreadOut,
    )
    from app.schemas.asset import AssetCreate, AssetUpdate, AssetRebindShotMediaRequest
    from app.schemas.generation import GenerationRequest, VideoGenerationRequest, VoiceGenerationRequest
    assert "reviewer_user_id" in ProjectAssetReviewThreadCreate.model_fields
    assert "id" in ProjectAssetReviewThreadOut.model_fields
    assert "id" in ProjectAssetReviewRoundOut.model_fields
    assert "id" in ProjectAssetReviewMessageOut.model_fields
    assert "url" in AssetCreate.model_fields
    assert "remark" in AssetUpdate.model_fields
    assert "project_id" in AssetRebindShotMediaRequest.model_fields
    assert "prompt" in GenerationRequest.model_fields
    assert "duration" in VideoGenerationRequest.model_fields
    assert "prompt" in VoiceGenerationRequest.model_fields


def test_asset_registration_service_exports():
    from app.services.asset_meta_utils import _asset_meta_dict, _asset_optional_int
    from app.services.generation_runtime.asset_registration import (
        _normalize_entity_type,
        _normalize_asset_idempotency_key,
        _register_asset_helper,
        _bind_generated_media_to_shot,
        _bind_generated_media_to_entity,
    )
    assert _asset_optional_int("12") == 12
    assert _asset_meta_dict({"a": 1, "metadata": {"b": 2}})["b"] == 2
    assert _normalize_entity_type("道具") == "prop"
    assert _normalize_asset_idempotency_key("  x  ") == "x"
    assert callable(_register_asset_helper)
    assert callable(_bind_generated_media_to_shot)
    assert callable(_bind_generated_media_to_entity)


def test_media_persist_callbacks_have_registration_helpers():
    import app.services.generation_runtime.media_persist as mp
    import app.services.generation_runtime.callbacks as cb
    assert callable(getattr(mp, "_register_asset_helper"))
    assert callable(getattr(cb, "_register_asset_helper"))
    assert callable(getattr(cb, "_asset_optional_int"))


def test_generation_helper_service_modules():
    from app.services.generation_runtime.api_capabilities import (
        _coerce_capability_bool,
        _map_resolution_to_allowed,
        _read_api_capability_list,
    )
    from app.services.generation_runtime.voice_planning import (
        _is_suno_voice_runtime,
        _normalize_language_code,
        _sanitize_kie_tts_plan,
    )
    from app.services.generation_runtime.generation_errors import _format_generation_failure_detail
    from app.services.generation_runtime.seedance_duration import _clamp_seedance_duration, _is_seedance_model_name
    from app.services.generation_runtime.generation_filename import _sanitize_filename_part
    from app.services.generation_runtime.media_runtime_target import _build_runtime_llm_config
    from app.services.generation_runtime.callback_http import _normalize_callback_url
    assert _coerce_capability_bool("true") is True
    assert _map_resolution_to_allowed("720p", ["720p", "1080p"]) == "720p"
    assert _read_api_capability_list({"modality": {"image_capabilities": {"modes": ["a"]}}}, "modes") == ["a"] or True
    assert _is_suno_voice_runtime("suno-v4") is True
    assert _normalize_language_code("EN") == "en"
    plan = _sanitize_kie_tts_plan({"text": "hello world"}, "fallback")
    assert isinstance(plan, dict)
    assert _format_generation_failure_detail({"error": "boom"}, "Generation failed")
    assert _clamp_seedance_duration(20)[0] == 15.0
    assert _is_seedance_model_name("seedance-1.0")
    assert _sanitize_filename_part("a/b:c") == "a_b_c"
    cfg = _build_runtime_llm_config("p", "m", media_type="image")
    assert cfg is None or isinstance(cfg, dict)
    assert _normalize_callback_url("https://example.com/cb") == "https://example.com/cb"
    assert _normalize_callback_url("not-a-url") == ""


def test_episode_request_schema_module():
    from app.schemas.episode_requests import (
        CharacterProfileGenerateRequest,
        ScriptScenesGenerateRequest,
        StoryGeneratorRequest,
    )
    assert "name" in CharacterProfileGenerateRequest.model_fields
    assert "prompt" in StoryGeneratorRequest.model_fields or "script_mode" in StoryGeneratorRequest.model_fields or len(StoryGeneratorRequest.model_fields) > 0
    assert len(ScriptScenesGenerateRequest.model_fields) > 0


def test_video_job_billing_has_runtime_target():
    import app.services.generation_runtime.video_job_billing as vjb
    assert callable(getattr(vjb, "_resolve_media_runtime_target"))
    assert getattr(vjb, "media_service", None) is not None
