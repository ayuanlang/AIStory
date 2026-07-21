# -*- coding: utf-8 -*-
from pathlib import Path


def test_job_store_singleton_and_setters():
    from app.services.generation_runtime import job_store as js
    assert isinstance(js.IMAGE_JOB_STORE, dict)
    assert callable(js._set_image_job)
    assert callable(js._set_video_job)


def test_media_persist_and_billing_exports():
    from app.services.generation_runtime import media_persist as mp
    from app.services.generation_runtime import video_job_billing as vjb
    assert callable(mp._persist_remote_image_result)
    assert callable(vjb._persist_video_job_billing_reservation)
    assert callable(vjb._settle_or_cancel_video_job_billing_from_callback)


def test_queue_worker_callbacks_prompt_cost():
    from app.services.generation_runtime.queue_worker import start_generation_queue_worker, _queue_runtime_config
    from app.services.generation_runtime import callbacks as cb
    from app.services.prompt_resolve import _resolve_prompt_text, _PROMPT_SKILL_ALIAS
    from app.services.project_cost_estimation import _compute_project_cost_estimation_snapshot
    from app.services.soft_delete import _active_episode_clause
    assert callable(start_generation_queue_worker)
    assert isinstance(_queue_runtime_config(), dict)
    assert callable(cb._process_generation_callback_async)
    assert "scene_analysis.txt" in _PROMPT_SKILL_ALIAS
    assert callable(_resolve_prompt_text)
    assert callable(_compute_project_cost_estimation_snapshot)
    assert _active_episode_clause() is not None


def test_new_routers_and_slim_endpoints():
    from app.api.routers.admin_queue import router as aq
    from app.api.routers.tasks import router as tasks
    from app.api.routers.settings_effective import router as se
    import app.api.endpoints as ep
    aq_paths = {getattr(r, "path", None) for r in aq.routes}
    assert "/admin/queue/tasks" in aq_paths
    assert "/tasks/{task_id}" in {getattr(r, "path", None) for r in tasks.routes}
    assert "/settings/effective" in {getattr(r, "path", None) for r in se.routes}
    text = Path(ep.__file__).read_text(encoding="utf-8")
    assert text.count("\n") < 800
    assert "IMAGE_JOB_STORE: Dict" not in text
    assert hasattr(ep, "start_generation_queue_worker")


def test_main_still_boots():
    from app.main import app
    paths = {getattr(r, "path", None) for r in app.routes}
    for p in [
        "/api/v1/generate/image",
        "/api/v1/admin/queue/tasks",
        "/api/v1/tasks/{task_id}",
        "/api/v1/settings/effective",
        "/api/v1/billing/recharge/plans",
        "/api/v1/analyze_scene",
    ]:
        assert p in paths
