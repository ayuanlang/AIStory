
import requests
import re
import urllib.parse
import urllib3
import time
import base64
import json
import hashlib
import hmac
import asyncio
import uuid
import os
import random
import io
import traceback
import math
import ipaddress
import mimetypes
import shutil
import tempfile
from PIL import Image
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Callable, Set, Tuple

from app.db.session import SessionLocal
from app.models.all_models import APISetting, SystemAPISetting, ProviderKeyPool
from app.core.config import settings
from app.core.mp4_faststart import optimize_mp4_faststart
from app.services.billing_service import BillingService
from app.services.oss_storage_service import oss_storage_service
from app.services.system_default_api_service import get_task_default_system_setting
from sqlalchemy import cast, String, func, text
from sqlalchemy.orm import load_only

# Suppress InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import logging
logger = logging.getLogger("media_service")
# ... imports ...

DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS = int(os.getenv("VIDEO_POLL_TIMEOUT_SECONDS", "600"))
DEFAULT_N1N_IMAGE_READ_TIMEOUT_SECONDS = max(120, int(os.getenv("N1N_IMAGE_READ_TIMEOUT_SECONDS", "300")))
# Upstream create-task HTTP only (not poll / callback wait). Keep short so hung providers fail fast.
DEFAULT_MEDIA_SUBMIT_CONNECT_TIMEOUT_SECONDS = max(
    5, int(os.getenv("MEDIA_SUBMIT_CONNECT_TIMEOUT_SECONDS", "15") or 15)
)
DEFAULT_MEDIA_SUBMIT_IO_TIMEOUT_SECONDS = max(
    15, int(os.getenv("MEDIA_SUBMIT_IO_TIMEOUT_SECONDS", "60") or 60)
)


def _media_submit_timeout_pair(
    connect_timeout: Optional[int] = None,
    io_timeout: Optional[int] = None,
) -> Tuple[int, int]:
    connect = DEFAULT_MEDIA_SUBMIT_CONNECT_TIMEOUT_SECONDS if connect_timeout is None else int(connect_timeout)
    io = DEFAULT_MEDIA_SUBMIT_IO_TIMEOUT_SECONDS if io_timeout is None else int(io_timeout)
    return (max(5, connect), max(15, io))

_BASE64_PATTERN = re.compile(r'(data:[\w/+.-]+;base64,)[A-Za-z0-9+/=]{64,}')
_RAW_BASE64_PATTERN = re.compile(r'(?<![A-Za-z0-9+/=])[A-Za-z0-9+/=]{256,}(?:={0,2})(?![A-Za-z0-9+/=])')
_LOG_STRING_PREVIEW_CHARS = max(128, int(os.getenv("MEDIA_LOG_STRING_PREVIEW_CHARS", "400")))
_LOG_LIST_PREVIEW_ITEMS = max(4, int(os.getenv("MEDIA_LOG_LIST_PREVIEW_ITEMS", "12")))
_LOG_DICT_PREVIEW_KEYS = max(8, int(os.getenv("MEDIA_LOG_DICT_PREVIEW_KEYS", "40")))
_LOG_MAX_DEPTH = max(2, int(os.getenv("MEDIA_LOG_MAX_DEPTH", "4")))
_LOG_SERIALIZED_MAX_CHARS = max(1024, int(os.getenv("MEDIA_LOG_SERIALIZED_MAX_CHARS", "8000")))
MEDIA_DEBUG_LOG_ENABLED = os.getenv("MEDIA_DEBUG_LOG", "0") == "1"
MEDIA_DEBUG_LOG_MAX_CHARS = max(512, int(os.getenv("MEDIA_DEBUG_LOG_MAX_CHARS", "1800") or 1800))

def _strip_base64_from_log(obj):
    """Recursively strip base64 content from data structures before logging."""
    if isinstance(obj, str):
        if obj.startswith("data:") and ";base64," in obj[:64]:
            prefix = obj[:obj.index(";base64,") + 8]
            return f"{prefix}<BASE64_STRIPPED len={len(obj)}>"
        stripped = _BASE64_PATTERN.sub(r'\1<BASE64_STRIPPED>', obj)
        stripped = _RAW_BASE64_PATTERN.sub(lambda match: f"<BASE64_STRIPPED len={len(match.group(0))}>", stripped)
        return stripped
    if isinstance(obj, dict):
        return {k: _strip_base64_from_log(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_strip_base64_from_log(item) for item in obj]
    return obj

def _strip_query_from_log_url(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = urllib.parse.urlsplit(raw)
        if parsed.scheme and parsed.netloc:
            return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except Exception:
        pass
    return raw[:300]

def _sanitize_payload_for_log(obj: Any, depth: int = 0) -> Any:
    if depth >= _LOG_MAX_DEPTH:
        return f"<TRUNCATED depth={depth}>"

    if isinstance(obj, str):
        stripped = _strip_base64_from_log(obj)
        if len(stripped) > _LOG_STRING_PREVIEW_CHARS:
            return f"{stripped[:_LOG_STRING_PREVIEW_CHARS]}...<TRUNCATED len={len(stripped)}>"
        return stripped

    if isinstance(obj, dict):
        items = list(obj.items())
        limited = {
            str(k): _sanitize_payload_for_log(v, depth + 1)
            for k, v in items[:_LOG_DICT_PREVIEW_KEYS]
        }
        if len(items) > _LOG_DICT_PREVIEW_KEYS:
            limited["__truncated_keys__"] = len(items) - _LOG_DICT_PREVIEW_KEYS
        return limited

    if isinstance(obj, (list, tuple)):
        seq = list(obj)
        limited_items = [_sanitize_payload_for_log(item, depth + 1) for item in seq[:_LOG_LIST_PREVIEW_ITEMS]]
        if len(seq) > _LOG_LIST_PREVIEW_ITEMS:
            limited_items.append(f"<TRUNCATED items={len(seq) - _LOG_LIST_PREVIEW_ITEMS}>")
        return limited_items

    return obj

def _format_payload_for_log(payload: Any) -> str:
    try:
        sanitized = _sanitize_payload_for_log(payload)
        rendered = json.dumps(sanitized, ensure_ascii=False, default=str)
    except Exception as e:
        rendered = f"<UNSERIALIZABLE payload error={type(e).__name__}>"
    if len(rendered) > _LOG_SERIALIZED_MAX_CHARS:
        return f"{rendered[:_LOG_SERIALIZED_MAX_CHARS]}...<TRUNCATED len={len(rendered)}>"
    return rendered

def _debug_log(msg, level="info"):
    """Bounded debug logger for optional verbose traces.

    Info-level debug traces are disabled by default and only enabled with
    MEDIA_DEBUG_LOG=1. Warning/error logs still flow for diagnostics.
    """
    method = getattr(logger, level, logger.info)
    if level not in {"warning", "error", "critical"} and not MEDIA_DEBUG_LOG_ENABLED:
        return
    text = str(msg or "")
    if len(text) > MEDIA_DEBUG_LOG_MAX_CHARS:
        text = f"{text[:MEDIA_DEBUG_LOG_MAX_CHARS]}...<TRUNCATED len={len(text)}>"
    method(text)


def _safe_usage_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
        return parsed if parsed > 0 else 0
    except Exception:
        return 0


def _safe_usage_float(value: Any) -> float:
    try:
        parsed = float(value or 0)
        return parsed if parsed > 0 else 0.0
    except Exception:
        return 0.0


def _optional_usage_non_negative_float(value: Any) -> Optional[float]:
    """Parse provider usage scalars; keep 0, drop null/empty/invalid."""
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except Exception:
        return None
    if parsed < 0 or parsed != parsed:  # NaN
        return None
    return parsed


_RUNNINGHUB_USAGE_KEYS = (
    "consumeCoins",
    "consume_coins",
    "consumeMoney",
    "consume_money",
    "thirdPartyConsumeMoney",
    "third_party_consume_money",
    "taskCostTime",
    "task_cost_time",
)


def _extract_scalar_provider_credits(payload: Any) -> Dict[str, Any]:
    """Pull scalar credit fields (e.g. KIE webhook data.creditsConsumed)."""
    if not isinstance(payload, dict):
        return {}
    for key in (
        "creditsConsumed",
        "credits_consumed",
        "kie_credits_consumed",
        "consumeCredits",
        "consume_credits",
        "credits",
        "credit",
        "points",
    ):
        if key not in payload or payload.get(key) in (None, ""):
            continue
        amount = _safe_usage_float(payload.get(key))
        if amount <= 0:
            continue
        return {
            "creditsConsumed": amount,
            "credits_consumed": amount,
            "kie_credits_consumed": amount,
            "credits": amount,
        }
    return {}


def _extract_provider_task_usage(payload: Any, *, _depth: int = 0) -> Dict[str, Any]:
    """Extract usage/credits from provider task-query / webhook payloads (Ark, KIE, ZLHub, RunningHub, etc.)."""
    if not isinstance(payload, dict) or _depth > 4:
        return {}
    for key in ("usage", "consume", "consumption", "billing", "cost"):
        value = payload.get(key)
        if isinstance(value, dict) and value:
            # Merge scalar credits on the same object when present (KIE sometimes nests both).
            merged = dict(value)
            scalar = _extract_scalar_provider_credits(payload)
            for sk, sv in scalar.items():
                merged.setdefault(sk, sv)
            return merged

    scalar = _extract_scalar_provider_credits(payload)
    if scalar:
        return scalar

    for nested_key in ("data", "output", "result", "content", "task", "response", "eventData"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            found = _extract_provider_task_usage(nested, _depth=_depth + 1)
            if found:
                return found
    return {}


def _normalize_provider_task_usage(usage: Any) -> Dict[str, Any]:
    """Normalize OpenAI/Ark/KIE/RunningHub usage into billing-friendly token/credit keys."""
    if not isinstance(usage, dict) or not usage:
        return {}
    normalized = dict(usage)
    prompt = _safe_usage_int(normalized.get("prompt_tokens") or normalized.get("input_tokens"))
    completion = _safe_usage_int(
        normalized.get("completion_tokens")
        or normalized.get("output_tokens")
        or normalized.get("generated_tokens")
    )
    total = _safe_usage_int(normalized.get("total_tokens"))
    if total <= 0:
        total = prompt + completion
    credits = _safe_usage_float(
        normalized.get("creditsConsumed")
        or normalized.get("credits_consumed")
        or normalized.get("kie_credits_consumed")
        or normalized.get("credits")
        or normalized.get("credit")
        or normalized.get("points")
        or normalized.get("consume_credits")
        or normalized.get("consumeCredits")
    )
    if prompt > 0:
        normalized["prompt_tokens"] = prompt
        normalized["input_tokens"] = prompt
    if completion > 0:
        normalized["completion_tokens"] = completion
        normalized["output_tokens"] = completion
    if total > 0:
        normalized["total_tokens"] = total
    if credits > 0:
        normalized["credits"] = credits
        normalized["creditsConsumed"] = credits
        normalized["credits_consumed"] = credits
        normalized["kie_credits_consumed"] = credits

    # RunningHub webhook/query: eventData.usage.{consumeCoins,consumeMoney,thirdPartyConsumeMoney,taskCostTime}
    has_runninghub_usage = any(key in normalized for key in _RUNNINGHUB_USAGE_KEYS)
    consume_coins = _optional_usage_non_negative_float(
        normalized.get("consumeCoins") if normalized.get("consumeCoins") not in (None, "") else normalized.get("consume_coins")
    )
    consume_money = _optional_usage_non_negative_float(
        normalized.get("consumeMoney") if normalized.get("consumeMoney") not in (None, "") else normalized.get("consume_money")
    )
    third_party_money = _optional_usage_non_negative_float(
        normalized.get("thirdPartyConsumeMoney")
        if normalized.get("thirdPartyConsumeMoney") not in (None, "")
        else normalized.get("third_party_consume_money")
    )
    task_cost_time = _optional_usage_non_negative_float(
        normalized.get("taskCostTime") if normalized.get("taskCostTime") not in (None, "") else normalized.get("task_cost_time")
    )
    if consume_coins is not None:
        normalized["consumeCoins"] = consume_coins
        normalized["consume_coins"] = consume_coins
    else:
        normalized.pop("consumeCoins", None)
        normalized.pop("consume_coins", None)
    if consume_money is not None:
        normalized["consumeMoney"] = consume_money
        normalized["consume_money"] = consume_money
    else:
        normalized.pop("consumeMoney", None)
        normalized.pop("consume_money", None)
    if third_party_money is not None:
        normalized["thirdPartyConsumeMoney"] = third_party_money
        normalized["third_party_consume_money"] = third_party_money
    else:
        normalized.pop("thirdPartyConsumeMoney", None)
        normalized.pop("third_party_consume_money", None)
    if task_cost_time is not None:
        normalized["taskCostTime"] = task_cost_time
        normalized["task_cost_time"] = task_cost_time
        normalized["provider_cost_time_seconds"] = task_cost_time
        normalized["cost_time"] = task_cost_time
    else:
        normalized.pop("taskCostTime", None)
        normalized.pop("task_cost_time", None)

    # Keep token/credit payloads, or RunningHub usage blocks (including all-null + taskCostTime=0).
    if total <= 0 and credits <= 0 and prompt <= 0 and completion <= 0 and not has_runninghub_usage:
        return {}
    if has_runninghub_usage and total <= 0 and credits <= 0 and prompt <= 0 and completion <= 0:
        # Drop unrelated empty noise; keep RH audit scalars (+ aliases already set).
        slim: Dict[str, Any] = {}
        for key in (
            "consumeCoins",
            "consume_coins",
            "consumeMoney",
            "consume_money",
            "thirdPartyConsumeMoney",
            "third_party_consume_money",
            "taskCostTime",
            "task_cost_time",
            "provider_cost_time_seconds",
            "cost_time",
        ):
            if normalized.get(key) not in (None, ""):
                slim[key] = normalized.get(key)
        # Preserve presence even when RH returned only nulls / zero runtime.
        if not slim and has_runninghub_usage:
            slim["taskCostTime"] = 0.0
            slim["task_cost_time"] = 0.0
            slim["provider_cost_time_seconds"] = 0.0
            slim["cost_time"] = 0.0
        return slim
    return normalized


def _attach_provider_usage_metadata(
    metadata: Optional[Dict[str, Any]],
    *,
    usage: Optional[Dict[str, Any]] = None,
    source: str = "provider",
    task_payload: Any = None,
) -> Dict[str, Any]:
    meta = dict(metadata or {})
    resolved = _normalize_provider_task_usage(usage) if usage else {}
    if not resolved and task_payload is not None:
        resolved = _normalize_provider_task_usage(_extract_provider_task_usage(task_payload))
    if resolved:
        meta["usage"] = resolved
        meta["provider_usage"] = resolved
        meta["usage_source"] = str(source or "provider").strip() or "provider"
        for credit_key in ("creditsConsumed", "credits_consumed", "kie_credits_consumed", "credits"):
            if resolved.get(credit_key) not in (None, "") and meta.get(credit_key) in (None, ""):
                meta[credit_key] = resolved.get(credit_key)
    return meta


def _is_kie_record_info_endpoint(endpoint: Optional[str], provider: Optional[str] = None) -> bool:
    provider_l = str(provider or "").strip().lower()
    endpoint_l = str(endpoint or "").strip().lower()
    if provider_l == "kie" or provider_l.startswith("kie/") or "kie.ai" in provider_l:
        return True
    return any(token in endpoint_l for token in ("recordinfo", "record-info", "record_detail", "record-detail", "kie.ai"))


def _kie_response_looks_successful(payload: Any) -> bool:
    """KIE docs sometimes show non-200 business codes with msg=success + data."""
    if not isinstance(payload, dict):
        return False
    code = payload.get("code")
    if code in (None, 200, "200", 0, "0"):
        return True
    try:
        if int(str(code).strip()) == 200:
            return True
    except Exception:
        pass
    msg = str(payload.get("msg") or payload.get("message") or "").strip().lower()
    data = payload.get("data")
    if msg in {"success", "ok", "succeeded"} and isinstance(data, (dict, list)):
        return True
    return False


class MediaGenerationService:
# ...
    DOUBAO_MIN_IMAGE_PIXELS = 3_686_400
    SMART_ROUTER_PROVIDER = "smart_router"
    USER_API_STRATEGY_FIXED = "fixed"
    USER_API_STRATEGY_SMART_DEFAULT = "smart_default"

    def _build_local_generated_url(self, user_id: int, filename: str) -> str:
        relative_path = f"/uploads/{user_id}/{filename}"
        if settings.RENDER_EXTERNAL_URL:
            return f"{settings.RENDER_EXTERNAL_URL.rstrip('/')}{relative_path}"
        return relative_path

    def _persist_binary_locally(self, binary: bytes, *, user_id: int, filename: str) -> str:
        upload_dir = settings.UPLOAD_DIR
        user_dir = os.path.join(upload_dir, str(user_id))
        if not os.path.isabs(user_dir):
            user_dir = os.path.abspath(user_dir)
        os.makedirs(user_dir, exist_ok=True)
        file_path = os.path.join(user_dir, filename)
        with open(file_path, "wb") as handle:
            handle.write(binary)
        return self._build_local_generated_url(user_id, filename)

    def _persist_generated_bytes(
        self,
        binary: bytes,
        *,
        user_id: int,
        filename: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        uploaded = oss_storage_service.upload_bytes(
            binary,
            user_id=user_id,
            filename=filename,
            content_type=content_type,
            category="generated",
            metadata=metadata,
            cache_control="public, max-age=31536000",
        )
        if uploaded and uploaded.get("url"):
            return str(uploaded["url"])
        return self._persist_binary_locally(binary, user_id=user_id, filename=filename)

    def _finalize_generated_file(
        self,
        file_path: str,
        *,
        user_id: int,
        filename: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        uploaded = oss_storage_service.upload_file(
            file_path,
            user_id=user_id,
            filename=filename,
            content_type=content_type,
            category="generated",
            metadata=metadata,
            cache_control="public, max-age=31536000",
        )
        if uploaded and uploaded.get("url"):
            try:
                os.remove(file_path)
            except Exception:
                pass
            return str(uploaded["url"])

        upload_dir = settings.UPLOAD_DIR
        user_dir = os.path.join(upload_dir, str(user_id))
        if not os.path.isabs(user_dir):
            user_dir = os.path.abspath(user_dir)
        os.makedirs(user_dir, exist_ok=True)
        final_path = os.path.join(user_dir, filename)
        if os.path.abspath(file_path) != os.path.abspath(final_path):
            shutil.move(file_path, final_path)
        return self._build_local_generated_url(user_id, filename)

    def _build_generated_storage_metadata(
        self,
        *,
        asset_type: Optional[str] = None,
        provider_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        provider_options = provider_options if isinstance(provider_options, dict) else {}
        meta: Dict[str, Any] = {}
        resolved_asset_type = str(provider_options.get("__asset_type") or asset_type or "").strip().lower()
        if resolved_asset_type:
            meta["asset_type"] = resolved_asset_type
        for src_key, dst_key in (
            ("__subject_type", "subject_type"),
            ("__subject_name", "subject_name"),
            ("__entity_id", "entity_id"),
            ("__entity_name", "entity_name"),
            ("__entity_type", "entity_type"),
            ("__project_id", "project_id"),
            ("__episode_id", "episode_id"),
            ("__scene_id", "scene_id"),
            ("__shot_id", "shot_id"),
        ):
            value = provider_options.get(src_key)
            if value not in (None, ""):
                meta[dst_key] = value
        subject_name_ascii = provider_options.get("__subject_name_ascii")
        if subject_name_ascii not in (None, ""):
            meta["subject_name"] = subject_name_ascii
        entity_name_ascii = provider_options.get("__entity_name_ascii")
        if entity_name_ascii not in (None, ""):
            meta["entity_name"] = entity_name_ascii
        return meta
    USER_API_STRATEGY_LOW_PRICE_REPLACE = "low_price_replace"
    _AGENT_POLICY_CATEGORY = "System_Payment"
    _AGENT_POLICY_PROVIDER = "agent_policy"
    _AGENT_POLICY_MODEL = "tool_acl"
    _SORA_MENTION_CONFIG_KEY = "sora_mention_config"
    _provider_key_cursors: Dict[str, int] = {}

    def _normalize_api_strategy(self, value: Any, default: str = USER_API_STRATEGY_SMART_DEFAULT) -> str:
        raw = str(value or "").strip().lower()
        if raw in {self.USER_API_STRATEGY_FIXED, self.USER_API_STRATEGY_SMART_DEFAULT, self.USER_API_STRATEGY_LOW_PRICE_REPLACE}:
            return raw
        return default

    def _normalize_generation_mode(self, value: Any) -> str:
        raw = str(value or "").strip().lower()
        aliases = {
            "text-to-image": "t2i",
            "image-to-image": "i2i",
            "text-to-video": "t2v",
            "image-to-video": "i2v",
            "image2video": "i2v",
            "img2video": "i2v",
            "image2image": "i2i",
            "img2img": "i2i",
            "text2video": "t2v",
            "text2image": "t2i",
            "video-to-video": "v2v",
        }
        return aliases.get(raw, raw)

    def _normalize_input_format(self, value: Any) -> str:
        raw = str(value or "").strip().lower()
        aliases = {
            "img": "image",
            "images": "image",
            "picture": "image",
            "pictures": "image",
            "photo": "image",
            "photos": "image",
            "txt": "text",
            "prompt": "text",
            "prompts": "text",
            "vid": "video",
            "videos": "video",
        }
        return aliases.get(raw, raw)

    def _get_media_routing_limit(
        self,
        category: str,
        suffix: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        raw_default = default
        try:
            raw_default = int(default)
        except Exception:
            raw_default = minimum
        raw_default = max(minimum, min(maximum, raw_default))

        env_keys = [
            f"{str(category or '').strip().upper()}_{suffix}",
            f"MEDIA_{suffix}",
        ]
        for env_key in env_keys:
            raw_value = str(os.getenv(env_key, "")).strip()
            if not raw_value:
                continue
            try:
                return max(minimum, min(maximum, int(raw_value)))
            except Exception:
                logger.warning(
                    "Invalid media routing limit env ignored | key=%s value=%s default=%s",
                    env_key,
                    raw_value,
                    raw_default,
                )
        return raw_default

    def _is_n1n_kling_image_row(self, row: Any) -> bool:
        model_lower = str(getattr(row, "model", "") or "").strip().lower()
        if model_lower == "kling_image":
            return True
        supplier_info = self._safe_json_dict(getattr(row, "supplier_info", None) if row is not None else None)
        n1n_info = self._safe_json_dict(supplier_info.get("n1n"))
        protocol_key = str(n1n_info.get("protocol_key") or "").strip().lower()
        family_key = str(n1n_info.get("family_key") or "").strip().lower()
        return protocol_key == "kling_image" or family_key == "kling"

    def _system_row_supports_generation_mode(self, row: Any, target_generation_mode: Any, cfg: Optional[Dict[str, Any]] = None) -> bool:
        target_mode = self._normalize_generation_mode(target_generation_mode)
        if not target_mode:
            return True

        raw_cfg = cfg if isinstance(cfg, dict) else self._safe_json_dict(getattr(row, "config", None) if row is not None else None)
        modality = self._safe_json_dict(getattr(row, "modality", None) if row is not None else None)
        supplier_info = self._safe_json_dict(getattr(row, "supplier_info", None) if row is not None else None)

        containers: List[Dict[str, Any]] = []
        for item in (
            raw_cfg,
            modality.get("capability_flags"),
            modality.get("image_capabilities"),
            modality.get("video_capabilities"),
            modality,
            supplier_info,
        ):
            normalized = self._safe_json_dict(item)
            if normalized:
                containers.append(normalized)
        for nested in supplier_info.values() if isinstance(supplier_info, dict) else []:
            normalized = self._safe_json_dict(nested)
            if normalized:
                containers.append(normalized)

        raw_generation_modes: List[str] = []
        raw_input_formats: List[str] = []
        for container in containers:
            for key in ("generation_modes", "generationModes", "supported_generation_modes", "supportedGenerationModes"):
                raw_generation_modes.extend(self._normalize_str_list(container.get(key)))
            for key in ("input_formats", "inputFormats", "supported_input_formats", "supportedInputFormats"):
                raw_input_formats.extend(self._normalize_str_list(container.get(key)))

        normalized_generation_modes = {
            self._normalize_generation_mode(item)
            for item in raw_generation_modes
            if str(item or "").strip().lower() not in {"", "n/a", "na", "none", "unknown", "all", "any"}
        }
        if raw_generation_modes:
            if not normalized_generation_modes:
                return False
            if target_mode not in normalized_generation_modes:
                return False

        required_input_by_mode = {
            "t2i": "text",
            "i2i": "image",
            "t2v": "text",
            "i2v": "image",
            "v2v": "video",
        }
        normalized_input_formats = {
            self._normalize_input_format(item)
            for item in raw_input_formats
            if str(item or "").strip().lower() not in {"", "n/a", "na", "none", "unknown", "all", "any"}
        }
        if self._is_n1n_kling_image_row(row):
            normalized_input_formats.update({"text", "image"})
        required_input = required_input_by_mode.get(target_mode)
        if raw_input_formats and required_input and required_input not in normalized_input_formats:
            return False

        model_lower = str(getattr(row, "model", "") or "").strip().lower()
        if target_mode == "i2i":
            if self._is_n1n_kling_image_row(row):
                return True
            if any(token in model_lower for token in ("image-to-image", "/edit", "-edit", "_edit", "i2i")):
                return True
            if any(token in model_lower for token in ("text-to-image", "t2i")):
                return False
            if model_lower in {"kling_image", "midjourney_image", "replicate_image", "tencent_image_image"}:
                return False

        return True

    def _provider_ci_filter(self, provider: Any):
        provider_norm = str(provider or "").strip().lower()
        return func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm

    def _vendor_label(self, provider: Any) -> str:
        raw = str(provider or "").strip()
        normalized = raw.lower()
        if normalized in {"lzhbu", "zlhub", "zhonglian"}:
            return "zlhub"
        return raw or "unknown"

    def _vendor_failed_message(self, provider: Any, reason: Any) -> str:
        vendor = self._vendor_label(provider)
        detail = str(reason or "unknown error").strip()
        if "供应商调用失败" in detail:
            return detail
        return f"{vendor}供应商调用失败: {detail}"

    def _safe_json_dict(self, value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except Exception:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _is_json_object_value(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, dict):
            return True
        if isinstance(value, (bytes, bytearray)):
            try:
                value = value.decode("utf-8", errors="ignore")
            except Exception:
                return False
        if isinstance(value, str):
            raw_obj: Any = value
            for _ in range(3):
                if isinstance(raw_obj, dict):
                    return True
                if not isinstance(raw_obj, str):
                    return False

                raw = raw_obj.strip()
                if not raw:
                    return True

                try:
                    parsed = json.loads(raw)
                except Exception:
                    return False
                raw_obj = parsed

            return isinstance(raw_obj, dict)
        return False

    def _flatten_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            parts = []
            for key in ["message", "msg", "error", "status", "reason", "code", "details"]:
                if key in value:
                    parts.append(self._flatten_text(value.get(key)))
            for item in value.values():
                parts.append(self._flatten_text(item))
            return " ".join(p for p in parts if p)
        if isinstance(value, list):
            return " ".join(self._flatten_text(item) for item in value)
        return str(value)

    def _normalize_retry_group(self, value: Any) -> str:
        return str(value or "").strip().lower()

    def _get_retry_group_from_config(self, config_obj: Any) -> str:
        cfg = self._safe_json_dict(config_obj)
        return self._normalize_retry_group(
            cfg.get("retry_group")
            or cfg.get("routing_group")
            or cfg.get("smart_group")
        )

    def _get_retry_price_group_from_config(self, config_obj: Any) -> str:
        cfg = self._safe_json_dict(config_obj)
        return self._normalize_retry_group(
            cfg.get("retry_price_group")
            or cfg.get("price_tier_group")
            or cfg.get("pricing_tier")
        )


    @staticmethod
    def _sign_volc_request_v4(
        path: str,
        method: str,
        headers: Dict[str, str],
        body: str,
        query: Dict[str, str],
        ak: str,
        sk: str,
        region: str,
        service: str,
        session_token: Optional[str] = None,
    ) -> None:
        """Volcengine Signature V4 (HMAC-SHA256). Local impl avoids volcenginesdkcore import.

        Importing volcenginesdkcore.signv4 pulls endpoint/providers/default_provider.py;
        a truncated/corrupt install of that file raises SyntaxError: '{' was never closed
        (default_provider.py, line 65) and breaks Ark private-asset registration.
        """
        from urllib.parse import quote

        if not path:
            path = "/"
        if method != "GET" and "Content-Type" not in headers:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"

        format_date = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        headers["X-Date"] = format_date
        body_text = body if isinstance(body, str) else (body or "")
        body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
        headers["X-Content-Sha256"] = body_hash
        if session_token:
            headers["X-Security-Token"] = session_token

        signed_headers: Dict[str, str] = {}
        for key, value in headers.items():
            if key in ("Content-Type", "Content-Md5", "Host") or key.startswith("X-"):
                signed_headers[key.lower()] = value

        if "host" in signed_headers:
            host_value = signed_headers["host"]
            if ":" in host_value:
                host_name, port = host_value.split(":", 1)
                if port in ("80", "443"):
                    signed_headers["host"] = host_name

        signed_str = "".join(f"{key}:{signed_headers[key]}\n" for key in sorted(signed_headers.keys()))
        signed_headers_string = ";".join(sorted(signed_headers.keys()))

        query_pairs = []
        for key, value in (query or {}).items():
            query_pairs.append((quote(str(key), safe="-_.~"), quote(str(value), safe="-_.~")))
        canonical_query = "&".join(f"{k}={v}" for k, v in sorted(query_pairs))

        canonical_request = "\n".join(
            [method, path, canonical_query, signed_str, signed_headers_string, body_hash]
        )
        credential_scope = "/".join([format_date[:8], region, service, "request"])
        string_to_sign = "\n".join(
            [
                "HMAC-SHA256",
                format_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        def _hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        signing_key = _hmac_sha256(
            _hmac_sha256(
                _hmac_sha256(_hmac_sha256(sk.encode("utf-8"), format_date[:8]), region),
                service,
            ),
            "request",
        )
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        credential = f"{ak}/{credential_scope}"
        headers["Authorization"] = (
            f"HMAC-SHA256 Credential={credential}, "
            f"SignedHeaders={signed_headers_string}, Signature={signature}"
        )

    def _do_volc_request(self, method: str, action: str, version: str, req_body: str, service: str, ak: str, sk: str) -> dict:
        host = "open.volcengineapi.com"
        headers = {
            "Content-Type": "application/json",
            "Host": host,
        }
        query = {
            "Action": action,
            "Version": version,
        }

        self._sign_volc_request_v4(
            "/",
            method,
            headers,
            req_body,
            query,
            ak,
            sk,
            "cn-beijing",
            service,
        )

        url = f"https://{host}/?Action={urllib.parse.quote(action)}&Version={urllib.parse.quote(version)}"
        logger.info("[Volcengine] Requesting: %s | payload length: %s", url, len(req_body or ""))
        resp = requests.request(method, url, headers=headers, data=(req_body or "").encode("utf-8"))
        logger.info("[Volcengine] Response %s: %s", resp.status_code, (resp.text or "")[:500])

        if resp.status_code != 200:
            raise Exception(f"Volcengine HTTP {resp.status_code}: {resp.text}")

        r_json = resp.json()
        if "ResponseMetadata" in r_json and "Error" in r_json["ResponseMetadata"]:
            raise Exception(f"Volcengine API Error: {r_json['ResponseMetadata']['Error']}")

        return r_json.get("Result", r_json)

    async def _handle_ark_seedance_generation(self, category: str, prompt: str, config: dict, reference_image_url: str = None, last_frame_url: str = None, duration=None, aspect_ratio=None) -> dict:
        api_key = config.get("api_key", "")
        tool_conf = config.get("config", {}) or {}
        ak, sk, dp_token = "", "", ""
        if ":" in api_key and api_key.count(":") >= 2:
            parts = api_key.split(":", 2)
            ak = parts[0]
            sk = parts[1]
            dp_token = parts[2]
            
        explicit_project_name = str(
            tool_conf.get("project_name")
            or tool_conf.get("projectName")
            or config.get("project_name")
            or os.getenv("ARK_PROJECT_NAME")
            or ""
        ).strip()
        project_name = explicit_project_name or "test3"
        if ":" in dp_token:
            subparts = dp_token.split(":", 1)
            dp_token = subparts[0]
            token_project_name = str(subparts[1] or "").strip()
            if not explicit_project_name and token_project_name:
                project_name = token_project_name
        project_name = str(project_name or "").strip() or "test3"
        if project_name.isdigit() and not str(tool_conf.get("project_name") or "").strip():
            # Some legacy keys append non-project numeric suffixes after EP token.
            # Treat them as invalid project names and fallback to default.
            _debug_log(
                f"[ark-seedance] ignore numeric project suffix from api_key | suffix={project_name}",
                "warning",
            )
            project_name = "test3"
        _debug_log(
            f"[ark-seedance] effective project selected | project_name={project_name}",
            "info",
        )
            
        if not ak or not sk or not dp_token:
            return {"error": "ark-seedance provider requires api_key format: AK:SK:EP_TOKEN"}
            
        image_ref_candidates = self._collect_video_reference_image_urls(
            reference_image_url,
            tool_conf,
            extra_sources=config,
        )
        ref_image = image_ref_candidates[0] if image_ref_candidates else None
        extra_ref_images = image_ref_candidates[1:] if len(image_ref_candidates) > 1 else []

        reference_video_urls_list = self._collect_video_reference_video_urls(
            tool_conf,
            extra_sources=config,
        )

        reference_audio_raw = tool_conf.get("reference_audio_urls") or tool_conf.get("ref_audio_urls") or config.get("reference_audio_urls") or []
        if isinstance(reference_audio_raw, str):
            reference_audio_urls_list = [reference_audio_raw] if reference_audio_raw.strip() else []
        elif isinstance(reference_audio_raw, list):
            reference_audio_urls_list = [str(x) for x in reference_audio_raw if x]
        else:
            reference_audio_urls_list = []

        if not ref_image and not reference_video_urls_list:
            return {"error": "seedance 2.0 requires at least one image or video reference"}

        # Align with other provider paths (e.g. KIE): normalize and refresh
        # managed OSS URLs before downstream submission.
        if ref_image:
            try:
                resolved_ref_image = await self._resolve_ref_for_api_async(
                    ref_image,
                    force_data_uri_for_local=False,
                    prefer_public_upload_url=True,
                )
                if resolved_ref_image:
                    ref_image = resolved_ref_image
                    _debug_log(
                        f"[ark-seedance] reference pre-resolved | preview={_strip_query_from_log_url(str(ref_image)[:300])}",
                        "info",
                    )
            except Exception as resolve_err:
                logger.warning("Ark Seedance reference pre-resolve failed | error=%s", str(resolve_err)[:300])
            
        import json
        import urllib.parse

        api_version = str(tool_conf.get("asset_api_version") or "2024-01-01").strip()
        asset_group_name = str(tool_conf.get("asset_group_name") or "seedance_asset").strip() or "seedance_asset"
        asset_item_name = str(tool_conf.get("asset_name") or tool_conf.get("asset_item_name") or "seedance_image").strip() or "seedance_image"
        asset_rebuild_source_url = ""

        def _guess_ark_asset_type(value: Any) -> str:
            if isinstance(value, dict):
                explicit_type = str(
                    value.get("asset_type")
                    or value.get("media_type")
                    or value.get("type")
                    or value.get("category")
                    or ""
                ).strip().lower()
                if "video" in explicit_type:
                    return "Video"
                if "audio" in explicit_type:
                    return "Audio"
                for key in ("video_url", "videoUrl", "video", "url", "src"):
                    nested = value.get(key)
                    if nested:
                        return _guess_ark_asset_type(nested)

            raw_value = str(value or "").strip().lower()
            path_only = raw_value.split("?", 1)[0].split("#", 1)[0]
            if path_only.endswith((".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v")):
                return "Video"
            if path_only.endswith((".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus")):
                return "Audio"
            return "Image"

        def _build_ark_reference_content(media_ref: str, asset_type: str) -> Dict[str, Any]:
            normalized_type = str(asset_type or "Image").strip().lower()
            if normalized_type == "video":
                return {
                    "type": "video_url",
                    "video_url": {"url": media_ref},
                    "role": "reference_video",
                }
            if normalized_type == "audio":
                return {
                    "type": "audio_url",
                    "audio_url": {"url": media_ref},
                    "role": "reference_audio",
                }
            return {
                "type": "image_url",
                "image_url": {"url": media_ref},
                "role": "reference_image",
            }

        def _collect_project_candidates() -> List[str]:
            candidates: List[str] = []
            for value in (
                project_name,
                tool_conf.get("project_name"),
                tool_conf.get("projectName"),
                tool_conf.get("project"),
                tool_conf.get("ark_project_name"),
                tool_conf.get("volc_project_name"),
                config.get("project_name"),
                os.getenv("ARK_PROJECT_NAME"),
                "default",
            ):
                item = str(value or "").strip()
                if item and item not in candidates:
                    candidates.append(item)
            return candidates

        async def _register_private_asset_from_public_url(source_url: str, target_project_name: Optional[str] = None, asset_type: str = "Image") -> str:
            candidate_url = str(source_url or "").strip()
            if not candidate_url.lower().startswith(("http://", "https://")):
                return ""
            effective_project_name = str(target_project_name or project_name or "").strip() or "default"
            normalized_asset_type = str(asset_type or "Image").strip().title()
            if normalized_asset_type not in {"Image", "Video", "Audio"}:
                normalized_asset_type = "Image"

            async def _register_once(project_for_register: str) -> str:
                local_project_name = str(project_for_register or "").strip() or "default"
                _debug_log(
                    f"[ark-seedance] private asset register start | project_name={local_project_name} asset_group={asset_group_name}",
                    "info",
                )
                group_id_local = str(tool_conf.get("asset_group_id") or "").strip()
                if not group_id_local:
                    list_payload = {
                        "Filter": {
                            "Name": asset_group_name,
                            "GroupType": "AIGC",
                        },
                        "PageNumber": 1,
                        "PageSize": 20,
                        "ProjectName": local_project_name,
                    }
                    list_res = self._do_volc_request(
                        "POST",
                        "ListAssetGroups",
                        api_version,
                        json.dumps(list_payload),
                        "ark",
                        ak,
                        sk,
                    )
                    list_items = list_res.get("Items") if isinstance(list_res, dict) else None
                    if isinstance(list_items, list):
                        matched_group = None
                        for item in list_items:
                            if not isinstance(item, dict):
                                continue
                            item_name = str(item.get("Name") or item.get("Title") or "").strip()
                            item_project = str(item.get("ProjectName") or "").strip()
                            if item_name == asset_group_name and (not item_project or item_project == local_project_name):
                                matched_group = item
                                break
                        if not matched_group and list_items:
                            first = list_items[0]
                            if isinstance(first, dict):
                                matched_group = first
                        if matched_group:
                            group_id_local = str(
                                matched_group.get("Id")
                                or matched_group.get("GroupId")
                                or matched_group.get("AssetGroupId")
                                or ""
                            ).strip()

                if not group_id_local:
                    group_payload = {
                        "Name": asset_group_name,
                        "Description": "aistory seedance private assets",
                        "GroupType": "AIGC",
                        "ProjectName": local_project_name,
                    }
                    group_res = self._do_volc_request(
                        "POST",
                        "CreateAssetGroup",
                        api_version,
                        json.dumps(group_payload),
                        "ark",
                        ak,
                        sk,
                    )
                    group_id_local = str(
                        group_res.get("GroupId")
                        or group_res.get("Id")
                        or group_res.get("AssetGroupId")
                        or ""
                    ).strip()

                if not group_id_local:
                    return ""

                asset_payload = {
                    "GroupId": group_id_local,
                    "URL": candidate_url,
                    "AssetType": normalized_asset_type,
                    "Name": f"{asset_item_name}_{normalized_asset_type.lower()}",
                    "ProjectName": local_project_name,
                }
                asset_res = self._do_volc_request(
                    "POST",
                    "CreateAsset",
                    api_version,
                    json.dumps(asset_payload),
                    "ark",
                    ak,
                    sk,
                )
                asset_obj = asset_res.get("Asset", {}) if isinstance(asset_res, dict) else {}
                created_asset_id = str(
                    asset_res.get("Id")
                    or asset_res.get("AssetId")
                    or asset_obj.get("Id")
                    or asset_obj.get("AssetId")
                    or ""
                ).strip()
                if not created_asset_id:
                    return ""

                max_polls = 180
                for _ in range(max_polls):
                    await asyncio.sleep(5)
                    poll_req = {"Id": created_asset_id, "ProjectName": local_project_name}
                    poll_res = self._do_volc_request(
                        "POST",
                        "GetAsset",
                        api_version,
                        json.dumps(poll_req),
                        "ark",
                        ak,
                        sk,
                    )
                    status = (
                        poll_res.get("Status")
                        or poll_res.get("status")
                        or poll_res.get("Asset", {}).get("Status")
                        or poll_res.get("Asset", {}).get("status")
                        or ""
                    )
                    status = str(status).strip().lower()
                    if status in {"active", "ready", "success", "completed"}:
                        _debug_log(
                            f"[ark-seedance] private asset active | project_name={local_project_name} asset_id={created_asset_id}",
                            "info",
                        )
                        return f"asset://{created_asset_id}"
                    if status == "failed":
                        return ""

                return ""
            try:
                return await _register_once(effective_project_name)
            except Exception as register_err:
                err_text = self._flatten_text(register_err).lower()
                if "notfound.projectname" in err_text and effective_project_name != "default":
                    logger.warning(
                        "Ark private asset register fallback to default project | invalid_project=%s",
                        effective_project_name,
                    )
                    return await _register_once("default")
                raise

        def _extract_asset_id_from_uri(value: Any) -> str:
            raw = str(value or "").strip()
            if not raw.startswith("asset://"):
                return ""
            return raw[len("asset://"):].strip()

        def _get_asset_info(asset_id: str, candidate_project: Optional[str]) -> Dict[str, Any]:
            req: Dict[str, Any] = {"Id": asset_id}
            if str(candidate_project or "").strip():
                req["ProjectName"] = str(candidate_project).strip()
            return self._do_volc_request(
                "POST",
                "GetAsset",
                api_version,
                json.dumps(req),
                "ark",
                ak,
                sk,
            )
        
        asset_id_or_url = ""
        primary_asset_type = "Image"
        asset_rebuild_source_url = ""

        if ref_image:
            asset_id_or_url = ref_image
            primary_asset_type = _guess_ark_asset_type(ref_image)
            ref_raw = str(ref_image or "").strip()
            ref_is_http = ref_raw.lower().startswith(("http://", "https://"))
            ref_has_ctrl = any(ord(ch) < 32 for ch in ref_raw)
            ref_has_inner_space = bool(re.search(r"\s", ref_raw))
            ref_scheme = ""
            ref_netloc = ""
            try:
                parsed_ref = urllib.parse.urlparse(ref_raw)
                ref_scheme = str(parsed_ref.scheme or "").lower()
                ref_netloc = str(parsed_ref.netloc or "")
            except Exception:
                parsed_ref = None

            _debug_log(
                f"[ark-seedance] reference classify | raw_preview={_strip_query_from_log_url(ref_raw)[:300]} "
                f"scheme={ref_scheme or None} netloc={ref_netloc or None} ref_is_http={ref_is_http} "
                f"has_ctrl={ref_has_ctrl} has_whitespace={ref_has_inner_space}",
                "info",
            )

            if not ref_raw.startswith("asset://"):
                resolved_public_ref = ref_raw
                if not ref_is_http:
                    _debug_log(
                        f"[ark-seedance] private-asset mode requires public URL; trying to resolve upload path | "
                        f"ref_preview={_strip_query_from_log_url(ref_raw)[:300]}",
                        "info",
                    )
                    resolved_candidate = await self._resolve_ref_for_api_async(
                        ref_image,
                        force_data_uri_for_local=False,
                        prefer_public_upload_url=True,
                    )
                    resolved_public_ref = str(resolved_candidate or "").strip()

                if not str(resolved_public_ref or "").lower().startswith(("http://", "https://")):
                    return {
                        "error": "Ark private avatar asset mode requires a publicly accessible HTTP(S) reference image URL"
                    }
                asset_rebuild_source_url = str(resolved_public_ref or "").strip()

                try:
                    rebuilt_asset_uri = await _register_private_asset_from_public_url(resolved_public_ref, project_name, primary_asset_type)
                    if not rebuilt_asset_uri:
                        return {"error": "Failed to register Ark private avatar asset from reference URL"}
                    asset_id_or_url = rebuilt_asset_uri
                except Exception as e:
                    return {"error": f"Private avatar asset flow raised exception: {e}"}
            else:
                try:
                    asset_id = _extract_asset_id_from_uri(ref_raw)
                    if not asset_id:
                        return {"error": "Invalid asset URI for Ark private avatar mode"}

                    resolved_asset = None
                    try:
                        resolved_asset = _get_asset_info(asset_id, project_name)
                    except Exception:
                        resolved_asset = None

                    status = str(
                        (resolved_asset or {}).get("Status")
                        or (resolved_asset or {}).get("status")
                        or (resolved_asset or {}).get("Asset", {}).get("Status")
                        or (resolved_asset or {}).get("Asset", {}).get("status")
                        or ""
                    ).strip().lower()
                    if status in {"active", "ready", "success", "completed"}:
                        asset_id_or_url = ref_raw
                    else:
                        # Recovery path: stale asset IDs may belong to another project.
                        # Try to discover source URL and re-register into current project.
                        discovered_source_url = ""
                        candidate_projects = [
                            str(tool_conf.get("asset_source_project") or "").strip(),
                            "default",
                            "",
                        ]
                        for candidate_project in candidate_projects:
                            if candidate_project == project_name:
                                continue
                            try:
                                info = _get_asset_info(asset_id, candidate_project if candidate_project else None)
                            except Exception:
                                continue
                            source_url = str(
                                info.get("URL")
                                or info.get("Url")
                                or info.get("Asset", {}).get("URL")
                                or info.get("Asset", {}).get("Url")
                                or ""
                            ).strip()
                            if source_url.lower().startswith(("http://", "https://")):
                                discovered_source_url = source_url
                                break

                        if not discovered_source_url:
                            fallback_source_keys = [
                                "asset_source_url",
                                "reference_image_url",
                                "source_image_url",
                                "image_url",
                            ]
                            for key in fallback_source_keys:
                                value = str(tool_conf.get(key) or "").strip()
                                if value.lower().startswith(("http://", "https://")):
                                    discovered_source_url = value
                                    break

                        if not discovered_source_url:
                            return {
                                "error": f"Ark private asset not found in project '{project_name}' and no fallback source URL for rebuild",
                                "submit_failed": True,
                            }

                        rebuilt_asset_uri = await _register_private_asset_from_public_url(discovered_source_url, project_name, primary_asset_type)
                        if not rebuilt_asset_uri:
                            return {
                                "error": "Ark private asset rebuild failed after missing asset detection",
                                "submit_failed": True,
                            }
                        asset_rebuild_source_url = discovered_source_url
                        asset_id_or_url = rebuilt_asset_uri
                except Exception as e:
                    return {"error": f"Ark private asset validation failed: {e}", "submit_failed": True}

        asset_image_refs: List[str] = []
        asset_rebuild_source_urls: List[str] = []
        asset_ref_types: List[str] = []
        if str(asset_id_or_url or "").strip():
            asset_image_refs.append(str(asset_id_or_url or "").strip())
            asset_rebuild_source_urls.append(str(asset_rebuild_source_url or "").strip())
            asset_ref_types.append(primary_asset_type)

        # Process additional reference media and append them to payload.
        for extra_ref in extra_ref_images:
            extra_raw = str(extra_ref or "").strip()
            if not extra_raw:
                continue
            extra_asset_type = _guess_ark_asset_type(extra_ref)

            try:
                resolved_extra = await self._resolve_ref_for_api_async(
                    extra_raw,
                    force_data_uri_for_local=False,
                    prefer_public_upload_url=True,
                )
                if resolved_extra:
                    extra_raw = str(resolved_extra or "").strip()
                    if extra_asset_type == "Image":
                        extra_asset_type = _guess_ark_asset_type(extra_raw)
            except Exception:
                pass

            if not extra_raw:
                continue

            extra_asset_ref = extra_raw
            extra_source_url = ""
            if not extra_raw.startswith("asset://"):
                if extra_raw.lower().startswith(("http://", "https://")):
                    extra_source_url = extra_raw
                    try:
                        rebuilt_extra_asset = await _register_private_asset_from_public_url(extra_raw, project_name, extra_asset_type)
                        if rebuilt_extra_asset:
                            extra_asset_ref = rebuilt_extra_asset
                    except Exception:
                        # Keep direct URL as fallback for this reference.
                        extra_asset_ref = extra_raw
                else:
                    continue

            asset_image_refs.append(str(extra_asset_ref or "").strip())
            asset_rebuild_source_urls.append(str(extra_source_url or "").strip())
            asset_ref_types.append(extra_asset_type)

        if reference_video_urls_list:
            _debug_log(
                f"[ark-seedance] processing reference videos | count={len(reference_video_urls_list)}",
                "info",
            )
        for video_ref in reference_video_urls_list:
            video_raw = str(video_ref or "").strip()
            if not video_raw:
                continue
            video_asset_type = "Video"

            try:
                resolved_video = await self._resolve_ref_for_api_async(
                    video_raw,
                    force_data_uri_for_local=False,
                    prefer_public_upload_url=True,
                )
                if resolved_video:
                    video_raw = str(resolved_video or "").strip()
            except Exception:
                pass

            if not video_raw:
                continue

            video_asset_ref = video_raw
            video_source_url = ""
            if not video_raw.startswith("asset://"):
                if not video_raw.lower().startswith(("http://", "https://")):
                    return {
                        "error": "Ark private avatar asset mode requires a publicly accessible HTTP(S) reference video URL",
                        "submit_failed": True,
                    }
                video_source_url = video_raw
                try:
                    rebuilt_video_asset = await _register_private_asset_from_public_url(video_raw, project_name, video_asset_type)
                    if not rebuilt_video_asset:
                        return {
                            "error": f"Failed to register Ark private video asset from reference URL: {_strip_query_from_log_url(video_raw)[:200]}",
                            "submit_failed": True,
                        }
                    video_asset_ref = rebuilt_video_asset
                except Exception as register_err:
                    return {
                        "error": f"Private video asset flow raised exception: {register_err}",
                        "submit_failed": True,
                    }

            asset_image_refs.append(str(video_asset_ref or "").strip())
            asset_rebuild_source_urls.append(str(video_source_url or "").strip())
            asset_ref_types.append(video_asset_type)

        if reference_audio_urls_list:
            _debug_log(
                f"[ark-seedance] processing reference audios | count={len(reference_audio_urls_list)}",
                "info",
            )
        for audio_ref in reference_audio_urls_list:
            audio_raw = str(audio_ref or "").strip()
            if not audio_raw:
                continue
            audio_asset_type = "Audio"

            try:
                resolved_audio = await self._resolve_ref_for_api_async(
                    audio_raw,
                    force_data_uri_for_local=False,
                    prefer_public_upload_url=True,
                )
                if resolved_audio:
                    audio_raw = str(resolved_audio or "").strip()
            except Exception:
                pass

            if not audio_raw:
                continue

            audio_asset_ref = audio_raw
            audio_source_url = ""
            if not audio_raw.startswith("asset://"):
                if not audio_raw.lower().startswith(("http://", "https://")):
                    return {
                        "error": "Ark private asset mode requires a publicly accessible HTTP(S) reference audio URL",
                        "submit_failed": True,
                    }
                audio_source_url = audio_raw
                try:
                    rebuilt_audio_asset = await _register_private_asset_from_public_url(audio_raw, project_name, audio_asset_type)
                    if not rebuilt_audio_asset:
                        return {
                            "error": f"Failed to register Ark private audio asset from reference URL: {_strip_query_from_log_url(audio_raw)[:200]}",
                            "submit_failed": True,
                        }
                    audio_asset_ref = rebuilt_audio_asset
                except Exception as register_err:
                    return {
                        "error": f"Private audio asset flow raised exception: {register_err}",
                        "submit_failed": True,
                    }

            asset_image_refs.append(str(audio_asset_ref or "").strip())
            asset_rebuild_source_urls.append(str(audio_source_url or "").strip())
            asset_ref_types.append(audio_asset_type)

        asset_image_refs = [item for item in asset_image_refs if item]
        if not asset_image_refs:
            return {"error": "seedance 2.0 requires at least one valid image or video reference"}
                
        # Fire the generation task
        inner_conf = tool_conf
        task_endpoint_raw = config.get("base_url") or inner_conf.get("base_url") or config.get("endpoint") or inner_conf.get("endpoint") or "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"

        raw_callback_url = str(
            tool_conf.get("_provider_callback_url")
            or tool_conf.get("callback_url")
            or tool_conf.get("callbackUrl")
            or tool_conf.get("callBackUrl")
            or tool_conf.get("webHook")
            or ""
        ).strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or "ark-seedance-video"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url:
            callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        if callback_url and callback_url != raw_callback_url:
            logger.info(
                "Ark Seedance callback auto-assigned | ticket=%s callback_url=%s raw_callback=%s",
                callback_ticket,
                callback_url,
                raw_callback_url or None,
            )
        
        # Private avatar assets are account/project scoped in Volcengine.
        # To avoid cross-vendor context mismatch (asset created via AK/SK on Ark,
        # but generation sent through third-party proxy), always submit directly
        # to native Ark endpoint for ark-seedance flow.
        if (
            "zlhub" in str(task_endpoint_raw or "").lower()
            or "zhonglian" in str(task_endpoint_raw or "").lower()
            or "proxy/ark" in str(task_endpoint_raw or "").lower()
        ):
            _debug_log(
                f"[ark-seedance] force native Ark endpoint for private assets | from={task_endpoint_raw}",
                "warning",
            )
            task_endpoint_raw = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"

        task_endpoint = self._normalize_doubao_video_tasks_endpoint(task_endpoint_raw)
        
        # Smart Model: ZLHub prefers base_model. Native requires actual model.
        if "zlhub" in task_endpoint.lower() or "zhonglian" in task_endpoint.lower():
            model_id = config.get("base_model") or inner_conf.get("base_model") or config.get("model") or inner_conf.get("model", "")
        else:
            model_id = config.get("model") or inner_conf.get("model") or config.get("base_model") or inner_conf.get("base_model", "")

        if not model_id or model_id in ["default", ""]:
            model_id = "doubao-seedance-2-0-260128"
            
        # Ensure the prompt references media assets to satisfy Volcengine requirement
        final_prompt = prompt
        prompt_lower = final_prompt.lower()
        if (
            "图片" not in final_prompt
            and "素材" not in final_prompt
            and "视频" not in final_prompt
            and "@video" not in prompt_lower
        ):
            if reference_video_urls_list and not ref_image:
                final_prompt = "视频1中，" + final_prompt
            else:
                final_prompt = "图片1中，" + final_prompt

        ref_url_kind = "asset"
        ref_has_token = False
        ref_log_url = ""
        try:
            ref_raw = str(asset_id_or_url or "").strip()
            if ref_raw.startswith("asset://"):
                ref_url_kind = "asset"
                ref_log_url = ref_raw
            elif ref_raw.startswith("data:"):
                ref_url_kind = "data_uri"
                ref_log_url = "data:image/..."
            elif ref_raw.lower().startswith(("http://", "https://")):
                import urllib.parse

                ref_url_kind = "http"
                ref_log_url = _strip_query_from_log_url(ref_raw)
                parsed = urllib.parse.urlparse(ref_raw)
                q = urllib.parse.parse_qs(parsed.query or "", keep_blank_values=True)
                ref_has_token = any(k.lower() in {"token", "e", "x-oss-signature", "x-amz-signature"} for k in q.keys())
            else:
                ref_url_kind = "other"
                ref_log_url = ref_raw[:120]
        except Exception:
            ref_url_kind = "unknown"
            ref_log_url = _strip_query_from_log_url(str(asset_id_or_url or ""))

        _debug_log(
            f"[ark-seedance] pre-submit reference image | kind={ref_url_kind} has_token={ref_has_token} url={ref_log_url}",
            "info",
        )
        _debug_log(
            f"[ark-seedance] submit context | project_name={project_name} endpoint={task_endpoint} asset_ref={asset_id_or_url}",
            "info",
        )

        content_items: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": final_prompt
            }
        ]
        for idx, image_ref in enumerate(asset_image_refs):
            ref_type = asset_ref_types[idx] if idx < len(asset_ref_types) else "Image"
            content_items.append(_build_ark_reference_content(image_ref, ref_type))

        if last_frame_url and str(last_frame_url).strip():
            content_items.append(_build_ark_reference_content(str(last_frame_url).strip(), "Image"))

        task_payload = {
            "model": model_id,
            "content": content_items,
            "return_last_frame": True,
            "generate_audio": self._normalize_bool_value(tool_conf.get("generate_audio"), default=True),
            "watermark": self._normalize_bool_value(tool_conf.get("watermark"), default=True)
        }
        is_draft_mode = self._normalize_bool_value(tool_conf.get("draft_mode") or tool_conf.get("draft"))
        requested_res = str(tool_conf.get("resolution") or tool_conf.get("video_resolution") or "").strip()
        if is_draft_mode:
            task_payload["resolution"] = "480p"
        elif requested_res:
            task_payload["resolution"] = requested_res if requested_res.lower().endswith("p") else f"{requested_res}p"
        else:
            task_payload["resolution"] = "720p"
        if callback_url and callback_url != "-1":
            task_payload["callback_url"] = callback_url
        
        if duration is not None:
            try:
                task_payload["duration"] = int(duration)
            except:
                pass
        
        # Seedance task create: ratio mirrors aspect_ratio (same value).
        final_ratio = self._normalize_aspect_ratio_value(aspect_ratio) or "16:9"
        task_payload["ratio"] = final_ratio
            
        task_headers = {
            "Authorization": f"Bearer {dp_token}",
            "Content-Type": "application/json"
        }
        
        _debug_log(
            f"Submitting seedance 2.0 generation (task create) -> {task_endpoint} | callback_enabled={bool(task_payload.get('callback_url'))}",
            "info",
        )
        extra_metadata = {"provider": "ark-seedance", "model": model_id}
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"})
        
        provider_payload_callback = tool_conf.get("_provider_payload_callback")
        if not callable(provider_payload_callback):
            provider_payload_callback = None

        try:
            ark_poll_timeout_seconds = int(tool_conf.get("poll_timeout_seconds") or tool_conf.get("timeout") or 1200)
            ark_poll_timeout_seconds = min(1800, max(300, ark_poll_timeout_seconds))
        except Exception:
            ark_poll_timeout_seconds = 1200

        first_result = await self._submit_and_poll_video(
            url=task_endpoint,
            payload=task_payload,
            api_key=dp_token,
            log_tag="ark-seedance",
            extra_metadata=extra_metadata,
            poll_timeout_seconds=ark_poll_timeout_seconds,
            pure_callback_mode=pure_callback_mode,
            callback_enabled=callback_enabled,
            callback_ticket=callback_ticket,
            callback_url=callback_url,
            provider_payload_callback=provider_payload_callback,
        )
        first_payload = first_result if isinstance(first_result, dict) else {}
        failure_text = self._flatten_text(first_payload).lower()
        missing_asset_match = re.search(r"content\[(\d+)\]\.(?:image_url|video_url|audio_url)\.url", failure_text)
        failed_payload_index = int(missing_asset_match.group(1)) if missing_asset_match else 1
        failed_ref_index = max(0, failed_payload_index - 1)
        rebuild_source_for_failed_ref = ""
        if 0 <= failed_ref_index < len(asset_rebuild_source_urls):
            rebuild_source_for_failed_ref = str(asset_rebuild_source_urls[failed_ref_index] or "").strip()
        failed_ref_type = asset_ref_types[failed_ref_index] if 0 <= failed_ref_index < len(asset_ref_types) else "Image"
        asset_not_found = (
            "specified asset" in failure_text
            and "is not found" in failure_text
            and ("image_url.url" in failure_text or "video_url.url" in failure_text or "audio_url.url" in failure_text)
        )
        if asset_not_found and rebuild_source_for_failed_ref.lower().startswith(("http://", "https://")):
            try:
                _debug_log(
                    "[ark-seedance] submit failed with missing asset; rebuilding private asset and retrying once",
                    "warning",
                )
                project_candidates = _collect_project_candidates()
                attempted_projects: List[str] = []
                for candidate_project in project_candidates:
                    attempted_projects.append(candidate_project)
                    rebuilt_asset_uri = await _register_private_asset_from_public_url(rebuild_source_for_failed_ref, candidate_project, failed_ref_type)
                    if not rebuilt_asset_uri:
                        continue

                    if 0 <= failed_payload_index < len(task_payload.get("content") or []):
                        task_payload["content"][failed_payload_index] = _build_ark_reference_content(rebuilt_asset_uri, failed_ref_type)
                    retry_result = await self._submit_and_poll_video(
                        url=task_endpoint,
                        payload=task_payload,
                        api_key=dp_token,
                        log_tag="ark-seedance",
                        extra_metadata=extra_metadata,
                        poll_timeout_seconds=ark_poll_timeout_seconds,
                        pure_callback_mode=pure_callback_mode,
                        callback_enabled=callback_enabled,
                        callback_ticket=callback_ticket,
                        callback_url=callback_url,
                        provider_payload_callback=provider_payload_callback,
                    )
                    retry_payload = retry_result if isinstance(retry_result, dict) else {}
                    if retry_payload.get("url") or retry_payload.get("video_url"):
                        _debug_log(
                            f"[ark-seedance] missing-asset retry succeeded | project={candidate_project}",
                            "warning",
                        )
                        return retry_result
                    retry_failure = self._flatten_text(retry_payload).lower()
                    if not ("specified asset" in retry_failure and "is not found" in retry_failure):
                        return retry_result

                if attempted_projects:
                    first_payload["diagnostic"] = {
                        "project_candidates": attempted_projects,
                        "hint": "asset not found across candidate projects; verify AK/SK account and EP token belong to same Volcengine account/project",
                    }

                # Final fallback: submit with original public URL directly to
                # separate "asset visibility" failures from content-policy issues.
                direct_ref_url = rebuild_source_for_failed_ref
                if direct_ref_url.lower().startswith(("http://", "https://")):
                    logger.warning("Ark Seedance fallback to direct URL submit after asset rebuild failures")
                    if 0 <= failed_payload_index < len(task_payload.get("content") or []):
                        task_payload["content"][failed_payload_index] = _build_ark_reference_content(direct_ref_url, failed_ref_type)
                    direct_result = await self._submit_and_poll_video(
                        url=task_endpoint,
                        payload=task_payload,
                        api_key=dp_token,
                        log_tag="ark-seedance",
                        extra_metadata=extra_metadata,
                        poll_timeout_seconds=ark_poll_timeout_seconds,
                        pure_callback_mode=pure_callback_mode,
                        callback_enabled=callback_enabled,
                        callback_ticket=callback_ticket,
                        callback_url=callback_url,
                        provider_payload_callback=provider_payload_callback,
                    )
                    direct_payload = direct_result if isinstance(direct_result, dict) else {}
                    if direct_payload.get("url") or direct_payload.get("video_url"):
                        return direct_result
                    direct_failure = self._flatten_text(direct_payload).lower()
                    if "specified asset" not in direct_failure or "is not found" not in direct_failure:
                        return direct_result
            except Exception as rebuild_err:
                logger.warning("Ark Seedance missing-asset retry failed | error=%s", str(rebuild_err)[:300])

        return first_result
    def _classify_media_retry(self, result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = result if isinstance(result, dict) else {}
        has_output = bool(payload.get("url")) or bool(payload.get("video_url"))
        ambiguous_submit = bool(payload.get("ambiguous_submit"))
        submit_failed = bool(payload.get("submit_failed"))
        has_error = bool(payload.get("error"))

        # Content policy / moderation denials are deterministic and should not
        # trigger provider fallback loops.
        failure_text = self._flatten_text(payload).lower()
        non_retryable_markers = (
            "output_moderation",
            "moderation blocked",
            "moderation blocked reference material",
            "inputimagesensitivecontentdetected.privacyinformation",
            "may contain real person",
            "contain real person",
            "privacyinformation",
            "content policy",
            "policy violation",
            "safety violation",
            "unsafe content",
            "内容审核",
            "审核拦截",
            "隐私信息",
            "违规",
        )
        if any(marker in failure_text for marker in non_retryable_markers):
            return {"retryable": False, "reason": "policy_blocked", "has_output": False}

        if has_output:
            return {"retryable": False, "reason": "success", "has_output": True}
        if ambiguous_submit:
            return {"retryable": False, "reason": "ambiguous_submit", "has_output": False}
        if submit_failed:
            return {"retryable": True, "reason": "submit_failed", "has_output": False}
        if has_error:
            return {"retryable": True, "reason": "generation_failed", "has_output": False}
        return {"retryable": True, "reason": "no_output", "has_output": False}

    def _enforce_no_watermark_payload(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._enforce_no_watermark_payload(item) for item in value]

        if not isinstance(value, dict):
            return value

        normalized: Dict[str, Any] = {}
        for key, item in value.items():
            lower_key = str(key or "").strip().lower()

            if lower_key == "remove_watermark":
                normalized[key] = True
                continue

            if lower_key in {"watermark", "water_mark"}:
                if isinstance(item, bool) or item is None:
                    normalized[key] = False
                elif isinstance(item, (int, float)):
                    normalized[key] = 0
                else:
                    normalized[key] = ""
                continue

            if lower_key == "watermark_text":
                normalized[key] = ""
                continue

            if lower_key in {"logoadd", "logo_add"}:
                normalized[key] = 0
                continue

            if lower_key == "add_logo":
                normalized[key] = False
                continue

            if lower_key == "logo_info":
                logo_info = item if isinstance(item, dict) else {}
                normalized[key] = {
                    **self._enforce_no_watermark_payload(logo_info),
                    "add_logo": False,
                }
                continue

            normalized[key] = self._enforce_no_watermark_payload(item)

        return normalized

    def _merge_negative_prompt(self, prompt: Any, negative_prompt: Any) -> str:
        base_prompt = str(prompt or "").strip()
        neg = str(negative_prompt or "").strip()
        if not neg:
            return base_prompt

        suffix = f"Negative Prompt: {neg}"
        if not base_prompt:
            return suffix

        lower_base = base_prompt.lower()
        if "negative prompt:" in lower_base and neg.lower() in lower_base:
            return base_prompt

        stripped = re.sub(r"\n\nnegative prompt:\s*[\s\S]*$", "", base_prompt, flags=re.IGNORECASE).rstrip()
        return f"{stripped}\n\n{suffix}"

    def _looks_like_scene_subject_placeholder_prompt(self, prompt: Any) -> bool:
        text = str(prompt or "").strip().lower()
        if not text:
            return False
        return (
            "auto-created placeholder from scene subject reference" in text
            and "subject type:" in text
            and ("core scene info:" in text or "original script text:" in text)
        )

    def _extract_structured_prompt_field(self, prompt: Any, label: str) -> str:
        text = str(prompt or "")
        if not text:
            return ""
        prefix = f"{str(label or '').strip().lower()}:"
        for block in re.split(r"\n\\s*\n", text):
            stable_block = str(block or "").strip()
            if not stable_block:
                continue
            lower_block = stable_block.lower()
            if lower_block.startswith(prefix):
                return stable_block.split(":", 1)[1].strip()
        return ""

    def _cleanup_prompt_grounding_text(self, value: Any, limit: int = 420) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        cleaned = text.replace("\r", "\n").replace("<br>", " ")
        cleaned = cleaned.replace("`", "")
        cleaned = cleaned.replace("**", "")
        cleaned = re.sub(r"\{([^{}]+)\}", r"\1", cleaned)
        cleaned = re.sub(r"\b(?:CHAR|PROP|ENV|VEFX|SFX)\s*:\s*\[\s*@?([^\]\(]+)\s*\]\s*\(([^)]*)\)", r"\1", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(?:CHAR|PROP|ENV|VEFX|SFX)\s*:\s*\[\s*@?([^\]]+)\s*\]", r"\1", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\([^)]*ref_image_url\s*:[^)]*\)", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")

        if len(cleaned) <= limit:
            return cleaned

        truncated = cleaned[:limit].rsplit(" ", 1)[0].strip()
        return f"{truncated or cleaned[:limit].strip()}..."

    def _sanitize_kie_placeholder_prompt(self, prompt: Any, subject_type: Optional[str] = None, subject_name: Optional[str] = None) -> str:
        raw_prompt = str(prompt or "").strip()
        if not self._looks_like_scene_subject_placeholder_prompt(raw_prompt):
            return raw_prompt

        resolved_type = str(subject_type or self._extract_structured_prompt_field(raw_prompt, "Subject Type") or "subject").strip().lower()
        resolved_name = self._cleanup_prompt_grounding_text(subject_name, limit=80)
        source_scene = self._cleanup_prompt_grounding_text(self._extract_structured_prompt_field(raw_prompt, "Source Scene"), limit=80)
        source_scene_name = self._cleanup_prompt_grounding_text(self._extract_structured_prompt_field(raw_prompt, "Source Scene Name"), limit=120)
        scene_environment = self._cleanup_prompt_grounding_text(self._extract_structured_prompt_field(raw_prompt, "Scene Environment"), limit=160)
        core_scene_info = self._cleanup_prompt_grounding_text(self._extract_structured_prompt_field(raw_prompt, "Core Scene Info"), limit=380)
        original_script = self._cleanup_prompt_grounding_text(self._extract_structured_prompt_field(raw_prompt, "Original Script Text"), limit=260)

        scene_label = source_scene_name or source_scene
        grounding_parts: List[str] = []
        if scene_environment:
            grounding_parts.append(f"Environment anchor: {scene_environment}.")
        if scene_label:
            grounding_parts.append(f"Source scene: {scene_label}.")
        if core_scene_info:
            grounding_parts.append(f"Visual grounding: {core_scene_info}.")
        if original_script:
            grounding_parts.append(f"Script grounding: {original_script}.")

        subject_label = resolved_name or "the referenced subject"
        if resolved_type in {"environment", "env"}:
            prefix = f"Cinematic environment reference still for {subject_label}. Preserve stable space identity, composition anchors, materials, and lighting."
            suffix = "No characters unless essential to the location. No dialogue text, captions, markdown, labels, or storyboard notes."
        elif resolved_type in {"prop", "object"}:
            prefix = f"Cinematic prop reference still for {subject_label}. Focus on the object design, materials, silhouette, and reusable production details."
            suffix = "Single clear asset focus. No extra hands, no captions, no markdown, no layout notes."
        else:
            prefix = f"Cinematic character reference still for {subject_label}. Focus on stable identity, wardrobe, silhouette, and screen-ready realism."
            suffix = "Single primary subject. No captions, no markdown, no split layout, no storyboard notes."

        sanitized = " ".join([prefix] + grounding_parts + [suffix]).strip()
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        if len(sanitized) > 900:
            sanitized = sanitized[:900].rsplit(" ", 1)[0].strip() + "..."
        return sanitized

    def _is_grsai_quota_or_throttle_error(self, payload: Any) -> bool:
        text = self._flatten_text(payload).lower()
        markers = [
            "resource_exhausted",
            "public_error_user_requests_throttled",
            "quota",
            "throttle",
            "429",
            "too many requests",
            "exhausted",
        ]
        return any(marker in text for marker in markers)

    def _is_n1n_capacity_error(self, payload: Any) -> bool:
        text = self._flatten_text(payload).lower()
        markers = [
            "insufficient_user_quota",
            "当前分组上游负载已饱和",
            "负载已饱和",
            "quota",
            "429",
            "too many requests",
        ]
        return any(marker in text for marker in markers)

    def _build_n1n_mirror_urls(self, url: str) -> List[str]:
        primary = str(url or "").strip()
        if not primary:
            return []

        candidates: List[str] = [primary]
        replacements = [
            ("://api.n1n.ai", "://hk.n1n.ai"),
            ("://hk.n1n.ai", "://api.n1n.ai"),
        ]
        for source, target in replacements:
            if source in primary:
                mirror = primary.replace(source, target, 1)
                if mirror not in candidates:
                    candidates.append(mirror)
        return candidates

    def _is_retryable_proxy_fallback_error(self, error: Any) -> bool:
        if isinstance(error, requests.exceptions.ProxyError):
            return True

        text = self._flatten_text(error).lower()
        proxy_markers = [
            "proxyerror",
            "cannot connect to proxy",
            "proxy authentication",
            "tunnel connection failed",
            "407 proxy",
            "https proxy",
            "http proxy",
        ]
        if any(marker in text for marker in proxy_markers):
            return True

        if isinstance(error, requests.exceptions.SSLError):
            ssl_proxy_markers = [
                "wrong version number",
                "tlsv1 alert",
                "certificate verify failed",
            ]
            return any(marker in text for marker in ssl_proxy_markers)

        return False

    def _is_ambiguous_submit_transport_error(self, provider_name: str, log_tag: str, error: Any) -> bool:
        if error is None or self._is_retryable_proxy_fallback_error(error):
            return False

        text = self._flatten_text(error).lower()
        markers = [
            "remotedisconnected",
            "remote end closed connection without response",
            "unexpected_eof_while_reading",
            "ssleoferror",
            "connection reset by peer",
            "connection aborted",
            "connection closed",
            "broken pipe",
            "read timed out",
            "readtimeout",
            "timed out",
            "10054",
            "unexpected eof",
        ]
        if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return True
        if isinstance(error, requests.exceptions.SSLError):
            return any(marker in text for marker in markers)
        return any(marker in text for marker in markers)

    def _extract_openai_compatible_image_output(self, data: Any) -> Optional[str]:
        if isinstance(data, dict):
            data_items = data.get("data")
            if isinstance(data_items, list):
                for item in data_items:
                    if not isinstance(item, dict):
                        continue
                    url_value = str(item.get("url") or "").strip()
                    if url_value:
                        return url_value
                    b64_value = str(item.get("b64_json") or "").strip()
                    if b64_value:
                        output_format = str(data.get("output_format") or item.get("output_format") or "png").strip().lower() or "png"
                        if output_format == "jpg":
                            output_format = "jpeg"
                        return f"data:image/{output_format};base64,{b64_value}"

            direct_url = str(data.get("url") or "").strip()
            if direct_url:
                return direct_url

        return None

    def _extract_any_image_output(self, value: Any) -> Optional[str]:
        direct = self._extract_openai_compatible_image_output(value)
        if direct:
            return direct

        if isinstance(value, dict):
            for key in ("url", "image", "image_url", "imageUrl", "result_url", "resultUrl"):
                candidate = str(value.get(key) or "").strip()
                if candidate:
                    return candidate
            for key in ("content", "result", "output", "outputs", "data", "images", "items", "results", "response"):
                found = self._extract_any_image_output(value.get(key))
                if found:
                    return found
            for nested in value.values():
                found = self._extract_any_image_output(nested)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = self._extract_any_image_output(item)
                if found:
                    return found
        elif isinstance(value, str):
            raw = value.strip()
            if raw.startswith("data:image/") or raw.lower().startswith(("http://", "https://")):
                return raw

        return None

    def _resolve_common_post_timeout(self, provider_name: str, log_tag: str, timeout: Optional[int]) -> int:
        if timeout is not None:
            try:
                return max(30, int(timeout))
            except Exception:
                pass

        normalized_provider = str(provider_name or "").strip().lower()
        normalized_tag = str(log_tag or "").strip().lower()
        if normalized_provider == "n1n" and normalized_tag == "n1n_image":
            return DEFAULT_N1N_IMAGE_READ_TIMEOUT_SECONDS
        return 60

    def _should_prefer_no_proxy(self, provider_name: str, log_tag: str) -> bool:
        normalized_provider = str(provider_name or "").strip().lower()
        normalized_tag = str(log_tag or "").strip().lower()
        return normalized_provider == "n1n" and normalized_tag in {"n1n_image", "n1n_gemini_image"}

    def _build_transport_headers(self, provider_name: str, log_tag: str, api_key: str, payload: Any) -> Dict[str, Any]:
        headers: Dict[str, Any] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        normalized_provider = str(provider_name or "").strip().lower()
        normalized_tag = str(log_tag or "").strip().lower()
        if normalized_provider == "n1n" and normalized_tag in {"n1n_image", "n1n_gemini_image"}:
            try:
                payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            except Exception:
                payload_text = str(payload)
            payload_digest = hashlib.sha256(payload_text.encode("utf-8", errors="ignore")).hexdigest()[:32]
            headers["Connection"] = "close"
            headers["Accept-Encoding"] = "identity"
            headers["X-Request-Id"] = f"{normalized_provider}-{normalized_tag}-{payload_digest}"
            headers["Idempotency-Key"] = payload_digest

        return headers

    def _build_ambiguous_submit_result(self, provider_name: str, log_tag: str, error: Any, submit_url: str, extra_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized_provider = str(provider_name or "").strip().lower()
        normalized_tag = str(log_tag or "").strip().lower()
        details = str(error or "").strip()
        if normalized_provider == "n1n" and normalized_tag == "n1n_image":
            user_error = "n1n 图像请求在上游响应前断开，接口无法确认结果；上游可能已经受理并扣费，系统未自动重试以避免重复生图"
        else:
            user_error = "Upstream request status unknown; provider may have accepted the request"

        metadata = {
            **(extra_metadata or {}),
            "submit_url": submit_url,
            "ambiguous_submit": True,
        }
        return {
            "error": user_error,
            "details": details,
            "submit_failed": False,
            "ambiguous_submit": True,
            "retry_safe": False,
            "failure_reason": "ambiguous_submit_transport",
            "metadata": metadata,
        }

    def _post_json_request(self, target_url: str, payload: Any, headers: Dict[str, Any], timeout_pair: Any, verify: bool = False, use_proxy: bool = True):
        if use_proxy:
            return requests.post(target_url, json=payload, headers=headers, timeout=timeout_pair, verify=verify)

        with requests.Session() as session:
            session.trust_env = False
            return session.post(target_url, json=payload, headers=headers, timeout=timeout_pair, verify=verify)

    def _normalize_doubao_size(self, width: Any, height: Any) -> Optional[str]:
        try:
            w = int(width)
            h = int(height)
        except Exception:
            return None

        if w <= 0 or h <= 0:
            return None

        pixels = w * h
        if pixels >= self.DOUBAO_MIN_IMAGE_PIXELS:
            return f"{w}x{h}"

        scale = math.sqrt(self.DOUBAO_MIN_IMAGE_PIXELS / float(pixels))
        new_w = max(1, int(math.ceil(w * scale)))
        new_h = max(1, int(math.ceil(h * scale)))

        # Safety loop against rounding edge cases
        while new_w * new_h < self.DOUBAO_MIN_IMAGE_PIXELS:
            if new_w <= new_h:
                new_w += 1
            else:
                new_h += 1

        logger.info(
            "Doubao size normalized | input=%sx%s pixels=%s min_pixels=%s normalized=%sx%s",
            w, h, pixels, self.DOUBAO_MIN_IMAGE_PIXELS, new_w, new_h,
        )
        return f"{new_w}x{new_h}"

    def _normalize_doubao_video_tasks_endpoint(self, endpoint: Optional[str]) -> str:
        raw = (endpoint or "").strip()
        if not raw:
            return "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"

        normalized = raw.rstrip("/")
        if normalized.endswith("/contents/generations/tasks"):
            return normalized
        if normalized.endswith("/api/v3"):
            return f"{normalized}/contents/generations/tasks"
        if normalized.endswith("/api/v3/contents/generations"):
            return f"{normalized}/tasks"
        if normalized.endswith("/contents/generations"):
            return f"{normalized}/tasks"
        if "/api/v3" in normalized and "contents/generations/tasks" not in normalized:
            return f"{normalized}/contents/generations/tasks"
        return normalized

    def fetch_provider_task_usage(
        self,
        *,
        task_id: str,
        api_key: str,
        query_endpoint: Optional[str] = None,
        provider: Optional[str] = None,
        refresh_if_missing: bool = True,
        include_raw_response: bool = False,
    ) -> Dict[str, Any]:
        """Query provider task usage and return normalized billing fields.

        KIE Market uses: GET /api/v1/jobs/recordInfo?taskId=...
        RunningHub uses: POST /openapi/v2/query {"taskId": ...}

        When include_raw_response=True, also attach the full provider API JSON under
        key ``raw_response`` (for admin single-task inspect).
        """
        def _with_raw(usage_payload: Optional[Dict[str, Any]], raw: Any) -> Dict[str, Any]:
            out = dict(usage_payload or {})
            if include_raw_response and isinstance(raw, dict) and raw:
                out["raw_response"] = raw
            return out

        stable_task_id = str(task_id or "").strip()
        stable_key = str(api_key or "").strip()
        if not stable_task_id or not stable_key:
            return {}

        provider_l = str(provider or "").strip().lower()
        # ark-seedance stores AK:SK:EP_TOKEN; Ark HTTP APIs expect Bearer EP_TOKEN only.
        if (
            stable_key.count(":") >= 2
            and ("ark" in provider_l or "seedance" in provider_l or "volc" in provider_l or "doubao" in provider_l)
        ):
            ep_token = stable_key.split(":", 2)[2].strip()
            if ":" in ep_token:
                ep_token = ep_token.split(":", 1)[0].strip()
            if ep_token:
                stable_key = ep_token
        endpoint = str(query_endpoint or "").strip()
        if not _is_kie_record_info_endpoint(endpoint, provider_l):
            endpoint = self._normalize_doubao_video_tasks_endpoint(query_endpoint)
        headers = {"Authorization": f"Bearer {stable_key}", "Content-Type": "application/json"}

        # RunningHub: POST /openapi/v2/query  body {"taskId": "..."}
        is_runninghub = (
            "runninghub" in provider_l
            or "runninghub.cn" in str(endpoint or "").lower()
            or "/openapi/v2/query" in str(endpoint or "").lower()
        )
        if is_runninghub:
            if not endpoint:
                endpoint = "https://www.runninghub.cn/openapi/v2/query"
            elif endpoint.startswith("/"):
                endpoint = "https://www.runninghub.cn" + endpoint

            def _rh_post_once(use_proxy: bool = True):
                kwargs = {
                    "headers": headers,
                    "json": {"taskId": stable_task_id},
                    "timeout": 30,
                    "verify": False,
                }
                if not use_proxy:
                    kwargs["proxies"] = {"http": None, "https": None}
                return requests.post(endpoint, **kwargs)

            raw_payload: Dict[str, Any] = {}
            try:
                try:
                    resp = _rh_post_once(True)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                    resp = _rh_post_once(False)
                if resp is not None and getattr(resp, "status_code", None) == 200:
                    try:
                        data = resp.json() if resp.content else {}
                    except Exception:
                        data = {}
                    raw_payload = data if isinstance(data, dict) else {}

                usage = _normalize_provider_task_usage(_extract_provider_task_usage(raw_payload))
                # Keep RH usage keys even when money/coins are still null.
                if not usage and isinstance(raw_payload.get("usage"), dict):
                    usage = _normalize_provider_task_usage(dict(raw_payload.get("usage") or {})) or dict(raw_payload.get("usage") or {})

                need_retry = False
                if refresh_if_missing:
                    has_cost = False
                    probe = usage or {}
                    for key in ("consumeMoney", "consumeCoins", "thirdPartyConsumeMoney", "creditsConsumed", "kie_credits_consumed"):
                        if probe.get(key) not in (None, "") and str(probe.get(key)).strip() != "":
                            has_cost = True
                            break
                    need_retry = not has_cost

                if need_retry:
                    time.sleep(0.5)
                    try:
                        resp = _rh_post_once(True)
                    except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                        resp = _rh_post_once(False)
                    if resp is not None and getattr(resp, "status_code", None) == 200:
                        try:
                            data = resp.json() if resp.content else {}
                        except Exception:
                            data = {}
                        if isinstance(data, dict) and data:
                            raw_payload = data
                            usage = _normalize_provider_task_usage(_extract_provider_task_usage(raw_payload))
                            if not usage and isinstance(raw_payload.get("usage"), dict):
                                usage = _normalize_provider_task_usage(dict(raw_payload.get("usage") or {})) or dict(raw_payload.get("usage") or {})
            except Exception as exc:
                logger.warning(
                    "[TaskUsage] RunningHub query failed | task_id=%s error=%s",
                    stable_task_id,
                    exc,
                )
                return _with_raw({}, raw_payload) if include_raw_response else {}

            if usage:
                usage["raw_task"] = {
                    "id": raw_payload.get("taskId") or stable_task_id,
                    "status": raw_payload.get("status") or raw_payload.get("state"),
                    "model": raw_payload.get("model"),
                }
            return _with_raw(usage, raw_payload)

        is_kie = _is_kie_record_info_endpoint(endpoint, provider_l)
        endpoint_candidates = [endpoint] if endpoint else []
        if is_kie and endpoint:
            if "/recordInfo" in endpoint:
                endpoint_candidates.append(endpoint.replace("/recordInfo", "/record-info"))
            elif "/record-info" in endpoint:
                endpoint_candidates.append(endpoint.replace("/record-info", "/recordInfo"))
        # de-dupe while preserving order
        seen_endpoints = set()
        endpoint_candidates = [
            item for item in endpoint_candidates
            if item and not (item in seen_endpoints or seen_endpoints.add(item))
        ]

        def _request_once(use_proxy: bool = True):
            kwargs = {"headers": headers, "timeout": 30, "verify": False}
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}

            last_resp = None
            if is_kie:
                param_candidates = (
                    {"taskId": stable_task_id},
                    {"task_id": stable_task_id},
                    {"id": stable_task_id},
                )
                for url in endpoint_candidates:
                    for params in param_candidates:
                        try:
                            resp = requests.get(url, params=params, **kwargs)
                            last_resp = resp
                            if getattr(resp, "status_code", None) == 200:
                                return resp
                        except Exception:
                            continue
                # Fallback: some deployments accept path-style ids.
                for url in endpoint_candidates:
                    try:
                        resp = requests.get(f"{url.rstrip('/')}/{urllib.parse.quote(stable_task_id)}", **kwargs)
                        last_resp = resp
                        if getattr(resp, "status_code", None) == 200:
                            return resp
                    except Exception:
                        continue
                return last_resp

            target_url = f"{endpoint.rstrip('/')}/{urllib.parse.quote(stable_task_id)}"
            return requests.get(target_url, **kwargs)

        def _load_payload(resp) -> Dict[str, Any]:
            if not resp or getattr(resp, "status_code", None) != 200:
                return {}
            try:
                data = resp.json() if resp.content else {}
            except Exception:
                return {}
            return data if isinstance(data, dict) else {}

        raw_payload: Dict[str, Any] = {}
        try:
            try:
                resp = _request_once(True)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                resp = _request_once(False)
            raw_payload = _load_payload(resp)
            if is_kie and raw_payload and not _kie_response_looks_successful(raw_payload):
                raw_payload = {}
        except Exception as exc:
            logger.warning(
                "[TaskUsage] provider task query failed | provider=%s task_id=%s error=%s",
                provider_l or None,
                stable_task_id,
                exc,
            )
            return _with_raw({}, raw_payload) if include_raw_response else {}

        usage = _normalize_provider_task_usage(_extract_provider_task_usage(raw_payload))
        if usage or not refresh_if_missing:
            if usage:
                data_obj = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else {}
                usage["raw_task"] = {
                    "id": data_obj.get("taskId") or raw_payload.get("id") or stable_task_id,
                    "status": data_obj.get("state") or raw_payload.get("status") or raw_payload.get("state"),
                    "model": data_obj.get("model") or raw_payload.get("model"),
                }
            return _with_raw(usage, raw_payload)

        try:
            time.sleep(0.5)
            try:
                resp = _request_once(True)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                resp = _request_once(False)
            raw_payload = _load_payload(resp)
            if is_kie and raw_payload and not _kie_response_looks_successful(raw_payload):
                raw_payload = {}
            usage = _normalize_provider_task_usage(_extract_provider_task_usage(raw_payload))
        except Exception as exc:
            logger.warning(
                "[TaskUsage] provider task usage refresh failed | provider=%s task_id=%s error=%s",
                provider_l or None,
                stable_task_id,
                exc,
            )

        if usage:
            data_obj = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else {}
            usage["raw_task"] = {
                "id": data_obj.get("taskId") or raw_payload.get("id") or stable_task_id,
                "status": data_obj.get("state") or raw_payload.get("status") or raw_payload.get("state"),
                "model": data_obj.get("model") or raw_payload.get("model"),
            }
        return _with_raw(usage, raw_payload)

    def fetch_provider_task_result(
        self,
        *,
        task_id: str,
        api_key: str,
        query_endpoint: Optional[str] = None,
        provider: Optional[str] = None,
        kind: str = "image",
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """One-shot provider task query for timeout/callback-supplement recovery.

        Returns ``{url, status, raw, metadata}`` when a media URL is ready,
        ``{status, raw, pending: True}`` while still running, or ``{error, ...}``.
        """
        stable_task_id = str(task_id or "").strip()
        stable_key = str(api_key or "").strip()
        if not stable_task_id or not stable_key:
            return {"error": "missing_task_id_or_api_key"}

        provider_l = str(provider or "").strip().lower()
        kind_l = str(kind or "image").strip().lower() or "image"
        endpoint = str(query_endpoint or "").strip()
        base = str(base_url or "").strip().rstrip("/")

        # ark-seedance stores AK:SK:EP_TOKEN; Ark HTTP APIs expect Bearer EP_TOKEN only.
        if (
            stable_key.count(":") >= 2
            and ("ark" in provider_l or "seedance" in provider_l or "volc" in provider_l or "doubao" in provider_l)
        ):
            ep_token = stable_key.split(":", 2)[2].strip()
            if ":" in ep_token:
                ep_token = ep_token.split(":", 1)[0].strip()
            if ep_token:
                stable_key = ep_token

        headers = {"Authorization": f"Bearer {stable_key}", "Content-Type": "application/json"}

        def _normalize_status(value: Any) -> str:
            text = str(value or "").strip().lower()
            if text in {"success", "succeeded", "completed", "done", "finish", "finished", "complete", "successed"}:
                return "succeeded"
            if text in {"fail", "failed", "error"}:
                return "failed"
            if text in {"canceled", "cancelled"}:
                return "canceled"
            if text in {
                "waiting",
                "queued",
                "queuing",
                "processing",
                "running",
                "generating",
                "pending",
                "submitted",
                "in_progress",
                "in-progress",
            }:
                return "running"
            return text

        def _pick_url(payload: Any) -> str:
            from app.services.generation_runtime.job_store import _extract_job_result_url

            found = str(_extract_job_result_url(payload) or "").strip()
            if found:
                return found
            urls = self._extract_urls_from_payload(payload)
            if not urls:
                return ""
            if kind_l in {"video", "audio"}:
                for url in urls:
                    lower = url.lower()
                    if any(token in lower for token in (".mp4", ".mov", ".webm", "video/", ".mp3", "audio/")):
                        return url
            return urls[0]

        def _pack(raw: Dict[str, Any], *, status: str = "", url: str = "", pending: bool = False, error: str = "") -> Dict[str, Any]:
            out: Dict[str, Any] = {
                "raw": raw if isinstance(raw, dict) else {},
                "status": status or None,
                "metadata": {
                    "task_id": stable_task_id,
                    "taskId": stable_task_id,
                    "provider": provider_l or None,
                    "query_endpoint": endpoint or None,
                    "timeout_poll_recovery": True,
                },
            }
            if url:
                out["url"] = url
                out["status"] = status or "succeeded"
            if pending:
                out["pending"] = True
            if error:
                out["error"] = error
            return out

        is_runninghub = (
            "runninghub" in provider_l
            or "runninghub.cn" in str(endpoint or "").lower()
            or "/openapi/v2/query" in str(endpoint or "").lower()
        )
        is_grsai = "grsai" in provider_l or "dakka.com" in str(endpoint or base or "").lower()
        is_kie = _is_kie_record_info_endpoint(endpoint, provider_l) or (
            "kie" in provider_l and not is_runninghub and not is_grsai
        )
        is_ark = (
            "ark" in provider_l
            or "seedance" in provider_l
            or "volces.com" in str(endpoint or base or "").lower()
            or "/contents/generations/tasks" in str(endpoint or "").lower()
        )

        try:
            raw_payload: Dict[str, Any] = {}

            if is_runninghub:
                if not endpoint:
                    endpoint = "https://www.runninghub.cn/openapi/v2/query"
                elif endpoint.startswith("/"):
                    endpoint = f"{base or 'https://www.runninghub.cn'}{endpoint}"

                def _rh_post(use_proxy: bool = True):
                    kwargs = {
                        "headers": headers,
                        "json": {"taskId": stable_task_id},
                        "timeout": 30,
                        "verify": False,
                    }
                    if not use_proxy:
                        kwargs["proxies"] = {"http": None, "https": None}
                    return requests.post(endpoint, **kwargs)

                try:
                    resp = _rh_post(True)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                    resp = _rh_post(False)
                if resp is None or getattr(resp, "status_code", None) != 200:
                    return {"error": f"runninghub_http_{getattr(resp, 'status_code', None)}"}
                try:
                    raw_payload = resp.json() if resp.content else {}
                except Exception:
                    return {"error": "runninghub_invalid_json"}
                if not isinstance(raw_payload, dict):
                    return {"error": "runninghub_invalid_payload"}

                data_obj = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else {}
                status = _normalize_status(
                    raw_payload.get("status")
                    or raw_payload.get("state")
                    or data_obj.get("status")
                    or data_obj.get("state")
                )
                url = _pick_url(raw_payload)
                if url and status not in {"failed", "canceled"}:
                    return _pack(raw_payload, status="succeeded", url=url)
                if status in {"failed", "canceled"}:
                    return _pack(raw_payload, status=status, error=status)
                return _pack(raw_payload, status=status or "running", pending=True)

            if is_grsai:
                poll_url = endpoint
                if not poll_url or "recordInfo" in poll_url or "record-info" in poll_url:
                    root = base
                    if not root and endpoint:
                        root = re.sub(r"/v1/(draw|video).*$", "", endpoint, flags=re.IGNORECASE)
                        root = re.sub(r"/v1/?$", "", root).rstrip("/")
                    if not root:
                        root = "https://grsaiapi.com"
                    poll_url = f"{root}/v1/draw/result"
                endpoint = poll_url

                def _grsai_post(use_proxy: bool = True):
                    kwargs = {
                        "headers": headers,
                        "json": {"id": stable_task_id},
                        "timeout": (10, 30),
                        "verify": False,
                    }
                    if not use_proxy:
                        kwargs["proxies"] = {"http": None, "https": None}
                    return requests.post(poll_url, **kwargs)

                try:
                    resp = _grsai_post(True)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                    resp = _grsai_post(False)
                if resp is None or getattr(resp, "status_code", None) != 200:
                    return {"error": f"grsai_http_{getattr(resp, 'status_code', None)}"}
                try:
                    raw_payload = resp.json() if resp.content else {}
                except Exception:
                    return {"error": "grsai_invalid_json"}
                if not isinstance(raw_payload, dict):
                    return {"error": "grsai_invalid_payload"}

                data_block = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else raw_payload
                status = _normalize_status(
                    (data_block.get("status") if isinstance(data_block, dict) else None)
                    or raw_payload.get("status")
                )
                url = _pick_url(raw_payload)
                if url and status not in {"failed", "canceled"}:
                    if oss_storage_service.is_managed_url(url):
                        url = str(oss_storage_service.refresh_url(url) or url)
                    return _pack(raw_payload, status="succeeded", url=url)
                if status in {"failed", "canceled"}:
                    return _pack(raw_payload, status=status, error=status)
                return _pack(raw_payload, status=status or "running", pending=True)

            if is_kie:
                if not endpoint:
                    endpoint = "https://api.kie.ai/api/v1/jobs/recordInfo"
                endpoint_candidates = [endpoint]
                if "/recordInfo" in endpoint:
                    endpoint_candidates.append(endpoint.replace("/recordInfo", "/record-info"))
                elif "/record-info" in endpoint:
                    endpoint_candidates.append(endpoint.replace("/record-info", "/recordInfo"))

                def _kie_get(use_proxy: bool = True):
                    kwargs = {"headers": headers, "timeout": 45, "verify": False}
                    if not use_proxy:
                        kwargs["proxies"] = {"http": None, "https": None}
                    last_resp = None
                    param_candidates = (
                        {"taskId": stable_task_id},
                        {"task_id": stable_task_id},
                        {"id": stable_task_id},
                    )
                    for url in endpoint_candidates:
                        for params in param_candidates:
                            try:
                                resp = requests.get(url, params=params, **kwargs)
                                last_resp = resp
                                if getattr(resp, "status_code", None) == 200:
                                    return resp
                            except Exception:
                                continue
                    return last_resp

                try:
                    resp = _kie_get(True)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                    resp = _kie_get(False)
                if resp is None or getattr(resp, "status_code", None) != 200:
                    return {"error": f"kie_http_{getattr(resp, 'status_code', None)}"}
                try:
                    raw_payload = resp.json() if resp.content else {}
                except Exception:
                    return {"error": "kie_invalid_json"}
                if not isinstance(raw_payload, dict):
                    return {"error": "kie_invalid_payload"}
                if raw_payload and not _kie_response_looks_successful(raw_payload):
                    # Still try URL extraction; some deployments return non-200 business codes.
                    pass

                record_raw = raw_payload.get("data") or raw_payload.get("result") or raw_payload
                if isinstance(record_raw, list):
                    record = record_raw[0] if (record_raw and isinstance(record_raw[0], dict)) else {}
                elif isinstance(record_raw, dict):
                    record = record_raw
                else:
                    record = {}
                status = _normalize_status(
                    record.get("state") or record.get("status") or raw_payload.get("state") or raw_payload.get("status")
                )
                url = _pick_url(record.get("resultJson") if isinstance(record, dict) else None) or _pick_url(record) or _pick_url(raw_payload)
                if url and status not in {"failed", "canceled"}:
                    return _pack(raw_payload, status="succeeded", url=url)
                if status in {"failed", "canceled"}:
                    return _pack(raw_payload, status=status, error=status)
                return _pack(raw_payload, status=status or "running", pending=True)

            # Ark / Seedance / generic GET {endpoint}/{task_id}
            if not endpoint:
                if is_ark:
                    endpoint = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
                elif base:
                    endpoint = base
                else:
                    return {"error": "missing_query_endpoint"}
            endpoint = self._normalize_doubao_video_tasks_endpoint(endpoint)
            target_url = f"{endpoint.rstrip('/')}/{urllib.parse.quote(stable_task_id)}"

            def _generic_get(use_proxy: bool = True):
                kwargs = {"headers": headers, "timeout": 30, "verify": False}
                if not use_proxy:
                    kwargs["proxies"] = {"http": None, "https": None}
                return requests.get(target_url, **kwargs)

            try:
                resp = _generic_get(True)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                resp = _generic_get(False)
            if resp is None or getattr(resp, "status_code", None) != 200:
                return {"error": f"provider_http_{getattr(resp, 'status_code', None)}"}
            try:
                raw_payload = resp.json() if resp.content else {}
            except Exception:
                return {"error": "provider_invalid_json"}
            if not isinstance(raw_payload, dict):
                return {"error": "provider_invalid_payload"}

            data_obj = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else {}
            status = _normalize_status(
                raw_payload.get("status")
                or raw_payload.get("state")
                or data_obj.get("status")
                or data_obj.get("state")
            )
            url = _pick_url(raw_payload)
            if url and status not in {"failed", "canceled"}:
                return _pack(raw_payload, status="succeeded", url=url)
            if status in {"failed", "canceled"}:
                return _pack(raw_payload, status=status, error=status)
            return _pack(raw_payload, status=status or "running", pending=True)
        except Exception as exc:
            logger.warning(
                "[TimeoutPoll] provider task result query failed | provider=%s task_id=%s error=%s",
                provider_l or None,
                stable_task_id,
                exc,
            )
            return {"error": str(exc)}

    def _finalize_kie_poll_metadata(
        self,
        *,
        base_metadata: Optional[Dict[str, Any]],
        poll_data: Any,
        record: Any,
        task_id: str,
        api_key: str,
        query_url: str,
        refresh_if_missing_credits: bool = True,
    ) -> Dict[str, Any]:
        """Attach KIE recordInfo usage (creditsConsumed) for non-callback settle."""
        meta = dict(base_metadata or {})
        stable_task_id = str(task_id or "").strip()
        meta.update(
            {
                "raw": poll_data if isinstance(poll_data, dict) else {"value": poll_data},
                "task_id": stable_task_id,
                "taskId": stable_task_id,
                "query_endpoint": str(query_url or "").strip() or None,
            }
        )
        if isinstance(record, dict):
            if record.get("costTime") is not None:
                meta["taskCostTime"] = record.get("costTime")
            if record.get("completeTime") is not None:
                meta["completeTime"] = record.get("completeTime")
            if record.get("model"):
                meta["provider_task_model"] = record.get("model")

        meta = _attach_provider_usage_metadata(
            meta,
            task_payload=poll_data,
            source="kie_recordInfo",
        )
        usage = meta.get("provider_usage") if isinstance(meta.get("provider_usage"), dict) else {}
        credits = _safe_usage_float(
            (usage or {}).get("creditsConsumed")
            or (usage or {}).get("kie_credits_consumed")
            or meta.get("creditsConsumed")
        )

        if credits <= 0 and refresh_if_missing_credits and stable_task_id and api_key and query_url:
            refreshed = self.fetch_provider_task_usage(
                task_id=stable_task_id,
                api_key=api_key,
                query_endpoint=query_url,
                provider="kie",
                refresh_if_missing=True,
            )
            if refreshed:
                meta = _attach_provider_usage_metadata(
                    meta,
                    usage=refreshed,
                    source="kie_recordInfo_refresh",
                )
                logger.info(
                    "KIE recordInfo credits refresh | task_id=%s creditsConsumed=%s source=%s",
                    stable_task_id,
                    refreshed.get("creditsConsumed") or refreshed.get("kie_credits_consumed"),
                    meta.get("usage_source"),
                )
        return meta

    def _normalize_zlhub_moderation_endpoint(self, endpoint: Optional[str]) -> str:
        raw = (endpoint or "").strip()
        if not raw:
            return "https://asset.zlhub.cn/api/asset/upload/sync"
        return raw.rstrip("/")

    def _normalize_aspect_ratio_value(self, aspect_ratio: Optional[str]) -> Optional[str]:
        raw = str(aspect_ratio or "").strip()
        if not raw:
            return None
        lowered = raw.lower()
        if lowered in {"adaptive", "auto"}:
            return "adaptive"
        if raw in {"2.35:1", "2.39:1"}:
            return "21:9"
        return raw

    def _normalize_image_size_value(self, image_size: Optional[str]) -> Optional[str]:
        raw = str(image_size or "").strip().upper().replace(" ", "")
        if raw in {"1K", "2K", "4K"}:
            return raw
        return None

    def _parse_resolution_pair(self, value: Any) -> Optional[Tuple[int, int]]:
        text = str(value or "").strip().lower().replace(" ", "")
        if not text or "x" not in text:
            return None
        left, right = text.split("x", 1)
        if not left.isdigit() or not right.isdigit():
            return None
        width = int(left)
        height = int(right)
        if width <= 0 or height <= 0:
            return None
        return width, height

    def _is_valid_grsai_gpt_image_2_vip_size(self, width: int, height: int) -> bool:
        # Constraint source: Grsai gpt-image-2-vip custom pixel rule.
        if width <= 0 or height <= 0:
            return False
        if max(width, height) > 3840:
            return False
        if width % 16 != 0 or height % 16 != 0:
            return False

        short_edge = min(width, height)
        long_edge = max(width, height)
        if short_edge <= 0:
            return False
        if float(long_edge) / float(short_edge) > 3.0:
            return False

        total_pixels = width * height
        if total_pixels < 655360 or total_pixels > 8294400:
            return False
        return True

    def _parse_ratio_float(self, ratio_text: Any) -> Optional[float]:
        text = str(ratio_text or "").strip().lower()
        if not text or ":" not in text:
            return None
        left, right = text.split(":", 1)
        try:
            left_val = float(left)
            right_val = float(right)
        except Exception:
            return None
        if left_val <= 0 or right_val <= 0:
            return None
        return float(left_val) / float(right_val)

    def _pick_nearest_ratio_key(self, target_ratio: float, ratio_keys: List[str], default_key: str = "1:1") -> str:
        if target_ratio <= 0:
            return default_key

        best_key = default_key
        best_distance = None
        for ratio_key in ratio_keys:
            ratio_value = self._parse_ratio_float(ratio_key)
            if not ratio_value or ratio_value <= 0:
                continue
            # Use log distance so portrait/landscape comparisons are scale-symmetric.
            distance = abs(math.log(target_ratio) - math.log(ratio_value))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_key = ratio_key
        return best_key

    def _resolve_grsai_gpt_image_2_size(
        self,
        model: Any,
        aspect_ratio: Any,
        explicit_size: Any,
        width: Any,
        height: Any,
    ) -> Tuple[str, bool]:
        model_key = str(model or "").strip().lower().replace("/", "-").replace("_", "-")
        is_vip = "gpt-image-2-vip" in model_key

        ratio_text = str(aspect_ratio or "").strip().lower()
        if ratio_text in {"adaptive", "auto"}:
            ratio_text = "auto"

        non_vip_ratio_map = {
            "1:1": "1024x1024",
            "16:9": "1672x941",
            "9:16": "941x1672",
            "4:3": "1443x1090",
            "3:4": "1090x1443",
            "3:2": "1536x1024",
            "2:3": "1024x1536",
            "5:4": "1408x1120",
            "4:5": "1120x1408",
            "21:9": "1920x832",
            "9:21": "832x1920",
            "1:2": "896x1792",
            "2:1": "1792x896",
        }

        vip_presets_by_tier = {
            "1k": {
                "1:1": "1024x1024",
                "16:9": "1280x720",
                "9:16": "720x1280",
                "4:3": "1152x864",
                "3:4": "864x1152",
                "3:2": "1536x1024",
                "2:3": "1024x1536",
                "5:4": "1120x896",
                "4:5": "896x1120",
                "21:9": "1456x624",
                "9:21": "624x1456",
                "1:3": "688x2048",
                "3:1": "2048x688",
                "2:1": "1536x768",
                "1:2": "768x1536",
            },
            "2k": {
                "1:1": "2048x2048",
                "16:9": "2048x1152",
                "9:16": "1152x2048",
                "4:3": "2304x1728",
                "3:4": "1728x2304",
                "3:2": "2048x1360",
                "2:3": "1360x2048",
                "5:4": "2240x1792",
                "4:5": "1792x2240",
                "21:9": "2912x1248",
                "9:21": "1248x2912",
                "1:3": "1280x3840",
                "3:1": "3840x1280",
                "2:1": "3072x1536",
                "1:2": "1536x3072",
            },
            "4k": {
                "1:1": "2880x2880",
                "16:9": "3840x2160",
                "9:16": "2160x3840",
                "4:3": "3264x2448",
                "3:4": "2448x3264",
                "3:2": "3504x2336",
                "2:3": "2336x3504",
                "5:4": "3200x2560",
                "4:5": "2560x3200",
                "21:9": "3840x1648",
                "9:21": "1648x3840",
                "3:1": "3840x1280",
                "2:1": "3840x1920",
                "1:2": "1920x3840",
            },
        }

        explicit_pair = self._parse_resolution_pair(explicit_size)
        if explicit_pair:
            logger.info(
                "Grsai gpt-image-2 size follows aspect_ratio | explicit_size_ignored=%sx%s model=%s",
                explicit_pair[0],
                explicit_pair[1],
                model,
            )

        if is_vip:
            # User preference: vip defaults to 1k preset, but preserve original framing.
            ratio_key = ratio_text if ratio_text and ratio_text != "auto" else ""
            tier_map = vip_presets_by_tier["1k"]
            if ratio_key not in tier_map:
                ratio_hint = self._parse_ratio_float(ratio_key)
                if ratio_hint:
                    ratio_key = self._pick_nearest_ratio_key(ratio_hint, list(tier_map.keys()), default_key="1:1")
                else:
                    ratio_key = "1:1"
                logger.warning(
                    "Grsai gpt-image-2-vip ratio unsupported | requested=%s selected_nearest_ratio=%s",
                    str(ratio_text or ""),
                    ratio_key,
                )
            return tier_map[ratio_key], True

        ratio_hint = None
        if ratio_text and ratio_text != "auto":
            ratio_hint = self._parse_ratio_float(ratio_text)

        if ratio_hint:
            nearest_ratio = self._pick_nearest_ratio_key(ratio_hint, list(non_vip_ratio_map.keys()), default_key="1:1")
            return non_vip_ratio_map.get(nearest_ratio, "1024x1024"), True

        if ratio_text and ratio_text != "auto" and ratio_text in non_vip_ratio_map:
            return non_vip_ratio_map[ratio_text], True

        if ratio_text and ratio_text not in {"", "auto"}:
            logger.warning(
                "Grsai gpt-image-2 ratio unsupported | requested=%s fallback_ratio=1:1",
                ratio_text,
            )

        # User preference: non-vip defaults to 2k preset.
        return "2048x2048", True

    def _resolve_openai_compatible_image_size(
        self,
        model: Any,
        explicit_size: Any,
        normalized_image_size: Optional[str],
        aspect_ratio: Optional[str],
    ) -> str:
        model_lower = str(model or "").strip().lower()
        ratio_value = self._normalize_aspect_ratio_value(aspect_ratio)
        explicit_text = str(explicit_size or "").strip()
        explicit_lower = explicit_text.lower()

        if model_lower == "gpt-image-1":
            allowed_sizes = {"1024x1024", "1536x1024", "1024x1536", "auto"}
            ratio_map = {
                "1:1": "1024x1024",
                "16:9": "1536x1024",
                "9:16": "1024x1536",
                "adaptive": "auto",
            }

            if explicit_text and explicit_text in allowed_sizes:
                return explicit_text
            if explicit_lower == "auto":
                return "auto"
            mapped_from_ratio = ratio_map.get(str(ratio_value or "").strip())
            if mapped_from_ratio:
                return mapped_from_ratio
            return "1024x1024"

        size_value = normalized_image_size or "2560x1440"
        if ratio_value and not normalized_image_size:
            ratio_map = {
                "1:1": "1024x1024",
                "16:9": "1536x1024",
                "9:16": "1024x1536",
            }
            size_value = ratio_map.get(str(ratio_value).strip(), size_value)
        return explicit_text or size_value

    def _get_runninghub_image_resolution_allowed_values(self, endpoint: Any, fallback_values: Any = None) -> List[str]:
        endpoint_lower = str(endpoint or "").strip().lower()
        if not endpoint_lower:
            return self._normalize_str_list(fallback_values)

        endpoint_rules = [
            ("/openapi/v2/rhart-image-n-pro-official/text-to-image-ultra", ["4k", "8k"]),
            ("/openapi/v2/rhart-image-n-pro-official/edit-ultra", ["4k", "8k"]),
            ("/openapi/v2/seedream-v4.5/text-to-image", ["2k", "4k"]),
            ("/openapi/v2/seedream-v4.5/image-to-image", ["2k", "4k"]),
            ("/openapi/v2/seedream-v5-lite/text-to-image", ["2k", "3k"]),
            ("/openapi/v2/seedream-v5-lite/image-to-image", ["2k", "3k"]),
            ("/openapi/v2/seedream-v4/text-to-image", ["1k", "2k", "4k"]),
            ("/openapi/v2/seedream-v4/image-to-image", ["1k", "2k", "4k"]),
            ("/openapi/v2/rhart-image-n-pro-official/text-to-image", ["1k", "2k", "4k"]),
            ("/openapi/v2/rhart-image-n-pro-official/edit", ["1k", "2k", "4k"]),
            ("/openapi/v2/rhart-image-n-pro/text-to-image", ["1k", "2k", "4k"]),
            ("/openapi/v2/rhart-image-n-pro/edit", ["1k", "2k", "4k"]),
            ("/openapi/v2/rhart-image-n-g31-flash-official/text-to-image", ["1k", "2k", "4k"]),
            ("/openapi/v2/rhart-image-n-g31-flash-official/image-to-image", ["1k", "2k", "4k"]),
            ("/openapi/v2/rhart-image-n-g31-flash/text-to-image", ["1k", "2k", "4k"]),
            ("/openapi/v2/rhart-image-n-g31-flash/image-to-image", ["1k", "2k", "4k"]),
        ]

        for endpoint_token, values in endpoint_rules:
            if endpoint_token in endpoint_lower:
                return self._normalize_str_list(values)

        return self._normalize_str_list(fallback_values)

    def _get_runninghub_image_aspect_ratio_allowed_values(self, endpoint: Any, fallback_values: Any = None) -> List[str]:
        endpoint_lower = str(endpoint or "").strip().lower()
        if not endpoint_lower:
            return self._normalize_str_list(fallback_values)

        endpoint_rules = [
            ("/openapi/v2/rhart-image-g/text-to-image", ["960x960", "720x1280", "1280x720", "1168x784", "784x1168"]),
            ("/openapi/v2/rhart-image-g-1.5/text-to-image", ["auto", "1:1", "3:2", "2:3"]),
            ("/openapi/v2/rhart-image-g-1.5/edit", ["auto", "1:1", "3:2", "2:3"]),
            ("/openapi/v2/rhart-image-v1-official/text-to-image", ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"]),
            ("/openapi/v2/rhart-image-v1-official/edit", ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"]),
            ("/openapi/v2/rhart-image-v1/text-to-image", ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"]),
            ("/openapi/v2/rhart-image-v1/edit", ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"]),
            ("/openapi/v2/rhart-image-n-pro-official/text-to-image-ultra", ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]),
            ("/openapi/v2/rhart-image-n-pro-official/edit-ultra", ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]),
            ("/openapi/v2/rhart-image-n-pro-official/text-to-image", ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]),
            ("/openapi/v2/rhart-image-n-pro-official/edit", ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]),
            ("/openapi/v2/rhart-image-n-pro/text-to-image", ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"]),
            ("/openapi/v2/rhart-image-n-pro/edit", ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"]),
            ("/openapi/v2/rhart-image-n-g31-flash-official/text-to-image", ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9", "1:4", "4:1", "1:8", "8:1"]),
            ("/openapi/v2/rhart-image-n-g31-flash-official/image-to-image", ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9", "1:4", "4:1", "1:8", "8:1"]),
            ("/openapi/v2/rhart-image-n-g31-flash/text-to-image", ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9", "1:4", "4:1", "1:8", "8:1"]),
            ("/openapi/v2/rhart-image-n-g31-flash/image-to-image", ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9", "1:4", "4:1", "1:8", "8:1"]),
            ("/openapi/v2/youchuan/text-to-image", ["1:1", "4:3", "3:2", "16:9", "3:4", "2:3", "9:16"]),
        ]

        for endpoint_token, values in endpoint_rules:
            if endpoint_token in endpoint_lower:
                return self._normalize_str_list(values)

        return self._normalize_str_list(fallback_values)

    def _sanitize_kie_prompt_mentions(self, prompt: Any, tool_conf: Dict[str, Any]) -> str:
        text = str(prompt or "")
        if not text:
            return ""
            
        elements = tool_conf.get("kling_elements")
        valid_element_names = set()
        if isinstance(elements, list):
            for e in elements:
                if isinstance(e, dict):
                    name = str(e.get("name") or "").strip()
                    if name:
                        valid_element_names.add(name)

        def _repl(match):
            name = match.group(1)
            lower_name = name.strip().lower()
            if lower_name.startswith("image") or lower_name.startswith("video") or lower_name.startswith("vedie") or lower_name.startswith("vedio"):
                return match.group(0)
            if name.strip() in valid_element_names or name in valid_element_names:
                return match.group(0)
            return name

        # Updated regex to capture @Video 1 as well
        return re.sub(r'@([\w\u4e00-\u9fa5A-Za-z0-9_]+\s*\d*)', _repl, text)

    def _sanitize_sora_prompt_mentions(self, prompt: Any) -> str:
        text = str(prompt or "")
        if not text:
            return ""

        # Sora family may interpret @mentions as user cameo references and reject
        cleaned = re.sub(r"@(?!(?:Image|Video|Vedie|Vedio)\s*\d+)(?=[A-Za-z0-9_\u4e00-\u9fff])", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bCHAR\s*:\s*\[\s*", "CHAR:[", cleaned, flags=re.IGNORECASE)
        return cleaned

    def _resolve_sora_mention_config(self, tool_conf: Dict[str, Any]) -> Dict[str, bool]:
        cfg = {
            "auto_use_sora_mention": False,
            "auto_upload_character": False,
        }

        # Model-level override from System API config.
        if isinstance(tool_conf, dict):
            if tool_conf.get("auto_use_sora_mention") is not None:
                cfg["auto_use_sora_mention"] = bool(self._normalize_bool_value(tool_conf.get("auto_use_sora_mention")))
            if tool_conf.get("auto_upload_character") is not None:
                cfg["auto_upload_character"] = bool(self._normalize_bool_value(tool_conf.get("auto_upload_character")))

        # Global fallback from settings/system/manage/sora-mention-config.
        if not cfg["auto_use_sora_mention"] and not cfg["auto_upload_character"]:
            try:
                with SessionLocal() as session:
                    row = self._system_setting_query(
                        session,
                        provider=self._AGENT_POLICY_PROVIDER,
                        category=self._AGENT_POLICY_CATEGORY,
                    ).filter(
                        SystemAPISetting.model == self._AGENT_POLICY_MODEL,
                    ).order_by(SystemAPISetting.id.desc()).first()
                    row_cfg = self._safe_json_dict(getattr(row, "config", {}) if row else {})
                    sora_cfg = self._safe_json_dict(row_cfg.get(self._SORA_MENTION_CONFIG_KEY, {}))
                    if sora_cfg:
                        cfg["auto_use_sora_mention"] = bool(self._normalize_bool_value(sora_cfg.get("auto_use_sora_mention")))
                        cfg["auto_upload_character"] = bool(self._normalize_bool_value(sora_cfg.get("auto_upload_character")))
            except Exception:
                pass

        if not cfg["auto_use_sora_mention"]:
            cfg["auto_upload_character"] = False

        return cfg

    def _normalize_bool_value(self, value: Any, default: Optional[bool] = None) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        raw = str(value or "").strip().lower()
        if not raw:
            return default
        if raw in {"1", "true", "yes", "y", "on", "supported"}:
            return True
        if raw in {"0", "false", "no", "n", "off", "unsupported"}:
            return False
        return default

    def _normalize_kie_standard_value(self, dimension: str, raw_value: Any) -> Optional[str]:
        dim = str(dimension or "").strip().upper()
        value = str(raw_value or "").strip()
        if not dim or not value:
            return None

        lower = value.lower()
        if dim == "ASPECT_RATIO":
            if lower == "portrait":
                return "9:16"
            if lower == "landscape":
                return "16:9"
            if lower == "auto":
                return "AUTO"
            return value

        if dim == "RESOLUTION_TIER":
            mapping = {
                "1k": "K1",
                "2k": "K2",
                "4k": "K4",
                "480p": "P480",
                "512p": "P512",
                "580p": "P580",
                "720p": "P720",
                "768p": "P768",
                "1080p": "P1080",
            }
            return mapping.get(lower.replace(" ", ""), value.upper())

        if dim == "DURATION_SECONDS":
            try:
                num = float(value)
                if num <= 0:
                    return None
                if abs(num - int(num)) < 1e-9:
                    return str(int(num))
                return str(num)
            except Exception:
                return value

        if dim == "MODE":
            mode_map = {
                "std": "STANDARD",
                "standard": "STANDARD",
                "pro": "PRO",
                "fast": "FAST",
                "turbo": "TURBO",
                "master": "MASTER",
                "fun": "FUN",
                "normal": "NORMAL",
                "spicy": "SPICY",
            }
            return mode_map.get(lower, value.upper())

        if dim == "QUALITY_LEVEL":
            quality_map = {
                "basic": "BASIC",
                "medium": "MEDIUM",
                "high": "HIGH",
                "std": "STANDARD",
                "standard": "STANDARD",
            }
            return quality_map.get(lower, value.upper())

        if dim in {"OUTPUT_FORMAT", "STYLE", "REASONING_EFFORT", "CHARACTER_ORIENTATION", "IMAGE_SIZE_CLASS"}:
            return value.upper()

        if dim in {"SOUND_SUPPORTED", "MULTI_SHOTS_SUPPORTED"}:
            b = self._normalize_bool_value(value)
            if b is None:
                return None
            return "TRUE" if b else "FALSE"

        return value

    def _normalize_str_list(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            items = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    items = parsed
                else:
                    items = [seg.strip() for seg in raw.replace("\n", ",").split(",")]
            except Exception:
                items = [seg.strip() for seg in raw.replace("\n", ",").split(",")]
        else:
            items = [value]

        out: List[str] = []
        seen = set()
        for item in items:
            text_item = str(item or "").strip()
            if not text_item:
                continue
            key = text_item.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(text_item)
        return out

    def _normalize_duration_enum_values(self, values: Any) -> List[int]:
        normalized = self._normalize_str_list(values)
        out: List[int] = []
        for item in normalized:
            try:
                num = int(float(item))
            except Exception:
                continue
            if num > 0:
                out.append(num)
        return sorted(set(out))

    def _map_duration_nearest(
        self,
        requested: Any,
        allowed_values: Any,
        prefer_higher_on_tie: bool = False,
    ) -> Optional[int]:
        allowed = self._normalize_duration_enum_values(allowed_values)
        if not allowed:
            return None
        try:
            requested_num = float(requested)
        except Exception:
            requested_num = float(allowed[0])

        return min(
            allowed,
            key=lambda item: (
                abs(float(item) - requested_num),
                -float(item) if prefer_higher_on_tie else float(item),
            ),
        )

    def _normalize_enum_token(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        return re.sub(r"[^a-z0-9]", "", text)

    def _parse_aspect_ratio_number(self, value: Any) -> Optional[float]:
        text = str(value or "").strip().lower()
        if not text:
            return None
        text = text.replace(" ", "")
        if text in {"adaptive", "auto"}:
            return None

        m = re.match(r"^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$", text)
        if m:
            try:
                a = float(m.group(1))
                b = float(m.group(2))
                if a > 0 and b > 0:
                    return a / b
            except Exception:
                return None

        m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", text)
        if m:
            try:
                a = float(m.group(1))
                b = float(m.group(2))
                if a > 0 and b > 0:
                    return a / b
            except Exception:
                return None

        m = re.match(r"^(\d+(?:\.\d+)?)[x\*](\d+(?:\.\d+)?)$", text)
        if m:
            try:
                a = float(m.group(1))
                b = float(m.group(2))
                if a > 0 and b > 0:
                    return a / b
            except Exception:
                return None

        try:
            num = float(text)
            return num if num > 0 else None
        except Exception:
            return None

    def _parse_resolution_tier(self, value: Any) -> Optional[int]:
        text = str(value or "").strip().lower().replace(" ", "")
        if not text:
            return None

        m = re.match(r"^(\d+)(?:p)?$", text)
        if m:
            try:
                num = int(m.group(1))
                return num if num > 0 else None
            except Exception:
                return None

        m = re.match(r"^(\d+)[x:](\d+)$", text)
        if m:
            try:
                a = int(m.group(1))
                b = int(m.group(2))
                if a > 0 and b > 0:
                    return min(a, b)
            except Exception:
                return None

        m = re.match(r"^(\d+(?:\.\d+)?)k$", text)
        if m:
            try:
                return int(float(m.group(1)) * 1000)
            except Exception:
                return None

        return None

    def _parse_image_size_rank(self, value: Any) -> Optional[int]:
        text = str(value or "").strip().lower().replace(" ", "")
        if not text:
            return None

        m = re.match(r"^(\d+(?:\.\d+)?)k$", text)
        if m:
            try:
                return int(float(m.group(1)) * 1000)
            except Exception:
                return None

        m = re.match(r"^k(\d+(?:\.\d+)?)$", text)
        if m:
            try:
                return int(float(m.group(1)) * 1000)
            except Exception:
                return None

        m = re.match(r"^(\d+)[x:](\d+)$", text)
        if m:
            try:
                a = int(m.group(1))
                b = int(m.group(2))
                if a > 0 and b > 0:
                    return min(a, b)
            except Exception:
                return None

        m = re.match(r"^(\d+)(?:p)?$", text)
        if m:
            try:
                num = int(m.group(1))
                return num if num > 0 else None
            except Exception:
                return None

        return None

    def _map_mode_to_allowed(self, requested: Any, allowed_values: Any) -> Optional[str]:
        allowed = self._normalize_str_list(allowed_values)
        if not allowed:
            return None

        req_text = str(requested or "").strip()
        if not req_text:
            return None

        exact_map = {item.lower(): item for item in allowed}
        req_lower = req_text.lower()
        if req_lower in exact_map:
            return exact_map[req_lower]

        req_std = self._normalize_kie_standard_value("MODE", req_text)
        if req_std:
            for item in allowed:
                if self._normalize_kie_standard_value("MODE", item) == req_std:
                    return item

        req_token = self._normalize_enum_token(req_text)
        if req_token:
            token_map = {self._normalize_enum_token(item): item for item in allowed}
            mapped = token_map.get(req_token)
            if mapped:
                return mapped

        return allowed[0]

    def _map_aspect_ratio_to_allowed(self, requested: Any, allowed_values: Any) -> Optional[str]:
        allowed = self._normalize_str_list(allowed_values)
        if not allowed:
            return None

        req_text = self._normalize_aspect_ratio_value(str(requested or "").strip())
        if not req_text:
            return None

        exact_map = {item.lower(): item for item in allowed}
        if req_text.lower() in exact_map:
            return exact_map[req_text.lower()]

        req_ratio = self._parse_aspect_ratio_number(req_text)
        if req_ratio is None:
            return allowed[0]

        best_item: Optional[str] = None
        best_diff: Optional[float] = None
        for item in allowed:
            ratio_val = self._parse_aspect_ratio_number(item)
            if ratio_val is None:
                continue
            diff = abs(ratio_val - req_ratio)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_item = item

        return best_item or allowed[0]

    def _map_numeric_enum_nearest_lower(
        self,
        requested: Any,
        allowed_values: Any,
        parser: Any,
    ) -> Optional[str]:
        allowed = self._normalize_str_list(allowed_values)
        if not allowed:
            return None

        req_text = str(requested or "").strip()
        if not req_text:
            return None

        exact_map = {item.lower(): item for item in allowed}
        req_lower = req_text.lower()
        if req_lower in exact_map:
            return exact_map[req_lower]

        req_num = parser(req_text)
        numeric_allowed: List[tuple[str, int]] = []
        for item in allowed:
            parsed = parser(item)
            if parsed is None:
                continue
            try:
                numeric_allowed.append((item, int(parsed)))
            except Exception:
                continue

        if req_num is None or not numeric_allowed:
            return allowed[0]

        lower_or_equal = [pair for pair in numeric_allowed if pair[1] <= int(req_num)]
        if lower_or_equal:
            best_val = max(pair[1] for pair in lower_or_equal)
            for item, val in lower_or_equal:
                if val == best_val:
                    return item

        min_val = min(pair[1] for pair in numeric_allowed)
        for item, val in numeric_allowed:
            if val == min_val:
                return item

        return allowed[0]

    def _map_image_size_to_allowed(self, requested: Any, allowed_values: Any) -> Optional[str]:
        return self._map_numeric_enum_nearest_lower(requested, allowed_values, self._parse_image_size_rank)

    def _map_resolution_to_allowed(self, requested: Any, allowed_values: Any) -> Optional[str]:
        return self._map_numeric_enum_nearest_lower(requested, allowed_values, self._parse_resolution_tier)

    def _map_text_value_to_allowed(self, requested: Any, allowed_values: Any) -> Optional[str]:
        allowed = self._normalize_str_list(allowed_values)
        if not allowed:
            return None

        req_text = str(requested or "").strip()
        if not req_text:
            return None

        exact_map = {item.lower(): item for item in allowed}
        req_lower = req_text.lower()
        if req_lower in exact_map:
            return exact_map[req_lower]

        req_token = self._normalize_enum_token(req_text)
        if req_token:
            token_map = {self._normalize_enum_token(item): item for item in allowed}
            mapped = token_map.get(req_token)
            if mapped:
                return mapped

        return allowed[0]

    def _load_system_api_runtime_enum_catalog(self, setting_id: Any) -> Dict[str, Any]:
        try:
            sid = int(setting_id or 0)
        except Exception:
            sid = 0
        if sid <= 0:
            return {}

        with SessionLocal() as session:
            row = self._system_setting_query(session).filter(SystemAPISetting.id == sid).first()
            if not row:
                return {}

            cfg = self._safe_json_dict(getattr(row, "config", None))
            enum_catalog = cfg.get("enum_catalog") if isinstance(cfg.get("enum_catalog"), dict) else {}
            modality = self._safe_json_dict(getattr(row, "modality", None))
            capability_flags = self._safe_json_dict(modality.get("capability_flags"))
            voice_capabilities = self._safe_json_dict(modality.get("voice_capabilities"))

            mode_values = self._normalize_str_list(getattr(row, "mode_values", None))
            if not mode_values:
                mode_values = self._normalize_str_list(enum_catalog.get("mode") if isinstance(enum_catalog, dict) else None)

            aspect_ratios = self._normalize_str_list(getattr(row, "aspect_ratios", None))
            if not aspect_ratios:
                aspect_ratios = self._normalize_str_list(enum_catalog.get("aspect_ratio") if isinstance(enum_catalog, dict) else None)

            image_size_values = self._normalize_str_list(getattr(row, "image_size_values", None))
            if not image_size_values:
                image_size_values = self._normalize_str_list(enum_catalog.get("image_size") if isinstance(enum_catalog, dict) else None)

            resolution_values = self._normalize_str_list(getattr(row, "supported_resolutions", None))
            if not resolution_values:
                resolution_values = self._normalize_str_list(enum_catalog.get("resolution") if isinstance(enum_catalog, dict) else None)

            duration_values_raw = getattr(row, "durations_seconds", None)
            if not duration_values_raw:
                duration_values_raw = enum_catalog.get("duration") if isinstance(enum_catalog, dict) else None
            duration_values_text = self._normalize_str_list(duration_values_raw)
            duration_values_num: List[int] = []
            for item in duration_values_text:
                try:
                    duration_values_num.append(int(float(item)))
                except Exception:
                    continue
                    
            if len(duration_values_num) == 0:
                from app.models.all_models import SystemAPIBillingRule
                billing_rules = session.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.system_api_id == sid).all()
                for rule in billing_rules:
                    try:
                        if getattr(rule, "duration_seconds_max", None) is not None and rule.duration_seconds_max > 0:
                            duration_values_num.append(int(float(rule.duration_seconds_max)))
                    except Exception:
                        continue

            duration_values_num = sorted(set([x for x in duration_values_num if x > 0]))

            max_duration = None
            try:
                max_duration = int(getattr(row, "max_duration", 0) or 0)
            except Exception:
                max_duration = None
            if max_duration is not None and max_duration <= 0:
                max_duration = None

            sound_supported = getattr(row, "sound_supported", None)
            if sound_supported is None:
                sound_supported = getattr(row, "has_audio", None)
            if sound_supported is not None:
                sound_supported = bool(sound_supported)

            multi_shots_supported = getattr(row, "multi_shots_supported", None)
            if multi_shots_supported is not None:
                multi_shots_supported = bool(multi_shots_supported)

            voice_values = self._normalize_str_list(
                voice_capabilities.get("voice_values")
                or voice_capabilities.get("voices")
                or voice_capabilities.get("allowed_voices")
                or voice_capabilities.get("supported_voices")
                or capability_flags.get("voice_values")
                or enum_catalog.get("voice")
                or enum_catalog.get("voice_values")
            )

            language_code_values = self._normalize_str_list(
                voice_capabilities.get("language_code_values")
                or voice_capabilities.get("language_values")
                or voice_capabilities.get("languages")
                or voice_capabilities.get("allowed_languages")
                or capability_flags.get("language_code_values")
                or enum_catalog.get("language_code")
                or enum_catalog.get("language_code_values")
                or enum_catalog.get("languages")
            )

            return {
                "mode": mode_values,
                "aspect_ratio": aspect_ratios,
                "image_size": image_size_values,
                "resolution": resolution_values,
                "durations_seconds": duration_values_num,
                "max_duration": max_duration,
                "sound_supported": sound_supported,
                "multi_shots_supported": multi_shots_supported,
                "voice": voice_values,
                "language_code": language_code_values,
            }

    def _apply_runtime_enum_constraints(
        self,
        runtime_config: Dict[str, Any],
        category: Optional[str],
        aspect_ratio: Optional[str],
        duration: Any,
        image_size: Optional[str],
    ) -> Dict[str, Any]:
        active_config = runtime_config if isinstance(runtime_config, dict) else {}
        tool_conf = active_config.get("config") if isinstance(active_config.get("config"), dict) else {}
        active_config["config"] = tool_conf

        resolved_setting_id = None
        try:
            resolved_setting_id = int((tool_conf or {}).get("__resolved_setting_id") or 0)
        except Exception:
            resolved_setting_id = None

        runtime_enum_catalog = self._load_system_api_runtime_enum_catalog(resolved_setting_id)
        config_base_model = str(
            active_config.get("base_model") or tool_conf.get("base_model") or ""
        ).strip().lower()
        model_hint = config_base_model or str(
            active_config.get("model") or tool_conf.get("model") or ""
        ).strip().lower()
        prefer_higher_seedance_duration = bool(category == "Video" and "seedance" in model_hint)
        seedance_resolution_override = None
        if category == "Video" and "seedance" in model_hint:
            is_draft_mode = self._normalize_bool_value(tool_conf.get("draft_mode") or tool_conf.get("draft"))
            requested_res = str(
                tool_conf.get("resolution")
                or tool_conf.get("video_resolution")
                or ""
            ).strip().lower().replace(" ", "")
            if requested_res.endswith("p") and requested_res[:-1].isdigit():
                requested_res = requested_res[:-1]
            elif requested_res.startswith("p") and requested_res[1:].isdigit():
                requested_res = requested_res[1:]
            if is_draft_mode:
                seedance_resolution_override = "480p"
            elif requested_res in {"480", "sd"}:
                seedance_resolution_override = "480p"
            elif requested_res in {"720", "hd"}:
                seedance_resolution_override = "720p"
            else:
                seedance_resolution_override = "720p"
            tool_conf["resolution"] = seedance_resolution_override

        effective_aspect_ratio = self._normalize_aspect_ratio_value(aspect_ratio)
        effective_image_size = str(image_size or "").strip() or None
        effective_duration: Optional[int] = None
        try:
            effective_duration = int(float(duration))
        except Exception:
            effective_duration = None

        mapped_mode = self._map_mode_to_allowed(tool_conf.get("mode"), runtime_enum_catalog.get("mode"))
        if mapped_mode:
            tool_conf["mode"] = str(mapped_mode).strip().lower()

        mapped_ar = self._map_aspect_ratio_to_allowed(effective_aspect_ratio, runtime_enum_catalog.get("aspect_ratio"))
        if mapped_ar:
            effective_aspect_ratio = mapped_ar

        current_image_size = str(
            effective_image_size or tool_conf.get("image_size") or tool_conf.get("imageSize") or ""
        ).strip()
        mapped_image_size = self._map_image_size_to_allowed(current_image_size, runtime_enum_catalog.get("image_size"))
        if mapped_image_size:
            effective_image_size = mapped_image_size
            tool_conf["image_size"] = effective_image_size
            tool_conf["imageSize"] = effective_image_size

        if seedance_resolution_override is None:
            mapped_resolution = self._map_resolution_to_allowed(tool_conf.get("resolution"), runtime_enum_catalog.get("resolution"))
            if mapped_resolution:
                tool_conf["resolution"] = mapped_resolution

        if category in {"Video", "Voice"}:
            allowed_durations = runtime_enum_catalog.get("durations_seconds") or []
            is_seedance2_auto_duration = (
                effective_duration == -1
                and self._is_seedance2_base_model(
                    active_config.get("base_model") or tool_conf.get("base_model"),
                )
            )
            if (
                not is_seedance2_auto_duration
                and isinstance(allowed_durations, list)
                and allowed_durations
                and effective_duration is not None
            ):
                mapped_duration = self._map_duration_nearest(
                    effective_duration,
                    allowed_durations,
                    prefer_higher_on_tie=prefer_higher_seedance_duration,
                )
                if mapped_duration is not None:
                    effective_duration = int(mapped_duration)
            max_duration = runtime_enum_catalog.get("max_duration")
            if (
                not is_seedance2_auto_duration
                and effective_duration is not None
                and max_duration is not None
            ):
                try:
                    max_duration_num = int(float(max_duration))
                    if max_duration_num > 0 and effective_duration > max_duration_num:
                        effective_duration = max_duration_num
                except Exception:
                    pass

        sound_supported = runtime_enum_catalog.get("sound_supported")
        if sound_supported is False and tool_conf.get("sound") is True:
            tool_conf["sound"] = True

        multi_shots_supported = runtime_enum_catalog.get("multi_shots_supported")
        if multi_shots_supported is False and tool_conf.get("multi_shots") is True:
            tool_conf["multi_shots"] = False

        return {
            "catalog": runtime_enum_catalog,
            "aspect_ratio": effective_aspect_ratio,
            "duration": effective_duration,
            "image_size": effective_image_size,
        }

    def _runtime_value_from_kie_standard(self, dimension: str, standard_value: Any) -> Any:
        dim = str(dimension or "").strip().upper()
        value = str(standard_value or "").strip()
        if not value:
            return None

        if dim == "RESOLUTION_TIER":
            reverse = {
                "K1": "1k",
                "K2": "2k",
                "K4": "4k",
                "P480": "480p",
                "P512": "512p",
                "P580": "580p",
                "P720": "720p",
                "P768": "768p",
                "P1080": "1080p",
            }
            return reverse.get(value.upper(), value)

        if dim == "MODE":
            if value.upper() == "STANDARD":
                return "std"
            return value.lower()

        if dim == "OUTPUT_FORMAT":
            return value.lower()

        if dim == "QUALITY_LEVEL":
            return value.lower()

        if dim == "IMAGE_SIZE_CLASS":
            return value.lower()

        if dim in {"SOUND_SUPPORTED", "MULTI_SHOTS_SUPPORTED"}:
            return value.upper() == "TRUE"

        if dim == "DURATION_SECONDS":
            try:
                num = float(value)
            except Exception:
                return None
            if num <= 0:
                return None
            if abs(num - int(num)) < 1e-9:
                return str(int(num))
            return str(num)

        return value

    def _get_kie_standard_reverse_mapping(
        self,
        model_key: str,
        standard_dimension: str,
        standard_value: str,
        preferred_fields: List[str],
    ) -> Optional[Dict[str, Any]]:
        model = str(model_key or "").strip()
        if not model or not standard_dimension or not standard_value:
            return None

        preferred = [str(item or "").strip() for item in preferred_fields if str(item or "").strip()]
        with SessionLocal() as session:
            for source_field in preferred:
                row = session.execute(
                    text(
                        """
                        SELECT source_field, source_enum_value, confidence, note
                        FROM kie_system_data_standard_mappings
                        WHERE provider = 'kie'
                          AND is_active = 1
                          AND standard_dimension = :dim
                          AND standard_value = :val
                          AND source_field = :field
                          AND lower(coalesce(model_key_inferred, '')) = lower(:model)
                        ORDER BY CASE upper(coalesce(confidence, ''))
                            WHEN 'HIGH' THEN 0
                            WHEN 'MEDIUM' THEN 1
                            WHEN 'LOW' THEN 2
                            ELSE 3 END,
                            id ASC
                        LIMIT 1
                        """
                    ),
                    {
                        "dim": standard_dimension,
                        "val": standard_value,
                        "field": source_field,
                        "model": model,
                    },
                ).mappings().first()
                if row:
                    return dict(row)

            for source_field in preferred:
                row = session.execute(
                    text(
                        """
                        SELECT source_field, source_enum_value, confidence, note
                        FROM kie_system_data_standard_mappings
                        WHERE provider = 'kie'
                          AND is_active = 1
                          AND standard_dimension = :dim
                          AND standard_value = :val
                          AND source_field = :field
                        ORDER BY CASE upper(coalesce(confidence, ''))
                            WHEN 'HIGH' THEN 0
                            WHEN 'MEDIUM' THEN 1
                            WHEN 'LOW' THEN 2
                            ELSE 3 END,
                            id ASC
                        LIMIT 1
                        """
                    ),
                    {
                        "dim": standard_dimension,
                        "val": standard_value,
                        "field": source_field,
                    },
                ).mappings().first()
                if row:
                    return dict(row)

        return None

    async def _submit_and_poll_image_task(
        self,
        url,
        payload,
        api_key,
        log_tag,
        extra_metadata=None,
        poll_timeout_seconds: int = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS,
        poll_interval_seconds: int = 2,
        provider_payload_callback: Any = None,
        pure_callback_mode: bool = False,
        callback_enabled: bool = False,
        callback_ticket: Optional[str] = None,
        callback_url: Optional[str] = None,
    ):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        provider_name = str((extra_metadata or {}).get("provider") or "").strip().lower()

        safe_url = _strip_query_from_log_url(url) or url
        _debug_log(f"[{log_tag}] Submitting to URL: {safe_url} | Payload: {_format_payload_for_log(payload)}")

        submit_timeouts = _media_submit_timeout_pair()

        def _post(use_proxy=True, connection_close: bool = False, connect_timeout=None):
            request_headers = dict(headers)
            if connection_close:
                request_headers["Connection"] = "close"
            c_timeout = connect_timeout or submit_timeouts[0]
            kwargs = {
                "json": payload,
                "headers": request_headers,
                "timeout": (c_timeout, submit_timeouts[1]),
                "verify": False,
            }
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(url, **kwargs)

        def _poll(use_proxy=True, task_id=None):
            kwargs = {"headers": headers, "timeout": 30, "verify": False}
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.get(f"{url}/{task_id}", **kwargs)

        try:
            try:
                resp = await asyncio.to_thread(_post, True)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError) as e:
                _debug_log(f"[{log_tag}] Submit failed with proxy ({str(e)[:120]}), retrying without proxy (connect_timeout=15s)...", "warning")
                try:
                    resp = await asyncio.to_thread(_post, False, False, 15)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e2:
                    return self._build_ambiguous_submit_result(provider_name, log_tag, e2, url, extra_metadata)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError) as e2:
                    _debug_log(f"[{log_tag}] Submit retry without proxy failed ({str(e2)[:120]}), retrying with connection close...", "warning")
                    try:
                        resp = await asyncio.to_thread(_post, False, True, 15)
                    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e3:
                        return self._build_ambiguous_submit_result(provider_name, log_tag, e3, url, extra_metadata)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                return self._build_ambiguous_submit_result(provider_name, log_tag, e, url, extra_metadata)

            if callable(provider_payload_callback) and isinstance(payload, dict):
                try:
                    provider_payload_callback(
                        {
                            "provider": provider_name or "unknown",
                            "type": "image",
                            "method": "POST",
                            "url": url,
                            "model": payload.get("model"),
                            "payload": _strip_base64_from_log(payload),
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "[%s] provider payload callback failed before image submit | error=%s",
                        log_tag,
                        callback_err,
                    )

            if resp.status_code not in [200, 201]:
                return {"error": f"Submission Failed {resp.status_code}", "details": resp.text, "submit_failed": True}

            data = resp.json()
            task_id = data.get("id") or data.get("task_id") or data.get("taskId")
            if not task_id and isinstance(data.get("data"), dict):
                task_id = data.get("data", {}).get("id") or data.get("data", {}).get("task_id") or data.get("data", {}).get("taskId")
            if not task_id:
                resolved_output = self._extract_any_image_output(data)
                if resolved_output:
                    metadata = {"raw": data}
                    if extra_metadata:
                        metadata.update(extra_metadata)
                    return {"url": resolved_output, "metadata": metadata}
                return {"error": "No Task ID", "submit_failed": True}

            if callable(provider_payload_callback) and isinstance(payload, dict):
                try:
                    provider_payload_callback(
                        {
                            "provider": provider_name or "unknown",
                            "type": "image",
                            "method": "POST",
                            "url": url,
                            "model": payload.get("model"),
                            "payload": _strip_base64_from_log(payload),
                            "final_submit": True,
                            "provider_task_id": str(task_id),
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "[%s] provider payload callback failed after image submit | task_id=%s error=%s",
                        log_tag,
                        task_id,
                        callback_err,
                    )

            if pure_callback_mode and callback_enabled:
                logger.info(
                    "[%s] pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s",
                    log_tag,
                    task_id,
                    callback_ticket or None,
                    callback_url or None,
                )
                pending_meta = dict(extra_metadata or {})
                pending_meta.update(
                    {
                        "raw": data,
                        "submit_raw": data,
                        "task_id": str(task_id),
                        "taskId": str(task_id),
                        "pending_callback": True,
                        "callback_ticket": callback_ticket,
                        "callback_url": callback_url,
                    }
                )
                return {
                    "pending_callback": True,
                    "provider_task_id": str(task_id),
                    "metadata": pending_meta,
                }

            max_attempts = max(1, int(poll_timeout_seconds / max(1, poll_interval_seconds)))
            for _ in range(max_attempts):
                await asyncio.sleep(poll_interval_seconds)
                try:
                    p_resp = await asyncio.to_thread(_poll, True, task_id)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                    p_resp = await asyncio.to_thread(_poll, False, task_id)
                except requests.exceptions.Timeout:
                    continue

                if p_resp.status_code != 200:
                    continue

                p_data = p_resp.json()
                status = str(p_data.get("status") or p_data.get("state") or p_data.get("task_status") or "").strip()
                status_l = status.lower()
                image_url = self._extract_any_image_output(p_data)
                if status_l in ["succeeded", "success", "completed", "done"] or (not status_l and image_url):
                    if not image_url:
                        return {
                            "error": "Generation completed without image URL",
                            "details": f"task_id={task_id} status={status or '<empty>'}",
                            "raw": p_data,
                        }
                    usage = _normalize_provider_task_usage(_extract_provider_task_usage(p_data))
                    if not usage:
                        try:
                            await asyncio.sleep(0.5)
                            try:
                                refresh_resp = await asyncio.to_thread(_poll, True, task_id)
                            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                                refresh_resp = await asyncio.to_thread(_poll, False, task_id)
                            if getattr(refresh_resp, "status_code", None) == 200:
                                refresh_data = refresh_resp.json()
                                if isinstance(refresh_data, dict):
                                    p_data = refresh_data
                                    usage = _normalize_provider_task_usage(_extract_provider_task_usage(refresh_data))
                        except Exception as usage_err:
                            logger.warning(
                                "[%s] image task usage refresh failed | task_id=%s error=%s",
                                log_tag,
                                task_id,
                                usage_err,
                            )
                    metadata = {"raw": p_data, "submit_raw": data, "task_id": task_id, "taskId": task_id}
                    if extra_metadata:
                        metadata.update(extra_metadata)
                        metadata["raw"] = p_data
                    metadata = _attach_provider_usage_metadata(
                        metadata,
                        usage=usage,
                        source=provider_name or "provider",
                        task_payload=p_data,
                    )
                    return {"url": image_url, "metadata": metadata}
                if status_l in ["failed", "error", "canceled", "cancelled"]:
                    return {"error": f"Generation Failed: {p_data.get('error') or p_data}", "details": p_data.get("error") or p_data}

            return {"error": f"Timeout after {poll_timeout_seconds}s"}
        except requests.exceptions.Timeout as e:
            if self._is_ambiguous_submit_transport_error(provider_name, log_tag, e):
                return self._build_ambiguous_submit_result(provider_name, log_tag, e, url, extra_metadata)
            return {"error": "Upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            if self._is_ambiguous_submit_transport_error(provider_name, log_tag, e):
                return self._build_ambiguous_submit_result(provider_name, log_tag, e, url, extra_metadata)
            details = str(e)
            if "10054" in details or "ConnectionResetError" in details:
                details = f"{details}. Possible network middlebox/proxy reset on large request body; retried with no-proxy once."
            return {"error": "Upstream request failed", "details": details, "submit_failed": True}
        except Exception as e:
            return {"error": str(e), "submit_failed": True}

    def _resolve_kie_standardized_runtime_inputs(
        self,
        model_key: str,
        gen_type: str,
        tool_conf: Dict[str, Any],
        aspect_ratio: Optional[str],
        duration: Any,
        image_size: Optional[str],
    ) -> Dict[str, Any]:
        cfg = tool_conf if isinstance(tool_conf, dict) else {}
        raw_std = cfg.get("standard_values") if isinstance(cfg.get("standard_values"), dict) else {}

        standard_values: Dict[str, str] = {}
        for dim, val in (raw_std or {}).items():
            norm_dim = str(dim or "").strip().upper()
            norm_val = self._normalize_kie_standard_value(norm_dim, val)
            if norm_dim and norm_val:
                standard_values[norm_dim] = norm_val

        auto_candidates = {
            "ASPECT_RATIO": aspect_ratio or cfg.get("aspect_ratio") or cfg.get("size"),
            "RESOLUTION_TIER": cfg.get("resolution") or cfg.get("image_resolution"),
            "DURATION_SECONDS": duration if duration is not None else cfg.get("duration") or cfg.get("n_frames"),
            "MODE": cfg.get("mode"),
            "QUALITY_LEVEL": cfg.get("quality"),
            "OUTPUT_FORMAT": cfg.get("outputFormat") or cfg.get("output_format"),
            "IMAGE_SIZE_CLASS": image_size or cfg.get("image_size"),
            "SOUND_SUPPORTED": cfg.get("sound"),
            "MULTI_SHOTS_SUPPORTED": cfg.get("multi_shots"),
        }
        for dim, raw in auto_candidates.items():
            if dim in standard_values:
                continue
            norm_val = self._normalize_kie_standard_value(dim, raw)
            if norm_val:
                standard_values[dim] = norm_val

        preferred_fields = {
            "ASPECT_RATIO": ["paths.post.input.aspect_ratio", "paths.post.input.size"],
            "RESOLUTION_TIER": ["paths.post.input.resolution", "paths.post.input.image_resolution"],
            "DURATION_SECONDS": ["paths.post.input.duration", "paths.post.input.n_frames"],
            "MODE": ["paths.post.input.mode"],
            "QUALITY_LEVEL": ["paths.post.input.quality"],
            "OUTPUT_FORMAT": ["paths.post.input.output_format"],
            "IMAGE_SIZE_CLASS": ["paths.post.input.image_size"],
            "SOUND_SUPPORTED": ["sound"],
            "MULTI_SHOTS_SUPPORTED": ["multi_shots"],
        }

        resolved: Dict[str, Any] = {
            "trace": {},
        }

        for dim, std_value in standard_values.items():
            reverse = self._get_kie_standard_reverse_mapping(
                model_key=model_key,
                standard_dimension=dim,
                standard_value=std_value,
                preferred_fields=preferred_fields.get(dim, []),
            )

            runtime_value = None
            source_field = None
            if reverse:
                source_field = str(reverse.get("source_field") or "").strip()
                runtime_value = reverse.get("source_enum_value")
            if runtime_value in (None, ""):
                runtime_value = self._runtime_value_from_kie_standard(dim, std_value)

            if runtime_value in (None, ""):
                continue

            if dim == "ASPECT_RATIO":
                resolved["aspect_ratio"] = str(runtime_value).strip()
            elif dim == "RESOLUTION_TIER":
                resolved["resolution"] = str(runtime_value).strip()
            elif dim == "DURATION_SECONDS":
                try:
                    duration_num = float(runtime_value)
                except Exception:
                    duration_num = None
                if duration_num is None or duration_num <= 0:
                    continue
                if abs(duration_num - int(duration_num)) < 1e-9:
                    resolved["duration"] = str(int(duration_num))
                else:
                    resolved["duration"] = str(duration_num)
            elif dim == "MODE":
                resolved["mode"] = str(runtime_value).strip().lower()
            elif dim == "QUALITY_LEVEL":
                resolved["quality"] = str(runtime_value).strip().lower()
            elif dim == "OUTPUT_FORMAT":
                resolved["output_format"] = str(runtime_value).strip().lower()
            elif dim == "IMAGE_SIZE_CLASS":
                resolved["image_size"] = str(runtime_value).strip().lower()
            elif dim == "SOUND_SUPPORTED":
                resolved["sound"] = bool(runtime_value)
            elif dim == "MULTI_SHOTS_SUPPORTED":
                resolved["multi_shots"] = bool(runtime_value)

            resolved["trace"][dim] = {
                "standard_value": std_value,
                "source_field": source_field,
                "runtime_value": runtime_value,
            }

        return resolved

    def _is_deprecated_system_config(self, config_value: Any, deprecated_flag: Any = None) -> bool:
        if isinstance(deprecated_flag, bool):
            return deprecated_flag
        return deprecated_flag is not None and str(deprecated_flag).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _extract_nested_runtime_flag(self, config_value: Any, key_paths: List[Any]) -> bool:
        cfg = self._safe_json_dict(config_value)
        for path in key_paths:
            if isinstance(path, str):
                candidate = cfg.get(path)
            elif isinstance(path, (list, tuple)):
                candidate = cfg
                for segment in path:
                    if not isinstance(candidate, dict):
                        candidate = None
                        break
                    candidate = candidate.get(segment)
            else:
                candidate = None
            if candidate is None:
                continue
            if isinstance(candidate, bool):
                return candidate
            if str(candidate).strip().lower() in {"1", "true", "yes", "y", "on"}:
                return True
        return False

    def _is_runtime_runnable_system_setting(self, category: str, system_row: Optional[SystemAPISetting]) -> bool:
        if system_row is None:
            return False
        resolved_category = str(category or "").strip()
        resolved_provider = self._normalize_provider_name(getattr(system_row, "provider", None), resolved_category)

        runtime_config = self._promote_runtime_endpoint(
            resolved_category,
            resolved_provider,
            getattr(system_row, "config", None),
            system_row=system_row,
        )
        runtime_ready = self._extract_nested_runtime_flag(runtime_config, ["runtime_ready", resolved_provider, "runtime_ready"])
        endpoint = str(runtime_config.get("endpoint") or "").strip()
        runtime_activation = str(runtime_config.get("runtime_activation") or "").strip()
        cat = resolved_category.lower()

        if cat in {"image", "video", "voice"}:
            if runtime_ready:
                return True
            if endpoint or runtime_activation:
                return True
            if resolved_provider in {"apiyi", "n1n", "aiclub"}:
                return False

        return True

    def _normalize_api_keys(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raw_items = value.replace("\r", "\n").replace(",", "\n").split("\n")
        elif isinstance(value, list):
            raw_items = value
        else:
            raw_items = [value]

        result: List[str] = []
        seen = set()
        for item in raw_items:
            key = str(item or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(key)
        return result

    def _pick_runtime_api_key(self, config_value: Any, fallback_key: Any = None, session=None, provider_name: str = None) -> str:
        cfg = self._safe_json_dict(config_value)
        strategy = str(cfg.get("provider_api_key_strategy") or "random").strip().lower()

        def _pick_from_pool(keys: List[str]) -> str:
            if not keys:
                return ""
            if strategy == "round_robin":
                cursor_key = str(cfg.get("provider") or cfg.get("__provider") or "default")
                cursor = int(self._provider_key_cursors.get(cursor_key, 0))
                selected = keys[cursor % len(keys)]
                self._provider_key_cursors[cursor_key] = cursor + 1
                return selected
            if strategy == "weighted":
                raw_weights = cfg.get("provider_api_key_weights")
                if isinstance(raw_weights, list) and raw_weights:
                    weights = []
                    for i in range(len(keys)):
                        try:
                            w = float(raw_weights[i]) if i < len(raw_weights) else 1.0
                        except Exception:
                            w = 1.0
                        weights.append(w if w > 0 else 1.0)
                    return random.choices(keys, weights=weights, k=1)[0]
            return random.choice(keys)

        # 1. 优先使用系统配置自带的 API Key (system_api_settings.api_key)
        explicit_pool = self._normalize_api_keys(fallback_key)
        if explicit_pool:
            return _pick_from_pool(explicit_pool)

        # 2. 如果系统配置为空，尝试从 ProviderKeyPool (直接查询) 获取
        if session and provider_name:
            prov = str(provider_name or "").strip().lower()
            if prov:
                record = session.query(ProviderKeyPool).filter(ProviderKeyPool.provider == prov).first()
                if record and record.api_keys:
                    pooled = self._normalize_api_keys(record.api_keys)
                    if pooled:
                        # 对于 ProviderKeyPool 的情况，覆盖上面的 strategy 为表内的策略
                        strategy = str(record.strategy or "random").strip().lower()
                        if strategy == "round_robin":
                            cursor = int(self._provider_key_cursors.get(prov, 0))
                            selected = pooled[cursor % len(pooled)]
                            self._provider_key_cursors[prov] = cursor + 1
                            return selected
                        if strategy == "weighted":
                            raw_weights = record.weights
                            if isinstance(raw_weights, list) and raw_weights:
                                weights = []
                                for i in range(len(pooled)):
                                    try:
                                        w = float(raw_weights[i]) if i < len(raw_weights) else 1.0
                                    except Exception:
                                        w = 1.0
                                    weights.append(w if w > 0 else 1.0)
                                return random.choices(pooled, weights=weights, k=1)[0]
                        return random.choice(pooled)

        # 3. 兼容配置字典中的 provider_api_keys
        pooled = self._normalize_api_keys(cfg.get("provider_api_keys"))
        if pooled:
            return _pick_from_pool(pooled)

        return str(fallback_key or "").strip()

    def _collect_provider_key_pool_bundle(self, session, category: str, provider: str) -> Dict[str, Any]:
        prov = str(provider or "").strip().lower()
        if not prov:
            return {"provider_api_keys": [], "provider_api_key_strategy": "random", "provider_api_key_weights": []}
        record = session.query(ProviderKeyPool).filter(ProviderKeyPool.provider == prov).first()
        if record and record.api_keys:
            keys = self._normalize_api_keys(record.api_keys)
            strategy = str(record.strategy or "random").strip().lower()
            if strategy not in ("random", "round_robin", "weighted"):
                strategy = "random"
            weights = record.weights if isinstance(record.weights, list) else []
            return {
                "provider_api_keys": keys,
                "provider_api_key_strategy": strategy,
                "provider_api_key_weights": weights,
            }
        return {"provider_api_keys": [], "provider_api_key_strategy": "random", "provider_api_key_weights": []}

    def _infer_image_size_from_dimensions(self, width: Any, height: Any) -> str:
        try:
            w = int(width)
            h = int(height)
        except Exception:
            return "1K"
        max_side = max(w, h)
        if max_side >= 3200:
            return "4K"
        if max_side >= 1900:
            return "2K"
        return "1K"

    def _repair_invalid_user_config_rows(self, session, user_id: int, category: Optional[str] = None) -> None:
        # api_settings no longer stores per-provider runtime config.
        return

    def _repair_invalid_system_config_rows(self, session, category: Optional[str] = None, provider: Optional[str] = None) -> None:
        q = session.query(
            SystemAPISetting.id,
            cast(SystemAPISetting.config, String).label("config_raw"),
        )
        if category:
            q = q.filter(SystemAPISetting.category == category)
        if provider:
            q = q.filter(self._provider_ci_filter(provider))

        bad_ids: List[int] = []
        for row in q.all():
            raw = getattr(row, "config_raw", None)
            if isinstance(raw, str) and raw.strip() and not self._is_json_object_value(raw):
                bad_ids.append(row.id)

        if bad_ids:
            logger.warning("Repair invalid system_api_settings.config rows in media service | category=%s provider=%s ids=%s", category, provider, bad_ids)
            session.query(SystemAPISetting).filter(SystemAPISetting.id.in_(bad_ids)).update(
                {SystemAPISetting.config: {}},
                synchronize_session=False,
            )
            session.commit()

    def _system_setting_query(self, session, provider: Optional[str] = None, category: Optional[str] = None):
        query = session.query(SystemAPISetting).options(
            load_only(
                SystemAPISetting.id,
                SystemAPISetting.name,
                SystemAPISetting.category,
                SystemAPISetting.provider,
                SystemAPISetting.api_key,
                SystemAPISetting.base_url,
                SystemAPISetting.model,
                SystemAPISetting.base_model,
                SystemAPISetting.modality,
                SystemAPISetting.tags,
                SystemAPISetting.supplier_info,
                SystemAPISetting.deprecated,
                SystemAPISetting.config,
                SystemAPISetting.is_active,
            )
        )
        if category:
            query = query.filter(SystemAPISetting.category == category)
        if provider:
            query = query.filter(self._provider_ci_filter(provider))
        return query

    def _setting_to_config(self, setting: Any, provider: str, defaults: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        resolved_category = str(getattr(setting, "category", "") or "").strip()
        runtime_config = self._promote_runtime_endpoint(
            resolved_category,
            provider,
            getattr(setting, "config", None),
            system_row=setting,
        )
        runtime_model = str(
            runtime_config.get("runtime_model")
            or runtime_config.get("upstream_model")
            or runtime_config.get("model_override")
            or getattr(setting, "model", None)
            or defaults.get(provider, {}).get("model")
            or ""
        ).strip()
        return {
            "api_key": self._pick_runtime_api_key(runtime_config, getattr(setting, "api_key", None)),
            "base_url": getattr(setting, "base_url", None) or defaults.get(provider, {}).get("base_url"),
            "model": runtime_model,
            "base_model": getattr(setting, "base_model", None),
            "modality": getattr(setting, "modality", None),
            "supplier_info": getattr(setting, "supplier_info", None),
            "config": runtime_config,
        }

    def _get_active_user_setting(self, session, user_id: int, category: str) -> Optional[APISetting]:
        rows = session.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.category == category,
        ).order_by(APISetting.id.desc()).all()

        if len(rows) > 1:
            logger.warning(
                "Multiple api settings found | user_id=%s category=%s ids=%s",
                user_id,
                category,
                [r.id for r in rows],
            )

        def _score(item: APISetting):
            has_system_setting_id = 1 if int(getattr(item, "system_api_id", 0) or 0) > 0 else 0
            has_mode = 1 if str(getattr(item, "mode", "") or "").strip() else 0
            return (has_system_setting_id, has_mode, int(getattr(item, "id", 0) or 0))

        best_active = max(rows, key=_score) if rows else None

        def _is_viable(item: Optional[APISetting]) -> bool:
            if not item:
                return False
            return int(getattr(item, "system_api_id", 0) or 0) > 0

        if _is_viable(best_active):
            return best_active

        # Latest row missing binding: select best viable setting in this category.
        all_rows = session.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.category == category,
        ).order_by(APISetting.id.desc()).all()
        viable_rows = [r for r in all_rows if _is_viable(r)]
        if not viable_rows:
            return best_active

        promoted = max(viable_rows, key=_score)
        logger.warning(
            "Auto-heal api setting selection in media service | user_id=%s category=%s old_selected_id=%s promoted_id=%s",
            user_id,
            category,
            getattr(best_active, "id", None),
            promoted.id,
        )
        return promoted

    def _read_system_api_base_model(self, setting: Any) -> str:
        return str(getattr(setting, "base_model", "") or "").strip()

    def _is_seedance2_base_model(self, base_model: Any) -> bool:
        candidate = str(base_model or "").strip().lower()
        if not candidate:
            return False
        if candidate.startswith("doubao-seedance-2"):
            return True
        if candidate.startswith("ep-doubao-seedance-2"):
            return True
        return bool(re.match(r"^seedance[-_]?2(?:$|[-_.])", candidate))

    def _is_seedance2_video_model(self, base_model: Any) -> bool:
        return self._is_seedance2_base_model(base_model)

    def _normalize_provider_name(self, provider: Optional[str], category: Optional[str] = None) -> str:
        raw = str(provider or "").strip().lower()
        mapping = {
            "grsai-image": "grsai",
            "grsai-video": "grsai",
            "grsai": "grsai",
            "kie-image": "kie",
            "kie-video": "kie",
            "kie-voice": "kie",
            "kie-tts": "kie",
            "kie": "kie",
            "doubao": "doubao",
            "doubao video": "doubao",
            "stable diffusion": "stability",
            "tencent hunyuan": "tencent",
            "wanxiang": "wanxiang",
            "wanx": "wanxiang",
            "happyhorse": "happyhorse",
            "happy horse": "happyhorse",
            "aliyun happyhorse": "happyhorse",
            "vidu (video)": "vidu",
            "runway": "runway",
            "kling": "kling",
            "runninghub": "runninghub",
            "pixelmove": "pixelmove",
            "pixelmove video": "pixelmove",
            "zlhub": "zlhub",
            "zlhub video": "zlhub",
            "lzhbu": "zlhub",
            "lzhbu video": "zlhub",
            "zhonglian": "zlhub",
        }
        if raw in mapping:
            return mapping[raw]
        if category == "Image" and raw == "ark":
            return "doubao"
        if category == "Video" and raw == "ark":
            return "doubao"
        return raw

    def _is_supported_provider(self, category: str, provider: Optional[str]) -> bool:
        normalized = self._normalize_provider_name(provider, category)
        # Provider validity follows system settings in DB; avoid hard-coded allowlists.
        return bool(normalized)

    def _infer_n1n_runtime_model(self, system_row: Optional[SystemAPISetting], cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
        cfg_dict = cfg if isinstance(cfg, dict) else self._safe_json_dict(cfg)
        for key in ("runtime_model", "upstream_model", "model_override"):
            value = str(cfg_dict.get(key) or "").strip()
            if value:
                return value

        supplier_info = getattr(system_row, "supplier_info", None) if system_row is not None else None
        n1n_info = (supplier_info or {}).get("n1n") if isinstance(supplier_info, dict) else {}
        model_hints = n1n_info.get("model_hints") if isinstance(n1n_info, dict) else None
        if isinstance(model_hints, list):
            for item in model_hints:
                candidate = str(item or "").strip()
                if not candidate or candidate.lower().startswith(("http://", "https://")):
                    continue
                if any(ch.isspace() for ch in candidate):
                    continue
                return candidate

        fallback_model = str(getattr(system_row, "model", "") or "").strip() if system_row is not None else ""
        return fallback_model or None

    def _promote_runtime_endpoint(self, category: str, provider: Optional[str], config_value: Any, system_row: Optional[SystemAPISetting] = None) -> Dict[str, Any]:
        cfg = self._safe_json_dict(config_value)
        resolved_category = str(category or "").strip()
        resolved_provider = self._normalize_provider_name(provider, resolved_category)
        endpoint = str(cfg.get("endpoint") or "").strip()
        endpoint_hint = str(cfg.get("endpoint_hint") or "").strip()

        if resolved_provider == "n1n" and resolved_category == "Image":
            supplier_info = getattr(system_row, "supplier_info", None) if system_row is not None else None
            n1n_supplier = (supplier_info or {}).get("n1n") if isinstance(supplier_info, dict) else {}
            n1n_cfg = cfg.get("n1n") if isinstance(cfg.get("n1n"), dict) else {}
            api_style = str((n1n_supplier or {}).get("api_style") or n1n_cfg.get("api_style") or "").strip().lower()
            supplier_endpoint_hint = str((n1n_supplier or {}).get("endpoint_hint") or "").strip()
            protocol_key = str((n1n_supplier or {}).get("protocol_key") or "").strip().lower()
            family_key = str((n1n_supplier or {}).get("family_key") or n1n_cfg.get("family_key") or "").strip().lower()

            if not endpoint_hint and (protocol_key == "kling_image" or family_key == "kling"):
                endpoint_hint = "/kling/v1/images/generations"

            if not endpoint_hint and supplier_endpoint_hint:
                endpoint_hint = supplier_endpoint_hint

            if not endpoint_hint and api_style in {"async_task", "openai_compatible", "chat_compatible"}:
                endpoint_hint = "/v1/images/generations"

        if endpoint or not endpoint_hint:
            return cfg
        endpoint_hint_lower = endpoint_hint.lower()
        runtime_activation = None
        if resolved_category == "Image" and "generatecontent" in endpoint_hint_lower:
            runtime_activation = "image_gemini_native"
        elif resolved_category == "Image" and "/kling/v1/images/generations" in endpoint_hint_lower:
            runtime_activation = "image_n1n_kling_native"
        elif resolved_category == "Image" and "/v1/images/generations" in endpoint_hint_lower:
            runtime_activation = "image_openai_compatible"
        elif resolved_category == "Video" and ("/v1/videos" in endpoint_hint_lower or "/v1/chat/completions" in endpoint_hint_lower):
            runtime_activation = "video_openai_compatible"
        elif resolved_category == "Voice" and "voice-clone" in endpoint_hint_lower:
            runtime_activation = "audio_runninghub_compatible"
        elif resolved_category == "Voice" and any(token in endpoint_hint_lower for token in ("tts", "text-to-speech", "voice", "/audio")):
            normalized_voice_provider = self._normalize_provider_name(provider, "Voice")
            runtime_activation = "audio_kie_compatible" if normalized_voice_provider == "kie" else "audio_runninghub_compatible"
        elif resolved_category == "LLM" and "/v1/chat/completions" in endpoint_hint_lower:
            runtime_activation = "llm_openai_compatible"
        if not runtime_activation:
            return cfg

        promoted = dict(cfg)
        promoted["endpoint"] = endpoint_hint
        promoted.setdefault("runtime_activation", runtime_activation)
        if resolved_provider == "n1n":
            inferred_runtime_model = self._infer_n1n_runtime_model(system_row, promoted)
            if inferred_runtime_model:
                promoted.setdefault("runtime_model", inferred_runtime_model)
        return promoted

    def _get_runtime_activation(self, api_config: Optional[Dict[str, Any]]) -> str:
        outer = api_config if isinstance(api_config, dict) else {}
        tool_conf = self._safe_json_dict(outer.get("config"))
        activation = tool_conf.get("runtime_activation")
        if activation is None:
            activation = outer.get("runtime_activation")
        return str(activation or "").strip().lower()

    def _coerce_optional_bool(self, value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return None

    def _iter_runtime_capability_containers(self, api_config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        outer = api_config if isinstance(api_config, dict) else {}
        modality = self._safe_json_dict(outer.get("modality"))
        containers: List[Dict[str, Any]] = []
        for raw in (
            modality.get("capability_flags"),
            modality.get("image_capabilities"),
            modality.get("video_capabilities"),
            modality.get("text_capabilities"),
            modality.get("digital_human_capabilities"),
            modality.get("voice_capabilities"),
            modality.get("music_capabilities"),
            modality,
        ):
            container = self._safe_json_dict(raw)
            if container:
                containers.append(container)
        return containers

    def _get_runtime_capability_flag(self, api_config: Optional[Dict[str, Any]], *keys: str) -> Optional[bool]:
        normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
        if not normalized_keys:
            return None
        for container in self._iter_runtime_capability_containers(api_config):
            for key in normalized_keys:
                value = self._coerce_optional_bool(container.get(key))
                if value is not None:
                    return value
        return None

    def _get_runtime_capability_int(self, api_config: Optional[Dict[str, Any]], *keys: str) -> Optional[int]:
        normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
        if not normalized_keys:
            return None
        for container in self._iter_runtime_capability_containers(api_config):
            for key in normalized_keys:
                value = container.get(key)
                if value is None or str(value).strip() == "":
                    continue
                try:
                    parsed = int(float(value))
                except Exception:
                    continue
                if parsed >= 0:
                    return parsed
        return None

    def _get_runtime_capability_number(self, api_config: Optional[Dict[str, Any]], *keys: str) -> Optional[float]:
        normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
        if not normalized_keys:
            return None
        for container in self._iter_runtime_capability_containers(api_config):
            for key in normalized_keys:
                value = container.get(key)
                if value is None or str(value).strip() == "":
                    continue
                try:
                    return float(value)
                except Exception:
                    continue
        return None

    def _get_runtime_capability_list(self, api_config: Optional[Dict[str, Any]], *keys: str) -> List[str]:
        normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
        if not normalized_keys:
            return []
        for container in self._iter_runtime_capability_containers(api_config):
            for key in normalized_keys:
                values = self._normalize_str_list(container.get(key))
                if values:
                    return values
        return []

    def _limit_reference_input(self, value: Any, limit: Optional[int]) -> Any:
        if limit is None:
            return value
        if limit <= 0:
            return [] if isinstance(value, list) else None
        if isinstance(value, list):
            refs = [str(item).strip() for item in value if str(item).strip()]
            return refs[:limit]
        text = str(value or "").strip()
        if not text:
            return value
        return text if limit >= 1 else None

    _VIDEO_REFERENCE_IMAGE_OPTION_KEYS = (
        "image_urls",
        "imageUrls",
        "reference_image_urls",
        "referenceImageUrls",
        "filesUrl",
        "files_url",
        "fileUrl",
        "file_url",
        "input_urls",
    )
    _VIDEO_REFERENCE_VIDEO_OPTION_KEYS = (
        "reference_video_urls",
        "ref_video_urls",
        "referenceVideoUrls",
        "refVideoUrls",
    )

    def _append_unique_reference_values(self, refs: List[str], seen: set, value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                self._append_unique_reference_values(refs, seen, item)
            return
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            refs.append(text)

    def _collect_video_reference_image_urls(
        self,
        ref_image: Optional[Union[str, List[str]]] = None,
        tool_conf: Optional[Dict[str, Any]] = None,
        *,
        extra_sources: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        include_last_frame: bool = False,
        last_frame_url: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Collect ordered, de-duplicated video reference image URLs.

        Frontend video submit usually passes refs via provider_options.image_urls while
        reference_image_url is cleared; direct API callers may still use ref_image_url.
        """
        refs: List[str] = []
        seen: set = set()
        self._append_unique_reference_values(refs, seen, ref_image)

        source_dicts: List[Dict[str, Any]] = []
        if isinstance(tool_conf, dict):
            source_dicts.append(self._safe_json_dict(tool_conf))
        if isinstance(extra_sources, dict):
            source_dicts.append(self._safe_json_dict(extra_sources))
        elif isinstance(extra_sources, list):
            for item in extra_sources:
                if isinstance(item, dict):
                    source_dicts.append(self._safe_json_dict(item))

        for source in source_dicts:
            for key in self._VIDEO_REFERENCE_IMAGE_OPTION_KEYS:
                if key in source:
                    self._append_unique_reference_values(refs, seen, source.get(key))

        if include_last_frame:
            self._append_unique_reference_values(refs, seen, last_frame_url)

        limited = self._limit_reference_input(refs, limit)
        if isinstance(limited, list):
            return limited
        if isinstance(limited, str) and limited.strip():
            return [limited.strip()]
        return []

    def _normalize_video_reference_image_input(
        self,
        refs: Optional[Union[str, List[str]]],
    ) -> Optional[Union[str, List[str]]]:
        if isinstance(refs, list):
            cleaned = [str(item).strip() for item in refs if str(item).strip()]
        elif str(refs or "").strip():
            cleaned = [str(refs).strip()]
        else:
            cleaned = []
        if not cleaned:
            return None
        if len(cleaned) == 1:
            return cleaned[0]
        return cleaned

    def _collect_video_reference_video_urls(
        self,
        tool_conf: Optional[Dict[str, Any]] = None,
        *,
        extra_sources: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        refs: List[str] = []
        seen: set = set()

        source_dicts: List[Dict[str, Any]] = []
        if isinstance(tool_conf, dict):
            source_dicts.append(self._safe_json_dict(tool_conf))
        if isinstance(extra_sources, dict):
            source_dicts.append(self._safe_json_dict(extra_sources))
        elif isinstance(extra_sources, list):
            for item in extra_sources:
                if isinstance(item, dict):
                    source_dicts.append(self._safe_json_dict(item))

        for source in source_dicts:
            for key in self._VIDEO_REFERENCE_VIDEO_OPTION_KEYS:
                if key in source:
                    self._append_unique_reference_values(refs, seen, source.get(key))

        limited = self._limit_reference_input(refs, limit)
        if isinstance(limited, list):
            return limited
        if isinstance(limited, str) and limited.strip():
            return [limited.strip()]
        return []

    def _apply_runtime_capability_constraints(
        self,
        *,
        category: str,
        api_config: Optional[Dict[str, Any]],
        reference_image_url: Optional[Union[str, List[str]]] = None,
        last_frame_url: Optional[str] = None,
        keyframes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        runtime_config = dict(api_config or {})
        tool_conf = self._safe_json_dict(runtime_config.get("config"))
        runtime_config["config"] = tool_conf
        resolved_category = str(category or "").strip()

        image_ref_limit = self._get_runtime_capability_int(
            runtime_config,
            "reference_image_limit",
            "max_reference_images",
            "max_image_refs",
        )
        video_ref_limit = self._get_runtime_capability_int(
            runtime_config,
            "reference_video_limit",
            "max_reference_videos",
            "max_video_refs",
        )

        if resolved_category == "Image":
            supports_mask = self._get_runtime_capability_flag(runtime_config, "supports_mask", "mask_supported")
            if supports_mask is False:
                tool_conf.pop("maskUrl", None)
                tool_conf.pop("mask_url", None)

            if image_ref_limit is not None:
                reference_image_url = self._limit_reference_input(reference_image_url, image_ref_limit)
                for key in ("filesUrl", "image_urls", "imageUrls"):
                    raw = tool_conf.get(key)
                    if isinstance(raw, list):
                        tool_conf[key] = raw[:image_ref_limit]

        if resolved_category == "Video":
            supports_first_frame = self._get_runtime_capability_flag(
                runtime_config,
                "supports_first_frame",
                "supports_start_frame",
                "first_frame_supported",
                "start_frame_supported",
            )
            if supports_first_frame is False:
                reference_image_url = None if not isinstance(reference_image_url, list) else []

            supports_last_frame = self._get_runtime_capability_flag(
                runtime_config,
                "supports_last_frame",
                "supports_last_frame_mode",
                "last_frame_supported",
            )
            if supports_last_frame is False:
                last_frame_url = None
                tool_conf.pop("last_frame_url", None)
                tool_conf.pop("lastFrameUrl", None)

            sound_supported = self._get_runtime_capability_flag(
                runtime_config,
                "sound_supported",
                "has_audio",
                "audio_supported",
                "supports_audio",
            )
            if sound_supported is False:
                tool_conf["sound"] = True

            multi_shots_supported = self._get_runtime_capability_flag(
                runtime_config,
                "multi_shots_supported",
                "supports_multi_shots",
                "supports_multi_shot",
            )
            if multi_shots_supported is False:
                tool_conf["multi_shots"] = False
                tool_conf.pop("multi_prompt", None)

            supports_keyframes = self._get_runtime_capability_flag(
                runtime_config,
                "supports_keyframes",
                "keyframes_supported",
                "supports_multi_keyframes",
            )
            max_keyframes = self._get_runtime_capability_int(
                runtime_config,
                "max_keyframes",
                "keyframe_limit",
            )
            if supports_keyframes is False:
                keyframes = None
            elif isinstance(keyframes, list) and max_keyframes is not None:
                normalized_keyframes = [str(item).strip() for item in keyframes if str(item).strip()]
                keyframes = normalized_keyframes[:max_keyframes] if max_keyframes > 0 else []

            if image_ref_limit is not None:
                reference_image_url = self._limit_reference_input(reference_image_url, image_ref_limit)
                for key in ("image_urls", "imageUrls"):
                    raw = tool_conf.get(key)
                    if isinstance(raw, list):
                        tool_conf[key] = raw[:image_ref_limit]

            if video_ref_limit is not None:
                for key in ("reference_video_urls", "ref_video_urls"):
                    raw = tool_conf.get(key)
                    if isinstance(raw, list):
                        tool_conf[key] = raw[:video_ref_limit]

        if resolved_category == "Voice":
            timestamps_supported = self._get_runtime_capability_flag(
                runtime_config,
                "supports_timestamps",
                "timestamps_supported",
            )
            previous_text_supported = self._get_runtime_capability_flag(
                runtime_config,
                "supports_previous_text",
                "previous_text_supported",
                "supports_context_text",
                "context_text_supported",
            )
            next_text_supported = self._get_runtime_capability_flag(
                runtime_config,
                "supports_next_text",
                "next_text_supported",
                "supports_context_text",
                "context_text_supported",
            )
            if timestamps_supported is False:
                tool_conf.pop("timestamps", None)
            if previous_text_supported is False:
                tool_conf.pop("previous_text", None)
            if next_text_supported is False:
                tool_conf.pop("next_text", None)

        return {
            "api_config": runtime_config,
            "reference_image_url": reference_image_url,
            "last_frame_url": last_frame_url,
            "keyframes": keyframes,
        }

    async def _dispatch_image_generation(
        self,
        provider: str,
        prompt: str,
        active_config: Dict[str, Any],
        reference_image_url: Optional[Union[str, List[str]]],
        aspect_ratio: Optional[str],
        negative_prompt: Optional[str],
        image_size: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        runtime_activation = self._get_runtime_activation(active_config)
        if runtime_activation == "image_gemini_native":
            return await self._handle_n1n_generation("image", prompt, active_config, reference_image_url, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt, image_size=image_size)
        if runtime_activation == "image_n1n_kling_native":
            return await self._handle_n1n_kling_generation("image", prompt, active_config, reference_image_url, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt, image_size=image_size)
        if runtime_activation == "image_openai_compatible":
            return await self._handle_apiyi_generation("image", prompt, active_config, reference_image_url, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt, image_size=image_size)
        return None

    async def _dispatch_video_generation(
        self,
        provider: str,
        prompt: str,
        active_config: Dict[str, Any],
        reference_image_url: Optional[Union[str, List[str]]],
        last_frame_url: Optional[str],
        duration: int,
        aspect_ratio: Optional[str],
        keyframes: Optional[List[str]],
        negative_prompt: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        runtime_activation = self._get_runtime_activation(active_config)
        if runtime_activation == "video_openai_compatible":
            return await self._handle_apiyi_generation("video", prompt, active_config, reference_image_url, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt)
        return None

    async def _dispatch_voice_generation(
        self,
        provider: str,
        prompt: str,
        active_config: Dict[str, Any],
        duration: int,
        negative_prompt: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        runtime_activation = self._get_runtime_activation(active_config)
        if runtime_activation == "audio_kie_compatible":
            return await self._handle_kie_generation(
                "audio",
                prompt,
                active_config,
                None,
                duration=duration,
                negative_prompt=negative_prompt,
            )
        if runtime_activation == "audio_runninghub_compatible":
            return await self._handle_runninghub_generation(
                "audio",
                prompt,
                active_config,
                duration=duration,
                negative_prompt=negative_prompt,
            )
        return None

    def _pick_system_setting_fallback(self, session, category: str, provider: Optional[str] = None) -> Optional[SystemAPISetting]:
        # Prefer task-default system setting when no provider is pinned.
        if not str(provider or "").strip():
            default_row = get_task_default_system_setting(session, category)
            if default_row:
                deprecated_default = self._is_deprecated_system_config(getattr(default_row, "config", None), getattr(default_row, "deprecated", None))
                if not deprecated_default:
                    _debug_log(
                        f"API_FALLBACK_TRACE picker category={category} provider={provider or '<none>'} selected=task_default setting_id={getattr(default_row, 'id', None)} mapped_provider={getattr(default_row, 'provider', None)} mapped_model={getattr(default_row, 'model', None)}"
                    )
                    return default_row
                _debug_log(
                    f"API_FALLBACK_TRACE picker category={category} provider={provider or '<none>'} skip_task_default setting_id={getattr(default_row, 'id', None)} deprecated={deprecated_default} mapped_provider={getattr(default_row, 'provider', None)} mapped_model={getattr(default_row, 'model', None)}",
                    "warning",
                )

        normalized_provider = self._normalize_provider_name(provider, category) if provider else ""
        query = self._system_setting_query(session, provider=normalized_provider or None, category=category)

        rows = query.order_by(SystemAPISetting.id.desc()).all()
        for row in rows:
            if self._is_deprecated_system_config(getattr(row, "config", None), getattr(row, "deprecated", None)):
                continue
            _debug_log(
                f"API_FALLBACK_TRACE picker category={category} provider={provider or '<none>'} selected=category_fallback setting_id={getattr(row, 'id', None)} selected_provider={getattr(row, 'provider', None)} selected_model={getattr(row, 'model', None)}"
            )
            return row
        _debug_log(
            f"API_FALLBACK_TRACE picker category={category} provider={provider or '<none>'} selected=<none>",
            "warning",
        )
        return None

    def _is_smart_routing_enabled(self, session, user_id: int) -> bool:
        rows = session.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.category == "Tools",
        ).order_by(APISetting.id.desc()).all()

        if not rows:
            return True

        # APISetting is now a lightweight user/category binding and no longer stores
        # provider/config payload. Use mode as the smart-routing switch instead.
        # fixed -> disabled; smart_default/low_price_replace -> enabled.
        for row in rows:
            strategy = self._normalize_api_strategy(
                getattr(row, "mode", None),
                default=self.USER_API_STRATEGY_SMART_DEFAULT,
            )
            return strategy != self.USER_API_STRATEGY_FIXED

        return True

    def _get_system_candidates(self, session, category: str, modality: str = None) -> List[Dict[str, Any]]:
        defaults = {
            "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4-turbo-preview"},
            "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-3-opus-20240229"},
            "stability": {"base_url": "https://api.stability.ai", "model": "stable-diffusion-xl-1024-v1-0"},
            "runway": {"base_url": "https://api.runwayml.com", "model": "gen-2"},
            "elevenlabs": {"base_url": "https://api.elevenlabs.io/v1", "model": "premade/Adam"},
            "doubao": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-seedream-4-5-251128"},
            "grsai": {"base_url": "https://grsaiapi.com", "model": "sora-image"},
            "kie": {"base_url": "https://api.kie.ai", "model": "veo-3-1-fast"},
            "tencent": {"base_url": "https://aiart.tencentcloudapi.com", "model": "hunyuan-vision"},
            "wanxiang": {"base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis", "model": "wanx2.1-i2v-plus"},
            "happyhorse": {"base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis", "model": "happyhorse-1.0-r2v"},
            "vidu": {"base_url": "https://api.vidu.studio/open/v1/creation/video", "model": "vidu2.0"},
            "runninghub": {"base_url": "https://www.runninghub.cn", "model": "runninghub-model"},
            "pixelmove": {"base_url": "https://portal.pixelmove.ai", "model": "seedance-2.0"},
        }

        rows = self._system_setting_query(session, category=category).order_by(SystemAPISetting.id.asc()).all()

        candidates: List[Dict[str, Any]] = []
        provider_bundle_cache: Dict[str, Dict[str, Any]] = {}
        target_generation_mode = self._normalize_generation_mode(modality)
        for row in rows:
            provider = self._normalize_provider_name(row.provider, category)
            if not provider:
                continue
            if self._is_deprecated_system_config(row.config, getattr(row, "deprecated", None)):
                continue
            # Modality filtering: if a modality is requested, skip rows whose
            # modality is non-empty and does not contain the requested value.
            # Empty/null modality on the row means "compatible with all".
            if modality:
                from app.services.modality_utils import modality_matches
                if not modality_matches(getattr(row, "modality", None), modality):
                    continue
            cfg = self._safe_json_dict(row.config)
            if target_generation_mode and not self._system_row_supports_generation_mode(row, target_generation_mode, cfg):
                continue

            if provider not in provider_bundle_cache:
                provider_bundle_cache[provider] = self._collect_provider_key_pool_bundle(session, category, provider)
            provider_pool_bundle = provider_bundle_cache.get(provider) or {}

            merged_config = self._safe_json_dict(row.config)
            pooled_keys = self._normalize_api_keys(provider_pool_bundle.get("provider_api_keys"))
            if pooled_keys:
                merged_config["provider_api_keys"] = pooled_keys
                strategy = str(provider_pool_bundle.get("provider_api_key_strategy") or "random").strip().lower()
                if strategy in {"random", "round_robin", "weighted"}:
                    merged_config["provider_api_key_strategy"] = strategy
                if strategy == "weighted":
                    merged_config["provider_api_key_weights"] = provider_pool_bundle.get("provider_api_key_weights") or []

            priority_raw = cfg.get("smart_priority", cfg.get("priority", 100))
            retry_raw = cfg.get("smart_retry_limit", cfg.get("retry_limit"))
            try:
                priority = int(priority_raw)
            except Exception:
                priority = 100
            try:
                retry_limit = int(retry_raw) if retry_raw is not None else None
            except Exception:
                retry_limit = None
            candidate_config = self._setting_to_config(row, provider, defaults)
            candidates.append({
                "id": row.id,
                "provider": provider,
                "model": candidate_config.get("model") or row.model,
                "priority": priority,
                "retry_limit": retry_limit,
                "retry_group": self._get_retry_group_from_config(cfg),
                "retry_price_group": self._get_retry_price_group_from_config(cfg),
                "is_multi_ref_default": bool(cfg.get("smart_multi_ref_default")),
                "avg_price_estimate": int((BillingService.estimate_system_api_average_price(
                    session,
                    int(row.id),
                    generation_mode=target_generation_mode,
                ) or {}).get("average_cost") or 0),
                "config": {
                    **candidate_config,
                    "config": {
                        **candidate_config.get("config", {}),
                        **merged_config,
                        "__resolved_source": f"smart_candidate:{provider}/{row.model}",
                        "__resolved_setting_id": row.id,
                    },
                },
            })

        return candidates

    async def _execute_generation_by_provider(
        self,
        category: str,
        provider: str,
        prompt: str,
        negative_prompt: Optional[str],
        api_config: Dict[str, Any],
        reference_image_url: Optional[Union[str, List[str]]],
        width: Optional[int] = None,
        height: Optional[int] = None,
        image_size: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        duration: int = 5,
        keyframes: Optional[List[str]] = None,
        ref_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        runtime_config = dict(api_config or {})
        runtime_inner_cfg = self._safe_json_dict(runtime_config.get("config"))
        if provider:
            runtime_inner_cfg.setdefault("provider", provider)
            runtime_inner_cfg.setdefault("__provider", provider)

        provider_key_pool = self._normalize_api_keys(runtime_inner_cfg.get("provider_api_keys"))
        fallback_key_pool = self._normalize_api_keys(runtime_config.get("api_key"))
        selectable_key_pool = provider_key_pool or fallback_key_pool

        runtime_config["api_key"] = self._pick_runtime_api_key(
            runtime_inner_cfg,
            selectable_key_pool if selectable_key_pool else runtime_config.get("api_key"),
        )
        runtime_config["config"] = runtime_inner_cfg

        def _is_auth_key_error(result: Dict[str, Any]) -> bool:
            if not isinstance(result, dict):
                return False
            error_text = self._flatten_text(result.get("error") or "").lower()
            details_text = self._flatten_text(result.get("details") or "").lower()
            merged = f"{error_text} {details_text}".strip()
            if not merged:
                return False
            markers = (
                "apikey error",
                "api key error",
                "invalid api key",
                "invalid_api_key",
                "authentication",
                "unauthorized",
                "401",
            )
            return any(token in merged for token in markers)

        async def _dispatch_with_config(active_config: Dict[str, Any]) -> Dict[str, Any]:
            constrained_inputs = self._apply_runtime_capability_constraints(
                category=category,
                api_config=active_config,
                reference_image_url=reference_image_url,
                last_frame_url=last_frame_url,
                keyframes=keyframes,
            )
            active_config = constrained_inputs.get("api_config") or active_config
            effective_reference_image_url = constrained_inputs.get("reference_image_url")
            effective_last_frame_url = constrained_inputs.get("last_frame_url")
            effective_keyframes = constrained_inputs.get("keyframes")

            if str(category or "").strip() == "Video":
                merged_video_image_refs = self._collect_video_reference_image_urls(
                    effective_reference_image_url,
                    (active_config.get("config") or {}),
                    extra_sources=active_config,
                )
                effective_reference_image_url = self._normalize_video_reference_image_input(
                    merged_video_image_refs
                )

            normalized_inputs = self._apply_runtime_enum_constraints(
                runtime_config=active_config,
                category=category,
                aspect_ratio=aspect_ratio,
                duration=duration,
                image_size=image_size,
            )
            effective_aspect_ratio = normalized_inputs.get("aspect_ratio")
            effective_duration = normalized_inputs.get("duration")
            if effective_duration is None:
                effective_duration = duration
            effective_image_size = normalized_inputs.get("image_size")
            effective_provider = self._normalize_provider_name(
                active_config.get("provider") or provider,
                category,
            )

            if category == "Image":
                if width and height:
                    if not active_config.get("config"):
                        active_config["config"] = {}
                    active_config["config"]["width"] = width
                    active_config["config"]["height"] = height
                normalized_image_size = self._normalize_image_size_value(effective_image_size)
                if normalized_image_size:
                    if not active_config.get("config"):
                        active_config["config"] = {}
                    active_config["config"]["image_size"] = normalized_image_size

                runtime_result = await self._dispatch_image_generation(
                    effective_provider,
                    prompt,
                    active_config,
                    effective_reference_image_url,
                    effective_aspect_ratio,
                    negative_prompt,
                    normalized_image_size,
                )
                if runtime_result is not None:
                    return runtime_result

                if effective_provider in ["doubao", "ark"]:
                    return await self._handle_doubao_generation(
                        "image",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                        image_size=normalized_image_size,
                    )
                if effective_provider == "grsai":
                    return await self._handle_grsai_generation("image", prompt, active_config, effective_reference_image_url, aspect_ratio=effective_aspect_ratio, negative_prompt=negative_prompt, image_size=normalized_image_size)
                if effective_provider == "kie":
                    return await self._handle_kie_generation(
                        "image",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                        image_size=normalized_image_size,
                    )
                if effective_provider == "tencent":
                    return await self._handle_tencent_generation("image", prompt, active_config, effective_reference_image_url, negative_prompt=negative_prompt)
                if effective_provider == "n1n":
                    return await self._handle_n1n_generation(
                        "image",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                        image_size=normalized_image_size,
                    )
                if effective_provider == "apiyi":
                    return await self._handle_apiyi_generation(
                        "image",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                        image_size=normalized_image_size,
                    )
                if effective_provider == "aiclub":
                    return await self._handle_aiclub_generation(
                        "image",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                        image_size=normalized_image_size,
                    )
                if effective_provider == "runninghub":
                    return await self._handle_runninghub_generation(
                        "image",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                        image_size=normalized_image_size,
                    )
                if effective_provider in ["stability", "stable diffusion"]:
                    return await self._handle_stability_generation("image", prompt, active_config, effective_reference_image_url, negative_prompt=negative_prompt)

                _debug_log(f"No runnable Image handler for provider={effective_provider}", "warning")
                return {
                    "error": f"No runnable image handler configured for provider: {effective_provider}",
                    "submit_failed": True,
                    "details": {
                        "provider": effective_provider,
                        "model": active_config.get("model", "default"),
                        "category": "Image",
                    },
                }

            if category == "Video":
                runtime_result = await self._dispatch_video_generation(
                    effective_provider,
                    prompt,
                    active_config,
                    effective_reference_image_url,
                    effective_last_frame_url,
                    effective_duration,
                    effective_aspect_ratio,
                    effective_keyframes,
                    negative_prompt,
                )
                if runtime_result is not None:
                    return runtime_result

                if effective_provider in ["doubao", "ark"]:
                    return await self._handle_doubao_generation("video", prompt, active_config, effective_reference_image_url, last_frame_url=effective_last_frame_url, duration=effective_duration, aspect_ratio=effective_aspect_ratio, negative_prompt=negative_prompt)
                if effective_provider == "grsai":
                    return await self._handle_grsai_generation("video", prompt, active_config, effective_reference_image_url, last_frame_url=effective_last_frame_url, duration=effective_duration, aspect_ratio=effective_aspect_ratio, negative_prompt=negative_prompt)
                if effective_provider == "ark-seedance":
                    return await self._handle_ark_seedance_generation("video", prompt, active_config, effective_reference_image_url, last_frame_url=effective_last_frame_url, duration=effective_duration, aspect_ratio=effective_aspect_ratio)
                if effective_provider == "kie":
                    return await self._handle_kie_generation(
                        "video",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        last_frame_url=effective_last_frame_url,
                        duration=effective_duration,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                    )
                if effective_provider == "tencent":
                    return await self._handle_tencent_generation("video", prompt, active_config, effective_reference_image_url, duration=effective_duration, negative_prompt=negative_prompt)
                if effective_provider in ["wanxiang", "wanx"]:
                    return await self._handle_wanxiang_generation("video", prompt, active_config, effective_reference_image_url, last_frame_url=effective_last_frame_url, duration=effective_duration, aspect_ratio=effective_aspect_ratio, negative_prompt=negative_prompt)
                if effective_provider == "happyhorse":
                    return await self._handle_happyhorse_generation(
                        "video",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        duration=effective_duration,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                    )
                if effective_provider == "vidu":
                    return await self._handle_vidu_generation("video", prompt, active_config, effective_reference_image_url, last_frame_url=effective_last_frame_url, duration=effective_duration, aspect_ratio=effective_aspect_ratio, keyframes=effective_keyframes, negative_prompt=negative_prompt)
                if effective_provider == "runninghub":
                    return await self._handle_runninghub_generation("video", prompt, active_config, effective_reference_image_url, last_frame_url=effective_last_frame_url, duration=effective_duration, aspect_ratio=effective_aspect_ratio, negative_prompt=negative_prompt, ref_mode=ref_mode)
                if effective_provider == "apiyi":
                    return await self._handle_apiyi_generation(
                        "video",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        last_frame_url=effective_last_frame_url,
                        duration=effective_duration,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                    )
                if effective_provider == "aiclub":
                    return await self._handle_aiclub_generation(
                        "video",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        last_frame_url=effective_last_frame_url,
                        duration=effective_duration,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                    )
                if effective_provider == "pixelmove":
                    return await self._handle_pixelmove_generation(
                        "video",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        last_frame_url=effective_last_frame_url,
                        duration=effective_duration,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                    )
                if effective_provider == "zlhub":
                    return await self._handle_zlhub_generation(
                        "video",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        last_frame_url=effective_last_frame_url,
                        duration=effective_duration,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                        ref_mode=ref_mode,
                    )

                # Some system rows may carry a generic/legacy provider while model is HappyHorse.
                # Keep video generation resilient by dispatching via model hint before hard-failing.
                model_hint = str((active_config or {}).get("model") or "").strip().lower()
                if "happyhorse" in model_hint:
                    return await self._handle_happyhorse_generation(
                        "video",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        duration=effective_duration,
                        aspect_ratio=effective_aspect_ratio,
                        negative_prompt=negative_prompt,
                    )

                _debug_log(f"No runnable Video handler for provider={effective_provider}", "warning")
                return {
                    "error": f"No runnable video handler configured for provider: {effective_provider}",
                    "submit_failed": True,
                    "details": {
                        "provider": effective_provider,
                        "model": active_config.get("model", "default"),
                        "duration": duration,
                        "category": "Video",
                    },
                }

            if category == "Voice":
                runtime_result = await self._dispatch_voice_generation(
                    effective_provider,
                    prompt,
                    active_config,
                    effective_duration,
                    negative_prompt,
                )
                if runtime_result is not None:
                    return runtime_result

                if effective_provider == "kie":
                    return await self._handle_kie_generation(
                        "audio",
                        prompt,
                        active_config,
                        reference_image_url,
                        duration=effective_duration,
                        negative_prompt=negative_prompt,
                    )
                if effective_provider == "runninghub":
                    return await self._handle_runninghub_generation(
                        "audio",
                        prompt,
                        active_config,
                        duration=effective_duration,
                        negative_prompt=negative_prompt,
                    )

                _debug_log(f"No runnable Voice handler for provider={effective_provider}", "warning")
                return {
                    "error": f"No runnable voice handler configured for provider: {effective_provider}",
                    "submit_failed": True,
                    "details": {
                        "provider": effective_provider,
                        "model": active_config.get("model", "default"),
                        "category": "Voice",
                    },
                }

            return {"error": f"Unsupported category: {category}"}

        first_result = await _dispatch_with_config(runtime_config)

        # When upstream rejects current key (e.g. "apikey error"), rotate within pool and retry.
        if bool((first_result or {}).get("submit_failed")) and _is_auth_key_error(first_result) and len(selectable_key_pool) > 1:
            selected_key = str(runtime_config.get("api_key") or "").strip()
            retry_keys = [k for k in selectable_key_pool if str(k or "").strip() and str(k).strip() != selected_key]
            last_result = first_result
            for idx, alt_key in enumerate(retry_keys, start=1):
                retry_config = dict(runtime_config)
                retry_config["api_key"] = str(alt_key).strip()
                key_tail = str(alt_key).strip()[-4:] if str(alt_key).strip() else ""
                logger.warning(
                    "Provider auth retry with alternate pooled key | provider=%s category=%s retry=%s key_tail=%s",
                    provider,
                    category,
                    idx,
                    key_tail,
                )
                retry_result = await _dispatch_with_config(retry_config)
                if not bool((retry_result or {}).get("submit_failed")):
                    return retry_result
                last_result = retry_result
                if not _is_auth_key_error(retry_result):
                    return retry_result
            return last_result

        return first_result

    async def _generate_with_smart_routing(
        self,
        category: str,
        prompt: str,
        negative_prompt: Optional[str],
        provider: str,
        api_config: Dict[str, Any],
        user_id: int,
        reference_image_url: Optional[Union[str, List[str]]],
        width: Optional[int] = None,
        height: Optional[int] = None,
        image_size: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        duration: int = 5,
        keyframes: Optional[List[str]] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        requested_model: Optional[str] = None,
        explicit_selection: bool = False,
        allow_priority_fallback_when_explicit: bool = False,
        fallback_candidate_limit: int = 3,
        modality: str = None,
        api_strategy: str = USER_API_STRATEGY_SMART_DEFAULT,
        primary_retry_limit: int = 3,
    ) -> Dict[str, Any]:
        with SessionLocal() as session:
            smart_enabled = self._is_smart_routing_enabled(session, user_id)
            candidates = self._get_system_candidates(session, category, modality=modality)

        strategy = self._normalize_api_strategy(api_strategy)
        smart_default_strategy = strategy == self.USER_API_STRATEGY_SMART_DEFAULT
        legacy_strategy = strategy not in {
            self.USER_API_STRATEGY_FIXED,
            self.USER_API_STRATEGY_SMART_DEFAULT,
            self.USER_API_STRATEGY_LOW_PRICE_REPLACE,
        }
        media_retry_mode = category in {"Image", "Video", "Voice"}

        if allow_priority_fallback_when_explicit and legacy_strategy:
            smart_enabled = True

        if explicit_selection and (legacy_strategy or smart_default_strategy):
            if allow_priority_fallback_when_explicit:
                logger.info(
                    "Smart routing kept for explicit selection (fallback-enabled) | category=%s user_id=%s provider=%s model=%s fallback_limit=%s",
                    category,
                    user_id,
                    provider,
                    requested_model,
                    fallback_candidate_limit,
                )
            else:
                logger.info(
                    "Smart routing bypassed for explicit selection | category=%s user_id=%s provider=%s model=%s",
                    category,
                    user_id,
                    provider,
                    requested_model,
                )
                smart_enabled = False

        effective_provider = self._normalize_provider_name(provider, category)
        request_provider_options = {}
        if isinstance((api_config or {}).get("__request_provider_options"), dict):
            request_provider_options = dict((api_config or {}).get("__request_provider_options") or {})

        def _merge_request_provider_options(config_obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            merged_config_obj = dict(config_obj or {})
            if request_provider_options:
                merged_inner = self._safe_json_dict(merged_config_obj.get("config"))
                merged_inner.update(request_provider_options)
                merged_config_obj["config"] = merged_inner
            return merged_config_obj

        baseline_config = _merge_request_provider_options(api_config)
        if requested_model:
            baseline_config["model"] = requested_model

        target_generation_mode = self._normalize_generation_mode(modality)
        if target_generation_mode and candidates and not explicit_selection:
            baseline_matches_candidate = any(
                c.get("provider") == effective_provider
                and str(c.get("model") or "") == str(baseline_config.get("model") or "")
                for c in candidates
            )
            if not baseline_matches_candidate:
                replacement_candidate = next((c for c in candidates if c.get("provider") == effective_provider), None)
                if replacement_candidate:
                    logger.info(
                        "Smart routing baseline remapped by modality | category=%s user_id=%s modality=%s provider=%s from_model=%s to_model=%s",
                        category,
                        user_id,
                        target_generation_mode,
                        effective_provider,
                        baseline_config.get("model"),
                        replacement_candidate.get("model"),
                    )
                    baseline_config = _merge_request_provider_options(replacement_candidate.get("config"))
                    effective_provider = self._normalize_provider_name(replacement_candidate.get("provider"), category)

        selected_setting_id = ((baseline_config.get("config") or {}).get("__resolved_setting_id")) if isinstance(baseline_config, dict) else None
        selected_candidate = None
        if selected_setting_id is not None:
            selected_candidate = next((c for c in candidates if int(c.get("id") or 0) == int(selected_setting_id or 0)), None)
        if selected_candidate is None:
            selected_candidate = next(
                (
                    c for c in candidates
                    if c.get("provider") == effective_provider
                    and str(c.get("model") or "") == str(baseline_config.get("model") or "")
                ),
                None,
            )

        selected_retry_group = self._normalize_retry_group(
            (selected_candidate or {}).get("retry_group")
            or self._get_retry_group_from_config((baseline_config or {}).get("config"))
        )
        selected_retry_price_group = self._normalize_retry_group(
            (selected_candidate or {}).get("retry_price_group")
            or self._get_retry_price_group_from_config((baseline_config or {}).get("config"))
        )

        fallback_candidates: List[Dict[str, Any]] = []
        effective_fallback_candidate_limit = max(0, int(fallback_candidate_limit or 0))
        total_attempt_limit: Optional[int] = None
        if media_retry_mode:
            selected_candidate_retry_limit = None
            try:
                if (selected_candidate or {}).get("retry_limit") is not None:
                    selected_candidate_retry_limit = int((selected_candidate or {}).get("retry_limit"))
            except Exception:
                selected_candidate_retry_limit = None

            retry_limit = self._get_media_routing_limit(
                category,
                "ROUTING_PRIMARY_RETRY_LIMIT",
                selected_candidate_retry_limit if selected_candidate_retry_limit is not None else int(primary_retry_limit if primary_retry_limit is not None else 2),
                1,
                5,
            )
            effective_fallback_candidate_limit = self._get_media_routing_limit(
                category,
                "ROUTING_FALLBACK_CANDIDATE_LIMIT",
                effective_fallback_candidate_limit if effective_fallback_candidate_limit is not None else 1,
                0,
                5,
            )
            fallback_candidates = sorted(
                [
                    c for c in candidates
                    if c.get("provider")
                    and int(c.get("id") or 0) != int((selected_candidate or {}).get("id") or 0)
                    and selected_retry_group
                    and self._normalize_retry_group(c.get("retry_group")) == selected_retry_group
                    and selected_retry_price_group
                    and self._normalize_retry_group(c.get("retry_price_group")) == selected_retry_price_group
                ],
                key=lambda x: (
                    int(x.get("priority", 100) or 100),
                    int(x.get("avg_price_estimate", 10**9) or 10**9),
                    int(x.get("id", 0) or 0),
                ),
            )
            if effective_fallback_candidate_limit > 0:
                fallback_candidates = fallback_candidates[:effective_fallback_candidate_limit]
            else:
                fallback_candidates = []

            total_attempt_limit = self._get_media_routing_limit(
                category,
                "ROUTING_TOTAL_ATTEMPT_LIMIT",
                min(3, retry_limit + max(0, effective_fallback_candidate_limit)),
                1,
                8,
            )
        else:
            if strategy == self.USER_API_STRATEGY_LOW_PRICE_REPLACE:
                fallback_candidates = sorted(
                    [
                        c for c in candidates
                        if c.get("provider") and not (
                            c.get("provider") == effective_provider
                            and str(c.get("model") or "") == str(baseline_config.get("model") or "")
                        )
                    ],
                    key=lambda x: (
                        int(x.get("avg_price_estimate", 10**9) or 10**9),
                        int(x.get("priority", 100) or 100),
                        int(x.get("id", 0) or 0),
                    ),
                )
                if effective_fallback_candidate_limit and effective_fallback_candidate_limit > 0:
                    fallback_candidates = fallback_candidates[: int(effective_fallback_candidate_limit)]
            elif strategy == self.USER_API_STRATEGY_SMART_DEFAULT:
                fallback_candidates = sorted(
                    [
                        c for c in candidates
                        if c.get("provider") and not (
                            c.get("provider") == effective_provider
                            and str(c.get("model") or "") == str(baseline_config.get("model") or "")
                        )
                    ],
                    key=lambda x: (
                        int(x.get("avg_price_estimate", 10**9) or 10**9),
                        int(x.get("priority", 100) or 100),
                        int(x.get("id", 0) or 0),
                    ),
                )
                if effective_fallback_candidate_limit and effective_fallback_candidate_limit > 0:
                    fallback_candidates = fallback_candidates[: int(effective_fallback_candidate_limit)]
            elif legacy_strategy and smart_enabled:
                fallback_candidates = sorted(
                    [
                        c for c in candidates
                        if c.get("provider") and not (
                            c.get("provider") == effective_provider
                            and str(c.get("model") or "") == str(baseline_config.get("model") or "")
                        )
                    ],
                    key=lambda x: (
                        int(x.get("avg_price_estimate", 10**9) or 10**9),
                        int(x.get("priority", 100) or 100),
                        int(x.get("id", 0) or 0),
                    ),
                )
                if effective_fallback_candidate_limit and effective_fallback_candidate_limit > 0:
                    fallback_candidates = fallback_candidates[: int(effective_fallback_candidate_limit)]

            retry_limit = max(1, int(primary_retry_limit if primary_retry_limit is not None else 3))
            if legacy_strategy:
                retry_limit = 2
            for c in candidates:
                if c.get("provider") == effective_provider and c.get("retry_limit") is not None:
                    if legacy_strategy:
                        retry_limit = max(1, int(c.get("retry_limit")))
                    break

        multi_ref_count = len(reference_image_url) if isinstance(reference_image_url, list) else 0
        attempt_items: List[Dict[str, Any]] = []

        if (not media_retry_mode) and smart_enabled and category == "Image" and multi_ref_count > 4:
            multi_ref_target = sorted(
                [c for c in candidates if c.get("is_multi_ref_default")],
                key=lambda x: (x.get("priority", 100), x.get("id", 0)),
            )
            if multi_ref_target:
                first = multi_ref_target[0]
                attempt_items.append({
                    "provider": first.get("provider"),
                    "config": _merge_request_provider_options(first.get("config")),
                    "tag": "multi_ref_default",
                })

        for _ in range(retry_limit):
            attempt_items.append({
                "provider": effective_provider,
                "config": _merge_request_provider_options(baseline_config),
                "tag": "active_retry",
            })

        if media_retry_mode:
            for c in fallback_candidates:
                attempt_items.append({
                    "provider": c.get("provider"),
                    "config": _merge_request_provider_options(c.get("config")),
                    "tag": "group_fallback",
                })
        elif strategy == self.USER_API_STRATEGY_LOW_PRICE_REPLACE:
            for c in fallback_candidates:
                attempt_items.append({
                    "provider": c.get("provider"),
                    "config": _merge_request_provider_options(c.get("config")),
                    "tag": "priority_fallback",
                })
        elif smart_enabled and legacy_strategy:
            for c in fallback_candidates:
                attempt_items.append({
                    "provider": c.get("provider"),
                    "config": _merge_request_provider_options(c.get("config")),
                    "tag": "priority_fallback",
                })

        seen = set()
        deduped_attempts: List[Dict[str, Any]] = []
        for idx, item in enumerate(attempt_items):
            key = (idx if item.get("tag") == "active_retry" else None, item.get("provider"), item.get("config", {}).get("model"), item.get("tag"))
            if item.get("tag") != "active_retry" and key in seen:
                continue
            seen.add(key)
            deduped_attempts.append(item)

        if media_retry_mode and total_attempt_limit is not None and len(deduped_attempts) > total_attempt_limit:
            deduped_attempts = deduped_attempts[:total_attempt_limit]

        attempt_sequence = ", ".join(
            [f"[{i+1}]{att.get('tag')}:{self._normalize_provider_name(att.get('provider'), category)}/{((att.get('config') or {}).get('model') or 'unknown')}" for i, att in enumerate(deduped_attempts)]
        )

        logger.info(
            "Media routing plan (API Selection Process) | category=%s user_id=%s "
            "strategy=%s explicit_selection=%s allow_fallback=%s "
            "primary_provider=%s primary_model=%s active_retry_limit=%s fallback_limit=%s total_attempt_limit=%s planned_attempts=%s sequence=%s",
            category,
            user_id,
            strategy,
            explicit_selection,
            allow_priority_fallback_when_explicit,
            effective_provider,
            baseline_config.get("model"),
            retry_limit,
            effective_fallback_candidate_limit,
            total_attempt_limit if media_retry_mode else len(deduped_attempts),
            len(deduped_attempts),
            attempt_sequence,
        )

        final_error: Dict[str, Any] = {"error": "Generation failed"}
        fallback_unlocked = False

        for index, attempt in enumerate(deduped_attempts, start=1):
            if attempt.get("tag") in {"priority_fallback", "group_fallback"} and not fallback_unlocked:
                continue

            selected_provider = self._normalize_provider_name(attempt.get("provider"), category)
            selected_config = _merge_request_provider_options(attempt.get("config"))
            if not selected_provider:
                continue

            logger.info(
                "Media routing attempt | category=%s user_id=%s attempt=%s/%s provider=%s model=%s tag=%s group=%s price_group=%s",
                category,
                user_id,
                index,
                len(deduped_attempts),
                selected_provider,
                selected_config.get("model"),
                attempt.get("tag"),
                selected_retry_group or "-",
                selected_retry_price_group or "-",
            )

            ref_mode = provider_options.get("ref_mode") if isinstance(provider_options, dict) else None
            
            result = await self._execute_generation_by_provider(
                category=category,
                provider=selected_provider,
                prompt=prompt,
                negative_prompt=negative_prompt,
                api_config=selected_config,
                reference_image_url=reference_image_url,
                width=width,
                height=height,
                image_size=image_size,
                aspect_ratio=aspect_ratio,
                last_frame_url=last_frame_url,
                duration=duration,
                keyframes=keyframes,
                ref_mode=ref_mode,
            )

            if result and not result.get("error"):
                metadata = result.get("metadata") or {}
                fallback_used = bool(fallback_unlocked) or attempt.get("tag") in {"priority_fallback", "group_fallback"}
                resolved_setting_id = (selected_config.get("config") or {}).get("__resolved_setting_id")
                resolved_model = str(selected_config.get("model") or metadata.get("model") or "").strip()
                logger.info(
                    "Media routing success | category=%s user_id=%s attempt=%s/%s provider=%s model=%s tag=%s fallback_used=%s",
                    category,
                    user_id,
                    index,
                    len(deduped_attempts),
                    selected_provider,
                    selected_config.get("model"),
                    attempt.get("tag"),
                    fallback_used,
                )
                metadata["smart_routing"] = {
                    "enabled": smart_enabled,
                    "attempt": index,
                    "attempt_tag": attempt.get("tag"),
                    "provider": selected_provider,
                    "model": resolved_model,
                    "fallback_used": bool(fallback_used),
                    "retry_group": selected_retry_group or None,
                    "retry_price_group": selected_retry_price_group or None,
                    "system_api_id": int(resolved_setting_id) if resolved_setting_id is not None else None,
                    "initial_provider": effective_provider,
                    "initial_model": str(baseline_config.get("model") or "").strip(),
                }
                metadata["provider"] = selected_provider
                if resolved_model:
                    metadata["model"] = resolved_model
                if resolved_setting_id is not None:
                    metadata["system_api_id"] = int(resolved_setting_id)
                result["metadata"] = metadata
                return result

            final_error = result or {"error": "Generation failed"}
            if isinstance(final_error, dict):
                runtime_model = final_error.get("runtime_model")
                final_error["_attempt_provider"] = selected_provider
                final_error["_attempt_model"] = runtime_model or selected_config.get("model")
                final_error["_attempt_tag"] = attempt.get("tag")
            retry_state = self._classify_media_retry(result)
            fallback_triggered_now = bool(retry_state.get("retryable"))
            fallback_reason = str(retry_state.get("reason") or "unknown")

            error_detail = str((result or {}).get("error") or "").strip() if isinstance(result, dict) else ""
            next_fallback_provider = ""
            next_fallback_model = ""
            if fallback_triggered_now:
                for next_attempt in deduped_attempts[index:]:
                    if next_attempt.get("tag") not in {"priority_fallback", "group_fallback"}:
                        continue
                    candidate_provider = self._normalize_provider_name(next_attempt.get("provider"), category)
                    if not candidate_provider:
                        continue
                    next_fallback_provider = candidate_provider
                    next_fallback_model = str((next_attempt.get("config") or {}).get("model") or "").strip()
                    break

            logger.warning(
                "Media routing failed | category=%s user_id=%s attempt=%s/%s provider=%s model=%s tag=%s reason=%s next_provider=%s next_model=%s error=%s",
                category,
                user_id,
                index,
                len(deduped_attempts),
                selected_provider,
                selected_config.get("model"),
                attempt.get("tag"),
                fallback_reason or "non_retryable",
                next_fallback_provider,
                next_fallback_model,
                error_detail,
            )

            if fallback_triggered_now:
                if not fallback_unlocked:
                    logger.info(
                        "Media routing fallback enabled | category=%s user_id=%s trigger_attempt=%s provider=%s reason=%s group=%s price_group=%s",
                        category,
                        user_id,
                        index,
                        selected_provider,
                        fallback_reason,
                        selected_retry_group or "-",
                        selected_retry_price_group or "-",
                    )
                fallback_unlocked = True
                continue

            return final_error

        return final_error

    def get_api_config(
        self,
        provider: str,
        user_id: int = 1,
        category: str = None,
        requested_model: Optional[str] = None,
        user_credits: int = 0,
        strict_provider: bool = False,
        function_name: Optional[str] = None,
        system_api_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Resolves runtime API configuration by category active user setting -> system provider+model match."""
        defaults = {
            "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4-turbo-preview"},
            "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-3-opus-20240229"},
            "stability": {"base_url": "https://api.stability.ai", "model": "stable-diffusion-xl-1024-v1-0"},
            "runway": {"base_url": "https://api.runwayml.com", "model": "gen-2"},
            "elevenlabs": {"base_url": "https://api.elevenlabs.io/v1", "model": "premade/Adam"},
            "doubao": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-seedream-4-5-251128"},
            "grsai": {"base_url": "https://grsaiapi.com", "model": "sora-image"},
            "tencent": {"base_url": "https://aiart.tencentcloudapi.com", "model": "hunyuan-vision"},
            "wanxiang": {"base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis", "model": "wanx2.1-i2v-plus"},
            "happyhorse": {"base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis", "model": "happyhorse-1.0-r2v"},
            "vidu": {"base_url": "https://api.vidu.studio/open/v1/creation/video", "model": "vidu2.0"},
        }

        try:
            with SessionLocal() as session:
                resolved_category = str(category or "").strip()
                if not resolved_category:
                    logger.warning("Missing category when resolving media API config | user_id=%s", user_id)
                    return {}

                self._repair_invalid_user_config_rows(session, user_id, category=category)
                self._repair_invalid_system_config_rows(session, category=category, provider=provider)

                use_function_based_routing = False
                global_explicit_selection = False
                global_strict_provider = False
                try:
                    from app.models.all_models import APIRoutingConfig
                    routing_conf = session.query(APIRoutingConfig).first()
                    if routing_conf:
                        use_function_based_routing = routing_conf.use_function_based_routing
                        global_explicit_selection = routing_conf.explicit_selection
                        global_strict_provider = routing_conf.strict_provider
                except Exception as e:
                    _debug_log(f"Failed to read APIRoutingConfig, defaulting to legacy routing: {e}")

                _debug_log(f"API_ROUTING_MODE mode={'new_function_based' if use_function_based_routing else 'old_legacy'} user_id={user_id} category={resolved_category} provider={provider or '<none>'} model={requested_model or '<none>'}")  



                _debug_log(f"API_ROUTING_MODE mode={'new_function_based' if use_function_based_routing else 'old_legacy'} user_id={user_id} category={resolved_category} provider={provider or '<none>'} model={requested_model or '<none>'}")

                user_setting = self._get_active_user_setting(session, user_id, resolved_category)
                requested_provider = self._normalize_provider_name(str(provider or "").strip(), resolved_category)
                requested_model_value = str(requested_model or "").strip()      
                from app.api.settings import get_task_default_system_setting    
                task_default_row = get_task_default_system_setting(session, resolved_category)

                selected_user_strategy = self._normalize_api_strategy(
                    getattr(user_setting, "api_strategy", None),
                    default=self.USER_API_STRATEGY_SMART_DEFAULT,
                )
                user_setting_id = getattr(user_setting, "id", None) if user_setting else None
                user_system_api_id = int(getattr(user_setting, "system_api_id", 0) or 0) if user_setting else 0
                user_binding_status = "no_user_setting" if not user_setting else ("no_system_api_id" if user_system_api_id <= 0 else "pending")

                func_explicit_args = {}
                function_routing_applied = False

                if use_function_based_routing and function_name:
                    try:
                        from app.models.all_models import FunctionAPIConfig
                        func_conf = session.query(FunctionAPIConfig).filter(FunctionAPIConfig.function_name == function_name).first()
                        if func_conf and func_conf.api_settings:
                            settings = func_conf.api_settings
                            
                            # Fallback is handled elsewhere or via resolve_function_apis, 
                            # but here we identify the TOP priority or explicit selection
                            # if no specific system_api_id was supplied.
                            target_setting = None
                            if system_api_id:
                                for s in settings:
                                    if s.get("system_api_id") and int(s.get("system_api_id")) == int(system_api_id): 
                                        target_setting = s
                                        break
                                if not target_setting:
                                    # Fallback if not found in list but directly provided
                                    target_setting = {"system_api_id": system_api_id}
                            else:
                                # Pick highest priority
                                sorted_settings = sorted(settings, key=lambda x: x.get('priority', 0), reverse=True)
                                target_setting = sorted_settings[0] if sorted_settings else None

                            if target_setting and target_setting.get("system_api_id"):
                                user_system_api_id = int(target_setting.get("system_api_id"))
                                selected_user_strategy = "unified_function_api"
                                user_setting_id = "func_based_" + getattr(category, "name", str(category))
                                user_binding_status = "function_api_direct_route"
                                function_routing_applied = True
                                
                                func_explicit_args["explicit_selection"] = target_setting.get("explicit_selection", False) or global_explicit_selection
                                func_explicit_args["strict_provider"] = target_setting.get("strict_provider", False) or global_strict_provider

                                # We need to spoof a dummy user_setting so the logic below triggers
                                class DummyUserSetting:
                                    system_api_id = user_system_api_id
                                    api_strategy = "unified_function_api"
                                    id = user_setting_id
                                user_setting = DummyUserSetting()
                                _debug_log(f"API selected via function_name={function_name} with system_api_id={user_system_api_id}")
                    except Exception as e:
                        _debug_log(f"Error querying FunctionAPIConfig for function_name={function_name}: {e}", "warning")

                if not function_routing_applied and system_api_id:
                    # STRICT BYPASS: If system_api_id is provided directly but without function_name matching, completely ignore user presets.
                    # We just spoof the user_system_api_id directly. This forces the downstream logic
                    # to use exactly the requested API configuration.
                    user_system_api_id = int(system_api_id)
                    selected_user_strategy = "explicit_request_overwrite"
                    user_setting_id = "explicit_bypass"
                    user_binding_status = "system_api_id_provided"

                    # Dummy class properly handles `id` attribute safely mapped below.
                    class BypassUserSetting:
                        id = -1
                        api_strategy = "explicit_request_overwrite"
                        system_api_id = user_system_api_id
                    user_setting = BypassUserSetting()
                    _debug_log(f"API Bypass configured manually using system_api_id={user_system_api_id}")

                user_binding_detail = "<none>"
                fallback_debug_cache: Dict[str, Dict[str, Any]] = {}

                def _collect_fallback_pool_debug() -> Dict[str, Any]:
                    cached = fallback_debug_cache.get("pool")
                    if cached is not None:
                        return cached

                    rows = self._system_setting_query(session, category=resolved_category).order_by(SystemAPISetting.id.desc()).all()
                    available_rows = []
                    skipped = []
                    for row in rows:
                        row_id = getattr(row, "id", None)
                        row_provider = getattr(row, "provider", None) or "<none>"
                        row_model = getattr(row, "model", None) or "<none>"
                        row_deprecated = self._is_deprecated_system_config(row.config, getattr(row, "deprecated", None))
                        summary = f"{row_id}:{row_provider}/{row_model}"
                        if not row_deprecated:
                            available_rows.append(summary)
                            continue
                        skipped.append(f"{summary}[deprecated]")

                    cached = {
                        "category_total": len(rows),
                        "available_total": len(available_rows),
                        "available_sample": "|".join(available_rows[:5]) or "<none>",
                        "skipped_sample": "|".join(skipped[:5]) or "<none>",
                    }
                    fallback_debug_cache["pool"] = cached
                    return cached

                def _trace_default_vs_selected(stage: str, selected_row: Optional[SystemAPISetting], selected_source: str, note: str = "") -> None:
                    mapped_id = getattr(task_default_row, "id", None)
                    mapped_provider = getattr(task_default_row, "provider", None)
                    mapped_model = getattr(task_default_row, "model", None)
                    mapped_deprecated = None
                    if task_default_row:
                        mapped_deprecated = self._is_deprecated_system_config(
                            getattr(task_default_row, "config", None),
                            getattr(task_default_row, "deprecated", None),
                        )

                    selected_id = getattr(selected_row, "id", None) if selected_row else None
                    selected_provider = getattr(selected_row, "provider", None) if selected_row else None
                    selected_model = getattr(selected_row, "model", None) if selected_row else None
                    mismatch = bool(task_default_row and selected_row and int(selected_id or 0) != int(mapped_id or 0))
                    extra_parts = [
                        f"user_setting_id={user_setting_id}",
                        f"user_system_api_id={user_system_api_id or '<none>'}",
                        f"user_strategy={selected_user_strategy}",
                        f"user_binding_status={user_binding_status}",
                        f"user_binding_detail={user_binding_detail}",
                    ]
                    if stage in {"task_default", "category_fallback"}:
                        pool_debug = _collect_fallback_pool_debug()
                        extra_parts.extend([
                            f"category_total={pool_debug['category_total']}",
                            f"available_total={pool_debug['available_total']}",
                            f"available_sample={pool_debug['available_sample']}",
                            f"skipped_sample={pool_debug['skipped_sample']}",
                        ])

                    details_payload = {
                        "category": resolved_category,
                        "function": function_name,
                        "requested_provider": requested_provider,
                        "requested_model": requested_model_value,
                        "selected_id": selected_id,
                        "selected_provider": selected_provider,
                        "selected_model": selected_model,
                        "source": selected_source,
                        "stage": stage,
                        "note": note,
                        "user_system_api_id": user_system_api_id,
                        "mismatch_default": mismatch,
                    }
                    try:
                        session.commit()
                    except Exception:
                        pass
                    try:
                        from app.services.system_log_service import log_action
                        log_action(session, int(user_id), f"user_{user_id}", "API_SELECTION_TRACE", details=", ".join(f"{k}={v}" for k, v in details_payload.items()), ip_address="127.0.0.1")
                    except Exception as e_log:
                        pass

                    _debug_log(
                        "API_FALLBACK_TRACE "
                        f"stage={stage} user_id={user_id} category={resolved_category} requested_provider={requested_provider or '<none>'} "
                        f"requested_model={requested_model_value or '<none>'} strict_provider={strict_provider} "
                        f"mapped_id={mapped_id} mapped_provider={mapped_provider or '<none>'} mapped_model={mapped_model or '<none>'} "
                        f"mapped_deprecated={mapped_deprecated} "
                        f"selected_id={selected_id} selected_provider={selected_provider or '<none>'} selected_model={selected_model or '<none>'} "
                        f"selected_source={selected_source or '<none>'} mismatch={mismatch} note={note or '<none>'} "
                        + " ".join(extra_parts),
                        "warning" if mismatch else "info",
                    )

                def _build_runtime_from_system_row(system_row: SystemAPISetting, resolved_source: str, selected_strategy: str) -> Dict[str, Any]:
                    resolved_provider = self._normalize_provider_name(system_row.provider, resolved_category) or requested_provider
                    provider_key_pool_bundle = self._collect_provider_key_pool_bundle(
                        session,
                        resolved_category,
                        resolved_provider,
                    )
                    runtime_config = self._promote_runtime_endpoint(
                        resolved_category,
                        resolved_provider,
                        system_row.config,
                        system_row=system_row,
                    )
                    merged_runtime_config = {
                        **runtime_config,
                        "provider": resolved_provider,
                    }
                    pooled_keys = self._normalize_api_keys(provider_key_pool_bundle.get("provider_api_keys"))
                    if pooled_keys:
                        merged_runtime_config["provider_api_keys"] = pooled_keys
                        strategy = str(provider_key_pool_bundle.get("provider_api_key_strategy") or "random").strip().lower()
                        if strategy in {"random", "round_robin", "weighted"}:
                            merged_runtime_config["provider_api_key_strategy"] = strategy
                        if strategy == "weighted":
                            merged_runtime_config["provider_api_key_weights"] = provider_key_pool_bundle.get("provider_api_key_weights") or []

                    if user_setting is not None:
                        user_mode = str(getattr(user_setting, "mode", "") or "").strip().lower()
                        if user_mode:
                            merged_runtime_config.setdefault("mode", user_mode)
                            merged_runtime_config["__user_selected_mode"] = user_mode

                    runtime_model = str(
                        merged_runtime_config.get("runtime_model")
                        or merged_runtime_config.get("upstream_model")
                        or merged_runtime_config.get("model_override")
                        or system_row.model
                        or defaults.get(resolved_provider, {}).get("model")
                        or ""
                    ).strip()

                    return {
                        "provider": system_row.provider,
                        "api_key": self._pick_runtime_api_key(merged_runtime_config, system_row.api_key),
                        "base_url": system_row.base_url or defaults.get(resolved_provider, {}).get("base_url"),
                        "model": runtime_model,
                        "base_model": getattr(system_row, "base_model", None),
                        "modality": getattr(system_row, "modality", None),
                        "supplier_info": getattr(system_row, "supplier_info", None),
                        "config": {
                            **runtime_config,
                            "__selection_source": "system_only",
                            "__resolved_source": resolved_source,
                            "__resolved_setting_id": system_row.id,
                            "__api_strategy": selected_strategy,
                            **func_explicit_args,
                        },
                    }

                # Strict mode: explicit provider/model request must resolve from system_api_settings directly.
                if strict_provider:
                    if not requested_provider:
                        logger.warning(
                            "Explicit provider missing in media service | user_id=%s category=%s provider=%s",
                            user_id,
                            resolved_category,
                            provider,
                        )
                        return {}

                    strict_query = self._system_setting_query(
                        session,
                        provider=requested_provider,
                        category=resolved_category,
                    )
                    if requested_model_value:
                        strict_query = strict_query.filter(SystemAPISetting.model == requested_model_value)
                    strict_rows = strict_query.order_by(SystemAPISetting.id.desc()).all()
                    strict_match = None
                    for row in strict_rows:
                        if self._is_deprecated_system_config(row.config, getattr(row, "deprecated", None)):
                            continue
                        strict_match = row
                        break

                    if not strict_match:
                        logger.warning(
                            "Explicit provider/model has no available system setting in media service | user_id=%s category=%s provider=%s model=%s",
                            user_id,
                            resolved_category,
                            requested_provider,
                            requested_model_value,
                        )
                        return {}

                    resolved_source = f"system_by_explicit_request:{requested_provider}/{requested_model_value or strict_match.model}"
                    _trace_default_vs_selected("explicit_provider", strict_match, resolved_source, "explicit_provider_selected")
                    return _build_runtime_from_system_row(strict_match, resolved_source, self.USER_API_STRATEGY_FIXED)

                # Non-strict mode: use the per-user category binding first.
                if user_setting:
                    selected_system_setting_id = int(getattr(user_setting, "system_api_id", 0) or 0)
                    logger.debug(f"[DEBUG] get_api_config | user_id={user_id} category={resolved_category} function_name={function_name} got user_setting with system_api_id={selected_system_setting_id} from {getattr(user_setting, 'id', None)}")
                    if selected_system_setting_id > 0:
                        selected_binding_deprecated = False
                        selected_by_id = self._system_setting_query(session, category=resolved_category).filter(
                            SystemAPISetting.id == selected_system_setting_id,
                        ).first()
                        if selected_by_id:
                            if self._is_deprecated_system_config(selected_by_id.config, getattr(selected_by_id, "deprecated", None)):
                                logger.warning(
                                    "Blocked deprecated system api setting in media service and continue fallback | user_id=%s category=%s system_api_id=%s",
                                    user_id,
                                    resolved_category,
                                    selected_system_setting_id,
                                )
                                selected_binding_deprecated = True
                                user_binding_status = "deprecated"
                                user_binding_detail = f"{getattr(selected_by_id, 'provider', None) or '<none>'}/{getattr(selected_by_id, 'model', None) or '<none>'}"
                            if not selected_binding_deprecated:
                                resolved_source = f"system_by_user_setting_id:{selected_system_setting_id}"
                                user_binding_status = "resolved"
                                user_binding_detail = f"{getattr(selected_by_id, 'provider', None) or '<none>'}/{getattr(selected_by_id, 'model', None) or '<none>'}"
                                _trace_default_vs_selected("direct_system_api_id", selected_by_id, resolved_source, "explicit_user_category_binding")
                                logger.debug(f"[DEBUG] _build_runtime_from_system_row hit! selected_by_id={selected_by_id}")
                                return _build_runtime_from_system_row(
                                    selected_by_id,
                                    resolved_source,
                                    selected_user_strategy,
                                )
                        if not selected_binding_deprecated:
                            selected_any_category = self._system_setting_query(session).filter(
                                SystemAPISetting.id == selected_system_setting_id,
                            ).first()
                            if selected_any_category:
                                user_binding_status = "cross_category"
                                user_binding_detail = (
                                    f"actual_category={getattr(selected_any_category, 'category', None) or '<none>'};"
                                    f"provider={getattr(selected_any_category, 'provider', None) or '<none>'};"
                                    f"model={getattr(selected_any_category, 'model', None) or '<none>'}"
                                )
                                logger.warning(
                                    "Cross-category user system_api_id binding in media service | user_id=%s category=%s user_setting_id=%s system_api_id=%s actual_category=%s provider=%s model=%s",
                                    user_id,
                                    resolved_category,
                                    getattr(user_setting, "id", None),
                                    selected_system_setting_id,
                                    getattr(selected_any_category, "category", None),
                                    getattr(selected_any_category, "provider", None),
                                    getattr(selected_any_category, "model", None),
                                )
                            else:
                                user_binding_status = "missing_system_api_id"
                                user_binding_detail = f"system_api_id={selected_system_setting_id}"
                                logger.warning(
                                    "Missing user system_api_id binding in media service | user_id=%s category=%s user_setting_id=%s system_api_id=%s",
                                    user_id,
                                    resolved_category,
                                    getattr(user_setting, "id", None),
                                    selected_system_setting_id,
                                )

                # Fallback 1: category task default system setting.
                default_row = task_default_row
                if default_row and not self._is_deprecated_system_config(default_row.config, getattr(default_row, "deprecated", None)):
                    resolved_source = f"task_default_system_setting:{default_row.provider}/{default_row.model}"
                    _trace_default_vs_selected("task_default", default_row, resolved_source, "select_task_default")
                    return _build_runtime_from_system_row(
                        default_row,
                        resolved_source,
                        selected_user_strategy,
                    )

                # Fallback 2: any non-deprecated system setting in category.
                fallback_any = self._pick_system_setting_fallback(session, resolved_category, None)
                if fallback_any:
                    resolved_source = f"system_category_fallback:{fallback_any.provider}/{fallback_any.model}"
                    _trace_default_vs_selected("category_fallback", fallback_any, resolved_source, "task_default_unavailable")
                    return _build_runtime_from_system_row(
                        fallback_any,
                        resolved_source,
                        selected_user_strategy,
                    )

                logger.warning(
                    "No available system api setting in media service | user_id=%s category=%s",
                    user_id,
                    resolved_category,
                )
        except Exception as e:
            _debug_log(f"Error fetching settings for {provider}: {e}", "error")

        return {}

    async def generate_image(self, prompt: str, negative_prompt: Optional[str] = None, llm_config: Optional[Dict[str, Any]] = None, reference_image_url: Optional[Union[str, List[str]]] = None, width: int = None, height: int = None, image_size: Optional[str] = None, aspect_ratio: str = None, provider_options: Optional[Dict[str, Any]] = None, user_id: int = 1, user_credits: int = 0, filename_base: Optional[str] = None, asset_type: Optional[str] = None, skip_download: bool = False):
        explicit_provider_selected = bool((llm_config or {}).get("__user_explicit_provider"))
        explicit_selection = bool((llm_config or {}).get("__user_explicit_selection"))
        provider = self._normalize_provider_name((llm_config or {}).get("provider"), "Image")
        pre_resolved_api_config = (llm_config or {}).get("__pre_resolved_api_config")
        if isinstance(pre_resolved_api_config, dict) and pre_resolved_api_config:
            api_config = dict(pre_resolved_api_config)
            logger.info(
                "Generate image provider resolution reused pre-resolved config | user_id=%s requested_provider=%s requested_model=%s resolved_provider=%s resolved_model=%s resolved_source=%s",
                user_id,
                self._normalize_provider_name((llm_config or {}).get("provider"), "Image") if llm_config else None,
                (llm_config or {}).get("model"),
                self._normalize_provider_name((api_config or {}).get("provider"), "Image") if api_config else None,
                (api_config or {}).get("model"),
                ((api_config or {}).get("config") or {}).get("__resolved_source"),
            )
        else:
            api_config = self.get_api_config(
                provider,
                user_id,
                category="Image",
                requested_model=(llm_config or {}).get("model"),
                user_credits=user_credits,
                strict_provider=explicit_provider_selected,
            )

        if api_config and api_config.get("__blocked"):
            return {
                "error": self._vendor_failed_message(self._normalize_provider_name((api_config or {}).get("provider"), "Image") or provider, api_config.get("__blocked_reason") or "该系统配置已弃用"),
                "submit_failed": True,
            }

        # Apply persisted overrides from the resolved model config
        if api_config and isinstance(api_config.get("config"), dict):
            if api_config["config"].get("explicit_selection"):
                explicit_selection = True
            if api_config["config"].get("strict_provider"):
                explicit_provider_selected = True

        resolved_provider = self._normalize_provider_name((api_config or {}).get("provider"), "Image") if api_config else None
        if resolved_provider:
            provider = resolved_provider

        if api_config is not None and isinstance(provider_options, dict) and provider_options:
            merged_config = dict((api_config.get("config") or {}))
            merged_config.update(provider_options)
            api_config["config"] = merged_config
            api_config["__request_provider_options"] = dict(provider_options)

        logger.info(
            "Generate image provider resolution | user_id=%s strict_provider=%s requested_provider=%s requested_model=%s resolved_provider=%s resolved_model=%s resolved_source=%s",
            user_id,
            explicit_provider_selected,
            self._normalize_provider_name((llm_config or {}).get("provider"), "Image") if llm_config else None,
            (llm_config or {}).get("model"),
            provider,
            (api_config or {}).get("model"),
            ((api_config or {}).get("config") or {}).get("__resolved_source"),
        )

        selected_strategy = self.USER_API_STRATEGY_FIXED
        try:
            selected_strategy = self._normalize_api_strategy(
                ((api_config or {}).get("config") or {}).get("__api_strategy"),
                default=self.USER_API_STRATEGY_FIXED,
            )
        except Exception:
            selected_strategy = self.USER_API_STRATEGY_FIXED

        _debug_log(f"[MediaService] Generating Image. Provider: {provider}, Refs Type: {type(reference_image_url)}, Refs: {_strip_base64_from_log(reference_image_url)}, W: {width}, H: {height}, image_size: {image_size}, AR: {aspect_ratio}")

        result = await self._generate_with_smart_routing(
            category="Image",
            prompt=prompt,
            negative_prompt=negative_prompt,
            provider=provider,
            api_config=api_config,
            user_id=user_id,
            reference_image_url=reference_image_url,
            width=width,
            height=height,
            image_size=image_size,
            aspect_ratio=aspect_ratio,
            requested_model=(llm_config or {}).get("model"),
            explicit_selection=explicit_selection,
            allow_priority_fallback_when_explicit=str(asset_type or "").strip().lower() in {"subject", "entity", "character", "prop", "environment"},
            fallback_candidate_limit=0,
            modality="image-to-image" if reference_image_url else "text-to-image",
            api_strategy=selected_strategy,
            primary_retry_limit=1,
        )

        storage_metadata = self._build_generated_storage_metadata(
            asset_type=asset_type,
            provider_options=provider_options,
        )
        if storage_metadata.get("asset_type") == "subject":
            logger.info(
                "[GenerateImageSubject] request_context user_id=%s asset_type=%s entity_id=%s entity_name=%s subject_name=%s subject_type=%s",
                user_id,
                storage_metadata.get("asset_type"),
                storage_metadata.get("entity_id"),
                storage_metadata.get("entity_name"),
                storage_metadata.get("subject_name"),
                storage_metadata.get("subject_type"),
            )

        # Download
        if not skip_download and result and "url" in result and result["url"]:
            result_url = str(result.get("url") or "").strip()
            result_meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            result_provider = str(
                result.get("provider")
                or result_meta.get("provider")
                or provider
                or ""
            ).strip().lower()
            # Grsai image APIs may already write directly to provider OSS (with authorized access).
            # Keep upstream URL as-is to avoid unnecessary re-download/localization.
            skip_provider_direct_oss_download = bool(
                result_provider == "grsai"
                and str(asset_type or "").strip().lower() != "video"
                and result_url.lower().startswith(("http://", "https://"))
            )
            if not skip_provider_direct_oss_download:
                result["url"] = await asyncio.to_thread(
                    self._download_and_save,
                    result["url"],
                    filename_base,
                    user_id,
                    storage_metadata,
                )
            else:
                logger.info(
                    "[GenerateImage] skip localization for provider-direct oss url | provider=%s user_id=%s url=%s",
                    result_provider,
                    user_id,
                    _strip_query_from_log_url(result_url),
                )
                if isinstance(result.get("metadata"), dict):
                    result["metadata"]["provider_direct_oss_url"] = True
                else:
                    result["metadata"] = {"provider_direct_oss_url": True, "provider": result_provider}
        if result and result.get("error"):
            error_provider = result.get("_attempt_provider") if isinstance(result, dict) else None
            result["error"] = self._vendor_failed_message(error_provider or provider, result.get("error"))
        return result

    async def generate_video(self, prompt: str, negative_prompt: Optional[str] = None, llm_config: Optional[Dict[str, Any]] = None, reference_image_url: Optional[Union[str, List[str]]] = None, reference_video_urls: Optional[List[str]] = None, last_frame_url: Optional[str] = None, duration: int = 5, aspect_ratio: Optional[str] = None, keyframes: Optional[List[str]] = None, provider_options: Optional[Dict[str, Any]] = None, user_id: int = 1, user_credits: int = 0, filename_base: Optional[str] = None, skip_download: bool = False):
        explicit_provider_selected = bool((llm_config or {}).get("__user_explicit_provider"))
        provider = self._normalize_provider_name((llm_config or {}).get("provider"), "Video")
        pre_resolved_api_config = (llm_config or {}).get("__pre_resolved_api_config")
        if isinstance(pre_resolved_api_config, dict) and pre_resolved_api_config:
            api_config = dict(pre_resolved_api_config)
        else:
            api_config = self.get_api_config(
                provider,
                user_id,
                category="Video",
                requested_model=(llm_config or {}).get("model"),
                user_credits=user_credits,
                strict_provider=explicit_provider_selected,
            )

        _debug_log(
            "[MediaService][VideoConfig] requested_provider=%s requested_model=%s strict_provider=%s resolved_provider=%s resolved_model=%s resolved_source=%s has_api_config=%s"
            % (
                self._normalize_provider_name((llm_config or {}).get("provider"), "Video") if llm_config else None,
                (llm_config or {}).get("model"),
                explicit_provider_selected,
                self._normalize_provider_name((api_config or {}).get("provider"), "Video") if api_config else None,
                (api_config or {}).get("model") if api_config else None,
                (((api_config or {}).get("config") or {}).get("__resolved_source") if api_config else None),
                bool(api_config),
            )
        )
        if api_config:
            resolved_source_dbg = str((((api_config or {}).get("config") or {}).get("__resolved_source") or "")).strip()
            if "task_default_system_setting" in resolved_source_dbg:
                _debug_log(
                    "[MediaService][VideoConfig] using task-default system setting | source=%s provider=%s model=%s"
                    % (
                        resolved_source_dbg,
                        (api_config or {}).get("provider"),
                        (api_config or {}).get("model"),
                    )
                )

        explicit_selection_for_video = bool((llm_config or {}).get("__user_explicit_selection"))
        if explicit_selection_for_video and not api_config:
            _debug_log(
                "[MediaService][VideoConfig] explicit provider/model requested but no active non-deprecated system setting matched; blocking request",
                "warning",
            )
            return {
                "error": "显式指定的视频 provider/model 未命中可用的系统配置（可能已弃用或不存在）",
                "submit_failed": True,
            }

        if api_config and api_config.get("__blocked"):
            return {
                "error": self._vendor_failed_message(self._normalize_provider_name((api_config or {}).get("provider"), "Video") or provider, api_config.get("__blocked_reason") or "该系统配置已弃用"),
                "submit_failed": True,
            }

        resolved_provider = self._normalize_provider_name((api_config or {}).get("provider"), "Video") if api_config else None
        if resolved_provider:
            provider = resolved_provider

        normalized_reference_video_urls: List[str] = []
        if isinstance(reference_video_urls, list):
            normalized_reference_video_urls = [str(item).strip() for item in reference_video_urls if str(item).strip()]

        if normalized_reference_video_urls:
            merged_provider_options = dict(provider_options or {})
            merged_provider_options.setdefault("reference_video_urls", normalized_reference_video_urls)
            provider_options = merged_provider_options

        if api_config is not None and isinstance(provider_options, dict) and provider_options:
            merged_config = dict((api_config.get("config") or {}))
            merged_config.update(provider_options)
            api_config["config"] = merged_config
            api_config["__request_provider_options"] = dict(provider_options)

        _debug_log(
            "[MediaService][VoiceConfig] requested_provider=%s requested_model=%s resolved_provider=%s resolved_model=%s resolved_source=%s voice=%s language_code=%s"
            % (
                self._normalize_provider_name((llm_config or {}).get("provider"), "Voice") if llm_config else None,
                (llm_config or {}).get("model"),
                self._normalize_provider_name((api_config or {}).get("provider"), "Voice") if api_config else None,
                (api_config or {}).get("model") if api_config else None,
                (((api_config or {}).get("config") or {}).get("__resolved_source") if api_config else None),
                (((api_config or {}).get("config") or {}).get("voice") if api_config else None),
                (((api_config or {}).get("config") or {}).get("language_code") if api_config else None),
            )
        )

        resolved_source = str((((api_config or {}).get("config") or {}).get("__resolved_source") or "")).strip().lower()
        provider_locked_by_active_setting = bool(resolved_provider) and ("system_by_user_provider_model:" in resolved_source)

        logger.info(
            "Generate video provider resolution | user_id=%s strict_provider=%s requested_provider=%s requested_model=%s resolved_provider=%s resolved_model=%s resolved_source=%s",
            user_id,
            explicit_provider_selected,
            self._normalize_provider_name((llm_config or {}).get("provider"), "Video") if llm_config else None,
            (llm_config or {}).get("model"),
            provider,
            (api_config or {}).get("model"),
            ((api_config or {}).get("config") or {}).get("__resolved_source"),
        )

        selected_strategy = self.USER_API_STRATEGY_FIXED
        try:
            selected_strategy = self._normalize_api_strategy(
                ((api_config or {}).get("config") or {}).get("__api_strategy"),
                default=self.USER_API_STRATEGY_FIXED,
            )
        except Exception:
            selected_strategy = self.USER_API_STRATEGY_FIXED

        if provider_locked_by_active_setting and not explicit_selection_for_video:
            logger.info(
                "Generate video provider lock enabled | user_id=%s provider=%s reason=active_setting_no_explicit_override fallback=enabled_on_failure",
                user_id,
                provider,
            )

        _debug_log(f"[MediaService] Generating Video. Provider: {provider}, Model: {(api_config or {}).get('model') or (llm_config or {}).get('model')}, Refs: {_strip_base64_from_log(reference_image_url)}, RefVideos: {len(normalized_reference_video_urls)}, LastFrame: {_strip_base64_from_log(last_frame_url)}, Ratio: {aspect_ratio}, Keyframes: {len(keyframes) if keyframes else 0}")

        result = await self._generate_with_smart_routing(
            category="Video",
            prompt=prompt,
            negative_prompt=negative_prompt,
            provider=provider,
            api_config=api_config,
            user_id=user_id,
            reference_image_url=reference_image_url,
            aspect_ratio=aspect_ratio,
            last_frame_url=last_frame_url,
            duration=duration,
            keyframes=keyframes,
            provider_options=provider_options,
            requested_model=(llm_config or {}).get("model"),
            explicit_selection=explicit_selection_for_video,
            modality="image-to-video" if reference_image_url else "text-to-video",
            api_strategy=selected_strategy,
            primary_retry_limit=0,
            fallback_candidate_limit=0,
        )

        # Download 
        if not skip_download and result and "url" in result and result["url"]:
            result["url"] = await asyncio.to_thread(
                self._download_and_save,
                result["url"],
                filename_base,
                user_id,
            )
        if result and result.get("error"):
            error_provider = result.get("_attempt_provider") if isinstance(result, dict) else None
            result["error"] = self._vendor_failed_message(error_provider or provider, result.get("error"))
        
        return result

    async def generate_voice(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        duration: int = 5,
        provider_options: Optional[Dict[str, Any]] = None,
        user_id: int = 1,
        user_credits: int = 0,
        skip_download: bool = False,
    ):
        explicit_provider_selected = bool((llm_config or {}).get("__user_explicit_provider"))
        explicit_selection = bool((llm_config or {}).get("__user_explicit_selection"))
        provider = None
        if llm_config and llm_config.get("provider"):
            provider = self._normalize_provider_name(llm_config["provider"], "Voice")

        if not provider:
            try:
                with SessionLocal() as session:
                    self._repair_invalid_user_config_rows(session, user_id, category="Voice")
                    active_setting = self._get_active_user_setting(session, user_id, "Voice")
                    if active_setting and active_setting.provider:
                        provider = self._normalize_provider_name(active_setting.provider, "Voice")
            except Exception as e:
                _debug_log(f"Error finding active voice provider: {e}", "error")

        if not provider:
            provider = "kie"

        pre_resolved_api_config = (llm_config or {}).get("__pre_resolved_api_config")
        if isinstance(pre_resolved_api_config, dict) and pre_resolved_api_config:
            api_config = dict(pre_resolved_api_config)
        else:
            api_config = self.get_api_config(
                provider,
                user_id,
                category="Voice",
                requested_model=(llm_config or {}).get("model"),
                user_credits=user_credits,
                strict_provider=explicit_provider_selected,
            )

        if not api_config:
            api_config = {
                "provider": "kie",
                "model": str((llm_config or {}).get("model") or "elevenlabs/text-to-speech-turbo-2-5").strip(),
                "api_key": settings.KIE_API_KEY,
                "base_url": "https://api.kie.ai",
                "config": {},
            }

        resolved_provider = self._normalize_provider_name((api_config or {}).get("provider"), "Voice") if api_config else None
        if resolved_provider:
            provider = resolved_provider

        if api_config is not None and isinstance(provider_options, dict) and provider_options:
            merged_config = dict((api_config.get("config") or {}))
            merged_config.update(provider_options)
            api_config["config"] = merged_config
            api_config["__request_provider_options"] = dict(provider_options)

        selected_strategy = self.USER_API_STRATEGY_FIXED
        try:
            selected_strategy = self._normalize_api_strategy(
                ((api_config or {}).get("config") or {}).get("__api_strategy"),
                default=self.USER_API_STRATEGY_FIXED,
            )
        except Exception:
            selected_strategy = self.USER_API_STRATEGY_FIXED

        result = await self._generate_with_smart_routing(
            category="Voice",
            prompt=prompt,
            negative_prompt=negative_prompt,
            provider=provider,
            api_config=api_config,
            user_id=user_id,
            reference_image_url=None,
            duration=duration,
            requested_model=(llm_config or {}).get("model"),
            explicit_selection=explicit_selection,
            allow_priority_fallback_when_explicit=True,
            fallback_candidate_limit=3,
            modality="text-to-audio",
            api_strategy=selected_strategy,
            primary_retry_limit=3,
        )

        if not skip_download and result and "url" in result and result["url"]:
            result["url"] = await asyncio.to_thread(
                self._download_and_save,
                result["url"],
                None,
                user_id,
            )
        if result and result.get("error"):
            error_provider = result.get("_attempt_provider") if isinstance(result, dict) else None
            result["error"] = self._vendor_failed_message(error_provider or provider, result.get("error"))

        return result
    
    # --- Provider Implementations ---
    
    async def _handle_doubao_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        api_key = config.get("api_key")
        if not api_key: return {"error": "No API Key"}
        model = config.get("model")
        tool_conf = config.get("config", {}) or {}
        # Defensive init for branches that may inspect image_size later.
        image_size = self._normalize_image_size_value(
            image_size or tool_conf.get("image_size") or tool_conf.get("imageSize")
        )
        
        # Base metadata
        base_metadata = {"provider": "doubao", "model": model, "prompt": prompt}
        
        # Image Generation
        if gen_type == "image":
            # Multi-Reference handling (if ref_image provided)
            if ref_image:
                _debug_log(f"DEBUG: Doubao Multi-Reference Gen refs: {_strip_base64_from_log(ref_image)}")
                raw_endpoint = tool_conf.get("endpoint") or "https://ark.cn-beijing.volces.com/api/v3"
                endpoint = raw_endpoint.strip()
                
                ref_list = ref_image if isinstance(ref_image, list) else [ref_image]
                ref_list = [r for r in ref_list if r]
                
                resolved_refs = self._resolve_ref_list_for_api(ref_list, force_data_uri_for_local=True, prefer_public_upload_url=True)
                    
                if resolved_refs:
                    model_name = model or "doubao-seedream-4-5-251128"
                    payload = {
                        "model": model_name, "prompt": prompt, "response_format": "url",
                        # USER FEEDBACK: Field name must be "image", not "image_urls" for Doubao image-to-image
                        "image": resolved_refs,
                        "sequential_image_generation": "disabled",
                        "watermark": False
                    }
                    if tool_conf.get("width") and tool_conf.get("height"):
                        normalized_size = self._normalize_doubao_size(
                            tool_conf.get("width"),
                            tool_conf.get("height"),
                        )
                        if normalized_size:
                            payload["size"] = normalized_size

                    url = f"{endpoint.rstrip('/')}/images/generations"
                    return await self._common_requests_post(
                        url,
                        payload,
                        api_key,
                        "doubao_image_multiref",
                        extra_metadata=base_metadata,
                        provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
                    )
            
            # Text to Image
            raw_endpoint = tool_conf.get("endpoint") or "https://ark.cn-beijing.volces.com/api/v3"
            endpoint = raw_endpoint.strip()
            url = f"{endpoint.rstrip('/')}/images/generations"
            payload = {
                "model": model or "doubao-seedream-4-5-251128", 
                "prompt": prompt, 
                "response_format": "url",
                "watermark": False
            }
            
            return await self._common_requests_post(
                url,
                payload,
                api_key,
                "doubao_image",
                extra_metadata=base_metadata,
                provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
            )

        # Video Generation
        elif gen_type == "video":
            raw_endpoint = tool_conf.get("endpoint") or "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
            endpoint = self._normalize_doubao_video_tasks_endpoint(raw_endpoint)
            raw_callback_url = str(
                tool_conf.get("_provider_callback_url")
                or tool_conf.get("callback_url")
                or tool_conf.get("callbackUrl")
                or tool_conf.get("callBackUrl")
                or tool_conf.get("webHook")
                or ""
            ).strip()
            callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"doubao-{gen_type}"
            callback_tool_conf = dict(tool_conf or {})
            if raw_callback_url:
                callback_tool_conf.setdefault("callback_url", raw_callback_url)
            callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
            callback_enabled = bool(callback_url and callback_url != "-1")
            pure_callback_mode = bool(
                str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"}
            )
            if callback_url and callback_url != raw_callback_url:
                logger.info(
                    "Doubao callback auto-assigned | gen_type=%s ticket=%s callback_url=%s raw_callback=%s",
                    gen_type,
                    callback_ticket,
                    callback_url,
                    raw_callback_url or None,
                )
            
            # Auto-correct model if user passed an Image model for a Video task
            if model and "seedream" in model:
                 model = "doubao-seedance-1-5-pro-251215"
            
            if last_frame_url and "1-0-pro-fast" in (model or ""):
                model = "doubao-seedance-1-5-pro-251215"
            
            # If the user is specifically using Seedance 2.0 through the generic Doubao provider flow,
            # route it to the advanced ark_seedance handler to fully support audio/video/multi-image refs.
            if "seedance-2" in str(model or "").lower():
                target_config = dict(config)
                
                # Try to fetch the proper AK:SK:EP_TOKEN configured in ark-seedance provider settings
                from app.db.session import SessionLocal
                with SessionLocal() as session:
                    ark_bundle = self._collect_provider_key_pool_bundle(session, "Video", "ark-seedance")
                    pooled_keys = self._normalize_api_keys(ark_bundle.get("provider_api_keys"))
                    if pooled_keys:
                        target_config["api_key"] = self._pick_runtime_api_key(ark_bundle)
                        
                        # Merge the config properties to make sure we don't lose callback / project configurations
                        ark_inner_config = ark_bundle.get("provider_api_keys", [{}])[0].get("config", {}) if isinstance(ark_bundle.get("provider_api_keys"), list) and ark_bundle["provider_api_keys"] and isinstance(ark_bundle["provider_api_keys"][0], dict) else {}
                        if isinstance(ark_inner_config, dict):
                            target_config["config"] = {**tool_conf, **ark_inner_config}
                            
                return await self._handle_ark_seedance_generation(
                    gen_type, prompt, target_config, reference_image_url=ref_image, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio
                )

            content_payload = [{"type": "text", "text": prompt}]
            
            # Handle Refs (List vs Single)
            start_img_url = ref_image
            if isinstance(ref_image, list):
                # Pick the first one as Start Frame
                start_img_url = ref_image[0] if ref_image else None
            
            if start_img_url and last_frame_url:
                # Start + End Frame Mode (Explicit Roles Required)
                start_ref = await self._resolve_ref_for_api_async(start_img_url, force_data_uri_for_local=True)
                end_ref = await self._resolve_ref_for_api_async(last_frame_url, force_data_uri_for_local=True)

                max_ref_size = 30 * 1024 * 1024
                start_ref_size = self._data_uri_image_size_bytes(start_ref)
                end_ref_size = self._data_uri_image_size_bytes(end_ref)
                if (start_ref_size is not None and start_ref_size > max_ref_size) or (end_ref_size is not None and end_ref_size > max_ref_size):
                    return {"error": "Doubao reference image too large. Base64 image must be < 30MB."}

                if not start_ref or not end_ref:
                    return {"error": "Failed to resolve reference image(s) for Doubao video"}
                content_payload.append({
                    "type": "image_url", 
                    "image_url": {"url": start_ref},
                    "role": "first_frame"
                })
                content_payload.append({
                    "type": "image_url", 
                    "image_url": {"url": end_ref},
                    "role": "last_frame"
                })
            elif start_img_url:
                # Start Frame Only - Strict 'first_frame' role required for newer models (1.5 Pro)
                start_ref = await self._resolve_ref_for_api_async(start_img_url, force_data_uri_for_local=True)
                start_ref_size = self._data_uri_image_size_bytes(start_ref)
                if start_ref_size is not None and start_ref_size > 30 * 1024 * 1024:
                    return {"error": "Doubao reference image too large. Base64 image must be < 30MB."}
                if not start_ref:
                    return {"error": "Failed to resolve start reference image for Doubao video"}
                content_payload.append({
                    "type": "image_url", 
                    "image_url": {"url": start_ref},
                     "role": "first_frame"
                })
            elif last_frame_url:
                # Last Frame Only (Rare, but use role if strictly End frame)
                end_ref = await self._resolve_ref_for_api_async(last_frame_url, force_data_uri_for_local=True)
                end_ref_size = self._data_uri_image_size_bytes(end_ref)
                if end_ref_size is not None and end_ref_size > 30 * 1024 * 1024:
                    return {"error": "Doubao reference image too large. Base64 image must be < 30MB."}
                if not end_ref:
                    return {"error": "Failed to resolve last reference image for Doubao video"}
                content_payload.append({
                    "type": "image_url", 
                    "image_url": {"url": end_ref},
                    "role": "last_frame"
                })

            # Ensure duration is always a valid positive value for Doubao payloads.
            final_duration = duration
            model_lower = str(model or "").strip().lower()
            is_seedance_model = "seedance" in model_lower or "1-5-pro" in model_lower
            
            # Config override (User Settings)
            if tool_conf.get("duration"):
                final_duration = tool_conf.get("duration")

            allowed_duration_values = self._normalize_duration_enum_values(
                tool_conf.get("durations_seconds")
                or tool_conf.get("duration_values")
                or tool_conf.get("allowed_durations")
            )
            if not allowed_duration_values and is_seedance_model:
                # Seedance models commonly accept fixed buckets; avoid non-positive or auto sentinel.
                allowed_duration_values = [5, 10]

            try:
                d_int = int(final_duration)
            except Exception:
                d_int = None

            if d_int is None or d_int <= 0:
                d_int = int(allowed_duration_values[0]) if allowed_duration_values else 5

            if allowed_duration_values:
                mapped_duration = self._map_duration_nearest(
                    d_int,
                    allowed_duration_values,
                    prefer_higher_on_tie=is_seedance_model,
                )
                if mapped_duration is not None:
                    d_int = int(mapped_duration)

            final_duration = int(max(1, d_int))

            if is_seedance_model:
                _debug_log(
                    f"[DoubaoVideo] duration_in={duration}, duration_cfg={tool_conf.get('duration')}, allowed={allowed_duration_values}, duration_final={final_duration}"
                )

            # Map aspect ratio for Doubao (Ark): keep adaptive when provided.
            final_ratio = self._normalize_aspect_ratio_value(aspect_ratio) or "16:9"

            payload = {
                "model": model or "doubao-seedance-1-5-pro-251215",
                "content": content_payload,
                "duration": final_duration,
                "logo_info": {"add_logo": False},
                "watermark": False
            }
            if is_seedance_model:
                payload["return_last_frame"] = True
                is_draft_mode = self._normalize_bool_value(tool_conf.get("draft_mode") or tool_conf.get("draft"))
                requested_res = str(tool_conf.get("resolution") or tool_conf.get("video_resolution") or "").strip()
                if is_draft_mode:
                    payload["resolution"] = "480p"
                elif requested_res:
                    payload["resolution"] = requested_res if requested_res.lower().endswith("p") else f"{requested_res}p"
                else:
                    payload["resolution"] = "720p"
            if callback_url and callback_url != "-1":
                payload["callback_url"] = callback_url

            # Apply Draft Mode (Sample Mode) if configured and supported (seedance models)
            if model and ("1-5-pro" in model or "seedance" in model):
                if "doubao-seedance-2" in model.lower() and (start_img_url or last_frame_url):
                    pass
                else:
                    payload["draft"] = bool(tool_conf.get("draft", False))
            
            # Seedance / Doubao video: always send ratio with the same value as aspect_ratio.
            payload["ratio"] = final_ratio
            _debug_log(
                f"[DoubaoVideo] ratio_in={aspect_ratio}, ratio_final={final_ratio}, "
                f"mode={'t2v' if (not start_img_url and not last_frame_url) else 'i2v'}, "
                f"callback_enabled={bool(payload.get('callback_url'))}"
            )


            # Enable generate_audio for 1.5 Pro models which support it.
            # Respect explicit config override (generate_audio: false for silent variants).
            if payload["model"] and "1-5-pro" in payload["model"]:
                if "generate_audio" in tool_conf:
                    payload["generate_audio"] = bool(tool_conf["generate_audio"])
                else:
                    payload["generate_audio"] = True

            poll_timeout_seconds = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS
            poll_interval_seconds = 2
            try:
                if tool_conf.get("poll_timeout_seconds") is not None:
                    poll_timeout_seconds = min(600, max(60, int(tool_conf.get("poll_timeout_seconds"))))
                elif tool_conf.get("timeout") is not None:
                    poll_timeout_seconds = min(600, max(60, int(tool_conf.get("timeout"))))
            except Exception:
                poll_timeout_seconds = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS

            try:
                if tool_conf.get("poll_interval_seconds") is not None:
                    poll_interval_seconds = max(1, int(tool_conf.get("poll_interval_seconds")))
            except Exception:
                poll_interval_seconds = 2

            return await self._submit_and_poll_video(
                endpoint,
                payload,
                api_key,
                "doubao_video",
                extra_metadata=base_metadata,
                poll_timeout_seconds=poll_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                pure_callback_mode=pure_callback_mode,
                callback_enabled=callback_enabled,
                callback_ticket=callback_ticket,
                callback_url=callback_url,
                provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
            )

        return {"error": "Unknown Type"}

    async def _handle_vidu_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, keyframes=None, negative_prompt: Optional[str] = None):
        """
        Vidu API Support (Images + Text -> Video)
        """
        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        api_key = config.get("api_key")
        if not api_key: return {"error": "No Vidu API Key"}
        
        raw_base_url = config.get("base_url") or "https://api.vidu.studio/open/v1/creation"
        endpoint = raw_base_url.rstrip("/")
        if "creation" not in endpoint: endpoint += "/open/v1/creation"
        
        model = config.get("model") or "vidu2.0"
        tool_conf = config.get("config", {}) or {}
        raw_callback_url = str(tool_conf.get("_provider_callback_url") or tool_conf.get("webhookUrl") or tool_conf.get("webHook") or tool_conf.get("webhook") or tool_conf.get("callBackUrl") or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or "").strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"vidu-{gen_type}"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url: callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(
            str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"}
        )

        def _normalize_bool(raw: Any, default: bool) -> bool:
            if raw is None:
                return default
            if isinstance(raw, bool):
                return raw
            text = str(raw).strip().lower()
            if text in {"1", "true", "yes", "y", "on"}:
                return True
            if text in {"0", "false", "no", "n", "off"}:
                return False
            return default

        # Vidu sound switch: prefer explicit `sound`, then legacy `is_rec`, default enabled.
        sound_enabled = _normalize_bool(
            tool_conf.get("sound") if "sound" in tool_conf else tool_conf.get("is_rec"),
            True,
        )
        
        # Check for Multi-Frame Mode (Keyframes present)
        is_multiframe = keyframes and len(keyframes) >= 1
        
        # If multi-frame, we use different payload structure
        if is_multiframe:
            _debug_log("[Vidu] Using Multi-Frame (Keyframes) Mode")
            # Required: model, start_image, image_settings
            # Typically model is viduq2-turbo or viduq2-pro for this mode (as per user snippet)
            # Default to viduq2-turbo if current model is not appropriate? 
            # Or just use configured model and hope user selected correct one.
            # User snippet: Optional values: viduq2-turbo, viduq2-pro
            
            payload = {
                "model": model, 
                "prompt": prompt[:2000] if prompt else ""
            }
            if callback_url and callback_url != "-1":
                payload["webhookUrl"] = callback_url

            if callback_url and callback_url != "-1":
                payload["webhookUrl"] = callback_url

            
            # 1. Start Image
            start_img_src = None
            if ref_image:
                 refs = ref_image if isinstance(ref_image, list) else [ref_image]
                 if refs: start_img_src = refs[0]
            
            if not start_img_src:
                 return {"error": "Vidu Multi-Frame requires a Start Image (Reference Image)"}
                 
            start_ref = await self._resolve_ref_for_api_async(start_img_src, force_data_uri_for_local=True)
            if not start_ref: return {"error": "Failed to load Start Image"}
            
            payload["start_image"] = start_ref
            
            # 2. Image Settings (Keyframes)
            # User spec: Array of keyframe config. Min 2.
            # Assuming structure: [{"image": "b64"}, ...] based on general Vidu practices or simplified interpretation.
            # Actually, user provided spec didn't define inside object.
            # But "image_settings" name implies objects. Maybe related to timestamps too.
            # Since we only have URLs, we will try to pass minimal object: {"image": "...", "timestamp": auto?}
            # Or just pass the images if the array expects strings? 
            # Note: "image_settings Array ... max 9 keyframes"
            # It's safest to assume standard keyframe format: { "image": "base64", "timestamp": float (0-1) } or just ordered list.
            # Given user didn't specify timestamp rules, likely just ordered frames?
            # Let's try passing list of objects with "image" key.
            
            settings_arr = []
            for kf in keyframes:
                 resolved_kf = await self._resolve_ref_for_api_async(kf, force_data_uri_for_local=True)
                 if resolved_kf:
                     # Attempt generic structure. 
                     # If backend rejects, we will know.
                     # Vidu Character Consistency uses "characters".
                     # This "image_settings" is likely for timeline control.
                     settings_arr.append({"image": resolved_kf})
            
            # Validation: Min 2 keyframes
            if len(settings_arr) < 2:
                  _debug_log("[Vidu] Warning: Multi-frame expects min 2 keyframes. Current: " + str(len(settings_arr)), "warning")
                  # If only 1 keyframe, maybe duplication works? Or fall back?
                  if len(settings_arr) == 1:
                       settings_arr.append(settings_arr[0]) # Duplicate to meet min requirements
            
            payload["image_settings"] = settings_arr[:9] # Max 9

        else:
            # Standard Start/End Mode
            payload = {
                "model": model,
                "prompt": prompt[:2000] if prompt else ""
            }
            images = []
            if ref_image:
                refs = ref_image if isinstance(ref_image, list) else [ref_image]
                if refs:
                    start_ref = await self._resolve_ref_for_api_async(refs[0], force_data_uri_for_local=True)
                    if start_ref: images.append(start_ref)
            
            if last_frame_url:
                end_ref = await self._resolve_ref_for_api_async(last_frame_url, force_data_uri_for_local=True)
                if end_ref:
                     if not images: images.append(end_ref) # Use as start if no start
                     else: images.append(end_ref) # Use as end
            
            if images: payload["images"] = images

        # Shared: Duration & Resolution
        is_draft_mode = self._normalize_bool_value(tool_conf.get("draft_mode") or tool_conf.get("draft"))
        if duration:
            dur_int = int(duration)
            if dur_int < 1:
                dur_int = 4
            if model == "vidu2.0":
                payload["duration"] = 8 if dur_int >= 6 else 4
                if payload["duration"] == 8:
                    payload["resolution"] = "720p"
            elif "viduq1" in model:
                payload["duration"] = 5
                payload["resolution"] = "720p"
            else:
                payload["duration"] = min(dur_int, 8)

        if is_draft_mode:
            payload["resolution"] = "480p"
        else:
            requested_res = str(
                tool_conf.get("resolution") or tool_conf.get("video_resolution") or payload.get("resolution") or ""
            ).strip()
            if requested_res:
                payload["resolution"] = requested_res if requested_res.lower().endswith("p") else f"{requested_res}p"
            elif "resolution" not in payload or str(payload.get("resolution") or "").strip().lower() == "1080p":
                payload["resolution"] = "720p"

        # Config overrides
        if config.get("config"):
             cf = config.get("config")
             if cf.get("seed"): payload["seed"] = int(cf.get("seed"))
             if cf.get("resolution"): payload["resolution"] = cf.get("resolution")
             if self._normalize_bool_value(cf.get("draft_mode") or cf.get("draft")): payload["resolution"] = "480p"

        # Always pass the resolved audio flag to Vidu payload.
        payload["is_rec"] = bool(sound_enabled)
        if callback_enabled:
            payload["webhookUrl"] = callback_url

        _debug_log(
            f"[Vidu] Job Submission: Model={model}, Dur={payload.get('duration')}, Res={payload.get('resolution')}, MultiFrame={is_multiframe}, Sound={payload.get('is_rec')}, callback_enabled={callback_enabled}"
        )
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {api_key}"
        }
        
        try:
            # Submit
            resp = await asyncio.to_thread(
                lambda: requests.post(endpoint, json=payload, headers=headers, timeout=_media_submit_timeout_pair())
            )
            if resp.status_code not in [200, 201]:
                return {"error": f"Vidu Error {resp.status_code}", "details": resp.text}

            data = resp.json()
            task_id = data.get("id")
            if not task_id:
                return {"error": "No Task ID returned", "details": resp.text}

            task_id_callback = tool_conf.get("_provider_task_id_callback")
            if callable(task_id_callback):
                try:
                    callback_result = task_id_callback(str(task_id))
                    if asyncio.iscoroutine(callback_result):
                        await callback_result
                except Exception as callback_err:
                    logger.warning("Vidu task_id_callback_failed | task_id=%s error=%s", task_id, callback_err)

            if pure_callback_mode and callback_enabled:
                logger.info(
                    "Vidu pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s",
                    task_id,
                    callback_ticket,
                    callback_url,
                )
                return {
                    "pending_callback": True,
                    "provider_task_id": str(task_id),
                    "metadata": {
                        "raw": data,
                        "submit_raw": data,
                        "provider": "vidu",
                        "model": model,
                        "task_id": str(task_id),
                        "taskId": str(task_id),
                        "pending_callback": True,
                        "callback_ticket": callback_ticket,
                        "callback_url": callback_url,
                        "has_audio": bool(sound_enabled),
                        "sound": bool(sound_enabled),
                    },
                }

            # Poll
            poll_url = f"{endpoint}/{task_id}"
            for _ in range(90):
                await asyncio.sleep(5)
                p_resp = await asyncio.to_thread(
                    lambda: requests.get(poll_url, headers=headers, timeout=30)
                )
                if p_resp.status_code == 200:
                    p_data = p_resp.json()
                    status = p_data.get("state") or p_data.get("status")

                    if status == "success" or status == "SUCCESS":
                        vid_url = p_data.get("valid_video_url") or p_data.get("video_url") or p_data.get("url")
                        if vid_url:
                            return {
                                "url": vid_url,
                                "metadata": {
                                    "raw": p_data,
                                    "provider": "vidu",
                                    "model": model,
                                    "has_audio": bool(sound_enabled),
                                    "sound": bool(sound_enabled),
                                },
                            }
                    elif status == "failed" or status == "FAILED":
                        return {"error": "Vidu Generation Failed", "details": str(p_data)}

            return {"error": "Timeout polling Vidu"}

        except Exception as e:
            traceback.print_exc()
            return {"error": f"Vidu Exception: {str(e)}"}
             
    async def _handle_grsai_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        trace_id = None
        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        api_key = config.get("api_key")
        model = config.get("model") or "unknown_model"
        trace_id = f"grsai-{uuid.uuid4().hex[:10]}"
        _debug_log(f"[Grsai] Starting Generation. Type={gen_type}, Model={model}, PromptLen={len(prompt) if prompt else 0}")
        logger.info(
            "[GrsaiTrace][%s] start | type=%s model=%s prompt_len=%s render_service=%s render_instance=%s",
            trace_id,
            gen_type,
            model,
            len(prompt) if prompt else 0,
            os.getenv("RENDER_SERVICE_ID", ""),
            os.getenv("RENDER_INSTANCE_ID", ""),
        )
        tool_conf = config.get("config", {}) or {}
        internal_callback_url = str(tool_conf.get("_provider_callback_url") or "").strip()
        raw_callback_url = str(
            internal_callback_url
                or tool_conf.get("webHook")
                or tool_conf.get("webhook")
            or tool_conf.get("callBackUrl")
            or tool_conf.get("callback_url")
            or tool_conf.get("callbackUrl")
            or ""
        ).strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"grsai-{gen_type}"
        callback_deployment_hint = self._is_public_deployment_hint()
        callback_public_base = self._resolve_public_base_url()
        callback_url = self._resolve_provider_callback_url(tool_conf, callback_ticket)
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(
            str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"}
        )
        # Never wait-only on callbacks when this process is not on a publicly reachable deploy.
        if pure_callback_mode and not self._is_public_deployment_hint():
            logger.info(
                "[GrsaiTrace][%s] pure_callback_mode ignored on non-public deploy; falling back to provider poll",
                trace_id,
            )
            pure_callback_mode = False
        callback_source = "none"
        if raw_callback_url and raw_callback_url != "-1":
            callback_source = "explicit"
        elif callback_url and callback_url != "-1":
            callback_source = "auto_public"
        elif callback_url == "-1" or raw_callback_url == "-1":
            callback_source = "disabled"
        logger.info(
            "[GrsaiTrace][%s] callback resolution | ticket=%s raw_callback=%s resolved_callback=%s callback_source=%s pure_callback_mode=%s deployment_hint=%s public_base=%s",
            trace_id,
            callback_ticket,
            _strip_query_from_log_url(raw_callback_url),
            _strip_query_from_log_url(callback_url),
            callback_source,
            pure_callback_mode and callback_enabled,
            callback_deployment_hint,
            _strip_query_from_log_url(callback_public_base),
        )
        if callback_url and callback_url != raw_callback_url:
            logger.info(
                "[GrsaiTrace][%s] callback auto-assigned | ticket=%s callback_url=%s raw_callback=%s",
                trace_id,
                callback_ticket,
                callback_url,
                raw_callback_url or None,
            )
        raw_endpoint = (tool_conf.get("endpoint") or "").strip()
        base_url = config.get("base_url") or "https://grsaiapi.com"
        
        # Robust stripping of Grsai specific paths to get the true base URL
        # Remove /v1/draw/..., /v1/video/..., or just /v1 at the end
        # This prevents "double pathing" if user pastes a full endpoint URL like .../v1/draw/nano-banana
        base_url = re.sub(r'/v1/(draw|video).*$', '', base_url, flags=re.IGNORECASE)
        base_url = re.sub(r'/v1/?$', '', base_url).rstrip("/")
        
        # Image
        if gen_type == "image":
            endpoint = raw_endpoint.rstrip("/") if raw_endpoint and "/draw/" in raw_endpoint else f"{base_url}/v1/draw/completions"
            is_banana = model and model.startswith("nano-banana")
            model_key = str(model or "").strip().lower().replace("/", "-").replace("_", "-")
            is_gpt_image_2_family = "gpt-image-2" in model_key
            if not raw_endpoint and is_banana:
                endpoint = f"{base_url}/v1/draw/nano-banana"

            request_user_id_raw = tool_conf.get("_request_user_id")
            try:
                request_user_id = int(request_user_id_raw or 1)
            except Exception:
                request_user_id = 1
            
            final_model = model or "sora-image"
            payload = {"model": final_model, "prompt": prompt, "shutProgress": False}
            oss_config = tool_conf.get("oss") if isinstance(tool_conf.get("oss"), dict) else {}
            oss_id = str(
                tool_conf.get("oss-id")
                or tool_conf.get("oss_id")
                or tool_conf.get("ossId")
                or (oss_config.get("id") if isinstance(oss_config, dict) else "")
                or os.getenv("GRSAI_OSS_ID")
                or "69c890a3a0a438550965e9ff"
                or ""
            ).strip()
            # Match OSS upload layout: .../{yyyymm}/{user_id}/...
            yyyymm = datetime.utcnow().strftime("%Y%m")
            raw_oss_path = str(
                tool_conf.get("oss-path")
                or tool_conf.get("oss_path")
                or tool_conf.get("ossPath")
                or (oss_config.get("path") if isinstance(oss_config, dict) else "")
                or os.getenv("GRSAI_OSS_PATH")
                or ""
            ).strip()
            if "{yyyymm}" in raw_oss_path:
                raw_oss_path = raw_oss_path.replace("{yyyymm}", yyyymm)
            if "{user_id}" in raw_oss_path:
                oss_path = raw_oss_path.replace("{user_id}", str(request_user_id))
            elif raw_oss_path:
                normalized_oss_path = raw_oss_path.rstrip("/")
                user_segment = f"/{request_user_id}"
                if normalized_oss_path.endswith(user_segment):
                    oss_path = normalized_oss_path
                else:
                    oss_path = f"{normalized_oss_path}{user_segment}"
            else:
                oss_path = f"file/images/{yyyymm}/{request_user_id}"
            # Ensure yyyymm segment exists before user_id (covers legacy templates).
            path_parts = [p for p in str(oss_path).strip("/").split("/") if p]
            user_str = str(request_user_id)
            if path_parts and path_parts[-1] == user_str:
                has_yyyymm_before_user = len(path_parts) >= 2 and bool(re.fullmatch(r"\d{6}", path_parts[-2] or ""))
                if not has_yyyymm_before_user:
                    path_parts.insert(-1, yyyymm)
                    oss_path = "/".join(path_parts)
            elif yyyymm not in path_parts:
                path_parts.extend([yyyymm, user_str])
                oss_path = "/".join(path_parts)
            grsai_extra_headers: Dict[str, str] = {}
            if oss_id:
                grsai_extra_headers["oss-id"] = oss_id
            if oss_path:
                grsai_extra_headers["oss-path"] = oss_path
            logger.info(
                "[GrsaiTrace][%s] image submit headers | content_type=application/json auth_bearer=%s has_oss_id=%s has_oss_path=%s oss_id=%s oss_path=%s",
                trace_id,
                bool(api_key),
                bool(oss_id),
                bool(oss_path),
                oss_id,
                oss_path,
            )
            callback_payload_value = callback_url if callback_url and callback_url != "-1" else "-1"
            payload["webHook"] = callback_payload_value
            payload["webhook"] = callback_payload_value
            task_id_callback = tool_conf.get("_grsai_task_id_callback")
            if not callable(task_id_callback):
                task_id_callback = None
            logger.info(
                "[GrsaiTrace][%s] image callback payload | callback_enabled=%s webHook=%s webhook=%s",
                trace_id,
                bool(callback_url and callback_url != "-1"),
                _strip_query_from_log_url(payload.get("webHook")),
                _strip_query_from_log_url(payload.get("webhook")),
            )
            base_metadata = {"provider": "grsai", "model": final_model, "prompt": prompt}

            normalized_ar = self._normalize_aspect_ratio_value(aspect_ratio)
            if normalized_ar:
                payload["aspectRatio"] = normalized_ar
                base_metadata["submit_aspect_ratio"] = normalized_ar

            if ref_image:
                ref_list = [ref_image] if isinstance(ref_image, str) else ref_image
                resolved_refs = []
                _debug_log(f"[Grsai] Processing {len(ref_list)} reference images...")
                prefer_public_upload_url = self._is_public_deployment_hint()
                request_filename_base = str(tool_conf.get("_request_filename_base") or "grsai_ref").strip() or "grsai_ref"
                for i, r in enumerate(ref_list):
                    candidate_ref = r
                    if (
                        prefer_public_upload_url
                        and isinstance(candidate_ref, str)
                        and str(candidate_ref).strip().startswith("data:image/")
                    ):
                        try:
                            hosted_ref = await asyncio.to_thread(
                                self._download_and_save,
                                str(candidate_ref).strip(),
                                f"{request_filename_base}_ref{i + 1}",
                                request_user_id,
                            )
                            public_hosted_ref = self._resolve_public_upload_url(hosted_ref) or hosted_ref
                            if public_hosted_ref and str(public_hosted_ref).strip().startswith(("http://", "https://")):
                                candidate_ref = public_hosted_ref
                                logger.info(
                                    "[GrsaiTrace][%s] ref hosted before submit | ref_index=%s user_id=%s hosted_ref=%s",
                                    trace_id,
                                    i,
                                    request_user_id,
                                    _strip_query_from_log_url(public_hosted_ref),
                                )
                        except Exception as ref_host_error:
                            logger.warning(
                                "[GrsaiTrace][%s] ref host before submit failed | ref_index=%s error=%s",
                                trace_id,
                                i,
                                ref_host_error,
                            )
                    resolved = await self._resolve_ref_for_api_async(
                        candidate_ref,
                        force_data_uri_for_local=True,
                        prefer_public_upload_url=prefer_public_upload_url,
                        data_uri_profile="grsai_image_ref",
                    )
                    if resolved:
                        resolved_refs.append(resolved)
                    else:
                        _debug_log(f"[Grsai] Error: Failed to resolve ref image {i} ({r}). Dropping.", "warning")
                
                _debug_log(f"[Grsai] Final Refs Count: {len(resolved_refs)}")
                payload["urls"] = resolved_refs
            
            # Resolution Logic
            w = tool_conf.get("width")
            h = tool_conf.get("height")
            explicit_size_raw = tool_conf.get("size")
            explicit_size = explicit_size_raw or tool_conf.get("imageSize") or tool_conf.get("image_size")
            
            if is_gpt_image_2_family:
                res_str, remove_aspect_ratio = self._resolve_grsai_gpt_image_2_size(
                    final_model,
                    normalized_ar,
                    explicit_size,
                    w,
                    h,
                )
                if remove_aspect_ratio:
                    payload.pop("aspectRatio", None)
                base_metadata["submit_size"] = res_str
            else:
                if aspect_ratio:
                     # Generic fallback mapping for non-gpt-image Grsai image models.
                     if aspect_ratio == "16:9": res_str = "2560x1440"
                     elif aspect_ratio == "9:16": res_str = "720x1280"
                     elif aspect_ratio == "4:3": res_str = "1024x768"
                     elif aspect_ratio == "3:4": res_str = "768x1024"
                     elif aspect_ratio == "21:9": res_str = "1536x640" 
                     else: res_str = "2560x1440"
                elif w and h:
                    res_str = f"{w}x{h}"
                else:
                     res_str = "2560x1440"

            normalized_image_size = self._normalize_image_size_value(
                image_size or tool_conf.get("image_size") or tool_conf.get("imageSize")
            )
            if not normalized_image_size:
                normalized_image_size = self._infer_image_size_from_dimensions(
                    w if w else (res_str.split("x")[0] if "x" in res_str else 1024),
                    h if h else (res_str.split("x")[1] if "x" in res_str else 1024),
                )

            if is_banana:
                payload["imageSize"] = normalized_image_size
            else:
                payload["size"] = res_str
            
            # Create a log-friendly copy of the payload to hide base64 content
            log_payload = _strip_base64_from_log(payload)

            result_base = endpoint.split("/v1/")[0] if "/v1/" in endpoint else base_url
            result_url = f"{result_base}/v1/draw/result"

            _debug_log(f"[Grsai] Submitting Payload: {_format_payload_for_log(log_payload)}")
            payload_bytes = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            inline_ref_bytes = sum(self._data_uri_image_size_bytes(item) or 0 for item in (payload.get("urls") or []))
            logger.info(
                "[GrsaiTrace][%s] image submit prepared | endpoint=%s result_url=%s has_refs=%s refs_count=%s callback_enabled=%s payload_keys=%s payload_bytes=%s inline_ref_bytes=%s",
                trace_id,
                endpoint,
                result_url,
                bool(payload.get("urls")),
                len(payload.get("urls") or []),
                bool(callback_url and callback_url != "-1"),
                sorted(list(payload.keys())),
                payload_bytes,
                inline_ref_bytes,
            )
            return await self._submit_and_poll_grsai(
                endpoint,
                payload,
                api_key,
                result_url,
                extra_metadata=base_metadata,
                trace_id=trace_id,
                task_id_callback=task_id_callback,
                extra_headers=grsai_extra_headers,
                pure_callback_mode=pure_callback_mode,
                callback_enabled=callback_enabled,
                callback_ticket=callback_ticket,
                callback_url=callback_url,
            )

        # Video
        elif gen_type == "video":
            model_lower = (model or "").lower()
            is_veo = "veo" in model_lower
            
            # Check if user provided a specific full endpoint (Prefer Map -> Then generic config)
            endpoint_map = tool_conf.get("endpointMap", {})
            mapped_endpoint = endpoint_map.get(model)
            resolved_endpoint = (mapped_endpoint or raw_endpoint or "").strip()
            
            if resolved_endpoint and ("/video/" in resolved_endpoint or resolved_endpoint.endswith("/veo")):
                endpoint = resolved_endpoint.rstrip("/")
            else:
                 # Auto-construct from base URL
                 endpoint_suffix = "sora-video" # default
                 if is_veo:
                     endpoint_suffix = "veo"
                 elif "kling" in model_lower or "banana" in model_lower:
                     endpoint_suffix = "kling"
                 elif "runway" in model_lower:
                     endpoint_suffix = "runway"
                 elif "luma" in model_lower:
                     endpoint_suffix = "luma"
                 elif "hailuo" in model_lower or "minimax" in model_lower:
                     endpoint_suffix = "hailuo"
                 elif "cogvideo" in model_lower:
                     endpoint_suffix = "cogvideox"
                     
                 # Use base_url which was sanitized at start of method (removing trailing /v1)
                 # Correct Grsai logic: base_url usually ends with host e.g. https://grsai.dakka.com.cn
                 # The correct paths are /v1/video/veo, /v1/video/sora-video, etc.
                 
                 # Strip any trailing logic to be safe
                 clean_base = base_url.split("/v1")[0].rstrip("/")
                 
                 # Force https if missing (common config error)
                 if not clean_base.startswith("http"):
                     clean_base = f"https://{clean_base}"
                     
                 endpoint = f"{clean_base}/v1/video/{endpoint_suffix}"
            
            # Recalculate result endpoint based on the FINAL submission endpoint
            # Logic: If endpoint is .../v1/video/veo, we want to go up to .../v1/draw/result
            # The pattern is fairly standard for this provider: base + /v1/draw/result
            
            # Attempt to extract base from final endpoint
            result_base = base_url
            if "/v1/" in endpoint:
                result_base = endpoint.split("/v1/")[0]
            
            result_url = f"{result_base}/v1/draw/result"
            _debug_log(f"[Grsai] Computed Result Poll URL: {result_url}")

            final_model = model or ("veo3.1-fast" if is_veo else "sora-2")
            
            # Common payload elements
            payload = {"model": final_model, "prompt": prompt, "shutProgress": True}
            
            if is_veo:
                # Veo spec: strict aspectRatio (only 16:9 or 9:16 supported), urls param empty if unused, webHook needs to be URL format
                # Enforce supported aspect ratios for the API parameter
                api_ar = "16:9"
                if aspect_ratio == "9:16": 
                    api_ar = "9:16"
                payload["aspectRatio"] = api_ar
                # API requires integer for duration
                payload["duration"] = int(duration) if duration else 5
                
                # payload["urls"] = [] # API Spec: urls cannot be used with firstFrameUrl/lastFrameUrl. We prioritize firstFrameUrl.
                # prompt truncation moved to end
            else:
                # Sora/Others
                callback_payload_value = callback_url if callback_url and callback_url != "-1" else "-1"
                payload["webHook"] = callback_payload_value
                payload["webhook"] = callback_payload_value
                # API requires integer for duration
                payload["duration"] = int(duration) if duration else 5
                video_is_draft = self._normalize_bool_value(tool_conf.get("draft_mode") or tool_conf.get("draft"))
                if aspect_ratio:
                    # Default map for common ratios if API expects WxH
                    map_size = {
                        "16:9": "854x480" if video_is_draft else "1280x720",
                        "9:16": "480x854" if video_is_draft else "720x1280",
                        "1:1": "480x480" if video_is_draft else "720x720",
                        "4:3": "640x480" if video_is_draft else "960x720",
                        "2.35:1": "1128x480" if video_is_draft else "1692x720"
                    }
                    if aspect_ratio in map_size:
                        payload["size"] = map_size[aspect_ratio]
                    else:
                        payload["aspect_ratio"] = aspect_ratio
                elif not is_veo:
                    payload["size"] = "854x480" if video_is_draft else "1280x720"

            base_metadata = {"provider": "grsai", "model": final_model, "prompt": prompt}
            
            # Grsai expects URLs or Base64
            # is_veo check moved up
            
            if ref_image:
                if is_veo:
                    # Explicitly process for Veo requirements
                    payload["firstFrameUrl"] = await self._process_veo_image_async(ref_image, aspect_ratio or "16:9")
                else:
                    val = await self._resolve_ref_for_api_async(ref_image, force_data_uri_for_local=True)
                    if val: payload["url"] = val
            elif is_veo:
                # Veo: firstFrameUrl is Optional. 
                # But if we have lastFrameUrl, we MUST have firstFrameUrl.
                # If we have neither, we can omit both.
                # Logic: Only force black frame if we have lastFrameUrl but no firstFrameUrl.
                if last_frame_url:
                     _debug_log("[Grsai] Auto-generating Black Start Frame for Veo (Required by Last Frame)...")
                     try:
                        # Generate black image
                        img = Image.new('RGB', (1024, 576), (0, 0, 0))
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
                        payload["firstFrameUrl"] = f"data:image/png;base64,{b64_str}"
                     except Exception as e:
                        _debug_log(f"[Grsai] Failed to gen black frame: {e}", "warning") 
            
            if last_frame_url:
                if is_veo:
                    payload["lastFrameUrl"] = await self._process_veo_image_async(last_frame_url, aspect_ratio or "16:9")
                else:
                    val = await self._resolve_ref_for_api_async(last_frame_url, force_data_uri_for_local=True)
                    if val: payload["end_reference_image"] = val

            # Veo Clean Prompt Logic
            if is_veo and prompt:
                 # Remove markdown and brackets to avoid API parsing errors
                 clean_prompt = re.sub(r'[\*\[\]\{\}]', '', prompt)
                 # Enforce length limit
                 payload["prompt"] = clean_prompt[:1200]

            # Ensure we don't send None
            if is_veo:
                 # Validation: If we have firstFrameUrl/lastFrameUrl, Remove urls key completely
                 if "firstFrameUrl" in payload or "lastFrameUrl" in payload:
                      if "urls" in payload: del payload["urls"]
                 else:
                      # If no frames, we could use urls, but we don't support it in this logic path yet.
                      # Ensure no empty firstFrameUrl keys exist
                      pass

                 # Remove lastFrameUrl/firstFrameUrl if empty string
                 if "lastFrameUrl" in payload and not payload["lastFrameUrl"]:
                     del payload["lastFrameUrl"]
                 if "firstFrameUrl" in payload and not payload["firstFrameUrl"]:
                     del payload["firstFrameUrl"]

                 payload["webHook"] = callback_url if callback_url and callback_url != "-1" else "-1"

            # Debug log (sanitized)
            debug_p = _strip_base64_from_log(payload)

            _debug_log(f"[Grsai] Video Payload: {_format_payload_for_log(debug_p)}")
            if is_veo:
                _debug_log(f"[Grsai][Veo] Submit Duration={payload.get('duration')} Model={final_model} Aspect={payload.get('aspectRatio')}")
            logger.info(
                "[GrsaiTrace][%s] video submit prepared | endpoint=%s result_url=%s is_veo=%s payload_keys=%s",
                trace_id,
                endpoint,
                result_url,
                is_veo,
                sorted(list(payload.keys())),
            )
            
            # Double check payload validity before sending
            video_task_id_callback = tool_conf.get("_grsai_task_id_callback")
            if not callable(video_task_id_callback):
                video_task_id_callback = tool_conf.get("_provider_task_id_callback")
            if not callable(video_task_id_callback):
                video_task_id_callback = None
            return await self._submit_and_poll_grsai(
                endpoint,
                payload,
                api_key,
                result_url,
                is_video=True,
                extra_metadata=base_metadata,
                trace_id=trace_id,
                task_id_callback=video_task_id_callback,
                pure_callback_mode=pure_callback_mode,
                callback_enabled=callback_enabled,
                callback_ticket=callback_ticket,
                callback_url=callback_url,
            )
    
    async def _submit_and_poll_grsai_legacy(self, url, payload, api_key, result_url, is_video=False, extra_metadata=None):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        def _post():
            return requests.post(url, json=payload, headers=headers, timeout=_media_submit_timeout_pair(), verify=False)
        
        try:
            resp = await asyncio.to_thread(_post)
            _debug_log(f"[Grsai Legacy] API Returned: {_strip_base64_from_log(resp.text[:1000])}") # DEBUG USER REQUEST
            if resp.status_code != 200:
                return {"error": f"Submission Failed {resp.status_code}", "details": resp.text}

            data = resp.json()
            task_id = data.get("data") # Grsai returns task ID directly in data field usually? or data.data?
            # Adjust based on Grsai spec: usually {code: 200, data: "taskId..."}
            if not task_id:
                return {"error": "No Task ID"}

            # Poll
            for _ in range(90):
                await asyncio.sleep(5)

                def _poll():
                    return requests.post(result_url, json={"id": task_id}, headers=headers, timeout=30, verify=False)

                p_resp = await asyncio.to_thread(_poll)

                if p_resp.status_code == 200:
                    p_data = p_resp.json()
                    # Check completion
                    if "data" in p_data and p_data["data"]:
                        final = p_data["data"][0].get("imageUrl" if not is_video else "videoUrl")
                        if final:
                            resolved_final = str(final)
                            if oss_storage_service.is_managed_url(resolved_final):
                                resolved_final = str(oss_storage_service.refresh_url(resolved_final) or resolved_final)
                            metadata = {"raw": p_data}
                            if extra_metadata:
                                metadata.update(extra_metadata)
                            return {"url": resolved_final, "metadata": metadata}
            return {"error": "Timeout"}
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Grsai Exception: {str(e)}"}


    async def _handle_tencent_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, negative_prompt: Optional[str] = None):
        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        if gen_type != "image":
             return {"error": "Tencent Video Not Implemented"}

        api_key = config.get("api_key")
        raw_key = (api_key or "").strip().replace("：", ":")
        parts = raw_key.split(":") if ":" in raw_key else [raw_key]
        if len(parts) < 2: return {"error": "Invalid Tencent Credentials"}
        secret_id, secret_key = parts[0].strip(), parts[1].strip()
        
        host = "aiart.tencentcloudapi.com"
        service = "aiart"
        version = "2022-12-29"
        region = "ap-shanghai"
        tool_conf = config.get("config", {}) or {}
        
        base_metadata = {"provider": "tencent", "model": "aiart", "prompt": prompt}

        # -- Helper: Sign and Request --
        async def call_tencent_api(action_name, req_payload):
            timestamp = int(time.time())
            date = datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')
            
            # 1. Canonical Request
            http_method = "POST"
            canonical_uri = "/"
            canonical_querystring = ""
            payload_json = json.dumps(req_payload, separators=(',', ':'))
            
            canonical_headers = f"content-type:application/json\nhost:{host}\nx-tc-action:{action_name.lower()}\n"
            signed_headers = "content-type;host;x-tc-action"
            
            hashed_payload = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            canonical_request = (http_method + "\n" + canonical_uri + "\n" + canonical_querystring + "\n" + canonical_headers + "\n" + signed_headers + "\n" + hashed_payload)
            
            # 2. String to Sign
            algorithm = "TC3-HMAC-SHA256"
            credential_scope = date + "/" + service + "/tc3_request"
            hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
            string_to_sign = (algorithm + "\n" + str(timestamp) + "\n" + credential_scope + "\n" + hashed_canonical)
            
            # 3. Calculate Signature
            def sign(key, msg): return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
            secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
            secret_service = sign(secret_date, service)
            secret_signing = sign(secret_service, "tc3_request")
            signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
            
            # 4. Access
            authorization = (algorithm + " " +
                                "Credential=" + secret_id + "/" + credential_scope + ", " +
                                "SignedHeaders=" + signed_headers + ", " +
                                "Signature=" + signature)
            
            req_headers = {
                "Authorization": authorization,
                "Content-Type": "application/json",
                "Host": host,
                "X-TC-Action": action_name,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Version": version,
                "X-TC-Region": region
            }
            
            def _post():
                return requests.post(f"https://{host}", data=payload_json, headers=req_headers, timeout=(15, 120), verify=False)
            
            return await asyncio.to_thread(_post)

        # -- Step 1: Submit Job --
        submit_action = "SubmitTextToImageJob"
        is_sync = False
        payload = {"Prompt": prompt, "LogoAdd": 0}
        
        # Image-to-Image logic
        if ref_image:
            submit_action = "ImageToImage"
            is_sync = True
            ref_value = await self._resolve_ref_for_api_async(ref_image, force_data_uri_for_local=False)
            if not ref_value:
                _debug_log("Failed to load reference image for Tencent I2I", "error")
                return {"error": "Failed to load reference image for Tencent I2I"}
            payload["InputImage"] = ref_value
            payload["RspImgType"] = "url"

        if submit_action == "SubmitTextToImageJob":
            payload["Resolution"] = "1024:768" # Default simplification

        resp = await call_tencent_api(submit_action, payload)
        if resp.status_code != 200: 
            _debug_log(f"[MediaService] Tencent Request Failed {resp.status_code}: {resp.text}", "error")
            return {"error": f"Tencent Request Failed {resp.status_code}", "details": resp.text}
        
        data = resp.json()
        if "Response" in data and "Error" in data["Response"]:
             _debug_log(f"[MediaService] Tencent API Error: {data['Response']['Error']}", "error")
             return {"error": f"Tencent API Error", "details": data["Response"]["Error"]}

        if is_sync:
            # Robust extraction of ResultImage (Handle String vs List)
            res_img = data.get("Response", {}).get("ResultImage")
            final_url = None
            if isinstance(res_img, list) and len(res_img) > 0:
                final_url = res_img[0]
            elif isinstance(res_img, str):
                final_url = res_img
                
            if final_url: 
                meta = {"raw": data}
                meta.update(base_metadata)
                return {"url": final_url, "metadata": meta}
            return {"error": "No ResultImage"}
        else:
            # Async
            job_id = data.get("Response", {}).get("JobId")
            if not job_id: return {"error": "No JobId"}
            
            for _ in range(60):
                await asyncio.sleep(5)
                q_resp = await call_tencent_api("QueryTextToImageJob", {"JobId": job_id})
                if q_resp.status_code == 200:
                    q_data = q_resp.json()
                    resp_inner = q_data.get("Response", {})
                    status = resp_inner.get("JobStatus") # SUCCESS, FAIL
                    if status == "SUCCESS":
                         # Robust extraction for async result
                         res_img = resp_inner.get("ResultImage")
                         final_url = None
                         if isinstance(res_img, list) and len(res_img) > 0:
                            final_url = res_img[0]
                         elif isinstance(res_img, str):
                            final_url = res_img
                            
                         meta = {"raw": q_data}
                         meta.update(base_metadata)
                         return {"url": final_url, "metadata": meta}
                    elif status == "FAIL":
                         return {"error": "Job Failed", "details": resp_inner.get("JobErrorMsg")}
            return {"error": "Timeout"}

    async def _handle_wanxiang_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None):
        if gen_type != "video": return {"error": "Wanxiang only supports video"}

        model_hint = str((config or {}).get("model") or "").strip().lower()
        if "happyhorse" in model_hint:
            return await self._handle_happyhorse_generation(
                gen_type,
                prompt,
                config,
                ref_image=ref_image,
                last_frame_url=last_frame_url,
                duration=duration,
                aspect_ratio=aspect_ratio,
                negative_prompt=negative_prompt,
            )

        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        tool_conf = config.get("config", {}) or {}
        raw_callback_url = str(
            tool_conf.get("_provider_callback_url")
            or tool_conf.get("callback_url")
            or tool_conf.get("callbackUrl")
            or tool_conf.get("callBackUrl")
            or tool_conf.get("webHook")
            or ""
        ).strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or "wanxiang-video"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url:
            callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"})
        
        api_key = config.get("api_key") or os.getenv("DASHSCOPE_API_KEY")
        endpoint = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis" 
        model = config.get("model") or "wanx2.1-i2v-plus"
        
        # Auto-correction for KF2V with single image to avoid "video frames must be set" error
        # KF2V likely requires multiple frames or specific array input, while I2V handles single image.
        if "kf2v" in model and ref_image and not last_frame_url:
             _debug_log(f"[Wanxiang] Model {model} requested but only 1 ref image provided. Switching to wanx2.1-i2v-plus.", "warning")
             model = "wanx2.1-i2v-plus"

        base_metadata = {"provider": "wanxiang", "model": model, "prompt": prompt}
        
        # Determine parameter names based on model type
        # i2v (Image) uses image_url
        # kf2v (KeyFrame) uses first_frame_url/last_frame_url, so we exclude it from is_i2v
        is_i2v = "i2v" in model
        
        first_img = await self._resolve_ref_for_api_async(ref_image, force_data_uri_for_local=True)
        
        # Validations
        if is_i2v and not first_img:
             return {"error": "Wanxiang I2V model requires a reference image."}
        
        input_data = {"prompt": prompt}
        effective_negative_prompt = str(negative_prompt or config.get("negative_prompt") or "").strip()
        if effective_negative_prompt:
            input_data["negative_prompt"] = effective_negative_prompt
        
        if is_i2v:
            input_data["image_url"] = first_img
        elif first_img:
            # T2V with start frame (if supported)
            input_data["first_frame_url"] = first_img

        if last_frame_url:
            last_img = await self._resolve_ref_for_api_async(last_frame_url, force_data_uri_for_local=True)
            if last_img:
                if is_i2v:
                     logger.warning("[Wanxiang] Warning: Model is i2v but last_frame_url provided. Ignoring.")
                else:
                     input_data["last_frame_url"] = last_img
        
        # Construct Parameters safely
        # Default resolution
        is_draft_mode = self._normalize_bool_value(tool_conf.get("draft_mode") or tool_conf.get("draft"))
        res = "480P" if is_draft_mode else str(config.get("resolution", "720P"))
        
        # Override with aspect_ratio if provided
        if aspect_ratio:
             # Wanx 2.1 strictly requires '720P' or '480P'. It does NOT accept '1280*720'.
             # It seems to infer orientation from valid input images or defaults to 1280x720.
             if aspect_ratio == "16:9": res = "720P"
             elif aspect_ratio == "9:16": res = "720P" # Use 720P and hope model respects input image
             elif aspect_ratio == "1:1": res = "720P"
             # If user provided a pixel string (e.g. 1280x720), force fallback to 720P to avoid API error
             elif "*" in aspect_ratio or "x" in aspect_ratio:
                  res = "720P"
        
        # Double check validity against known strict list
        if res not in ["720P", "480P", "1080P"]:
            # Wanx2.1 typically only supports 720P and 480P. 1080P might be available on some but safer to fallback.
            if "1280" in res or "720" in res:
                res = "720P"
            else:
                res = "720P" # Fallback safe default

        
        parameters = {
            "resolution": res,
            "prompt_extend": bool(config.get("prompt_extend", True))
        }
        if config.get("seed"): parameters["seed"] = int(config.get("seed"))
        
        payload = {
            "model": model,
            "input": input_data,
            "parameters": parameters
        }
        if callback_enabled:
            payload["webhook_url"] = callback_url
            payload["webhookUrl"] = callback_url
            payload["callback_url"] = callback_url
            payload["notify_url"] = callback_url

        # logger.info(f"[Wanxiang] Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        headers = {"X-DashScope-Async": "enable", "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        _debug_log(f"[Wanxiang] POSTING to {endpoint} with Model {model}")
        
        def _post():
            return requests.post(endpoint, json=payload, headers=headers, timeout=_media_submit_timeout_pair(), verify=False)
        
        try:
            resp = await asyncio.to_thread(_post)
            
            if resp.status_code != 200: 
                _debug_log(f"[Wanxiang] HTTP {resp.status_code} Error Body: {resp.text}", "error")
                # Try to parse error code if json
                try: 
                    err_body = resp.json()
                    return {"error": f"Wanxiang API Error ({err_body.get('code', 'Unknown')})", "details": err_body.get('message', resp.text)}
                except:
                    return {"error": f"Submission Failed {resp.status_code}", "details": resp.text}
            
            data = resp.json()
            _debug_log(f"[Wanxiang] Submission Success: {_strip_base64_from_log(data)}")
        except Exception as e:
            _debug_log(f"[Wanxiang] Exception: {e}", "error")
            import traceback
            traceback.print_exc()
            return {"error": f"Wanxiang Request Exception: {e}"}

        task_id = data.get("output", {}).get("task_id")
        if not task_id: return {"error": "No Task ID"}

        if pure_callback_mode and callback_enabled:
            logger.info(
                "Wanxiang pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s",
                task_id,
                callback_ticket,
                callback_url,
            )
            pending_meta = dict(base_metadata)
            pending_meta.update(
                {
                    "raw": data,
                    "submit_raw": data,
                    "task_id": str(task_id),
                    "taskId": str(task_id),
                    "pending_callback": True,
                    "callback_ticket": callback_ticket,
                    "callback_url": callback_url,
                }
            )
            return {
                "pending_callback": True,
                "provider_task_id": str(task_id),
                "metadata": pending_meta,
            }
        
        task_endpoint = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        
        for _ in range(120):
            await asyncio.sleep(5)
            def _poll(): return requests.get(task_endpoint, headers={"Authorization": f"Bearer {api_key}"}, timeout=30, verify=False)
            p_resp = await asyncio.to_thread(_poll)
            
            if p_resp.status_code == 200:
                p_data = p_resp.json()
                status = p_data.get("output", {}).get("task_status")
                if status == "SUCCEEDED":
                     meta = {"raw": p_data}
                     meta.update(base_metadata)
                     return {"url": p_data.get("output", {}).get("video_url"), "metadata": meta}
                elif status in ["FAILED", "CANCELED"]:
                     err_msg = p_data.get("output", {}).get("message")
                     _debug_log(f"[Wanxiang] Task Failed: {err_msg}", "error")
                     return {"error": "Generation Failed", "details": err_msg}
        return {"error": "Timeout"}

    async def _handle_happyhorse_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None):
        if gen_type != "video":
            return {"error": "HappyHorse only supports video"}

        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        api_key = config.get("api_key") or os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            return {"error": "Missing DASHSCOPE_API_KEY"}

        endpoint = str(
            config.get("base_url")
            or config.get("endpoint")
            or "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
        ).strip()
        model = str(config.get("model") or "happyhorse-1.0-r2v").strip() or "happyhorse-1.0-r2v"
        cfg = self._safe_json_dict(config.get("config"))
        raw_callback_url = str(
            cfg.get("_provider_callback_url")
            or cfg.get("callback_url")
            or cfg.get("callbackUrl")
            or cfg.get("callBackUrl")
            or cfg.get("webHook")
            or ""
        ).strip()
        callback_ticket = str(cfg.get("_provider_callback_ticket") or "").strip() or "happyhorse-video"
        callback_tool_conf = dict(cfg or {})
        if raw_callback_url:
            callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(str(cfg.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"})

        raw_refs = self._collect_video_reference_image_urls(
            ref_image,
            cfg,
            extra_sources=config,
            include_last_frame=True,
            last_frame_url=last_frame_url,
            limit=9,
        )
        unique_refs = raw_refs

        if not unique_refs:
            return {"error": "HappyHorse requires 1-9 reference images"}

        if len(unique_refs) > 9:
            unique_refs = unique_refs[:9]

        resolved_refs: List[str] = []
        for item in unique_refs:
            resolved = await self._resolve_ref_for_api_async(
                item,
                force_data_uri_for_local=False,
                prefer_public_upload_url=True,
            )
            resolved_text = str(resolved or "").strip()
            if not resolved_text:
                continue
            if not resolved_text.lower().startswith(("http://", "https://")):
                continue
            resolved_refs.append(resolved_text)

        if not resolved_refs:
            return {"error": "HappyHorse reference images must be public HTTP/HTTPS URLs"}

        if len(resolved_refs) > 9:
            resolved_refs = resolved_refs[:9]

        ratio = str(
            aspect_ratio
            or config.get("ratio")
            or config.get("aspect_ratio")
            or cfg.get("ratio")
            or "16:9"
        ).strip()

        resolution = str(
            config.get("resolution")
            or cfg.get("resolution")
            or "720P"
        ).strip().upper()
        if resolution not in {"1080P", "720P"}:
            resolution = "720P"

        safe_duration = 5
        try:
            safe_duration = int(duration)
        except Exception:
            safe_duration = 5
        safe_duration = max(3, min(15, safe_duration))

        seed_value = config.get("seed")
        try:
            seed_value = int(seed_value) if seed_value is not None and str(seed_value).strip() != "" else None
        except Exception:
            seed_value = None

        watermark_value = config.get("watermark")
        if watermark_value is None:
            watermark_value = cfg.get("watermark")
        if watermark_value is None:
            watermark_value = True
        watermark = bool(watermark_value)

        payload = {
            "model": model,
            "input": {
                "prompt": prompt,
                "media": [{"type": "reference_image", "url": ref} for ref in resolved_refs],
            },
            "parameters": {
                "resolution": resolution,
                "ratio": ratio or "16:9",
                "duration": safe_duration,
                "watermark": watermark,
            },
        }
        if callback_enabled:
            payload["webhook_url"] = callback_url
            payload["webhookUrl"] = callback_url
            payload["callback_url"] = callback_url
            payload["notify_url"] = callback_url
        if seed_value is not None:
            payload["parameters"]["seed"] = seed_value

        headers = {
            "X-DashScope-Async": "enable",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        _debug_log(f"[HappyHorse] POSTING to {endpoint} with model={model} refs={len(resolved_refs)}")

        def _post():
            return requests.post(endpoint, json=payload, headers=headers, timeout=_media_submit_timeout_pair(), verify=False)

        try:
            resp = await asyncio.to_thread(_post)
            if resp.status_code != 200:
                _debug_log(f"[HappyHorse] HTTP {resp.status_code} Error Body: {resp.text}", "error")
                try:
                    err_body = resp.json()
                    return {
                        "error": f"HappyHorse API Error ({err_body.get('code', 'Unknown')})",
                        "details": err_body.get("message", resp.text),
                    }
                except Exception:
                    return {"error": f"Submission Failed {resp.status_code}", "details": resp.text}
            data = resp.json()
        except Exception as e:
            _debug_log(f"[HappyHorse] Exception: {e}", "error")
            return {"error": f"HappyHorse Request Exception: {e}"}

        task_id = str((data.get("output") or {}).get("task_id") or "").strip()
        if not task_id:
            return {"error": "No Task ID", "details": data}

        if pure_callback_mode and callback_enabled:
            logger.info(
                "HappyHorse pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s",
                task_id,
                callback_ticket,
                callback_url,
            )
            pending_meta = {
                "provider": "happyhorse",
                "model": model,
                "prompt": prompt,
                "task_id": str(task_id),
                "raw": data,
                "submit_raw": data,
                "reference_images": resolved_refs,
                "pending_callback": True,
                "callback_ticket": callback_ticket,
                "callback_url": callback_url,
            }
            return {
                "pending_callback": True,
                "provider_task_id": str(task_id),
                "metadata": pending_meta,
            }

        parsed = urllib.parse.urlparse(endpoint)
        if not parsed.scheme or not parsed.netloc:
            return {"error": "Invalid HappyHorse endpoint", "details": endpoint}
        task_endpoint = f"{parsed.scheme}://{parsed.netloc}/api/v1/tasks/{task_id}"

        poll_timeout_seconds = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS
        poll_interval_seconds = 15
        try:
            if config.get("poll_timeout_seconds") is not None:
                poll_timeout_seconds = min(1800, max(60, int(config.get("poll_timeout_seconds"))))
            elif cfg.get("poll_timeout_seconds") is not None:
                poll_timeout_seconds = min(1800, max(60, int(cfg.get("poll_timeout_seconds"))))
        except Exception:
            poll_timeout_seconds = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS

        try:
            if config.get("poll_interval_seconds") is not None:
                poll_interval_seconds = max(2, int(config.get("poll_interval_seconds")))
            elif cfg.get("poll_interval_seconds") is not None:
                poll_interval_seconds = max(2, int(cfg.get("poll_interval_seconds")))
        except Exception:
            poll_interval_seconds = 15

        max_attempts = max(1, int(poll_timeout_seconds / max(1, poll_interval_seconds)))
        for _ in range(max_attempts):
            await asyncio.sleep(poll_interval_seconds)

            def _poll():
                return requests.get(
                    task_endpoint,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=30,
                    verify=False,
                )

            p_resp = await asyncio.to_thread(_poll)
            if p_resp.status_code != 200:
                continue

            p_data = p_resp.json()
            output = p_data.get("output") or {}
            status = str(output.get("task_status") or "").strip().upper()
            if status == "SUCCEEDED":
                video_url = output.get("video_url")
                if not video_url:
                    result_list = output.get("results") if isinstance(output.get("results"), list) else []
                    if result_list:
                        first_result = result_list[0] if isinstance(result_list[0], dict) else {}
                        video_url = first_result.get("video_url") or first_result.get("url")

                meta = {
                    "provider": "happyhorse",
                    "model": model,
                    "prompt": prompt,
                    "task_id": task_id,
                    "raw": p_data,
                    "submit_raw": data,
                    "reference_images": resolved_refs,
                }
                return {"url": video_url, "metadata": meta}

            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                return {
                    "error": f"HappyHorse task {status or 'FAILED'}",
                    "details": output.get("message") or output.get("code") or p_data,
                }

        return {"error": f"Timeout after {poll_timeout_seconds}s"}

    def _looks_like_video_media_ref(self, value: Any) -> bool:
        raw = str(value or "").strip().lower()
        if not raw:
            return False
        if raw.startswith("data:video/"):
            return True
        return any(token in raw for token in (".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v", "/video/", "video/"))

    def _resolve_public_media_url(self, value: Any) -> Optional[str]:
        raw = str(value or "").strip()
        if not raw:
            return None
        if self._is_public_http_url(raw):
            return raw
        return self._resolve_public_upload_url(raw)

    def _resolve_public_media_urls(self, values: Any) -> List[str]:
        source = values if isinstance(values, list) else [values]
        resolved: List[str] = []
        for item in source:
            url = self._resolve_public_media_url(item)
            if url:
                resolved.append(url)
        return resolved

    def _load_media_binary_for_upload(self, url_or_path: Any):
        raw = str(url_or_path or "").strip()
        if not raw:
            return None, None, None

        def _normalize_ext(ext: str, mime: str) -> str:
            normalized = str(ext or "").strip().lower()
            if normalized == ".jpe":
                return ".jpg"
            if normalized:
                # Discard any query parameters or URL encoding that might have leaked into extension
                normalized = normalized.split('?')[0].split('%')[0]
                if normalized.startswith('.') and len(normalized) <= 5: # basic sanity check
                    return normalized
            guessed = mimetypes.guess_extension(mime or "") or ""
            if guessed == ".jpe":
                guessed = ".jpg"
            return guessed

        if raw.startswith("data:"):
            marker = ";base64,"
            idx = raw.find(marker)
            if idx <= 5:
                return None, None, None
            mime = raw[5:idx].strip().lower() or "application/octet-stream"
            b64 = raw[idx + len(marker):].strip()
            if not b64:
                return None, None, None
            try:
                data = base64.b64decode(b64)
            except Exception:
                return None, None, None
            ext = _normalize_ext("", mime)
            filename = f"rh-upload-{uuid.uuid4().hex[:12]}{ext or '.bin'}"
            return data, mime, filename

        if raw.startswith("http://") or raw.startswith("https://"):
            try:
                resp = requests.get(raw, stream=True, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    return None, None, None
                data = resp.content
                mime = str(resp.headers.get("Content-Type", "")).split(";")[0].strip().lower() or "application/octet-stream"
                parsed_path = requests.utils.urlparse(raw).path or ""
                ext = _normalize_ext(os.path.splitext(parsed_path)[1], mime)
                filename = f"rh-upload-{uuid.uuid4().hex[:12]}{ext or '.bin'}"
                return data, mime, filename
            except Exception:
                return None, None, None

        path = raw
        if raw.startswith("/uploads/") or "/uploads/" in raw:
            fname = raw.split("/uploads/")[-1]
            upload_dir = settings.UPLOAD_DIR
            if not os.path.isabs(upload_dir):
                upload_dir = os.path.abspath(upload_dir)
            import urllib.parse
            clean_fname = fname.split('?')[0]
            path = os.path.join(upload_dir, urllib.parse.unquote(clean_fname))

        if not os.path.isabs(path):
            path = os.path.abspath(path)

        if not os.path.exists(path) or not os.path.isfile(path):
            return None, None, None

        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception:
            return None, None, None

        mime = (mimetypes.guess_type(path)[0] or "application/octet-stream").lower()
        ext = _normalize_ext(os.path.splitext(path)[1], mime)
        filename = f"rh-upload-{uuid.uuid4().hex[:12]}{ext or '.bin'}"
        return data, mime, filename

    def _upload_runninghub_binary_ref(self, ref_value: Any, api_key: str, base_url: str) -> Optional[str]:
        if not api_key:
            return None
        data, mime, filename = self._load_media_binary_for_upload(ref_value)
        if not data:
            return None

        upload_url = f"{str(base_url or 'https://www.runninghub.cn').rstrip('/')}/openapi/v2/media/upload/binary"
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {
            "file": (filename or f"rh-upload-{uuid.uuid4().hex[:12]}.bin", data, mime or "application/octet-stream")
        }

        try:
            resp = requests.post(upload_url, headers=headers, files=files, timeout=(15, 120), verify=False)
            if resp.status_code != 200:
                logger.warning("RunningHub binary upload failed | status=%s body=%s", resp.status_code, (resp.text or "")[:500])
                return None

            payload = resp.json() if resp.content else {}
            if not isinstance(payload, dict):
                return None

            code = payload.get("code")
            if code not in (0, "0", None):
                logger.warning("RunningHub binary upload rejected | code=%s message=%s", code, str(payload.get("message") or payload)[:300])
                return None

            data_block = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            download_url = str(data_block.get("download_url") or data_block.get("downloadUrl") or "").strip()
            if download_url.startswith(("http://", "https://")):
                return download_url
            return None
        except Exception as e:
            logger.warning("RunningHub binary upload exception | error=%s", str(e)[:300])
            return None

    def _resolve_runninghub_media_input(self, value: Any, api_key: str, base_url: str, media_kind: str = "image") -> Optional[str]:
        raw = str(value or "").strip()
        if not raw:
            return None
        if self._is_public_http_url(raw):
            if oss_storage_service.is_managed_url(raw):
                return str(oss_storage_service.refresh_url(raw) or raw)
            return raw

        uploaded_url = self._upload_runninghub_binary_ref(raw, api_key=api_key, base_url=base_url)
        if uploaded_url:
            return uploaded_url

        if str(media_kind or "").strip().lower() == "image":
            fallback = self._resolve_ref_for_api(raw, force_data_uri_for_local=True)
            return str(fallback or "").strip() or None

        return None

    async def _handle_runninghub_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None, ref_mode: Optional[str] = None):
        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            return {"error": "No RunningHub API Key"}

        tool_conf = config.get("config", {}) or {}
        base_url = str(config.get("base_url") or tool_conf.get("base_url") or "https://www.runninghub.cn").strip().rstrip("/")
        endpoint = str(tool_conf.get("endpoint") or "").strip()
        if not endpoint:
            return {"error": "RunningHub endpoint missing from system configuration", "submit_failed": True}

        try:
            resolved_setting_id = int((tool_conf or {}).get("__resolved_setting_id") or 0)
        except Exception:
            resolved_setting_id = 0
        runtime_enum_catalog = self._load_system_api_runtime_enum_catalog(resolved_setting_id) if resolved_setting_id > 0 else {}

        submit_url = endpoint if re.match(r"^https?://", endpoint, flags=re.IGNORECASE) else f"{base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
        query_endpoint = str(tool_conf.get("query_endpoint") or "/openapi/v2/query").strip() or "/openapi/v2/query"
        query_url = query_endpoint if re.match(r"^https?://", query_endpoint, flags=re.IGNORECASE) else f"{base_url}{query_endpoint if query_endpoint.startswith('/') else '/' + query_endpoint}"
        endpoint_lower = endpoint.lower()
        model_lower = str(config.get("model") or tool_conf.get("model") or "").strip().lower()

        raw_ref_values = ref_image if isinstance(ref_image, list) else [ref_image]
        image_refs: List[str] = []
        video_refs: List[str] = []
        for item in raw_ref_values:
            raw = str(item or "").strip()
            if not raw:
                continue
            media_kind = "video" if self._looks_like_video_media_ref(raw) else "image"
            resolved_value = await asyncio.to_thread(
                self._resolve_runninghub_media_input,
                raw,
                api_key,
                base_url,
                media_kind,
            )
            if not resolved_value:
                continue
            if media_kind == "video":
                video_refs.append(resolved_value)
            else:
                image_refs.append(resolved_value)

        def _normalize_bool(raw: Any, default: bool) -> bool:
            if raw is None:
                return default
            if isinstance(raw, bool):
                return raw
            text = str(raw).strip().lower()
            if text in {"1", "true", "yes", "y", "on"}:
                return True
            if text in {"0", "false", "no", "n", "off"}:
                return False
            return default

        def _set_if_present(payload: Dict[str, Any], key: str, value: Any):
            if value is None:
                return
            if isinstance(value, str) and not value.strip():
                return
            payload[key] = value

        def _normalize_duration_value(raw: Any, default: int = 5) -> str:
            try:
                return str(int(raw or default))
            except Exception:
                return str(default)

        def _normalize_duration_int(raw: Any, default: Optional[int] = None) -> Optional[int]:
            if raw is None:
                return default
            text = str(raw).strip().lower()
            if not text:
                return default
            text = re.sub(r"[^0-9.]+$", "", text)
            try:
                return int(float(text))
            except Exception:
                return default

        def _pick_tool_value(*keys: str) -> Any:
            for key in keys:
                if key in tool_conf and tool_conf.get(key) is not None:
                    return tool_conf.get(key)
                if key in config and config.get(key) is not None:
                    return config.get(key)
            return None

        configured_video_refs = _pick_tool_value("reference_video_urls", "ref_video_urls")
        for item in (configured_video_refs if isinstance(configured_video_refs, list) else [configured_video_refs]):
            raw = str(item or "").strip()
            if not raw:
                continue
            resolved_video = await asyncio.to_thread(
                self._resolve_runninghub_media_input,
                raw,
                api_key,
                base_url,
                "video",
            )
            if resolved_video:
                video_refs.append(resolved_video)
        if image_refs:
            image_refs = list(dict.fromkeys(image_refs))
        if video_refs:
            video_refs = list(dict.fromkeys(video_refs))
        resolved_last_frame = await asyncio.to_thread(
            self._resolve_runninghub_media_input,
            last_frame_url,
            api_key,
            base_url,
            "image",
        )

        def _is_runninghub_vidu_video_endpoint() -> bool:
            return "/vidu/" in endpoint_lower or endpoint_lower.startswith("vidu") or "vidu" in model_lower

        def _runninghub_video_duration_allowed_values() -> List[int]:
            endpoint_rules = [
                ("/openapi/v2/kling-video-o1/image-to-video", [5, 10]),
                ("/openapi/v2/kling-video-o1/start-to-end", [5, 10]),
                ("/openapi/v2/kling-video-o1/text-to-video", [5, 10]),
                ("/openapi/v2/kling-video-o1-std/refrence-to-video", [5, 10]),
                ("/openapi/v2/kling-v2.5-turbo-pro/image-to-video", [5, 10]),
                ("/openapi/v2/kling-v2.5-turbo-pro/text-to-video", [5, 10]),
                ("/openapi/v2/kling-v2.5-turbo-std/image-to-video", [5, 10]),
                ("/openapi/v2/kling-v2.6-pro/image-to-video", [5, 10]),
                ("/openapi/v2/kling-v2.6-pro/text-to-video", [5, 10]),
                ("/openapi/v2/kling-v3.0-pro/image-to-video", [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                ("/openapi/v2/kling-v3.0-pro/text-to-video", [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                ("/openapi/v2/kling-v3.0-std/image-to-video", [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                ("/openapi/v2/kling-v3.0-std/text-to-video", [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                ("/openapi/v2/seedance-v1.5-pro/", [4, 5, 6, 7, 8, 9, 10, 11, 12]),
                ("/openapi/v2/seedance-v1-lite/", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]),
                ("/openapi/v2/rhart-video/sparkvideo", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                ("/openapi/v2/rhart-video/sparkvideo-2.0-fast/multimodal-video", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                ("/openapi/v2/rhart-video/sparkvideo-2.0/multimodal-video", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
            ]

            for endpoint_token, values in endpoint_rules:
                if endpoint_token in endpoint_lower:
                    return self._normalize_duration_enum_values(values)

            return self._normalize_duration_enum_values(
                runtime_enum_catalog.get("durations_seconds") if isinstance(runtime_enum_catalog, dict) else None
            )

        def _is_runninghub_seedance_video_endpoint() -> bool:
            haystack = f"{endpoint_lower} {model_lower}"
            return "seedance" in haystack

        def _runninghub_video_primary_image_field() -> str:
            # Seedance / Kling / Runway / Hailuo / Youchuan i2v all require firstImageUrl.
            if "luma" in endpoint_lower and "image-to-video" in endpoint_lower:
                return "imageUrl"
            if "/openapi/v2/rhart-video" in endpoint_lower:
                return "firstFrameUrl"
            if (
                "image-to-video" in endpoint_lower
                or "start-end-to-video" in endpoint_lower
                or "start-to-end" in endpoint_lower
                or _is_runninghub_seedance_video_endpoint()
            ):
                return "firstImageUrl"
            return "imageUrl"

        def _normalize_runninghub_video_duration(raw_value: Any, default_value: Any = 5) -> Optional[str]:
            requested_duration = _normalize_duration_int(raw_value, None)
            if requested_duration is None:
                requested_duration = _normalize_duration_int(default_value, 5)

            allowed_values = _runninghub_video_duration_allowed_values()
            if requested_duration is None:
                requested_duration = allowed_values[0] if allowed_values else 5

            if allowed_values:
                mapped_duration = self._map_duration_nearest(requested_duration, allowed_values)
                if mapped_duration is not None:
                    return str(int(mapped_duration))

            return _normalize_duration_value(requested_duration, 5)

        def _runninghub_video_resolution_allowed_values() -> List[str]:
            runtime_values = self._normalize_str_list(runtime_enum_catalog.get("resolution") if isinstance(runtime_enum_catalog, dict) else None)
            if runtime_values:
                return runtime_values
            if "/openapi/v2/rhart-video" in endpoint_lower:
                return ["480p", "720p", "1080p", "2k", "4k"]
            if not _is_runninghub_vidu_video_endpoint():
                return []
            if "q2-pro-fast" in endpoint_lower:
                return ["720p", "1080p"]
            if "q2-pro" in endpoint_lower or "q3-pro" in endpoint_lower:
                return ["540p", "720p", "1080p"]
            return ["720p", "1080p"]

        def _normalize_runninghub_video_resolution(raw_value: Any, default_value: Optional[str] = None) -> Optional[str]:
            allowed_values = _runninghub_video_resolution_allowed_values()
            raw = str(raw_value or "").strip()
            if not raw:
                raw = str(default_value or "").strip()
            if not raw:
                return None
            if not allowed_values:
                return raw
            mapped = self._map_resolution_to_allowed(raw, allowed_values)
            return str(mapped or raw).strip() or None

        def _set_audio_flags(payload_obj: Dict[str, Any]):
            if _is_runninghub_vidu_video_endpoint():
                if _pick_tool_value("audio") is not None:
                    payload_obj["audio"] = _normalize_bool(_pick_tool_value("audio"), True)
                elif _pick_tool_value("sound") is not None:
                    payload_obj["audio"] = _normalize_bool(_pick_tool_value("sound"), True)
                elif _pick_tool_value("generateAudio") is not None:
                    payload_obj["audio"] = _normalize_bool(_pick_tool_value("generateAudio"), False)
                elif _pick_tool_value("bgm") is not None:
                    payload_obj["audio"] = _normalize_bool(_pick_tool_value("bgm"), True)
                else:
                    payload_obj["audio"] = True
            else:
                if _is_runninghub_seedance_video_endpoint():
                    av = _pick_tool_value("generateAudio", "audio", "sound")
                    payload_obj["generateAudio"] = "true" if _normalize_bool(av, True) else "false"
                elif "/openapi/v2/rhart-video/sparkvideo" in endpoint_lower:
                    av = _pick_tool_value("generateAudio") or _pick_tool_value("audio") or _pick_tool_value("sound")
                    if av is not None:
                        payload_obj["generateAudio"] = True
                elif _pick_tool_value("generateAudio") is not None:
                    payload_obj["generateAudio"] = True
                elif _pick_tool_value("audio") is not None:
                    payload_obj["audio"] = True
                elif _pick_tool_value("sound") is not None:
                    payload_obj["sound"] = True
                elif _pick_tool_value("bgm") is not None:
                    payload_obj["bgm"] = _normalize_bool(_pick_tool_value("bgm"), True)

            if _pick_tool_value("keepOriginalSound") is not None:
                payload_obj["keepOriginalSound"] = _normalize_bool(_pick_tool_value("keepOriginalSound"), True)

        def _is_runninghub_hailuo_video_endpoint() -> bool:
            haystack = f"{endpoint_lower} {model_lower}"
            return "hailuo" in haystack or "minimax" in haystack

        def _set_runninghub_prompt_expansion_flag(payload_obj: Dict[str, Any]):
            explicit_value = _pick_tool_value(
                "enablePromptExpansion",
                "enable_prompt_expansion",
                "promptExpansion",
                "prompt_expand",
                "promptExtend",
                "prompt_extend",
            )
            if explicit_value is not None:
                payload_obj["enablePromptExpansion"] = _normalize_bool(explicit_value, True)
                return
            if _is_runninghub_hailuo_video_endpoint():
                payload_obj["enablePromptExpansion"] = True

        raw_callback_url = str(
            tool_conf.get("_provider_callback_url")
            or tool_conf.get("webhookUrl")
            or tool_conf.get("webHook")
            or tool_conf.get("webhook")
            or tool_conf.get("callBackUrl")
            or tool_conf.get("callback_url")
            or tool_conf.get("callbackUrl")
            or ""
        ).strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"runninghub-{gen_type}"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url:
            callback_tool_conf.setdefault("webhookUrl", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"})
        if callback_url and callback_url != raw_callback_url:
            logger.info(
                "RunningHub callback auto-assigned | gen_type=%s ticket=%s callback_url=%s raw_callback=%s",
                gen_type,
                callback_ticket,
                callback_url,
                raw_callback_url or None,
            )
        elif callback_url == "-1":
            logger.info(
                "RunningHub callback disabled | gen_type=%s raw_callback=%s public_hint=%s",
                gen_type,
                raw_callback_url or None,
                self._is_public_deployment_hint(),
            )

        base_metadata = {
            "provider": "runninghub",
            "model": config.get("model") or "runninghub-model",
            "prompt": prompt,
            "submit_url": submit_url,
            "query_url": query_url,
            "endpoint": endpoint,
        }

        logger.info("RunningHub payload building... Ref Mode: %s | Endpoint: %s | Images: %s", ref_mode, endpoint, len(image_refs))

        if gen_type == "image":
            payload: Dict[str, Any] = {"prompt": prompt}

            if callback_url and callback_url != "-1":
                payload["webhookUrl"] = callback_url
            is_image_edit = any(token in endpoint_lower for token in ("image-to-image", "/edit", "image-edit"))

            if is_image_edit:
                if not image_refs:
                    return {"error": "RunningHub image edit requires at least one reference image input", "submit_failed": True}
                payload["imageUrls"] = image_refs[:3]
            elif image_refs and "youchuan/" in endpoint_lower:
                payload["imageUrl"] = image_refs[0]

            _set_if_present(payload, "negativePrompt", str(negative_prompt or "").strip() or None)

            normalized_image_size = self._normalize_image_size_value(image_size or _pick_tool_value("image_size", "imageSize"))
            explicit_size = _pick_tool_value("size")
            explicit_resolution = _pick_tool_value("resolution")
            explicit_aspect_ratio = self._normalize_aspect_ratio_value(_pick_tool_value("aspectRatio", "aspect_ratio") or aspect_ratio)
            allowed_resolution_values = self._get_runninghub_image_resolution_allowed_values(
                endpoint_lower,
                runtime_enum_catalog.get("resolution") if isinstance(runtime_enum_catalog, dict) else None,
            )
            allowed_aspect_ratio_values = self._get_runninghub_image_aspect_ratio_allowed_values(
                endpoint_lower,
                runtime_enum_catalog.get("aspect_ratio") if isinstance(runtime_enum_catalog, dict) else None,
            )

            if explicit_size is not None:
                payload["size"] = str(explicit_size).strip()
            elif normalized_image_size and any(token in endpoint_lower for token in ("qwen-image", "rhart-image-g-1.5", "rhart-image-g/")):
                payload["size"] = normalized_image_size
            if explicit_resolution is not None:
                requested_resolution = str(explicit_resolution).strip()
                if allowed_resolution_values:
                    mapped_resolution = self._map_resolution_to_allowed(requested_resolution, allowed_resolution_values)
                    if mapped_resolution:
                        payload["resolution"] = str(mapped_resolution).strip().lower()
                elif requested_resolution:
                    payload["resolution"] = requested_resolution
            elif normalized_image_size and normalized_image_size.lower() in {"1k", "2k", "3k", "4k", "8k"} and allowed_resolution_values:
                mapped_resolution = self._map_resolution_to_allowed(normalized_image_size.lower(), allowed_resolution_values)
                if mapped_resolution:
                    payload["resolution"] = str(mapped_resolution).strip().lower()
            if explicit_aspect_ratio and "size" not in payload and allowed_aspect_ratio_values:
                mapped_aspect_ratio = self._map_aspect_ratio_to_allowed(explicit_aspect_ratio, allowed_aspect_ratio_values)
                if mapped_aspect_ratio:
                    payload["aspectRatio"] = str(mapped_aspect_ratio).strip()

            # Enforce resolution if endpoint explicitly requires it
            if allowed_resolution_values and "resolution" not in payload:
                payload["resolution"] = str(allowed_resolution_values[0])
            
            # Enforce aspectRatio if endpoint explicitly requires it
            if allowed_aspect_ratio_values and "aspectRatio" not in payload and "size" not in payload and "resolution" not in payload:
                payload["aspectRatio"] = str(allowed_aspect_ratio_values[0])

            if "resolution" not in payload and "size" not in payload and "aspectRatio" not in payload:
                if any(token in endpoint_lower for token in ("seedream", "rhart-image-n", "ultra")):
                    payload["resolution"] = "1k"
                elif "g-1.5" in endpoint_lower or "v1" in endpoint_lower:
                    payload["aspectRatio"] = "16:9"
                else:
                    payload["resolution"] = "1k" # Safe fallback for resolution if empty

            for key in ["quality", "inputFidelity", "imageNum", "promptExtend", "sequentialImageGeneration", "maxImages", "toolsType", "chaos", "stylize", "weird", "raw", "iw", "sw", "sv", "model"]:
                _set_if_present(payload, key, _pick_tool_value(key))

            if "model" not in payload:
                supplier_runninghub = ((config.get("supplier_info") or {}).get("runninghub") or {}) if isinstance(config.get("supplier_info"), dict) else {}
                configured_base_model = str(config.get("base_model") or supplier_runninghub.get("base_model") or "").strip().lower()
                configured_model_slug = str(config.get("model") or supplier_runninghub.get("model_slug") or "").strip().lower()
                if "/rhart-image-g/" in endpoint_lower or configured_base_model == "rhart-image-g" or configured_model_slug.startswith("rhart-image-g-"):
                    payload["model"] = "g-4.2"

            if _pick_tool_value("sref") is not None:
                _set_if_present(payload, "sref", _pick_tool_value("sref"))
            elif len(image_refs) > 1:
                payload["sref"] = image_refs[1]

            base_metadata.update({
                "resolution": payload.get("resolution"),
                "aspectRatio": payload.get("aspectRatio"),
                "size": payload.get("size"),
            })

            logger.info(f"[RunningHub] Image Payload: {_format_payload_for_log(payload)}")
            return await self._submit_and_poll_runninghub(
                submit_url,
                query_url,
                payload,
                api_key,
                "RunningHubImage",
                extra_metadata=base_metadata,
                provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
            )

        if gen_type == "audio":
            if "voice-clone" in endpoint_lower:
                return {"error": "RunningHub voice-clone requires a reference audio sample; current voice entrypoint does not provide one", "submit_failed": True}

            payload = {"text": prompt}
            if callback_url and callback_url != "-1":
                payload["webhookUrl"] = callback_url
            _set_if_present(payload, "voice_id", _pick_tool_value("voice_id", "voiceId", "voice"))
            _set_if_present(payload, "emotion", _pick_tool_value("emotion"))
            _set_if_present(payload, "speed", _pick_tool_value("speed"))
            _set_if_present(payload, "volume", _pick_tool_value("volume"))
            _set_if_present(payload, "pitch", _pick_tool_value("pitch"))
            _set_if_present(payload, "pronunciation_dict", _pick_tool_value("pronunciation_dict"))
            payload["enable_base64_output"] = _normalize_bool(_pick_tool_value("enable_base64_output"), False)
            if _pick_tool_value("english_normalization") is not None:
                payload["english_normalization"] = _normalize_bool(_pick_tool_value("english_normalization"), False)

            logger.info(f"[RunningHub] Audio Payload: {_format_payload_for_log(payload)}")
            return await self._submit_and_poll_runninghub(
                submit_url,
                query_url,
                payload,
                api_key,
                "RunningHubAudio",
                extra_metadata=base_metadata,
                provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
            )

        if gen_type != "video":
            return {"error": f"RunningHub generation type not supported: {gen_type}", "submit_failed": True}

        payload: Dict[str, Any] = {}
        _set_if_present(payload, "prompt", prompt)
        _set_if_present(payload, "negativePrompt", str(negative_prompt or "").strip() or None)
        _set_if_present(payload, "seed", _pick_tool_value("seed", "seeds"))
        if callback_url and callback_url != "-1":
            payload["webhookUrl"] = callback_url

        explicit_duration = _pick_tool_value("duration")
        explicit_resolution = _pick_tool_value("resolution")
        explicit_aspect_ratio = _pick_tool_value("aspectRatio", "aspect_ratio") or aspect_ratio
        explicit_size = _pick_tool_value("size")
        movement_amplitude = str(_pick_tool_value("movementAmplitude", "movement_amplitude", "motion_amplitude") or "").strip() or None
        if not movement_amplitude and _is_runninghub_vidu_video_endpoint():
            movement_amplitude = "auto"
            
        is_draft = _normalize_bool(_pick_tool_value("draft_mode", "draft"), False)
        if is_draft:
            if "doubao-seedance-2" in model_lower and len(image_refs) > 0:
                pass
            else:
                payload["draft"] = True
            if "sparkvideo" in submit_url.lower() and "fast" not in submit_url.lower():
                submit_url = re.sub(
                    r"/sparkvideo-2\.0(?=/|$)",
                    "/sparkvideo-2.0-fast",
                    submit_url,
                    flags=re.IGNORECASE,
                )
                submit_url = re.sub(
                    r"/sparkvideo(?=/|$)",
                    "/sparkvideo-2.0-fast",
                    submit_url,
                    flags=re.IGNORECASE,
                )
                endpoint_lower = submit_url.lower()

        normalized_video_duration = _normalize_runninghub_video_duration(explicit_duration, duration)
        default_video_resolution = "480p" if is_draft else "720p"
        normalized_video_resolution = _normalize_runninghub_video_resolution(explicit_resolution, default_video_resolution)
        if is_draft:
            normalized_video_resolution = _normalize_runninghub_video_resolution("480p", "480p") or "480p"

        if "video-edit" in endpoint_lower or "edit-video" in endpoint_lower or "video-extend" in endpoint_lower:
            source_video = video_refs[0] if video_refs else None
            if not source_video:
                return {"error": "RunningHub video-edit/video-extend requires a source video input; current request did not include one", "submit_failed": True}
            if "video-extend" in endpoint_lower:
                payload["video"] = source_video
            else:
                payload["videoUrl"] = source_video
            if image_refs:
                payload["imageUrls"] = image_refs[:3]
            _set_if_present(payload, "resolution", normalized_video_resolution)
            _set_audio_flags(payload)
        elif "reference-to-video" in endpoint_lower:
            if not image_refs and not video_refs:
                return {"error": "RunningHub reference-to-video requires reference images or videos", "submit_failed": True}
            if image_refs:
                payload["imageUrls"] = image_refs[:3]
            if video_refs:
                if "/alibaba/wan-" in endpoint_lower:
                    payload["videoUrls"] = video_refs[:3]
                elif "/vidu/" in endpoint_lower and "-q2-pro" in endpoint_lower:
                    payload["videos"] = video_refs[:3]
                elif len(video_refs) > 1:
                    payload["videoUrls"] = video_refs[:3]
                else:
                    payload["videoUrl"] = video_refs[0]
            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution)
            if _is_runninghub_seedance_video_endpoint():
                payload["aspectRatio"] = str(explicit_aspect_ratio or "").strip() or "16:9"
            else:
                _set_if_present(payload, "aspectRatio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            _set_if_present(payload, "size", str(explicit_size).strip() if explicit_size is not None else None)
            camera_fixed = _pick_tool_value("cameraFixed")
            if _is_runninghub_seedance_video_endpoint():
                payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"
            else:
                payload["cameraFixed"] = _normalize_bool(camera_fixed, False)
            _set_audio_flags(payload)
        elif "multimodal-video" in endpoint_lower:
            payload["imageUrls"] = image_refs[:9]
            if video_refs:
                payload["videoUrls"] = video_refs[:3]
            else:
                payload["videoUrls"] = []
                
            audio_refs = _pick_tool_value("audioUrls") or []
            if isinstance(audio_refs, str): audio_refs = [audio_refs]
            payload["audioUrls"] = audio_refs[:3]
            
            payload["duration"] = str(normalized_video_duration) if normalized_video_duration else "5"
            _set_if_present(payload, "resolution", normalized_video_resolution or "720p")
            _set_if_present(payload, "ratio", "adaptive" if not explicit_aspect_ratio else str(explicit_aspect_ratio).strip())
            _set_if_present(payload, "realPersonMode", True)
            payload["conversionSlots"] = ["all"]
            payload["returnLastFrame"] = False
            
            _set_audio_flags(payload)
        elif "start-end-to-video" in endpoint_lower or "start-to-end" in endpoint_lower:
            first_image = image_refs[0] if image_refs else None
            # Only casually grab the second image if the API endpoint inherently expects two keyframes AND we actually got two images
            # Do not grab it for start-to-end generic tasks unless the user explicitly provided two references meant to be first & last
            last_image = resolved_last_frame
            if not last_image and len(image_refs) >= 2:
                # To prevent confusing multi-character entity references as an end frame, 
                # we map it only if there are exactly 2 images, or if we confidently know this mode. 
                if len(image_refs) == 2:
                    last_image = image_refs[1]
            
            if not first_image:
                return {"error": "RunningHub start-end video requires a first-frame image input", "submit_failed": True}
            if "/rhart-video-" in endpoint_lower:
                payload["firstFrameUrl"] = first_image
                if last_image:
                    payload["lastFrameUrl"] = last_image
            else:
                payload["firstImageUrl"] = first_image
                if last_image:
                    payload["lastImageUrl"] = last_image
            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution)
            _set_if_present(payload, "aspectRatio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            _set_if_present(payload, "mode", _pick_tool_value("mode"))
            _set_if_present(payload, "movementAmplitude", movement_amplitude)
            _set_audio_flags(payload)
        elif "text-to-video" in endpoint_lower:
            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution)
            if _is_runninghub_seedance_video_endpoint():
                payload["aspectRatio"] = str(explicit_aspect_ratio or "").strip() or "16:9"
            else:
                _set_if_present(payload, "aspectRatio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            _set_if_present(payload, "size", str(explicit_size).strip() if explicit_size is not None else None)
            
            camera_fixed = _pick_tool_value("cameraFixed")
            if _is_runninghub_seedance_video_endpoint():
                payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"
            else:
                payload["cameraFixed"] = _normalize_bool(camera_fixed, False)
                    
            _set_audio_flags(payload)
        else:
            first_image = image_refs[0] if image_refs else None
            if not first_image:
                return {"error": "RunningHub image-to-video requires a reference image input", "submit_failed": True}
            
            primary_field = _runninghub_video_primary_image_field()
            is_seedance_i2v = _is_runninghub_seedance_video_endpoint() and "image-to-video" in endpoint_lower
            
            if is_seedance_i2v:
                # Seedance i2v contract: firstImageUrl (required) + optional lastImageUrl.
                # Do not send imageUrls — upstream rejects empty/missing firstImageUrl.
                payload["firstImageUrl"] = first_image
                if resolved_last_frame:
                    payload["lastImageUrl"] = resolved_last_frame
                elif len(image_refs) == 2:
                    payload["lastImageUrl"] = image_refs[1]
            elif ref_mode == "entity_refs":
                if "/openapi/v2/rhart-video" in endpoint_lower and "/multimodal-video" not in endpoint_lower:
                    if "sparkvideo" in submit_url.lower():
                        submit_url = submit_url.replace("/image-to-video", "/multimodal-video")
                        endpoint_lower = submit_url.lower()

                unique_refs = []
                seen = set()
                for x in image_refs:
                    base = x.split('?')[0]
                    if base not in seen:
                        seen.add(base)
                        unique_refs.append(x)
                
                payload["imageUrls"] = unique_refs
                # 实体参考图模式下，如果是多模态接口不传单图属性（如 firstFrameUrl 等）避免报错
                if primary_field not in ["imageUrls"] and "/multimodal-video" not in endpoint_lower:
                    payload[primary_field] = first_image
            else:
                payload[primary_field] = first_image

                if "/openapi/v2/rhart-video" not in endpoint_lower:
                    if primary_field != "imageUrls":
                        payload["imageUrls"] = image_refs[:3]
                    
                    # Prevent setting the second reference image as the 'lastImageUrl' by default
                    # unless it's a specific Vidu generation parameter or start-end mode.
                    # This avoids poisoning the last frame generation with e.g. character mapping images.
                    pass
            if not is_seedance_i2v:
                if resolved_last_frame and ("/openapi/v2/rhart-video/sparkvideo" in endpoint_lower):
                    payload["lastFrameUrl"] = resolved_last_frame
                elif resolved_last_frame and "/rhart-video-" in endpoint_lower:
                    payload["lastImageUrl"] = resolved_last_frame
                elif resolved_last_frame:
                    payload["lastImageUrl"] = resolved_last_frame

            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution or "720p")
            
            if "/openapi/v2/rhart-video" in endpoint_lower:
                _set_if_present(payload, "ratio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
                _set_if_present(payload, "realPersonMode", True)
            elif is_seedance_i2v or _is_runninghub_seedance_video_endpoint():
                # Seedance requires aspectRatio; i2v default is adaptive.
                seedance_ar = str(explicit_aspect_ratio or "").strip() or ("adaptive" if is_seedance_i2v else "16:9")
                payload["aspectRatio"] = seedance_ar
            else:
                _set_if_present(payload, "aspectRatio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            
            _set_if_present(payload, "movementAmplitude", movement_amplitude)
            
            camera_fixed = _pick_tool_value("cameraFixed")
            if _is_runninghub_seedance_video_endpoint():
                payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"
            else:
                payload["cameraFixed"] = _normalize_bool(camera_fixed, False)
                    
            _set_audio_flags(payload)

        _set_runninghub_prompt_expansion_flag(payload)

        base_metadata.update({
            "duration": payload.get("duration"),
            "resolution": payload.get("resolution"),
            "aspectRatio": payload.get("aspectRatio"),
            "size": payload.get("size"),
        })

        print(f"\n========== RUNNINGHUB VIDEO PAYLOAD DEBUG ==========")
        print(f"ref_mode: {ref_mode}")
        print(f"endpoint: {endpoint}")
        print(f"payload: {payload}")
        print(f"======================================================\n")

        logger.info(f"[RunningHub] Video Payload: {_format_payload_for_log(payload)}")
        return await self._submit_and_poll_runninghub(
            submit_url,
            query_url,
            payload,
            api_key,
            "RunningHub",
            extra_metadata=base_metadata,
            pure_callback_mode=pure_callback_mode,
            callback_enabled=callback_enabled,
            callback_ticket=callback_ticket,
            callback_url=callback_url,
            provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
        )

    async def _handle_apiyi_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        provider_name = self._vendor_label(config.get("provider") or ((config.get("config") or {}).get("provider")) or "apiyi")
        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            return {"error": f"No {provider_name} API Key", "submit_failed": True}

        tool_conf = config.get("config", {}) or {}
        raw_callback_url = str(tool_conf.get("_provider_callback_url") or tool_conf.get("webhookUrl") or tool_conf.get("webHook") or tool_conf.get("webhook") or tool_conf.get("callBackUrl") or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or "").strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"apiyi-{gen_type}"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url: callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        base_url = str(config.get("base_url") or "https://api.apiyi.com").strip().rstrip("/")
        endpoint = str(tool_conf.get("endpoint") or tool_conf.get("endpoint_hint") or "").strip()
        model = str(config.get("model") or "").strip()
        
        provider_key = str(provider_name).strip().lower()
        if not endpoint:
            if provider_key == "aiclub":
                if gen_type == "image":
                    endpoint = "/v1/images/generations"
                elif gen_type == "video":
                    endpoint = "/v1/videos"
                else:
                    return {"error": f"{provider_name} generation type not supported by default endpoint injection", "submit_failed": True}
            else:
                return {"error": f"{provider_name} endpoint missing from system configuration", "submit_failed": True}

        submit_url = endpoint if re.match(r"^https?://", endpoint, flags=re.IGNORECASE) else f"{base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"

        def _sanitize_video_prompt_if_needed(raw_prompt: Any, raw_negative_prompt: Optional[str] = None, resolved_model_name: Optional[str] = None) -> str:
            merged_prompt = self._merge_negative_prompt(raw_prompt, raw_negative_prompt)
            model_name = str(resolved_model_name or model or "").strip().lower()
            if not model_name.startswith("sora"):
                return merged_prompt
            sanitized_prompt = self._sanitize_sora_prompt_mentions(merged_prompt)
            if sanitized_prompt and sanitized_prompt != str(merged_prompt or ""):
                logger.warning(
                    "APIYI Sora prompt mention sanitizer applied | model=%s removed_at_mentions=%s",
                    resolved_model_name or model,
                    str(merged_prompt or "").count("@"),
                )
            return sanitized_prompt

        if gen_type == "image":
            # Native Google API Format for APIYI Image models
            if "gemini" in model.lower():
                submit_url = f"{base_url}/v1beta/models/{model}:generateContent"
                
                image_config = {}
                resolved_aspect_ratio = aspect_ratio or tool_conf.get("aspect_ratio")
                if resolved_aspect_ratio:
                    image_config["aspectRatio"] = resolved_aspect_ratio
                
                normalized_image_size = self._normalize_image_size_value(
                    image_size or tool_conf.get("image_size") or tool_conf.get("imageSize")
                )
                if normalized_image_size == "2k":
                    image_config["imageSize"] = "2K"
                elif normalized_image_size == "1k":
                     image_config["imageSize"] = "1K"
                elif normalized_image_size == "512":
                     image_config["imageSize"] = "256" # not sure if supported, but whatever
                     
                prompt_text = self._merge_negative_prompt(prompt, negative_prompt)
                parts = []
                final_contents = []

                if prompt and prompt.startswith("GEMINI_BATCH::"):
                    try:
                        batch_data = json.loads(prompt[14:])
                        for item in batch_data:
                            item_text = self._merge_negative_prompt(item.get("text", ""), negative_prompt)
                            item_parts = [{"text": item_text}]
                            item_ref = item.get("ref")
                            if item_ref:
                                data_uri = await self._get_image_base64_for_api_async(item_ref, force_data_uri=True)
                                if isinstance(data_uri, str) and data_uri.startswith("data:image/"):
                                    idx = data_uri.find(";base64,")
                                    if idx > 5:
                                        mime = data_uri[5:idx].strip().lower() or "image/png"
                                        item_parts.append({
                                            "inline_data": {
                                                "mime_type": mime,
                                                "data": data_uri[idx + len(";base64,"):].strip(),
                                            }
                                        })
                            # Append directly as parts inside the main object, since multiple results come from single content with multiple inputs, OR single part
                            # According to instruction, "数组功能" implies putting all prompts/images in one request part array or multiple parts
                            parts.extend(item_parts)
                        final_contents = [{"role": "user", "parts": parts}]
                    except Exception as e:
                        _debug_log(f"[n1n_gemini_image] Failed to parse GEMINI_BATCH: {e}")
                        final_contents = [{"role": "user", "parts": [{"text": prompt_text}]}]
                else:
                    parts = [{"text": prompt_text}]
                    reference_values = ref_image if isinstance(ref_image, list) else [ref_image]
                    for ref_item in reference_values:
                        if ref_item is None:
                            continue
                        if isinstance(ref_item, str) and not ref_item.strip():
                            continue
                        data_uri = await self._get_image_base64_for_api_async(ref_item, force_data_uri=True)
                        if isinstance(data_uri, str) and data_uri.startswith("data:image/"):
                            idx = data_uri.find(";base64,")
                            if idx > 5:
                                mime = data_uri[5:idx].strip().lower() or "image/png"
                                parts.append({
                                    "inline_data": {
                                        "mime_type": mime,
                                        "data": data_uri[idx + len(";base64,"):].strip(),
                                    }
                                })
                    final_contents = [{"role": "user", "parts": parts}]
                if config.get("is_gemini_multi_turn_edit"):
                    base_prompt = config.get("gemini_base_prompt") or prompt_text
                    edit_instruction = config.get("gemini_edit_instruction") or prompt_text
                    inline_parts = [p for p in parts if "inline_data" in p]
                    if inline_parts:
                        final_contents = [
                            {"role": "user", "parts": [{"text": base_prompt}]},
                            {"role": "model", "parts": inline_parts},
                            {"role": "user", "parts": [{"text": edit_instruction}]}
                        ]

                payload = {
                     "contents": final_contents,
                     "generationConfig": {
                         "responseModalities": ["IMAGE"],
                     }
                }
                if image_config:
                    payload["generationConfig"]["imageConfig"] = image_config

                if config.get("has_google_search") or tool_conf.get("has_google_search"):
                    payload["tools"] = [{"google_search": {}}]

                if config.get("has_thinking_mode") or tool_conf.get("has_thinking_mode"):
                    think_level = str(config.get("thinking_level") or tool_conf.get("thinking_level") or "high").lower()
                    if think_level not in ["minimal", "high"]: think_level = "high"
                    payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": think_level, "includeThoughts": True}

                if callback_url and callback_url != "-1":
                    payload["webhookUrl"] = callback_url
                    
                base_metadata = {
                    "provider": provider_name,
                    "model": model,
                    "prompt": prompt,
                    "submit_url": submit_url,
                    "endpoint_family": "gemini-native",
                }
                
                # We need special handling for the response since it returns base64
                res = await self._common_requests_post(
                    submit_url,
                    payload,
                    api_key,
                    f"{str(provider_name).lower()}_image_gemini",
                    extra_metadata=base_metadata,
                    provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
                )
                
                # Check for base64 inlineData in response
                if isinstance(res, dict) and not res.get("error"):
                    try:
                        raw_data = res.get("metadata", {}).get("raw", {})
                        if "candidates" in raw_data:
                            # Handle multiple images when batching
                            out_parts = raw_data["candidates"][0]["content"]["parts"]
                            urls = []
                            for p in out_parts:
                                if "inlineData" in p:
                                    b64_data = p["inlineData"]["data"]
                                    if b64_data:
                                        urls.append(f"data:image/png;base64,{b64_data}")
                            
                            if len(urls) > 1:
                                # For batch array feature, we return multiple URLs joined by a sentinel delimiter
                                # Which will be split by the frontend.
                                logger.info(f"[{provider_name}_gemini_image] 批处理模式：收到了 {len(urls)} 张图片的返回结果。")
                                res["url"] = "|||".join(urls)
                            elif len(urls) == 1:
                                logger.info(f"[{provider_name}_gemini_image] 标准模式：只收到了 1 张图片的返回结果。")
                                res["url"] = urls[0]
                            elif len(out_parts) > 0 and "inlineData" in out_parts[0]:
                                b64_data = out_parts[0]["inlineData"]["data"]
                                if b64_data:
                                    logger.info(f"[{provider_name}_gemini_image] 标准模式：只收到了 1 张图片的返回结果(out_parts[0])。")
                                    res["url"] = f"data:image/png;base64,{b64_data}"
                            else:
                                logger.warning(f"[{provider_name}_gemini_image] 警告：没有从返回的 payload 中解析到符合条件的图片。")
                    except Exception as e:
                        logger.error(f"[{provider_name}_gemini_image] 无法解析 base64 响应内容: {e}")
                return res

            # Fallback to OpenAI compatible for non-gemini apiyi image models if any (or we replace entirely)
            endpoint_lower = endpoint.lower()
            if "/v1/images/generations" not in endpoint_lower:
                return {"error": f"{provider_name} image endpoint family not supported yet: {endpoint}", "submit_failed": True}

            normalized_image_size = self._normalize_image_size_value(
                image_size or tool_conf.get("image_size") or tool_conf.get("imageSize")
            )
            size_value = self._resolve_openai_compatible_image_size(
                model=model,
                explicit_size=tool_conf.get("size"),
                normalized_image_size=normalized_image_size,
                aspect_ratio=aspect_ratio,
            )

            payload = {
                "model": model,
                "prompt": self._merge_negative_prompt(prompt, negative_prompt),
                "n": int(tool_conf.get("n") or 1),
                "size": str(size_value),
            }
            resolved_refs = self._resolve_ref_list_for_api(
                ref_image,
                force_data_uri_for_local=True,
                prefer_public_upload_url=True,
                data_uri_profile="n1n_image_ref",
            ) if ref_image else []
            if resolved_refs:
                payload["image_urls"] = resolved_refs
                payload["imageUrls"] = resolved_refs
                payload["filesUrl"] = resolved_refs[:5]
                if len(resolved_refs) == 1:
                    payload["fileUrl"] = resolved_refs[0]
                mask_url_candidate = str(tool_conf.get("maskUrl") or tool_conf.get("mask_url") or "").strip()
                if mask_url_candidate:
                    payload["maskUrl"] = mask_url_candidate
            if str(provider_name).strip().lower() != "n1n":
                payload["response_format"] = str(tool_conf.get("response_format") or "url")
            for optional_key in ["quality", "output_format", "output_compression", "background", "user"]:
                if tool_conf.get(optional_key) is not None:
                    payload[optional_key] = tool_conf.get(optional_key)

            if callback_url and callback_url != "-1":
                payload["webhookUrl"] = callback_url

            base_metadata = {
                "provider": provider_name,
                "model": model,
                "prompt": prompt,
                "submit_url": submit_url,
                "endpoint_family": "/v1/images/generations",
            }
            return await self._common_requests_post(
                submit_url,
                payload,
                api_key,
                f"{str(provider_name).lower()}_image",
                extra_metadata=base_metadata,
                provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
            )

        if gen_type == "video":
            endpoint_lower = endpoint.lower()
            if "/v1/chat/completions" in endpoint_lower:
                if last_frame_url:
                    return {"error": f"{provider_name} chat/completions video does not support last-frame control", "submit_failed": True}

                resolved_model = self._resolve_apiyi_chat_video_model(model, aspect_ratio=aspect_ratio, duration=duration)
                resolved_refs = self._resolve_ref_list_for_api(
                    ref_image,
                    force_data_uri_for_local=True,
                    prefer_public_upload_url=True,
                ) if ref_image else []
                content_payload: List[Dict[str, Any]] = []
                merged_prompt = _sanitize_video_prompt_if_needed(prompt, negative_prompt, resolved_model)
                if merged_prompt:
                    content_payload.append({"type": "text", "text": merged_prompt})
                if resolved_refs:
                    content_payload.append({
                        "type": "image_url",
                        "image_url": {"url": resolved_refs[0]},
                    })

                payload = {
                    "model": resolved_model,
                    "stream": True,
                    "messages": [{
                        "role": "user",
                        "content": content_payload,
                    }],
                }
                base_metadata = {
                    "provider": provider_name,
                    "model": resolved_model,
                    "requested_model": model,
                    "prompt": prompt,
                    "submit_url": submit_url,
                    "endpoint_family": "/v1/chat/completions",
                    "requested_duration": int(duration or 0),
                    "requested_aspect_ratio": str(aspect_ratio or "").strip() or None,
                    "resolved_reference_count": len(resolved_refs),
                    "resolved_video_size": self._apiyi_chat_video_size_for_model(resolved_model),
                }
                return await self._submit_apiyi_chat_video_stream(
                    submit_url,
                    payload,
                    api_key,
                    f"{str(provider_name).lower()}_video",
                    extra_metadata=base_metadata,
                    provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
                )
            elif "/v1/videos" not in endpoint_lower:
                return {"error": f"{provider_name} video endpoint family not supported yet: {endpoint}", "submit_failed": True}

            video_resolution = str(tool_conf.get("resolution") or ("480p" if self._normalize_bool_value(tool_conf.get("draft_mode") or tool_conf.get("draft")) else "720p")).strip()
            payload = {
                "model": model,
                "prompt": _sanitize_video_prompt_if_needed(prompt, negative_prompt, model),
                "seconds": str(int(duration or tool_conf.get("seconds") or 4)),
                "size": str(tool_conf.get("size") or ("854x480" if video_resolution == "480p" else "1280x720")),
            }
            if aspect_ratio and not tool_conf.get("size"):
                size_map = {
                    "16:9": "854x480" if video_resolution == "480p" else "1280x720",
                    "9:16": "480x854" if video_resolution == "480p" else "720x1280",
                }
                payload["size"] = size_map.get(str(aspect_ratio).strip(), payload["size"])

            # APIYI /v1/videos: Handle reference images specifically for kling models
            model_lower = model.lower()

            if "kling" in model_lower and (ref_image or last_frame_url):
                resolved_refs = self._resolve_ref_list_for_api(
                    ref_image,
                    force_data_uri_for_local=True,
                    prefer_public_upload_url=True,
                ) if ref_image else []
                
                payload["input"] = {
                    "prompt": payload.get("prompt"),
                    "duration": int(payload.get("seconds") or 5)
                }
                if resolved_refs:
                    payload["input"]["image_urls"] = resolved_refs
                
                if last_frame_url:
                    last_frame_resolved = self._resolve_ref_list_for_api(
                        last_frame_url, 
                        force_data_uri_for_local=True, 
                        prefer_public_upload_url=True
                    )
                    if last_frame_resolved:
                        current_urls = payload["input"].get("image_urls", [])
                        if last_frame_resolved[0] not in current_urls:
                            current_urls.append(last_frame_resolved[0])
                        payload["input"]["image_urls"] = current_urls
                
                payload.pop("prompt", None)
                payload.pop("seconds", None)
                payload.pop("size", None)
            else:
                # non-fl models are text-to-video only by default — silently
                # ignore any reference image the caller passes through.  For -fl models
                # the async API requires multipart upload which is not implemented yet.
                is_frame_model = model_lower.endswith("-fl") or "-fl-" in model_lower
                if is_frame_model and (ref_image or last_frame_url):
                    return {"error": f"{provider_name} /v1/videos frame-to-video (multipart upload) is not enabled yet in media service", "submit_failed": True}
                # For non-fl models, just drop the ref images
                if not is_frame_model:
                    ref_image = None
                    last_frame_url = None

            base_metadata = {
                "provider": provider_name,
                "model": model,
                "prompt": prompt,
                "submit_url": submit_url,
                "endpoint_family": "/v1/videos",
                "seconds": payload.get("seconds"),
                "size": payload.get("size"),
            }
            callback_enabled = bool(callback_url and callback_url != "-1")
            pure_callback_mode = bool(
                str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"}
            )
            if callback_enabled:
                payload["webhookUrl"] = callback_url
                payload["callback_url"] = callback_url
            return await self._submit_and_poll_video(
                submit_url,
                payload,
                api_key,
                f"{str(provider_name).lower()}_video",
                extra_metadata=base_metadata,
                pure_callback_mode=pure_callback_mode,
                callback_enabled=callback_enabled,
                callback_ticket=callback_ticket,
                callback_url=callback_url,
                provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
            )

        return {"error": f"{provider_name} generation type not supported: {gen_type}", "submit_failed": True}

    async def _handle_pixelmove_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None):
        if str(gen_type or "").strip().lower() != "video":
            return {"error": "Pixelmove currently supports video generation only", "submit_failed": True}

        api_key = str(config.get("api_key") or config.get("clientApiKey") or "").strip()
        tool_conf = config.get("config", {}) or {}
        tenant_id = str(
            tool_conf.get("tenant_id")
            or tool_conf.get("tenantId")
            or tool_conf.get("x_tenant_id")
            or config.get("tenant_id")
            or config.get("tenantId")
            or ""
        ).strip()

        if not api_key:
            return {"error": "No Pixelmove clientApiKey", "submit_failed": True}
        if not tenant_id:
            return {"error": "No Pixelmove tenantId", "submit_failed": True}

        raw_callback_url = str(
            tool_conf.get("_provider_callback_url")
            or tool_conf.get("callback_url")
            or tool_conf.get("callbackUrl")
            or tool_conf.get("callBackUrl")
            or tool_conf.get("webHook")
            or ""
        ).strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or "pixelmove-video"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url:
            callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"})
        callback_payload_field = str(tool_conf.get("callback_field") or "callback_url").strip() or "callback_url"
        if callback_url and callback_url != raw_callback_url:
            logger.info(
                "Pixelmove callback auto-assigned | ticket=%s callback_url=%s raw_callback=%s",
                callback_ticket,
                callback_url,
                raw_callback_url or None,
            )

        base_url = str(config.get("base_url") or tool_conf.get("base_url") or "https://portal.pixelmove.ai").strip().rstrip("/")
        endpoint = str(tool_conf.get("endpoint") or f"{base_url}/api/v1/bytedance/seedance-2.0").strip() or f"{base_url}/api/v1/bytedance/seedance-2.0"

        prompt_text = self._merge_negative_prompt(prompt, negative_prompt)

        allowed_duration_values = self._normalize_duration_enum_values(
            tool_conf.get("durations_seconds")
            or tool_conf.get("duration_values")
            or tool_conf.get("allowed_durations")
            or [5, 8, 10]
        )
        try:
            duration_in = int(float(duration or tool_conf.get("duration") or 5))
        except Exception:
            duration_in = 5
        is_seedance2_model = self._is_seedance2_base_model(
            config.get("base_model") or tool_conf.get("base_model"),
        )
        if duration_in <= 0 and not (is_seedance2_model and duration_in == -1):
            duration_in = 5
        if allowed_duration_values and not (is_seedance2_model and duration_in == -1):
            mapped_duration = self._map_duration_nearest(duration_in, allowed_duration_values, prefer_higher_on_tie=False)
            if mapped_duration is not None:
                duration_in = int(mapped_duration)

        is_draft_mode = self._normalize_bool_value(tool_conf.get("draft_mode") or tool_conf.get("draft"))
        resolution = str(tool_conf.get("resolution") or ("480p" if is_draft_mode else "720p")).strip() or ("480p" if is_draft_mode else "720p")
        normalized_ratio = self._normalize_aspect_ratio_value(aspect_ratio or tool_conf.get("ratio"))
        if not normalized_ratio or normalized_ratio == "adaptive":
            normalized_ratio = "16:9"

        generate_audio = bool(self._normalize_bool_value(tool_conf.get("generate_audio"))) if tool_conf.get("generate_audio") is not None else False
        try:
            seed = int(tool_conf.get("seed")) if tool_conf.get("seed") is not None else -1
        except Exception:
            seed = -1

        image_refs = self._resolve_ref_list_for_api(
            ref_image,
            force_data_uri_for_local=True,
            prefer_public_upload_url=True,
        )
        image_refs = [u for u in image_refs if self._is_public_http_url(u)]

        extra_image_refs = self._resolve_ref_list_for_api(
            tool_conf.get("referenceImageUrls") or tool_conf.get("reference_image_urls") or [],
            force_data_uri_for_local=True,
            prefer_public_upload_url=True,
        )
        for item in extra_image_refs:
            if self._is_public_http_url(item) and item not in image_refs:
                image_refs.append(item)

        video_refs = self._normalize_str_list(tool_conf.get("referenceVideoUrls") or tool_conf.get("reference_video_urls"))
        video_refs = [u for u in video_refs if self._is_public_http_url(u)]

        audio_refs = self._normalize_str_list(tool_conf.get("referenceAudioUrls") or tool_conf.get("reference_audio_urls"))
        audio_refs = [u for u in audio_refs if self._is_public_http_url(u)]

        payload: Dict[str, Any] = {
            "prompt": prompt_text,
            "duration": int(duration_in),
            "resolution": resolution,
            "ratio": normalized_ratio,
            "generate_audio": generate_audio,
            "seed": seed,
        }
        if callback_enabled:
            payload[callback_payload_field] = callback_url

        last_frame_resolved = self._resolve_ref_for_api(
            last_frame_url,
            force_data_uri_for_local=True,
            prefer_public_upload_url=True,
        ) if last_frame_url else None
        if last_frame_resolved and not self._is_public_http_url(last_frame_resolved):
            last_frame_resolved = None

        first_frame = image_refs[0] if image_refs else None
        if first_frame and last_frame_resolved:
            payload["frame_mode"] = "first-last"
            payload["first_image"] = first_frame
            payload["last_image"] = last_frame_resolved
        else:
            if image_refs:
                payload["referenceImageUrls"] = image_refs
            if video_refs:
                payload["referenceVideoUrls"] = video_refs
            if audio_refs:
                payload["referenceAudioUrls"] = audio_refs

        poll_timeout_seconds = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS
        poll_interval_seconds = 2
        try:
            if tool_conf.get("poll_timeout_seconds") is not None:
                poll_timeout_seconds = min(900, max(60, int(tool_conf.get("poll_timeout_seconds"))))
        except Exception:
            poll_timeout_seconds = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS
        try:
            if tool_conf.get("poll_interval_seconds") is not None:
                poll_interval_seconds = max(1, int(tool_conf.get("poll_interval_seconds")))
        except Exception:
            poll_interval_seconds = 2

        base_metadata = {
            "provider": "pixelmove",
            "model": str(config.get("model") or "seedance-2.0").strip() or "seedance-2.0",
            "prompt": prompt_text,
            "submit_url": endpoint,
            "tenant_id": tenant_id,
            "payload_mode": "first-last" if payload.get("frame_mode") == "first-last" else "multi-reference",
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Tenant-Id": tenant_id,
            "Content-Type": "application/json",
        }

        def _extract_task_id(data: Any) -> Optional[str]:
            if isinstance(data, dict):
                for key in ("taskId", "task_id", "id"):
                    val = data.get(key)
                    if val:
                        return str(val).strip()
                inner = data.get("data") if isinstance(data.get("data"), dict) else {}
                for key in ("taskId", "task_id", "id"):
                    val = inner.get(key)
                    if val:
                        return str(val).strip()
            return None

        def _extract_result_url(data: Any) -> Optional[str]:
            if not isinstance(data, dict):
                return None
            inner = data.get("data") if isinstance(data.get("data"), dict) else {}
            output = inner.get("output") if isinstance(inner.get("output"), dict) else {}
            result = inner.get("result") if isinstance(inner.get("result"), dict) else {}
            candidates = [
                data.get("url"),
                data.get("video_url"),
                data.get("resultUrl"),
                data.get("result_url"),
                inner.get("url"),
                inner.get("video_url"),
                inner.get("resultUrl"),
                inner.get("result_url"),
                output.get("url"),
                output.get("video_url"),
                output.get("resultUrl"),
                output.get("result_url"),
                result.get("url"),
                result.get("video_url"),
                result.get("resultUrl"),
                result.get("result_url"),
            ]
            for item in candidates:
                text_item = str(item or "").strip()
                if text_item.startswith(("http://", "https://")):
                    return text_item
            for coll_name in ("urls", "videoUrls", "video_urls", "results", "outputs"):
                coll = data.get(coll_name) or inner.get(coll_name) or output.get(coll_name)
                if isinstance(coll, list) and coll:
                    first = coll[0]
                    if isinstance(first, str) and first.startswith(("http://", "https://")):
                        return first
                    if isinstance(first, dict):
                        nested = str(first.get("url") or first.get("video_url") or first.get("resultUrl") or "").strip()
                        if nested.startswith(("http://", "https://")):
                            return nested
            return None

        def _extract_status(data: Any) -> str:
            if not isinstance(data, dict):
                return ""
            inner = data.get("data") if isinstance(data.get("data"), dict) else {}
            output = inner.get("output") if isinstance(inner.get("output"), dict) else {}
            raw_status = data.get("status") or data.get("state") or inner.get("status") or inner.get("state") or output.get("status")
            return str(raw_status or "").strip().lower()

        headers["X-Request-Id"] = str(uuid.uuid4())
        submit_resp = await asyncio.to_thread(
            requests.post,
            endpoint,
            json=payload,
            headers=headers,
            timeout=_media_submit_timeout_pair(),
            verify=False,
        )

        submit_data: Dict[str, Any] = {}
        if submit_resp.text:
            try:
                parsed_submit = submit_resp.json()
                submit_data = parsed_submit if isinstance(parsed_submit, dict) else {}
            except Exception:
                submit_data = {}

        task_id = _extract_task_id(submit_data)
        if submit_resp.status_code == 409:
            duplicate_code = str(submit_data.get("code") or submit_data.get("errorCode") or submit_data.get("message") or "").upper()
            is_duplicate_request_id = "DUPLICATE_REQUEST_ID" in duplicate_code
            if not is_duplicate_request_id:
                return {
                    "error": f"Pixelmove submit failed 409: {submit_resp.text}",
                    "submit_failed": True,
                    "details": submit_data or submit_resp.text,
                }
            if not task_id:
                headers["X-Request-Id"] = str(uuid.uuid4())
                submit_resp_retry = await asyncio.to_thread(
                    requests.post,
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=_media_submit_timeout_pair(),
                    verify=False,
                )
                if submit_resp_retry.status_code not in [200, 201, 202]:
                    return {
                        "error": f"Pixelmove submit failed after DUPLICATE_REQUEST_ID retry: {submit_resp_retry.status_code}",
                        "submit_failed": True,
                        "details": (submit_resp_retry.text or "")[:1000],
                    }
                try:
                    retry_data = submit_resp_retry.json() if submit_resp_retry.text else {}
                    submit_data = retry_data if isinstance(retry_data, dict) else {}
                except Exception:
                    submit_data = {}
                task_id = _extract_task_id(submit_data)
        elif submit_resp.status_code not in [200, 201, 202]:
            return {
                "error": f"Pixelmove submit failed {submit_resp.status_code}",
                "submit_failed": True,
                "details": (submit_resp.text or "")[:1000],
            }

        if not task_id:
            direct_url = _extract_result_url(submit_data)
            if direct_url:
                return {"url": direct_url, "metadata": {**base_metadata, "raw": submit_data}}
            return {
                "error": "Pixelmove submit succeeded but task id missing",
                "submit_failed": True,
                "details": submit_data,
            }

        if pure_callback_mode and callback_enabled:
            logger.info(
                "Pixelmove pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s",
                task_id,
                callback_ticket,
                callback_url,
            )
            pending_meta = dict(base_metadata)
            pending_meta.update(
                {
                    "raw": submit_data,
                    "submit_raw": submit_data,
                    "task_id": str(task_id),
                    "taskId": str(task_id),
                    "pending_callback": True,
                    "callback_ticket": callback_ticket,
                    "callback_url": callback_url,
                }
            )
            return {
                "pending_callback": True,
                "provider_task_id": str(task_id),
                "metadata": pending_meta,
            }

        poll_template = str(tool_conf.get("poll_endpoint") or f"{endpoint.rstrip('/')}/tasks/{{taskId}}")
        poll_url = poll_template.replace("{taskId}", urllib.parse.quote(task_id)).replace("{task_id}", urllib.parse.quote(task_id))

        max_attempts = max(1, int(poll_timeout_seconds / max(1, poll_interval_seconds)))
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(poll_interval_seconds)
            poll_headers = dict(headers)
            poll_headers["X-Request-Id"] = str(uuid.uuid4())
            try:
                poll_resp = await asyncio.to_thread(
                    requests.get,
                    poll_url,
                    headers=poll_headers,
                    timeout=30,
                    verify=False,
                )
            except requests.exceptions.Timeout:
                continue
            except Exception:
                if attempt == max_attempts:
                    return {"error": "Pixelmove polling exception", "submit_failed": False}
                continue

            if poll_resp.status_code not in [200, 201]:
                if poll_resp.status_code == 404:
                    continue
                if attempt == max_attempts:
                    return {
                        "error": f"Pixelmove polling failed {poll_resp.status_code}",
                        "submit_failed": False,
                        "details": (poll_resp.text or "")[:1000],
                    }
                continue

            try:
                poll_data = poll_resp.json() if poll_resp.text else {}
            except Exception:
                poll_data = {}

            status_val = _extract_status(poll_data)
            result_url = _extract_result_url(poll_data)

            if result_url and status_val in {"", "success", "succeeded", "completed", "done", "finished"}:
                return {"url": result_url, "metadata": {**base_metadata, "raw": poll_data, "task_id": task_id}}

            if status_val in {"success", "succeeded", "completed", "done", "finished"}:
                if result_url:
                    return {"url": result_url, "metadata": {**base_metadata, "raw": poll_data, "task_id": task_id}}
                return {
                    "error": "Pixelmove generation completed without URL",
                    "submit_failed": False,
                    "details": poll_data,
                }

            if status_val in {"failed", "error", "cancelled", "canceled", "rejected"}:
                return {
                    "error": "Pixelmove generation failed",
                    "submit_failed": False,
                    "details": poll_data,
                }

        return {"error": f"Pixelmove polling timeout after {poll_timeout_seconds}s", "submit_failed": False}

    async def _handle_aiclub_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        provider_name = self._vendor_label(config.get("provider") or ((config.get("config") or {}).get("provider")) or "aiclub")
        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            return {"error": f"No {provider_name} API Key", "submit_failed": True}

        tool_conf = config.get("config", {}) or {}
        raw_callback_url = str(tool_conf.get("_provider_callback_url") or tool_conf.get("webhookUrl") or tool_conf.get("webHook") or tool_conf.get("webhook") or tool_conf.get("callBackUrl") or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or "").strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"aiclub-{gen_type}"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url: callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"})
        base_url = str(config.get("base_url") or "https://aiclub.zimaocloud.com/model/openApi").strip().rstrip("/")
        model = str(config.get("model") or "nanoBanana").strip()
        
        # Depending on base_url format (some might be just domain, some might include path)
        if "/model/openApi" in base_url and not base_url.endswith("/v1"):
            pass
        elif base_url.endswith("/v1"):
            base_url = base_url[:-3].rstrip("/") # remove /v1

        model_lower = model.lower()
        if "gemini" in model_lower:
            route_group = "nanoBanana"
            submit_url = f"{base_url}/{route_group}/v1/{model}"
            poll_base = f"{base_url}/{route_group}/v1"
        elif "veo" in model_lower and gen_type == "video":
            submit_url = f"{base_url}/veo/v1/video"
            poll_base = f"{base_url}/veo/v1"
        elif "kling" in model_lower and gen_type == "video":
            path = "image2video" if (ref_image or last_frame_url) else "text2video"
            submit_url = f"{base_url}/kling/v1/videos/{path}"
            poll_base = f"{base_url}/kling/v1"
        elif "hailuo" in model_lower and gen_type == "video":
            path = "image2video" if (ref_image or last_frame_url) else "text2video"
            submit_url = f"{base_url}/hailuo/v1/videos/{path}"
            poll_base = f"{base_url}/hailuo/v1"
        elif "vidu" in model_lower and gen_type == "video":
            path = "image2video" if (ref_image or last_frame_url) else "text2video"
            submit_url = f"{base_url}/vidu/v1/videos/{path}"
            poll_base = f"{base_url}/vidu/v1"
        elif "sora" in model_lower and gen_type == "video":
            submit_url = f"{base_url}/sora/v1/video"
            poll_base = f"{base_url}/sora/v1"
        elif "jimeng" in model_lower and gen_type == "video":
            submit_url = f"{base_url}/jimeng/v1/video"
            poll_base = f"{base_url}/jimeng/v1"
        else:
            submit_url = f"{base_url}/{model}/v1/"
            poll_base = f"{base_url}/{model}/v1"

        resolved_ref_image = None
        resolved_last_frame = None
        if gen_type == "video":
            if ref_image:
                resolved_ref_image = await self._resolve_ref_for_api_async(
                    ref_image,
                    force_data_uri_for_local=True,
                    prefer_public_upload_url=True,
                )
            if last_frame_url:
                resolved_last_frame = await self._resolve_ref_for_api_async(
                    last_frame_url,
                    force_data_uri_for_local=True,
                    prefer_public_upload_url=True,
                )

        video_resolution = str(tool_conf.get("resolution") or ("480p" if self._normalize_bool_value(tool_conf.get("draft_mode") or tool_conf.get("draft")) else "720p")).strip()
        if "veo" in model_lower and gen_type == "video":
            payload = {
                "model": model,
                "prompt": prompt,
                "negativePrompt": negative_prompt or "",
                "aspectRatio": str(aspect_ratio or "9:16").strip(),
                "durationSeconds": str(duration or 6),
                "resolution": video_resolution,
                "generateAudio": False,
                "personGeneration": "allow_adult"
            }
            if resolved_ref_image:
                payload["image"] = {"imageUrl": resolved_ref_image}
            if resolved_last_frame:
                payload["lastFrame"] = {"imageUrl": resolved_last_frame}
        elif any(k in model_lower for k in ["kling", "hailuo", "vidu", "sora", "jimeng"]) and gen_type == "video":
            payload = {
                "model": model,
                "prompt": prompt,
                "resolution": video_resolution,
            }
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt
                
            # For endpoints needing reference images
            if resolved_ref_image:
                payload["image_url"] = resolved_ref_image
            if resolved_last_frame:
                payload["last_frame_url"] = resolved_last_frame
        else:
            payload = {
                "prompt": self._merge_negative_prompt(prompt, negative_prompt)
            }
            if gen_type == "image":
                payload["type"] = "TEXTTOIAMGE"
                size_map = {
                    "16:9": "16:9",
                    "9:16": "9:16",
                    "1:1": "1:1",
                    "4:3": "4:3",
                    "3:4": "3:4"
                }
                ar_key = str(aspect_ratio or "").strip()
                payload["image_size"] = size_map.get(ar_key, "9:16")
                payload["resolution"] = str(image_size or "2K").strip()
            elif gen_type == "video":
                payload["type"] = "TEXTTOVIDEO"
                payload["resolution"] = video_resolution
                
        if callback_url and callback_url != "-1":
            payload["webhook_url"] = callback_url
            payload["webhookUrl"] = callback_url
            payload["callback_url"] = callback_url
            payload["notify_url"] = callback_url

        base_metadata = {
            "provider": provider_name,
            "model": model,
            "prompt": prompt,
            "submit_url": submit_url,
        }

        import logging
        logging.getLogger(__name__).info(f"[AICLUB DEBUG] provider={provider_name} model={model} gen_type={gen_type} submit_url={submit_url} payload={payload}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            resp = await asyncio.to_thread(
                requests.post,
                submit_url,
                json=payload,
                headers=headers,
                timeout=_media_submit_timeout_pair(),
                verify=False,
            )
            data = resp.json() if resp.text else {}
            if resp.status_code not in [200, 201]:
                return {"error": f"Submission Failed {resp.status_code}", "details": data, "submit_failed": True}
        except Exception as e:
            return {"error": f"Submission Exception: {e}", "submit_failed": True}

        if isinstance(data, dict):
            if "url" in data:
                return {"url": data["url"], "metadata": base_metadata}
            elif "data" in data and isinstance(data["data"], dict) and "url" in data["data"]:
                return {"url": data["data"]["url"], "metadata": base_metadata}

        task_id = None
        if isinstance(data, dict):
            task_id = data.get("id") or data.get("task_id") or data.get("taskId")
            if not task_id and "data" in data and isinstance(data["data"], dict):
                inner = data["data"]
                task_id = inner.get("taskId") or inner.get("task_id") or inner.get("id")

        if not task_id:
            return {"error": f"No Task ID or URL returned: {data}", "submit_failed": True}

        if pure_callback_mode and callback_enabled and str(gen_type or "").strip().lower() in {"video", "image"}:
            logger.info(
                "AICLUB pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s gen_type=%s",
                task_id,
                callback_ticket,
                callback_url,
                gen_type,
            )
            pending_meta = dict(base_metadata)
            pending_meta.update(
                {
                    "raw": data,
                    "submit_raw": data,
                    "task_id": str(task_id),
                    "taskId": str(task_id),
                    "pending_callback": True,
                    "callback_ticket": callback_ticket,
                    "callback_url": callback_url,
                }
            )
            return {
                "pending_callback": True,
                "provider_task_id": str(task_id),
                "metadata": pending_meta,
            }

        poll_url = f"{poll_base}/tasks/{task_id}"

        for attempt in range(150):
            await asyncio.sleep(5)
            try:
                poll_resp = await asyncio.to_thread(requests.get, poll_url, headers=headers, timeout=30, verify=False)
                if poll_resp.status_code in [200, 201] and poll_resp.text:
                    polled_data = poll_resp.json()
                    status_val = None
                    result_url = None
                    
                    if isinstance(polled_data, dict):
                        inner = polled_data.get("data", {}) if isinstance(polled_data.get("data"), dict) else {}
                        info = inner.get("info", {}) if isinstance(inner.get("info"), dict) else {}
                        status_val = polled_data.get("status") or inner.get("status") or inner.get("taskStatus") or info.get("status") or polled_data.get("state")
                        print(f"[AIClub Polling] attempt={attempt} url={poll_url} data={polled_data}")
                        
                        url_candidates = [
                            polled_data.get("url"), inner.get("url"), info.get("url"),
                            inner.get("resultUrl"), polled_data.get("resultUrl"), info.get("resultUrl"),
                            inner.get("videoUrl"), polled_data.get("videoUrl"), info.get("videoUrl"),
                            inner.get("imageUrl"), polled_data.get("imageUrl"), info.get("imageUrl"),
                            polled_data.get("image_url"), inner.get("image_url"), info.get("image_url"),
                            polled_data.get("video_url"), inner.get("video_url"), info.get("video_url"),
                            info.get("resultImageUrl"), info.get("resultVideoUrl")
                        ]
                        result_url = next((u for u in url_candidates if isinstance(u, str) and u), None)
                        
                        if not result_url:
                            for coll in ["images", "videos", "results", "video_url"]:
                                items = inner.get(coll) or polled_data.get(coll) or info.get(coll) or []
                                if isinstance(items, list) and items:
                                    first = items[0]
                                    if isinstance(first, dict):
                                        result_url = first.get("url") or first.get("imageUrl") or first.get("videoUrl") or first.get("resultUrl")
                                    elif isinstance(first, str):
                                        result_url = first
                                    if result_url: break
                                    
                        if result_url and not status_val:
                            # For endpoints where no explicit success status is given, presence of URL indicates success
                            status_val = "SUCCESS"

                        if str(status_val).upper() in ["SUCCESS", "SUCCESSFUL", "COMPLETED", "200"]:
                            if result_url: return {"url": result_url, "metadata": base_metadata}
                            else: return {"error": f"No URL inside SUCCESS response: {polled_data}", "submit_failed": False}

                        if str(status_val).upper() in ["FAILED", "ERROR", "CANCELED", "CANCELLED"]:
                            err_msg = inner.get("reason") or inner.get("error") or polled_data.get("message") or "Unknown error"
                            return {"error": f"Generation failed: {err_msg}", "details": polled_data, "submit_failed": False}

            except Exception as pe:
                if attempt == 149: return {"error": f"Polling Exception: {pe}", "submit_failed": False}
                
        return {"error": "Polling Timeout", "submit_failed": False}

    def _extract_zlhub_task_id(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        if isinstance(value, dict):
            for key in ("task_id", "taskId", "id"):
                candidate = self._extract_zlhub_task_id(value.get(key))
                if candidate:
                    return candidate
            for key in ("data", "result"):
                candidate = self._extract_zlhub_task_id(value.get(key))
                if candidate:
                    return candidate
        if isinstance(value, list):
            for item in value:
                candidate = self._extract_zlhub_task_id(item)
                if candidate:
                    return candidate
        return None

    def _extract_zlhub_moderation_asset_ref(self, payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(payload, dict):
            return None

        items = payload.get("items")
        if not isinstance(items, list):
            for key in ("data", "result", "output"):
                nested = payload.get(key)
                if isinstance(nested, dict) and isinstance(nested.get("items"), list):
                    items = nested.get("items")
                    break

        if not isinstance(items, list) or not items:
            return None

        first_item = items[0] if isinstance(items[0], dict) else None
        if not isinstance(first_item, dict):
            return None

        asset_url = str(first_item.get("asset_url") or first_item.get("assetUrl") or "").strip()
        if asset_url:
            if re.match(r"^asset://", asset_url, flags=re.IGNORECASE):
                return asset_url
            if re.match(r"^https?://", asset_url, flags=re.IGNORECASE):
                return asset_url

        downstream_asset_id = str(first_item.get("downstream_asset_id") or first_item.get("downstreamAssetId") or "").strip()
        if downstream_asset_id:
            return f"asset://{downstream_asset_id}"

        for key in ("tos_url", "tosUrl", "downstream_final_url", "downstreamFinalUrl", "source_url", "sourceUrl"):
            candidate = str(first_item.get(key) or "").strip()
            if re.match(r"^https?://", candidate, flags=re.IGNORECASE):
                return candidate

        return None

    def _extract_zlhub_moderation_items(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []

        items = payload.get("items")
        if not isinstance(items, list):
            for key in ("data", "result", "output"):
                nested = payload.get(key)
                if isinstance(nested, dict) and isinstance(nested.get("items"), list):
                    items = nested.get("items")
                    break

        if not isinstance(items, list):
            return []

        normalized_items: List[Dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                normalized_items.append(item)
        return normalized_items

    def _parse_zlhub_moderation_item(self, item: Dict[str, Any], fallback_ref: str = "") -> Dict[str, Any]:
        approved_ref = self._extract_zlhub_moderation_asset_ref({"items": [item]}) or str(fallback_ref or "").strip()
        result = {
            "checked": True,
            "blocked": True,
            "status": "unknown_or_in_progress",
            "reason": None,
            "approved_ref": approved_ref,
            "raw": item or {},
        }

        try:
            if "submit_review_status" in item:
                submit_status = int(item.get("submit_review_status"))
                if submit_status != 1:
                    result["blocked"] = True
                    result["status"] = "submission_failed"
                    result["reason"] = "submit_review_status_not_1"
                    return result
        except Exception:
            pass

        status = str(
            item.get("status")
            or item.get("result")
            or item.get("verdict")
            or item.get("decision")
            or ""
        ).strip().lower()
        if status:
            result["status"] = status
            result["reason"] = str(item.get("reason") or item.get("message") or status)
            if status in {"pass", "passed", "approved", "allow", "allowed", "safe", "ok", "success", "compliant"}:
                result["blocked"] = False
                return result
            if status in {"block", "blocked", "reject", "rejected", "fail", "failed", "unsafe", "violation", "violated", "non_compliant"}:
                result["blocked"] = True
                return result
        elif item.get("submit_review_status") == 1:
            if item.get("asset_url") or item.get("image_url") or item.get("tos_url") or item.get("downstream_final_url"):
                result["status"] = "passed"
                result["blocked"] = False
                return result

        return result

    def _parse_zlhub_moderation_decision(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "blocked": True,
            "status": "unknown_or_in_progress",
            "reason": None,
            "raw": payload or {},
            "approved_ref": self._extract_zlhub_moderation_asset_ref(payload),
        }

        items = None
        if isinstance(payload, dict):
            raw_items = payload.get("items")
            if isinstance(raw_items, list):
                items = raw_items
            else:
                for key in ("data", "result", "output"):
                    nested = payload.get(key)
                    if isinstance(nested, dict) and isinstance(nested.get("items"), list):
                        items = nested.get("items")
                        break
        if isinstance(items, list) and items:
            statuses: List[int] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    statuses.append(int(item.get("submit_review_status")))
                except Exception:
                    continue
            if statuses:
                all_submitted = all(status == 1 for status in statuses)
                if not all_submitted:
                    result["blocked"] = True
                    result["status"] = "submission_failed"
                    result["reason"] = "submit_review_status_not_1"
                    return result

        containers: List[Any] = [payload]
        if isinstance(payload, dict):
            for key in ("data", "result", "moderation", "output"):
                if payload.get(key) is not None:
                    containers.append(payload.get(key))

        safe_statuses = {"pass", "passed", "approved", "allow", "allowed", "safe", "ok", "success", "compliant"}
        block_statuses = {"block", "blocked", "reject", "rejected", "fail", "failed", "unsafe", "violation", "violated", "non_compliant"}

        for container in containers:
            if not isinstance(container, dict):
                continue

            for key in ("blocked", "is_blocked", "flagged"):
                if key in container:
                    blocked = bool(container.get(key))
                    result["blocked"] = blocked
                    result["status"] = key
                    result["reason"] = str(container.get("reason") or container.get("message") or key)
                    return result

            for key in ("pass", "passed", "approved", "is_safe", "safe", "compliant"):
                if key in container:
                    allowed = bool(container.get(key))
                    result["blocked"] = not allowed
                    result["status"] = key
                    result["reason"] = str(container.get("reason") or container.get("message") or key)
                    return result

            status = str(
                container.get("status")
                or container.get("result")
                or container.get("verdict")
                or container.get("decision")
                or ""
            ).strip().lower()
            if status:
                result["status"] = status
                result["reason"] = str(container.get("reason") or container.get("message") or status)
                if status in safe_statuses:
                    result["blocked"] = False
                    return result
                if status in block_statuses:
                    result["blocked"] = True
                    return result

        return result

    def _resolve_zlhub_moderation_settings(self, config: Dict[str, Any]) -> Dict[str, Any]:
        outer = config if isinstance(config, dict) else {}
        tool_conf = self._safe_json_dict(outer.get("config"))

        resolved: Dict[str, Any] = {
            "moderation_enabled": bool(tool_conf.get("moderation_enabled", True)),
            "moderation_required": bool(tool_conf.get("moderation_required", True)),
            "moderation_endpoint": str(
                tool_conf.get("moderation_endpoint")
                or tool_conf.get("moderationEndpoint")
                or outer.get("moderation_endpoint")
                or outer.get("moderationEndpoint")
                or ""
            ).strip(),
            "moderation_user_id": str(
                tool_conf.get("moderation_user_id")
                or tool_conf.get("moderationUserId")
                or tool_conf.get("user_id")
                or tool_conf.get("userId")
                or outer.get("moderation_user_id")
                or outer.get("moderationUserId")
                or outer.get("user_id")
                or outer.get("userId")
                or ""
            ).strip(),
            "moderation_aes_key": str(
                tool_conf.get("moderation_aes_key")
                or tool_conf.get("moderationAesKey")
                or tool_conf.get("moderation_key")
                or tool_conf.get("moderationKey")
                or outer.get("moderation_aes_key")
                or outer.get("moderationAesKey")
                or outer.get("moderation_key")
                or outer.get("moderationKey")
                or ""
            ).strip(),
            "source": "current_config",
        }

        def _merge_candidate(candidate_cfg: Dict[str, Any], source: str) -> bool:
            if not isinstance(candidate_cfg, dict):
                return False
            changed = False
            for key in ("moderation_user_id", "moderation_aes_key", "moderation_endpoint"):
                if resolved.get(key):
                    continue
                raw_value = candidate_cfg.get(key)
                if raw_value is None and key == "moderation_user_id":
                    raw_value = candidate_cfg.get("moderationUserId") or candidate_cfg.get("user_id") or candidate_cfg.get("userId")
                if raw_value is None and key == "moderation_aes_key":
                    raw_value = candidate_cfg.get("moderationAesKey") or candidate_cfg.get("moderation_key") or candidate_cfg.get("moderationKey")
                if raw_value is None and key == "moderation_endpoint":
                    raw_value = candidate_cfg.get("moderationEndpoint")
                value = str(raw_value or "").strip()
                if value:
                    resolved[key] = value
                    changed = True
            if changed and source:
                resolved["source"] = source
            return changed

        if not resolved.get("moderation_user_id") or not resolved.get("moderation_aes_key"):
            provider_aliases = ["zlhub", "lzhbu", "zhonglian"]
            seen_ids: Set[int] = set()
            for provider_alias in provider_aliases:
                try:
                    with SessionLocal() as session:
                        rows = (
                            self._system_setting_query(session, provider=provider_alias)
                            .filter(SystemAPISetting.is_active == True)
                            .order_by(SystemAPISetting.id.desc())
                            .all()
                        )
                except Exception as exc:
                    logger.warning("zlhub moderation fallback lookup failed | provider=%s err=%s", provider_alias, exc)
                    continue

                for row in rows:
                    row_id = int(getattr(row, "id", 0) or 0)
                    if row_id > 0 and row_id in seen_ids:
                        continue
                    if row_id > 0:
                        seen_ids.add(row_id)
                    row_cfg = self._safe_json_dict(getattr(row, "config", None))
                    if not row_cfg:
                        continue
                    if _merge_candidate(row_cfg, f"system_setting:{row_id or provider_alias}"):
                        if resolved.get("moderation_user_id") and resolved.get("moderation_aes_key"):
                            break
                if resolved.get("moderation_user_id") and resolved.get("moderation_aes_key"):
                    break

        if not resolved.get("moderation_user_id"):
            resolved["moderation_user_id"] = str(
                os.getenv("ZLHUB_MODERATION_USER_ID")
                or os.getenv("LZHBU_MODERATION_USER_ID")
                or ""
            ).strip()
            if resolved.get("moderation_user_id"):
                resolved["source"] = "env"

        if not resolved.get("moderation_aes_key"):
            resolved["moderation_aes_key"] = str(
                os.getenv("ZLHUB_MODERATION_AES_KEY")
                or os.getenv("LZHBU_MODERATION_AES_KEY")
                or ""
            ).strip()
            if resolved.get("moderation_aes_key"):
                resolved["source"] = "env"

        if not resolved.get("moderation_endpoint"):
            resolved["moderation_endpoint"] = str(
                os.getenv("ZLHUB_MODERATION_ENDPOINT")
                or os.getenv("LZHBU_MODERATION_ENDPOINT")
                or ""
            ).strip()

        return resolved

    async def _maybe_moderate_zlhub_images(self, image_refs: List[Any], config: Dict[str, Any], roles: Optional[List[str]] = None) -> Dict[str, Any]:
        moderation_cfg = self._resolve_zlhub_moderation_settings(config)
        moderation_enabled = bool(moderation_cfg.get("moderation_enabled", True))
        if not moderation_enabled:
            return {"checked": False, "blocked": False, "reason": "disabled", "items": []}

        normalized_refs = [str(item or "").strip() for item in (image_refs or []) if str(item or "").strip()]
        if not normalized_refs:
            return {"checked": False, "blocked": False, "reason": "empty_ref", "items": []}

        normalized_roles = [str(item or "").strip() for item in (roles or [])]
        if len(normalized_roles) < len(normalized_refs):
            normalized_roles.extend([""] * (len(normalized_refs) - len(normalized_roles)))

        moderation_user_id = str(moderation_cfg.get("moderation_user_id") or "").strip()
        moderation_key = str(moderation_cfg.get("moderation_aes_key") or "").strip()
        moderation_required = bool(moderation_cfg.get("moderation_required", True))
        if not moderation_user_id or not moderation_key:
            if moderation_required:
                logger.warning(
                    "zlhub moderation credentials missing | provider=%s model=%s source=%s has_user_id=%s has_aes_key=%s",
                    config.get("provider"),
                    config.get("model"),
                    moderation_cfg.get("source"),
                    bool(moderation_user_id),
                    bool(moderation_key),
                )
                return {
                    "checked": False,
                    "blocked": True,
                    "error": "zlhub moderation credentials missing",
                    "submit_failed": True,
                    "items": [],
                }
            return {"checked": False, "blocked": False, "reason": "credentials_missing", "items": []}

        moderation_endpoint = self._normalize_zlhub_moderation_endpoint(
            moderation_cfg.get("moderation_endpoint")
        )
        
        # Determine asset type, default to Image (can be Video/Audio but here we only handle images currently)
        asset_type = "Image"
        # X-Track-Id based on V2 docs
        track_id = uuid.uuid4().hex
        
        business_payload: Dict[str, Any] = {
            "images": normalized_refs,
            "asset_type": asset_type
        }
        
        _key_str = str(moderation_key or "")
        _key_preview = f"{_key_str[:4]}...{_key_str[-4:]}" if len(_key_str) > 8 else "***"
        logger.info(f"[ZLHubModeration_Diag] Submit req: key_len={len(_key_str)} key_preview={_key_preview} assets={len(normalized_refs)} endpoint={moderation_endpoint}")

        request_payload = business_payload

        headers = {
            "Content-Type": "application/json", 
            "X-Access-Token": _key_str,
            "X-Track-Id": track_id
        }

        def _post_moderation(use_proxy: bool = True):
            kwargs = {
                "json": request_payload,
                "headers": headers,
                "timeout": (15, 60),
                "verify": False,
            }
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(moderation_endpoint, **kwargs)

        try:
            try:
                resp = await asyncio.to_thread(_post_moderation, True)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                resp = await asyncio.to_thread(_post_moderation, False)
        except requests.exceptions.RequestException as exc:
            return {
                "checked": False,
                "blocked": moderation_required,
                "error": f"zlhub moderation request failed: {exc}",
                "submit_failed": moderation_required,
                "items": [],
            }

        if resp.status_code not in (200, 202):
            return {
                "checked": False,
                "blocked": moderation_required,
                "error": f"zlhub moderation failed {resp.status_code}",
                "details": (resp.text or "")[:1000],
                "submit_failed": moderation_required,
                "items": [],
            }

        try:
            response_payload = resp.json() if resp.content else {}
        except Exception:
            response_payload = {}
        
        payload_dict = response_payload if isinstance(response_payload, dict) else {}

        if payload_dict.get("code") == 400 and "解密失败" in str(payload_dict.get("message", "")):
            return {
                "checked": True,
                "blocked": moderation_required,
                "status": "failed",
                "reason": "decryption_failed",
                "error": "zlhub moderation decrypt failed on server: " + str(payload_dict.get("message")),
                "submit_failed": moderation_required,
                "raw": payload_dict,
                "items": [],
            }

        overall = self._parse_zlhub_moderation_decision(payload_dict)
        raw_items = self._extract_zlhub_moderation_items(payload_dict)
        parsed_items: List[Dict[str, Any]] = []
        for idx, raw_ref in enumerate(normalized_refs):
            item_payload = raw_items[idx] if idx < len(raw_items) and isinstance(raw_items[idx], dict) else {}
            if not item_payload and overall.get("status") not in (None, "unknown_or_in_progress"):
                item_payload = {"status": overall.get("status"), "reason": overall.get("reason"), "blocked": overall.get("blocked")}
            item_result = self._parse_zlhub_moderation_item(item_payload, raw_ref)
            item_result.update({
                "role": normalized_roles[idx] if idx < len(normalized_roles) else "",
                "input_ref": _strip_query_from_log_url(raw_ref),
            })
            parsed_items.append(item_result)

        blocked = any(bool(item.get("blocked")) for item in parsed_items) if parsed_items else bool(overall.get("blocked"))
        pass_count = sum(1 for x in parsed_items if x.get("status") == "passed")
        unknown_count = sum(1 for x in parsed_items if x.get("status") not in ("passed", "blocked", "failed", "submission_failed"))
        block_count = sum(1 for x in parsed_items if x.get("blocked"))

        final_status = overall.get("status")
        if parsed_items and final_status in {None, "unknown_or_in_progress", "completed", "success", "done"}:
            if blocked:
                final_status = "blocked"
            elif pass_count == len(parsed_items):
                final_status = "passed"

        logger.info(f"[ZLHubModeration_Diag] Moderation finished | assets={len(normalized_refs)} passed={pass_count} blocked={block_count} unknown={unknown_count} overall={final_status} provider_code={payload_dict.get('code')}")
        return {
            "checked": True,
            "blocked": blocked,
            "status": final_status,
            "reason": overall.get("reason"),
            "raw": payload_dict,
            "items": parsed_items,
        }

    async def _maybe_moderate_zlhub_image(self, image_ref: Any, config: Dict[str, Any], role: str) -> Dict[str, Any]:
        resolved_ref = str(image_ref or "").strip()
        if not resolved_ref:
            return {"checked": False, "blocked": False, "reason": "empty_ref"}

        batch_result = await self._maybe_moderate_zlhub_images([resolved_ref], config, [role])
        items = batch_result.get("items") if isinstance(batch_result.get("items"), list) else []
        if items:
            first_item = dict(items[0] or {})
            if batch_result.get("error") and not first_item.get("error"):
                first_item["error"] = batch_result.get("error")
            if batch_result.get("details") is not None and first_item.get("details") is None:
                first_item["details"] = batch_result.get("details")
            if batch_result.get("submit_failed") and not first_item.get("submit_failed"):
                first_item["submit_failed"] = batch_result.get("submit_failed")
            return first_item
        return batch_result

    async def _handle_zlhub_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None, ref_mode: Optional[str] = None):
        if gen_type != "video":
            return {"error": "zlhub generation type not supported yet", "submit_failed": True}

        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            return {"error": "No zlhub API Key", "submit_failed": True}

        tool_conf = config.get("config", {}) or {}
        raw_callback_url = str(tool_conf.get("_provider_callback_url") or tool_conf.get("webhookUrl") or tool_conf.get("webHook") or tool_conf.get("webhook") or tool_conf.get("callBackUrl") or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or "").strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"zlhub-{gen_type}"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url: callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"})
        provider_name = self._vendor_label(config.get("provider") or tool_conf.get("provider") or "zlhub")
        base_url = str(config.get("base_url") or "https://api.zlhub.cn/v1").strip().rstrip("/")
        base_url = re.sub(r"https?://(?:[^/]*\.)?zlhub\.xiaowaiyou\.cn/zhonglian/api/v[0-9]+", "https://api.zlhub.cn/v1", base_url, flags=re.IGNORECASE)
        
        if "proxy/ark" in base_url.lower():
            # Handle specialized proxy paths
            base_url = re.sub(r"/proxy/ark/contents/generations(?:/tasks)?/?$", "", base_url, flags=re.IGNORECASE).rstrip("/")
        
        raw_endpoint = str(tool_conf.get("endpoint") or "").strip()
        if "proxy/ark" in raw_endpoint.lower():
            raw_endpoint = ""
        # Make sure that path begins with /
        if raw_endpoint and not raw_endpoint.startswith("/"):
            raw_endpoint = "/" + raw_endpoint
        endpoint = raw_endpoint or "/task/create"
        model = str(config.get("model") or "doubao-seedance-2-0").strip()
        model_lower = str(model or "").strip().lower()
        is_seedance2 = model_lower.startswith("doubao-seedance-2")
        zlhub_trace_id = f"zlhub-{uuid.uuid4().hex[:10]}"
        if re.match(r"^https?://", endpoint, flags=re.IGNORECASE):
            if "/proxy/chat/completions" in endpoint.lower():
                submit_url = re.sub(r"/proxy/chat/completions/?$", "/proxy/ark/contents/generations/tasks", endpoint, flags=re.IGNORECASE)
            elif "/api/v3" in endpoint.lower() or endpoint.lower().endswith("/contents/generations/tasks"):
                submit_url = self._normalize_doubao_video_tasks_endpoint(endpoint)
            else:
                submit_url = endpoint.rstrip("/")
        elif endpoint:
            normalized_relative_endpoint = endpoint
            if "/proxy/chat/completions" in normalized_relative_endpoint.lower():
                normalized_relative_endpoint = re.sub(r"/proxy/chat/completions/?$", "/proxy/ark/contents/generations/tasks", normalized_relative_endpoint, flags=re.IGNORECASE)
            submit_url = f"{base_url}{normalized_relative_endpoint if normalized_relative_endpoint.startswith('/') else '/' + normalized_relative_endpoint}"
        elif "/api/v3" in base_url.lower() or base_url.lower().endswith("/contents/generations/tasks"):
            submit_url = self._normalize_doubao_video_tasks_endpoint(base_url)
        else:
            submit_url = f"{base_url}/task/create"

        explicit_query_endpoint = str(tool_conf.get("query_endpoint") or tool_conf.get("queryEndpoint") or "").strip()
        if "proxy/ark" in explicit_query_endpoint.lower():
            explicit_query_endpoint = ""

        if not explicit_query_endpoint:
            if "/api/v3" in base_url.lower() or base_url.lower().endswith("/contents/generations/tasks"):
                query_endpoint = self._normalize_doubao_video_tasks_endpoint(base_url)
            else:
                query_endpoint = f"{base_url}/task/get/{{id}}"
        elif re.match(r"^https?://", explicit_query_endpoint, flags=re.IGNORECASE):
            if "/api/v3" in explicit_query_endpoint.lower() or explicit_query_endpoint.lower().endswith("/contents/generations/tasks"):
                query_endpoint = self._normalize_doubao_video_tasks_endpoint(explicit_query_endpoint)
            else:
                query_endpoint = explicit_query_endpoint.rstrip("/")
        elif "/api/v3" in base_url.lower() or base_url.lower().endswith("/contents/generations/tasks"):
            query_endpoint = self._normalize_doubao_video_tasks_endpoint(f"{base_url}/{explicit_query_endpoint.lstrip('/')}")
        else:
            query_endpoint = f"{base_url}/{explicit_query_endpoint.lstrip('/')}"
        
        if "{id}" not in query_endpoint and "{task_id}" not in query_endpoint and not query_endpoint.endswith("/tasks"):
            if query_endpoint.endswith("task/get"):
                query_endpoint = f"{query_endpoint}/{{id}}"
            elif not query_endpoint.endswith("/{id}"):
                query_endpoint = f"{query_endpoint}/{{id}}"

        prompt_text = self._merge_negative_prompt(prompt, negative_prompt)

        if is_seedance2:
            logger.info(
                "[ZLHubSeedance2] request_init | trace_id=%s gen_type=%s provider=%s model=%s submit_url=%s query_endpoint=%s duration_in=%s aspect_ratio_in=%s",
                zlhub_trace_id,
                gen_type,
                provider_name,
                model,
                submit_url,
                query_endpoint,
                duration,
                aspect_ratio,
            )

        raw_image_refs = self._collect_video_reference_image_urls(
            ref_image,
            tool_conf,
            extra_sources=config,
        )
        resolved_image_refs: List[str] = []
        for item in raw_image_refs:
            text = str(item or "").strip()
            if not text:
                continue
            resolved = await self._resolve_ref_for_api_async(
                text,
                force_data_uri_for_local=True,
                prefer_public_upload_url=True,
            )
            if resolved:
                resolved_image_refs.append(str(resolved).strip())
        resolved_image_refs = [item for item in dict.fromkeys(resolved_image_refs) if item]

        resolved_last_frame = None
        if str(last_frame_url or "").strip():
            resolved_last_frame = await self._resolve_ref_for_api_async(
                last_frame_url,
                force_data_uri_for_local=True,
                prefer_public_upload_url=True,
            )
            resolved_last_frame = str(resolved_last_frame or "").strip() or None

        reference_video_urls = self._resolve_public_media_urls(
            self._collect_video_reference_video_urls(tool_conf, extra_sources=config)
        )
        reference_audio_urls = self._resolve_public_media_urls(
            tool_conf.get("reference_audio_urls") or tool_conf.get("ref_audio_urls") or []
        )

        dropped_mixed_reference_counts = {
            "image": 0,
            "video": 0,
            "audio": 0,
        }

        seedance2_ref_mode = ""
        seedance2_payload_mode = ""
        if is_seedance2:
            raw_ref_mode = str(
                tool_conf.get("ref_mode")
                or tool_conf.get("video_ref_mode")
                or tool_conf.get("video_mode")
                or tool_conf.get("video_mode_unified")
                or ""
            ).strip().lower()

            if raw_ref_mode in {"refs_video", "entity_refs", "reference", "reference_images", "reference_image"}:
                seedance2_ref_mode = "entity_refs"
            elif raw_ref_mode in {"start_end", "start-end", "start+end", "first_last", "first_last_frame", "first_and_last"}:
                seedance2_ref_mode = "start_end"
            elif raw_ref_mode in {"end", "last", "last_frame"}:
                seedance2_ref_mode = "end"
            elif raw_ref_mode in {"start", "first", "first_frame", "auto"}:
                seedance2_ref_mode = "start"

            if not seedance2_ref_mode:
                if resolved_last_frame:
                    seedance2_ref_mode = "start_end"
                elif len(resolved_image_refs) > 1 or reference_video_urls or reference_audio_urls:
                    seedance2_ref_mode = "entity_refs"
                elif resolved_image_refs:
                    seedance2_ref_mode = "entity_refs"
                else:
                    seedance2_ref_mode = "entity_refs"

            seedance2_payload_mode = "reference_media" if seedance2_ref_mode == "entity_refs" else "frame_content"

        # Seedance-2 rejects payloads that mix first/last frame content with
        # additional reference media roles in the same request content.
        if is_seedance2 and (resolved_image_refs or resolved_last_frame or reference_video_urls or reference_audio_urls):
            if seedance2_payload_mode == "frame_content":
                keep_first_ref = str(resolved_image_refs[0] or "").strip() if resolved_image_refs else ""
                dropped_mixed_reference_counts["image"] = max(0, len(resolved_image_refs) - (1 if keep_first_ref else 0))
                dropped_mixed_reference_counts["video"] = len(reference_video_urls)
                dropped_mixed_reference_counts["audio"] = len(reference_audio_urls)

                resolved_image_refs = [keep_first_ref] if keep_first_ref else []
                reference_video_urls = []
                reference_audio_urls = []
            else:
                dropped_last_frame = 1 if bool(resolved_last_frame) else 0
                resolved_last_frame = None
                if dropped_last_frame:
                    logger.info(
                        "[ZLHubSeedance2] dropped last_frame in reference_media mode | trace_id=%s",
                        zlhub_trace_id,
                    )

            if any(dropped_mixed_reference_counts.values()):
                logger.info(
                    "[ZLHubSeedance2] dropped mixed reference media | trace_id=%s ref_mode=%s payload_mode=%s dropped_image_refs=%s dropped_video_refs=%s dropped_audio_refs=%s",
                    zlhub_trace_id,
                    seedance2_ref_mode or "start",
                    seedance2_payload_mode or "frame_content",
                    dropped_mixed_reference_counts["image"],
                    dropped_mixed_reference_counts["video"],
                    dropped_mixed_reference_counts["audio"],
                )

        if is_seedance2:
            logger.info(
                "[ZLHubSeedance2] refs_resolved | trace_id=%s ref_mode=%s payload_mode=%s image_refs=%s has_last_frame=%s ref_videos=%s ref_audios=%s",
                zlhub_trace_id,
                seedance2_ref_mode or "start",
                seedance2_payload_mode or "frame_content",
                len(resolved_image_refs),
                bool(resolved_last_frame),
                len(reference_video_urls),
                len(reference_audio_urls),
            )

        moderation_results: List[Dict[str, Any]] = []
        moderation_candidates: List[tuple[str, str]] = []
        if resolved_image_refs:
            if len(resolved_image_refs) == 1 and not resolved_last_frame:
                moderation_candidates.append((resolved_image_refs[0], "first_frame"))
            else:
                for idx, item in enumerate(resolved_image_refs):
                    moderation_candidates.append((item, "first_frame" if idx == 0 else "reference_image"))
        if resolved_last_frame:
            moderation_candidates.append((resolved_last_frame, "last_frame"))

        moderated_first_and_refs: List[str] = []
        moderated_last_frame = resolved_last_frame
        if moderation_candidates:
            candidate_refs = [item[0] for item in moderation_candidates]
            candidate_roles = [item[1] for item in moderation_candidates]
            batch_result = await self._maybe_moderate_zlhub_images(candidate_refs, config, candidate_roles)
            if batch_result.get("error") and batch_result.get("submit_failed"):
                return {
                    "error": batch_result.get("error"),
                    "details": batch_result.get("details") or batch_result,
                    "submit_failed": True,
                }
            
            if batch_result.get("blocked") and not batch_result.get("items"):
                return {
                    "error": f"ZLHub moderation blocked the request",
                    "details": batch_result.get("reason") or batch_result,
                    "submit_failed": True,
                }

            moderation_results = list(batch_result.get("items") or [])
            for idx, moderation_result in enumerate(moderation_results):
                candidate_ref, role = moderation_candidates[idx] if idx < len(moderation_candidates) else ("", "")
                if moderation_result.get("blocked"):
                    logger.error(f"[ZLHubModeration] Blocked Details: {moderation_result} | batch_result: {batch_result}")
                    return {
                        "error": f"{provider_name} moderation blocked reference material",
                        "details": moderation_result,
                        "submit_failed": True,
                    }
                approved_ref = str(moderation_result.get("approved_ref") or candidate_ref or "").strip()
                if role == "last_frame":
                    moderated_last_frame = approved_ref or moderated_last_frame
                elif approved_ref:
                    moderated_first_and_refs.append(approved_ref)

        if moderated_first_and_refs:
            resolved_image_refs = [item for item in dict.fromkeys(moderated_first_and_refs) if item]
        if moderated_last_frame:
            resolved_last_frame = moderated_last_frame

        is_i2v_request = bool(resolved_image_refs or resolved_last_frame)

        content_payload: List[Dict[str, Any]] = []
        if prompt_text:
            content_payload.append({"type": "text", "text": prompt_text})

        if is_seedance2 and seedance2_payload_mode == "reference_media":
            for item in resolved_image_refs:
                content_payload.append({
                    "type": "image_url",
                    "image_url": {"url": item},
                    "role": "reference_image",
                })
        elif resolved_image_refs:
            if is_seedance2 and seedance2_payload_mode == "frame_content":
                content_payload.append({
                    "type": "image_url",
                    "image_url": {"url": resolved_image_refs[0]},
                    "role": "first_frame",
                })
            elif len(resolved_image_refs) == 1 and not resolved_last_frame:
                content_payload.append({
                    "type": "image_url",
                    "image_url": {"url": resolved_image_refs[0]},
                    "role": "first_frame",
                })
            else:
                for idx, item in enumerate(resolved_image_refs):
                    content_payload.append({
                        "type": "image_url",
                        "image_url": {"url": item},
                        "role": "reference_image",
                    })
        if resolved_last_frame:
            content_payload.append({
                "type": "image_url",
                "image_url": {"url": resolved_last_frame},
                "role": "last_frame",
            })
        for item in reference_video_urls:
            content_payload.append({
                "type": "video_url",
                "video_url": {"url": item},
                "role": "reference_video",
            })
        for item in reference_audio_urls:
            content_payload.append({
                "type": "audio_url",
                "audio_url": {"url": item},
                "role": "reference_audio",
            })

        payload: Dict[str, Any] = {
            "model": model,
            "content": content_payload,
        }

        is_draft = bool(self._normalize_bool_value(tool_conf.get("draft_mode")) or self._normalize_bool_value(tool_conf.get("draft")))
        if is_draft:
            if is_seedance2 and is_i2v_request:
                pass
            else:
                payload["draft"] = True

        if callback_url and callback_url != "-1":
            payload["webhook_url"] = callback_url
            payload["webhookUrl"] = callback_url
            payload["callback_url"] = callback_url
            payload["notify_url"] = callback_url

        # Seedance: ratio uses the same value as aspect_ratio (default 16:9).
        normalized_ratio = self._normalize_aspect_ratio_value(aspect_ratio) or "16:9"
        payload["ratio"] = normalized_ratio

        try:
            payload["duration"] = int(duration if duration is not None else (tool_conf.get("duration") if tool_conf.get("duration") is not None else 5))
        except Exception:
            payload["duration"] = 5
        if is_seedance2 and payload.get("duration") == -1:
            logger.info(
                "[ZLHubSeedance2] auto_duration | trace_id=%s duration=-1",
                zlhub_trace_id,
            )

        for source_key, target_key in (("resolution", "resolution"), ("generate_audio", "generate_audio")):
            value = tool_conf.get(source_key)
            if source_key == "resolution" and not value:
                value = image_size or tool_conf.get("image_size") or tool_conf.get("size")
            if source_key == "resolution" and not value:
                value = "720p"
            if source_key == "resolution" and is_draft:
                value = "480p"
            if value is None:
                continue
            if source_key == "resolution" and is_seedance2 and is_i2v_request and not is_draft:
                logger.info(
                    "[ZLHubSeedance2] dropping unsupported i2v resolution | trace_id=%s model=%s resolution=%s",
                    zlhub_trace_id,
                    model,
                    value,
                )
                continue
            payload[target_key] = value

        raw_tools = tool_conf.get("tools")
        if raw_tools is None and tool_conf.get("web_search"):
            raw_tools = ["web_search"]
        if isinstance(raw_tools, str):
            raw_tools = [raw_tools]
        if isinstance(raw_tools, list):
            normalized_tools: List[Dict[str, Any]] = []
            for item in raw_tools:
                if isinstance(item, dict) and item.get("type"):
                    normalized_tools.append(item)
                    continue
                name = str(item or "").strip().lower()
                if name == "web_search":
                    normalized_tools.append({"type": "web_search"})
            if normalized_tools:
                payload["tools"] = normalized_tools

        base_metadata = {
            "provider": "zlhub",
            "provider_label": provider_name,
            "model": model,
            "prompt": prompt,
            "trace_id": zlhub_trace_id,
            "submit_url": submit_url,
            "query_endpoint": query_endpoint,
            "requested_duration": payload.get("duration"),
            "requested_aspect_ratio": payload.get("ratio"),
            "resolved_reference_count": len(resolved_image_refs),
            "resolved_reference_video_count": len(reference_video_urls),
            "resolved_reference_audio_count": len(reference_audio_urls),
            "resolved_ref_mode": seedance2_ref_mode or None,
            "seedance2_payload_mode": seedance2_payload_mode or None,
            "dropped_mixed_reference_counts": dropped_mixed_reference_counts,
            "moderation": moderation_results,
        }
        if is_seedance2:
            logger.info(
                "[ZLHubSeedance2] submit_ready | trace_id=%s payload_duration=%s payload_ratio=%s tools=%s content_items=%s",
                zlhub_trace_id,
                payload.get("duration"),
                payload.get("ratio"),
                len(payload.get("tools") or []) if isinstance(payload.get("tools"), list) else 0,
                len(content_payload),
            )
        with open('last_payload.txt', 'w') as fh:
            import json
            fh.write(json.dumps(payload, indent=2))
        return await self._submit_and_poll_zlhub_video(
            submit_url,
            query_endpoint,
            payload,
            api_key,
            "zlhub_video",
            extra_metadata=base_metadata,
            pure_callback_mode=pure_callback_mode,
            callback_enabled=callback_enabled,
            callback_ticket=callback_ticket,
            callback_url=callback_url,
            provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
        )

    def _resolve_apiyi_chat_video_model(self, model: str, aspect_ratio: Optional[str] = None, duration: Optional[int] = None) -> str:
        normalized_model = str(model or "").strip() or "sora_video2"
        normalized_ratio = self._normalize_aspect_ratio_value(aspect_ratio)
        try:
            duration_value = int(duration or 0)
        except Exception:
            duration_value = 0

        if normalized_model == "sora-2-pro":
            return normalized_model

        known_reverse = {
            "sora_video2",
            "sora_video2-15s",
            "sora_video2-landscape",
            "sora_video2-landscape-15s",
        }
        if normalized_model not in known_reverse:
            return normalized_model

        wants_landscape = normalized_ratio == "16:9" or "landscape" in normalized_model
        wants_15s = duration_value >= 15 or normalized_model.endswith("-15s")

        resolved_model = "sora_video2-landscape" if wants_landscape else "sora_video2"
        if wants_15s:
            resolved_model = f"{resolved_model}-15s"
        return resolved_model

    def _apiyi_chat_video_size_for_model(self, model: str) -> Optional[str]:
        normalized_model = str(model or "").strip().lower()
        size_map = {
            "sora_video2": "720x1280",
            "sora_video2-15s": "720x1280",
            "sora_video2-landscape": "1280x720",
            "sora_video2-landscape-15s": "1280x720",
            "sora-2-pro": "1024x1792",
        }
        return size_map.get(normalized_model)

    def _extract_apiyi_sse_video_url(self, message_text: str) -> Optional[str]:
        raw = str(message_text or "").strip()
        if not raw:
            return None
        markdown_match = re.search(r"\((https?://[^)\s]+)\)", raw, flags=re.IGNORECASE)
        if markdown_match:
            return markdown_match.group(1)
        url_match = re.search(r"https?://\S+", raw, flags=re.IGNORECASE)
        if url_match:
            return url_match.group(0).rstrip(")].,!?\"'")
        return None

    async def _submit_apiyi_chat_video_stream(self, url, payload, api_key, log_tag, extra_metadata=None, provider_payload_callback: Any = None):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        _debug_log(f"[{log_tag}] Streaming submit to URL: {url} | Payload: {_strip_base64_from_log(payload)}")

        def _post(use_proxy=True, connection_close: bool = False):
            request_headers = dict(headers)
            if connection_close:
                request_headers["Connection"] = "close"
            kwargs = {
                "json": payload,
                "headers": request_headers,
                "timeout": (60, 360),
                "verify": False,
                "stream": True,
            }
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(url, **kwargs)

        try:
            try:
                resp = await asyncio.to_thread(_post, True, False)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                try:
                    resp = await asyncio.to_thread(_post, False, False)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                    resp = await asyncio.to_thread(_post, False, True)

            if callable(provider_payload_callback) and isinstance(payload, dict):
                try:
                    provider_payload_callback(
                        {
                            "provider": str((extra_metadata or {}).get("provider") or "apiyi").strip().lower() or "apiyi",
                            "type": "video",
                            "method": "POST",
                            "url": url,
                            "model": payload.get("model"),
                            "payload": _strip_base64_from_log(payload),
                            "final_submit": True,
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "[%s] provider payload callback failed on apiyi chat submit | error=%s",
                        log_tag,
                        callback_err,
                    )

            if resp.status_code != 200:
                body = ""
                try:
                    body = resp.text
                except Exception:
                    body = ""
                return {"error": f"Submission Failed {resp.status_code}", "details": body[:1000], "submit_failed": True}

            def _consume_stream() -> Dict[str, Any]:
                last_messages: List[str] = []
                progress_value: Optional[float] = None
                video_url: Optional[str] = None
                event_data_lines: List[str] = []

                def _flush_event() -> Optional[str]:
                    nonlocal progress_value, video_url, event_data_lines
                    if not event_data_lines:
                        return None
                    raw_event = "\n".join(event_data_lines).strip()
                    event_data_lines = []
                    if not raw_event:
                        return None
                    if raw_event == "[DONE]":
                        return "done"
                    try:
                        payload_obj = json.loads(raw_event)
                    except Exception:
                        return None
                    choices = payload_obj.get("choices") if isinstance(payload_obj, dict) else None
                    if not isinstance(choices, list) or not choices:
                        return None
                    delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
                    content = ""
                    if isinstance(delta, dict):
                        content = str(delta.get("content") or "")
                    if not content:
                        return None
                    content = content.strip()
                    if content:
                        last_messages.append(content)
                        if len(last_messages) > 12:
                            last_messages.pop(0)
                        progress_match = re.search(r"(\d+(?:\.\d+)?)%", content)
                        if progress_match:
                            try:
                                progress_value = float(progress_match.group(1))
                            except Exception:
                                pass
                        extracted_url = self._extract_apiyi_sse_video_url(content)
                        if extracted_url:
                            video_url = extracted_url
                    return None

                for raw_line in resp.iter_lines(decode_unicode=True):
                    if raw_line is None:
                        continue
                    line = str(raw_line)
                    if not line.strip():
                        signal = _flush_event()
                        if signal == "done":
                            break
                        continue
                    if not line.startswith("data:"):
                        continue
                    event_data_lines.append(line[5:].strip())

                signal = _flush_event()
                if signal == "done":
                    pass
                return {
                    "video_url": video_url,
                    "progress": progress_value,
                    "messages": last_messages,
                }

            stream_result = await asyncio.to_thread(_consume_stream)
            video_url = str((stream_result or {}).get("video_url") or "").strip()
            if not video_url:
                return {
                    "error": "Generation completed without video URL",
                    "details": " | ".join((stream_result or {}).get("messages") or [])[:1000],
                    "submit_failed": True,
                }

            metadata = {
                "apiyi_stream_messages": (stream_result or {}).get("messages") or [],
                "progress": (stream_result or {}).get("progress"),
            }
            if extra_metadata:
                metadata.update(extra_metadata)
            return {"url": video_url, "metadata": metadata}
        except requests.exceptions.Timeout as e:
            return {"error": "Upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            return {"error": "Upstream request failed", "details": str(e), "submit_failed": True}
        except Exception as e:
            return {"error": str(e), "submit_failed": True}

    async def _handle_n1n_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        provider_name = self._vendor_label(config.get("provider") or ((config.get("config") or {}).get("provider")) or "n1n")
        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            return {"error": f"No {provider_name} API Key", "submit_failed": True}

        if gen_type != "image":
            return {"error": f"{provider_name} generation type not supported yet: {gen_type}", "submit_failed": True}

        tool_conf = config.get("config", {}) or {}
        base_url = str(config.get("base_url") or "https://api.n1n.ai").strip().rstrip("/")
        endpoint = str(tool_conf.get("endpoint") or tool_conf.get("endpoint_hint") or "").strip()
        model = str(config.get("model") or "").strip()
        if not endpoint:
            endpoint = "/models/{model}:generateContent" if "v1beta" in base_url or "v1" in base_url else "/v1beta/models/{model}:generateContent"
        if not model:
            return {"error": f"{provider_name} runtime model missing from system configuration", "submit_failed": True}

        endpoint_lower = endpoint.lower()
        if "generatecontent" not in endpoint_lower:
            return {"error": f"{provider_name} image endpoint family not supported yet: {endpoint}", "submit_failed": True}

        resolved_endpoint = endpoint.replace("{model}", urllib.parse.quote(model, safe="-._~"))
        submit_url = resolved_endpoint if re.match(r"^https?://", resolved_endpoint, flags=re.IGNORECASE) else f"{base_url}{resolved_endpoint if resolved_endpoint.startswith('/') else '/' + resolved_endpoint}"

        prompt_text = self._merge_negative_prompt(prompt, negative_prompt)
        parts: List[Dict[str, Any]] = []
        if prompt_text:
            parts.append({"text": prompt_text})

        reference_values = ref_image if isinstance(ref_image, list) else [ref_image]
        for ref_item in reference_values:
            if ref_item is None:
                continue
            if isinstance(ref_item, str) and not ref_item.strip():
                continue
            data_uri = await self._get_image_base64_for_api_async(ref_item, force_data_uri=True)
            if not isinstance(data_uri, str) or not data_uri.startswith("data:image/"):
                return {"error": f"{provider_name} Gemini image editing requires resolvable image inputs", "submit_failed": True}
            marker = ";base64,"
            idx = data_uri.find(marker)
            if idx <= 5:
                return {"error": f"{provider_name} Gemini image input data URI is malformed", "submit_failed": True}
            mime = data_uri[5:idx].strip().lower() or "image/png"
            parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": data_uri[idx + len(marker):].strip(),
                }
            })

        if not parts:
            return {"error": f"{provider_name} Gemini image generation requires at least one prompt or image input", "submit_failed": True}

        response_modalities = tool_conf.get("responseModalities") or tool_conf.get("response_modalities") or ["TEXT", "IMAGE"]
        if isinstance(response_modalities, str):
            response_modalities = [response_modalities]
        normalized_modalities = []
        for item in response_modalities if isinstance(response_modalities, list) else []:
            value = str(item or "").strip().upper()
            if value and value not in normalized_modalities:
                normalized_modalities.append(value)
        if "IMAGE" not in normalized_modalities:
            normalized_modalities.append("IMAGE")

        final_contents = [{
            "role": "user",
            "parts": parts,
        }]

        if config.get("is_gemini_multi_turn_edit"):
            base_prompt = config.get("gemini_base_prompt") or prompt_text
            edit_instruction = config.get("gemini_edit_instruction") or prompt_text
            inline_parts = [p for p in parts if "inline_data" in p]
            if inline_parts:
                final_contents = [
                    {"role": "user", "parts": [{"text": base_prompt}]},
                    {"role": "model", "parts": inline_parts},
                    {"role": "user", "parts": [{"text": edit_instruction}]}
                ]

        payload: Dict[str, Any] = {
            "contents": final_contents,
            "generationConfig": {
                "responseModalities": normalized_modalities,
            },
        }

        image_config: Dict[str, Any] = {}
        normalized_aspect_ratio = self._normalize_aspect_ratio_value(aspect_ratio or tool_conf.get("aspect_ratio") or tool_conf.get("aspectRatio"))
        if normalized_aspect_ratio and normalized_aspect_ratio != "adaptive":
            image_config["aspectRatio"] = normalized_aspect_ratio

        normalized_image_size = self._normalize_image_size_value(image_size or tool_conf.get("image_size") or tool_conf.get("imageSize"))
        if normalized_image_size:
            model_lower = model.lower()
            if "gemini-3-pro-image-preview" in model_lower or "gemini-3.1-flash-image-preview" in model_lower:
                image_config["imageSize"] = normalized_image_size

        if image_config:
            payload["generationConfig"]["imageConfig"] = image_config

        if config.get("has_google_search") or tool_conf.get("has_google_search"):
            payload["tools"] = [{"google_search": {}}]

        if config.get("has_thinking_mode") or tool_conf.get("has_thinking_mode"):
            think_level = str(config.get("thinking_level") or tool_conf.get("thinking_level") or "high").lower()
            if think_level not in ["minimal", "high"]: think_level = "high"
            payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": think_level, "includeThoughts": True}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        prefer_no_proxy = self._should_prefer_no_proxy(provider_name, "n1n_gemini_image")

        def _post(use_proxy=True, connect_timeout=None):
            c_timeout = connect_timeout or 120
            return self._post_json_request(submit_url, payload, headers, (c_timeout, 120), verify=False, use_proxy=use_proxy)

        def _extract_generated_image(value: Any) -> Optional[str]:
            if isinstance(value, dict):
                for key in ["inline_data", "inlineData"]:
                    inline_block = value.get(key)
                    if isinstance(inline_block, dict):
                        mime = str(inline_block.get("mime_type") or inline_block.get("mimeType") or "").strip().lower()
                        data = str(inline_block.get("data") or "").strip()
                        if mime.startswith("image/") and data:
                            return f"data:{mime};base64,{data}"
                for key in ["url", "imageUrl", "image_url"]:
                    candidate = value.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
                preferred_keys = ["parts", "content", "contents", "candidates", "data", "result", "results", "response"]
                for key in preferred_keys:
                    found = _extract_generated_image(value.get(key))
                    if found:
                        return found
                for nested in value.values():
                    found = _extract_generated_image(nested)
                    if found:
                        return found
            elif isinstance(value, list):
                for item in value:
                    found = _extract_generated_image(item)
                    if found:
                        return found
            elif isinstance(value, str):
                raw = value.strip()
                if raw.startswith("data:image/") or raw.lower().startswith(("http://", "https://")):
                    return raw
            return None

        try:
            try:
                resp = await asyncio.to_thread(_post, not prefer_no_proxy)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if prefer_no_proxy:
                    raise
                _debug_log(f"[n1n_gemini_image] Connection Failed with Proxy ({str(e)[:50]}...). Retrying without proxy (connect_timeout=15s)...", "warning")
                resp = await asyncio.to_thread(_post, False, 15)

            if resp.status_code != 200:
                _debug_log(f"[n1n_gemini_image] Error {resp.status_code}: {resp.text}", "error")
                return {"error": f"n1n API Error {resp.status_code}", "details": resp.text, "submit_failed": True}

            data = resp.json()
            _debug_log(f"[n1n_gemini_image] API Response: {_strip_base64_from_log(data)}")
            generated_image = _extract_generated_image(data)
            if not generated_image:
                return {
                    "error": "n1n Gemini response did not include an image output",
                    "details": _strip_base64_from_log(data),
                    "submit_failed": True,
                }

            metadata = {
                "raw": data,
                "provider": "n1n",
                "model": model,
                "submit_url": submit_url,
                "endpoint_family": "/v1beta/models/{model}:generateContent",
            }
            return {"url": generated_image, "metadata": metadata}
        except requests.exceptions.Timeout as e:
            _debug_log(f"[n1n_gemini_image] Timeout: {e}", "error")
            return {"error": "n1n upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            _debug_log(f"[n1n_gemini_image] RequestException: {e}", "error")
            return {"error": "n1n upstream request failed", "details": str(e), "submit_failed": True}
        except Exception as e:
            _debug_log(f"[n1n_gemini_image] Exception: {e}", "error")
            return {"error": str(e), "submit_failed": True}

    async def _handle_n1n_kling_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        provider_name = self._vendor_label(config.get("provider") or ((config.get("config") or {}).get("provider")) or "n1n")
        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            return {"error": f"No {provider_name} API Key", "submit_failed": True}

        if gen_type != "image":
            return {"error": f"{provider_name} generation type not supported yet: {gen_type}", "submit_failed": True}

        tool_conf = config.get("config", {}) or {}
        base_url = str(config.get("base_url") or "https://api.n1n.ai").strip().rstrip("/")
        endpoint = str(tool_conf.get("endpoint") or tool_conf.get("endpoint_hint") or "/kling/v1/images/generations").strip()
        submit_url = endpoint if re.match(r"^https?://", endpoint, flags=re.IGNORECASE) else f"{base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"

        configured_model_name = str(
            tool_conf.get("model_name")
            or tool_conf.get("modelName")
            or ((tool_conf.get("n1n") or {}).get("model_name") if isinstance(tool_conf.get("n1n"), dict) else "")
            or ((tool_conf.get("n1n") or {}).get("kling_model_name") if isinstance(tool_conf.get("n1n"), dict) else "")
            or ""
        ).strip()
        has_ref_image = bool(ref_image)
        model_name = configured_model_name or ("kling-v1-5" if has_ref_image else "kling-v1")

        payload: Dict[str, Any] = {
            "model_name": model_name,
            "prompt": str(prompt or "").strip(),
            "n": int(tool_conf.get("n") or 1),
        }

        neg_prompt = str(negative_prompt or tool_conf.get("negative_prompt") or tool_conf.get("negativePrompt") or "").strip()
        if neg_prompt:
            payload["negative_prompt"] = neg_prompt

        normalized_image_size = self._normalize_image_size_value(
            image_size or tool_conf.get("image_size") or tool_conf.get("imageSize") or tool_conf.get("resolution")
        )
        resolution_value = str(tool_conf.get("resolution") or (normalized_image_size.lower() if normalized_image_size else "")).strip().lower()
        if resolution_value in {"1k", "2k"}:
            payload["resolution"] = resolution_value

        normalized_aspect_ratio = self._normalize_aspect_ratio_value(aspect_ratio or tool_conf.get("aspect_ratio") or tool_conf.get("aspectRatio"))
        if normalized_aspect_ratio and normalized_aspect_ratio != "adaptive":
            payload["aspect_ratio"] = normalized_aspect_ratio

            resolved_refs = self._resolve_ref_list_for_api(
                ref_image,
                force_data_uri_for_local=True,
                prefer_public_upload_url=True,
                data_uri_profile="n1n_image_ref",
            ) if ref_image else []
        if resolved_refs:
            payload["image"] = resolved_refs[0]
            payload["image_reference"] = str(tool_conf.get("image_reference") or tool_conf.get("imageReference") or "subject").strip() or "subject"
            image_fidelity = tool_conf.get("image_fidelity") if tool_conf.get("image_fidelity") is not None else tool_conf.get("imageFidelity")
            human_fidelity = tool_conf.get("human_fidelity") if tool_conf.get("human_fidelity") is not None else tool_conf.get("humanFidelity")
            if image_fidelity is None:
                image_fidelity = 0.5
            payload["image_fidelity"] = image_fidelity
            if human_fidelity is not None:
                payload["human_fidelity"] = human_fidelity

        internal_callback_url = str(tool_conf.get("_provider_callback_url") or "").strip()
        raw_callback_url = str(internal_callback_url or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or tool_conf.get("callBackUrl") or "").strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or "n1n-kling-image"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url:
            callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        if callback_url and callback_url != raw_callback_url:
            logger.info(
                "n1n Kling callback auto-assigned | ticket=%s callback_url=%s raw_callback=%s",
                callback_ticket,
                callback_url,
                raw_callback_url or None,
            )
        if callback_url:
            payload["callback_url"] = callback_url
        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(
            str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"}
        )

        extra_metadata = {
            "provider": provider_name,
            "model": model_name,
            "prompt": prompt,
            "submit_url": submit_url,
            "endpoint_family": "/kling/v1/images/generations",
        }
        return await self._submit_and_poll_image_task(
            submit_url,
            payload,
            api_key,
            f"{str(provider_name).lower()}_kling_image",
            extra_metadata=extra_metadata,
            provider_payload_callback=tool_conf.get("_provider_payload_callback") if callable(tool_conf.get("_provider_payload_callback")) else None,
            pure_callback_mode=pure_callback_mode,
            callback_enabled=callback_enabled,
            callback_ticket=callback_ticket,
            callback_url=callback_url,
        )

    async def _handle_stability_generation(self, gen_type, prompt, config, ref_image=None, negative_prompt: Optional[str] = None):
        if gen_type != "image": return {"error": "Stability only supports image"}
        
        api_key = config.get("api_key")
        tool_conf = config.get("config", {}) or {}
        endpoint = tool_conf.get("endpoint") or "https://api.stability.ai"
        endpoint = endpoint.rstrip("/")
        model = config.get("model") or "stable-diffusion-xl-1024-v1-0"
        
        base_metadata = {"provider": "stability", "model": model, "prompt": prompt}
        
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
        
        # I2I
        if ref_image:
             url = f"{endpoint}/v1/generation/{model}/image-to-image"
             ref_bytes = None

             if self._is_public_http_url(ref_image):
                 try:
                     resp = await asyncio.to_thread(lambda: requests.get(ref_image, timeout=30))
                     if resp.status_code == 200:
                         ref_bytes = resp.content
                 except Exception:
                     ref_bytes = None
             else:
                 b64 = await self._get_image_base64_for_api_async(ref_image)
                 if b64 and b64 != ref_image:
                     ref_bytes = base64.b64decode(b64)
            
             if ref_bytes:
                 files = {"init_image": ("init_image.png", ref_bytes, "image/png")}
                 data = {"text_prompts[0][text]": prompt, "init_image_mode": "IMAGE_STRENGTH", "image_strength": 0.35}
                 if str(negative_prompt or "").strip():
                     data["text_prompts[1][text]"] = str(negative_prompt).strip()
                     data["text_prompts[1][weight]"] = -1
                 
                 def _post_i2i(): return requests.post(url, headers=headers, files=files, data=data, timeout=(15, 120), verify=False)
                 resp = await asyncio.to_thread(_post_i2i)
             else:
                 return {"error": "Could not load reference image"}

        else:
             # T2I
             url = f"{endpoint}/v1/generation/{model}/text-to-image"
             headers["Content-Type"] = "application/json"
             cfg_scale = 7.0
             try:
                 configured_cfg = tool_conf.get("cfg_scale")
                 if configured_cfg is None:
                     configured_cfg = tool_conf.get("cfg")
                 if configured_cfg is not None:
                     parsed_cfg = float(configured_cfg)
                     if parsed_cfg > 0:
                         cfg_scale = parsed_cfg
             except Exception:
                 pass
             body = {"text_prompts": [{"text": prompt}], "cfg_scale": cfg_scale, "height": 1024, "width": 1024, "samples": 1}
             if str(negative_prompt or "").strip():
                 body["text_prompts"].append({"text": str(negative_prompt).strip(), "weight": -1})
             def _post_t2i(): return requests.post(url, headers=headers, json=body, timeout=(15, 120), verify=False)
             resp = await asyncio.to_thread(_post_t2i)
        
        if resp.status_code != 200: return {"error": f"Stability Error {resp.status_code}", "details": resp.text}
        
        data = resp.json()
        artifacts = data.get("artifacts", [])
        if artifacts:
             b64 = artifacts[0].get("base64")
             try:
                 meta = {"raw": data}
                 meta.update(base_metadata)
                 return {"url": f"data:image/png;base64,{b64}", "metadata": meta}
             except Exception as e:
                 return {"error": f"Failed to save image: {e}"}
        return {"error": "No artifacts"}

    # --- Helper to Common Requests ---
    async def _common_requests_post(self, url, payload, api_key, log_tag, timeout=None, extra_metadata=None, provider_payload_callback: Any = None):
        # Async wrap for requests
        provider_name = str((extra_metadata or {}).get("provider") or "").strip().lower()
        headers = self._build_transport_headers(provider_name, log_tag, api_key, payload)
        read_timeout = self._resolve_common_post_timeout(provider_name, log_tag, timeout)
        prefer_no_proxy = self._should_prefer_no_proxy(provider_name, log_tag)
        upstream_urls = [str(url or "").strip()]
        if provider_name == "n1n":
            upstream_urls = self._build_n1n_mirror_urls(url)
        
        def _post(target_url, use_proxy=True, connect_timeout=None):
            c_timeout = connect_timeout or min(30, read_timeout)
            return self._post_json_request(target_url, payload, headers, (c_timeout, read_timeout), verify=False, use_proxy=use_proxy)
        
        try:
            last_response = None
            selected_url = upstream_urls[0] if upstream_urls else str(url or "").strip()
            for index, target_url in enumerate(upstream_urls or [str(url or "").strip()]):
                try:
                    resp = await asyncio.to_thread(_post, target_url, not prefer_no_proxy)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError) as e:
                    if prefer_no_proxy:
                        raise
                    _debug_log(f"[{log_tag}] Connection Failed with Proxy ({str(e)[:50]}...). Retrying without proxy (connect_timeout=15s)...", "warning")
                    try:
                        resp = await asyncio.to_thread(_post, target_url, False, 15)
                    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e2:
                        if self._is_ambiguous_submit_transport_error(provider_name, log_tag, e2):
                            return self._build_ambiguous_submit_result(provider_name, log_tag, e2, target_url, extra_metadata)
                        raise
                    except Exception as e2:
                        _debug_log(f"[{log_tag}] No-proxy retry also failed: {str(e2)[:120]}", "error")
                        if self._is_ambiguous_submit_transport_error(provider_name, log_tag, e2):
                            return self._build_ambiguous_submit_result(provider_name, log_tag, e2, target_url, extra_metadata)
                        raise
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    if self._is_ambiguous_submit_transport_error(provider_name, log_tag, e):
                        return self._build_ambiguous_submit_result(provider_name, log_tag, e, target_url, extra_metadata)
                    raise

                last_response = resp
                selected_url = target_url
                if (
                    provider_name == "n1n"
                    and resp.status_code == 429
                    and self._is_n1n_capacity_error(resp.text)
                    and index < len(upstream_urls) - 1
                ):
                    _debug_log(
                        f"[{log_tag}] Capacity/throttle on {target_url}; retrying mirror {upstream_urls[index + 1]}",
                        "warning",
                    )
                    continue
                break

            resp = last_response
            if resp is None:
                return {"error": "Upstream request failed", "details": "No upstream response", "submit_failed": True}

            if callable(provider_payload_callback) and isinstance(payload, dict):
                try:
                    provider_payload_callback(
                        {
                            "provider": provider_name or "unknown",
                            "type": "image",
                            "method": "POST",
                            "url": selected_url,
                            "model": payload.get("model"),
                            "payload": _strip_base64_from_log(payload),
                            "final_submit": True,
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "[%s] provider payload callback failed on common post | error=%s",
                        log_tag,
                        callback_err,
                    )

            if resp.status_code == 200:
                data = resp.json()
                _debug_log(f"[{log_tag}] API Response: {_strip_base64_from_log(data)}") # DEBUG USER REQUEST
                metadata = {"raw": data}
                if extra_metadata:
                    metadata.update(extra_metadata)
                metadata["submit_url"] = selected_url

                resolved_output = self._extract_openai_compatible_image_output(data)
                if resolved_output:
                    return {"url": resolved_output, "metadata": metadata}
                return {"url": data.get("url"), "metadata": metadata}
            else:
                _debug_log(f"[{log_tag}] Error {resp.status_code}: {resp.text}", "error")
                return {"error": f"API Error {resp.status_code}", "details": resp.text, "submit_failed": True}
        except requests.exceptions.Timeout as e:
            if self._is_ambiguous_submit_transport_error(provider_name, log_tag, e):
                return self._build_ambiguous_submit_result(provider_name, log_tag, e, selected_url, extra_metadata)
            _debug_log(f"[{log_tag}] Timeout: {e}", "error")
            return {"error": "Upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            _debug_log(f"[{log_tag}] RequestException: {e}", "error")
            if self._is_ambiguous_submit_transport_error(provider_name, log_tag, e):
                return self._build_ambiguous_submit_result(provider_name, log_tag, e, selected_url, extra_metadata)
            return {"error": "Upstream request failed", "details": str(e), "submit_failed": True}
        except Exception as e:
            _debug_log(f"[{log_tag}] Exception: {e}", "error")
            return {"error": str(e), "submit_failed": True}

    async def _submit_and_poll_runninghub(
        self,
        submit_url,
        query_url,
        payload,
        api_key,
        log_tag,
        extra_metadata=None,
        poll_timeout_seconds: int = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS,
        poll_interval_seconds: int = 2,
        pure_callback_mode: bool = False,
        callback_enabled: bool = False,
        callback_ticket: Optional[str] = None,
        callback_url: Optional[str] = None,
        provider_payload_callback: Any = None,
    ):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        retryable_statuses = {502, 503, 504, 520, 521, 522, 523, 524, 525, 526}
        max_submit_attempts = 1
        logger.info(f"[{log_tag}] RunningHub submit URL: {submit_url} | Payload: {_strip_base64_from_log(payload)}")

        def _extract_runninghub_media_url(value: Any) -> Optional[str]:
            if isinstance(value, dict):
                for key in [
                    "url",
                    "videoUrl",
                    "imageUrl",
                    "audioUrl",
                    "audio_url",
                    "fileUrl",
                    "file_url",
                    "downloadUrl",
                    "download_url",
                    "outputUrl",
                    "output_url",
                    "resultUrl",
                    "result_url",
                    "resourceUrl",
                    "resource_url",
                    "modelUrl",
                    "model_url",
                ]:
                    candidate = value.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
                for nested_key in ["results", "data", "output"]:
                    found = _extract_runninghub_media_url(value.get(nested_key))
                    if found:
                        return found
            elif isinstance(value, list):
                for item in value:
                    found = _extract_runninghub_media_url(item)
                    if found:
                        return found
            elif isinstance(value, str):
                raw = value.strip()
                if raw.lower().startswith(("http://", "https://")):
                    return raw
            return None

        def _extract_runninghub_usage(value: Any) -> Optional[Dict[str, Any]]:
            normalized = _normalize_provider_task_usage(_extract_provider_task_usage(value))
            return normalized or None

        def _post_json(url, body, use_proxy=True, connect_timeout=None, read_timeout=None):
            submit_timeouts = _media_submit_timeout_pair(connect_timeout=connect_timeout, io_timeout=read_timeout)
            kwargs = {
                "json": body,
                "headers": headers,
                "timeout": submit_timeouts,
                "verify": False,
            }
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(url, **kwargs)

        try:
            resp = None
            for submit_attempt in range(max_submit_attempts):
                try:
                    try:
                        resp = await asyncio.to_thread(_post_json, submit_url, payload, True)
                    except (requests.exceptions.ProxyError, requests.exceptions.SSLError) as e:
                        _debug_log(f"[{log_tag}] RunningHub submit failed with proxy ({str(e)[:120]}), retrying without proxy...", "warning")
                        resp = await asyncio.to_thread(_post_json, submit_url, payload, False)
                    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                        return self._build_ambiguous_submit_result("runninghub", log_tag, e, submit_url, extra_metadata)
                except requests.exceptions.RequestException as e:
                    if self._is_ambiguous_submit_transport_error("runninghub", log_tag, e):
                        return self._build_ambiguous_submit_result("runninghub", log_tag, e, submit_url, extra_metadata)
                    if submit_attempt < max_submit_attempts - 1:
                        _debug_log(
                            f"[{log_tag}] RunningHub submit request exception on attempt {submit_attempt + 1}/{max_submit_attempts}: {str(e)[:200]}; retrying...",
                            "warning",
                        )
                        await asyncio.sleep(min(2 * (submit_attempt + 1), 5))
                        continue
                    raise

                if callable(provider_payload_callback) and isinstance(payload, dict):
                    try:
                        provider_payload_callback(
                            {
                                "provider": "runninghub",
                                "type": "audio" if "audio" in str(log_tag or "").lower() else "video",
                                "method": "POST",
                                "url": submit_url,
                                "model": payload.get("model"),
                                "payload": _strip_base64_from_log(payload),
                            }
                        )
                    except Exception as callback_err:
                        logger.warning(
                            "[%s] provider payload callback failed before runninghub submit | error=%s",
                            log_tag,
                            callback_err,
                        )

                if resp.status_code in [200, 201]:
                    try:
                        data = resp.json()
                        task_id = data.get("taskId") or data.get("task_id") or data.get("id")
                        if not task_id and isinstance(data.get("data"), dict):
                            task_id = data.get("data", {}).get("taskId") or data.get("data", {}).get("task_id") or data.get("data", {}).get("id")
                        if not task_id:
                            submit_error_message = str(data.get("errorMessage") or "").strip()
                            if "is not in the allowed options" in submit_error_message and "allowed values:" in submit_error_message:
                                field_match = re.search(r"field\s+'([^']+)'", submit_error_message, re.IGNORECASE)
                                field_name = field_match.group(1).strip() if field_match else "duration"
                                val_match = re.search(r"allowed values:\s*(.*)", submit_error_message, re.IGNORECASE)
                                if val_match:
                                    allowed_vals = [x.strip() for x in val_match.group(1).split(",") if x.strip()]
                                    if allowed_vals:
                                        target_val = allowed_vals[-1] # Fallback to latest
                                        if field_name == "resolution" and payload.get("resolution"):
                                            req_res = str(payload.get("resolution")).lower()
                                            if "1080" in req_res:
                                                target_val = next((v for v in allowed_vals if "1080" in v), target_val)
                                            elif "720" in req_res:
                                                target_val = next((v for v in allowed_vals if "720" in v), target_val)
                                            elif "480" in req_res:
                                                target_val = next((v for v in allowed_vals if "480" in v), target_val)
                                        elif field_name == "duration":
                                            target_val = allowed_vals[0]

                                        _debug_log(f"[{log_tag}] RunningHub field '{field_name}' mismatch detected '{submit_error_message}', retrying with '{target_val}'...", "warning")
                                        payload[field_name] = target_val
                                        await asyncio.sleep(min(2 * (submit_attempt + 1), 5))
                                        continue
                            elif "is required, can not be empty" in submit_error_message:
                                field_match = re.search(r"field\s+'([^']+)'", submit_error_message, re.IGNORECASE)
                                if field_match:
                                    field_name = field_match.group(1).strip()
                                    if field_name in ["generateAudio", "bgm", "audio", "sound", "cameraFixed"]:
                                        _debug_log(f"[{log_tag}] RunningHub missing field '{field_name}' detected '{submit_error_message}', automatically assigning False...", "warning")
                                        if field_name in ["generateAudio", "cameraFixed"] and ("seedance" in submit_url.lower() or "seedance" in str(payload.get("model", "")).lower()):
                                            payload[field_name] = "false"
                                        else:
                                            payload[field_name] = False
                                        await asyncio.sleep(min(2 * (submit_attempt + 1), 5))
                                        continue
                    except Exception:
                        pass
                    break

                if resp.status_code in retryable_statuses and submit_attempt < max_submit_attempts - 1:
                    _debug_log(
                        f"[{log_tag}] RunningHub submit transient status {resp.status_code} on attempt {submit_attempt + 1}/{max_submit_attempts}; retrying...",
                        "warning",
                    )
                    await asyncio.sleep(min(2 * (submit_attempt + 1), 5))
                    continue

                break

            if resp.status_code not in [200, 201]:
                _debug_log(f"[{log_tag}] RunningHub submit error {resp.status_code}: {_strip_base64_from_log(resp.text)}", "error")
                return {"error": f"Submission Failed {resp.status_code}", "details": resp.text, "submit_failed": True}

            data = resp.json()
            submit_error_code = data.get("errorCode")
            submit_error_message = str(data.get("errorMessage") or "").strip()
            task_id = data.get("taskId") or data.get("task_id") or data.get("id")
            if not task_id and isinstance(data.get("data"), dict):
                task_id = data.get("data", {}).get("taskId") or data.get("data", {}).get("task_id") or data.get("data", {}).get("id")
            if not task_id:
                if submit_error_code not in (None, "", 0, "0") or submit_error_message:
                    upstream_message = submit_error_message or f"RunningHub submit rejected with code {submit_error_code}"
                    return {
                        "error": upstream_message,
                        "details": data,
                        "submit_failed": True,
                    }
                return {"error": "No Task ID", "details": data, "submit_failed": True}

            if callable(provider_payload_callback) and isinstance(payload, dict):
                try:
                    provider_payload_callback(
                        {
                            "provider": "runninghub",
                            "type": "audio" if "audio" in str(log_tag or "").lower() else "video",
                            "method": "POST",
                            "url": submit_url,
                            "model": payload.get("model"),
                            "payload": _strip_base64_from_log(payload),
                            "final_submit": True,
                            "provider_task_id": str(task_id),
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "[%s] provider payload callback failed after runninghub submit | task_id=%s error=%s",
                        log_tag,
                        task_id,
                        callback_err,
                    )

            if pure_callback_mode and callback_enabled:
                logger.info(
                    "[RunningHub] pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s",
                    task_id,
                    callback_ticket or None,
                    callback_url or None,
                )
                pending_meta = dict(extra_metadata or {})
                pending_meta.update(
                    {
                        "raw": data,
                        "submit_raw": data,
                        "task_id": str(task_id),
                        "taskId": str(task_id),
                        "pending_callback": True,
                        "callback_ticket": callback_ticket,
                        "callback_url": callback_url,
                    }
                )
                return {
                    "pending_callback": True,
                    "provider_task_id": str(task_id),
                    "metadata": pending_meta,
                }

            max_attempts = max(1, int(poll_timeout_seconds / max(1, poll_interval_seconds)))
            for _ in range(max_attempts):
                await asyncio.sleep(poll_interval_seconds)
                poll_body = {"taskId": task_id}
                try:
                    p_resp = await asyncio.to_thread(_post_json, query_url, poll_body, True, 15, 60)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                    p_resp = await asyncio.to_thread(_post_json, query_url, poll_body, False, 15, 60)
                except requests.exceptions.Timeout:
                    continue

                if p_resp.status_code != 200:
                    if p_resp.status_code in retryable_statuses:
                        _debug_log(
                            f"[{log_tag}] RunningHub poll transient status {p_resp.status_code}; continuing to poll...",
                            "warning",
                        )
                        continue
                    _debug_log(f"[{log_tag}] RunningHub poll error {p_resp.status_code}: {_strip_base64_from_log(p_resp.text[:500])}", "warning")
                    continue

                p_data = p_resp.json()
                status = str(p_data.get("status") or p_data.get("state") or "").strip().upper()
                if status in {"SUCCESS", "SUCCEEDED"}:
                    final_url = _extract_runninghub_media_url(p_data)
                    metadata = {"raw": p_data, "submit_raw": data, "taskId": task_id, "task_id": str(task_id)}
                    if extra_metadata:
                        metadata.update(extra_metadata)
                        metadata["raw"] = p_data
                    metadata = _attach_provider_usage_metadata(
                        metadata,
                        usage=_extract_runninghub_usage(p_data),
                        source="runninghub",
                        task_payload=p_data,
                    )
                    if final_url:
                        return {"url": final_url, "metadata": metadata}
                    return {"error": "RunningHub task completed without output URL", "details": p_data}

                if status == "FAILED":
                    failed_reason = p_data.get("failedReason")
                    error_message = p_data.get("errorMessage")
                    return {"error": "Generation Failed", "details": failed_reason or error_message or p_data}

            return {"error": f"Timeout after {poll_timeout_seconds}s"}
        except requests.exceptions.Timeout as e:
            return {"error": "Upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            return {"error": "Upstream request failed", "details": str(e), "submit_failed": True}
        except Exception as e:
            return {"error": str(e), "submit_failed": True}

    async def _submit_and_poll_video(
        self,
        url,
        payload,
        api_key,
        log_tag,
        extra_metadata=None,
        poll_timeout_seconds: int = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS,
        poll_interval_seconds: int = 2,
        pure_callback_mode: bool = False,
        callback_enabled: bool = False,
        callback_ticket: Optional[str] = None,
        callback_url: Optional[str] = None,
        provider_payload_callback: Any = None,
    ):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        provider_name = str((extra_metadata or {}).get("provider") or "").strip().lower()
        
        _debug_log(f"[{log_tag}] Submitting to URL: {url} | Payload: {_strip_base64_from_log(payload)}")
        
        submit_timeouts = _media_submit_timeout_pair()

        def _post(use_proxy=True, connection_close: bool = False, connect_timeout=None):
            request_headers = dict(headers)
            if connection_close:
                request_headers["Connection"] = "close"
            c_timeout = connect_timeout or submit_timeouts[0]
            kwargs = {
                "json": payload,
                "headers": request_headers,
                "timeout": (c_timeout, submit_timeouts[1]),
                "verify": False,
            }
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(url, **kwargs)

        def _poll(use_proxy=True, task_id=None):
            kwargs = {"headers": headers, "timeout": 30, "verify": False}
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.get(f"{url}/{task_id}", **kwargs)
        
        try:
            try:
                resp = await asyncio.to_thread(_post, True)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError) as e:
                _debug_log(f"[{log_tag}] Submit failed with proxy ({str(e)[:120]}), retrying without proxy (connect_timeout=15s)...", "warning")
                try:
                    resp = await asyncio.to_thread(_post, False, False, 15)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e2:
                    return self._build_ambiguous_submit_result(provider_name, log_tag, e2, url, extra_metadata)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError) as e2:
                    _debug_log(f"[{log_tag}] Submit retry without proxy failed ({str(e2)[:120]}), retrying with connection close...", "warning")
                    try:
                        resp = await asyncio.to_thread(_post, False, True, 15)
                    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e3:
                        return self._build_ambiguous_submit_result(provider_name, log_tag, e3, url, extra_metadata)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                return self._build_ambiguous_submit_result(provider_name, log_tag, e, url, extra_metadata)
            if callable(provider_payload_callback) and isinstance(payload, dict):
                try:
                    provider_payload_callback(
                        {
                            "provider": provider_name or "unknown",
                            "type": "video",
                            "method": "POST",
                            "url": url,
                            "model": payload.get("model"),
                            "payload": _strip_base64_from_log(payload),
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "[%s] provider payload callback failed before submit | error=%s",
                        log_tag,
                        callback_err,
                    )

            if resp.status_code not in [200, 201]:
                return {"error": f"Submission Failed {resp.status_code}", "details": resp.text, "submit_failed": True}
            
            data = resp.json()
            task_id = data.get("id") or data.get("task_id")
            if not task_id and isinstance(data.get("data"), dict):
                task_id = data.get("data", {}).get("id") or data.get("data", {}).get("task_id")
            if not task_id: return {"error": "No Task ID", "submit_failed": True}

            if callable(provider_payload_callback) and isinstance(payload, dict):
                try:
                    provider_payload_callback(
                        {
                            "provider": provider_name or "unknown",
                            "type": "video",
                            "method": "POST",
                            "url": url,
                            "model": payload.get("model"),
                            "payload": _strip_base64_from_log(payload),
                            "final_submit": True,
                            "provider_task_id": str(task_id),
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "[%s] provider payload callback failed after submit | task_id=%s error=%s",
                        log_tag,
                        task_id,
                        callback_err,
                    )

            if pure_callback_mode and callback_enabled:
                logger.info(
                    "[%s] pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s",
                    log_tag,
                    task_id,
                    callback_ticket or None,
                    callback_url or None,
                )
                pending_meta = dict(extra_metadata or {})
                pending_meta.update(
                    {
                        "raw": data,
                        "submit_raw": data,
                        "task_id": str(task_id),
                        "taskId": str(task_id),
                        "pending_callback": True,
                        "callback_ticket": callback_ticket,
                        "callback_url": callback_url,
                    }
                )
                return {
                    "pending_callback": True,
                    "provider_task_id": str(task_id),
                    "metadata": pending_meta,
                }
            
            # Poll
            max_attempts = max(1, int(poll_timeout_seconds / max(1, poll_interval_seconds)))
            for _ in range(max_attempts):
                await asyncio.sleep(poll_interval_seconds)
                try:
                    p_resp = await asyncio.to_thread(_poll, True, task_id)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                    p_resp = await asyncio.to_thread(_poll, False, task_id)
                except requests.exceptions.Timeout:
                    continue
                if p_resp.status_code == 200:
                    p_data = p_resp.json()
                    status = str(p_data.get("status") or p_data.get("state") or "").strip()
                    status_l = status.lower()
                    if status_l in ["succeeded", "success", "completed", "done"]:
                        content = p_data.get("content") or {}
                        video_url = None
                        if isinstance(content, dict):
                            video_url = content.get("video_url") or content.get("url")
                        if not video_url and isinstance(p_data.get("data"), dict):
                            data_content = p_data.get("data", {}).get("content", {}) or {}
                            video_url = data_content.get("video_url") or data_content.get("url")
                        # Veo-style: url at top level of poll response
                        if not video_url:
                            video_url = p_data.get("video_url") or p_data.get("url")
                        # Veo async API: separate /content endpoint
                        if not video_url and task_id:
                            try:
                                content_url = f"{url}/{task_id}/content"
                                c_resp = await asyncio.to_thread(lambda: requests.get(content_url, headers=headers, timeout=30, verify=False))
                                if c_resp.status_code == 200:
                                    c_data = c_resp.json()
                                    video_url = c_data.get("url") or c_data.get("video_url")
                            except Exception:
                                pass
                        
                        last_frame_url_res = None
                        if isinstance(content, dict):
                            last_frame_url_res = content.get("last_frame_url")
                        if not last_frame_url_res and isinstance(p_data.get("data"), dict):
                            data_content = p_data.get("data", {}).get("content", {}) or {}
                            last_frame_url_res = data_content.get("last_frame_url")

                        if not video_url:
                            return {
                                "error": "Generation completed without video URL",
                                "details": f"task_id={task_id} status={status or '<empty>'}",
                                "raw": p_data,
                            }
                        # Prefer provider-reported usage (Ark Seedance: usage.total_tokens / completion_tokens).
                        # Status may flip to succeeded before usage is populated; refresh task once if missing.
                        usage = _normalize_provider_task_usage(_extract_provider_task_usage(p_data))
                        if not usage:
                            try:
                                await asyncio.sleep(0.5)
                                try:
                                    refresh_resp = await asyncio.to_thread(_poll, True, task_id)
                                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                                    refresh_resp = await asyncio.to_thread(_poll, False, task_id)
                                if getattr(refresh_resp, "status_code", None) == 200:
                                    refresh_data = refresh_resp.json()
                                    if isinstance(refresh_data, dict):
                                        p_data = refresh_data
                                        usage = _normalize_provider_task_usage(_extract_provider_task_usage(refresh_data))
                            except Exception as usage_err:
                                logger.warning(
                                    "[%s] task usage refresh failed | task_id=%s error=%s",
                                    log_tag,
                                    task_id,
                                    usage_err,
                                )
                        metadata = {"raw": p_data, "task_id": str(task_id), "taskId": str(task_id)}
                        if extra_metadata:
                            metadata.update(extra_metadata)
                            metadata["raw"] = p_data
                        usage_source = provider_name or "ark"
                        metadata = _attach_provider_usage_metadata(
                            metadata,
                            usage=usage,
                            source=usage_source,
                            task_payload=p_data,
                        )
                        if usage:
                            logger.info(
                                "[%s] provider usage captured | task_id=%s source=%s total_tokens=%s completion_tokens=%s",
                                log_tag,
                                task_id,
                                usage_source,
                                usage.get("total_tokens"),
                                usage.get("completion_tokens") or usage.get("output_tokens"),
                            )
                        if last_frame_url_res:
                            metadata["last_frame_url"] = last_frame_url_res
                        return {"url": video_url, "metadata": metadata}
                    elif status_l in ["failed", "error", "canceled", "cancelled"]:
                        return {"error": "Generation Failed", "details": p_data.get("error")}
            return {"error": f"Timeout after {poll_timeout_seconds}s"}
        except requests.exceptions.Timeout as e:
            if self._is_ambiguous_submit_transport_error(provider_name, log_tag, e):
                return self._build_ambiguous_submit_result(provider_name, log_tag, e, url, extra_metadata)
            return {"error": "Upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            if self._is_ambiguous_submit_transport_error(provider_name, log_tag, e):
                return self._build_ambiguous_submit_result(provider_name, log_tag, e, url, extra_metadata)
            details = str(e)
            if "10054" in details or "ConnectionResetError" in details:
                details = f"{details}. Possible network middlebox/proxy reset on large request body; retried with no-proxy once."
            return {"error": "Upstream request failed", "details": details, "submit_failed": True}
        except Exception as e:
            return {"error": str(e), "submit_failed": True}

    async def _submit_and_poll_zlhub_video(
        self,
        submit_url,
        query_url,
        payload,
        api_key,
        log_tag,
        extra_metadata=None,
        poll_timeout_seconds: int = 1200,
        poll_interval_seconds: int = 2,
        pure_callback_mode: bool = False,
        callback_enabled: bool = False,
        callback_ticket: Optional[str] = None,
        callback_url: Optional[str] = None,
        provider_payload_callback: Any = None,
    ):
        trace_id = None
        media_url = None
        # ZLHub V2 requires X-Track-Id and X-Trace-ID specifically to be 32-char hex string
        track_id = uuid.uuid4().hex
        raw_trace_id = str((extra_metadata or {}).get("trace_id") or "").replace("-", "")
        trace_id = raw_trace_id if len(raw_trace_id) == 32 else track_id
        headers = {
            "Authorization": f"Bearer {api_key}", 
            "Content-Type": "application/json", 
            "X-Track-Id": track_id, 
            "X-Access-Token": api_key,
            "X-Trace-ID": trace_id
        }
        payload_model = str(payload.get("model") or "").strip().lower()
        is_seedance2 = payload_model.startswith("doubao-seedance-2")

        _debug_log(f"[{log_tag}] Submitting to URL: {submit_url} | Payload: {_strip_base64_from_log(payload)}")
        if is_seedance2:
            logger.info(
                "[ZLHubSeedance2] submit_start | trace_id=%s submit_url=%s query_url=%s duration=%s ratio=%s",
                trace_id,
                submit_url,
                query_url,
                payload.get("duration"),
                payload.get("ratio"),
            )

        def _submit(use_proxy: bool = True, connection_close: bool = False):
            request_headers = dict(headers)
            if connection_close:
                request_headers["Connection"] = "close"
            kwargs = {
                "json": payload,
                "headers": request_headers,
                "timeout": _media_submit_timeout_pair(),
                "verify": False,
            }
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(submit_url, **kwargs)

        def _poll(task_id: str, use_proxy: bool = True):
            normalized_query = str(query_url or "").strip()
            target_url = normalized_query.replace("{id}", urllib.parse.quote(task_id)).replace("{task_id}", urllib.parse.quote(task_id)) if "{id}" in normalized_query or "{task_id}" in normalized_query else f"{normalized_query.rstrip('/')}/{urllib.parse.quote(task_id)}"
            kwargs = {"headers": headers, "timeout": 30, "verify": False}
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.get(target_url, **kwargs)

        try:
            try:
                resp = await asyncio.to_thread(_submit, True, False)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                try:
                    resp = await asyncio.to_thread(_submit, False, False)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                    resp = await asyncio.to_thread(_submit, False, True)

            if is_seedance2:
                logger.info(
                    "[ZLHubSeedance2] submit_response | trace_id=%s status=%s bytes=%s",
                    trace_id,
                    getattr(resp, "status_code", None),
                    len(getattr(resp, "content", b"") or b""),
                )

            if callable(provider_payload_callback) and isinstance(payload, dict):
                try:
                    provider_payload_callback(
                        {
                            "provider": "zlhub",
                            "type": "video",
                            "method": "POST",
                            "url": submit_url,
                            "model": payload.get("model"),
                            "payload": _strip_base64_from_log(payload),
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "[%s] provider payload callback failed before zlhub submit | error=%s",
                        log_tag,
                        callback_err,
                    )

            if resp.status_code not in [200, 201]:
                if is_seedance2:
                    logger.error(
                        "[ZLHubSeedance2] submit_failed | trace_id=%s status=%s body=%s",
                        trace_id,
                        resp.status_code,
                        _strip_base64_from_log((resp.text or "")[:1000]),
                    )
                return {"error": f"Submission Failed {resp.status_code}", "details": (resp.text or "")[:1000], "submit_failed": True}

            data = resp.json() if resp.content else {}
            task_id = self._extract_zlhub_task_id(data)
            if not task_id:
                if is_seedance2:
                    logger.error(
                        "[ZLHubSeedance2] task_id_missing | trace_id=%s submit_raw=%s",
                        trace_id,
                        _strip_base64_from_log(data),
                    )
                return {"error": "No Task ID", "details": data, "submit_failed": True}

            if callable(provider_payload_callback) and isinstance(payload, dict):
                try:
                    provider_payload_callback(
                        {
                            "provider": "zlhub",
                            "type": "video",
                            "method": "POST",
                            "url": submit_url,
                            "model": payload.get("model"),
                            "payload": _strip_base64_from_log(payload),
                            "final_submit": True,
                            "provider_task_id": str(task_id),
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "[%s] provider payload callback failed after zlhub submit | task_id=%s error=%s",
                        log_tag,
                        task_id,
                        callback_err,
                    )

            if pure_callback_mode and callback_enabled:
                logger.info(
                    "[ZLHub] pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s",
                    task_id,
                    callback_ticket or None,
                    callback_url or None,
                )
                pending_meta = dict(extra_metadata or {})
                pending_meta.update(
                    {
                        "raw": data,
                        "submit_raw": data,
                        "task_id": str(task_id),
                        "taskId": str(task_id),
                        "pending_callback": True,
                        "callback_ticket": callback_ticket,
                        "callback_url": callback_url,
                    }
                )
                return {
                    "pending_callback": True,
                    "provider_task_id": str(task_id),
                    "metadata": pending_meta,
                }

            if is_seedance2:
                logger.info(
                    "[ZLHubSeedance2] task_id_acquired | trace_id=%s task_id=%s timeout_s=%s interval_s=%s",
                    trace_id,
                    task_id,
                    poll_timeout_seconds,
                    poll_interval_seconds,
                )

            max_attempts = max(1, int(poll_timeout_seconds / max(1, poll_interval_seconds)))
            for attempt in range(1, max_attempts + 1):
                await asyncio.sleep(poll_interval_seconds)
                try:
                    p_resp = await asyncio.to_thread(_poll, task_id, True)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                    p_resp = await asyncio.to_thread(_poll, task_id, False)
                except requests.exceptions.Timeout:
                    if is_seedance2 and (attempt == 1 or attempt % 5 == 0):
                        logger.warning(
                            "[ZLHubSeedance2] poll_timeout | trace_id=%s task_id=%s attempt=%s/%s",
                            trace_id,
                            task_id,
                            attempt,
                            max_attempts,
                        )
                    continue

                if p_resp.status_code != 200:
                    if is_seedance2 and (attempt == 1 or attempt % 5 == 0):
                        logger.warning(
                            "[ZLHubSeedance2] poll_http_non200 | trace_id=%s task_id=%s attempt=%s/%s status=%s",
                            trace_id,
                            task_id,
                            attempt,
                            max_attempts,
                            p_resp.status_code,
                        )
                    continue

                try:
                    p_data = p_resp.json() if p_resp.content else {}
                except Exception:
                    continue

                container = p_data.get("data") if isinstance(p_data.get("data"), dict) else p_data
                status = str(
                    (container or {}).get("status")
                    or (container or {}).get("state")
                    or p_data.get("status")
                    or p_data.get("state")
                    or ""
                ).strip().lower()
                media_url = None

                if is_seedance2 and (attempt == 1 or attempt % 5 == 0 or status in {"succeeded", "success", "completed", "done", "failed", "error", "canceled", "cancelled", "rejected"}):
                    logger.info(
                        "[ZLHubSeedance2] poll_status | trace_id=%s task_id=%s attempt=%s/%s status=%s has_url=%s",
                        trace_id,
                        task_id,
                        attempt,
                        max_attempts,
                        status or "<empty>",
                        bool(media_url),
                    )

                content = (container or {}).get("content") if isinstance((container or {}).get("content"), dict) else {}
                if isinstance(content, dict):
                    media_url = content.get("video_url") or content.get("url")
                if not media_url and isinstance((container or {}).get("result"), dict):
                    media_url = (container or {}).get("result", {}).get("video_url") or (container or {}).get("result", {}).get("url")
                if not media_url:
                    media_url = (container or {}).get("video_url") or (container or {}).get("url") or p_data.get("video_url") or p_data.get("url")

                if status in {"succeeded", "success", "completed", "done"} or (not status and media_url):
                    if not media_url:
                        if is_seedance2:
                            logger.error(
                                "[ZLHubSeedance2] completed_without_url | trace_id=%s task_id=%s status=%s",
                                trace_id,
                                task_id,
                                status or "<empty>",
                            )
                        return {
                            "error": "Generation completed without video URL",
                            "details": p_data,
                            "submit_failed": True,
                        }
                    usage = _normalize_provider_task_usage(_extract_provider_task_usage(p_data))
                    if not usage:
                        try:
                            await asyncio.sleep(0.5)
                            try:
                                refresh_resp = await asyncio.to_thread(_poll, task_id, True)
                            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                                refresh_resp = await asyncio.to_thread(_poll, task_id, False)
                            if getattr(refresh_resp, "status_code", None) == 200:
                                refresh_data = refresh_resp.json() if refresh_resp.content else {}
                                if isinstance(refresh_data, dict):
                                    p_data = refresh_data
                                    usage = _normalize_provider_task_usage(_extract_provider_task_usage(refresh_data))
                        except Exception as usage_err:
                            logger.warning(
                                "[%s] zlhub task usage refresh failed | task_id=%s error=%s",
                                log_tag,
                                task_id,
                                usage_err,
                            )
                    metadata = {"raw": p_data, "submit_raw": data, "task_id": task_id, "taskId": str(task_id)}
                    if extra_metadata:
                        metadata.update(extra_metadata)
                        metadata["raw"] = p_data
                    metadata = _attach_provider_usage_metadata(
                        metadata,
                        usage=usage,
                        source="zlhub",
                        task_payload=p_data,
                    )
                    if is_seedance2:
                        logger.info(
                            "[ZLHubSeedance2] success | trace_id=%s task_id=%s media_url=%s usage_tokens=%s",
                            trace_id,
                            task_id,
                            _strip_query_from_log_url(media_url),
                            (usage or {}).get("total_tokens"),
                        )
                    return {"url": media_url, "metadata": metadata}

                if status in {"failed", "error", "canceled", "cancelled", "rejected"}:
                    if is_seedance2:
                        logger.error(
                            "[ZLHubSeedance2] failed | trace_id=%s task_id=%s status=%s raw=%s",
                            trace_id,
                            task_id,
                            status,
                            _strip_base64_from_log(p_data),
                        )
                    return {"error": "Generation Failed", "details": p_data}

            if is_seedance2:
                logger.error(
                    "[ZLHubSeedance2] timeout | trace_id=%s task_id=%s timeout_s=%s",
                    trace_id,
                    task_id,
                    poll_timeout_seconds,
                )
            return {"error": f"Timeout after {poll_timeout_seconds}s"}
        except requests.exceptions.RequestException as exc:
            if is_seedance2:
                logger.error(
                    "[ZLHubSeedance2] request_exception | trace_id=%s err=%s",
                    trace_id,
                    exc,
                )
            return {"error": "Upstream request failed", "details": str(exc), "submit_failed": True}
        except Exception as exc:
            if is_seedance2:
                logger.exception(
                    "[ZLHubSeedance2] unhandled_exception | trace_id=%s err=%s",
                    trace_id,
                    exc,
                )
            return {"error": str(exc), "submit_failed": True}

    async def _submit_and_poll_grsai(
        self,
        url,
        payload,
        api_key,
        result_url,
        is_video=False,
        extra_metadata=None,
        trace_id: Optional[str] = None,
        task_id_callback: Optional[Callable[[str], Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        pure_callback_mode: bool = False,
        callback_enabled: bool = False,
        callback_ticket: Optional[str] = None,
        callback_url: Optional[str] = None,
    ):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if extra_headers:
            for header_name, header_value in extra_headers.items():
                if header_name and header_value:
                    headers[str(header_name).strip()] = str(header_value).strip()
        trace_id = trace_id or f"grsai-{uuid.uuid4().hex[:10]}"
        logger.info(
            "[GrsaiTrace][%s] submit headers effective | content_type=%s auth_bearer=%s has_oss_id=%s has_oss_path=%s oss_id=%s oss_path=%s",
            trace_id,
            str(headers.get("Content-Type") or ""),
            str(headers.get("Authorization") or "").startswith("Bearer "),
            bool(str(headers.get("oss-id") or "").strip()),
            bool(str(headers.get("oss-path") or "").strip()),
            str(headers.get("oss-id") or "").strip(),
            str(headers.get("oss-path") or "").strip(),
        )
        payload_digest = hashlib.md5(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        payload_bytes = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        log_tag = "grsai_video" if is_video else "grsai_image"
        submit_connect_timeout = max(
            5,
            int(os.getenv("GRSAI_SUBMIT_CONNECT_TIMEOUT_SECONDS", str(DEFAULT_MEDIA_SUBMIT_CONNECT_TIMEOUT_SECONDS)) or DEFAULT_MEDIA_SUBMIT_CONNECT_TIMEOUT_SECONDS),
        )
        submit_io_timeout = max(
            15,
            int(os.getenv("GRSAI_SUBMIT_IO_TIMEOUT_SECONDS", str(DEFAULT_MEDIA_SUBMIT_IO_TIMEOUT_SECONDS)) or DEFAULT_MEDIA_SUBMIT_IO_TIMEOUT_SECONDS),
        )

        def _build_url_pairs(submit_url: str, poll_url: str):
            pairs = [(submit_url, poll_url)]
            host_pairs = [
                ("grsai.dakka.com.cn", "grsaiapi.com"),
                ("grsaiapi.com", "grsai.dakka.com.cn"),
            ]
            for source_host, target_host in host_pairs:
                if source_host in submit_url:
                    alt_submit = submit_url.replace(source_host, target_host)
                    alt_poll = poll_url.replace(source_host, target_host)
                    if (alt_submit, alt_poll) not in pairs:
                        pairs.append((alt_submit, alt_poll))
            return pairs

        upstream_candidates = _build_url_pairs(url, result_url)
        retryable_statuses = {502, 503, 504, 520, 521, 522, 523, 524, 525, 526}
        last_error = None

        for index, (submit_url, poll_url) in enumerate(upstream_candidates):

            def _post():
                return requests.post(submit_url, json=payload, headers=headers, timeout=(submit_connect_timeout, submit_io_timeout), verify=False)

            def _post_no_proxy():
                return requests.post(
                    submit_url,
                    json=payload,
                    headers=headers,
                    timeout=(submit_connect_timeout, submit_io_timeout),
                    verify=False,
                    proxies={"http": None, "https": None},
                )

            try:
                submit_started = time.perf_counter()
                logger.info(
                    "[GrsaiTrace][%s] submit begin | endpoint=%s candidate_index=%s payload_digest=%s payload_bytes=%s submit_timeouts=%s/%s",
                    trace_id,
                    submit_url,
                    index,
                    payload_digest,
                    payload_bytes,
                    submit_connect_timeout,
                    submit_io_timeout,
                )
                try:
                    resp = await asyncio.to_thread(_post)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError):
                    logger.warning("[GrsaiTrace][%s] submit primary failed, retry without proxy | submit_url=%s", trace_id, submit_url)
                    try:
                        resp = await asyncio.to_thread(_post_no_proxy)
                    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ambiguous_error:
                        return self._build_ambiguous_submit_result("grsai", log_tag, ambiguous_error, submit_url, extra_metadata)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ambiguous_error:
                    return self._build_ambiguous_submit_result("grsai", log_tag, ambiguous_error, submit_url, extra_metadata)
                submit_ms = int((time.perf_counter() - submit_started) * 1000)
                logger.info(
                    "[GrsaiTrace][%s] submit done | endpoint=%s status=%s latency_ms=%s",
                    trace_id,
                    submit_url,
                    getattr(resp, "status_code", None),
                    submit_ms,
                )
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                logger.error("[GrsaiTrace][%s] submit network_error | submit_url=%s error=%s", trace_id, submit_url, last_error)
                continue

            if resp.status_code != 200:
                if resp.status_code == 429 or self._is_grsai_quota_or_throttle_error(resp.text):
                    logger.error("[GrsaiTrace][%s] submit throttled_or_quota | status=%s body=%s", trace_id, resp.status_code, (resp.text or "")[:500])
                    return {
                        "error": "Veo/Grsai 配额或频率受限",
                        "details": "上游返回 429 RESOURCE_EXHAUSTED（请求过于频繁或额度耗尽）。请降低并发、等待冷却或提升配额后重试。",
                        "submit_failed": True,
                    }
                if resp.status_code in retryable_statuses and index < len(upstream_candidates) - 1:
                    last_error = f"Submission Failed {resp.status_code}: {resp.text[:300]}"
                    logger.warning(
                        "[GrsaiTrace][%s] submit retryable_status | status=%s next_try=%s",
                        trace_id,
                        resp.status_code,
                        True,
                    )
                    continue
                logger.error(
                    "[GrsaiTrace][%s] submit failed_status | status=%s detail=%s",
                    trace_id,
                    resp.status_code,
                    (resp.text or "")[:500],
                )
                return {"error": f"Submission Failed {resp.status_code}", "details": resp.text, "submit_failed": True}

            try:
                data = resp.json()
            except Exception:
                return {"error": "Invalid Grsai response", "details": resp.text[:1000], "submit_failed": True}

            data_obj = data.get("data")
            if data_obj is None:
                msg = data.get("msg") or data.get("message") or "Unknown Error"
                return {"error": f"API Error {data.get('code')}", "details": msg, "submit_failed": True}

            task_id = None
            if isinstance(data_obj, dict):
                task_id = data_obj.get("id") or data_obj.get("task_id") or data_obj.get("taskId")
                if not task_id and isinstance(data_obj.get("data"), dict):
                    nested = data_obj.get("data") or {}
                    task_id = nested.get("id") or nested.get("task_id") or nested.get("taskId")
            elif isinstance(data_obj, str):
                task_id = data_obj.strip()
            elif isinstance(data_obj, list) and len(data_obj) > 0:
                first = data_obj[0]
                if isinstance(first, dict):
                    task_id = first.get("id") or first.get("task_id") or first.get("taskId")
                elif isinstance(first, str):
                    task_id = first.strip()

            if not task_id:
                task_id = data.get("id") or data.get("task_id") or data.get("taskId")

            if not task_id:
                logger.error("[GrsaiTrace][%s] submit missing_task_id | response=%s", trace_id, str(data)[:1000])
                return {"error": "No Task ID", "details": data, "submit_failed": True}

            if callable(task_id_callback):
                try:
                    callback_result = task_id_callback(str(task_id))
                    if asyncio.iscoroutine(callback_result):
                        await callback_result
                except Exception as callback_err:
                    logger.warning(
                        "[GrsaiTrace][%s] task_id_callback_failed | task_id=%s error=%s",
                        trace_id,
                        task_id,
                        callback_err,
                    )

            if pure_callback_mode and callback_enabled:
                logger.info(
                    "[GrsaiTrace][%s] pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s is_video=%s",
                    trace_id,
                    task_id,
                    callback_ticket or None,
                    _strip_query_from_log_url(callback_url),
                    bool(is_video),
                )
                pending_meta = dict(extra_metadata or {})
                pending_meta.update(
                    {
                        "raw": data,
                        "submit_raw": data,
                        "task_id": str(task_id),
                        "taskId": str(task_id),
                        "pending_callback": True,
                        "callback_ticket": callback_ticket,
                        "callback_url": callback_url,
                    }
                )
                return {
                    "pending_callback": True,
                    "provider_task_id": str(task_id),
                    "metadata": pending_meta,
                }

            for i in range(150):
                await asyncio.sleep(5)

                def _poll():
                    return requests.post(poll_url, json={"id": task_id}, headers=headers, timeout=(10, 30), verify=False)

                try:
                    p_resp = await asyncio.to_thread(_poll)
                except requests.exceptions.Timeout:
                    continue
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    if i < 95:
                        continue
                    return {"error": "Grsai poll failed", "details": last_error}

                if p_resp.status_code == 200:
                    try:
                        p_data = p_resp.json()
                    except Exception:
                        continue

                    data_block = p_data.get("data")
                    status = None
                    media_url = None

                    if isinstance(data_block, dict):
                        status = data_block.get("status") or p_data.get("status")
                        results = data_block.get("results")
                        if isinstance(results, list) and results:
                            first_result = results[0] if isinstance(results[0], dict) else {}
                            media_url = first_result.get("url") or first_result.get("imageUrl") or first_result.get("videoUrl")
                        if not media_url:
                            media_url = (
                                data_block.get("url")
                                or data_block.get("imageUrl")
                                or data_block.get("videoUrl")
                                or data_block.get("result_url")
                            )
                    elif isinstance(data_block, list) and data_block:
                        first_item = data_block[0]
                        if isinstance(first_item, dict):
                            status = first_item.get("status") or p_data.get("status")
                            media_url = (
                                first_item.get("url")
                                or first_item.get("imageUrl")
                                or first_item.get("videoUrl")
                                or first_item.get("result_url")
                            )

                    status_l = str(status or "").lower()
                    if status_l in {"succeeded", "success", "completed", "done"} or (not status_l and media_url):
                        if media_url:
                            resolved_media_url = str(media_url)
                            if oss_storage_service.is_managed_url(resolved_media_url):
                                resolved_media_url = str(oss_storage_service.refresh_url(resolved_media_url) or resolved_media_url)
                            meta = {"raw": p_data, "submit_raw": data, "task_id": task_id, "taskId": task_id}
                            if extra_metadata:
                                meta.update(extra_metadata)
                            return {"url": resolved_media_url, "metadata": meta}
                    elif status_l in {"failed", "error", "canceled", "cancelled"}:
                        if self._is_grsai_quota_or_throttle_error(p_data):
                            return {
                                "error": "Veo/Grsai 配额或频率受限",
                                "details": "任务失败原因为 429 RESOURCE_EXHAUSTED（上传图片或生成请求被限流/额度不足）。请稍后重试或调整账号配额。",
                            }
                        return {"error": "Generation Failed", "details": p_data}

            last_error = "Timeout"

        if last_error:
            return {"error": "Grsai request failed", "details": last_error, "submit_failed": True}
        return {"error": "Grsai request failed", "details": "All upstream endpoints failed", "submit_failed": True}

    def _extract_urls_from_payload(self, value: Any) -> List[str]:
        urls: List[str] = []

        def _walk(node: Any):
            if node is None:
                return
            if isinstance(node, str):
                text = node.strip()
                if text.startswith("http://") or text.startswith("https://"):
                    urls.append(text)
                    return
                if text and (text.startswith("{") or text.startswith("[")):
                    try:
                        parsed = json.loads(text)
                    except Exception:
                        return
                    _walk(parsed)
                return
            if isinstance(node, dict):
                for item in node.values():
                    _walk(item)
                return
            if isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(value)

        deduped: List[str] = []
        seen = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped

    async def _handle_kie_generation(
        self,
        gen_type,
        prompt,
        config,
        ref_image=None,
        last_frame_url=None,
        duration=5,
        aspect_ratio=None,
        negative_prompt: Optional[str] = None,
        image_size: Optional[str] = None,
    ):
        api_key = (config.get("api_key") or "").strip()
        if not api_key:
            return {"error": "Missing KIE API key", "submit_failed": True}

        model = (config.get("model") or "").strip() or ("flux-kontext-pro" if gen_type == "image" else "veo-3-1-fast")
        model_alias = {
            "veo-3-1-fast": "veo-3-1-fast",
            "veo3-fast": "veo-3-1-fast",
            "veo-3-fast": "veo-3-1-fast",
            "veo3": "veo3",
            "veo-3": "veo3",
            "veo": "veo3",
            "veo-3.1": "veo3",
            "veo3.1": "veo3",

            "klingv2.5": "kling-v2.5",
            "klingv2.1": "kling-v2.1",
            "kling3": "kling-3.0/video",
            "kling3.0": "kling-3.0/video",
            "kling-3.0": "kling-3.0/video",
            "kling-3-0": "kling-3.0/video",
            "kling-3.0/video": "kling-3.0/video",
            "kling/2.6-text-to-video": "kling-2.6/text-to-video",
            "kling/2.6-image-to-video": "kling-2.6/image-to-video",
            "kling/2.6-motion-control": "kling-2.6/motion-control",
            "kling/v25-turbo-text-to-video-pro": "kling/v2-5-turbo-text-to-video-pro",
            "kling/v25-turbo-image-to-video-pro": "kling/v2-5-turbo-image-to-video-pro",

            "grok-imagine": "grok-imagine/text-to-image",
            "grok-imagine-t2i": "grok-imagine/text-to-image",
            "grok-imagine-i2i": "grok-imagine/image-to-image",
            "qwen-image": "qwen/text-to-image",
            "qwen-i2i": "qwen/image-to-image",
            "qwen-edit": "qwen/image-edit",
            "imagen4-fast": "google/imagen4-fast",
            "imagen4-ultra": "google/imagen4-ultra",
            "imagen4": "google/imagen4",
            "nano-banana": "google/nano-banana",
            "nano-banana-edit": "google/nano-banana-edit",
            "nanobanana2": "google/nanobanana2",
            "seedream4.5": "seedream/4.5-text-to-image",
            "seedream4.5-edit": "seedream/4.5-edit",
            "seedream5-lite": "seedream/5-lite-text-to-image",
            "seedream5-lite-i2i": "seedream/5-lite-image-to-image",
            "seedream/5-lite-text-to-image": "seedream/5-lite-text-to-image",
            "seedream/5-lite-image-to-image": "seedream/5-lite-image-to-image",
            "flux2-pro": "flux-2/pro-text-to-image",
            "flux2-pro-i2i": "flux-2/pro-image-to-image",
            "flux2-flex": "flux-2/flex-text-to-image",
            "flux2-flex-i2i": "flux-2/flex-image-to-image",
            "gpt-image-1.5": "gpt-image/1.5-text-to-image",
            "gpt-image-1.5-i2i": "gpt-image/1.5-image-to-image",
            "gpt-image/1-5-text-to-image": "gpt-image/1.5-text-to-image",
            "gpt-image/1-5-image-to-image": "gpt-image/1.5-image-to-image",

            "sora2": "sora-2-text-to-video",
            "sora2-t2v": "sora-2-text-to-video",
            "sora2-i2v": "sora-2-image-to-video",
            "sora2-pro": "sora-2-pro-text-to-video",
            "sora2-pro-i2v": "sora-2-pro-image-to-video",
            "bytedance-v1-pro": "bytedance/v1-pro-text-to-video",
            "bytedance-v1-pro-i2v": "bytedance/v1-pro-image-to-video",
            "bytedance-v1-pro-fast-i2v": "bytedance/v1-pro-fast-image-to-video",
            "bytedance-v1-lite": "bytedance/v1-lite-text-to-video",
            "bytedance-v1-lite-i2v": "bytedance/v1-lite-image-to-video",
            "hailuo": "hailuo/02-text-to-video-pro",
            "hailuo-pro-i2v": "hailuo/02-image-to-video-pro",
            "hailuo-standard": "hailuo/02-text-to-video-standard",
            "hailuo-standard-i2v": "hailuo/02-image-to-video-standard",
            "hailuo-2.3-pro": "hailuo/2-3-image-to-video-pro",
            "hailuo-2.3-standard": "hailuo/2-3-image-to-video-standard",
            "wan-turbo": "wan/2-6-text-to-video",
            "wan-i2v": "wan/2-6-image-to-video",
            "wan-v2v": "wan/2-6-video-to-video",
            "wan-a14b-t2v": "wan/2-2-a14b-text-to-video-turbo",
            "wan-a14b-i2v": "wan/2-2-a14b-image-to-video-turbo",
            "wan-a14b-s2v": "wan/2-2-a14b-speech-to-video-turbo",
            "wan-flash-i2v": "wan/2-6-flash-image-to-video",
            "wan-flash-v2v": "wan/2-6-flash-video-to-video",
            "grok-imagine-video": "grok-imagine/text-to-video",
            "gemini-omni-video": "gemini-omni-video",
            "topaz-video-upscale": "topaz/video-upscale",
            "topaz/video-upscale": "topaz/video-upscale",
        }
        if gen_type in {"video", "image"}:
            remapped_model = model_alias.get(str(model or "").strip().lower())
            if remapped_model:
                logger.warning(
                    "KIE legacy model remapped | from=%s to=%s",
                    model,
                    remapped_model,
                )
                model = remapped_model

        # Capture after alias remap, before modality auto-switch (t2v→i2v / t2i→i2i).
        initial_submitted_model = str(model or "").strip()

        # ── Modality-aware model switching for KIE video ──
        # When a reference image is provided, auto-switch text-to-video models to
        # their image-to-video counterpart so the image is actually used as input.
        if gen_type == "video" and ref_image:
            has_ref = bool(ref_image if not isinstance(ref_image, list) else any(ref_image))
            if has_ref:
                _t2v_to_i2v_map = {
                    "sora-2-text-to-video":                  "sora-2-image-to-video",
                    "sora-2-pro-text-to-video":              "sora-2-pro-image-to-video",
                    "bytedance/v1-pro-text-to-video":        "bytedance/v1-pro-image-to-video",
                    "bytedance/v1-lite-text-to-video":       "bytedance/v1-lite-image-to-video",
                    "hailuo/02-text-to-video-pro":           "hailuo/02-image-to-video-pro",
                    "hailuo/02-text-to-video-standard":      "hailuo/02-image-to-video-standard",
                    "wan/2-6-text-to-video":                 "wan/2-6-image-to-video",
                    "wan/2-2-a14b-text-to-video-turbo":      "wan/2-2-a14b-image-to-video-turbo",
                    "kling-2.6/text-to-video":               "kling-2.6/image-to-video",
                    "kling/v2-5-turbo-text-to-video-pro":    "kling/v2-5-turbo-image-to-video-pro",
                    "kling/v2-1-master-text-to-video":       "kling/v2-1-master-image-to-video",
                    "grok-imagine/text-to-video":            "grok-imagine/image-to-video",
                }
                i2v_model = _t2v_to_i2v_map.get(str(model or "").strip().lower())
                if i2v_model:
                    logger.info(
                        "KIE modality switch t2v→i2v | from=%s to=%s reason=reference_image_provided",
                        model,
                        i2v_model,
                    )
                    model = i2v_model

        # ── Modality-aware model switching for KIE image ──
        # When a reference image is provided, auto-switch text-to-image models to
        # their image-to-image counterpart.
        if gen_type == "image" and ref_image:
            has_ref = bool(ref_image if not isinstance(ref_image, list) else any(ref_image))
            if has_ref:
                _t2i_to_i2i_map = {
                    "grok-imagine/text-to-image":     "grok-imagine/image-to-image",
                    "qwen/text-to-image":             "qwen/image-to-image",
                    "seedream/4.5-text-to-image":     "seedream/4.5-edit",
                    "seedream/5-lite-text-to-image":  "seedream/5-lite-image-to-image",
                    "flux-2/pro-text-to-image":       "flux-2/pro-image-to-image",
                    "flux-2/flex-text-to-image":      "flux-2/flex-image-to-image",
                    "gpt-image/1.5-text-to-image":    "gpt-image/1.5-image-to-image",
                    "gpt-image/1-5-text-to-image":    "gpt-image/1.5-image-to-image",
                }
                i2i_model = _t2i_to_i2i_map.get(str(model or "").strip().lower())
                if i2i_model:
                    logger.info(
                        "KIE modality switch t2i→i2i | from=%s to=%s reason=reference_image_provided",
                        model,
                        i2i_model,
                    )
                    model = i2i_model

        tool_conf = config.get("config", {}) or {}
        subject_type_hint = str(tool_conf.get("__subject_type") or "").strip().lower() or None
        subject_name_hint = str(
            tool_conf.get("__subject_name")
            or tool_conf.get("subject_name")
            or tool_conf.get("entity_name")
            or tool_conf.get("name")
            or ""
        ).strip() or None
        prompt = self._sanitize_kie_placeholder_prompt(prompt, subject_type_hint, subject_name_hint)
        prompt = self._merge_negative_prompt(prompt, negative_prompt)

        # Fix 422: "kling_elements is required when prompt contains role references like @element_dog"
        # KIE validates all video API calls using its unified proxy struct which treats `@` as kling elements.
        prompt = self._sanitize_kie_prompt_mentions(prompt, tool_conf)
        raw_multi_prompt = tool_conf.get("multi_prompt")
        if isinstance(raw_multi_prompt, list):
            for mp in raw_multi_prompt:
                if isinstance(mp, dict) and isinstance(mp.get("prompt"), str):
                    mp["prompt"] = self._sanitize_kie_prompt_mentions(mp["prompt"], tool_conf)

        resolved_setting_id = None
        try:
            resolved_setting_id = int((tool_conf or {}).get("__resolved_setting_id") or 0)
        except Exception:
            resolved_setting_id = None
        runtime_enum_catalog = self._load_system_api_runtime_enum_catalog(resolved_setting_id)

        model_lower = str(model or "").strip().lower()
        use_veo_api = bool(gen_type == "video" and model_lower.startswith("veo"))
        use_runway_api = bool(gen_type == "video" and "runway" in model_lower)
        use_4o_image_api = bool(gen_type == "image" and ("gpt4o-image" in model_lower or "4o-image" in model_lower))
        use_flux_kontext_api = bool(gen_type == "image" and ("flux-kontext" in model_lower or "flux/kontext" in model_lower))
        use_suno_api = bool(gen_type == "audio" and "suno" in model_lower)
        is_sora2_video_model = bool(gen_type == "video" and model_lower.startswith("sora-2"))
        is_kling_3_video = bool(gen_type == "video" and ("kling-3.0" in model_lower or model_lower == "kling3"))
        is_kling_26_i2v_model = bool(gen_type == "video" and model_lower == "kling-2.6/image-to-video")
        is_seedance_video_model = bool(gen_type == "video" and model_lower.startswith("bytedance/seedance"))
        is_gemini_omni_video_model = bool(gen_type == "video" and model_lower == "gemini-omni-video")
        is_topaz_video_upscale = bool(gen_type == "video" and str(model_lower or "").strip() == "topaz/video-upscale")
        is_flux2_image_model = bool(gen_type == "image" and str(model_lower or "").startswith("flux-2/"))
        # KIE market video endpoints require duration as string for compatibility across models.
        duration_string_required_model = bool(gen_type == "video" and not is_topaz_video_upscale)

        base_url = (config.get("base_url") or tool_conf.get("base_url") or "https://api.kie.ai").strip().rstrip("/")
        if "/api/v1/jobs" in base_url:
            base_url = base_url.split("/api/v1/jobs")[0]
            
        for suffix in ["/api/v1/veo", "/api/v1/runway", "/api/v1/flux/kontext", "/api/v1/gpt4o-image", "/api/v1/generate"]:
            if base_url.endswith(suffix):
                base_url = base_url[:-len(suffix)]

        submit_url = (tool_conf.get("endpoint") or f"{base_url}/api/v1/jobs/createTask").strip()
        query_url = (tool_conf.get("query_endpoint") or f"{base_url}/api/v1/jobs/recordInfo").strip()
        if use_veo_api:
            submit_url = (tool_conf.get("veo_endpoint") or f"{base_url}/api/v1/veo/generate").strip()
            query_url = (tool_conf.get("veo_query_endpoint") or f"{base_url}/api/v1/veo/record-info").strip()
        elif use_runway_api:
            submit_url = (tool_conf.get("runway_endpoint") or f"{base_url}/api/v1/runway/generate").strip()
            query_url = (tool_conf.get("runway_query_endpoint") or f"{base_url}/api/v1/runway/record-detail").strip()
        elif use_4o_image_api:
            submit_url = (tool_conf.get("gpt4o_image_endpoint") or f"{base_url}/api/v1/gpt4o-image/generate").strip()
            query_url = (tool_conf.get("gpt4o_image_query_endpoint") or f"{base_url}/api/v1/gpt4o-image/record-info").strip()
        elif use_flux_kontext_api:
            submit_url = (tool_conf.get("flux_kontext_endpoint") or f"{base_url}/api/v1/flux/kontext/generate").strip()
            query_url = (tool_conf.get("flux_kontext_query_endpoint") or f"{base_url}/api/v1/flux/kontext/record-info").strip()
        elif use_suno_api:
            submit_url = (tool_conf.get("suno_endpoint") or f"{base_url}/api/v1/generate").strip()
            query_url = (tool_conf.get("suno_query_endpoint") or f"{base_url}/api/v1/record-info").strip()  # Needs verification

        route_mode = "market"
        if use_veo_api: route_mode = "veo"
        elif use_runway_api: route_mode = "runway"
        elif use_4o_image_api: route_mode = "4o_image"
        elif use_flux_kontext_api: route_mode = "flux_kontext"
        elif use_suno_api: route_mode = "suno"
        
        logger.info(
            "KIE route selected | mode=%s model=%s submit_url=%s query_url=%s",
            route_mode,
            model,
            submit_url,
            query_url,
        )

        payload_input: Dict[str, Any] = {
            "prompt": prompt,
        }

        if is_sora2_video_model:
            sora_mention_cfg = self._resolve_sora_mention_config(tool_conf if isinstance(tool_conf, dict) else {})
            if sora_mention_cfg.get("auto_use_sora_mention"):
                logger.info(
                    "Sora mention mode enabled | model=%s auto_upload_character=%s",
                    model,
                    bool(sora_mention_cfg.get("auto_upload_character")),
                )
            else:
                sanitized_prompt = self._sanitize_sora_prompt_mentions(prompt)
                if sanitized_prompt and sanitized_prompt != str(prompt or ""):
                    payload_input["prompt"] = sanitized_prompt
                    logger.warning(
                        "Sora prompt mention sanitizer applied | model=%s removed_at_mentions=%s",
                        model,
                        str(prompt or "").count("@"),
                    )

        requested_mode = str(tool_conf.get("mode") or "").strip().lower()
        mode_source_hint = str(tool_conf.get("__mode_source") or "").strip().lower()

        if not requested_mode:
            mode_binding_raw = (
                tool_conf.get("model_mode_defaults")
                or tool_conf.get("mode_by_model")
                or tool_conf.get("default_mode_by_model")
                or tool_conf.get("model_mode_bindings")
            )
            if isinstance(mode_binding_raw, dict):
                lookup_keys = [
                    str(model or "").strip(),
                    str(model or "").strip().lower(),
                    str(initial_submitted_model or "").strip(),
                    str(initial_submitted_model or "").strip().lower(),
                ]
                for lookup_key in lookup_keys:
                    if not lookup_key:
                        continue
                    bound_mode = mode_binding_raw.get(lookup_key)
                    if bound_mode is None:
                        continue
                    candidate_mode = str(bound_mode).strip().lower()
                    if candidate_mode:
                        requested_mode = candidate_mode
                        mode_source_hint = "settings_model_binding"
                        break

        allowed_modes = [str(item or "").strip().lower() for item in runtime_enum_catalog.get("mode") or [] if str(item or "").strip()]
        if requested_mode and allowed_modes:
            mapped_mode = self._map_mode_to_allowed(requested_mode, runtime_enum_catalog.get("mode"))
            mapped_mode_lower = str(mapped_mode or "").strip().lower()
            if mapped_mode_lower and mapped_mode_lower != requested_mode:
                fallback_mode = mapped_mode_lower
                logger.warning(
                    "KIE mode enum remap | model=%s requested=%s allowed=%s mapped=%s",
                    model,
                    requested_mode,
                    allowed_modes,
                    fallback_mode,
                )
                requested_mode = fallback_mode
                mode_source_hint = "enum_fallback"
            elif requested_mode not in allowed_modes:
                fallback_mode = allowed_modes[0]
                logger.warning(
                    "KIE mode enum fallback | model=%s requested=%s allowed=%s fallback=%s",
                    model,
                    requested_mode,
                    allowed_modes,
                    fallback_mode,
                )
                requested_mode = fallback_mode
                mode_source_hint = "enum_fallback"

        if requested_mode:
            payload_input["mode"] = requested_mode

        if gen_type == "audio":
            forced_submit_text = str(tool_conf.get("__voice_submit_text") or "").strip()
            strict_text_only = bool(tool_conf.get("__voice_strict_text_only"))
            effective_submit_text = forced_submit_text or str(prompt or "").strip()
            timestamps_supported = self._get_runtime_capability_flag(
                config,
                "supports_timestamps",
                "timestamps_supported",
            )
            previous_text_supported = self._get_runtime_capability_flag(
                config,
                "supports_previous_text",
                "previous_text_supported",
                "supports_context_text",
                "context_text_supported",
            )
            allowed_voice_values = runtime_enum_catalog.get("voice") or self._get_runtime_capability_list(
                config,
                "voice_values",
                "voices",
                "allowed_voices",
                "supported_voices",
            )
            allowed_language_values = runtime_enum_catalog.get("language_code") or self._get_runtime_capability_list(
                config,
                "language_code_values",
                "language_values",
                "languages",
                "allowed_languages",
                "supported_languages",
            )
            stability_min = self._get_runtime_capability_number(config, "stability_min")
            stability_max = self._get_runtime_capability_number(config, "stability_max")
            similarity_min = self._get_runtime_capability_number(config, "similarity_boost_min")
            similarity_max = self._get_runtime_capability_number(config, "similarity_boost_max")
            style_min = self._get_runtime_capability_number(config, "style_min")
            style_max = self._get_runtime_capability_number(config, "style_max")
            speed_min = self._get_runtime_capability_number(config, "speed_min")
            speed_max = self._get_runtime_capability_number(config, "speed_max")
            next_text_supported = self._get_runtime_capability_flag(
                config,
                "supports_next_text",
                "next_text_supported",
                "supports_context_text",
                "context_text_supported",
            )

            payload_input["prompt"] = effective_submit_text
            payload_input["text"] = effective_submit_text

            # Keep backward compatibility for legacy non-strict flows only.
            if not strict_text_only and tool_conf.get("text") is not None and str(tool_conf.get("text") or "").strip():
                payload_input["text"] = str(tool_conf.get("text") or "").strip()
            if not strict_text_only and tool_conf.get("prompt") is not None and str(tool_conf.get("prompt") or "").strip():
                payload_input["prompt"] = str(tool_conf.get("prompt") or "").strip()

            for key in ["voice", "language_code", "previous_text", "next_text"]:
                if key == "previous_text" and previous_text_supported is False:
                    continue
                if key == "next_text" and next_text_supported is False:
                    continue
                if tool_conf.get(key) is not None and str(tool_conf.get(key)).strip() != "":
                    payload_input[key] = tool_conf.get(key)

            # Compatibility alias: if caller passes "language", map to docs field "language_code".
            if tool_conf.get("language") is not None and str(tool_conf.get("language")).strip() != "":
                payload_input["language_code"] = str(tool_conf.get("language")).strip()

            mapped_voice = self._map_text_value_to_allowed(payload_input.get("voice"), allowed_voice_values)
            if mapped_voice:
                payload_input["voice"] = mapped_voice

            mapped_language = self._map_text_value_to_allowed(payload_input.get("language_code"), allowed_language_values)
            if mapped_language:
                payload_input["language_code"] = mapped_language

            def _set_float(key: str, min_val: float, max_val: float):
                raw = tool_conf.get(key)
                if raw is None or str(raw).strip() == "":
                    return
                try:
                    value = float(raw)
                    value = max(min_val, min(max_val, value))
                    payload_input[key] = value
                except Exception:
                    pass

            _set_float("stability", stability_min if stability_min is not None else 0.0, stability_max if stability_max is not None else 1.0)
            _set_float("similarity_boost", similarity_min if similarity_min is not None else 0.0, similarity_max if similarity_max is not None else 1.0)
            _set_float("style", style_min if style_min is not None else 0.0, style_max if style_max is not None else 1.0)
            _set_float("speed", speed_min if speed_min is not None else 0.7, speed_max if speed_max is not None else 1.2)

            if timestamps_supported is not False and tool_conf.get("timestamps") is not None:
                payload_input["timestamps"] = bool(tool_conf.get("timestamps"))

        raw_ar = str(aspect_ratio or "").strip()
        normalized_ar = self._normalize_aspect_ratio_value(aspect_ratio)
        if use_veo_api and raw_ar.lower() in {"auto", "adaptive"}:
            normalized_ar = "Auto"
        allowed_aspect_ratios = [str(item or "").strip() for item in runtime_enum_catalog.get("aspect_ratio") or [] if str(item or "").strip()]
        if normalized_ar and allowed_aspect_ratios:
            mapped_ar = self._map_aspect_ratio_to_allowed(normalized_ar, runtime_enum_catalog.get("aspect_ratio"))
            if mapped_ar and str(mapped_ar).strip() and str(mapped_ar).strip().lower() != str(normalized_ar).strip().lower():
                logger.warning(
                    "KIE aspect_ratio enum remap | model=%s requested=%s allowed=%s mapped=%s",
                    model,
                    normalized_ar,
                    allowed_aspect_ratios,
                    mapped_ar,
                )
                normalized_ar = str(mapped_ar).strip()
            elif not mapped_ar:
                fallback_ar = allowed_aspect_ratios[0]
                logger.warning(
                    "KIE aspect_ratio enum fallback | model=%s requested=%s allowed=%s fallback=%s",
                    model,
                    normalized_ar,
                    allowed_aspect_ratios,
                    fallback_ar,
                )
                normalized_ar = fallback_ar
        if normalized_ar:
            payload_input["aspect_ratio"] = normalized_ar

        is_gpt_image_15_i2i = bool(
            gen_type == "image"
            and str(model_lower or "").strip().lower() in {"gpt-image/1.5-image-to-image", "gpt-image/1-5-image-to-image"}
        )
        is_gpt_image_2_i2i = bool(
            gen_type == "image"
            and str(model_lower or "").strip().lower() in {"gpt-image/2-image-to-image", "gpt-image-2-image-to-image"}
        )
        is_gpt_image_2 = bool(
            gen_type == "image"
            and str(model_lower or "").strip().lower().replace("/", "-").startswith("gpt-image-2")
        )
        is_seedream_5_lite_i2i = bool(
            gen_type == "image"
            and str(model_lower or "").strip().lower() in {"seedream/5-lite-image-to-image"}
        )
        is_grok_imagine_i2i = bool(
            gen_type == "image"
            and str(model_lower or "").strip().lower() in {"grok-imagine/image-to-image"}
        )

        is_gpt_image_family = bool(
            gen_type == "image"
            and ("gpt-image" in str(model_lower or "").strip().lower() or "gpt4o-image" in str(model_lower or "").strip().lower())
        )
        is_gemini_image = bool(
            gen_type == "image"
            and "gemini" in str(model_lower or "").strip().lower()
        )

        if gen_type == "image":
            if is_gemini_image:
                payload_input["image_size"] = str(tool_conf.get("image_size") or payload_input.get("image_size") or "2k").strip().lower()
            if is_gpt_image_family:
                quality_val = str(tool_conf.get("quality") or payload_input.get("quality") or "").strip().lower()
                if quality_val not in {"auto", "low", "medium", "high"}:
                    quality_val = "high"
                payload_input["quality"] = quality_val

            # z-image family requires aspect_ratio in input (per KIE API examples).
            # Keep a safe default to avoid "This field is required" errors when ratio
            # is not provided by upstream context.
            is_z_image_model = str(model_lower or "").startswith("z-image")
            if is_z_image_model:
                payload_input["aspect_ratio"] = str(payload_input.get("aspect_ratio") or "1:1").strip() or "1:1"
                payload_input.pop("image_size", None)
            elif is_gpt_image_2:
                ar_val = str(payload_input.pop("aspect_ratio", "")).strip()
                if ar_val == "16:9": res_str = "2560x1440"
                elif ar_val == "9:16": res_str = "720x1280"
                elif ar_val == "4:3": res_str = "1024x768"
                elif ar_val == "3:4": res_str = "768x1024"
                elif ar_val == "21:9": res_str = "1536x640" 
                else: res_str = "2560x1440"
                payload_input["size"] = res_str
                payload_input.pop("image_size", None)
            elif is_gpt_image_15_i2i or is_gpt_image_2_i2i:
                # KIE 1.5/2.0 Image-To-Image contract:
                # model=gpt-image-2-image-to-image, input.input_urls, input.aspect_ratio, input.quality
                if is_gpt_image_2_i2i:
                    payload_input["aspect_ratio"] = "auto"
                else:
                    allowed_ar = {"1:1", "2:3", "3:2"}
                    ar_val = str(payload_input.get("aspect_ratio") or "").strip()
                    if ar_val not in allowed_ar:
                        ar_val = "3:2"
                    payload_input["aspect_ratio"] = ar_val

                payload_input.pop("image_size", None)
            elif is_seedream_5_lite_i2i:
                # KIE Seedream 5-lite I2I contract:
                # model=seedream/5-lite-image-to-image, input.image_urls, input.aspect_ratio, input.quality
                allowed_ar = {"1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"}
                ar_val = str(payload_input.get("aspect_ratio") or "").strip()
                if ar_val not in allowed_ar:
                    ar_val = "1:1"
                payload_input["aspect_ratio"] = ar_val

                quality_val = str(tool_conf.get("quality") or payload_input.get("quality") or "").strip().lower()
                if quality_val not in {"basic", "high"}:
                    quality_val = "basic"
                payload_input["quality"] = quality_val

                payload_input.pop("image_size", None)
            elif is_flux2_image_model:
                # KIE Flux-2 contract: input.resolution required (1K|2K), not image_size.
                kie_resolution = self._normalize_image_size_value(
                    image_size or tool_conf.get("image_size") or tool_conf.get("resolution")
                ) or "1K"
                allowed_flux2_resolutions = [
                    str(item or "").strip()
                    for item in runtime_enum_catalog.get("resolution") or []
                    if str(item or "").strip()
                ]
                if allowed_flux2_resolutions:
                    mapped_resolution = self._map_resolution_to_allowed(
                        kie_resolution,
                        runtime_enum_catalog.get("resolution"),
                    )
                    if mapped_resolution:
                        kie_resolution = str(mapped_resolution).strip()
                    elif kie_resolution.upper() not in {v.upper() for v in allowed_flux2_resolutions}:
                        kie_resolution = allowed_flux2_resolutions[0]
                kie_resolution = str(kie_resolution).strip().upper()
                if kie_resolution not in {"1K", "2K"}:
                    kie_resolution = "1K"
                payload_input["resolution"] = kie_resolution
                payload_input.pop("image_size", None)

                allowed_flux2_ar = {"1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"}
                ar_val = str(payload_input.get("aspect_ratio") or "").strip()
                if ar_val not in allowed_flux2_ar:
                    payload_input["aspect_ratio"] = "1:1"
            else:
                # Other KIE market image models may still expect image_size-style input.
                # Use resolution tier only when an actual size tier is available.
                kie_image_size = self._normalize_image_size_value(
                    image_size or tool_conf.get("image_size") or tool_conf.get("imageSize")
                )
                allowed_image_sizes = [str(item or "").strip().lower() for item in runtime_enum_catalog.get("image_size") or [] if str(item or "").strip()]
                if kie_image_size and allowed_image_sizes:
                    mapped_image_size = self._map_image_size_to_allowed(kie_image_size, runtime_enum_catalog.get("image_size"))
                    if mapped_image_size and str(mapped_image_size).strip().lower() != str(kie_image_size).strip().lower():
                        logger.warning(
                            "KIE image_size enum remap | model=%s requested=%s allowed=%s mapped=%s",
                            model,
                            kie_image_size,
                            allowed_image_sizes,
                            mapped_image_size,
                        )
                        kie_image_size = str(mapped_image_size).strip().lower()
                    elif mapped_image_size:
                        kie_image_size = str(mapped_image_size).strip().lower()
                    else:
                        fallback_image_size = allowed_image_sizes[0]
                        logger.warning(
                            "KIE image_size enum fallback | model=%s requested=%s allowed=%s fallback=%s",
                            model,
                            kie_image_size,
                            allowed_image_sizes,
                            fallback_image_size,
                        )
                        kie_image_size = fallback_image_size
                if kie_image_size:
                    payload_input["image_size"] = kie_image_size
                else:
                    payload_input.pop("image_size", None)
        elif gen_type == "video":
            if is_topaz_video_upscale:
                source_video_url = str(
                    tool_conf.get("video_url")
                    or tool_conf.get("source_video_url")
                    or ""
                ).strip()
                if not source_video_url:
                    ref_videos_raw = tool_conf.get("reference_video_urls") or tool_conf.get("ref_video_urls") or []
                    if isinstance(ref_videos_raw, list):
                        for item in ref_videos_raw:
                            text = str(item or "").strip()
                            if text:
                                source_video_url = text
                                break

                if not source_video_url:
                    return {
                        "error": "KIE submission validation failed",
                        "details": "topaz/video-upscale requires input.video_url",
                        "submit_failed": True,
                        "runtime_model": model,
                    }

                upscale_factor = str(tool_conf.get("upscale_factor") or "2").strip() or "2"
                if upscale_factor not in {"1", "2", "4"}:
                    upscale_factor = "2"
                payload_input = {
                    "video_url": source_video_url,
                    "upscale_factor": upscale_factor,
                }

            if not is_topaz_video_upscale:
                duration_value = 5
                try:
                    duration_value = int(float(duration if duration is not None else 5))
                except Exception:
                    duration_value = 5
                allowed_durations = runtime_enum_catalog.get("durations_seconds") or []
                if duration_value <= 0:
                    normalized_allowed = self._normalize_duration_enum_values(allowed_durations)
                    duration_value = int(normalized_allowed[0]) if normalized_allowed else 5
                if isinstance(allowed_durations, list) and allowed_durations:
                    mapped_duration = self._map_duration_nearest(
                        duration_value,
                        allowed_durations,
                        prefer_higher_on_tie=is_seedance_video_model,
                    )
                    if mapped_duration is not None:
                        duration_value = int(mapped_duration)

                max_duration = runtime_enum_catalog.get("max_duration")
                try:
                    if max_duration is not None:
                        duration_value = min(int(duration_value), int(max_duration))
                except Exception:
                    pass
                duration_normalized = int(max(1, duration_value))
                payload_input["duration"] = str(duration_normalized) if duration_string_required_model else duration_normalized

                # Propagate project/request-level sound setting to all video models.
                # Previously only kling 2.6 explicitly consumed this flag.
                sound_raw = tool_conf.get("sound")
                if sound_raw is not None:
                    if isinstance(sound_raw, bool):
                        payload_input["sound"] = sound_raw
                    else:
                        payload_input["sound"] = str(sound_raw).strip().lower() in {"1", "true", "yes", "on", "y"}

                if is_kling_26_i2v_model:
                    kling_allowed_durations = runtime_enum_catalog.get("durations_seconds") or []
                    kling_allowed_durations = self._normalize_duration_enum_values(kling_allowed_durations)
                    # KIE Kling 2.6 i2v rejects non-enum durations; use a safe fallback
                    # when runtime enum catalog is missing or incomplete.
                    if not kling_allowed_durations:
                        kling_allowed_durations = [5, 10]
                    mapped_duration = self._map_duration_nearest(duration_value, kling_allowed_durations)
                    if mapped_duration is not None:
                        duration_value = int(mapped_duration)
                    payload_input["duration"] = str(int(duration_value))

                    sound_raw = tool_conf.get("sound")
                    if sound_raw is None:
                        payload_input["sound"] = True
                    elif isinstance(sound_raw, bool):
                        payload_input["sound"] = sound_raw
                    else:
                        payload_input["sound"] = str(sound_raw).strip().lower() in {"1", "true", "yes", "on", "y"}

                # --- Inject quality/output_format for KIE video ---
                # quality
                requested_quality = str(tool_conf.get("quality") or "").strip().lower()
                allowed_qualities = [str(item or "").strip().lower() for item in (runtime_enum_catalog.get("quality") or []) if str(item or "").strip()]
                if requested_quality and allowed_qualities:
                    if requested_quality not in allowed_qualities:
                        fallback_quality = allowed_qualities[0]
                        logger.warning(
                            "KIE quality enum fallback | model=%s requested=%s allowed=%s fallback=%s",
                            model,
                            requested_quality,
                            allowed_qualities,
                            fallback_quality,
                        )
                        requested_quality = fallback_quality
                    payload_input["quality"] = requested_quality
                elif requested_quality:
                    payload_input["quality"] = requested_quality

                # output_format
                requested_output_format = str(tool_conf.get("output_format") or tool_conf.get("outputFormat") or "").strip().lower()
                allowed_output_formats = [str(item or "").strip().lower() for item in (runtime_enum_catalog.get("output_format") or []) if str(item or "").strip()]
                if requested_output_format and allowed_output_formats:
                    if requested_output_format not in allowed_output_formats:
                        fallback_output_format = allowed_output_formats[0]
                        logger.warning(
                            "KIE output_format enum fallback | model=%s requested=%s allowed=%s fallback=%s",
                            model,
                            requested_output_format,
                            allowed_output_formats,
                            fallback_output_format,
                        )
                        requested_output_format = fallback_output_format
                    payload_input["output_format"] = requested_output_format
                elif requested_output_format:
                    payload_input["output_format"] = requested_output_format
        if gen_type == "audio":
            payload_input.pop("duration", None)

        if is_gemini_omni_video_model:
            omni_audio_ids = tool_conf.get("audio_ids")
            if omni_audio_ids is None:
                omni_audio_ids = tool_conf.get("audioIds")
            if isinstance(omni_audio_ids, list):
                normalized_audio_ids = [str(item or "").strip() for item in omni_audio_ids if str(item or "").strip()]
                if normalized_audio_ids:
                    payload_input["audio_ids"] = normalized_audio_ids

            omni_video_list = tool_conf.get("video_list")
            if omni_video_list is None:
                omni_video_list = tool_conf.get("videoList")
            if isinstance(omni_video_list, list):
                normalized_video_list: List[Dict[str, Any]] = []
                for item in omni_video_list:
                    if not isinstance(item, dict):
                        continue
                    video_url = str(item.get("url") or "").strip()
                    if not video_url:
                        continue
                    normalized_item: Dict[str, Any] = {"url": video_url}
                    for key in ("start", "end", "ends"):
                        raw_val = item.get(key)
                        if raw_val is None or str(raw_val).strip() == "":
                            continue
                        try:
                            normalized_item[key] = int(float(raw_val))
                        except Exception:
                            normalized_item[key] = raw_val
                    normalized_video_list.append(normalized_item)
                if normalized_video_list:
                    payload_input["video_list"] = normalized_video_list

        raw_image_refs = self._collect_video_reference_image_urls(
            ref_image,
            tool_conf,
            extra_sources=config,
        )
        resolved_refs: List[str] = []
        for ref in raw_image_refs:
            ref_text = str(ref or "").strip()
            if not ref_text:
                continue
            if ref_text.startswith("asset://"):
                logger.warning("KIE ignored Ark private asset URI reference | ref=%s", ref_text[:80])
                continue
            if ref_text.lower().startswith(("http://", "https://")):
                resolved_refs.append(ref_text)
                continue
            if use_veo_api:
                resolved = await asyncio.to_thread(self._process_veo_image, ref, normalized_ar or "16:9")
            else:
                resolved = await asyncio.to_thread(
                    self._resolve_ref_for_api,
                    ref,
                    force_data_uri_for_local=True,
                    prefer_public_upload_url=True,
                )
            if resolved:
                resolved_refs.append(str(resolved).strip())

        if resolved_refs:
            # Use resolved public URLs (for example OSS URLs) directly in KIE payloads.
            # Avoid KIE pre-upload as requested and keep references untouched.
            resolved_refs = [str(item or "").strip() for item in resolved_refs if str(item or "").strip()]
            if gen_type == "video":
                video_ref_limit = self._get_runtime_capability_int(
                    {"config": tool_conf},
                    "reference_image_limit",
                    "max_reference_images",
                    "max_image_refs",
                ) or 9
                if len(resolved_refs) > video_ref_limit:
                    logger.warning(
                        "KIE video image refs truncated | model=%s provided=%s kept=%s",
                        model,
                        len(resolved_refs),
                        video_ref_limit,
                    )
                    resolved_refs = resolved_refs[:video_ref_limit]

        is_sora2_i2v_model = bool(gen_type == "video" and str(model_lower or "").strip().startswith("sora-2") and "image-to-video" in str(model_lower or "").strip())

        if is_sora2_i2v_model and resolved_refs:
            converted_refs: List[str] = []
            for idx, ref in enumerate(resolved_refs):
                ref_text = str(ref or "").strip()
                if not ref_text:
                    continue
                if ref_text.startswith("http"):
                    converted_refs.append(ref_text)
                    continue
                if not ref_text.startswith("data:"):
                    converted_refs.append(ref_text)
                    continue

                normalized_ref = ref_text
                mime = self._extract_data_uri_mime(ref_text)
                if not any(token in mime for token in ("jpeg", "jpg", "png", "webp")):
                    normalized_candidate = self._normalize_data_uri_image_for_kie(ref_text, target_format="JPEG")
                    if normalized_candidate:
                        normalized_ref = normalized_candidate
                        mime = self._extract_data_uri_mime(normalized_candidate)

                ext = ".jpg"
                if "png" in mime:
                    ext = ".png"
                elif "webp" in mime:
                    ext = ".webp"
                uploaded_ref = await asyncio.to_thread(
                    self._upload_kie_data_uri,
                    normalized_ref,
                    api_key=api_key,
                    file_name=f"sora2-input-{uuid.uuid4().hex[:10]}-{idx + 1}{ext}",
                    upload_path="sora2-inputs",
                )
                if uploaded_ref:
                    converted_refs.append(uploaded_ref)
                else:
                    converted_refs.append(normalized_ref)

            if converted_refs:
                resolved_refs = converted_refs

            single_ref = tool_conf.get("image_url") or tool_conf.get("imageUrl")
            if single_ref and not resolved_refs:
                if use_veo_api:
                    resolved = await asyncio.to_thread(self._process_veo_image, single_ref, normalized_ar or "16:9")
                else:
                    resolved = await asyncio.to_thread(self._resolve_ref_for_api, single_ref, True)
                if resolved:
                    resolved_refs.append(resolved)

        if resolved_refs and not is_topaz_video_upscale:
            if is_gpt_image_15_i2i or is_gpt_image_2_i2i:
                payload_input["input_urls"] = resolved_refs
                payload_input.pop("image_urls", None)
                payload_input.pop("image_url", None)
            elif is_seedream_5_lite_i2i:
                payload_input["image_urls"] = resolved_refs
                payload_input.pop("image_url", None)
            else:
                payload_input["image_urls"] = resolved_refs
                payload_input["image_url"] = resolved_refs[0]
                
            # For multimodal LLM wrappers (like GPT-image family) that rely on the prompt text 
            # to map characters to reference images, replace #1, #2 placeholders with the actual URLs.
            current_prompt_text = str(payload_input.get("prompt") or "")
            if "#1" in current_prompt_text:
                for idx, ref_url in enumerate(resolved_refs):
                    current_prompt_text = re.sub(rf"#{idx + 1}\b", ref_url, current_prompt_text)
                payload_input["prompt"] = current_prompt_text

        if is_gemini_omni_video_model and isinstance(payload_input.get("image_urls"), list):
            payload_input.pop("image_url", None)

        if is_sora2_i2v_model:
            sora_refs = payload_input.get("image_urls")
            if not isinstance(sora_refs, list) or not sora_refs:
                return {
                    "error": "KIE submission validation failed",
                    "details": "sora-2-image-to-video requires input.image_urls (at least one public image URL)",
                    "submit_failed": True,
                    "runtime_model": model,
                }

            if any(str(item or "").strip().startswith("data:") for item in sora_refs):
                return {
                    "error": "KIE submission validation failed",
                    "details": "sora-2-image-to-video requires public image_urls (data URI is not supported)",
                    "submit_failed": True,
                    "runtime_model": model,
                }

            payload_input.pop("image_url", None)
            payload_input.pop("last_frame_url", None)
            payload_input.pop("duration", None)

            sora_ar = str(payload_input.get("aspect_ratio") or normalized_ar or "").strip().lower()
            if sora_ar in {"9:16", "portrait"}:
                payload_input["aspect_ratio"] = "portrait"
            else:
                payload_input["aspect_ratio"] = "landscape"

            n_frames_value = str(tool_conf.get("n_frames") or payload_input.get("n_frames") or "").strip()
            if n_frames_value not in {"10", "15"}:
                n_frames_value = "15" if int(duration_value) >= 15 else "10"
            payload_input["n_frames"] = n_frames_value

            payload_input["remove_watermark"] = True

            upload_method_value = str(tool_conf.get("upload_method") or payload_input.get("upload_method") or "s3").strip().lower()
            if upload_method_value not in {"s3", "oss"}:
                upload_method_value = "s3"
            payload_input["upload_method"] = upload_method_value

        if is_kling_26_i2v_model:
            kling_refs = payload_input.get("image_urls")
            if not isinstance(kling_refs, list) or not kling_refs:
                return {
                    "error": "KIE submission validation failed",
                    "details": "kling-2.6/image-to-video requires input.image_urls (at least one image URL)",
                    "submit_failed": True,
                    "runtime_model": model,
                }

        if (is_gpt_image_15_i2i or is_gpt_image_2_i2i) and not isinstance(payload_input.get("input_urls"), list):
            return {
                "error": "KIE submission validation failed",
                "details": "gpt-image/1.5 or 2.0 image-to-image requires input.input_urls (at least one image URL)",
                "submit_failed": True,
                "runtime_model": model,
            }
        if is_seedream_5_lite_i2i and not isinstance(payload_input.get("image_urls"), list):
            return {
                "error": "KIE submission validation failed",
                "details": "seedream/5-lite-image-to-image requires input.image_urls (at least one image URL)",
                "submit_failed": True,
                "runtime_model": model,
            }
        if is_grok_imagine_i2i:
            grok_refs = payload_input.get("image_urls")
            if not isinstance(grok_refs, list) or not [str(item).strip() for item in grok_refs if str(item).strip()]:
                return {
                    "error": "KIE submission validation failed",
                    "details": "grok-imagine/image-to-image requires input.image_urls (at least one image URL)",
                    "submit_failed": True,
                    "runtime_model": model,
                }

        if last_frame_url and not is_sora2_i2v_model and not is_topaz_video_upscale:
            if use_veo_api:
                last_ref = await self._process_veo_image_async(last_frame_url, normalized_ar or "16:9")
            else:
                last_ref = await self._resolve_ref_for_api_async(last_frame_url, force_data_uri_for_local=True)

            last_ref_text = str(last_ref or "").strip()
            if last_ref_text:
                payload_input["last_frame_url"] = last_ref_text

        if is_seedance_video_model:
            seedance_refs: List[str] = []
            if isinstance(payload_input.get("image_urls"), list):
                seedance_refs.extend([str(x).strip() for x in payload_input.get("image_urls") or [] if str(x).strip()])
            if isinstance(payload_input.get("input_urls"), list):
                seedance_refs.extend([str(x).strip() for x in payload_input.get("input_urls") or [] if str(x).strip()])
            single_ref = str(payload_input.get("image_url") or "").strip()
            if single_ref:
                seedance_refs.append(single_ref)
                
            seedance_refs = [x for x in dict.fromkeys(seedance_refs) if x]
            
            ref_videos = tool_conf.get("reference_video_urls") or tool_conf.get("ref_video_urls")
            has_ref_videos = isinstance(ref_videos, list) and any(str(v).strip() for v in ref_videos)

            if has_ref_videos:
                # Video extension: pass all references. `endpoints.py` tags all refs as @Image1...N.
                if seedance_refs:
                    payload_input["reference_image_urls"] = seedance_refs
                
                payload_input.pop("first_frame_url", None)
                payload_input.pop("last_frame_url", None)
                
                valid_videos: List[str] = []
                invalid_videos: List[str] = []
                for video_ref in ref_videos:
                    raw_video_ref = str(video_ref or "").strip()
                    if not raw_video_ref:
                        continue
                    resolved_video_ref = self._resolve_public_media_url(raw_video_ref) or raw_video_ref
                    if not self._is_public_http_url(resolved_video_ref):
                        invalid_videos.append(raw_video_ref[:300])
                        continue
                    valid_videos.append(resolved_video_ref)
                valid_videos = [x for x in dict.fromkeys(valid_videos) if x]
                seedance_slot_limit = self._get_runtime_capability_int(
                    {"config": tool_conf},
                    "reference_image_limit",
                    "max_reference_images",
                    "max_image_refs",
                ) or 9
                combined_ref_count = len(seedance_refs) + len(valid_videos)
                if combined_ref_count > seedance_slot_limit:
                    overflow = combined_ref_count - seedance_slot_limit
                    while overflow > 0 and valid_videos:
                        valid_videos.pop()
                        overflow -= 1
                    while overflow > 0 and seedance_refs:
                        seedance_refs.pop()
                        overflow -= 1
                    logger.warning(
                        "KIE Seedance reference slots truncated | model=%s kept_images=%s kept_videos=%s limit=%s",
                        model,
                        len(seedance_refs),
                        len(valid_videos),
                        seedance_slot_limit,
                    )
                if invalid_videos:
                    return {
                        "error": "KIE submission validation failed",
                        "details": f"Seedance reference_video_urls must be public http(s) URLs; unresolved refs={invalid_videos[:3]}",
                        "submit_failed": True,
                        "runtime_model": model,
                    }
                payload_input["reference_video_urls"] = valid_videos
            else:
                # Normal image-to-video
                if seedance_refs:
                    if len(seedance_refs) > 1:
                        # Treat first frame as reference image along with others to avoid 422 mutually exclusive error
                        payload_input["reference_image_urls"] = seedance_refs
                        payload_input.pop("first_frame_url", None)
                        payload_input.pop("last_frame_url", None)
                    else:
                        payload_input["first_frame_url"] = seedance_refs[0]
            
            # Follow official Seedance shape and avoid ambiguous legacy aliases.
            payload_input.pop("image_urls", None)
            payload_input.pop("image_url", None)
            payload_input.pop("input_urls", None)

            # Prefer explicit Seedance flags when provided.
            if "fixed_lens" in tool_conf:
                payload_input["fixed_lens"] = bool(tool_conf.get("fixed_lens"))

            if "sound" in payload_input:
                payload_input["generate_audio"] = bool(payload_input.get("sound"))
            elif "generate_audio" in tool_conf:
                payload_input["generate_audio"] = bool(tool_conf.get("generate_audio"))

        if not use_veo_api and gen_type == "video":
            model_lower = str(model or "").strip().lower()

            if model_lower in {"hailuo/2-3-image-to-video-standard", "hailuo/2-3-image-to-video-pro"}:
                # KIE Hailuo 2.3 i2v contract:
                # - duration: "6" or "10"
                # - resolution: "768P" or "1080P"
                # - 1080P does not support 10s
                req_duration_text = str(
                    payload_input.get("duration")
                    or tool_conf.get("duration")
                    or duration
                    or ""
                ).strip()
                try:
                    req_duration_val = float(req_duration_text) if req_duration_text else 6.0
                except Exception:
                    req_duration_val = 6.0

                raw_resolution = str(
                    payload_input.get("resolution")
                    or tool_conf.get("resolution")
                    or "768P"
                ).strip().upper()

                req_res_val = 768.0
                if raw_resolution in {"768P", "1080P"}:
                    req_res_val = float(int(raw_resolution.replace("P", "")))
                else:
                    try:
                        digits = ''.join(ch for ch in raw_resolution if ch.isdigit())
                        req_res_val = float(int(digits)) if digits else 768.0
                    except Exception:
                        req_res_val = 768.0

                # Choose the closest valid pair to the requested duration/resolution.
                valid_pairs = [(6, 768), (10, 768), (6, 1080)]
                best_duration, best_resolution = min(
                    valid_pairs,
                    key=lambda pair: (
                        abs(float(pair[0]) - float(req_duration_val))
                        + abs(float(pair[1]) - float(req_res_val)) / 100.0,
                        abs(float(pair[0]) - float(req_duration_val)),
                        abs(float(pair[1]) - float(req_res_val)),
                    ),
                )

                payload_input["duration"] = str(int(best_duration))
                payload_input["resolution"] = f"{int(best_resolution)}P"

                # Keep only documented hailuo 2.3 i2v fields to avoid 422 Invalid parameter.
                payload_input.pop("aspect_ratio", None)
                payload_input.pop("image_urls", None)
                payload_input.pop("last_frame_url", None)

                # image_url is required by this endpoint.
                primary_image_url = str(payload_input.get("image_url") or "").strip()
                if not primary_image_url:
                    fallback_ref = resolved_refs[0] if resolved_refs else None
                    if fallback_ref:
                        payload_input["image_url"] = str(fallback_ref)

                if not str(payload_input.get("image_url") or "").strip():
                    return {
                        "error": "KIE submission validation failed",
                        "details": "image_url is required for hailuo 2.3 image-to-video",
                        "submit_failed": True,
                        "runtime_model": model,
                    }

                # Hailuo 2.3 i2v rejects some data-uri formats; normalize and prefer hosted URL.
                hailuo_image_url = str(payload_input.get("image_url") or "").strip()
                if hailuo_image_url.startswith("data:"):
                    hailuo_mime = self._extract_data_uri_mime(hailuo_image_url)
                    if "jpeg" not in hailuo_mime and "jpg" not in hailuo_mime and "png" not in hailuo_mime:
                        normalized_data_uri = self._normalize_data_uri_image_for_kie(hailuo_image_url, target_format="JPEG")
                        if normalized_data_uri:
                            hailuo_image_url = normalized_data_uri

                    hailuo_ext = ".jpg"
                    if "png" in self._extract_data_uri_mime(hailuo_image_url):
                        hailuo_ext = ".png"

                    uploaded_hailuo_url = self._upload_kie_data_uri(
                        hailuo_image_url,
                        api_key=api_key,
                        file_name=f"hailuo-{uuid.uuid4().hex[:10]}{hailuo_ext}",
                        upload_path="hailuo-inputs",
                    )
                    if uploaded_hailuo_url:
                        payload_input["image_url"] = uploaded_hailuo_url
                        logger.info("KIE Hailuo 2.3 image_url uploaded | hosted=true")
                    else:
                        payload_input["image_url"] = hailuo_image_url
                        logger.warning("KIE Hailuo 2.3 image_url upload failed; using data URI fallback")

            if model_lower == "bytedance/v1-pro-text-to-video":
                payload_input.setdefault("aspect_ratio", normalized_ar or "16:9")
                payload_input.setdefault("resolution", str(tool_conf.get("resolution") or "720p"))
            elif model_lower == "bytedance/v1-lite-text-to-video":
                payload_input.setdefault("aspect_ratio", normalized_ar or "16:9")
                payload_input.setdefault("resolution", str(tool_conf.get("resolution") or "720p"))
            elif model_lower == "wan/2-6-text-to-video":
                payload_input["duration"] = "10" if str(payload_input.get("duration")) not in {"5", "10", "15"} else str(payload_input.get("duration"))
                payload_input.setdefault("resolution", str(tool_conf.get("resolution") or "720p"))
            elif model_lower == "sora-2-text-to-video":
                if "n_frames" not in payload_input:
                    payload_input["n_frames"] = "10"
                if "aspect_ratio" not in payload_input:
                    payload_input["aspect_ratio"] = "portrait" if normalized_ar == "9:16" else "landscape"
            elif model_lower == "hailuo/02-text-to-video-pro":
                if "prompt_optimizer" not in payload_input:
                    payload_input["prompt_optimizer"] = bool(tool_conf.get("prompt_optimizer", True))

            allowed_resolution_values = [
                str(item or "").strip()
                for item in (runtime_enum_catalog.get("resolution") or [])
                if str(item or "").strip()
            ]
            if "resolution" not in payload_input and allowed_resolution_values:
                default_resolution = self._map_resolution_to_allowed("720p", allowed_resolution_values)
                if default_resolution:
                    payload_input["resolution"] = str(default_resolution).strip()

        internal_callback_url = str(tool_conf.get("_provider_callback_url") or "").strip()
        raw_callback_url = str(
            internal_callback_url
            or tool_conf.get("webHook")
            or tool_conf.get("callBackUrl")
            or tool_conf.get("callback_url")
            or tool_conf.get("callbackUrl")
            or os.getenv("KIE_CALLBACK_URL")
            or os.getenv("AISTORY_KIE_CALLBACK_URL")
            or ""
        ).strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"kie-{gen_type}"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url:
            callback_tool_conf.setdefault("callBackUrl", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)

        if callback_url and callback_url != raw_callback_url:
            logger.info(
                "KIE callback auto-assigned | model=%s gen_type=%s ticket=%s callback_url=%s raw_callback=%s",
                model,
                gen_type,
                callback_ticket,
                callback_url,
                raw_callback_url or None,
            )
        elif callback_url == "-1":
            logger.info(
                "KIE callback disabled | model=%s gen_type=%s raw_callback=%s public_hint=%s",
                model,
                gen_type,
                raw_callback_url or None,
                self._is_public_deployment_hint(),
            )
        if use_veo_api:
            raw_model = str(model or "").strip()
            # According to KIE API, REFERENCE_2_VIDEO only works with "veo3_fast"
            veo_model = "veo3_fast"

            if raw_model != veo_model:
                logger.warning("KIE Veo model canonicalized | from=%s to=%s", raw_model, veo_model)

            veo_image_urls = list(resolved_refs)
            last_frame_resolved = payload_input.get("last_frame_url") or payload_input.get("lastFrameUrl")
            if last_frame_resolved:
                last_frame_text = str(last_frame_resolved).strip()
                if last_frame_text and last_frame_text not in veo_image_urls:
                    veo_image_urls.append(last_frame_text)

            generation_type = "TEXT_2_VIDEO"
            if veo_image_urls:
                if "fast" in str(veo_model).lower():
                    generation_type = "REFERENCE_2_VIDEO"
                    veo_image_urls = veo_image_urls[:3]
                elif len(veo_image_urls) >= 2:
                    generation_type = "FIRST_AND_LAST_FRAMES_2_VIDEO"
                    veo_image_urls = veo_image_urls[:2]
                else:
                    # Non-fast Veo variants generally require at least first+last frames.
                    # Keep this call valid by falling back to pure text mode when only one frame is provided.
                    generation_type = "TEXT_2_VIDEO"
                    veo_image_urls = []

            if generation_type == "REFERENCE_2_VIDEO" and "fast" not in str(veo_model).lower():
                logger.warning(
                    "KIE Veo generationType adjusted | from=REFERENCE_2_VIDEO to=FIRST_AND_LAST_FRAMES_2_VIDEO reason=model_not_fast model=%s",
                    veo_model,
                )
                generation_type = "FIRST_AND_LAST_FRAMES_2_VIDEO"
                veo_image_urls = veo_image_urls[:2]

            # Prefer hosted URLs via KIE File Upload API to avoid base64 body limits on Veo submit endpoint.
            converted_image_urls: List[str] = []
            for idx, ref in enumerate(veo_image_urls):
                ref_text = str(ref or "").strip()
                if not ref_text:
                    continue
                if ref_text.startswith("http"):
                    converted_image_urls.append(ref_text)
                    continue
                if not ref_text.startswith("data:"):
                    converted_image_urls.append(ref_text)
                    continue

                mime = self._extract_data_uri_mime(ref_text)
                ext = ".jpg"
                if "png" in mime:
                    ext = ".png"
                elif "webp" in mime:
                    ext = ".webp"

                generated_name = f"veo-{uuid.uuid4().hex[:10]}-{idx + 1}{ext}"
                uploaded_url = self._upload_kie_data_uri(
                    ref_text,
                    api_key=api_key,
                    file_name=generated_name,
                    upload_path="veo-inputs",
                )
                if uploaded_url:
                    converted_image_urls.append(uploaded_url)
                else:
                    # Keep data URI as fallback when upload endpoint is unavailable.
                    converted_image_urls.append(ref_text)

            if converted_image_urls:
                veo_image_urls = converted_image_urls

            payload: Dict[str, Any] = {
                "prompt": prompt,
                "model": veo_model,
                "generationType": generation_type,
            }

            if generation_type == "REFERENCE_2_VIDEO":
                if normalized_ar not in {"16:9", "9:16"}:
                    logger.warning(
                        "KIE Veo aspect ratio adjusted | from=%s to=16:9 reason=reference_mode_requires_16_9_or_9_16",
                        normalized_ar,
                    )
                    normalized_ar = "16:9"

            if normalized_ar:
                payload["aspect_ratio"] = normalized_ar
            if duration:
                try:
                    payload["duration"] = int(duration)
                except Exception:
                    pass
            if veo_image_urls:
                payload["imageUrls"] = veo_image_urls

            seeds_value = tool_conf.get("seeds")
            try:
                if seeds_value is not None and str(seeds_value).strip() != "":
                    seeds_int = int(seeds_value)
                    if 10000 <= seeds_int <= 99999:
                        payload["seeds"] = seeds_int
            except Exception:
                pass

            if "enableTranslation" in tool_conf:
                payload["enableTranslation"] = bool(tool_conf.get("enableTranslation"))

            payload["watermark"] = False

            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url

            logger.info(
                "KIE Veo submit payload | endpoint=%s model=%s generationType=%s aspect_ratio=%s duration=%s image_count=%s callback_enabled=%s seeds=%s enableTranslation=%s watermark=%s",
                submit_url,
                payload.get("model"),
                payload.get("generationType"),
                payload.get("aspect_ratio"),
                payload.get("duration"),
                len(payload.get("imageUrls") or []),
                bool(payload.get("callBackUrl")),
                payload.get("seeds"),
                payload.get("enableTranslation"),
                bool(payload.get("watermark")),
            )
            try:
                image_sizes = [self._data_uri_image_size_bytes(item) or 0 for item in (payload.get("imageUrls") or [])]
                hosted_count = sum(1 for item in (payload.get("imageUrls") or []) if str(item or "").startswith("http"))
                logger.info(
                    "KIE Veo image payload bytes | per_image=%s total=%s hosted_count=%s",
                    image_sizes,
                    sum(image_sizes),
                    hosted_count,
                )
            except Exception:
                pass
        elif use_runway_api:
            # Handle Runway payload (generate-ai-video or aleph)
            payload = {
                "prompt": prompt,
                "duration": "10" if str(duration) in {"10"} else "5",
                "quality": "480p" if tool_conf.get("draft") or tool_conf.get("draft_mode") else ("1080p" if "1080" in str(tool_conf.get("resolution") or "") else "720p"),
                "aspectRatio": normalized_ar if normalized_ar in {"16:9", "4:3", "1:1", "3:4", "9:16"} else "16:9",
                "waterMark": "",
            }
            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url
            if resolved_refs:
                payload["imageUrl"] = resolved_refs[0]
            
            logger.info("KIE Runway submit payload | endpoint=%s", submit_url)
        elif use_4o_image_api:
            # Handle 4o image payload
            allowed_4o_sizes = {"1:1", "3:2", "2:3"}
            size_candidate = str(tool_conf.get("size") or payload_input.get("aspect_ratio") or "").strip()
            if size_candidate not in allowed_4o_sizes:
                size_candidate = "1:1"

            prompt_candidate = str(prompt or "").strip()
            fallback_model_value = str(tool_conf.get("fallbackModel") or "FLUX_MAX").strip().upper()
            if fallback_model_value not in {"GPT_IMAGE_1", "FLUX_MAX"}:
                fallback_model_value = "FLUX_MAX"

            payload = {
                "size": size_candidate,
                "isEnhance": bool(tool_conf.get("isEnhance")),
                "uploadCn": bool(tool_conf.get("uploadCn")),
                "enableFallback": bool(tool_conf.get("enableFallback")),
                "fallbackModel": fallback_model_value,
            }

            if prompt_candidate:
                payload["prompt"] = prompt_candidate

            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url

            if resolved_refs:
                payload["filesUrl"] = resolved_refs[:5]

            file_url_candidate = str(tool_conf.get("fileUrl") or tool_conf.get("file_url") or "").strip()
            if file_url_candidate and "filesUrl" not in payload:
                payload["fileUrl"] = file_url_candidate

            mask_url_candidate = str(tool_conf.get("maskUrl") or tool_conf.get("mask_url") or "").strip()
            if mask_url_candidate and len(payload.get("filesUrl") or []) <= 1:
                payload["maskUrl"] = mask_url_candidate

            if not str(payload.get("prompt") or "").strip() and not (payload.get("filesUrl") or payload.get("fileUrl")):
                return {
                    "error": "KIE submission validation failed",
                    "details": "gpt4o-image requires prompt or filesUrl/fileUrl",
                    "submit_failed": True,
                    "runtime_model": model,
                }
            
            logger.info("KIE 4o Image submit payload | endpoint=%s", submit_url)
        elif use_flux_kontext_api:
            # Handle Flux Kontext payload
            payload = {
                "prompt": prompt,
                "model": "flux-kontext-max" if "max" in model_lower else "flux-kontext-pro",
                "aspectRatio": normalized_ar if normalized_ar in {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"} else "16:9",
                "outputFormat": tool_conf.get("outputFormat", "jpeg"),
                "promptUpsampling": bool(tool_conf.get("promptUpsampling")),
                "safetyTolerance": int(tool_conf.get("safetyTolerance", 2)),
                "enableTranslation": bool(tool_conf.get("enableTranslation", True)),
                "uploadCn": bool(tool_conf.get("uploadCn")),
                "watermark": False,
            }
            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url
            if resolved_refs:
                payload["inputImage"] = resolved_refs[0]
            
            logger.info("KIE Flux Kontext submit payload | endpoint=%s model=%s", submit_url, payload["model"])
        elif use_suno_api:
            def _suno_conf_value(*keys: str, default: Any = None) -> Any:
                for key in keys:
                    if not key:
                        continue
                    if key in tool_conf and tool_conf.get(key) not in (None, ""):
                        return tool_conf.get(key)
                return default

            def _suno_bool(*keys: str, default: bool = False) -> bool:
                raw = _suno_conf_value(*keys, default=default)
                if isinstance(raw, bool):
                    return raw
                text = str(raw or "").strip().lower()
                if text in {"1", "true", "yes", "y", "on"}:
                    return True
                if text in {"0", "false", "no", "n", "off"}:
                    return False
                return default

            def _suno_float(*keys: str, default: Optional[float] = None) -> Optional[float]:
                raw = _suno_conf_value(*keys, default=default)
                if raw in (None, ""):
                    return default
                try:
                    return float(raw)
                except Exception:
                    return default

            suno_model_version = str(
                _suno_conf_value("suno_model", "sunoModel", "model_version", "modelVersion", default="")
                or ""
            ).strip().upper()
            if not suno_model_version:
                if "v5" in model_lower:
                    suno_model_version = "V5"
                elif "v4.5" in model_lower or "4.5" in model_lower or "v4_5" in model_lower:
                    suno_model_version = "V4_5"
                else:
                    suno_model_version = "V4"
            if suno_model_version not in {"V4", "V4_5", "V5"}:
                suno_model_version = "V4"

            custom_mode = _suno_bool("customMode", "custom_mode", default=True)
            instrumental = _suno_bool("instrumental", default=True)
            payload = {
                "prompt": prompt,
                "model": suno_model_version,
                "customMode": custom_mode,
                "instrumental": instrumental,
            }
            if custom_mode:
                style_val = str(_suno_conf_value("suno_style", "music_style", "style", default="Classical") or "Classical").strip()
                title_val = str(
                    _suno_conf_value("suno_title", "music_title", "title", default="AI Generated Track")
                    or "AI Generated Track"
                ).strip()
                payload["style"] = style_val or "Classical"
                payload["title"] = title_val or "AI Generated Track"

            negative_tags = str(_suno_conf_value("negativeTags", "negative_tags", default="") or "").strip()
            if negative_tags:
                payload["negativeTags"] = negative_tags

            vocal_gender = str(_suno_conf_value("vocalGender", "vocal_gender", default="") or "").strip().lower()
            if vocal_gender in {"m", "f", "male", "female"}:
                payload["vocalGender"] = "m" if vocal_gender in {"m", "male"} else "f"

            for target_key, source_keys in (
                ("styleWeight", ("styleWeight", "style_weight")),
                ("weirdnessConstraint", ("weirdnessConstraint", "weirdness_constraint")),
                ("audioWeight", ("audioWeight", "audio_weight")),
            ):
                numeric_val = _suno_float(*source_keys)
                if numeric_val is not None:
                    payload[target_key] = max(0.0, min(1.0, float(numeric_val)))

            persona_id = str(_suno_conf_value("personaId", "persona_id", default="") or "").strip()
            if persona_id:
                payload["personaId"] = persona_id
            persona_model = str(_suno_conf_value("personaModel", "persona_model", default="") or "").strip()
            if persona_model:
                payload["personaModel"] = persona_model

            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url

            logger.info(
                "KIE Suno submit payload | model=%s customMode=%s instrumental=%s style=%s title=%s vocalGender=%s",
                payload.get("model"),
                payload.get("customMode"),
                payload.get("instrumental"),
                payload.get("style"),
                payload.get("title"),
                payload.get("vocalGender"),
            )
        elif is_kling_3_video:
            kling_model = "kling-3.0/video"

            def _normalize_bool(raw: Any, default: bool) -> bool:
                if raw is None:
                    return default
                if isinstance(raw, bool):
                    return raw
                text = str(raw).strip().lower()
                if text in {"1", "true", "yes", "y", "on"}:
                    return True
                if text in {"0", "false", "no", "n", "off"}:
                    return False
                return default

            kling_mode = str(tool_conf.get("mode") or tool_conf.get("kling_mode") or "pro").strip().lower()
            if kling_mode not in {"std", "pro"}:
                kling_mode = "pro"

            multi_shots = _normalize_bool(tool_conf.get("multi_shots"), False)
            # KIE Kling 3.0 requires input.sound and defaults to enabled.
            sound_enabled = _normalize_bool(tool_conf.get("sound"), True)
            if multi_shots and not sound_enabled:
                logger.info(
                    "KIE Kling3 sound overridden to true because multi_shots=true requires sound=true"
                )
                sound_enabled = True

            duration_int = 5
            try:
                duration_int = int(float(duration if duration is not None else 5))
            except Exception:
                duration_int = 5
            duration_int = max(3, min(15, duration_int))

            kling_input: Dict[str, Any] = {
                "prompt": prompt,
                "sound": sound_enabled,
                "duration": str(duration_int),
                "mode": kling_mode,
                "multi_shots": multi_shots,
            }

            if normalized_ar in {"16:9", "9:16", "1:1"}:
                kling_input["aspect_ratio"] = normalized_ar

            kling_image_urls: List[str] = list(resolved_refs)
            if not kling_image_urls:
                kling_image_urls = self._collect_video_reference_image_urls(
                    None,
                    tool_conf,
                    extra_sources=config,
                )
            last_frame_resolved = payload_input.get("last_frame_url") or payload_input.get("lastFrameUrl")
            if last_frame_resolved:
                last_frame_text = str(last_frame_resolved).strip()
                if last_frame_text and last_frame_text not in kling_image_urls:
                    kling_image_urls.append(last_frame_text)

            # Mutually exclusive: If reference_video_urls is set in tool_conf, clear images
            # User request: Keep reference images even when video is submitted.
            # ref_videos = tool_conf.get("reference_video_urls") or tool_conf.get("ref_video_urls")
            # if isinstance(ref_videos, list) and any(str(v).strip() for v in ref_videos):
            #     kling_image_urls = []

            if multi_shots and len(kling_image_urls) > 1:
                logger.info(
                    "KIE Kling3 image_urls truncated for multi-shot | provided=%s kept=1",
                    len(kling_image_urls),
                )
                kling_image_urls = kling_image_urls[:1]

            if kling_image_urls:
                kling_input["image_urls"] = kling_image_urls

            raw_multi_prompt = tool_conf.get("multi_prompt")
            normalized_multi_prompt: List[Dict[str, Any]] = []
            if isinstance(raw_multi_prompt, list):
                for item in raw_multi_prompt:
                    if not isinstance(item, dict):
                        continue
                    shot_prompt = str(item.get("prompt") or "").strip()
                    if not shot_prompt:
                        continue
                    try:
                        shot_duration = int(item.get("duration"))
                    except Exception:
                        shot_duration = 3
                    shot_duration = max(1, min(12, shot_duration))
                    normalized_multi_prompt.append({"prompt": shot_prompt, "duration": shot_duration})
                    if len(normalized_multi_prompt) >= 5:
                        break

            if multi_shots:
                if not normalized_multi_prompt:
                    normalized_multi_prompt = [{"prompt": prompt, "duration": max(1, min(12, duration_int))}]
                kling_input["multi_prompt"] = normalized_multi_prompt
            elif normalized_multi_prompt:
                kling_input["multi_prompt"] = normalized_multi_prompt

            raw_kling_elements = tool_conf.get("kling_elements")
            normalized_elements: List[Dict[str, Any]] = []
            seen_element_names: set[str] = set()
            max_kling_elements = 3
            if isinstance(raw_kling_elements, list):
                for element in raw_kling_elements:
                    if len(normalized_elements) >= max_kling_elements:
                        break
                    if not isinstance(element, dict):
                        continue
                    name = str(element.get("name") or "").strip()
                    description = str(element.get("description") or "").strip()
                    if not name or not description:
                        continue

                    normalized_name = name.lower()
                    if normalized_name in seen_element_names:
                        continue

                    normalized_element: Dict[str, Any] = {
                        "name": name,
                        "description": description,
                    }

                    image_inputs = element.get("element_input_urls")
                    if isinstance(image_inputs, list):
                        urls = [str(item).strip() for item in image_inputs if str(item).strip()]
                        if urls:
                            # KIE API requires between 2 and 4 images
                            if len(urls) == 1:
                                urls.append(urls[0])
                            elif len(urls) > 4:
                                urls = urls[:4]
                            normalized_element["element_input_urls"] = urls

                    video_inputs = element.get("element_input_video_urls")
                    if isinstance(video_inputs, list):
                        urls = [str(item).strip() for item in video_inputs if str(item).strip()]
                        if urls:
                            normalized_element["element_input_video_urls"] = urls

                    normalized_elements.append(normalized_element)
                    seen_element_names.add(normalized_name)

            if isinstance(raw_kling_elements, list) and len(raw_kling_elements) > len(normalized_elements):
                logger.info(
                    "KIE Kling3 elements truncated/deduped before submit | raw=%s normalized=%s max=%s",
                    len(raw_kling_elements),
                    len(normalized_elements),
                    max_kling_elements,
                )

            if normalized_elements:
                kling_input["kling_elements"] = normalized_elements
                logger.info(
                    "KIE Kling3 final elements detail | elements=%s",
                    [
                        {
                            "name": str(item.get("name") or "").strip(),
                            "image_url_count": len(item.get("element_input_urls") or []) if isinstance(item.get("element_input_urls"), list) else 0,
                            "video_url_count": len(item.get("element_input_video_urls") or []) if isinstance(item.get("element_input_video_urls"), list) else 0,
                        }
                        for item in normalized_elements
                        if isinstance(item, dict)
                    ],
                )

            payload = {
                "model": kling_model,
                "input": kling_input,
            }

            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url

            logger.info(
                "KIE Kling3 submit payload | endpoint=%s model=%s mode=%s multi_shots=%s duration=%s aspect_ratio=%s image_count=%s multi_prompt_count=%s elements_count=%s sound=%s callback_enabled=%s",
                submit_url,
                payload.get("model"),
                kling_input.get("mode"),
                kling_input.get("multi_shots"),
                kling_input.get("duration"),
                kling_input.get("aspect_ratio"),
                len(kling_input.get("image_urls") or []),
                len(kling_input.get("multi_prompt") or []),
                len(kling_input.get("kling_elements") or []),
                kling_input.get("sound"),
                bool(payload.get("callBackUrl")),
            )
        elif is_gemini_omni_video_model:
            omni_input: Dict[str, Any] = {
                "prompt": str(payload_input.get("prompt") or "").strip(),
            }

            omni_aspect_ratio_raw = str(payload_input.get("aspect_ratio") or normalized_ar or "").strip().lower()
            # Pass through exactly supported values for gemini-omni-video.
            omni_aspect_ratio = "9:16" if omni_aspect_ratio_raw == "9:16" else "16:9"
            omni_input["aspect_ratio"] = omni_aspect_ratio

            omni_res_raw = str(
                payload_input.get("resolution")
                or tool_conf.get("resolution")
                or tool_conf.get("image_size")
                or ""
            ).strip().lower().replace(" ", "")
            if omni_res_raw in {"4k", "2160", "2160p", "uhd", "3840"}:
                omni_input["resolution"] = "4k"
            elif omni_res_raw in {"1080", "1080p", "p1080", "fhd"}:
                omni_input["resolution"] = "1080p"
            else:
                omni_input["resolution"] = "720p"

            if isinstance(payload_input.get("image_urls"), list):
                image_urls = [str(item or "").strip() for item in payload_input.get("image_urls") if str(item or "").strip()]
                if image_urls:
                    omni_input["image_urls"] = image_urls
            if isinstance(payload_input.get("audio_ids"), list):
                audio_ids = [str(item or "").strip() for item in payload_input.get("audio_ids") if str(item or "").strip()]
                if audio_ids:
                    omni_input["audio_ids"] = audio_ids
            if isinstance(payload_input.get("video_list"), list) and payload_input.get("video_list"):
                omni_input["video_list"] = payload_input.get("video_list")

            omni_duration_raw = payload_input.get("duration")
            if omni_duration_raw is None:
                omni_duration_raw = duration
            try:
                omni_duration_num = int(float(omni_duration_raw))
            except Exception:
                omni_duration_num = 4
            # Official buckets: 4 | 6 | 8 | 10
            allowed_omni_durations = (4, 6, 8, 10)
            omni_duration_num = min(allowed_omni_durations, key=lambda bucket: abs(bucket - max(1, omni_duration_num)))
            omni_input["duration"] = str(omni_duration_num)

            payload = {
                "model": "gemini-omni-video",
                "input": omni_input,
            }
            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url

            logger.info(
                "KIE Gemini Omni Video submit payload | endpoint=%s model=%s duration=%s image_count=%s audio_count=%s video_count=%s callback_enabled=%s",
                submit_url,
                payload.get("model"),
                omni_input.get("duration"),
                len(omni_input.get("image_urls") or []),
                len(omni_input.get("audio_ids") or []),
                len(omni_input.get("video_list") or []),
                bool(payload.get("callBackUrl")),
            )
        else:
            payload = {
                "model": model,
                "input": payload_input,
            }
            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url

        # Final enum guard: enforce payload input values against system_api dictionary catalog.
        payload_input_obj = payload.get("input") if isinstance(payload, dict) else None
        if isinstance(payload_input_obj, dict) and runtime_enum_catalog:
            allowed_modes = [str(item or "").strip().lower() for item in runtime_enum_catalog.get("mode") or [] if str(item or "").strip()]
            current_mode = str(payload_input_obj.get("mode") or "").strip().lower()
            if current_mode and allowed_modes:
                mapped_mode = self._map_mode_to_allowed(current_mode, runtime_enum_catalog.get("mode"))
                if mapped_mode:
                    payload_input_obj["mode"] = str(mapped_mode).strip().lower()

            allowed_aspect_ratios = [str(item or "").strip() for item in runtime_enum_catalog.get("aspect_ratio") or [] if str(item or "").strip()]
            current_ar = str(payload_input_obj.get("aspect_ratio") or "").strip()
            if current_ar and allowed_aspect_ratios:
                mapped_ar = self._map_aspect_ratio_to_allowed(current_ar, runtime_enum_catalog.get("aspect_ratio"))
                if mapped_ar:
                    payload_input_obj["aspect_ratio"] = str(mapped_ar).strip()

            allowed_image_sizes = [str(item or "").strip().lower() for item in runtime_enum_catalog.get("image_size") or [] if str(item or "").strip()]
            current_image_size = str(payload_input_obj.get("image_size") or "").strip().lower()
            if current_image_size and allowed_image_sizes:
                mapped_image_size = self._map_image_size_to_allowed(current_image_size, runtime_enum_catalog.get("image_size"))
                if mapped_image_size:
                    payload_input_obj["image_size"] = str(mapped_image_size).strip().lower()

            allowed_resolutions = [str(item or "").strip().lower() for item in runtime_enum_catalog.get("resolution") or [] if str(item or "").strip()]
            current_resolution = str(payload_input_obj.get("resolution") or "").strip()
            if current_resolution and allowed_resolutions:
                mapped_resolution = self._map_resolution_to_allowed(current_resolution, runtime_enum_catalog.get("resolution"))
                if mapped_resolution:
                    payload_input_obj["resolution"] = str(mapped_resolution).strip()

            # Hailuo 2.3 i2v requires uppercase-P literals (768P / 1080P).
            if str(model_lower or "") in {"hailuo/2-3-image-to-video-standard", "hailuo/2-3-image-to-video-pro"}:
                normalized_resolution = str(payload_input_obj.get("resolution") or "").strip()
                if normalized_resolution:
                    digits = ''.join(ch for ch in normalized_resolution if ch.isdigit())
                    if digits in {"768", "1080"}:
                        payload_input_obj["resolution"] = f"{digits}P"

            current_duration_text = str(payload_input_obj.get("duration") or "").strip()
            if current_duration_text:
                try:
                    current_duration_int = int(float(current_duration_text))
                    allowed_durations = runtime_enum_catalog.get("durations_seconds") or []
                    if isinstance(allowed_durations, list) and allowed_durations:
                        mapped_duration = self._map_duration_nearest(
                            current_duration_int,
                            allowed_durations,
                            prefer_higher_on_tie=is_seedance_video_model,
                        )
                        if mapped_duration is not None:
                            current_duration_int = int(mapped_duration)
                    max_duration = runtime_enum_catalog.get("max_duration")
                    if max_duration is not None:
                        current_duration_int = min(int(current_duration_int), int(max_duration))
                    normalized_duration_int = int(max(1, int(current_duration_int)))
                    payload_input_obj["duration"] = str(normalized_duration_int) if duration_string_required_model else normalized_duration_int
                except Exception:
                    pass

            sound_supported = runtime_enum_catalog.get("sound_supported")
            if sound_supported is False and "sound" in payload_input_obj:
                payload_input_obj["sound"] = True

            multi_shots_supported = runtime_enum_catalog.get("multi_shots_supported")
            if multi_shots_supported is False and "multi_shots" in payload_input_obj:
                payload_input_obj["multi_shots"] = False

            if is_seedance_video_model and not is_gemini_omni_video_model:
                seedance_default_resolution = "480p" if (tool_conf.get("draft") or tool_conf.get("draft_mode")) else "720p"
                if not str(payload_input_obj.get("resolution") or "").strip():
                    payload_input_obj["resolution"] = seedance_default_resolution
                elif allowed_resolutions:
                    mapped_seedance_resolution = self._map_resolution_to_allowed(
                        payload_input_obj.get("resolution"),
                        runtime_enum_catalog.get("resolution"),
                    )
                    if mapped_seedance_resolution:
                        payload_input_obj["resolution"] = str(mapped_seedance_resolution).strip()

            if tool_conf.get("draft") or tool_conf.get("draft_mode"):
                if not is_gemini_omni_video_model and not is_flux2_image_model:
                    payload_input_obj["resolution"] = "480p"

            if is_flux2_image_model:
                flux2_resolution = str(payload_input_obj.get("resolution") or "").strip().upper()
                if flux2_resolution not in {"1K", "2K"}:
                    flux2_resolution = "1K"
                payload_input_obj["resolution"] = flux2_resolution
                payload_input_obj.pop("image_size", None)

            # KIE gemini-omni-video accepts resolution: 720p | 1080p | 4k (default 720p).
            if is_gemini_omni_video_model:
                omni_res_raw = str(
                    payload_input_obj.get("resolution")
                    or tool_conf.get("resolution")
                    or tool_conf.get("image_size")
                    or ""
                ).strip().lower().replace(" ", "")
                if omni_res_raw in {"4k", "2160", "2160p", "uhd", "3840"}:
                    payload_input_obj["resolution"] = "4k"
                elif omni_res_raw in {"1080", "1080p", "p1080", "fhd"}:
                    payload_input_obj["resolution"] = "1080p"
                else:
                    payload_input_obj["resolution"] = "720p"
                final_ar = str(payload_input_obj.get("aspect_ratio") or "").strip().lower()
                if final_ar == "9:16":
                    payload_input_obj["aspect_ratio"] = "9:16"
                elif final_ar == "16:9":
                    payload_input_obj["aspect_ratio"] = "16:9"
                else:
                    payload_input_obj["aspect_ratio"] = "16:9"

            payload["input"] = payload_input_obj

        if isinstance(payload, dict):
            payload = self._enforce_no_watermark_payload(payload)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        def _is_unsupported_model_message(value: Any) -> bool:
            text = str(value or "").strip().lower()
            if not text:
                return False
            return (
                "model name you specified is not supported" in text
                or "model is not supported" in text
                or "unsupported model" in text
            )

        def _is_kie_image_size_error(value: Any) -> bool:
            text = str(value or "").strip().lower()
            if not text:
                return False
            return "images size exceeds limit" in text or "image size exceeds limit" in text

        def _is_kie_invalid_voice_error(value: Any) -> bool:
            text = str(value or "").strip().lower()
            if not text:
                return False
            return (
                "voice is not within the range of allowed options" in text
                or "voice is not within the range" in text
                or "invalid voice" in text
            )

        def _is_veo_fast_model_name(current_model: Any) -> bool:
            return "fast" in str(current_model or "").strip().lower()

        def _build_veo_retry_models(initial_model: Any) -> List[str]:
            initial = str(initial_model or "").strip()
            initial_lower = initial.lower()
            fast_candidates = ["veo3_fast", "veo-3-fast", "veo3-fast", "veo_3_fast", "veo31_fast"]
            quality_candidates = ["veo3", "veo-3", "veo", "veo_3", "veo31"]

            ordered: List[str] = [initial] if initial else []
            if _is_veo_fast_model_name(initial):
                ordered.extend(fast_candidates)
                ordered.extend(quality_candidates)
            elif initial_lower in {"veo3", "veo-3", "veo", "veo3.1", "veo-3.1"}:
                ordered.extend(quality_candidates)
                ordered.extend(fast_candidates)
            else:
                ordered.extend(fast_candidates)
                ordered.extend(quality_candidates)

            deduped: List[str] = []
            seen = set()
            for item in ordered:
                key = str(item or "").strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                deduped.append(str(item).strip())
            return deduped

        def _adapt_veo_payload_for_model(base_payload: Dict[str, Any], target_model: str) -> Dict[str, Any]:
            patched = dict(base_payload or {})
            patched["model"] = target_model
            current_generation_type = str(patched.get("generationType") or "").strip().upper()
            if current_generation_type == "REFERENCE_2_VIDEO" and not _is_veo_fast_model_name(target_model):
                patched["generationType"] = "FIRST_AND_LAST_FRAMES_2_VIDEO"
                if isinstance(patched.get("imageUrls"), list):
                    patched["imageUrls"] = patched.get("imageUrls")[:2]
            return patched

        def _post_submit(submit_payload: Dict[str, Any]):
            import json
            log_payload = _strip_base64_from_log(submit_payload)
            kie_tag = "audio" if gen_type == "audio" else ("video" if gen_type == "video" else "image")
            try:
                dumped = json.dumps(log_payload, ensure_ascii=False)
            except:
                dumped = str(log_payload)
            logger.info(f"====== PRE_SUBMIT DUMP [{kie_tag}] ======\nURL: {submit_url}\nModel: {submit_payload.get('model')}\nPayload: {dumped}\n====== END PRE_SUBMIT DUMP ======")
            _debug_log(f"[KIE_{kie_tag}] Submitting to URL: {submit_url} | Model: {submit_payload.get('model')} | Payload: {log_payload}")
            if callable(provider_payload_callback):
                try:
                    provider_payload_callback(
                        {
                            "provider": "kie",
                            "type": kie_tag,
                            "method": "POST",
                            "url": submit_url,
                            "model": submit_payload.get("model"),
                            "payload": log_payload,
                        }
                    )
                except Exception as callback_err:
                    logger.warning(
                        "KIE provider payload callback failed | model=%s error=%s",
                        submit_payload.get("model"),
                        callback_err,
                    )
            
            logger.info("KIE performing HTTP Request | Method: POST | URL: %s | Payload_model: %s", submit_url, submit_payload.get('model'))
            return requests.post(
                submit_url,
                json=submit_payload,
                headers=headers,
                timeout=_media_submit_timeout_pair(
                    connect_timeout=max(
                        5,
                        int(os.getenv("KIE_SUBMIT_CONNECT_TIMEOUT_SECONDS", str(DEFAULT_MEDIA_SUBMIT_CONNECT_TIMEOUT_SECONDS)) or DEFAULT_MEDIA_SUBMIT_CONNECT_TIMEOUT_SECONDS),
                    ),
                    io_timeout=max(
                        15,
                        int(os.getenv("KIE_SUBMIT_IO_TIMEOUT_SECONDS", str(DEFAULT_MEDIA_SUBMIT_IO_TIMEOUT_SECONDS)) or DEFAULT_MEDIA_SUBMIT_IO_TIMEOUT_SECONDS),
                    ),
                ),
                verify=False,
            )

        def _kie_response_details(response: requests.Response) -> Dict[str, Any]:
            raw_text = ""
            try:
                raw_text = str(response.text or "")
            except Exception:
                raw_text = ""

            parsed_json: Any = None
            try:
                parsed_json = response.json()
            except Exception:
                parsed_json = None

            return {
                "status_code": int(getattr(response, "status_code", 0) or 0),
                "response_json": parsed_json,
                "response_text": raw_text[:8000],
            }

        def _truncate_kie_log_value(value: Any, limit: int = 1500) -> str:
            try:
                text = json.dumps(_strip_base64_from_log(value), ensure_ascii=False)
            except Exception:
                text = str(_strip_base64_from_log(value))
            text = str(text or "")
            if len(text) <= limit:
                return text
            return f"{text[:limit]}..."

        def _summarize_kie_input_for_log(payload_input_obj: Any) -> Dict[str, Any]:
            input_obj = payload_input_obj if isinstance(payload_input_obj, dict) else {}
            summary: Dict[str, Any] = {
                "mode": str(input_obj.get("mode") or "").strip() or None,
                "aspect_ratio": str(input_obj.get("aspect_ratio") or "").strip() or None,
                "duration": input_obj.get("duration"),
                "quality": str(input_obj.get("quality") or "").strip() or None,
                "image_url": bool(str(input_obj.get("image_url") or "").strip()),
                "last_frame_url": bool(str(input_obj.get("last_frame_url") or "").strip()),
                "image_urls": len(input_obj.get("image_urls") or []) if isinstance(input_obj.get("image_urls"), list) else 0,
                "input_urls": len(input_obj.get("input_urls") or []) if isinstance(input_obj.get("input_urls"), list) else 0,
                "generate_audio": input_obj.get("generate_audio") if "generate_audio" in input_obj else None,
                "sound": input_obj.get("sound") if "sound" in input_obj else None,
            }
            return summary

        submit_payload: Dict[str, Any] = dict(payload or {})
        submitted_model = submit_payload.get("model") if isinstance(submit_payload, dict) else model
        initial_submitted_model = str(submitted_model or "").strip()
        veo_retry_models = _build_veo_retry_models(submitted_model) if use_veo_api else []
        task_id_callback = tool_conf.get("_provider_task_id_callback")
        if not callable(task_id_callback):
            task_id_callback = None
        provider_payload_callback = tool_conf.get("_provider_payload_callback")
        if not callable(provider_payload_callback):
            provider_payload_callback = None

        if gen_type in {"image", "video"}:
            logger.info(
                "KIE submit prepared | gen_type=%s endpoint=%s model=%s callback_enabled=%s callback_url=%s input_summary=%s",
                gen_type,
                submit_url,
                submitted_model,
                bool(callback_url and callback_url != "-1"),
                callback_url or None,
                _summarize_kie_input_for_log(submit_payload.get("input") if isinstance(submit_payload, dict) else None),
            )

        def _rebuild_veo_image_urls_with_limit(limit_bytes: int) -> List[str]:
            rebuilt_refs: List[str] = []
            if ref_image:
                src_list = ref_image if isinstance(ref_image, list) else [ref_image]
                for src in src_list:
                    rebuilt = self._process_veo_image(src, normalized_ar or "16:9")
                    if rebuilt:
                        rebuilt_text = str(rebuilt or "").strip()
                        if rebuilt_text:
                            rebuilt_refs.append(rebuilt_text)
            if last_frame_url:
                rebuilt_last = self._process_veo_image(last_frame_url, normalized_ar or "16:9")
                rebuilt_last_text = str(rebuilt_last or "").strip()
                if rebuilt_last_text and rebuilt_last_text not in rebuilt_refs:
                    rebuilt_refs.append(rebuilt_last_text)
            return rebuilt_refs

        async def _retry_veo_on_image_size_limit(current_resp: requests.Response, current_payload: Dict[str, Any]):
            if not use_veo_api:
                return current_resp, current_payload

            try:
                current_data = current_resp.json() if current_resp.status_code == 200 else None
            except Exception:
                current_data = None

            current_msg = ""
            if current_data and isinstance(current_data, dict):
                current_msg = current_data.get("msg") or current_data.get("message") or ""
            elif current_resp is not None:
                current_msg = getattr(current_resp, "text", "") or ""

            if not _is_kie_image_size_error(current_msg):
                return current_resp, current_payload

            retry_limits = [70 * 1024, 50 * 1024]
            retry_resp = current_resp
            retry_payload = dict(current_payload or {})
            original_env = os.getenv("KIE_VEO_IMAGE_MAX_BYTES")
            try:
                for limit in retry_limits:
                    os.environ["KIE_VEO_IMAGE_MAX_BYTES"] = str(limit)
                    rebuilt_urls = _rebuild_veo_image_urls_with_limit(limit)
                    if not rebuilt_urls:
                        continue
                    retry_payload["imageUrls"] = rebuilt_urls[:3]
                    logger.warning(
                        "KIE Veo image-size retry | limit=%s image_count=%s",
                        limit,
                        len(retry_payload.get("imageUrls") or []),
                    )
                    retry_resp = await asyncio.to_thread(_post_submit, retry_payload)
                    if retry_resp.status_code != 200:
                        continue
                    try:
                        retry_data = retry_resp.json()
                    except Exception:
                        continue
                    retry_code = retry_data.get("code")
                    retry_msg = retry_data.get("msg") or retry_data.get("message") or ""
                    if retry_code in (None, 200, "200") or not _is_kie_image_size_error(retry_msg):
                        return retry_resp, retry_payload
                return retry_resp, retry_payload
            finally:
                if original_env is None:
                    os.environ.pop("KIE_VEO_IMAGE_MAX_BYTES", None)
                else:
                    os.environ["KIE_VEO_IMAGE_MAX_BYTES"] = original_env

        def _is_kie_resource_download_error(value: Any) -> bool:
            text = str(value or "").strip().lower()
            if not text:
                return False
            return (
                ("resource download failed" in text)
                or ("download failed" in text and "image_url" in text)
                or ("invalidparameter" in text and "image_url" in text)
                or ("file type not supported" in text)
            )

        def _rehost_kie_submit_input_urls(payload_obj: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
            import copy as copy_module

            candidate = copy_module.deepcopy(payload_obj or {})
            changed = False

            def _upload_one_ref(raw_value: Any, tag: str) -> Optional[str]:
                value_text = str(raw_value or "").strip()
                if not value_text:
                    return None
                if not value_text.startswith(("http://", "https://", "data:")):
                    return None

                # Convert uncommon/unsupported data-uri image mime types to JPEG before re-upload.
                if value_text.startswith("data:image/"):
                    mime = self._extract_data_uri_mime(value_text)
                    if not any(token in mime for token in ("jpeg", "jpg", "png", "webp")):
                        normalized_candidate = self._normalize_data_uri_image_for_kie(value_text, target_format="JPEG")
                        if normalized_candidate:
                            value_text = normalized_candidate

                return self._upload_kie_ref_to_hosted_url(
                    value_text,
                    api_key=api_key,
                    upload_path="market-inputs",
                    file_name_prefix=f"kie-retry-{tag}",
                )

            def _replace_single(container: Dict[str, Any], key: str) -> None:
                nonlocal changed
                if not isinstance(container, dict):
                    return
                raw_value = container.get(key)
                hosted = _upload_one_ref(raw_value, key)
                if hosted:
                    container[key] = hosted
                    changed = True

            def _replace_list(container: Dict[str, Any], key: str) -> None:
                nonlocal changed
                if not isinstance(container, dict):
                    return
                raw_value = container.get(key)
                if not isinstance(raw_value, list):
                    return
                replaced: List[Any] = []
                item_changed = False
                for idx, item in enumerate(raw_value):
                    hosted = _upload_one_ref(item, f"{key}-{idx + 1}")
                    if hosted:
                        replaced.append(hosted)
                        item_changed = True
                    else:
                        replaced.append(item)
                if item_changed:
                    container[key] = replaced
                    changed = True

            def _replace_video_list(container: Dict[str, Any], key: str = "video_list") -> None:
                nonlocal changed
                if not isinstance(container, dict):
                    return
                raw_value = container.get(key)
                if not isinstance(raw_value, list):
                    return

                replaced_list: List[Any] = []
                item_changed = False
                for idx, item in enumerate(raw_value):
                    if not isinstance(item, dict):
                        replaced_list.append(item)
                        continue
                    patched_item = dict(item)
                    hosted = _upload_one_ref(item.get("url"), f"{key}-{idx + 1}")
                    if hosted:
                        patched_item["url"] = hosted
                        item_changed = True
                    replaced_list.append(patched_item)

                if item_changed:
                    container[key] = replaced_list
                    changed = True

            payload_input = candidate.get("input") if isinstance(candidate.get("input"), dict) else {}

            for key in ("image_url", "last_frame_url", "first_frame_url", "end_frame_url"):
                _replace_single(payload_input, key)

            for key in ("image_urls", "input_urls", "reference_image_urls"):
                _replace_list(payload_input, key)

            for key in ("reference_video_urls", "video_urls"):
                _replace_list(payload_input, key)

            _replace_video_list(payload_input, "video_list")

            # Veo-style payload occasionally uses top-level imageUrls.
            _replace_list(candidate, "imageUrls")

            if isinstance(candidate.get("input"), dict):
                candidate["input"] = payload_input
            return candidate, changed

        async def _retry_kie_on_resource_download_failure(
            current_resp: requests.Response,
            current_payload: Dict[str, Any],
            current_data: Optional[Dict[str, Any]] = None,
        ) -> tuple[requests.Response, Dict[str, Any], Optional[Dict[str, Any]]]:
            if gen_type not in {"image", "video"}:
                return current_resp, current_payload, current_data

            detail_text = ""
            if isinstance(current_data, dict):
                detail_text = str(current_data.get("msg") or current_data.get("message") or "").strip()
            if not detail_text:
                detail_text = str(getattr(current_resp, "text", "") or "").strip()

            if not _is_kie_resource_download_error(detail_text):
                return current_resp, current_payload, current_data

            retry_payload, changed = await asyncio.to_thread(_rehost_kie_submit_input_urls, current_payload)
            if not changed:
                return current_resp, current_payload, current_data

            logger.warning(
                "KIE submission retry with file-url-upload fallback | model=%s gen_type=%s reason=%s",
                submitted_model,
                gen_type,
                detail_text[:300],
            )

            try:
                retry_resp = await asyncio.to_thread(_post_submit, retry_payload)
            except Exception:
                return current_resp, current_payload, current_data

            retry_data = None
            if retry_resp.status_code == 200:
                try:
                    retry_data = retry_resp.json()
                except Exception:
                    retry_data = None
            return retry_resp, retry_payload, retry_data

        try:
            try:
                resp = await asyncio.to_thread(_post_submit, submit_payload)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as first_err:
                _debug_log(f"[KIE] Submit connection/timeout error, retrying once: {str(first_err)[:150]}", "warning")
                await asyncio.sleep(5)
                resp = await asyncio.to_thread(_post_submit, submit_payload)
        except requests.exceptions.RequestException as e:
            return {"error": "KIE request failed", "details": str(e), "submit_failed": True}
        except Exception as e:
            return {"error": "KIE request failed", "details": str(e), "submit_failed": True}

        if use_veo_api:
            resp, submit_payload = await _retry_veo_on_image_size_limit(resp, submit_payload)

        # Veo-specific safety retry for upstream model compatibility drift.
        if use_veo_api and resp.status_code != 200 and _is_unsupported_model_message(getattr(resp, "text", "")):
            for alt_model in veo_retry_models:
                if str(alt_model).strip().lower() == str(submitted_model or "").strip().lower():
                    continue
                retry_payload = _adapt_veo_payload_for_model(submit_payload, alt_model)
                logger.warning(
                    "KIE Veo model fallback retry | from=%s to=%s reason=unsupported_model_status_%s",
                    submitted_model,
                    alt_model,
                    resp.status_code,
                )
                try:
                    retry_resp = await asyncio.to_thread(_post_submit, retry_payload)
                    if retry_resp.status_code == 200:
                        resp = retry_resp
                        submit_payload = retry_payload
                        submitted_model = alt_model
                        break
                except Exception:
                    continue

        if resp.status_code != 200:
            resp, submit_payload, _ = await _retry_kie_on_resource_download_failure(resp, submit_payload, None)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = None
                if isinstance(data, dict):
                    pass
                else:
                    return {
                        "error": "Invalid KIE response",
                        "details": resp.text[:1000],
                        "submit_failed": True,
                    }
            else:
                return {
                    "error": f"KIE submission failed {resp.status_code}",
                    "details": _kie_response_details(resp),
                    "submit_failed": True,
                    "runtime_model": submitted_model,
                }
        if 'data' not in locals():
            try:
                data = resp.json()
            except Exception:
                return {"error": "Invalid KIE response", "details": resp.text[:1000], "submit_failed": True}

        if use_veo_api:
            code_preview = data.get("code")
            msg_preview = data.get("msg") or data.get("message") or ""
            if code_preview not in (None, 200, "200") and _is_unsupported_model_message(msg_preview):
                for alt_model in veo_retry_models:
                    if str(alt_model).strip().lower() == str(submitted_model or "").strip().lower():
                        continue
                    retry_payload = _adapt_veo_payload_for_model(submit_payload, alt_model)
                    logger.warning(
                        "KIE Veo model fallback retry | from=%s to=%s reason=unsupported_model_code_%s",
                        submitted_model,
                        alt_model,
                        code_preview,
                    )
                    try:
                        retry_resp = await asyncio.to_thread(_post_submit, retry_payload)
                        if retry_resp.status_code == 200:
                            retry_data = retry_resp.json()
                            retry_code = retry_data.get("code")
                            if retry_code in (None, 200, "200"):
                                resp = retry_resp
                                data = retry_data
                                submit_payload = retry_payload
                                submitted_model = alt_model
                                break
                    except Exception:
                        continue

        if gen_type == "audio":
            code_preview = data.get("code")
            msg_preview = data.get("msg") or data.get("message") or ""
            voice_value = None
            if isinstance(submit_payload.get("input"), dict):
                voice_value = submit_payload.get("input", {}).get("voice")
            if code_preview not in (None, 200, "200") and _is_kie_invalid_voice_error(msg_preview) and str(voice_value or "").strip():
                retry_payload = dict(submit_payload or {})
                retry_input = dict(retry_payload.get("input") or {})
                old_voice = retry_input.pop("voice", None)
                retry_payload["input"] = retry_input
                logger.warning(
                    "KIE audio voice fallback retry | model=%s old_voice=%s reason=%s",
                    submitted_model,
                    old_voice,
                    msg_preview,
                )
                _debug_log(
                    f"[KIE_audio] voice invalid fallback retry | model={submitted_model} old_voice={old_voice}"
                )
                try:
                    retry_resp = await asyncio.to_thread(_post_submit, retry_payload)
                    if retry_resp.status_code == 200:
                        retry_data = retry_resp.json()
                        retry_code = retry_data.get("code")
                        if retry_code in (None, 200, "200"):
                            resp = retry_resp
                            data = retry_data
                            submit_payload = retry_payload
                except Exception as retry_err:
                    logger.warning("KIE audio voice fallback retry failed: %s", retry_err)

        submitted_mode_value = ""
        submitted_aspect_ratio_value = ""
        submitted_quality_value = ""
        submitted_image_count_value = 0
        if isinstance(submit_payload, dict):
            submit_input = submit_payload.get("input") if isinstance(submit_payload.get("input"), dict) else {}
            submitted_mode_value = str(
                submit_input.get("mode")
                or submit_payload.get("mode")
                or ""
            ).strip().lower()
            submitted_aspect_ratio_value = str(submit_input.get("aspect_ratio") or submit_input.get("size") or "").strip()
            submitted_quality_value = str(submit_input.get("quality") or "").strip().lower()
            if isinstance(submit_input.get("image_urls"), list):
                submitted_image_count_value = len(submit_input.get("image_urls") or [])
            elif isinstance(submit_input.get("input_urls"), list):
                submitted_image_count_value = len(submit_input.get("input_urls") or [])

        resolved_mode_source = ""
        if requested_mode:
            resolved_mode_source = mode_source_hint or "config"
        elif submitted_mode_value:
            resolved_mode_source = "model_default"

        base_metadata = {
            "provider": "kie",
            "model": submitted_model,
            "prompt": prompt,
            "submit_mode": submitted_mode_value or None,
            "submit_aspect_ratio": submitted_aspect_ratio_value or None,
            "submit_quality": submitted_quality_value or None,
            "submit_image_count": int(submitted_image_count_value or 0),
            "mode_source": resolved_mode_source or None,
            "standard_resolution_trace": tool_conf.get("__standard_resolution_trace") if isinstance(tool_conf, dict) else None,
            "system_api_id": int(resolved_setting_id) if resolved_setting_id else None,
            "query_endpoint": str(query_url or "").strip() or None,
        }

        code = data.get("code")
        if code not in (None, 200, "200"):
            resp2, payload2, data2 = await _retry_kie_on_resource_download_failure(resp, submit_payload, data if isinstance(data, dict) else None)
            if resp2 is not resp or payload2 is not submit_payload:
                resp = resp2
                submit_payload = payload2
                if isinstance(data2, dict):
                    data = data2
                    code = data.get("code")

            if code in (None, 200, "200"):
                pass
            else:
                details_payload: Any = {
                    "status_code": int(getattr(resp, "status_code", 0) or 0),
                    "code": code,
                    "message": data.get("msg") or data.get("message"),
                    "response_json": data,
                }
                return {
                    "error": f"KIE submission failed code={code}",
                    "details": details_payload,
                    "submit_failed": True,
                    "runtime_model": submitted_model,
                }

        data_block = data.get("data") or {}
        task_id = (
            data_block.get("taskId")
            or data_block.get("task_id")
            or data_block.get("id")
            or data.get("taskId")
            or data.get("task_id")
            or data.get("id")
        )
        if not task_id:
            return {"error": "No taskId from KIE", "details": data, "submit_failed": True, "runtime_model": submitted_model}

        if callable(provider_payload_callback) and isinstance(submit_payload, dict):
            try:
                provider_payload_callback(
                    {
                        "provider": "kie",
                        "type": "audio" if gen_type == "audio" else ("video" if gen_type == "video" else "image"),
                        "method": "POST",
                        "url": submit_url,
                        "model": submit_payload.get("model"),
                        "payload": _strip_base64_from_log(submit_payload),
                        "final_submit": True,
                        "provider_task_id": str(task_id),
                    }
                )
            except Exception as callback_err:
                logger.warning(
                    "KIE final provider payload callback failed | model=%s task_id=%s error=%s",
                    submit_payload.get("model"),
                    task_id,
                    callback_err,
                )

        callback_enabled = bool(callback_url and callback_url != "-1")
        pure_callback_mode = bool(str(tool_conf.get("_pure_callback_mode") or "").strip().lower() in {"1", "true", "yes", "on"})
        callback_assisted_job = bool(
            callback_enabled
            and str(callback_ticket or "").strip().startswith(("image-job-", "video-job-"))
        )

        if callable(task_id_callback):
            try:
                callback_result = task_id_callback(str(task_id))
                if asyncio.iscoroutine(callback_result):
                    await callback_result
            except Exception as callback_err:
                logger.warning(
                    "KIE task_id_callback_failed | task_id=%s error=%s",
                    task_id,
                    callback_err,
                )

        if pure_callback_mode and callback_enabled and str(gen_type or "").strip().lower() in {"video", "image"}:
            logger.info(
                "KIE pure callback mode enabled | task_id=%s callback_ticket=%s callback_url=%s gen_type=%s",
                task_id,
                callback_ticket or None,
                callback_url or None,
                gen_type,
            )
            pending_meta = dict(base_metadata or {})
            pending_meta.update(
                {
                    "raw": data,
                    "submit_raw": data,
                    "task_id": str(task_id),
                    "taskId": str(task_id),
                    "pending_callback": True,
                    "callback_ticket": callback_ticket,
                    "callback_url": callback_url,
                }
            )
            return {
                "pending_callback": True,
                "provider_task_id": str(task_id),
                "metadata": pending_meta,
            }

        if use_veo_api:
            final_generation_type = str((submit_payload or {}).get("generationType") or "").strip()
            final_aspect_ratio = str((submit_payload or {}).get("aspect_ratio") or "").strip()
            final_image_count = len((submit_payload or {}).get("imageUrls") or []) if isinstance((submit_payload or {}).get("imageUrls"), list) else 0
            logger.info(
                "KIE Veo final submit resolved | endpoint=%s model=%s generationType=%s aspect_ratio=%s image_count=%s taskId=%s fallback_model_switch=%s",
                submit_url,
                submitted_model,
                final_generation_type,
                final_aspect_ratio,
                final_image_count,
                task_id,
                bool(str(submitted_model or "").strip().lower() != str(initial_submitted_model or "").strip().lower()),
            )
        elif gen_type == "image":
            final_input = (submit_payload or {}).get("input") if isinstance((submit_payload or {}).get("input"), dict) else {}
            final_input_count = 0
            if isinstance(final_input.get("input_urls"), list):
                final_input_count = len(final_input.get("input_urls") or [])
            elif isinstance(final_input.get("image_urls"), list):
                final_input_count = len(final_input.get("image_urls") or [])
            logger.info(
                "KIE image final submit resolved | endpoint=%s model=%s aspect_ratio=%s quality=%s input_count=%s taskId=%s",
                submit_url,
                submitted_model,
                str(final_input.get("aspect_ratio") or "").strip(),
                str(final_input.get("quality") or "").strip(),
                final_input_count,
                task_id,
            )
        elif is_kling_3_video:
            final_input = (submit_payload or {}).get("input") if isinstance((submit_payload or {}).get("input"), dict) else {}
            final_mode = str(final_input.get("mode") or "").strip()
            final_multi_shots = bool(final_input.get("multi_shots"))
            final_aspect_ratio = str(final_input.get("aspect_ratio") or "").strip()
            final_image_count = len(final_input.get("image_urls") or []) if isinstance(final_input.get("image_urls"), list) else 0
            final_multi_prompt_count = len(final_input.get("multi_prompt") or []) if isinstance(final_input.get("multi_prompt"), list) else 0
            final_elements_count = len(final_input.get("kling_elements") or []) if isinstance(final_input.get("kling_elements"), list) else 0
            logger.info(
                "KIE Kling3 final submit resolved | endpoint=%s model=%s mode=%s multi_shots=%s aspect_ratio=%s image_count=%s multi_prompt_count=%s elements_count=%s taskId=%s",
                submit_url,
                submitted_model,
                final_mode,
                final_multi_shots,
                final_aspect_ratio,
                final_image_count,
                final_multi_prompt_count,
                final_elements_count,
                task_id,
            )
        elif gen_type == "video":
            final_input = (submit_payload or {}).get("input") if isinstance((submit_payload or {}).get("input"), dict) else {}
            logger.info(
                "KIE video final submit resolved | endpoint=%s model=%s taskId=%s input_summary=%s",
                submit_url,
                submitted_model,
                task_id,
                _summarize_kie_input_for_log(final_input),
            )

        def _is_ok_code(value: Any) -> bool:
            if value in (None, 200, "200"):
                return True
            try:
                return int(str(value).strip()) == 200
            except Exception:
                return False

        def _build_success_meta(poll_data_obj: Any, record_obj: Any) -> Dict[str, Any]:
            return self._finalize_kie_poll_metadata(
                base_metadata=base_metadata,
                poll_data=poll_data_obj,
                record=record_obj,
                task_id=str(task_id),
                api_key=api_key,
                query_url=query_url,
                refresh_if_missing_credits=True,
            )

        def _pick_preferred_kie_media_url(candidates: List[str]) -> Optional[str]:
            ordered: List[str] = []
            seen = set()
            for item in candidates or []:
                text = str(item or "").strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                ordered.append(text)

            if not ordered:
                return None

            if gen_type == "video" or gen_type == "audio":
                for url in ordered:
                    lower_url = url.lower()
                    if any(token in lower_url for token in (".mp4", ".mov", ".webm", "video/", ".mp3", "audio/")):
                        return url

            return ordered[0]

        def _extract_kie_video_urls(value: Any) -> List[str]:
            video_like_urls: List[str] = []

            def _walk(node: Any):
                if node is None:
                    return

                if isinstance(node, str):
                    raw = node.strip()
                    if not raw:
                        return
                    if raw.startswith("http://") or raw.startswith("https://"):
                        lowered = raw.lower()
                        if any(token in lowered for token in (".mp4", ".mov", ".webm", "video/", ".mp3", "audio/")):
                            video_like_urls.append(raw)
                        return
                    if raw.startswith("{") or raw.startswith("["):
                        try:
                            parsed = json.loads(raw)
                            _walk(parsed)
                        except Exception:
                            pass
                    return

                if isinstance(node, list):
                    for item in node:
                        _walk(item)
                    return

                if isinstance(node, dict):
                    for key, item in node.items():
                        key_lower = str(key or "").strip().lower()
                        if key_lower in {
                            "videourl",
                            "video_url",
                            "resultvideourl",
                            "result_video_url",
                            "outputvideourl",
                            "output_video_url",
                            "audiourl",
                            "audio_url",
                        }:
                            if isinstance(item, str):
                                text = item.strip()
                                if text.startswith("http://") or text.startswith("https://"):
                                    video_like_urls.append(text)
                            elif isinstance(item, list):
                                for sub in item:
                                    if isinstance(sub, str):
                                        text = sub.strip()
                                        if text.startswith("http://") or text.startswith("https://"):
                                            video_like_urls.append(text)
                            continue
                        _walk(item)

            _walk(value)

            deduped: List[str] = []
            seen_urls = set()
            for url in video_like_urls:
                stable = str(url or "").strip()
                if not stable or stable in seen_urls:
                    continue
                seen_urls.add(stable)
                deduped.append(stable)
            return deduped

        is_public_deploy = bool(
            str(os.getenv("RENDER_EXTERNAL_URL") or "").strip()
            or str(os.getenv("RENDER") or "").strip()
            or str(os.getenv("RAILWAY_STATIC_URL") or "").strip()
        )

        # Callback-assisted jobs still need long polling fallback when provider callbacks are delayed.
        kie_min_poll_timeout_seconds = max(
            120,
            int(os.getenv("KIE_MIN_POLL_TIMEOUT_SECONDS", "900") or 900),
        )
        raw_tool_poll_timeout = tool_conf.get("poll_timeout_seconds")
        raw_tool_timeout = tool_conf.get("timeout")

        poll_timeout_seconds = max(kie_min_poll_timeout_seconds, DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS)
        if callback_assisted_job:
            try:
                poll_timeout_seconds = max(
                    kie_min_poll_timeout_seconds,
                    int(
                        os.getenv(
                            "KIE_CALLBACK_ASSISTED_POLL_TIMEOUT_SECONDS",
                            "900",
                        )
                    ),
                )
            except Exception:
                poll_timeout_seconds = kie_min_poll_timeout_seconds
        try:
            if tool_conf.get("poll_timeout_seconds") is not None:
                poll_timeout_seconds = max(kie_min_poll_timeout_seconds, int(tool_conf.get("poll_timeout_seconds")))
            elif tool_conf.get("timeout") is not None:
                poll_timeout_seconds = max(kie_min_poll_timeout_seconds, int(tool_conf.get("timeout")))
        except Exception:
            poll_timeout_seconds = max(kie_min_poll_timeout_seconds, DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS)

        # Strategy:
        # - keep callback as the preferred completion path when available
        # - keep polling responsive enough that local state does not lag far behind provider completion
        poll_interval_seconds = 5 if callback_assisted_job else 2
        if callback_enabled and is_public_deploy:
            poll_interval_seconds = max(poll_interval_seconds, 3)
        elif callback_enabled:
            poll_interval_seconds = max(poll_interval_seconds, 2)
        try:
            if tool_conf.get("poll_interval_seconds") is not None:
                poll_interval_seconds = max(2, int(tool_conf.get("poll_interval_seconds")))
        except Exception:
            pass

        logger.info(
            "KIE poll strategy | task_id=%s callback_enabled=%s callback_assisted_job=%s timeout_seconds=%s interval_seconds=%s min_timeout_seconds=%s raw_poll_timeout=%s raw_timeout=%s",
            task_id,
            callback_enabled,
            callback_assisted_job,
            poll_timeout_seconds,
            poll_interval_seconds,
            kie_min_poll_timeout_seconds,
            raw_tool_poll_timeout,
            raw_tool_timeout,
        )

        poll_attempts = max(1, int(poll_timeout_seconds / max(1, poll_interval_seconds)))
        last_poll_state_marker: Optional[str] = None

        def _poll_status():
            param_candidates = [
                {"taskId": task_id},
                {"task_id": task_id},
                {"id": task_id},
            ]
            endpoint_candidates = [query_url]
            if "/recordInfo" in query_url:
                endpoint_candidates.append(query_url.replace("/recordInfo", "/record-info"))
            elif "/record-info" in query_url:
                endpoint_candidates.append(query_url.replace("/record-info", "/recordInfo"))

            last_resp = None
            for endpoint in endpoint_candidates:
                for params in param_candidates:
                    try:
                        resp = requests.get(endpoint, params=params, headers=headers, timeout=45, verify=False)
                        last_resp = resp
                        if resp.status_code == 200:
                            return resp
                    except Exception:
                        continue

                # Some KIE routes are POST query APIs in specific deployments.
                for body in param_candidates:
                    try:
                        resp = requests.post(endpoint, json=body, headers=headers, timeout=45, verify=False)
                        last_resp = resp
                        if resp.status_code == 200:
                            return resp
                    except Exception:
                        continue

            if last_resp is not None:
                return last_resp
            return requests.get(query_url, params={"taskId": task_id}, headers=headers, timeout=45, verify=False)

        for i in range(poll_attempts):
            await asyncio.sleep(poll_interval_seconds)
            try:
                poll_resp = await asyncio.to_thread(_poll_status)
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                continue

            if poll_resp.status_code != 200:
                if i % 10 == 0:
                    logger.info("KIE poll non-200 | status=%s task_id=%s", poll_resp.status_code, task_id)
                continue

            try:
                poll_data = poll_resp.json()
            except Exception:
                continue

            poll_code = poll_data.get("code")
            # Official docs may show non-200 business codes with msg=success + data.creditsConsumed.
            if not _is_ok_code(poll_code) and not _kie_response_looks_successful(poll_data):
                continue

            record_raw = poll_data.get("data") or poll_data.get("result") or poll_data
            if isinstance(record_raw, list):
                record = record_raw[0] if (record_raw and isinstance(record_raw[0], dict)) else {}
            elif isinstance(record_raw, dict):
                record = record_raw
            else:
                record = {}

            state = str(record.get("state") or record.get("status") or poll_data.get("state") or poll_data.get("status") or "").strip().lower()
            success_flag = record.get("successFlag")
            if success_flag is None:
                success_flag = record.get("success_flag")
            if success_flag is None and isinstance(record.get("response"), dict):
                success_flag = record.get("response", {}).get("successFlag")

            if isinstance(success_flag, str):
                success_flag = success_flag.strip().lower()

            video_urls = _extract_kie_video_urls(record.get("resultJson"))
            if not video_urls:
                video_urls = _extract_kie_video_urls(record)
            if not video_urls and isinstance(record.get("response"), dict):
                video_urls = _extract_kie_video_urls(record.get("response"))

            poll_state_marker = f"{state or '<empty>'}|{success_flag}|{len(video_urls)}"
            if poll_state_marker != last_poll_state_marker:
                logger.info(
                    "KIE poll state change | task_id=%s attempt=%s/%s state=%s success_flag=%s media_url_count=%s creditsConsumed=%s record_keys=%s",
                    task_id,
                    i + 1,
                    poll_attempts,
                    state or None,
                    success_flag,
                    len(video_urls),
                    record.get("creditsConsumed") if isinstance(record, dict) else None,
                    sorted([str(key) for key in record.keys()])[:20] if isinstance(record, dict) else [],
                )
                last_poll_state_marker = poll_state_marker

            if state in {"waiting", "queued", "queuing", "processing", "running", "generating", "pending", "submitted", "in_progress", "in-progress"}:
                continue
            if success_flag in {0, "0", False, "false", "failed", "error"}:
                continue

            result_payload = record.get("resultJson")
            video_urls = _extract_kie_video_urls(result_payload)
            if not video_urls:
                video_urls = _extract_kie_video_urls(record)
            if not video_urls and isinstance(record.get("response"), dict):
                video_urls = _extract_kie_video_urls(record.get("response"))

            # Upstream may omit/lag status while URLs are already ready.
            if video_urls and state not in {"fail", "failed", "error", "canceled", "cancelled"}:
                if gen_type == "video" or gen_type == "audio":
                    selected_video_url = _pick_preferred_kie_media_url(video_urls)
                    if selected_video_url:
                        return {"url": selected_video_url, "metadata": _build_success_meta(poll_data, record)}

            if state in {"success", "succeeded", "completed", "done", "finish", "finished", "complete", "successed"}:

                if gen_type == "video" or gen_type == "audio":
                    selected_video_url = _pick_preferred_kie_media_url(video_urls)
                    if selected_video_url:
                        return {"url": selected_video_url, "metadata": _build_success_meta(poll_data, record)}

                urls = self._extract_urls_from_payload(result_payload)
                if not urls:
                    urls = self._extract_urls_from_payload(record)
                selected_url = _pick_preferred_kie_media_url(urls)
                if not selected_url:
                    logger.error(
                        "KIE poll succeeded without media URL | task_id=%s state=%s success_flag=%s raw=%s",
                        task_id,
                        state or None,
                        success_flag,
                        _truncate_kie_log_value(poll_data),
                    )
                    return {"error": "KIE task succeeded but no media URL found", "details": poll_data}

                return {"url": selected_url, "metadata": _build_success_meta(poll_data, record)}
            if success_flag in {1, "1", True, "true", "success", "succeeded"}:
                video_urls = _extract_kie_video_urls(record.get("resultUrls"))
                if not video_urls:
                    video_urls = _extract_kie_video_urls(record)
                if not video_urls and isinstance(record.get("response"), dict):
                    video_urls = _extract_kie_video_urls(record.get("response"))

                if gen_type == "video" or gen_type == "audio":
                    selected_video_url = _pick_preferred_kie_media_url(video_urls)
                    if selected_video_url:
                        return {"url": selected_video_url, "metadata": _build_success_meta(poll_data, record)}

                urls = self._extract_urls_from_payload(record.get("resultUrls"))
                if not urls:
                    urls = self._extract_urls_from_payload(record)
                if not urls and isinstance(record.get("response"), dict):
                    urls = self._extract_urls_from_payload(record.get("response"))
                selected_url = _pick_preferred_kie_media_url(urls)
                if not selected_url:
                    logger.error(
                        "KIE poll successFlag without media URL | task_id=%s state=%s success_flag=%s raw=%s",
                        task_id,
                        state or None,
                        success_flag,
                        _truncate_kie_log_value(poll_data),
                    )
                    return {"error": "KIE task succeeded but no media URL found", "details": poll_data}
                return {"url": selected_url, "metadata": _build_success_meta(poll_data, record)}

            if state in {"fail", "failed", "error", "canceled", "cancelled", "abort", "aborted", "timeout"}:
                logger.error(
                    "KIE poll terminal failure | task_id=%s state=%s success_flag=%s details=%s raw=%s",
                    task_id,
                    state or None,
                    success_flag,
                    _truncate_kie_log_value(record.get("failMsg") or record.get("message") or poll_data, limit=800),
                    _truncate_kie_log_value(poll_data),
                )
                return {
                    "error": "KIE generation failed",
                    "details": record.get("failMsg") or record.get("message") or poll_data,
                    "runtime_model": submitted_model,
                }
            if success_flag in {2, "2", 3, "3", "2", "3", "cancelled", "canceled"}:
                logger.error(
                    "KIE poll terminal failure by success_flag | task_id=%s state=%s success_flag=%s raw=%s",
                    task_id,
                    state or None,
                    success_flag,
                    _truncate_kie_log_value(poll_data),
                )
                return {
                    "error": "KIE generation failed",
                    "details": record.get("failMsg") or record.get("message") or poll_data,
                    "runtime_model": submitted_model,
                }

        logger.error("KIE polling timeout | task_id=%s attempts=%s interval=%s", task_id, poll_attempts, poll_interval_seconds)
        return {"error": "Timeout polling KIE task"}

    # -- Helpers --
    def _download_and_save(
        self,
        url: str,
        filename_base: str = None,
        user_id: int = 1,
        storage_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        try:
             if url.startswith("data:"):
                 marker = ";base64,"
                 idx = url.find(marker)
                 if idx > 5:
                     mime = url[5:idx].strip().lower() or "application/octet-stream"
                     encoded = url[idx + len(marker):].strip()
                     binary = base64.b64decode(encoded)
                     ext = mimetypes.guess_extension(mime) or ".bin"
                     if ext == ".jpe":
                         ext = ".jpg"
                     filename = f"gen_{uuid.uuid4().hex[:8]}{ext}"
                     if filename_base:
                         filename = f"{filename_base}_{filename}"
                     return self._persist_generated_bytes(
                         binary,
                         user_id=user_id,
                         filename=filename,
                         content_type=mime,
                        metadata=storage_metadata,
                     )

             if url.startswith("/"): return url
             if "localhost" in url or "127.0.0.1" in url: return url

             def _fetch_remote_media(use_proxy: bool = True):
                 kwargs = {
                     "stream": True,
                     "timeout": 600,
                     "headers": {"User-Agent": "Mozilla/5.0"},
                     "verify": False,
                 }
                 if not use_proxy:
                     kwargs["proxies"] = {"http": None, "https": None}
                 return requests.get(url, **kwargs)

             response = None
             fetch_errors: List[str] = []
             for use_proxy in (True, False):
                 try:
                     candidate = _fetch_remote_media(use_proxy=use_proxy)
                 except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as fetch_err:
                     fetch_errors.append(f"proxy={'on' if use_proxy else 'off'} err={fetch_err}")
                     continue
                 if candidate.status_code == 200:
                     response = candidate
                     break
                 fetch_errors.append(f"proxy={'on' if use_proxy else 'off'} status={candidate.status_code}")
                 if use_proxy:
                     continue
                 response = candidate

             if response is None:
                 detail = "; ".join(fetch_errors) if fetch_errors else "unknown fetch error"
                 _debug_log(f"Download failed: {detail} for {url}", "error")
                 raise ValueError(detail)

             if response.status_code != 200:
                _debug_log(f"Download failed: HTTP {response.status_code} for {url}", "error")
                raise ValueError(f"HTTP {response.status_code}")

             if response.status_code == 200:
                from urllib.parse import urlparse

                ct = str(response.headers.get("Content-Type", "")).split(";")[0].strip().lower()
                path_ext = os.path.splitext(urlparse(url).path or "")[1].lower()

                ext_by_ct = {
                    "image/png": ".png",
                    "image/jpeg": ".jpg",
                    "image/jpg": ".jpg",
                    "image/webp": ".webp",
                    "image/gif": ".gif",
                    "image/bmp": ".bmp",
                    "video/mp4": ".mp4",
                    "video/quicktime": ".mov",
                    "video/webm": ".webm",
                    "video/x-msvideo": ".avi",
                    "video/x-matroska": ".mkv",
                    "audio/mpeg": ".mp3",
                    "audio/mp3": ".mp3",
                    "audio/wav": ".wav",
                    "audio/x-wav": ".wav",
                    "audio/mp4": ".m4a",
                    "audio/aac": ".aac",
                    "audio/flac": ".flac",
                    "audio/ogg": ".ogg",
                    "audio/opus": ".opus",
                }

                allowed_exts = {
                    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
                    ".mp4", ".mov", ".webm", ".avi", ".mkv",
                    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
                }

                ext = ext_by_ct.get(ct)
                if not ext and path_ext in allowed_exts:
                    ext = path_ext

                if not ext:
                    if "video" in ct:
                        ext = ".mp4"
                    elif "audio" in ct:
                        ext = ".mp3"
                    elif "image" in ct:
                        ext = ".png"
                    else:
                        ext = ".bin"
                
                filename = f"gen_{uuid.uuid4().hex[:8]}{ext}"
                if filename_base:
                    filename = f"{filename_base}_{filename}"

                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                file_path = temp_file.name
                try:
                    with temp_file:
                        for chunk in response.iter_content(4096):
                            if chunk:
                                temp_file.write(chunk)

                    if ext == ".mp4":
                        try:
                            if optimize_mp4_faststart(file_path):
                                _debug_log(f"[MediaService] Applied mp4 faststart optimization: {file_path}")
                        except Exception as faststart_error:
                            _debug_log(f"[MediaService] MP4 faststart optimization skipped: {faststart_error}", "warning")

                    resolved_content_type = ct or mimetypes.guess_type(filename)[0] or "application/octet-stream"
                    return self._finalize_generated_file(
                        file_path,
                        user_id=user_id,
                        filename=filename,
                        content_type=resolved_content_type,
                        metadata=storage_metadata,
                    )
                except Exception:
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    raise
        except Exception as e:
            _debug_log(f"Download failed: {e}", "error")
            logger.warning(
                "[MediaService] remote media download/save failed | url=%s err=%s",
                url,
                e,
            )
        return url

    async def _process_veo_image_async(self, url_or_path, aspect_ratio):
        return await asyncio.to_thread(self._process_veo_image, url_or_path, aspect_ratio)

    def _process_veo_image(self, url_or_path, aspect_ratio):
        """Helper to resize/crop images to strictly match Veo aspect ratio requirements"""
        raw_url = str(url_or_path or '').strip()
        if self._is_public_http_url(raw_url): return raw_url
        if raw_url.startswith('/uploads/'):
            public_url = self._resolve_public_upload_url(raw_url)
            if public_url: return public_url
        try:
            # Reuse base fetch logic
            b64_raw = self._get_image_base64_for_api(url_or_path, force_data_uri=False)
            if not b64_raw: return ""
            
            img_data = base64.b64decode(b64_raw)
            with Image.open(io.BytesIO(img_data)) as orig_img:
                img = orig_img.convert("RGB")
            
            # Default target (16:9)
            w, h = 1280, 720
            
            # Map common ratios
            ar_map = {
                "16:9": (1280, 720),
                "9:16": (720, 1280),
                "1:1": (1024, 1024),
                "4:3": (1024, 768),
                "3:4": (768, 1024),
                "21:9": (1920, 816),
                "2.35:1": (1920, 816)
            }
            if aspect_ratio in ar_map: w, h = ar_map[aspect_ratio]
            
            # Resize/Crop logic
            target_aspect = w / h
            current_aspect = img.width / img.height
            
            # Crop to matching aspect ratio first
            if abs(current_aspect - target_aspect) > 0.05:
                if current_aspect > target_aspect:
                    # Too wide: crop width
                    new_w = int(img.height * target_aspect)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                else:
                    # Too tall: crop height
                    new_h = int(img.width / target_aspect)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))
                    
            # Resize to target resolution if needed
            if img.width != w or img.height != h:
                # Use LANDZOS if available, else standard
                resample = getattr(Image, 'LANCZOS', Image.BICUBIC)
                img = img.resize((w, h), resample)
                
            # VEO API is sensitive to input image payload size. Prefer JPEG and progressively reduce.
            # KIE Veo may enforce a stricter per-image limit than source docs for some routes.
            max_bytes = max(40 * 1024, int(os.getenv("KIE_VEO_IMAGE_MAX_BYTES", str(90 * 1024))))
            quality_steps = [82, 74, 66, 58, 50, 44, 38]
            scale_steps = [1.0, 0.85, 0.7, 0.6, 0.5]
            best_data = b""

            for scale in scale_steps:
                if scale < 1.0:
                    scaled_w = max(320, int(w * scale))
                    scaled_h = max(320, int(h * scale))
                    scaled_img = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
                else:
                    scaled_img = img

                for quality in quality_steps:
                    out = io.BytesIO()
                    scaled_img.save(out, format='JPEG', quality=quality, optimize=True)
                    candidate = out.getvalue()
                    best_data = candidate
                    if len(candidate) <= max_bytes:
                        break

                if best_data and len(best_data) <= max_bytes:
                    break

            if not best_data:
                return ""

            _debug_log(f"[Veo] Ref processed size={len(best_data)} bytes target<={max_bytes} ratio={aspect_ratio}")
            b64_final = base64.b64encode(best_data).decode('utf-8')
            return f"data:image/jpeg;base64,{b64_final}"
            
        except Exception as e:
            _debug_log(f"[Veo] Image Process Error: {e}", "error")
            import traceback
            traceback.print_exc()
            return ""

    def _is_public_http_url(self, value: Any) -> bool:
        raw = str(value or "").strip()
        if not raw.lower().startswith(("http://", "https://")):
            return False
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(raw)
            host = (parsed.hostname or "").strip().lower()
            if not host:
                return False
            if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
                return False
            try:
                ip_obj = ipaddress.ip_address(host)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                    return False
            except Exception:
                pass
            return True
        except Exception:
            return False

    async def _resolve_ref_for_api_async(self, url_or_path, force_data_uri_for_local=True, prefer_public_upload_url=True, data_uri_profile=None):
        return await asyncio.to_thread(self._resolve_ref_for_api, url_or_path, force_data_uri_for_local, prefer_public_upload_url, data_uri_profile)

    def _resolve_ref_for_api(self, url_or_path, force_data_uri_for_local=True, prefer_public_upload_url=True, data_uri_profile: Optional[str] = None):
        if isinstance(url_or_path, list):
            if not url_or_path:
                return None
            url_or_path = url_or_path[0]

        raw = str(url_or_path or "").strip()
        if not raw:
            return None
        if raw.startswith("asset://"):
            return None
        if raw.startswith("data:"):
            optimized = self._optimize_data_uri_image(raw, profile=data_uri_profile)
            return optimized or raw
        if self._is_public_http_url(raw):
            # Ensure managed OSS URLs (e.g. Qiniu) are always refreshed to signed URLs
            # before they are sent to upstream providers as reference images.
            if oss_storage_service.is_managed_url(raw):
                return str(oss_storage_service.refresh_url(raw) or raw)
            return raw
        if prefer_public_upload_url:
            public_url = self._resolve_public_upload_url(raw)
            if public_url:
                if oss_storage_service.is_managed_url(public_url):
                    return str(oss_storage_service.refresh_url(public_url) or public_url)
                return public_url

        encoded = self._get_image_base64_for_api(raw, force_data_uri=force_data_uri_for_local, data_uri_profile=data_uri_profile)
        if not encoded or encoded == raw:
            return None
        return encoded

    def _resolve_public_upload_url(self, url_or_path: Any) -> Optional[str]:
        raw = str(url_or_path or "").strip()
        if not raw:
            return None
        if self._is_public_http_url(raw):
            return raw

        upload_suffix = ""
        if raw.startswith("/uploads/"):
            upload_suffix = raw
        elif "/uploads/" in raw:
            upload_suffix = raw[raw.index("/uploads/"):]

        if not upload_suffix:
            return None

        public_base = str(
            os.getenv("AISTORY_PUBLIC_BASE_URL")
            or os.getenv("PUBLIC_BASE_URL")
            or str(getattr(settings, "RENDER_EXTERNAL_URL", "") or "")
            or os.getenv("RENDER_EXTERNAL_URL")
            or ""
        ).strip().rstrip("/")
        if not public_base:
            public_base = self._resolve_public_base_url()
        if not public_base:
            return None
        if not re.match(r"^https?://", public_base, flags=re.IGNORECASE):
            public_base = f"https://{public_base}"
        return f"{public_base}{upload_suffix}"

    def _resolve_public_base_url(self) -> str:
        public_base = str(
            os.getenv("AISTORY_PUBLIC_BASE_URL")
            or os.getenv("PUBLIC_BASE_URL")
            or str(getattr(settings, "RENDER_EXTERNAL_URL", "") or "")
            or os.getenv("RENDER_EXTERNAL_URL")
            or os.getenv("RAILWAY_STATIC_URL")
            or ""
        ).strip()

        if not public_base:
            frontend_url = str(
                os.getenv("AISTORY_FRONTEND_BASE_URL")
                or os.getenv("FRONTEND_BASE_URL")
                or str(getattr(settings, "FRONTEND_BASE_URL", "") or "")
                or ""
            ).strip()
            try:
                match = re.match(r"^https?://[^/]+", frontend_url, flags=re.IGNORECASE)
                frontend_origin = match.group(0) if match else ""
            except Exception:
                frontend_origin = ""
            if frontend_origin:
                public_base = frontend_origin
                public_base = public_base.replace("-frontend.", "-backend.")
                public_base = public_base.replace("frontend.onrender.com", "backend.onrender.com")

        if public_base and not re.match(r"^https?://", public_base, flags=re.IGNORECASE):
            public_base = f"https://{public_base}"
        return public_base.rstrip("/")

    def _is_public_deployment_hint(self) -> bool:
        """True only when a cloud/public base can actually receive provider webhooks.

        FRONTEND_BASE_URL alone is not enough — local Vite often sets it, and providers
        cannot reach localhost. Match queue ``pure_callback_mode_auto`` deploy signals.
        """
        return bool(
            str(os.getenv("AISTORY_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL") or "").strip()
            or str(getattr(settings, "RENDER_EXTERNAL_URL", "") or "").strip()
            or str(os.getenv("RENDER_EXTERNAL_URL") or "").strip()
            or str(os.getenv("RENDER") or "").strip()
            or str(os.getenv("RAILWAY_STATIC_URL") or "").strip()
            or str(os.getenv("RAILWAY_PUBLIC_DOMAIN") or "").strip()
            or str(os.getenv("VERCEL_URL") or "").strip()
        )

    def _resolve_provider_callback_url(self, tool_conf: Dict[str, Any], callback_ticket: str) -> str:
        callback_url = str(
            tool_conf.get("webhookUrl")
            or tool_conf.get("webHook")
            or tool_conf.get("webhook")
            or tool_conf.get("callBackUrl")
            or tool_conf.get("callback_url")
            or tool_conf.get("callbackUrl")
            or ""
        ).strip()

        if callback_url and callback_url != "-1":
            return callback_url

        if not self._is_public_deployment_hint():
            return "-1" if callback_url == "-1" else ""

        public_base = self._resolve_public_base_url()
        if not public_base:
            return "-1" if callback_url == "-1" else ""

        api_prefix = str(getattr(settings, "API_V1_STR", "/api/v1") or "/api/v1").strip("/")
        return f"{public_base}/{api_prefix}/generate/callback/{callback_ticket}"

    def _data_uri_image_size_bytes(self, value: Any) -> Optional[int]:
        raw = str(value or "")
        if not raw.startswith("data:image/"):
            return None
        marker = ";base64,"
        idx = raw.find(marker)
        if idx < 0:
            return None
        b64 = raw[idx + len(marker):]
        if not b64:
            return 0
        padding = 0
        if b64.endswith("=="):
            padding = 2
        elif b64.endswith("="):
            padding = 1
        # Approximate decoded size from base64 length without allocating decode buffer.
        return max(0, (len(b64) * 3) // 4 - padding)

    def _extract_data_uri_mime(self, value: Any) -> str:
        raw = str(value or "")
        if not raw.startswith("data:"):
            return ""
        marker = ";base64,"
        idx = raw.find(marker)
        if idx <= 5:
            return ""
        return raw[5:idx].strip().lower()

    def _normalize_data_uri_image_for_kie(self, data_uri: str, target_format: str = "JPEG") -> Optional[str]:
        raw = str(data_uri or "").strip()
        if not raw.startswith("data:image/"):
            return None

        marker = ";base64,"
        idx = raw.find(marker)
        if idx <= 0:
            return None

        b64_part = raw[idx + len(marker):].strip()
        if not b64_part:
            return None

        try:
            binary = base64.b64decode(b64_part)
            with Image.open(io.BytesIO(binary)) as img:
                work = img.convert("RGB")
                out = io.BytesIO()
                save_format = "JPEG" if str(target_format or "").strip().upper() == "JPEG" else "PNG"
                if save_format == "JPEG":
                    work.save(out, format="JPEG", quality=90, optimize=True)
                    mime = "image/jpeg"
                else:
                    work.save(out, format="PNG", optimize=True)
                    mime = "image/png"
                encoded = base64.b64encode(out.getvalue()).decode("utf-8")
                return f"data:{mime};base64,{encoded}"
        except Exception as e:
            logger.warning("KIE data-uri normalize failed | error=%s", str(e)[:300])
            return None

    async def _upload_kie_data_uri_async(self, data_uri, api_key, file_name=None, upload_path="veo-inputs"):
        return await asyncio.to_thread(self._upload_kie_data_uri, data_uri, api_key, file_name, upload_path)

    def _upload_kie_data_uri(self, data_uri: str, api_key: str, file_name: Optional[str] = None, upload_path: str = "veo-inputs") -> Optional[str]:
        if not data_uri or not str(data_uri).startswith("data:"):
            return None
        if not api_key:
            return None

        base_url = str(os.getenv("KIE_FILE_UPLOAD_BASE_URL", "https://kieai.redpandaai.co")).strip().rstrip("/")
        endpoint = f"{base_url}/api/file-base64-upload"
        payload: Dict[str, Any] = {
            "base64Data": data_uri,
            "uploadPath": upload_path,
        }
        if file_name:
            payload["fileName"] = file_name

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "KIE file upload attempt | mode=base64 endpoint=%s upload_path=%s file_name=%s mime=%s bytes=%s",
            endpoint,
            upload_path,
            file_name,
            self._extract_data_uri_mime(data_uri) or None,
            self._data_uri_image_size_bytes(data_uri),
        )

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=(15, 120), verify=False)
            if resp.status_code != 200:
                logger.warning("KIE file upload failed | status=%s body=%s", resp.status_code, (resp.text or "")[:500])
                return None

            data = resp.json() if resp.content else {}
            code = data.get("code") if isinstance(data, dict) else None
            success = data.get("success") if isinstance(data, dict) else None
            if code not in (None, 200, "200") and success is not True:
                logger.warning("KIE file upload rejected | code=%s msg=%s", code, (data.get("msg") if isinstance(data, dict) else ""))
                return None

            data_block = data.get("data") if isinstance(data, dict) else {}
            if not isinstance(data_block, dict):
                return None
            file_url = str(data_block.get("fileUrl") or data_block.get("downloadUrl") or "").strip()
            if file_url and file_url.startswith("http"):
                logger.info(
                    "KIE file upload success | mode=base64 file_name=%s hosted_url=%s",
                    file_name,
                    file_url,
                )
                return file_url
            return None
        except Exception as e:
            logger.warning("KIE file upload exception | error=%s", str(e)[:300])
            return None

    def _upload_kie_file_url(self, file_url: str, api_key: str, file_name: Optional[str] = None, upload_path: str = "market-inputs") -> Optional[str]:
        raw_url = str(file_url or "").strip()
        if not raw_url.startswith("http"):
            return None
        if not api_key:
            return None

        # KIE file-url upload is sensitive to non-ASCII/unsafe URL characters.
        # Normalize URL path and query encoding so remote fetchers can resolve it reliably.
        try:
            from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

            parsed = urlparse(raw_url)
            encoded_path = quote(parsed.path or "", safe="/%._-~")
            encoded_query = urlencode(parse_qsl(parsed.query or "", keep_blank_values=True), doseq=True)
            normalized_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                encoded_path,
                parsed.params,
                encoded_query,
                parsed.fragment,
            ))
        except Exception:
            normalized_url = raw_url

        base_url = str(os.getenv("KIE_FILE_UPLOAD_BASE_URL", "https://kieai.redpandaai.co")).strip().rstrip("/")
        endpoint = f"{base_url}/api/file-url-upload"
        payload: Dict[str, Any] = {
            "fileUrl": normalized_url,
            "uploadPath": upload_path,
        }
        if file_name:
            payload["fileName"] = file_name

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "KIE file upload attempt | mode=file_url endpoint=%s upload_path=%s file_name=%s file_url=%s",
            endpoint,
            upload_path,
            file_name,
            normalized_url[:500],
        )

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=(15, 120), verify=False)
            if resp.status_code != 200:
                logger.warning("KIE file-url upload failed | status=%s body=%s", resp.status_code, (resp.text or "")[:500])
                return None

            data = resp.json() if resp.content else {}
            code = data.get("code") if isinstance(data, dict) else None
            success = data.get("success") if isinstance(data, dict) else None
            if code not in (None, 200, "200") and success is not True:
                logger.warning("KIE file-url upload rejected | code=%s msg=%s", code, (data.get("msg") if isinstance(data, dict) else ""))
                return None

            data_block = data.get("data") if isinstance(data, dict) else {}
            if not isinstance(data_block, dict):
                return None
            hosted_url = str(data_block.get("fileUrl") or data_block.get("downloadUrl") or "").strip()
            if hosted_url.startswith("http"):
                logger.info(
                    "KIE file upload success | mode=file_url file_name=%s hosted_url=%s",
                    file_name,
                    hosted_url,
                )
                return hosted_url
            return None
        except Exception as e:
            logger.warning("KIE file-url upload exception | error=%s", str(e)[:300])
            return None

    async def _upload_kie_ref_to_hosted_url_async(self, ref_value, api_key, upload_path="market-inputs", file_name_prefix="kie-input"):
        return await asyncio.to_thread(self._upload_kie_ref_to_hosted_url, ref_value, api_key, upload_path, file_name_prefix)

    def _upload_kie_ref_to_hosted_url(self, ref_value: Any, api_key: str, upload_path: str = "market-inputs", file_name_prefix: str = "kie-input") -> Optional[str]:
        ref_text = str(ref_value or "").strip()
        if not ref_text or not api_key:
            return None

        if ref_text.startswith("http"):
            from urllib.parse import urlparse
            guessed_ext = os.path.splitext(urlparse(ref_text).path or "")[1] or ""
            safe_ext = guessed_ext if guessed_ext and len(guessed_ext) <= 8 else ""
            hosted = self._upload_kie_file_url(
                ref_text,
                api_key=api_key,
                file_name=f"{file_name_prefix}-{uuid.uuid4().hex[:10]}{safe_ext}",
                upload_path=upload_path,
            )
            if hosted:
                return hosted

            # Fallback: if KIE cannot pull the public URL directly, download and upload as base64.
            fallback_data_uri = self._get_image_base64_for_api(ref_text, force_data_uri=True)
            fallback_data_uri = str(fallback_data_uri or "").strip()
            if fallback_data_uri.startswith("data:"):
                fallback_hosted = self._upload_kie_data_uri(
                    fallback_data_uri,
                    api_key=api_key,
                    file_name=f"{file_name_prefix}-{uuid.uuid4().hex[:10]}{safe_ext or '.jpg'}",
                    upload_path=upload_path,
                )
                if fallback_hosted:
                    logger.info("KIE reference upload fallback succeeded | mode=base64 file_name_prefix=%s", file_name_prefix)
                    return fallback_hosted
            logger.warning(
                "KIE reference upload failed | ref_kind=public_url ref_preview=%s file_name_prefix=%s",
                ref_text[:300],
                file_name_prefix,
            )
            return None

        data_uri = ref_text
        if not ref_text.startswith("data:"):
            resolved = self._resolve_ref_for_api(ref_text, force_data_uri_for_local=True)
            data_uri = str(resolved or "").strip()

        if not data_uri.startswith("data:"):
            return None

        mime = self._extract_data_uri_mime(data_uri)
        ext = ".jpg"
        if "png" in mime:
            ext = ".png"
        elif "webp" in mime:
            ext = ".webp"
        elif "gif" in mime:
            ext = ".gif"
        elif "mp4" in mime:
            ext = ".mp4"

        hosted = self._upload_kie_data_uri(
            data_uri,
            api_key=api_key,
            file_name=f"{file_name_prefix}-{uuid.uuid4().hex[:10]}{ext}",
            upload_path=upload_path,
        )
        if not hosted:
            logger.warning(
                "KIE reference upload failed | ref_kind=local_or_data_uri ref_preview=%s file_name_prefix=%s mime=%s",
                ref_text[:300],
                file_name_prefix,
                mime or None,
            )
        return hosted

    def _resolve_data_uri_optimization_limits(self, profile: Optional[str] = None) -> tuple[int, int]:
        normalized_profile = str(profile or "").strip().lower()
        if normalized_profile == "grsai_image_ref":
            max_bytes = max(192 * 1024, int(os.getenv("GRSAI_IMAGE_REF_DATA_URI_MAX_BYTES", str(512 * 1024))))
            max_edge = max(768, int(os.getenv("GRSAI_IMAGE_REF_DATA_URI_MAX_EDGE", "1280")))
            return max_bytes, max_edge
        if normalized_profile == "n1n_image_ref":
            max_bytes = max(256 * 1024, int(os.getenv("N1N_IMAGE_REF_DATA_URI_MAX_BYTES", str(2 * 1024 * 1024))))
            max_edge = max(512, int(os.getenv("N1N_IMAGE_REF_DATA_URI_MAX_EDGE", "1536")))
            return max_bytes, max_edge

        max_bytes = max(512 * 1024, int(os.getenv("VIDEO_REF_DATA_URI_MAX_BYTES", str(6 * 1024 * 1024))))
        max_edge = max(512, int(os.getenv("VIDEO_REF_DATA_URI_MAX_EDGE", "2048")))
        return max_bytes, max_edge

    def _optimize_image_bytes_for_data_uri(self, data: bytes, mime: str = "image/png", profile: Optional[str] = None) -> tuple[bytes, str]:
        # Keep provider compatibility while avoiding very large JSON request payloads.
        max_bytes, max_edge = self._resolve_data_uri_optimization_limits(profile)

        if not data:
            return data, mime

        # Fast path: already small enough.
        if len(data) <= max_bytes:
            return data, mime

        try:
            with Image.open(io.BytesIO(data)) as img:
                has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
                # JPEG cannot carry alpha; flatten to white background.
                if has_alpha:
                    work = Image.new("RGB", img.size, (255, 255, 255))
                    alpha_src = img.convert("RGBA")
                    work.paste(alpha_src, mask=alpha_src.split()[-1])
                else:
                    work = img.convert("RGB")

                if max(work.width, work.height) > max_edge:
                    work.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

                quality_steps = [90, 84, 78, 72, 66, 60, 52]
                best_bytes = b""
                for q in quality_steps:
                    out = io.BytesIO()
                    work.save(out, format="JPEG", quality=q, optimize=True)
                    candidate = out.getvalue()
                    best_bytes = candidate
                    if len(candidate) <= max_bytes:
                        break

                if best_bytes:
                    return best_bytes, "image/jpeg"
        except Exception as e:
            _debug_log(f"[MediaService] Image optimize skipped: {e}", "warning")

        return data, mime

    def _optimize_data_uri_image(self, value: Any, profile: Optional[str] = None) -> Optional[str]:
        raw = str(value or "").strip()
        if not raw.startswith("data:image/"):
            return None

        marker = ";base64,"
        idx = raw.find(marker)
        if idx <= 0:
            return None

        mime = raw[5:idx].strip().lower() or "image/png"
        b64_part = raw[idx + len(marker):].strip()
        if not b64_part:
            return None

        try:
            binary = base64.b64decode(b64_part)
        except Exception:
            return None

        optimized_bytes, optimized_mime = self._optimize_image_bytes_for_data_uri(binary, mime, profile=profile)
        if not optimized_bytes:
            return None
        if optimized_bytes == binary and optimized_mime == mime:
            return raw

        encoded = base64.b64encode(optimized_bytes).decode("utf-8")
        return f"data:{optimized_mime};base64,{encoded}"

    def _resolve_ref_list_for_api(self, refs, force_data_uri_for_local=True, prefer_public_upload_url=True, data_uri_profile: Optional[str] = None):
        source = refs if isinstance(refs, list) else [refs]
        result = []
        for item in source:
            resolved = self._resolve_ref_for_api(
                item,
                force_data_uri_for_local=force_data_uri_for_local,
                prefer_public_upload_url=prefer_public_upload_url,
                data_uri_profile=data_uri_profile,
            )
            if resolved:
                result.append(resolved)
        return result

    async def _get_image_base64_for_api_async(self, url_or_path, force_data_uri=False, data_uri_profile=None):
        return await asyncio.to_thread(self._get_image_base64_for_api, url_or_path, force_data_uri, data_uri_profile)

    def _get_image_base64_for_api(self, url_or_path, force_data_uri=False, data_uri_profile: Optional[str] = None):
        # Helper to get base64 from local or remote
        # NOTE: This only processes ONE image. If list is passed, we take the first.
        # Callers MUST handle lists if they need multiple images.
        def _extract_ref_candidate(value: Any) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, str):
                candidate = value.strip()
                return candidate or None
            if isinstance(value, dict):
                direct_keys = [
                    "url",
                    "image_url",
                    "imageUrl",
                    "src",
                    "path",
                    "uri",
                    "href",
                    "value",
                ]
                for key in direct_keys:
                    raw = value.get(key)
                    if isinstance(raw, str) and raw.strip():
                        return raw.strip()

                nested_image = value.get("image")
                if isinstance(nested_image, dict):
                    nested_found = _extract_ref_candidate(nested_image)
                    if nested_found:
                        return nested_found

                media = value.get("media")
                if isinstance(media, dict):
                    nested_found = _extract_ref_candidate(media)
                    if nested_found:
                        return nested_found
                return None
            if isinstance(value, list):
                for item in value:
                    found = _extract_ref_candidate(item)
                    if found:
                        return found
                return None
            candidate = str(value).strip()
            return candidate or None

        if isinstance(url_or_path, list):
             if not url_or_path: return None
             url_or_path = url_or_path[0]

        extracted_ref = _extract_ref_candidate(url_or_path)
        if not extracted_ref:
            return None
        url_or_path = extracted_ref

        try:
            _debug_log(f"[MediaService] Conversion: Processing ref image: {str(url_or_path)[:100]}")
            data = None
            mime = "image/png"
            raw_ref = str(url_or_path or "").strip()
            normalized_ref = raw_ref.replace("\\", "/")

            def _guess_mime_from_path(path_value: str) -> str:
                lowered = str(path_value or "").strip().lower()
                if lowered.endswith((".jpg", ".jpeg")):
                    return "image/jpeg"
                if lowered.endswith(".webp"):
                    return "image/webp"
                if lowered.endswith(".gif"):
                    return "image/gif"
                return "image/png"

            def _resolve_local_ref_path(raw_value: str) -> Optional[str]:
                candidate = str(raw_value or "").strip()
                if not candidate:
                    return None

                if candidate.lower().startswith("file:///"):
                    from urllib.parse import unquote

                    candidate = unquote(candidate[8:])
                elif candidate.lower().startswith("file://"):
                    from urllib.parse import unquote

                    candidate = unquote(candidate[7:])

                candidate = candidate.strip().strip('"').strip("'")
                normalized_candidate = candidate.replace("\\", "/")

                local_candidates: List[str] = []

                if "/uploads/" in normalized_candidate:
                    upload_suffix = normalized_candidate.split("/uploads/", 1)[1].split("?", 1)[0].lstrip("/")
                    upload_dir = settings.UPLOAD_DIR
                    if not os.path.isabs(upload_dir):
                        upload_dir = os.path.abspath(upload_dir)
                    from urllib.parse import unquote

                    local_candidates.append(os.path.join(upload_dir, unquote(upload_suffix.replace("/", os.sep))))

                if os.path.isabs(candidate):
                    local_candidates.append(candidate)
                else:
                    workspace_candidate = os.path.abspath(candidate)
                    backend_candidate = os.path.abspath(os.path.join(os.getcwd(), candidate))
                    local_candidates.append(workspace_candidate)
                    if backend_candidate != workspace_candidate:
                        local_candidates.append(backend_candidate)

                for item in local_candidates:
                    try:
                        if item and os.path.exists(item):
                            return item
                    except Exception:
                        continue
                return None

            local_path = _resolve_local_ref_path(raw_ref)
            if local_path:
                logger.info("KIE local ref resolved | source=%s local_path=%s", raw_ref[:300], local_path)
                with open(local_path, "rb") as f:
                    data = f.read()
                mime = _guess_mime_from_path(local_path)
            elif raw_ref.startswith("http"):
                http_ref = raw_ref
                try:
                    if oss_storage_service.is_managed_url(http_ref):
                        http_ref = str(oss_storage_service.refresh_url(http_ref) or http_ref)
                except Exception:
                    pass

                r = requests.get(http_ref, timeout=30)
                if r.status_code == 200:
                    data = r.content
                    ct = r.headers.get("Content-Type", "")
                    if "jpeg" in ct:
                        mime = "image/jpeg"
                    elif "webp" in ct:
                        mime = "image/webp"
                    elif "gif" in ct:
                        mime = "image/gif"
                else:
                    _debug_log(f"[MediaService] Error: HTTP Download Failed {r.status_code}: {http_ref}", "error")
            
            if data:
                logger.info(
                    "KIE ref bytes loaded | source=%s mime=%s bytes=%s force_data_uri=%s",
                    raw_ref[:300],
                    mime,
                    len(data),
                    force_data_uri,
                )
                if force_data_uri:
                    before_size = len(data)
                    data, mime = self._optimize_image_bytes_for_data_uri(data, mime, profile=data_uri_profile)
                    after_size = len(data)
                    if after_size < before_size:
                        _debug_log(f"[MediaService] Ref optimized for data URI: {before_size} -> {after_size} bytes ({mime})")
                b64 = base64.b64encode(data).decode("utf-8")
                if force_data_uri: return f"data:{mime};base64,{b64}"
                return b64
            else:
                _debug_log(f"[MediaService] Error: No Data retrieved for {url_or_path} | normalized={normalized_ref[:200]}", "error")
        except Exception as e:
            _debug_log(f"[MediaService] Exception in Base64 Conversion: {e}", "error")
        
        return url_or_path # Return original if fail

media_service = MediaGenerationService()

