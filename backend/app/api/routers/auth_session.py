# -*- coding: utf-8 -*-
"""Register / login / password routes for auth router."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import cache_user_identity, get_current_user
from app.core.config import settings
from app.core.homepage_referral import parse_homepage_referral_token
from app.db.session import get_db
from app.models.all_models import User
from app.schemas.user_auth import (
    EMAIL_VERIFICATION_TRIAL_CREDITS,
    USER_ACTIVE_LEVEL_DEFAULT,
    EmailVerificationConfirmRequest,
    EmailVerificationSendRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserOut,
    is_user_enabled,
    normalize_user_active_level,
)
from app.services.auth_email import (
    _generate_email_verification_code,
    _is_valid_email_format,
    _resolve_runtime_smtp_config,
    send_email_verification_code,
    send_password_reset_email,
    send_welcome_trial_credits_email,
)
from app.services.auth_login import (
    _describe_login_identifier,
    _get_request_client_ip,
    _log_login_is_active_diagnostics,
    _log_login_stage,
    _should_block_login_for_maintenance,
    authenticate_user,
)
from app.services.auth_security import (
    create_access_token,
    create_password_reset_token,
    get_password_hash,
    verify_password_reset_token,
)
from app.services.system_log_service import log_action

logger = logging.getLogger("api_logger")
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["auth"])


def _seed_default_system_settings_for_user_lazy(db, user_id: int) -> None:
    from app.api.endpoints import _seed_default_system_settings_for_user
    return _seed_default_system_settings_for_user(db, user_id)

@router.post("/users/", response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    normalized_email = (user.email or "").strip().lower()
    if not _is_valid_email_format(normalized_email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    homepage_referral: Dict[str, Any] = {}
    referral_token = str(user.homepage_referral_token or "").strip()
    if referral_token:
        try:
            parsed_referral = parse_homepage_referral_token(referral_token, settings.SECRET_KEY)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid homepage referral token")

        inviter_user = db.query(User).filter(User.id == int(parsed_referral["inviter_user_id"])).first()
        if not inviter_user:
            raise HTTPException(status_code=400, detail="Homepage referral inviter not found")

        homepage_referral = {
            "channel": "homepage_link",
            "token_version": int(parsed_referral.get("token_version") or 1),
            "inviter_user_id": int(parsed_referral["inviter_user_id"]),
            "issued_at": str(parsed_referral.get("issued_at") or ""),
            "masked_user_id": str(parsed_referral.get("masked_user_id") or ""),
            "registered_at": datetime.utcnow().isoformat(),
        }

    db_user_email = db.query(User).filter(User.email == normalized_email).first()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user_username = db.query(User).filter(User.username == user.username).first()
    if db_user_username:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = get_password_hash(user.password)
    verify_code = _generate_email_verification_code()
    expire_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    db_user = User(
        email=normalized_email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password,
        is_active=0,
        account_status=-1,
        email_verified=False,
        email_verification_code=verify_code,
        email_verification_expires_at=expire_at,
        preferences={"homepage_referral": homepage_referral} if homepage_referral else {},
    )
    db.add(db_user)
    db.flush()
    _seed_default_system_settings_for_user_lazy(db, db_user.id)
    db.commit()
    db.refresh(db_user)
    try:
        send_email_verification_code(normalized_email, verify_code)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", normalized_email, e)
    return db_user


@router.post("/users/verification/send")
@limiter.limit(settings.RATE_LIMIT_RESET)
def send_user_verification_code(
    request: Request,
    payload: EmailVerificationSendRequest,
    db: Session = Depends(get_db),
):
    email = (payload.email or "").strip().lower()
    if not _is_valid_email_format(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    code = _generate_email_verification_code()
    user.email_verification_code = code
    user.email_verification_expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    db.commit()
    try:
        send_email_verification_code(email, code)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", email, e)
        raise HTTPException(status_code=500, detail="Failed to send verification code")
    return {"status": "ok", "message": "Verification code sent"}


@router.post("/users/verification/confirm", response_model=UserOut)
@limiter.limit(settings.RATE_LIMIT_RESET)
def confirm_user_verification_code(
    request: Request,
    payload: EmailVerificationConfirmRequest,
    db: Session = Depends(get_db),
):
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code are required")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_verified and user.account_status == 1:
        return user

    if not user.email_verification_code or user.email_verification_code != code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    try:
        expire_at = datetime.fromisoformat(str(user.email_verification_expires_at or ""))
    except Exception:
        expire_at = None
    if not expire_at or datetime.utcnow() > expire_at:
        raise HTTPException(status_code=400, detail="Verification code expired")

    old_credits = int(user.credits or 0)
    target_credits = int(EMAIL_VERIFICATION_TRIAL_CREDITS)
    granted_credits = max(0, target_credits - old_credits)
    if granted_credits > 0:
        user.credits = old_credits + granted_credits
        trans = TransactionHistory(
            user_id=user.id,
            amount=granted_credits,
            balance_after=int(user.credits or 0),
            description="signup_bonus", 
            details={
                "task_type": "signup_bonus", "provider": "system", "model": "email_verification",
                "reason": "email_verification_trial_bonus",
                "target_credits": target_credits,
                "old_credits": old_credits,
            },
        )
        db.add(trans)

    user.email_verified = True
    user.account_status = 1
    user.is_active = USER_ACTIVE_LEVEL_DEFAULT
    user.email_verification_code = None
    user.email_verification_expires_at = None
    db.commit()
    db.refresh(user)
    _refresh_user_identity_cache(user)

    try:
        if granted_credits > 0:
            send_welcome_trial_credits_email(email)
    except Exception as e:
        logger.error("Failed to send trial credits welcome email to %s: %s", email, e)

    return user





@router.post("/login/access-token", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Requires 'username' and 'password' as form fields.
    """
    request_started_at = time.perf_counter()
    login_identifier = _describe_login_identifier(form_data.username)
    client_ip = _get_request_client_ip(request)
    _log_login_stage(
        logging.INFO,
        "[login] access-token request start",
        identifier=login_identifier,
        client_ip=client_ip,
        path=str(getattr(request, "url", "") or ""),
    )
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        _log_login_stage(
            logging.WARNING,
            "[login] access-token rejected: invalid credentials",
            identifier=login_identifier,
            client_ip=client_ip,
            elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    _log_login_is_active_diagnostics(db, user, login_identifier, "access-token-authenticated")
    if _should_block_login_for_maintenance(
        db,
        user,
        login_identifier=login_identifier,
        client_ip=client_ip,
        request_started_at=request_started_at,
        flow_name="access-token",
    ):
        _log_login_stage(
            logging.WARNING,
            "[login] access-token rejected: maintenance mode",
            identifier=login_identifier,
            client_ip=client_ip,
            user_id=user.id,
            elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
        )
        raise HTTPException(status_code=403, detail="System is under maintenance. Only system administrators can login now")
    if (
        user.account_status == -1
        and (not is_user_enabled(user.is_active))
        and (not bool(getattr(user, "is_superuser", False)))
    ):
        _log_login_stage(
            logging.WARNING,
            "[login] access-token rejected: email verification required",
            identifier=login_identifier,
            client_ip=client_ip,
            user_id=user.id,
            elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
        )
        raise HTTPException(status_code=403, detail="Email verification required. Please verify your email code before login")
    if not is_user_enabled(user.is_active):
        _log_login_stage(
            logging.WARNING,
            "[login] access-token rejected: user disabled",
            identifier=login_identifier,
            client_ip=client_ip,
            user_id=user.id,
            elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
        )
        raise HTTPException(status_code=403, detail="User is disabled")

    try:
        seed_started_at = time.perf_counter()
        _log_login_stage(logging.INFO, "[login] seeding default settings start", user_id=user.id, identifier=login_identifier)
        _seed_default_system_settings_for_user_lazy(db, user.id)
        db.commit()
        _log_login_stage(
            logging.INFO,
            "[login] seeding default settings finished",
            user_id=user.id,
            identifier=login_identifier,
            elapsed_ms=int((time.perf_counter() - seed_started_at) * 1000),
        )
    except Exception as e:
        db.rollback()
        logger.exception(
            "Failed to seed default API settings on login | user_id=%s identifier=%s elapsed_ms=%s error=%s",
            user.id,
            login_identifier,
            int((time.perf_counter() - request_started_at) * 1000),
            e,
        )
    
    # Log Successful Login
    audit_started_at = time.perf_counter()
    _log_login_stage(logging.INFO, "[login] audit log write start", user_id=user.id, identifier=login_identifier)
    log_action(db, user_id=user.id, user_name=user.username, action="LOGIN", details="User logged in via OAuth2 Form")
    _log_login_stage(
        logging.INFO,
        "[login] audit log write finished",
        user_id=user.id,
        identifier=login_identifier,
        elapsed_ms=int((time.perf_counter() - audit_started_at) * 1000),
    )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    cache_user_identity(user)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "uid": user.id,
            "pv": 1,
            "uname": user.username,
            "email": getattr(user, "email", None),
            "full_name": getattr(user, "full_name", None),
            "avatar_url": getattr(user, "avatar_url", None),
            "is_active": normalize_user_active_level(getattr(user, "is_active", USER_ACTIVE_LEVEL_DEFAULT), USER_ACTIVE_LEVEL_DEFAULT),
            "account_status": int(getattr(user, "account_status", 1) or 1),
            "email_verified": bool(getattr(user, "email_verified", False)),
            "is_superuser": bool(getattr(user, "is_superuser", False)),
            "is_authorized": bool(getattr(user, "is_authorized", False)),
            "is_system": bool(getattr(user, "is_system", False)),
            "credits": int(getattr(user, "credits", 0) or 0),
        },
        expires_delta=access_token_expires
    )
    _log_login_stage(
        logging.INFO,
        "[login] access-token request success",
        identifier=login_identifier,
        client_ip=client_ip,
        user_id=user.id,
        elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login_json(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    JSON compatible login endpoint. 
    Accepts {"username": "...", "password": "..."} in body.
    """
    request_started_at = time.perf_counter()
    login_identifier = _describe_login_identifier(login_data.username)
    client_ip = _get_request_client_ip(request)
    _log_login_stage(
        logging.INFO,
        "[login] json request start",
        identifier=login_identifier,
        client_ip=client_ip,
        path=str(getattr(request, "url", "") or ""),
    )
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        # Optional: Log failed login attempts?
        # log_action(db, user_id=None, user_name=login_data.username, action="LOGIN_FAILED", details="Incorrect password")
        _log_login_stage(
            logging.WARNING,
            "[login] json rejected: invalid credentials",
            identifier=login_identifier,
            client_ip=client_ip,
            elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    _log_login_is_active_diagnostics(db, user, login_identifier, "json-authenticated")
    if _should_block_login_for_maintenance(
        db,
        user,
        login_identifier=login_identifier,
        client_ip=client_ip,
        request_started_at=request_started_at,
        flow_name="json",
    ):
        _log_login_stage(
            logging.WARNING,
            "[login] json rejected: maintenance mode",
            identifier=login_identifier,
            client_ip=client_ip,
            user_id=user.id,
            elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
        )
        raise HTTPException(status_code=403, detail="System is under maintenance. Only system administrators can login now")
    if (
        user.account_status == -1
        and (not is_user_enabled(user.is_active))
        and (not bool(getattr(user, "is_superuser", False)))
    ):
        _log_login_stage(
            logging.WARNING,
            "[login] json rejected: email verification required",
            identifier=login_identifier,
            client_ip=client_ip,
            user_id=user.id,
            elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
        )
        raise HTTPException(status_code=403, detail="Email verification required. Please verify your email code before login")
    if not is_user_enabled(user.is_active):
        _log_login_stage(
            logging.WARNING,
            "[login] json rejected: user disabled",
            identifier=login_identifier,
            client_ip=client_ip,
            user_id=user.id,
            elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
        )
        raise HTTPException(status_code=403, detail="User is disabled")

    try:
        seed_started_at = time.perf_counter()
        _log_login_stage(logging.INFO, "[login] json seed default settings start", user_id=user.id, identifier=login_identifier)
        _seed_default_system_settings_for_user_lazy(db, user.id)
        db.commit()
        _log_login_stage(
            logging.INFO,
            "[login] json seed default settings finished",
            user_id=user.id,
            identifier=login_identifier,
            elapsed_ms=int((time.perf_counter() - seed_started_at) * 1000),
        )
    except Exception as e:
        db.rollback()
        logger.exception(
            "Failed to seed default API settings on login | user_id=%s identifier=%s elapsed_ms=%s error=%s",
            user.id,
            login_identifier,
            int((time.perf_counter() - request_started_at) * 1000),
            e,
        )
    
    # Log Successful Login
    audit_started_at = time.perf_counter()
    _log_login_stage(logging.INFO, "[login] json audit log write start", user_id=user.id, identifier=login_identifier)
    log_action(db, user_id=user.id, user_name=user.username, action="LOGIN", details="User logged in via API")
    _log_login_stage(
        logging.INFO,
        "[login] json audit log write finished",
        user_id=user.id,
        identifier=login_identifier,
        elapsed_ms=int((time.perf_counter() - audit_started_at) * 1000),
    )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    cache_user_identity(user)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "uid": user.id,
            "pv": 1,
            "uname": user.username,
            "email": getattr(user, "email", None),
            "full_name": getattr(user, "full_name", None),
            "avatar_url": getattr(user, "avatar_url", None),
            "is_active": normalize_user_active_level(getattr(user, "is_active", USER_ACTIVE_LEVEL_DEFAULT), USER_ACTIVE_LEVEL_DEFAULT),
            "account_status": int(getattr(user, "account_status", 1) or 1),
            "email_verified": bool(getattr(user, "email_verified", False)),
            "is_superuser": bool(getattr(user, "is_superuser", False)),
            "is_authorized": bool(getattr(user, "is_authorized", False)),
            "is_system": bool(getattr(user, "is_system", False)),
            "credits": int(getattr(user, "credits", 0) or 0),
        },
        expires_delta=access_token_expires
    )
    _log_login_stage(
        logging.INFO,
        "[login] json request success",
        identifier=login_identifier,
        client_ip=client_ip,
        user_id=user.id,
        elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/password/forgot")
@limiter.limit(settings.RATE_LIMIT_RESET)
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = (payload.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    user = db.query(User).filter(User.email == email).first()
    # Always return generic success to avoid account enumeration
    success_msg = "If the email exists, a password reset link has been sent."

    if not user:
        return {"status": "ok", "message": success_msg}

    token = create_password_reset_token(email)
    smtp_cfg = _resolve_runtime_smtp_config()
    frontend_base = str(smtp_cfg.get("frontend_base_url") or "").strip()
    if not frontend_base:
        frontend_base = "http://localhost:5173"
    reset_link = f"{frontend_base.rstrip('/')}/auth?mode=reset&token={token}"

    try:
        send_password_reset_email(email, reset_link)
        log_action(
            db,
            user_id=user.id,
            user_name=user.username,
            action="PASSWORD_RESET_REQUEST",
            details=f"email={email}",
        )
    except Exception as e:
        logger.error("Failed to send password reset email to %s: %s", email, e)
        raise HTTPException(status_code=500, detail="Failed to send reset email")

    return {"status": "ok", "message": success_msg}


@router.post("/password/reset")
@limiter.limit(settings.RATE_LIMIT_RESET)
def reset_password(request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token = (payload.token or "").strip()
    new_password = (payload.new_password or "").strip()

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    email = verify_password_reset_token(token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset request")

    user.hashed_password = get_password_hash(new_password)
    db.commit()

    try:
        log_action(
            db,
            user_id=user.id,
            user_name=user.username,
            action="PASSWORD_RESET_SUCCESS",
            details=f"email={email}",
        )
    except Exception:
        pass

    return {"status": "ok", "message": "Password has been reset successfully"}

