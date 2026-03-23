import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


_TOKEN_VERSION = 1
_TOKEN_CONTEXT = "homepage_referral_v1"


def _urlsafe_b64encode_nopad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _urlsafe_b64decode_nopad(raw: str) -> bytes:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("empty token")
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(f"{text}{padding}".encode("ascii"))


def _derive_user_mask(secret_key: str) -> int:
    digest = hashlib.sha256(f"{_TOKEN_CONTEXT}:{secret_key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _sign_payload(secret_key: str, masked_user_id: str, issued_at_seconds: int) -> str:
    body = f"{_TOKEN_VERSION}:{masked_user_id}:{issued_at_seconds}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def create_homepage_referral_token(
    user_id: int,
    secret_key: str,
    issued_at: Optional[datetime] = None,
) -> str:
    parsed_user_id = int(user_id or 0)
    if parsed_user_id <= 0:
        raise ValueError("invalid user id")

    current_time = issued_at or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    else:
        current_time = current_time.astimezone(timezone.utc)

    issued_at_seconds = int(current_time.timestamp())
    mask = _derive_user_mask(secret_key)
    masked_user_id = format(parsed_user_id ^ mask, "x")
    signature = _sign_payload(secret_key, masked_user_id, issued_at_seconds)
    payload = {
        "v": _TOKEN_VERSION,
        "m": masked_user_id,
        "t": issued_at_seconds,
        "s": signature,
    }
    return _urlsafe_b64encode_nopad(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def parse_homepage_referral_token(token: str, secret_key: str) -> Dict[str, Any]:
    try:
        payload = json.loads(_urlsafe_b64decode_nopad(token).decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid token encoding") from exc

    if not isinstance(payload, dict):
        raise ValueError("invalid token payload")

    version = int(payload.get("v") or 0)
    if version != _TOKEN_VERSION:
        raise ValueError("unsupported token version")

    masked_user_id = str(payload.get("m") or "").strip().lower()
    signature = str(payload.get("s") or "").strip().lower()
    try:
        issued_at_seconds = int(payload.get("t") or 0)
    except Exception as exc:
        raise ValueError("invalid token timestamp") from exc

    if not masked_user_id or not signature or issued_at_seconds <= 0:
        raise ValueError("missing token fields")

    expected_signature = _sign_payload(secret_key, masked_user_id, issued_at_seconds)
    if len(signature) != len(expected_signature) or not hmac.compare_digest(signature, expected_signature):
        raise ValueError("invalid token signature")

    try:
        encoded_value = int(masked_user_id, 16)
    except Exception as exc:
        raise ValueError("invalid masked user id") from exc

    user_id = encoded_value ^ _derive_user_mask(secret_key)
    if user_id <= 0:
        raise ValueError("invalid decoded user id")

    issued_at_iso = datetime.fromtimestamp(issued_at_seconds, tz=timezone.utc).isoformat()
    return {
        "token_version": version,
        "inviter_user_id": user_id,
        "issued_at": issued_at_iso,
        "masked_user_id": masked_user_id,
    }