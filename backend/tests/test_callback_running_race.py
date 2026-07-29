# -*- coding: utf-8 -*-
"""Regression: running callback must not block / clobber a later succeeded callback."""
from __future__ import annotations

import asyncio

from app.services.generation_runtime import callbacks as cb
from app.services.generation_runtime.job_store import (
    GENERATION_CALLBACK_ASYNC_INFLIGHT,
    GENERATION_CALLBACK_ASYNC_REPROCESS,
    GENERATION_CALLBACK_STORE,
)


def _clear_callback_state() -> None:
    with cb.GENERATION_CALLBACK_LOCK:
        GENERATION_CALLBACK_STORE.clear()
    with cb.GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK:
        GENERATION_CALLBACK_ASYNC_INFLIGHT.clear()
        GENERATION_CALLBACK_ASYNC_REPROCESS.clear()


def setup_function() -> None:
    _clear_callback_state()


def teardown_function() -> None:
    _clear_callback_state()


def test_running_cannot_overwrite_succeeded_payload():
    ticket = "video-job-race-test-1"
    cb._set_generation_callback_payload(
        ticket,
        {"id": "cgt-1", "status": "succeeded", "url": "https://example.com/out.mp4"},
    )
    cb._set_generation_callback_payload(
        ticket,
        {"id": "cgt-1", "status": "running"},
    )
    stored = cb._get_generation_callback_payload(ticket)
    assert stored.get("status") == "succeeded"
    assert "example.com/out.mp4" in str(stored.get("url") or stored.get("result_url") or "")


def test_finish_inflight_consumes_reprocess_flag():
    ticket = "video-job-race-test-2"
    assert cb._mark_generation_callback_inflight(ticket) is True
    cb._mark_generation_callback_reprocess(ticket)
    assert cb._finish_generation_callback_inflight(ticket) is True
    assert ticket not in GENERATION_CALLBACK_ASYNC_INFLIGHT
    assert ticket not in GENERATION_CALLBACK_ASYNC_REPROCESS


def test_process_async_does_not_clobber_newer_store_with_stale_running(monkeypatch):
    ticket = "video-job-race-test-3"
    finalized = []

    async def _capture_finalize(ticket_arg):
        finalized.append(cb._get_generation_callback_payload(ticket_arg))

    monkeypatch.setattr(cb, "_finalize_image_jobs_from_provider_callback", _capture_finalize)
    monkeypatch.setattr(cb, "_finalize_video_jobs_from_provider_callback", _capture_finalize)

    cb._set_generation_callback_payload(
        ticket,
        {"id": "cgt-3", "status": "succeeded", "url": "https://example.com/done.mp4"},
    )
    assert cb._mark_generation_callback_inflight(ticket) is True

    asyncio.run(
        cb._process_generation_callback_async(
            ticket,
            {"id": "cgt-3", "status": "running"},
        )
    )

    stored = cb._get_generation_callback_payload(ticket)
    assert stored.get("status") == "succeeded"
    assert finalized, "expected at least one finalize pass"
    assert finalized[0].get("status") == "succeeded"


def test_reprocess_runs_after_newer_callback_during_inflight(monkeypatch):
    ticket = "video-job-race-test-4"
    finalized = []

    async def _capture_finalize(ticket_arg):
        if len(finalized) == 0:
            cb._mark_generation_callback_reprocess(ticket_arg)
            cb._set_generation_callback_payload(
                ticket_arg,
                {"id": "cgt-4", "status": "succeeded", "url": "https://example.com/late.mp4"},
            )
        finalized.append(cb._get_generation_callback_payload(ticket_arg))

    monkeypatch.setattr(cb, "_finalize_image_jobs_from_provider_callback", _capture_finalize)
    monkeypatch.setattr(cb, "_finalize_video_jobs_from_provider_callback", _capture_finalize)

    cb._set_generation_callback_payload(ticket, {"id": "cgt-4", "status": "failed", "error": "temp"})
    assert cb._mark_generation_callback_inflight(ticket) is True

    asyncio.run(
        cb._process_generation_callback_async(
            ticket,
            {"id": "cgt-4", "status": "failed", "error": "temp"},
        )
    )

    assert len(finalized) == 2
    assert finalized[1].get("status") == "succeeded"
    assert ticket not in GENERATION_CALLBACK_ASYNC_INFLIGHT
    assert ticket not in GENERATION_CALLBACK_ASYNC_REPROCESS
