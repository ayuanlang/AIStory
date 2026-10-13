# -*- coding: utf-8 -*-
"""Video submit must not start a second provider task for an in-flight shot."""

from app.services.generation_task_queue import generation_scope_owner_blocks_status
from app.services.video_submit_dedup import video_scope_reservation_is_active


def test_waiting_callback_scope_stays_reserved():
    assert video_scope_reservation_is_active({"status": "waiting_callback", "job_id": "a"})
    assert video_scope_reservation_is_active({"status": "queued", "job_id": "a"})
    assert video_scope_reservation_is_active({"status": "submit", "job_id": "a"})
    assert video_scope_reservation_is_active({"job_id": "placeholder"})


def test_terminal_and_missing_scope_can_be_released():
    assert video_scope_reservation_is_active({"status": "succeeded", "job_id": "a"}) is False
    assert video_scope_reservation_is_active({"status": "failed", "job_id": "a"}) is False
    assert video_scope_reservation_is_active({"status": "canceled", "job_id": "a"}) is False
    assert video_scope_reservation_is_active(None) is False
    assert video_scope_reservation_is_active({}) is False


def test_queue_waiting_callback_blocks_a_second_submit():
    assert generation_scope_owner_blocks_status(
        queue_status="waiting_callback",
        state_status="waiting_callback",
        age_seconds=5,
    )


def test_claim_without_queue_row_only_blocks_during_reserve():
    assert generation_scope_owner_blocks_status(
        queue_status="",
        state_status="queued",
        age_seconds=1,
    )
    assert generation_scope_owner_blocks_status(
        queue_status="",
        state_status="queued",
        age_seconds=120,
    ) is False


def test_finished_queue_row_does_not_block_regenerate():
    assert generation_scope_owner_blocks_status(
        queue_status="completed",
        state_status="succeeded",
        age_seconds=2,
    ) is False
