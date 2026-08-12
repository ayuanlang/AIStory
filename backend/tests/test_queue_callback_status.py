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


def test_poll_mode_submit_job_is_not_callback_waiting():
    """Local Grsai poll keeps status=submit without callback_pending; must not be exhausted."""
    from app.core.time_utils import now_bj_iso
    from app.services.generation_runtime.job_store import _job_is_callback_waiting

    assert _job_is_callback_waiting(
        {
            "status": "submit",
            "started_at": now_bj_iso(),
            "upstream_submit_state": None,
        }
    ) is False
    assert _job_is_callback_waiting(
        {
            "status": "running",
            "started_at": now_bj_iso(),
            "upstream_submit_state": "submitted",
        }
    ) is False
    assert _job_is_callback_waiting(
        {
            "status": "submit",
            "upstream_submit_state": "callback_pending",
        }
    ) is True


def test_normalize_keeps_queued_distinct_from_running():
    from app.services.generation_runtime.callbacks import _normalize_generation_status

    assert _normalize_generation_status("queued") == "queued"
    assert _normalize_generation_status("running") == "running"
    assert _normalize_generation_status("pending") == "running"


def test_normalize_kie_fail_state_is_terminal_failed():
    """KIE playground callbacks use state=fail (not failed); must finalize as failed."""
    from app.services.generation_runtime.callbacks import (
        _extract_callback_status,
        _get_generation_callback_payload,
        _normalize_generation_status,
        _set_generation_callback_payload_for_ack,
    )

    assert _normalize_generation_status("fail") == "failed"
    assert _normalize_generation_status("failure") == "failed"

    payload = {
        "code": 500,
        "msg": "generate playground failed, task id is blank",
        "data": {
            "state": "fail",
            "taskId": "231901276a7a14814496b2be8c410fb4",
            "model": "minimax-h3/image-to-video",
        },
    }
    assert _normalize_generation_status(_extract_callback_status(payload)) == "failed"

    ticket = "video-job-kie-fail-status-test"
    _set_generation_callback_payload_for_ack(ticket, payload)
    normalized = _get_generation_callback_payload(ticket)
    assert normalized.get("status") == "failed"
    assert "generate playground failed" in str(normalized.get("error") or "")


def test_queued_job_not_subject_to_running_timeout():
    from app.services.generation_runtime.job_timeout import _job_is_subject_to_running_timeout

    assert _job_is_subject_to_running_timeout(
        {
            "status": "queued",
            "created_at": "2026-07-21T16:43:16+08:00",
            "provider_callback_ticket": "image-job-abc",
        }
    ) is False


def test_naive_beijing_timestamp_not_inflated_by_eight_hours():
    from app.services.generation_runtime.job_store import _parse_iso_datetime, _seconds_since_iso_timestamp

    tz = timezone(timedelta(hours=8))
    wall = datetime.now(tz).replace(tzinfo=None) - timedelta(seconds=120)
    naive_bj_iso = wall.isoformat(timespec="seconds")
    elapsed = _seconds_since_iso_timestamp(naive_bj_iso)
    assert elapsed is not None
    assert 60 <= elapsed <= 300, elapsed
    parsed = _parse_iso_datetime(naive_bj_iso)
    assert parsed is not None


def test_callback_wait_elapsed_ignores_created_at():
    from app.services.generation_runtime.job_store import _job_callback_wait_elapsed_seconds
    from app.core.time_utils import now_bj_iso

    old = "2026-07-21T12:00:00.000+08:00"
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


def test_job_is_subject_to_timeout_excludes_succeeded_with_stale_pending():
    from app.api.routers.generation.shared import _job_is_subject_to_running_timeout

    assert _job_is_subject_to_running_timeout(
        {
            "status": "succeeded",
            "upstream_submit_state": "callback_pending",
            "started_at": "2026-07-21T16:43:16+08:00",
        }
    ) is False


def test_set_image_job_heals_false_exhaust_on_success():
    from app.services.generation_runtime.job_store import (
        IMAGE_JOB_LOCK,
        IMAGE_JOB_STORE,
        _set_image_job,
    )

    job_id = "test-heal-false-exhaust"
    with IMAGE_JOB_LOCK:
        IMAGE_JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "failed",
            "error": "image job callback wait exhausted after 28859s (retries=1/1, limit=900s)",
            "upstream_submit_state": "callback_wait_exhausted",
            "callback_submit_retries": 1,
            "callback_retry_at": "2026-07-21T23:53:38.961024+08:00",
        }

    _set_image_job(job_id, status="succeeded", finished_at="2026-07-21T23:56:05+08:00")

    with IMAGE_JOB_LOCK:
        healed = dict(IMAGE_JOB_STORE.pop(job_id, {}) or {})

    assert healed.get("status") == "succeeded"
    assert healed.get("upstream_submit_state") == "completed"
    assert healed.get("error") in (None, "")
    assert int(healed.get("callback_submit_retries") or 0) == 0
    assert healed.get("callback_retry_at") is None
