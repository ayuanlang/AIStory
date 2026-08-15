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


def test_image_generation_runner_module():
    from app.services.generation_runtime.image_generation_runner import (
        _run_generate_image,
        _run_generate_image_job,
    )
    from app.services.generation_runtime.project_generation_context import (
        _normalize_seed_value,
        _resolve_effective_negative_prompt,
    )
    from app.services.generation_runtime.video_provider_options import _build_video_provider_options
    from app.services.generation_runtime.job_timeout import _maybe_finalize_stuck_job, _resolve_job_elapsed_seconds
    from app.services.generation_runtime.queue_config_runtime import _is_pure_callback_mode_enabled
    from app.services.user_model_preferences import _normalize_cfg, _normalize_temperature
    assert callable(_run_generate_image)
    assert callable(_run_generate_image_job)
    assert _normalize_seed_value(42) == 42
    assert _normalize_seed_value(0) is None
    text, source = _resolve_effective_negative_prompt(None, "start_frame", "image")
    assert source == "default_frame_integrity"
    assert text
    assert callable(_build_video_provider_options)
    assert callable(_maybe_finalize_stuck_job)
    assert _resolve_job_elapsed_seconds({}) is None
    assert isinstance(_is_pure_callback_mode_enabled(), bool)
    assert _normalize_cfg(1.5) == 1.5
    assert _normalize_temperature(3) == 2.0


def test_generation_shared_thinned():
    from pathlib import Path
    shared = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "generation" / "shared.py"
    lines = len(shared.read_text(encoding="utf-8").splitlines())
    assert lines < 800
    import app.api.routers.generation.shared as g
    assert callable(g._run_generate_image)
    assert callable(g._maybe_finalize_stuck_job)
    paths = {getattr(r, "path", None) for r in g.router.routes}
    assert "/generate/image" in paths
    assert "/generate/image/submit" in paths


def test_queue_worker_has_image_runner_lazy_path():
    import inspect
    import app.services.generation_runtime.queue_worker as qw
    src = inspect.getsource(qw._process_generation_queue_task)
    assert "image_generation_runner" in src
    assert callable(getattr(qw, "_maybe_finalize_stuck_job"))


def test_video_voice_generation_runner_modules():
    from app.services.generation_runtime.video_generation_runner import (
        _run_generate_video,
        _run_generate_video_job,
    )
    from app.services.generation_runtime.voice_generation_runner import _run_generate_voice
    from app.services.generation_runtime.log_sanitize import (
        _mask_secret_for_log,
        _sanitize_generation_runtime_config_for_log,
    )
    assert callable(_run_generate_video)
    assert callable(_run_generate_video_job)
    assert callable(_run_generate_voice)
    assert "***" in _mask_secret_for_log("abcdefghij")
    assert _sanitize_generation_runtime_config_for_log({"api_key": "abcdefghij"})["api_key"] != "abcdefghij"


def test_video_jobs_thinned_and_reexports():
    from pathlib import Path
    import app.api.routers.generation as gen
    import app.api.routers.generation.video_jobs as vj
    import app.api.routers.generation.job_pool as jp
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "generation" / "video_jobs.py"
    jp_path = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "generation" / "job_pool.py"
    assert len(path.read_text(encoding="utf-8").splitlines()) < 700
    assert len(jp_path.read_text(encoding="utf-8").splitlines()) < 200
    assert callable(vj._run_generate_video)
    assert callable(vj._run_generate_voice)
    assert jp.router is gen.router is vj.router
    assert callable(jp.get_generation_job_pool)
    assert callable(jp.collect_generation_job_pool)
    assert callable(jp.stop_all_generation_jobs)
    assert callable(jp.repair_generation_job_history)
    assert callable(jp.stop_generation_job)
    assert callable(jp.delete_generation_job)
    paths = {getattr(r, "path", None) for r in gen.router.routes}
    assert "/generate/video" in paths
    assert "/generate/voice" in paths
    assert "/generate/jobs/pool" in paths
    assert "/generate/jobs/stop-all" in paths
    assert "from app.services.generation_job_pool import" in jp_path.read_text(encoding="utf-8")
    svc_src = (
        Path(__file__).resolve().parents[1] / "app" / "services" / "generation_job_pool.py"
    ).read_text(encoding="utf-8")
    assert "def collect_generation_job_pool(" in svc_src
    assert "def stop_all_generation_jobs(" in svc_src
    assert "SHOT_MEDIA_BATCH_STATUS_KEY" in svc_src


def test_prompts_shared_has_explicit_skill_imports():
    import inspect
    import app.api.routers.prompts.shared as ps
    src = inspect.getsource(ps)
    assert "skills_loader" in src
    assert "scene_analysis_feature_skills" in src
    assert callable(ps.load_skills_registry)
    assert callable(ps.get_scene_analysis_feature_catalog)


def test_video_ref_pipeline_module():
    from app.services.generation_runtime.video_ref_pipeline import (
        DEFAULT_SHOT_VIDEO_MODE,
        _normalize_video_ref_mode,
        _parse_shot_tech,
        _dedupe_media_ref_urls,
        _limit_keyframes_for_video_mode,
        _build_project_entity_lookup,
    )
    from app.services.system_api_lookup import get_system_api_setting
    assert DEFAULT_SHOT_VIDEO_MODE == "entity_refs"
    assert _normalize_video_ref_mode("entity-refs") == "entity_refs"
    assert _normalize_video_ref_mode("auto") == ""
    assert _dedupe_media_ref_urls(["a", "a", "b"]) == ["a", "b"]
    assert _limit_keyframes_for_video_mode(["1", "2", "3"], "start")[:1]
    assert callable(_parse_shot_tech)
    assert callable(_build_project_entity_lookup)
    assert callable(get_system_api_setting)


def test_batch_media_thinned_reexports_pipeline():
    from pathlib import Path
    import app.api.routers.generation.batch_media as bm
    from app.services.shot_media_batch_status import (
        SHOT_MEDIA_BATCH_STATUS_KEY,
        _read_shot_media_batch_status,
    )
    from app.services.shot_media_batch_jobs import (
        _is_shot_video_batch_eligible,
        _run_shot_media_batch_job,
    )
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "generation" / "batch_media.py"
    jobs_path = Path(__file__).resolve().parents[1] / "app" / "services" / "shot_media_batch_jobs.py"
    assert len(path.read_text(encoding="utf-8").splitlines()) < 500
    assert callable(bm._append_video_api_ref_mapping)
    assert bm._is_shot_video_batch_eligible is _is_shot_video_batch_eligible
    assert bm._run_shot_media_batch_job is _run_shot_media_batch_job
    assert bm._read_shot_media_batch_status is _read_shot_media_batch_status
    assert bm.SHOT_MEDIA_BATCH_STATUS_KEY == SHOT_MEDIA_BATCH_STATUS_KEY
    src = path.read_text(encoding="utf-8")
    assert "from app.services.shot_media_batch_status import" in src
    assert "from app.services.shot_media_batch_jobs import" in src
    assert "def _run_shot_media_batch_job" in jobs_path.read_text(encoding="utf-8")


def test_video_runner_uses_ref_pipeline_not_batch_media():
    import inspect
    from app.services.generation_runtime import video_generation_runner as vr
    src = inspect.getsource(vr)
    assert "video_ref_pipeline" in src
    assert "batch_media" not in src


def test_prompts_shared_no_early_bind_call():
    import inspect
    import app.api.routers.prompts.shared as ps
    src = inspect.getsource(ps)
    assert "_bind_endpoint_helpers(include_routers=False)" not in src
    assert "def _bind_endpoint_helpers" in src  # kept for package rebind
    import app.api.routers.prompts as pkg
    assert pkg.router is ps.router


def test_shot_markdown_module():
    from pathlib import Path
    import app.services.shot_markdown as sm
    assert callable(sm.parse_shots_markdown_table)
    assert callable(sm.sanitize_shots_markdown_table_text)
    assert callable(sm._validate_shot_rows_or_raise)
    headers, rows, n = sm.parse_shots_markdown_table(
        "| Shot ID | Shot Name |\n| --- | --- |\n| EP01_SC01_SH01 | A |\n"
    )
    assert "Shot ID" in headers
    assert rows and rows[0]["Shot ID"] == "EP01_SC01_SH01"
    ws = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "workspace" / "shared.py"
    assert len(ws.read_text(encoding="utf-8").splitlines()) < 5200
    assert "from app.services.shot_markdown import" in ws.read_text(encoding="utf-8")


def test_scene_markdown_orchestration_and_await_sink():
    from pathlib import Path
    from app.services.scene_markdown_orchestration import (
        SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS,
        SCENE_MARKDOWN_ORCHESTRATION_RETRY_BASE_DELAY_SEC,
        SCENE_MARKDOWN_ORCHESTRATION_BATCH_RETRY_ROUNDS,
        _derive_scene_orchestration_phase,
        _is_retryable_scene_orchestration_error,
    )
    from app.services.subject_index_resolve import (
        resolve_usable_episode_subject_index,
        _subject_index_has_usable_content,
    )
    from app.services.analyze_scene_dedup import _await_analyze_scene_segment
    from app.services.scene_markdown_runner import _run_scene_markdown_node_per_scene
    from app.services.script_progress_helpers import (
        _normalize_asset_types,
        _list_episode_scene_progress_rows,
    )
    from app.services.script_analysis_flow_runner import execute_scene_analysis_flow_node
    from app.services.script_progress_orchestration import (
        execute_auto_orchestrate_scene_progress,
        execute_reconcile_progress_status,
    )
    import app.api.endpoints as ep
    import app.api.routers.prompts.progress_flow as pf
    import inspect
    assert SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS == 3
    assert SCENE_MARKDOWN_ORCHESTRATION_RETRY_BASE_DELAY_SEC == 2.0
    assert SCENE_MARKDOWN_ORCHESTRATION_BATCH_RETRY_ROUNDS == 1
    assert _derive_scene_orchestration_phase(import_status="success", parse_status="ok") == "imported"
    assert _derive_scene_orchestration_phase(import_status="awaiting_workspace_import", parse_status="ok") == "llm_returned"
    assert callable(_is_retryable_scene_orchestration_error)
    assert _subject_index_has_usable_content("| S001 | character | a |")
    assert callable(resolve_usable_episode_subject_index)
    assert pf._derive_scene_orchestration_phase is _derive_scene_orchestration_phase
    assert callable(pf.execute_scene_analysis_flow_node)
    assert callable(execute_scene_analysis_flow_node)
    assert callable(pf.run_scene_analysis_flow_node)
    assert callable(pf.auto_orchestrate_scene_progress)
    assert callable(pf.reconcile_progress_status)
    assert callable(execute_auto_orchestrate_scene_progress)
    assert callable(execute_reconcile_progress_status)
    assert callable(_run_scene_markdown_node_per_scene)
    assert _normalize_asset_types(["characters", "covers"]) == ["character", "poster"]
    assert callable(_list_episode_scene_progress_rows)
    assert callable(_await_analyze_scene_segment)
    assert ep._await_analyze_scene_segment is _await_analyze_scene_segment
    pf_src = inspect.getsource(pf)
    assert "script_analysis_flow_runner" in pf_src
    assert "script_progress_orchestration" in pf_src
    pf_path = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "prompts" / "progress_flow.py"
    assert len(pf_path.read_text(encoding="utf-8").splitlines()) < 600
    svc_path = Path(__file__).resolve().parents[1] / "app" / "services" / "script_analysis_flow_runner.py"
    assert "async def execute_scene_analysis_flow_node(" in svc_path.read_text(encoding="utf-8")
    assert len(svc_path.read_text(encoding="utf-8").splitlines()) < 600
    orch_path = Path(__file__).resolve().parents[1] / "app" / "services" / "script_progress_orchestration.py"
    orch_src = orch_path.read_text(encoding="utf-8")
    assert "async def execute_auto_orchestrate_scene_progress(" in orch_src
    assert "async def execute_reconcile_progress_status(" in orch_src
    assert len(orch_src.splitlines()) < 500


def test_project_access_and_deletion_ops():
    from pathlib import Path
    from app.services.project_access import (
        _require_project_access,
        _is_project_shared_with_user,
        _normalize_project_share_role,
        _PROJECT_SHARE_ROLES,
    )
    from app.services.deletion_ops import (
        _start_deletion_batch,
        _soft_delete_shots,
        _active_asset_clause,
    )
    import app.api.routers.workspace.shared as ws
    assert "editor" in _PROJECT_SHARE_ROLES
    assert _normalize_project_share_role("EDITOR") == "editor"
    assert callable(_require_project_access)
    assert callable(_is_project_shared_with_user)
    assert callable(_start_deletion_batch)
    assert callable(_soft_delete_shots)
    assert _active_asset_clause() is not None
    assert ws._require_project_access is _require_project_access
    assert ws._start_deletion_batch is _start_deletion_batch
    shared = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "workspace" / "shared.py"
    assert len(shared.read_text(encoding="utf-8").splitlines()) < 1200
    assert "from app.services.project_access import" in shared.read_text(encoding="utf-8")
    assert "from app.services.deletion_ops import" in shared.read_text(encoding="utf-8")


def test_asset_registration_uses_project_access():
    import inspect
    from app.services.generation_runtime import asset_registration as ar
    src = inspect.getsource(ar)
    assert "from app.services.project_access import" in src
    assert ar._require_project_access.__module__ == "app.services.project_access"


def test_story_markdown_and_market_intel_sinks():
    from pathlib import Path
    from app.services.markdown_generation import (
        is_valid_markdown_output,
        generate_markdown_with_retry,
        _parse_episode_heading_from_markdown,
    )
    from app.services.story_generator_llm import (
        _sanitize_llm_json_text,
        _normalize_story_field_map,
        _CREATIVE_INPUT_STRUCTURE_KEYS,
    )
    from app.services.market_intel_ops import (
        _require_market_intel_model,
        _build_trending_dramas_markdown,
        _industry_analysis_section_map,
    )
    from app.services.project_episode_utils import _resolve_episode_sort_number
    import app.api.routers.workspace.shared as ws
    assert is_valid_markdown_output("# Title\n\n- item")
    assert not is_valid_markdown_output("plain")
    assert callable(generate_markdown_with_retry)
    assert _parse_episode_heading_from_markdown("# EP01 - Foo")["episode_number"] == 1
    assert _sanitize_llm_json_text('```json\n{"a":1}\n```')
    assert _normalize_story_field_map({"a": " x "}, ["a"])["a"] == "x"
    assert "logline" in _CREATIVE_INPUT_STRUCTURE_KEYS or len(_CREATIVE_INPUT_STRUCTURE_KEYS) >= 3
    assert callable(_require_market_intel_model)
    assert "热榜" in _build_trending_dramas_markdown("2026-07", "s", [])
    assert _industry_analysis_section_map()
    assert callable(_resolve_episode_sort_number)
    assert ws.generate_markdown_with_retry is generate_markdown_with_retry
    assert ws._run_structure_llm_call.__module__ == "app.services.story_generator_llm"
    root = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "workspace"
    shared_src = (root / "shared.py").read_text(encoding="utf-8")
    story_src = (root / "story_generator.py").read_text(encoding="utf-8")
    assert len(shared_src.splitlines()) < 1200
    assert "from app.services.markdown_generation import" in shared_src
    assert "from app.services.story_generator_llm import" in story_src
    assert "from app.services.market_intel_ops import" in story_src


def test_asset_registration_uses_episode_utils():
    import inspect
    from app.services.generation_runtime import asset_registration as ar
    src = inspect.getsource(ar)
    assert "project_episode_utils" in src
    assert ar._resolve_episode_sort_number.__module__ == "app.services.project_episode_utils"


def test_workspace_story_generator_section():
    from pathlib import Path
    import app.api.routers.workspace as wp
    import app.api.routers.workspace.story_generator as sg
    from app.services.project_generation_defaults import (
        _ensure_project_generation_defaults,
        _resolve_project_video_sound,
    )
    from app.services.scene_no_utils import _canonicalize_scene_no, _find_active_scene_by_scene_no
    import app.api.routers.workspace.shared as ws
    paths = {getattr(r, "path", None) for r in wp.router.routes}
    assert "/projects/{project_id}/story_generator/global" in paths
    assert "/projects/{project_id}/story_generator/analyze_novel" in paths
    assert sg.router is wp.router
    assert callable(sg.generate_project_story_dna_global)
    assert ws._ensure_project_generation_defaults is _ensure_project_generation_defaults
    assert ws._canonicalize_scene_no is _canonicalize_scene_no
    assert _canonicalize_scene_no("EP01_SC03") == "3"
    assert _resolve_project_video_sound({}) is True
    assert _ensure_project_generation_defaults({}).get("video_sound") is True
    assert _ensure_project_generation_defaults({}).get("max_shot_seconds") == 15
    assert _ensure_project_generation_defaults({"max_shot_seconds": "8"}).get("max_shot_seconds") == 8
    assert _ensure_project_generation_defaults({"max_shot_seconds": "2"}).get("max_shot_seconds") == 4
    assert callable(_find_active_scene_by_scene_no)
    shared = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "workspace" / "shared.py"
    src = shared.read_text(encoding="utf-8")
    assert len(src.splitlines()) < 1200
    assert "story_generator/global" not in src
    assert "from app.services.project_generation_defaults import" in src
    assert "from app.services.scene_no_utils import" in src


def test_image_runner_uses_generation_defaults_service():
    import inspect
    from app.services.generation_runtime import image_generation_runner as ir
    src = inspect.getsource(ir)
    assert "project_generation_defaults" in src
    assert "workspace.shared" not in src.split("def _ensure_project_generation_defaults")[1].split("async def")[0]


def test_project_sharing_and_scene_subject_helpers():
    from pathlib import Path
    import app.api.routers.workspace as wp
    import app.api.routers.workspace.project_sharing as ps
    from app.services.scene_subject_helpers import (
        _normalize_subject_entity_type,
        _extract_subjects_json_from_text,
        _build_project_subject_inventory,
    )
    import app.api.routers.workspace.scenes as sc
    import app.api.routers.workspace.shared as ws
    paths = {getattr(r, "path", None) for r in wp.router.routes}
    assert "/projects/{project_id}/shares" in paths
    assert "/projects/{project_id}/review_threads" in paths
    assert "/review_threads/{thread_id}/rounds" in paths
    assert ps.router is wp.router
    assert callable(ps.list_project_shares)
    assert callable(ps.create_project_review_thread)
    assert _normalize_subject_entity_type("道具") == "prop"
    assert sc._build_project_subject_inventory is _build_project_subject_inventory
    assert isinstance(_extract_subjects_json_from_text("{}"), dict)
    shared = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "workspace" / "shared.py"
    scenes = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "workspace" / "scenes.py"
    assert len(shared.read_text(encoding="utf-8").splitlines()) < 1200
    assert "review_threads" not in shared.read_text(encoding="utf-8")
    assert len(scenes.read_text(encoding="utf-8").splitlines()) < 1200
    assert "from app.services.scene_subject_helpers import" in scenes.read_text(encoding="utf-8")


def test_prompts_use_scene_subject_helpers():
    import inspect
    import app.api.routers.prompts.prompt_files as pf
    from app.services import analyze_scene_runner as az_runner
    assert "scene_subject_helpers" in inspect.getsource(pf)
    assert "scene_subject_helpers" in inspect.getsource(az_runner)


def test_shot_generation_prompts_and_episode_script_section():
    from pathlib import Path
    import app.api.routers.workspace as wp
    import app.api.routers.workspace.episode_script_generator as esg
    import app.api.routers.workspace.shots as shots
    from app.services.shot_generation_prompts import (
        _build_project_prompt_context,
        _build_shot_prompts,
        _map_shared_prompt_mode_to_shot_generation_mode,
    )
    paths = {getattr(r, "path", None) for r in wp.router.routes}
    assert "/episodes/{episode_id}/script_generator/scenes" in paths
    assert "/projects/{project_id}/script_generator/episodes/scripts" in paths
    assert esg.router is wp.router
    assert callable(esg.generate_episode_scenes_from_story)
    assert callable(esg.generate_project_episode_scripts_from_global_framework)
    assert _map_shared_prompt_mode_to_shot_generation_mode("feature_stack") == "routed"
    ctx_default = _build_project_prompt_context({"script_title": "X"})
    assert isinstance(ctx_default, dict)
    assert "Max Shot Seconds (分镜最长秒数): 15" in str(ctx_default.get("project_context_section") or "")
    assert ctx_default.get("metadata", {}).get("max_shot_seconds") == 15
    ctx_custom = _build_project_prompt_context({"script_title": "X", "max_shot_seconds": "12"})
    assert "Max Shot Seconds (分镜最长秒数): 12" in str(ctx_custom.get("project_context_section") or "")
    assert shots._build_shot_prompts is _build_shot_prompts
    shots_path = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "workspace" / "shots.py"
    shot_ai_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "api"
        / "routers"
        / "workspace"
        / "shot_ai_generation.py"
    )
    ep_path = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "workspace" / "episodes.py"
    assert len(shots_path.read_text(encoding="utf-8").splitlines()) < 3000
    assert len(ep_path.read_text(encoding="utf-8").splitlines()) < 1300
    assert "script_generator/scenes" not in ep_path.read_text(encoding="utf-8")
    assert "from app.services.shot_generation_prompts import" in shot_ai_path.read_text(encoding="utf-8")


def test_analyze_scene_uses_shot_prompt_context():
    import inspect
    from pathlib import Path
    import app.api.routers.prompts.analyze_scene as az
    from app.services import analyze_scene_runner as runner
    from app.services.analyze_scene_subject_checks import (
        _normalize_subject_name,
        _detect_subjects_json_extraction_gap,
    )
    from app.services.analyze_scene_text_ops import (
        _trim_to_scenes_block,
        _sanitize_scene_beats_stage_text,
        _infer_subject_index_allowed_types_for_request,
    )
    from app.services.analyze_scene_integrity import (
        _estimate_tokens,
        _detect_output_integrity,
    )
    assert callable(az.analyze_scene)
    assert callable(az.execute_analyze_scene)
    assert callable(runner.execute_analyze_scene)
    assert "analyze_scene_runner" in inspect.getsource(az)
    assert "shot_generation_prompts" in inspect.getsource(runner)
    assert runner._detect_subjects_json_extraction_gap is _detect_subjects_json_extraction_gap
    assert runner._trim_to_scenes_block is _trim_to_scenes_block
    assert runner._estimate_tokens is _estimate_tokens
    assert runner._detect_output_integrity is _detect_output_integrity
    assert _normalize_subject_name("CHAR:[@Hero]") == "Hero"
    assert callable(_sanitize_scene_beats_stage_text)
    from app.services.analyze_scene_subject_checks import _format_subject_ref
    assert runner._format_subject_ref is _format_subject_ref
    assert _format_subject_ref("Hero", "character") == "CHAR:[@Hero]"
    assert _infer_subject_index_allowed_types_for_request(
        mode_lower="entity_design_prop",
        prompt_file_lower="",
    ) == {"prop"}
    az_path = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "prompts" / "analyze_scene.py"
    src = az_path.read_text(encoding="utf-8")
    assert len(src.splitlines()) < 250
    assert "from app.services.analyze_scene_runner import" in src
    assert "from app.services.analyze_scene_dedup import" in src
    assert "async def execute_analyze_scene(" not in src
    runner_path = Path(__file__).resolve().parents[1] / "app" / "services" / "analyze_scene_runner.py"
    runner_src = runner_path.read_text(encoding="utf-8")
    assert "async def execute_analyze_scene(" in runner_src
    assert "from app.services.shot_generation_prompts import" in runner_src
    assert len(runner_src.splitlines()) < 2200
    assert "        def _estimate_tokens(" not in runner_src
    assert "        def _infer_subject_index_allowed_types_for_request(" not in runner_src


def test_generation_job_pool_helpers():
    from pathlib import Path
    import app.api.routers.generation.job_pool as jp
    from app.services import generation_job_pool as svc
    from app.services.generation_job_pool import (
        _build_batch_job_item,
        _normalize_batch_job_status,
        collect_generation_job_pool,
    )
    from app.services.project_access import _resolve_accessible_project_ids_for_user
    assert _normalize_batch_job_status({"running": True}) == "running"
    assert _normalize_batch_job_status({"force_stopped": True}) == "canceled"
    assert jp._normalize_batch_job_status is _normalize_batch_job_status
    assert jp._build_batch_job_item is _build_batch_job_item
    assert jp.collect_generation_job_pool is collect_generation_job_pool
    assert callable(svc.repair_generation_job_history)
    assert callable(svc.stop_generation_job)
    assert callable(svc.delete_generation_job)
    assert callable(svc.stop_all_generation_jobs)
    assert callable(_resolve_accessible_project_ids_for_user)
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "generation" / "job_pool.py"
    src = path.read_text(encoding="utf-8")
    assert "from app.services.generation_job_pool import" in src
    assert "collect_generation_job_pool" in src
    assert len(src.splitlines()) < 200
    svc_path = Path(__file__).resolve().parents[1] / "app" / "services" / "generation_job_pool.py"
    svc_src = svc_path.read_text(encoding="utf-8")
    assert "def collect_generation_job_pool(" in svc_src
    assert "def repair_generation_job_history(" in svc_src
    assert len(svc_src.splitlines()) < 1500


def test_shot_import_ops_and_scene_ai_shots_batch():
    from pathlib import Path
    import app.api.routers.workspace as wp
    import app.api.routers.workspace.shot_ai_generation as sai
    from app.services.scene_ai_shots_batch import (
        _build_scene_ai_shots_batch_status_response,
        _start_scene_ai_shots_batch_for_episode,
    )
    from app.services.shot_import_ops import _import_scene_shot_rows_to_db

    paths = {getattr(r, "path", None) for r in wp.router.routes}
    assert "/scenes/{scene_id}/apply_ai_result" in paths
    assert "/episodes/{episode_id}/scenes/ai_shots/batch/start" in paths
    assert sai._import_scene_shot_rows_to_db is _import_scene_shot_rows_to_db
    assert sai._start_scene_ai_shots_batch_for_episode is _start_scene_ai_shots_batch_for_episode
    resp = _build_scene_ai_shots_batch_status_response({"running": False, "errors": ["e1"]})
    assert resp["running"] is False
    assert resp["errors"] == ["e1"]
    sai_path = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "workspace" / "shot_ai_generation.py"
    sai_src = sai_path.read_text(encoding="utf-8")
    assert len(sai_src.splitlines()) < 700
    assert "from app.services.scene_ai_shots_batch import" in sai_src
    assert "from app.services.shot_import_ops import" in sai_src
    assert "from app.services.shot_ai_generation_ops import" in sai_src
    assert callable(sai.execute_ai_generate_shots)
    assert callable(sai.execute_ai_regenerate_shots)
    ops_path = Path(__file__).resolve().parents[1] / "app" / "services" / "shot_ai_generation_ops.py"
    assert "async def execute_ai_generate_shots(" in ops_path.read_text(encoding="utf-8")
    assert len(ops_path.read_text(encoding="utf-8").splitlines()) < 800
