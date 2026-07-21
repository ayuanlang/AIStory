# -*- coding: utf-8 -*-
"""Queue / callback status machine guards."""

from datetime import datetime, timedelta, timezone


def test_job_is_callback_waiting_ignores_stale_pending_on_success():
    from app.services.generation_runtime.job_store import _job_is_callback_waiting

    assert _job_is_callback_waiting(
        {
            "status": "succeeded",
            "upstream_submit_state": "callback_pending",
            "finished_at": "2026-07-21T16:52:33+08:00",
        }
    ) is False
    assert _job_is_callback_waiting(
        {
            "status": "waiting_callback",
            "upstream_submit_state": "callback_pending",
        }
    ) is True


def test_naive_beijing_timestamp_not_inflated_by_eight_hours():
    from app.services.generation_runtime.job_store import _parse_iso_datetime, _seconds_since_iso_timestamp

    bj = timezone(timedelta(hours=8))
    wall = datetime.now(bj).replace(tzinfo=None) - timedelta(seconds=120)
    naive_bj_iso = wall.isoformat(timespec="seconds")
    elapsed = _seconds_since_iso_timestamp(naive_bj_iso)
    assert elapsed is not None
    assert 60 <= elapsed <= 300, elapsed
    parsed = _parse_iso_datetime(naive_bj_iso)
    assert parsed is not None


def test_callback_wait_elapsed_ignores_created_at():
    from app.services.generation_runtime.job_store import _job_callback_wait_elapsed_seconds
    from app.core.time_utils import now_bj_iso

    old = "2026-07-20T12:00:00+08:00"
    job = {
        "created_at": old,
        "started_at": None,
        "callback_retry_at": None,
    }
    assert _job_callback_wait_elapsed_seconds(job) is None

    job["started_at"] = now_bj_iso()
    elapsed = _job_callback_wait_elapsed_seconds(job)
    assert elapsed is not None
    assert elapsed < 60


def test_job_has_success_result():
    from app.services.generation_runtime.job_store import _job_has_success_result

    assert _job_has_success_result({"status": "waiting_callback", "result": {"url": "https://cdn.example/a.png"}})
    assert _job_has_success_result({"status": "failed", "error": "callback wait exhausted", "result": {"url": "/uploads/a.png"}})
    assert not _job_has_success_result({"status": "waiting_callback", "result": None})


def test_job_subject_to_timeout_excludes_succeeded_with_stale_pending():
    from app.api.routers.generation.shared import _job_is_subject_to_running_timeout

    assert _job_is_subject_to_running_timeout(
        {
            "status": "succeeded",
            "upstream_submit_state": "callback_pending",
            "started_at": "2026-07-21T16:43:16+08:00",
        }
    ) is False
