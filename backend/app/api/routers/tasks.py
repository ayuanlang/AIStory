# -*- coding: utf-8 -*-
"""Generic async task poll/cancel routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models.all_models import User
from app.services.generation_runtime.queue_worker import (
    _cancel_generation_task_ref,
    _generation_task_status,
)
from app.services.task_manager import cancel as _cancel_task
from app.services.task_manager import get_status as _get_task_status

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}")
def poll_task(task_id: str, current_user: User = Depends(get_current_user)):
    info = _get_task_status(task_id, user_id=current_user.id)
    if info is None:
        info = _generation_task_status(task_id, user_id=current_user.id)
    if info is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return info


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, current_user: User = Depends(get_current_user)):
    _cancel_generation_task_ref(task_id, user_id=current_user.id, reason="Task canceled by user request")
    info = _cancel_task(task_id, user_id=current_user.id, reason="Task canceled by user request")
    if info is None:
        info = _generation_task_status(task_id, user_id=current_user.id)
    if info is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return info
