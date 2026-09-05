import asyncio
from datetime import timedelta

import httpx
import pytest

from app.core.time_utils import now_bj
from app.services.analyze_scene_dedup import _await_analyze_scene_segment
from app.services.llm_service import (
    is_llm_timeout_error,
    is_stale_llm_request_timestamp,
)


def test_is_llm_timeout_error_detects_transport_and_message():
    assert is_llm_timeout_error(httpx.ReadTimeout("LLM stream exceeded wall-clock timeout (900s)"))
    assert is_llm_timeout_error(TimeoutError("LLM call timed out after 900s"))
    assert is_llm_timeout_error(Exception("vendor failed: Read timeout: idle"))
    assert not is_llm_timeout_error(Exception("upstream 500"))


def test_finalize_stale_pipeline_nodes_skips_wait_env_inside_budget():
    from types import SimpleNamespace
    from app.core.time_utils import now_bj
    from app.services.script_analysis_flow import finalize_stale_pipeline_nodes

    wait_ts = (now_bj() - timedelta(seconds=1000)).isoformat(timespec="microseconds")
    row = SimpleNamespace(
        status="running",
        node_name="scene_subskill_scene",
        episode_id=1,
        updated_at=wait_ts,
        started_at=wait_ts,
        created_at=wait_ts,
        runtime_meta={"current_step": "wait_env"},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return [row]

    class _Session:
        committed = False

        def query(self, *_args, **_kwargs):
            return _Query()

        def commit(self):
            self.committed = True

    assert finalize_stale_pipeline_nodes(_Session(), episode_id=1, timeout_seconds=900) == 0
    assert row.status == "running"


def test_finalize_stale_pipeline_nodes_skips_coordinator_with_fresh_child():
    from types import SimpleNamespace
    from app.core.time_utils import now_bj
    from app.services.script_analysis_flow import finalize_stale_pipeline_nodes

    now = now_bj()
    parent_ts = (now - timedelta(seconds=1200)).isoformat(timespec="microseconds")
    child_ts = (now - timedelta(seconds=10)).isoformat(timespec="microseconds")
    parent = SimpleNamespace(
        status="running",
        node_name="scene_subskill_pipeline",
        episode_id=1,
        updated_at=parent_ts,
        started_at=parent_ts,
        created_at=parent_ts,
        runtime_meta={},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
    )
    child = SimpleNamespace(
        status="running",
        node_name="scene_subskill_scene",
        episode_id=1,
        updated_at=child_ts,
        started_at=child_ts,
        created_at=child_ts,
        runtime_meta={"current_step": "combat"},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return [parent, child]

    class _Session:
        committed = False

        def query(self, *_args, **_kwargs):
            return _Query()

        def commit(self):
            self.committed = True

    assert finalize_stale_pipeline_nodes(_Session(), episode_id=1, timeout_seconds=900) == 0
    assert parent.status == "running"
    assert child.status == "running"


def test_finalize_stale_pipeline_nodes_marks_old_running_row():
    from types import SimpleNamespace
    from app.core.time_utils import now_bj
    from app.services.script_analysis_flow import finalize_stale_pipeline_nodes

    stale_ts = (now_bj() - timedelta(seconds=1200)).isoformat(timespec="microseconds")
    row = SimpleNamespace(
        status="running",
        updated_at=stale_ts,
        started_at=stale_ts,
        created_at=stale_ts,
        runtime_meta={"current_step": "staging"},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return [row]

    class _Session:
        committed = False

        def query(self, *_args, **_kwargs):
            return _Query()

        def commit(self):
            self.committed = True

    session = _Session()
    assert finalize_stale_pipeline_nodes(session, episode_id=1, timeout_seconds=900) == 1
    assert row.status == "failed"
    assert row.last_error_code == "NODE_TIMEOUT"
    assert session.committed is True


def test_mark_storyboard_generation_applied_writes_scene_and_episode_success(monkeypatch):
    from types import SimpleNamespace
    from app.services import script_analysis_flow as flow

    calls = []

    def _upsert(_db, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(flow, "upsert_pipeline_node_status", _upsert)
    monkeypatch.setattr(
        flow,
        "_episode_workspace_storyboard_coverage",
        lambda *_args, **_kwargs: {"scene_count": 1, "with_shots": 1, "ok": True, "no_scenes": False},
    )
    flow.mark_storyboard_generation_applied(
        object(),
        project_id=9,
        episode_id=3,
        scene=SimpleNamespace(id=11, scene_no="EP01_SC02"),
        shot_count=8,
    )
    assert [row.get("scene_id") for row in calls] == ["EP01_SC02", None]
    assert all(row["status"] == "success" for row in calls)
    assert all(row["node_name"] == "storyboard_generation" for row in calls)


def test_mark_storyboard_generation_applied_canonicalizes_numeric_scene_no(monkeypatch):
    from types import SimpleNamespace
    from app.services import script_analysis_flow as flow

    calls = []

    def _upsert(_db, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(**kwargs)

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class _Session:
        def query(self, *_args, **_kwargs):
            return _Query()

    monkeypatch.setattr(flow, "upsert_pipeline_node_status", _upsert)
    monkeypatch.setattr(
        flow,
        "_episode_workspace_storyboard_coverage",
        lambda *_args, **_kwargs: {"scene_count": 1, "with_shots": 1, "ok": True, "no_scenes": False},
    )
    flow.mark_storyboard_generation_applied(
        _Session(),
        project_id=9,
        episode_id=5,
        scene=SimpleNamespace(id=11, scene_no="1"),
        shot_count=4,
    )
    assert [row.get("scene_id") for row in calls] == ["EP01_SC01", None]


def test_finalize_stale_pipeline_nodes_closes_per_scene_storyboard_when_that_scene_has_shots(monkeypatch):
    from types import SimpleNamespace
    from app.core.time_utils import now_bj
    from app.services import script_analysis_flow as flow

    stale_ts = (now_bj() - timedelta(seconds=1200)).isoformat(timespec="microseconds")
    row = SimpleNamespace(
        status="running",
        node_name="storyboard_generation",
        episode_id=1,
        scene_id="EP01_SC01",
        updated_at=stale_ts,
        started_at=stale_ts,
        created_at=stale_ts,
        runtime_meta={},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return [row]

    class _Session:
        committed = False

        def query(self, *_args, **_kwargs):
            return _Query()

        def commit(self):
            self.committed = True

    monkeypatch.setattr(flow, "_workspace_scene_has_shots", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        flow,
        "_episode_workspace_storyboard_coverage",
        lambda *_args, **_kwargs: {"scene_count": 2, "with_shots": 1, "ok": False, "no_scenes": False},
    )
    session = _Session()
    assert flow.finalize_stale_pipeline_nodes(session, episode_id=1, timeout_seconds=900) == 1
    assert row.status == "success"
    assert row.last_error_code is None
    assert session.committed is True


def test_finalize_stale_pipeline_nodes_closes_storyboard_when_shots_exist(monkeypatch):
    from types import SimpleNamespace
    from app.core.time_utils import now_bj
    from app.services import script_analysis_flow as flow

    stale_ts = (now_bj() - timedelta(seconds=1200)).isoformat(timespec="microseconds")
    row = SimpleNamespace(
        status="queued",
        node_name="storyboard_generation",
        episode_id=1,
        updated_at=stale_ts,
        started_at=stale_ts,
        created_at=stale_ts,
        runtime_meta={},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return [row]

    class _Session:
        committed = False

        def query(self, *_args, **_kwargs):
            return _Query()

        def commit(self):
            self.committed = True

    monkeypatch.setattr(
        flow,
        "_episode_workspace_storyboard_coverage",
        lambda *_args, **_kwargs: {"scene_count": 1, "with_shots": 1, "ok": True, "no_scenes": False},
    )
    session = _Session()
    assert flow.finalize_stale_pipeline_nodes(session, episode_id=1, timeout_seconds=900) == 1
    assert row.status == "success"
    assert row.last_error_code is None
    assert session.committed is True


def test_finalize_stale_pipeline_nodes_keeps_queued_storyboard_placeholder():
    from types import SimpleNamespace
    from app.core.time_utils import now_bj
    from app.services.script_analysis_flow import finalize_stale_pipeline_nodes

    stale_ts = (now_bj() - timedelta(seconds=1200)).isoformat(timespec="microseconds")
    row = SimpleNamespace(
        status="queued",
        node_name="storyboard_generation",
        episode_id=1,
        updated_at=stale_ts,
        started_at=stale_ts,
        created_at=stale_ts,
        runtime_meta={},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return [row]

    class _Session:
        committed = False

        def query(self, *_args, **_kwargs):
            return _Query()

        def commit(self):
            self.committed = True

    session = _Session()
    assert finalize_stale_pipeline_nodes(session, episode_id=1, timeout_seconds=900) == 0
    assert row.status == "queued"
    assert session.committed is False


def test_is_stale_llm_request_timestamp_uses_beijing_clock():
    now = now_bj()
    fresh = (now - timedelta(seconds=60)).isoformat(timespec="microseconds")
    stale = (now - timedelta(seconds=1200)).isoformat(timespec="microseconds")
    assert is_stale_llm_request_timestamp(fresh, 900, now=now) is False
    assert is_stale_llm_request_timestamp(stale, 900, now=now) is True
    assert is_stale_llm_request_timestamp("", 900, now=now) is False


def test_await_analyze_scene_segment_hard_cancels_hanging_call(monkeypatch):
    import app.services.analyze_scene_dedup as dedup

    monkeypatch.setattr(dedup, "_ANALYZE_SCENE_SEGMENT_HARD_TIMEOUT_SECONDS", 0.2)

    cancelled = {"done": False}

    async def _hang(_messages, _config):
        try:
            await asyncio.sleep(30)
            return {"content": "should-not-return", "finish_reason": "stop"}
        except asyncio.CancelledError:
            cancelled["done"] = True
            raise

    monkeypatch.setattr(dedup.llm_service, "chat_completion_with_fallback", _hang)

    async def _run():
        with pytest.raises(TimeoutError, match="timed out after"):
            await _await_analyze_scene_segment(
                [{"role": "user", "content": "ping"}],
                {"provider": "grsai", "model": "gemini-2.5-pro"},
            )
        await asyncio.sleep(0)

    asyncio.run(_run())
    assert cancelled["done"] is True
