# -*- coding: utf-8 -*-
"""User / auth Pydantic schemas and active-level helpers."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


EMAIL_VERIFICATION_TRIAL_CREDITS = 500

USER_ACTIVE_LEVEL_DEFAULT = 1
USER_ACTIVE_LEVEL_MAX = 12
USER_PARALLEL_LIMIT_BONUS = 2
USER_PARALLEL_LIMIT_MAX = USER_ACTIVE_LEVEL_MAX + USER_PARALLEL_LIMIT_BONUS
# Backward-compatible aliases
USER_BATCH_PARALLEL_LIMIT_MAX = USER_ACTIVE_LEVEL_MAX
USER_MEDIA_GENERATION_PARALLEL_BONUS = USER_PARALLEL_LIMIT_BONUS
USER_MEDIA_GENERATION_PARALLEL_LIMIT_MAX = USER_PARALLEL_LIMIT_MAX


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    homepage_referral_token: Optional[str] = None


class EmailVerificationSendRequest(BaseModel):
    email: str


class EmailVerificationConfirmRequest(BaseModel):
    email: str
    code: str


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: int
    account_status: int = 1
    email_verified: bool = False
    is_superuser: bool
    is_authorized: bool = False
    is_system: bool
    credits: Optional[int] = 0

    class Config:
        from_attributes = True


class UserPageOut(BaseModel):
    items: List[UserOut]
    total: int
    page: int
    page_size: int


class Token(BaseModel):
    access_token: str
    token_type: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[int] = None
    account_status: Optional[int] = None
    email_verified: Optional[bool] = None
    is_authorized: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_system: Optional[bool] = None
    password: Optional[str] = None


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str


def normalize_user_active_level(value: Any, default: int = USER_ACTIVE_LEVEL_DEFAULT) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(0, parsed)


def is_user_enabled(value: Any) -> bool:
    return normalize_user_active_level(value, USER_ACTIVE_LEVEL_DEFAULT) > 0


def resolve_user_active_level(value: Any, default: int = USER_ACTIVE_LEVEL_DEFAULT) -> int:
    """Clamp raw is_active to 1..USER_ACTIVE_LEVEL_MAX (no +2 bonus)."""
    normalized = normalize_user_active_level(value, default)
    if normalized <= 0:
        normalized = max(1, int(default or USER_ACTIVE_LEVEL_DEFAULT))
    return min(USER_ACTIVE_LEVEL_MAX, max(1, normalized))


def resolve_user_batch_parallel_limit(value: Any, default: int = USER_ACTIVE_LEVEL_DEFAULT) -> int:
    """Batch + media parallel cap: is_active + 2 (clamped to USER_PARALLEL_LIMIT_MAX)."""
    active_level = resolve_user_active_level(value, default)
    return min(USER_PARALLEL_LIMIT_MAX, max(1, int(active_level) + int(USER_PARALLEL_LIMIT_BONUS)))


def resolve_user_media_generation_parallel_limit(value: Any, default: int = USER_ACTIVE_LEVEL_DEFAULT) -> int:
    """Image/video submit parallel cap — same as batch: is_active + 2."""
    return resolve_user_batch_parallel_limit(value, default)
