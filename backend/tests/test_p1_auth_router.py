# -*- coding: utf-8 -*-
from app.api.routers.auth import router


def test_auth_router_exposes_me_routes():
    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/users/me" in paths
    assert "/users/me/profile" in paths
    assert "/users/me/password" in paths
    assert "/users/me/avatar" in paths


def test_auth_router_exposes_session_routes():
    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/users/" in paths
    assert "/users/verification/send" in paths
    assert "/users/verification/confirm" in paths
    assert "/login" in paths
    assert "/login/access-token" in paths
    assert "/password/forgot" in paths
    assert "/password/reset" in paths


def test_user_auth_schema_and_security_standalone():
    from app.schemas.user_auth import UserOut, USER_ACTIVE_LEVEL_DEFAULT, normalize_user_active_level
    from app.services.auth_security import get_password_hash, verify_password

    assert normalize_user_active_level(3) == 3
    assert USER_ACTIVE_LEVEL_DEFAULT == 1
    hashed = get_password_hash("abc123")
    assert verify_password("abc123", hashed)
    assert UserOut.__name__ == "UserOut"


def test_auth_email_helpers_importable():
    from app.services.auth_email import _is_valid_email_format
    assert _is_valid_email_format("a@b.co")
    assert not _is_valid_email_format("bad")
