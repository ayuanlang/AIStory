# -*- coding: utf-8 -*-
"""Project asset review thread / round / message API schemas."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ProjectAssetReviewThreadCreate(BaseModel):
    reviewer_user_id: Optional[int] = None
    reviewer_user: Optional[str] = None
    title: Optional[str] = None
    request_message: Optional[str] = None
    scope_type: Optional[str] = "all_current"
    entity_required: Optional[bool] = True
    shot_required: Optional[bool] = True
    entity_ids: Optional[List[int]] = None
    shot_ids: Optional[List[int]] = None
    due_at: Optional[str] = None


class ProjectAssetReviewThreadOut(BaseModel):
    id: int
    project_id: int
    requester_user_id: int
    requester_username: Optional[str] = None
    reviewer_user_id: int
    reviewer_username: Optional[str] = None
    title: Optional[str] = None
    status: str
    latest_round_no: int
    latest_activity_at: Optional[str] = None
    has_unread: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectAssetReviewThreadStatusUpdate(BaseModel):
    status: str


class ProjectAssetReviewThreadReadUpdate(BaseModel):
    read: bool = True


class ProjectAssetReviewRoundCreate(BaseModel):
    request_message: Optional[str] = None
    scope_type: Optional[str] = "all_current"
    entity_required: Optional[bool] = True
    shot_required: Optional[bool] = True
    entity_ids: Optional[List[int]] = None
    shot_ids: Optional[List[int]] = None
    due_at: Optional[str] = None


class ProjectAssetReviewRoundOut(BaseModel):
    id: int
    thread_id: int
    round_no: int
    initiated_by_user_id: int
    initiated_by_username: Optional[str] = None
    request_message: Optional[str] = None
    scope_type: str
    entity_required: bool
    shot_required: bool
    entity_decision: str
    shot_decision: str
    overall_status: str
    entity_feedback: Optional[str] = None
    shot_feedback: Optional[str] = None
    due_at: Optional[str] = None
    selected_entity_ids: List[int] = []
    selected_shot_ids: List[int] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None


class ProjectAssetReviewMessageCreate(BaseModel):
    message_text: Optional[str] = None
    message_type: Optional[str] = "message"
    entity_decision: Optional[str] = None
    shot_decision: Optional[str] = None
    entity_feedback: Optional[str] = None
    shot_feedback: Optional[str] = None


class ProjectAssetReviewMessageOut(BaseModel):
    id: int
    round_id: int
    sender_user_id: int
    sender_username: Optional[str] = None
    sender_role: str
    message_type: str
    message_text: Optional[str] = None
    entity_decision: Optional[str] = None
    shot_decision: Optional[str] = None
    entity_feedback: Optional[str] = None
    shot_feedback: Optional[str] = None
    created_at: Optional[str] = None
