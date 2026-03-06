
import requests
import re
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
from PIL import Image
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from app.db.session import SessionLocal
from app.models.all_models import APISetting, SystemAPISetting
from app.core.config import settings
from sqlalchemy import cast, String, func

# Suppress InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import logging
logger = logging.getLogger("media_service")
# ... imports ...

DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS = min(600, max(300, int(os.getenv("VIDEO_POLL_TIMEOUT_SECONDS", "600"))))

class MediaGenerationService:
# ...
    DOUBAO_MIN_IMAGE_PIXELS = 3_686_400
    SMART_ROUTER_PROVIDER = "smart_router"
    _provider_key_cursors: Dict[str, int] = {}

    def _provider_ci_filter(self, provider: Any):
        provider_norm = str(provider or "").strip().lower()
        return func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm

    def _vendor_label(self, provider: Any) -> str:
        raw = str(provider or "").strip()
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

    def _merge_negative_prompt(self, prompt: Any, negative_prompt: Any) -> str:
        base_prompt = str(prompt or "").strip()
        neg_prompt = str(negative_prompt or "").strip()
        if not neg_prompt:
            return base_prompt
        if re.search(r"negative\s*prompt\s*:", base_prompt, flags=re.IGNORECASE):
            return base_prompt
        if base_prompt:
            return f"{base_prompt}\n\nNegative prompt constraints: {neg_prompt}"
        return f"Negative prompt constraints: {neg_prompt}"

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

    def _normalize_aspect_ratio_value(self, aspect_ratio: Optional[str]) -> Optional[str]:
        raw = str(aspect_ratio or "").strip()
        if not raw:
            return None
        lowered = raw.lower()
        if lowered in {"adaptive", "auto"}:
            return "16:9"
        if raw == "2.35:1":
            return "21:9"
        return raw

    def _normalize_image_size_value(self, image_size: Optional[str]) -> Optional[str]:
        raw = str(image_size or "").strip().upper().replace(" ", "")
        if raw in {"1K", "2K", "4K"}:
            return raw
        return None

    def _is_deprecated_system_config(self, config_value: Any, deprecated_flag: Any = None) -> bool:
        if isinstance(deprecated_flag, bool):
            if deprecated_flag:
                return True
        elif deprecated_flag is not None and str(deprecated_flag).strip().lower() in {"1", "true", "yes", "y", "on"}:
            return True
        cfg = self._safe_json_dict(config_value)
        return bool(
            cfg.get("deprecated")
            or cfg.get("is_deprecated")
            or cfg.get("disable_api")
        )

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

    def _pick_runtime_api_key(self, config_value: Any, fallback_key: Any = None) -> str:
        cfg = self._safe_json_dict(config_value)
        pooled = self._normalize_api_keys(cfg.get("provider_api_keys"))
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

        if pooled:
            return _pick_from_pool(pooled)

        fallback_pool = self._normalize_api_keys(fallback_key)
        if fallback_pool:
            return _pick_from_pool(fallback_pool)
        return str(fallback_key or "").strip()

    def _collect_provider_key_pool_bundle(self, session, category: str, provider: str) -> Dict[str, Any]:
        rows = session.query(SystemAPISetting).filter(
            SystemAPISetting.category == category,
            self._provider_ci_filter(provider),
        ).order_by(SystemAPISetting.id.desc()).all()

        merged_keys: List[str] = []
        seen = set()
        selected_strategy = "random"
        selected_weights: List[float] = []

        for row in rows:
            cfg = self._safe_json_dict(getattr(row, "config", None))
            row_keys = self._normalize_api_keys(cfg.get("provider_api_keys"))
            for key in row_keys:
                if key in seen:
                    continue
                seen.add(key)
                merged_keys.append(key)

            if selected_strategy == "random":
                candidate_strategy = str(cfg.get("provider_api_key_strategy") or "").strip().lower()
                if candidate_strategy in {"random", "round_robin", "weighted"}:
                    selected_strategy = candidate_strategy

            if not selected_weights:
                raw_weights = cfg.get("provider_api_key_weights")
                if isinstance(raw_weights, list) and raw_weights:
                    normalized_weights: List[float] = []
                    for item in raw_weights:
                        try:
                            val = float(item)
                        except Exception:
                            val = 1.0
                        normalized_weights.append(val if val > 0 else 1.0)
                    selected_weights = normalized_weights

        return {
            "provider_api_keys": merged_keys,
            "provider_api_key_strategy": selected_strategy,
            "provider_api_key_weights": selected_weights,
        }

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
        q = session.query(
            APISetting.id,
            cast(APISetting.config, String).label("config_raw"),
        ).filter(APISetting.user_id == user_id)
        if category:
            q = q.filter(APISetting.category == category)

        bad_ids: List[int] = []
        for row in q.all():
            raw = getattr(row, "config_raw", None)
            if isinstance(raw, str) and raw.strip() and not self._is_json_object_value(raw):
                bad_ids.append(row.id)

        if bad_ids:
            logger.warning("Repair invalid api_settings.config rows in media service | user_id=%s category=%s ids=%s", user_id, category, bad_ids)
            session.query(APISetting).filter(APISetting.id.in_(bad_ids)).update(
                {APISetting.config: {}},
                synchronize_session=False,
            )
            session.commit()

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

    def _system_setting_query(self, session, provider: str, category: str = None):
        query = session.query(SystemAPISetting).filter(
            self._provider_ci_filter(provider),
        )
        if category:
            query = query.filter(SystemAPISetting.category == category)
        return query

    def _setting_to_config(self, setting: Any, provider: str, defaults: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        return {
            "api_key": setting.api_key,
            "base_url": setting.base_url or defaults.get(provider, {}).get("base_url"),
            "model": setting.model or defaults.get(provider, {}).get("model"),
            "config": setting.config or {},
        }

    def _get_active_user_setting(self, session, user_id: int, category: str) -> Optional[APISetting]:
        rows = session.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.category == category,
            APISetting.is_active == True,
        ).order_by(APISetting.id.desc()).all()

        if len(rows) > 1:
            logger.warning(
                "Multiple active api settings found | user_id=%s category=%s active_ids=%s",
                user_id,
                category,
                [r.id for r in rows],
            )

        def _score(item: APISetting):
            normalized_provider = self._normalize_provider_name(getattr(item, "provider", None), category)
            provider_supported = 1 if self._is_supported_provider(category, normalized_provider) else 0
            has_model = 1 if str(getattr(item, "model", "") or "").strip() else 0
            cfg = self._safe_json_dict(getattr(item, "config", None))
            selection_source = str((cfg or {}).get("selection_source") or "").strip().lower()
            is_system_selected = 1 if selection_source == "system" else 0
            return (provider_supported, has_model, is_system_selected, int(getattr(item, "id", 0) or 0))

        best_active = max(rows, key=_score) if rows else None

        def _is_viable(item: Optional[APISetting]) -> bool:
            if not item:
                return False
            normalized_provider = self._normalize_provider_name(getattr(item, "provider", None), category)
            if not self._is_supported_provider(category, normalized_provider):
                return False
            return bool(str(getattr(item, "model", "") or "").strip())

        if _is_viable(best_active):
            return best_active

        # Active row missing model/unsupported provider: promote best viable setting in this category.
        all_rows = session.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.category == category,
        ).order_by(APISetting.id.desc()).all()
        viable_rows = [r for r in all_rows if _is_viable(r)]
        if not viable_rows:
            return best_active

        promoted = max(viable_rows, key=_score)
        for row in all_rows:
            row.is_active = bool(row.id == promoted.id)
        session.commit()
        logger.warning(
            "Auto-heal active api setting in media service | user_id=%s category=%s old_active_id=%s promoted_id=%s",
            user_id,
            category,
            getattr(best_active, "id", None),
            promoted.id,
        )
        return promoted

    def _normalize_provider_name(self, provider: Optional[str], category: Optional[str] = None) -> str:
        raw = str(provider or "").strip().lower()
        mapping = {
            "grsai-image": "grsai",
            "grsai-video": "grsai",
            "grsai": "grsai",
            "kie-image": "kie",
            "kie-video": "kie",
            "kie": "kie",
            "doubao": "doubao",
            "doubao video": "doubao",
            "stable diffusion": "stability",
            "tencent hunyuan": "tencent",
            "wanxiang": "wanxiang",
            "wanx": "wanxiang",
            "vidu (video)": "vidu",
            "runway": "runway",
            "kling": "kling",
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
        cat = str(category or "").strip().lower()
        if cat == "image":
            return normalized in {"doubao", "grsai", "kie", "tencent", "stability"}
        if cat == "video":
            return normalized in {"doubao", "grsai", "kie", "tencent", "wanxiang", "vidu"}
        return False

    def _pick_system_setting_fallback(self, session, category: str, provider: Optional[str] = None) -> Optional[SystemAPISetting]:
        query = session.query(SystemAPISetting).filter(SystemAPISetting.category == category)
        normalized_provider = self._normalize_provider_name(provider, category) if provider else ""
        if normalized_provider:
            query = query.filter(self._provider_ci_filter(normalized_provider))

        rows = query.order_by(SystemAPISetting.id.desc()).all()
        for row in rows:
            if self._is_deprecated_system_config(getattr(row, "config", None), getattr(row, "deprecated", None)):
                continue
            row_provider = self._normalize_provider_name(getattr(row, "provider", None), category)
            if not self._is_supported_provider(category, row_provider):
                continue
            return row
        return None

    def _is_smart_routing_enabled(self, session, user_id: int) -> bool:
        rows = session.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.category == "Tools",
        ).order_by(APISetting.id.desc()).all()

        if not rows:
            return True

        for row in rows:
            cfg = self._safe_json_dict(row.config)
            if row.provider == self.SMART_ROUTER_PROVIDER and "auto_intelligent_api_calling" in cfg:
                return bool(cfg.get("auto_intelligent_api_calling"))

        for row in rows:
            cfg = self._safe_json_dict(row.config)
            if "auto_intelligent_api_calling" in cfg:
                return bool(cfg.get("auto_intelligent_api_calling"))

        return True

    def _get_system_candidates(self, session, category: str) -> List[Dict[str, Any]]:
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
            "vidu": {"base_url": "https://api.vidu.studio/open/v1/creation/video", "model": "vidu2.0"},
        }

        rows = session.query(SystemAPISetting).filter(
            SystemAPISetting.category == category,
        ).order_by(SystemAPISetting.id.asc()).all()

        candidates: List[Dict[str, Any]] = []
        provider_bundle_cache: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            provider = self._normalize_provider_name(row.provider, category)
            if not provider:
                continue
            if self._is_deprecated_system_config(row.config, getattr(row, "deprecated", None)):
                continue
            cfg = self._safe_json_dict(row.config)

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
            candidates.append({
                "id": row.id,
                "provider": provider,
                "model": row.model,
                "priority": priority,
                "retry_limit": retry_limit,
                "is_multi_ref_default": bool(cfg.get("smart_multi_ref_default")),
                "config": {
                    **self._setting_to_config(row, provider, defaults),
                    "config": merged_config,
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
            if category == "Image":
                if width and height:
                    if not active_config.get("config"):
                        active_config["config"] = {}
                    active_config["config"]["width"] = width
                    active_config["config"]["height"] = height
                normalized_image_size = self._normalize_image_size_value(image_size)
                if normalized_image_size:
                    if not active_config.get("config"):
                        active_config["config"] = {}
                    active_config["config"]["image_size"] = normalized_image_size

                if provider in ["doubao", "ark"]:
                    return await self._handle_doubao_generation("image", prompt, active_config, reference_image_url, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt)
                if provider == "grsai":
                    return await self._handle_grsai_generation("image", prompt, active_config, reference_image_url, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt, image_size=normalized_image_size)
                if provider == "kie":
                    return await self._handle_kie_generation(
                        "image",
                        prompt,
                        active_config,
                        reference_image_url,
                        aspect_ratio=aspect_ratio,
                        negative_prompt=negative_prompt,
                        image_size=normalized_image_size,
                    )
                if provider == "tencent":
                    return await self._handle_tencent_generation("image", prompt, active_config, reference_image_url, negative_prompt=negative_prompt)
                if provider in ["stability", "stable diffusion"]:
                    return await self._handle_stability_generation("image", prompt, active_config, reference_image_url, negative_prompt=negative_prompt)

                print(f"Unsupported Image provider: {provider}")
                return {
                    "error": f"Unsupported image provider: {provider}",
                    "submit_failed": True,
                    "details": {
                        "provider": provider,
                        "model": active_config.get("model", "default"),
                        "category": "Image",
                    },
                }

            if category == "Video":
                if provider in ["doubao", "ark"]:
                    return await self._handle_doubao_generation("video", prompt, active_config, reference_image_url, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt)
                if provider == "grsai":
                    return await self._handle_grsai_generation("video", prompt, active_config, reference_image_url, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt)
                if provider == "kie":
                    return await self._handle_kie_generation(
                        "video",
                        prompt,
                        active_config,
                        reference_image_url,
                        last_frame_url=last_frame_url,
                        duration=duration,
                        aspect_ratio=aspect_ratio,
                        negative_prompt=negative_prompt,
                    )
                if provider == "tencent":
                    return await self._handle_tencent_generation("video", prompt, active_config, reference_image_url, duration=duration, negative_prompt=negative_prompt)
                if provider in ["wanxiang", "wanx"]:
                    return await self._handle_wanxiang_generation("video", prompt, active_config, reference_image_url, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt)
                if provider == "vidu":
                    return await self._handle_vidu_generation("video", prompt, active_config, reference_image_url, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio, keyframes=keyframes, negative_prompt=negative_prompt)

                print(f"Unsupported Video provider: {provider}")
                return {
                    "error": f"Unsupported video provider: {provider}",
                    "submit_failed": True,
                    "details": {
                        "provider": provider,
                        "model": active_config.get("model", "default"),
                        "duration": duration,
                        "category": "Video",
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
        requested_model: Optional[str] = None,
        explicit_selection: bool = False,
        allow_priority_fallback_when_explicit: bool = False,
        fallback_candidate_limit: int = 1,
    ) -> Dict[str, Any]:
        with SessionLocal() as session:
            smart_enabled = self._is_smart_routing_enabled(session, user_id)
            candidates = self._get_system_candidates(session, category)

        if allow_priority_fallback_when_explicit:
            smart_enabled = True

        if explicit_selection:
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
        baseline_config = dict(api_config or {})
        if requested_model:
            baseline_config["model"] = requested_model

        fallback_candidates = sorted(
            [
                c for c in candidates
                if c.get("provider") and not (
                    c.get("provider") == effective_provider
                    and str(c.get("model") or "") == str(baseline_config.get("model") or "")
                )
            ],
            key=lambda x: (x.get("priority", 100), x.get("id", 0)),
        )
        if fallback_candidate_limit and fallback_candidate_limit > 0:
            fallback_candidates = fallback_candidates[: int(fallback_candidate_limit)]

        retry_limit = 1
        for c in candidates:
            if c.get("provider") == effective_provider and c.get("retry_limit") is not None:
                retry_limit = max(1, int(c.get("retry_limit")))
                break

        multi_ref_count = len(reference_image_url) if isinstance(reference_image_url, list) else 0
        attempt_items: List[Dict[str, Any]] = []

        if smart_enabled and category == "Image" and multi_ref_count > 4:
            multi_ref_target = sorted(
                [c for c in candidates if c.get("is_multi_ref_default")],
                key=lambda x: (x.get("priority", 100), x.get("id", 0)),
            )
            if multi_ref_target:
                first = multi_ref_target[0]
                attempt_items.append({
                    "provider": first.get("provider"),
                    "config": dict(first.get("config") or {}),
                    "tag": "multi_ref_default",
                })

        for _ in range(retry_limit):
            attempt_items.append({
                "provider": effective_provider,
                "config": dict(baseline_config),
                "tag": "active_retry",
            })

        if smart_enabled:
            for c in fallback_candidates:
                attempt_items.append({
                    "provider": c.get("provider"),
                    "config": dict(c.get("config") or {}),
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

        final_error: Dict[str, Any] = {"error": "Generation failed"}
        fallback_unlocked = False

        for index, attempt in enumerate(deduped_attempts, start=1):
            if attempt.get("tag") == "active_retry" and fallback_unlocked:
                logger.info(
                    "Smart routing skip active retry | category=%s user_id=%s attempt=%s/%s reason=fallback_unlocked",
                    category,
                    user_id,
                    index,
                    len(deduped_attempts),
                )
                continue

            if attempt.get("tag") == "priority_fallback" and not fallback_unlocked:
                logger.info(
                    "Smart routing skip fallback | category=%s user_id=%s attempt=%s/%s reason=no_explicit_submit_failure",
                    category,
                    user_id,
                    index,
                    len(deduped_attempts),
                )
                continue

            selected_provider = self._normalize_provider_name(attempt.get("provider"), category)
            selected_config = dict(attempt.get("config") or {})
            if not selected_provider:
                continue

            logger.info(
                "Smart routing attempt | category=%s user_id=%s attempt=%s/%s provider=%s model=%s tag=%s smart_enabled=%s fallback_triggered=%s",
                category,
                user_id,
                index,
                len(deduped_attempts),
                selected_provider,
                selected_config.get("model"),
                attempt.get("tag"),
                smart_enabled,
                fallback_unlocked,
            )

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
            )

            if result and not result.get("error"):
                metadata = result.get("metadata") or {}
                fallback_used = bool(fallback_unlocked) or attempt.get("tag") == "priority_fallback"
                logger.info(
                    "Smart routing success | category=%s user_id=%s attempt=%s/%s provider=%s model=%s tag=%s fallback_used=%s initial_provider=%s initial_model=%s",
                    category,
                    user_id,
                    index,
                    len(deduped_attempts),
                    selected_provider,
                    selected_config.get("model"),
                    attempt.get("tag"),
                    fallback_used,
                    effective_provider,
                    baseline_config.get("model"),
                )
                metadata["smart_routing"] = {
                    "enabled": smart_enabled,
                    "attempt": index,
                    "attempt_tag": attempt.get("tag"),
                    "provider": selected_provider,
                }
                result["metadata"] = metadata
                return result

            final_error = result or {"error": "Generation failed"}
            if isinstance(final_error, dict):
                runtime_model = final_error.get("runtime_model")
                final_error["_attempt_provider"] = selected_provider
                final_error["_attempt_model"] = runtime_model or selected_config.get("model")
                final_error["_attempt_tag"] = attempt.get("tag")
            has_error = bool((result or {}).get("error"))
            has_output = bool((result or {}).get("url")) or bool((result or {}).get("video_url"))
            submit_failed = bool((result or {}).get("submit_failed"))
            fallback_reason = ""
            fallback_triggered_now = submit_failed
            if has_error or not has_output:
                fallback_triggered_now = True

            if fallback_triggered_now:
                if submit_failed:
                    fallback_reason = "submit_failed"
                elif has_error:
                    fallback_reason = "generation_failed"
                elif not has_output:
                    fallback_reason = "no_output"
                else:
                    fallback_reason = "unknown"

            error_detail = str((result or {}).get("error") or "").strip() if isinstance(result, dict) else ""
            error_details_extra = ""
            if isinstance(result, dict):
                raw_details = result.get("details")
                if raw_details is not None:
                    try:
                        if isinstance(raw_details, (dict, list)):
                            error_details_extra = json.dumps(raw_details, ensure_ascii=False)[:1000]
                        else:
                            error_details_extra = str(raw_details)[:1000]
                    except Exception:
                        error_details_extra = str(raw_details)[:1000]
            next_fallback_provider = ""
            next_fallback_model = ""
            if fallback_triggered_now:
                for next_attempt in deduped_attempts[index:]:
                    if next_attempt.get("tag") != "priority_fallback":
                        continue
                    candidate_provider = self._normalize_provider_name(next_attempt.get("provider"), category)
                    if not candidate_provider:
                        continue
                    next_fallback_provider = candidate_provider
                    next_fallback_model = str((next_attempt.get("config") or {}).get("model") or "").strip()
                    break

            logger.warning(
                "Smart routing attempt failed | category=%s user_id=%s attempt=%s/%s provider=%s model=%s tag=%s reason=%s submit_failed=%s has_error=%s has_output=%s next_fallback_provider=%s next_fallback_model=%s error=%s",
                category,
                user_id,
                index,
                len(deduped_attempts),
                selected_provider,
                selected_config.get("model"),
                attempt.get("tag"),
                fallback_reason or "non_fallback",
                submit_failed,
                has_error,
                has_output,
                next_fallback_provider,
                next_fallback_model,
                error_detail,
            )
            if error_details_extra:
                logger.warning(
                    "Smart routing attempt failed details | category=%s user_id=%s attempt=%s/%s provider=%s model=%s details=%s",
                    category,
                    user_id,
                    index,
                    len(deduped_attempts),
                    selected_provider,
                    selected_config.get("model"),
                    error_details_extra,
                )

            if fallback_triggered_now:
                if not fallback_unlocked:
                    logger.info(
                        "Smart routing fallback triggered | category=%s user_id=%s trigger_attempt=%s provider=%s reason=%s",
                        category,
                        user_id,
                        index,
                        selected_provider,
                        fallback_reason,
                    )
                fallback_unlocked = True
                continue

            logger.info(
                "Smart routing stop without fallback | category=%s user_id=%s attempt=%s/%s provider=%s reason=non_submit_failure",
                category,
                user_id,
                index,
                len(deduped_attempts),
                selected_provider,
            )
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

                user_setting = self._get_active_user_setting(session, user_id, resolved_category)
                requested_provider = self._normalize_provider_name(str(provider or "").strip(), resolved_category)
                requested_model_value = str(requested_model or "").strip()

                if strict_provider and (not requested_provider or not self._is_supported_provider(resolved_category, requested_provider)):
                    logger.warning(
                        "Explicit provider unsupported/missing in media service | user_id=%s category=%s provider=%s",
                        user_id,
                        resolved_category,
                        provider,
                    )
                    return {}

                if not user_setting and not (strict_provider and requested_provider):
                    logger.warning(
                        "No active user api setting found in media service | user_id=%s category=%s",
                        user_id,
                        resolved_category,
                    )
                    return {}

                if strict_provider and requested_provider:
                    target_provider = requested_provider
                    target_model = requested_model_value
                else:
                    target_provider = self._normalize_provider_name(str((user_setting.provider if user_setting else "") or "").strip(), resolved_category)
                    target_model = requested_model_value or str((user_setting.model if user_setting else "") or "").strip()

                provider_locked = bool(target_provider)

                if not target_provider or not self._is_supported_provider(resolved_category, target_provider):
                    logger.warning(
                        "Active user setting provider unsupported/missing in media service | user_id=%s category=%s setting_id=%s provider=%s",
                        user_id,
                        resolved_category,
                        (user_setting.id if user_setting else None),
                        (user_setting.provider if user_setting else None),
                    )
                    if strict_provider and requested_provider:
                        return {}
                    fallback_any = self._pick_system_setting_fallback(session, resolved_category, None)
                    if fallback_any:
                        target_provider = self._normalize_provider_name(fallback_any.provider, resolved_category)
                        target_model = str(fallback_any.model or "").strip()

                if target_provider and not target_model:
                    logger.warning(
                        "Active user setting missing model in media service | user_id=%s category=%s setting_id=%s provider=%s",
                        user_id,
                        resolved_category,
                        (user_setting.id if user_setting else None),
                        target_provider,
                    )
                    fallback_same_provider = self._pick_system_setting_fallback(session, resolved_category, target_provider)
                    if fallback_same_provider:
                        target_model = str(fallback_same_provider.model or "").strip()

                if not target_provider:
                    if strict_provider and requested_provider:
                        logger.warning(
                            "Explicit provider has no resolvable provider in media service | user_id=%s category=%s provider=%s requested_model=%s",
                            user_id,
                            resolved_category,
                            requested_provider,
                            requested_model_value,
                        )
                        return {}
                    fallback_any = self._pick_system_setting_fallback(session, resolved_category, None)
                    if fallback_any:
                        target_provider = self._normalize_provider_name(fallback_any.provider, resolved_category)
                        target_model = str(fallback_any.model or "").strip()

                if target_provider and not target_model and strict_provider and requested_provider:
                    logger.warning(
                        "Explicit provider has no resolvable model in media service | user_id=%s category=%s provider=%s requested_model=%s",
                        user_id,
                        resolved_category,
                        requested_provider,
                        requested_model_value,
                    )
                    return {}

                if not target_provider or not target_model:
                    logger.warning(
                        "Unable to resolve provider/model in media service | user_id=%s category=%s setting_id=%s provider=%s model=%s",
                        user_id,
                        resolved_category,
                        (user_setting.id if user_setting else None),
                        (user_setting.provider if user_setting else None),
                        (user_setting.model if user_setting else None),
                    )
                    return {}

                system_setting = None
                resolved_source = f"system_by_user_provider_model:{target_provider}/{target_model}"

                if target_provider and target_model:
                    system_setting = session.query(SystemAPISetting).filter(
                        SystemAPISetting.category == resolved_category,
                        self._provider_ci_filter(target_provider),
                        SystemAPISetting.model == target_model,
                    ).order_by(SystemAPISetting.id.desc()).first()

                if not system_setting:
                    system_setting = self._pick_system_setting_fallback(session, resolved_category, target_provider)
                    if system_setting:
                        resolved_source = f"system_by_provider_fallback:{target_provider}/{system_setting.model}"

                if not system_setting:
                    if strict_provider and requested_provider:
                        logger.warning(
                            "Explicit provider has no available system setting in media service | user_id=%s category=%s provider=%s model=%s",
                            user_id,
                            resolved_category,
                            target_provider,
                            target_model,
                        )
                        return {}
                    if provider_locked:
                        logger.warning(
                            "Provider-locked selection has no available system setting in media service | user_id=%s category=%s provider=%s model=%s",
                            user_id,
                            resolved_category,
                            target_provider,
                            target_model,
                        )
                        return {}
                    system_setting = self._pick_system_setting_fallback(session, resolved_category, None)
                    if system_setting:
                        resolved_source = f"system_by_category_fallback:{system_setting.provider}/{system_setting.model}"

                if system_setting:
                    resolved_provider = self._normalize_provider_name(system_setting.provider, resolved_category) or target_provider
                    provider_key_pool_bundle = self._collect_provider_key_pool_bundle(
                        session,
                        resolved_category,
                        resolved_provider,
                    )
                    merged_runtime_config = {
                        **(system_setting.config or {}),
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

                    if self._is_deprecated_system_config(system_setting.config, getattr(system_setting, "deprecated", None)):
                        logger.warning(
                            "Blocked deprecated system api setting in media service | user_id=%s category=%s provider=%s model=%s setting_id=%s",
                            user_id,
                            resolved_category,
                            target_provider,
                            target_model,
                            system_setting.id,
                        )
                        return {
                            "provider": system_setting.provider,
                            "model": system_setting.model,
                            "__blocked": True,
                            "__blocked_reason": "该 System API 配置已弃用，禁止发起 API 调用。",
                        }
                    logger.info(
                        "Resolved media API config | user_id=%s category=%s provider=%s source=%s selection_source=system_only setting_id=%s model=%s endpoint=%s",
                        user_id,
                        resolved_category,
                        target_provider,
                        resolved_source,
                        system_setting.id,
                        system_setting.model,
                        system_setting.base_url,
                    )
                    return {
                        "provider": system_setting.provider,
                        "api_key": self._pick_runtime_api_key(merged_runtime_config, system_setting.api_key),
                        "base_url": system_setting.base_url or defaults.get(resolved_provider, {}).get("base_url"),
                        "model": system_setting.model or defaults.get(resolved_provider, {}).get("model"),
                        "config": {
                            **(system_setting.config or {}),
                            "__selection_source": "system_only",
                            "__resolved_source": resolved_source,
                            "__resolved_setting_id": system_setting.id,
                        },
                    }
                logger.warning(
                    "No matching system api setting by provider+model in media service | user_id=%s category=%s provider=%s model=%s",
                    user_id,
                    resolved_category,
                    target_provider,
                    target_model,
                )
        except Exception as e:
            print(f"Error fetching settings for {provider}: {e}")

        return {}

    async def generate_image(self, prompt: str, negative_prompt: Optional[str] = None, llm_config: Optional[Dict[str, Any]] = None, reference_image_url: Optional[Union[str, List[str]]] = None, width: int = None, height: int = None, image_size: Optional[str] = None, aspect_ratio: str = None, user_id: int = 1, user_credits: int = 0, filename_base: Optional[str] = None, asset_type: Optional[str] = None):
        explicit_provider_selected = bool((llm_config or {}).get("provider"))
        provider = None
        if llm_config and "provider" in llm_config and llm_config["provider"]:
            provider = self._normalize_provider_name(llm_config["provider"], "Image")

        if not provider:
            try:
                with SessionLocal() as session:
                    self._repair_invalid_user_config_rows(session, user_id, category="Image")
                    active_setting = self._get_active_user_setting(session, user_id, "Image")
                    if active_setting and active_setting.provider:
                        provider = self._normalize_provider_name(active_setting.provider, "Image")
            except Exception as e:
                print(f"Error finding active provider: {e}")

        if not provider:
            provider = "grsai"

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

        resolved_provider = self._normalize_provider_name((api_config or {}).get("provider"), "Image") if api_config else None
        if resolved_provider:
            provider = resolved_provider

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

        print(f"[MediaService] Generating Image. Provider: {provider}, Refs Type: {type(reference_image_url)}, Refs: {reference_image_url}, W: {width}, H: {height}, image_size: {image_size}, AR: {aspect_ratio}")

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
            explicit_selection=bool((llm_config or {}).get("provider") or (llm_config or {}).get("model")),
            allow_priority_fallback_when_explicit=str(asset_type or "").strip().lower() in {"subject", "entity", "character", "prop", "environment"},
            fallback_candidate_limit=1,
        )

        # Download 
        if result and "url" in result and result["url"]:
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

    async def generate_video(self, prompt: str, negative_prompt: Optional[str] = None, llm_config: Optional[Dict[str, Any]] = None, reference_image_url: Optional[Union[str, List[str]]] = None, last_frame_url: Optional[str] = None, duration: int = 5, aspect_ratio: Optional[str] = None, keyframes: Optional[List[str]] = None, provider_options: Optional[Dict[str, Any]] = None, user_id: int = 1, user_credits: int = 0, filename_base: Optional[str] = None):
        explicit_provider_selected = bool((llm_config or {}).get("provider"))
        provider = None
        if llm_config and "provider" in llm_config and llm_config["provider"]:
            provider = self._normalize_provider_name(llm_config["provider"], "Video")

        if not provider:
            try:
                with SessionLocal() as session:
                    self._repair_invalid_user_config_rows(session, user_id, category="Video")
                    active_setting = self._get_active_user_setting(session, user_id, "Video")
                    if active_setting and active_setting.provider:
                        provider = self._normalize_provider_name(active_setting.provider, "Video")
            except Exception as e:
                print(f"Error finding active provider: {e}")

        if not provider:
            provider = "grsai"

        api_config = self.get_api_config(
            provider,
            user_id,
            category="Video",
            requested_model=(llm_config or {}).get("model"),
            user_credits=user_credits,
            strict_provider=explicit_provider_selected,
        )

        if api_config and api_config.get("__blocked"):
            return {
                "error": self._vendor_failed_message(self._normalize_provider_name((api_config or {}).get("provider"), "Video") or provider, api_config.get("__blocked_reason") or "该系统配置已弃用"),
                "submit_failed": True,
            }

        resolved_provider = self._normalize_provider_name((api_config or {}).get("provider"), "Video") if api_config else None
        if resolved_provider:
            provider = resolved_provider

        if api_config is not None and isinstance(provider_options, dict) and provider_options:
            merged_config = dict((api_config.get("config") or {}))
            merged_config.update(provider_options)
            api_config["config"] = merged_config

        resolved_source = str((((api_config or {}).get("config") or {}).get("__resolved_source") or "")).strip().lower()
        provider_locked_by_active_setting = bool(resolved_provider) and ("system_by_user_provider_model:" in resolved_source)
        explicit_selection_for_video = bool((llm_config or {}).get("provider") or (llm_config or {}).get("model"))

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

        if provider_locked_by_active_setting and not bool((llm_config or {}).get("provider") or (llm_config or {}).get("model")):
            logger.info(
                "Generate video provider lock enabled | user_id=%s provider=%s reason=active_setting_no_explicit_override fallback=enabled_on_failure",
                user_id,
                provider,
            )

        print(f"[MediaService] Generating Video. Provider: {provider}, Model: {(api_config or {}).get('model') or (llm_config or {}).get('model')}, Refs: {reference_image_url}, LastFrame: {last_frame_url}, Ratio: {aspect_ratio}, Keyframes: {len(keyframes) if keyframes else 0}")

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
            requested_model=(llm_config or {}).get("model"),
            explicit_selection=explicit_selection_for_video,
        )

        # Download 
        if result and "url" in result and result["url"]:
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
    
    # --- Provider Implementations ---
    
    async def _handle_doubao_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None):
        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        api_key = config.get("api_key")
        if not api_key: return {"error": "No API Key"}
        model = config.get("model")
        tool_conf = config.get("config", {}) or {}
        
        # Base metadata
        base_metadata = {"provider": "doubao", "model": model, "prompt": prompt}
        
        # Image Generation
        if gen_type == "image":
            # Multi-Reference handling (if ref_image provided)
            if ref_image:
                print(f"DEBUG: Doubao Multi-Reference Gen refs: {ref_image}")
                raw_endpoint = tool_conf.get("endpoint") or "https://ark.cn-beijing.volces.com/api/v3"
                endpoint = raw_endpoint.strip()
                
                ref_list = ref_image if isinstance(ref_image, list) else [ref_image]
                ref_list = [r for r in ref_list if r]
                
                resolved_refs = self._resolve_ref_list_for_api(ref_list, force_data_uri_for_local=True)
                    
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
                    return await self._common_requests_post(url, payload, api_key, "doubao_image_multiref", extra_metadata=base_metadata)
            
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
            
            return await self._common_requests_post(url, payload, api_key, "doubao_image", extra_metadata=base_metadata)

        # Video Generation
        elif gen_type == "video":
            raw_endpoint = tool_conf.get("endpoint") or "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
            endpoint = self._normalize_doubao_video_tasks_endpoint(raw_endpoint)
            
            # Auto-correct model if user passed an Image model for a Video task
            if model and "seedream" in model:
                 model = "doubao-seedance-1-5-pro-251215"
            
            if last_frame_url and "1-0-pro-fast" in (model or ""):
                model = "doubao-seedance-1-5-pro-251215"
            
            content_payload = [{"type": "text", "text": prompt}]
            
            # Handle Refs (List vs Single)
            start_img_url = ref_image
            if isinstance(ref_image, list):
                # Pick the first one as Start Frame
                start_img_url = ref_image[0] if ref_image else None
            
            if start_img_url and last_frame_url:
                # Start + End Frame Mode (Explicit Roles Required)
                start_ref = self._resolve_ref_for_api(start_img_url, force_data_uri_for_local=True)
                end_ref = self._resolve_ref_for_api(last_frame_url, force_data_uri_for_local=True)

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
                start_ref = self._resolve_ref_for_api(start_img_url, force_data_uri_for_local=True)
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
                end_ref = self._resolve_ref_for_api(last_frame_url, force_data_uri_for_local=True)
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

            # Ensure duration is within valid range. 
            # Note: The default 5s often causes InvalidParameter for Doubao (Seedance).
            # "Switch back to config, unless invalid" -> Validate and fallback to -1 (Auto).
            final_duration = duration
            
            # Config override (User Settings)
            if tool_conf.get("duration"):
                 final_duration = tool_conf.get("duration")

            try:
                 d_int = int(final_duration)
                 # Filter out <=0 and the known-bad default 5 (unless 5 works for some models, but here it failed)
                 if d_int <= 0 or d_int == 5: 
                      final_duration = -1
                 else:
                      final_duration = d_int
            except:
                 final_duration = -1

            # Map aspect ratio for Doubao
            final_ratio = aspect_ratio if aspect_ratio else "16:9" # Default to 16:9 if not provided for T2V
            if final_ratio == "2.35:1": final_ratio = "21:9"
            if final_ratio == "adaptive": final_ratio = "16:9" # Handle legacy "adaptive" if passed

            payload = {
                "model": model or "doubao-seedance-1-5-pro-251215",
                "content": content_payload,
                "duration": final_duration,
                "logo_info": {"add_logo": False},
                "watermark": False
            }

            # Apply Draft Mode (Sample Mode) if configured and supported (1.5 Pro only)
            if model and "1-5-pro" in model:
                 # Default to False (Normal Mode) unless explicitly enabled
                 payload["draft"] = bool(tool_conf.get("draft", False))
            
            # For Doubao (Ark), if image is provided, ratio should typically be omitted 
            # to respect image dimensions (or use 'size'/'resolution' params if available, but ratio causes 400).
            # Only add ratio for Text-to-Video (no start/end images)
            if not start_img_url and not last_frame_url:
                 payload["ratio"] = final_ratio


            # Only enable generate_audio for 1.5 Pro models which support it
            if payload["model"] and "1-5-pro" in payload["model"]:
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
        
        # Check for Multi-Frame Mode (Keyframes present)
        is_multiframe = keyframes and len(keyframes) >= 1
        
        # If multi-frame, we use different payload structure
        if is_multiframe:
            print("[Vidu] Using Multi-Frame (Keyframes) Mode")
            # Required: model, start_image, image_settings
            # Typically model is viduq2-turbo or viduq2-pro for this mode (as per user snippet)
            # Default to viduq2-turbo if current model is not appropriate? 
            # Or just use configured model and hope user selected correct one.
            # User snippet: Optional values: viduq2-turbo, viduq2-pro
            
            payload = {
                "model": model, 
                "prompt": prompt[:2000] if prompt else ""
            }
            
            # 1. Start Image
            start_img_src = None
            if ref_image:
                 refs = ref_image if isinstance(ref_image, list) else [ref_image]
                 if refs: start_img_src = refs[0]
            
            if not start_img_src:
                 return {"error": "Vidu Multi-Frame requires a Start Image (Reference Image)"}
                 
            start_ref = self._resolve_ref_for_api(start_img_src, force_data_uri_for_local=True)
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
                 resolved_kf = self._resolve_ref_for_api(kf, force_data_uri_for_local=True)
                 if resolved_kf:
                     # Attempt generic structure. 
                     # If backend rejects, we will know.
                     # Vidu Character Consistency uses "characters".
                     # This "image_settings" is likely for timeline control.
                     settings_arr.append({"image": resolved_kf})
            
            # Validation: Min 2 keyframes
            if len(settings_arr) < 2:
                  print("[Vidu] Warning: Multi-frame expects min 2 keyframes. Current: " + str(len(settings_arr)))
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
                    start_ref = self._resolve_ref_for_api(refs[0], force_data_uri_for_local=True)
                    if start_ref: images.append(start_ref)
            
            if last_frame_url:
                end_ref = self._resolve_ref_for_api(last_frame_url, force_data_uri_for_local=True)
                if end_ref:
                     if not images: images.append(end_ref) # Use as start if no start
                     else: images.append(end_ref) # Use as end
            
            if images: payload["images"] = images

        # Shared: Duration & Resolution
        if duration:
            dur_int = int(duration)
            if dur_int < 1: dur_int = 4 
            if model == "vidu2.0":
                 payload["duration"] = 8 if dur_int >= 6 else 4
                 if payload["duration"] == 8: payload["resolution"] = "720p" 
            elif "viduq1" in model:
                 payload["duration"] = 5
                 payload["resolution"] = "1080p"
            else:
                 payload["duration"] = min(dur_int, 8)

        if "resolution" not in payload: payload["resolution"] = "720p" 

        # Config overrides
        if config.get("config"):
             cf = config.get("config")
             if cf.get("seed"): payload["seed"] = int(cf.get("seed"))
             if cf.get("is_rec") is not None: payload["is_rec"] = bool(cf.get("is_rec"))
             if cf.get("resolution"): payload["resolution"] = cf.get("resolution")

        print(f"[Vidu] Job Submission: Model={model}, Dur={payload.get('duration')}, Res={payload.get('resolution')}, MultiFrame={is_multiframe}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {api_key}"
        }
        
        try:
             # Submit
             resp = requests.post(endpoint, json=payload, headers=headers, timeout=60)
             if resp.status_code not in [200, 201]:
                  return {"error": f"Vidu Error {resp.status_code}", "details": resp.text}
             
             data = resp.json()
             task_id = data.get("id")
             if not task_id: return {"error": "No Task ID returned", "details": resp.text}
             
             # Poll
             poll_url = f"{endpoint}/{task_id}"
             for _ in range(60):
                  await asyncio.sleep(3)
                  p_resp = requests.get(poll_url, headers=headers, timeout=30)
                  if p_resp.status_code == 200:
                       p_data = p_resp.json()
                       status = p_data.get("state") or p_data.get("status") 
                       
                       if status == "success" or status == "SUCCESS":
                            vid_url = p_data.get("valid_video_url") or p_data.get("video_url") or p_data.get("url")
                            if vid_url:
                                 return {"url": vid_url, "metadata": {"raw": p_data, "provider": "vidu"}}
                       elif status == "failed" or status == "FAILED":
                            return {"error": "Vidu Generation Failed", "details": str(p_data)}
             
             return {"error": "Timeout polling Vidu"}

        except Exception as e:
             traceback.print_exc()
             return {"error": f"Vidu Exception: {str(e)}"}
             
    async def _handle_grsai_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        api_key = config.get("api_key")
        model = config.get("model") or "unknown_model"
        trace_id = f"grsai-{uuid.uuid4().hex[:10]}"
        print(f"[Grsai] Starting Generation. Type={gen_type}, Model={model}, PromptLen={len(prompt) if prompt else 0}")
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
            if not raw_endpoint and is_banana:
                endpoint = f"{base_url}/v1/draw/nano-banana"
            
            final_model = model or "sora-image"
            payload = {"model": final_model, "prompt": prompt, "webHook": "-1", "shutProgress": False}
            base_metadata = {"provider": "grsai", "model": final_model, "prompt": prompt}

            normalized_ar = self._normalize_aspect_ratio_value(aspect_ratio)
            if normalized_ar:
                payload["aspectRatio"] = normalized_ar
                base_metadata["submit_aspect_ratio"] = normalized_ar

            if ref_image:
                ref_list = [ref_image] if isinstance(ref_image, str) else ref_image
                resolved_refs = []
                print(f"[Grsai] Processing {len(ref_list)} reference images...")
                for i, r in enumerate(ref_list):
                    resolved = self._resolve_ref_for_api(r, force_data_uri_for_local=True)
                    if resolved:
                        resolved_refs.append(resolved)
                    else:
                        print(f"[Grsai] Error: Failed to resolve ref image {i} ({r}). Dropping.")
                
                print(f"[Grsai] Final Refs Count: {len(resolved_refs)}")
                payload["urls"] = resolved_refs
            
            # Resolution Logic
            w = tool_conf.get("width")
            h = tool_conf.get("height")
            
            if w and h:
                res_str = f"{w}x{h}"
            elif aspect_ratio:
                 # Minimal mapping for Grsai (Assuming it supports standard sizes or 1024 based aspect)
                 if aspect_ratio == "16:9": res_str = "1280x720"
                 elif aspect_ratio == "9:16": res_str = "720x1280"
                 elif aspect_ratio == "4:3": res_str = "1024x768"
                 elif aspect_ratio == "3:4": res_str = "768x1024"
                 elif aspect_ratio == "21:9": res_str = "1536x640" 
                 else: res_str = "1024x1024"
            else:
                 res_str = "1024x1024"

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
            log_payload = payload.copy()
            if "urls" in log_payload:
                 log_payload["urls"] = [f"<Base64 Data (len={len(u)})>" for u in log_payload["urls"]]

            result_base = endpoint.split("/v1/")[0] if "/v1/" in endpoint else base_url
            result_url = f"{result_base}/v1/draw/result"

            print(f"[Grsai] Submitting Payload: {json.dumps(log_payload, ensure_ascii=False)}")
            logger.info(
                "[GrsaiTrace][%s] image submit prepared | endpoint=%s result_url=%s has_refs=%s refs_count=%s payload_keys=%s",
                trace_id,
                endpoint,
                result_url,
                bool(payload.get("urls")),
                len(payload.get("urls") or []),
                sorted(list(payload.keys())),
            )
            return await self._submit_and_poll_grsai(endpoint, payload, api_key, result_url, extra_metadata=base_metadata, trace_id=trace_id)

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
            print(f"[Grsai] Computed Result Poll URL: {result_url}")

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
                payload["webHook"] = "-1"
                # API requires integer for duration
                payload["duration"] = int(duration) if duration else 5
                if aspect_ratio:
                    # Default map for common ratios if API expects WxH
                    map_size = {
                        "16:9": "1280x720", 
                        "9:16": "720x1280", 
                        "1:1": "1024x1024", 
                        "4:3": "1024x768",
                        "2.35:1": "1920x816"
                    }
                    if aspect_ratio in map_size:
                        payload["size"] = map_size[aspect_ratio]
                    else:
                        payload["aspect_ratio"] = aspect_ratio

            base_metadata = {"provider": "grsai", "model": final_model, "prompt": prompt}
            
            # Grsai expects URLs or Base64
            # is_veo check moved up
            
            if ref_image:
                if is_veo:
                    # Explicitly process for Veo requirements
                    payload["firstFrameUrl"] = self._process_veo_image(ref_image, aspect_ratio or "16:9")
                else:
                    val = self._resolve_ref_for_api(ref_image, force_data_uri_for_local=True)
                    if val: payload["url"] = val
            elif is_veo:
                # Veo: firstFrameUrl is Optional. 
                # But if we have lastFrameUrl, we MUST have firstFrameUrl.
                # If we have neither, we can omit both.
                # Logic: Only force black frame if we have lastFrameUrl but no firstFrameUrl.
                if last_frame_url:
                     print("[Grsai] Auto-generating Black Start Frame for Veo (Required by Last Frame)...")
                     try:
                        # Generate black image
                        img = Image.new('RGB', (1024, 576), (0, 0, 0))
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
                        payload["firstFrameUrl"] = f"data:image/png;base64,{b64_str}"
                     except Exception as e:
                        print(f"[Grsai] Failed to gen black frame: {e}") 
            
            if last_frame_url:
                if is_veo:
                    payload["lastFrameUrl"] = self._process_veo_image(last_frame_url, aspect_ratio or "16:9")
                else:
                    val = self._resolve_ref_for_api(last_frame_url, force_data_uri_for_local=True)
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

                 # Webhook fix: Docs say "-1" for immediate ID return if no callback used
                 payload["webHook"] = "-1" 

            # Debug log (sanitized)
            valid_payload_log = json.dumps(payload, ensure_ascii=False)
            if "urls" in payload and payload["urls"]:
                 # Simple hack to avoid dumping massive base64 in logs if present
                 pass 
            # If payload has direct base64 fields (firstFrameUrl often is one), we truncate for logs
            debug_p = payload.copy()
            for key in ["firstFrameUrl", "lastFrameUrl", "image", "urls"]:
                if key in debug_p and debug_p[key]:
                    if isinstance(debug_p[key], str) and len(debug_p[key]) > 200:
                         debug_p[key] = debug_p[key][:50] + "...<Base64>..."
                    elif isinstance(debug_p[key], list):
                         debug_p[key] = [ (s[:50] + "...<Base64>...") if isinstance(s, str) and len(s) > 200 else s for s in debug_p[key] ]

            print(f"[Grsai] Video Payload: {json.dumps(debug_p, ensure_ascii=False)}")
            if is_veo:
                print(f"[Grsai][Veo] Submit Duration={payload.get('duration')} Model={final_model} Aspect={payload.get('aspectRatio')}")
            logger.info(
                "[GrsaiTrace][%s] video submit prepared | endpoint=%s result_url=%s is_veo=%s payload_keys=%s",
                trace_id,
                endpoint,
                result_url,
                is_veo,
                sorted(list(payload.keys())),
            )
            
            # Double check payload validity before sending
            return await self._submit_and_poll_grsai(endpoint, payload, api_key, result_url, is_video=True, extra_metadata=base_metadata, trace_id=trace_id)
    
    async def _submit_and_poll_grsai_legacy(self, url, payload, api_key, result_url, is_video=False, extra_metadata=None):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        # Increased timeout to 300s
        def _post(): return requests.post(url, json=payload, headers=headers, timeout=300, verify=False)
        
        try:
            resp = await asyncio.to_thread(_post)
            print(f"[Grsai Legacy] API Returned: {resp.text[:1000]}") # DEBUG USER REQUEST
            if resp.status_code != 200: return {"error": f"Submission Failed {resp.status_code}", "details": resp.text}
            
            data = resp.json()
            task_id = data.get("data") # Grsai returns task ID directly in data field usually? or data.data?
            # Adjust based on Grsai spec: usually {code: 200, data: "taskId..."}
            if not task_id: return {"error": "No Task ID"}
            
            # Poll
            for _ in range(60):
                 await asyncio.sleep(3)
                 def _poll(): return requests.post(result_url, json={"id": task_id}, headers=headers, timeout=30, verify=False)
                 p_resp = await asyncio.to_thread(_poll)
                 
                 if p_resp.status_code == 200:
                     p_data = p_resp.json()
                     # Check completion
                     if "data" in p_data and p_data["data"]:
                         final = p_data["data"][0].get("imageUrl" if not is_video else "videoUrl")
                         if final:
                              metadata = {"raw": p_data}
                              if extra_metadata: metadata.update(extra_metadata)
                              return {"url": final, "metadata": metadata}
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
            canonical_request = (http_method + "\n" +
                                    canonical_uri + "\n" +
                                    canonical_querystring + "\n" +
                                    canonical_headers + "\n" +
                                    signed_headers + "\n" +
                                    hashed_payload)
            
            # 2. String to Sign
            algorithm = "TC3-HMAC-SHA256"
            credential_scope = date + "/" + service + "/tc3_request"
            hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
            string_to_sign = (algorithm + "\n" +
                                str(timestamp) + "\n" +
                                credential_scope + "\n" +
                                hashed_canonical)
            
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
                return requests.post(f"https://{host}", data=payload_json, headers=req_headers, timeout=60, verify=False)
            
            return await asyncio.to_thread(_post)

        # -- Step 1: Submit Job --
        submit_action = "SubmitTextToImageJob"
        is_sync = False
        payload = {"Prompt": prompt, "LogoAdd": 0}
        
        # Image-to-Image logic
        if ref_image:
            submit_action = "ImageToImage"
            is_sync = True
            ref_value = self._resolve_ref_for_api(ref_image, force_data_uri_for_local=False)
            if not ref_value:
                print("Failed to load reference image for Tencent I2I")
                return {"error": "Failed to load reference image for Tencent I2I"}
            payload["InputImage"] = ref_value
            payload["RspImgType"] = "url"

        if submit_action == "SubmitTextToImageJob":
            payload["Resolution"] = "1024:768" # Default simplification

        resp = await call_tencent_api(submit_action, payload)
        if resp.status_code != 200: 
            print(f"[MediaService] Tencent Request Failed {resp.status_code}: {resp.text}")
            return {"error": f"Tencent Request Failed {resp.status_code}", "details": resp.text}
        
        data = resp.json()
        if "Response" in data and "Error" in data["Response"]:
             print(f"[MediaService] Tencent API Error: {data['Response']['Error']}")
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
                await asyncio.sleep(2)
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

        prompt = self._merge_negative_prompt(prompt, negative_prompt)
        
        api_key = config.get("api_key") or os.getenv("DASHSCOPE_API_KEY")
        endpoint = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis" 
        model = config.get("model") or "wanx2.1-i2v-plus"
        
        # Auto-correction for KF2V with single image to avoid "video frames must be set" error
        # KF2V likely requires multiple frames or specific array input, while I2V handles single image.
        if "kf2v" in model and ref_image and not last_frame_url:
             print(f"[Wanxiang] Model {model} requested but only 1 ref image provided. Switching to wanx2.1-i2v-plus.")
             model = "wanx2.1-i2v-plus"

        base_metadata = {"provider": "wanxiang", "model": model, "prompt": prompt}
        
        # Determine parameter names based on model type
        # i2v (Image) uses image_url
        # kf2v (KeyFrame) uses first_frame_url/last_frame_url, so we exclude it from is_i2v
        is_i2v = "i2v" in model
        
        first_img = self._resolve_ref_for_api(ref_image, force_data_uri_for_local=True)
        
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
            last_img = self._resolve_ref_for_api(last_frame_url, force_data_uri_for_local=True)
            if last_img:
                if is_i2v:
                     logger.warning("[Wanxiang] Warning: Model is i2v but last_frame_url provided. Ignoring.")
                else:
                     input_data["last_frame_url"] = last_img
        
        # Construct Parameters safely
        # Default resolution
        res = str(config.get("resolution", "720P"))
        
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

        # logger.info(f"[Wanxiang] Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        headers = {"X-DashScope-Async": "enable", "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        print(f"[Wanxiang] POSTING to {endpoint} with Model {model}")
        
        def _post(): return requests.post(endpoint, json=payload, headers=headers, timeout=60, verify=False)
        
        try:
            resp = await asyncio.to_thread(_post)
            
            if resp.status_code != 200: 
                print(f"[Wanxiang] HTTP {resp.status_code} Error Body: {resp.text}")
                # Try to parse error code if json
                try: 
                    err_body = resp.json()
                    return {"error": f"Wanxiang API Error ({err_body.get('code', 'Unknown')})", "details": err_body.get('message', resp.text)}
                except:
                    return {"error": f"Submission Failed {resp.status_code}", "details": resp.text}
            
            data = resp.json()
            print(f"[Wanxiang] Submission Success: {data}")
        except Exception as e:
            print(f"[Wanxiang] Exception: {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"Wanxiang Request Exception: {e}"}

        task_id = data.get("output", {}).get("task_id")
        if not task_id: return {"error": "No Task ID"}
        
        task_endpoint = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        
        for _ in range(120):
            await asyncio.sleep(2)
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
                     print(f"[Wanxiang] Task Failed: {err_msg}")
                     return {"error": "Generation Failed", "details": err_msg}
        return {"error": "Timeout"}

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
                     resp = requests.get(ref_image, timeout=30)
                     if resp.status_code == 200:
                         ref_bytes = resp.content
                 except Exception:
                     ref_bytes = None
             else:
                 b64 = self._get_image_base64_for_api(ref_image)
                 if b64 and b64 != ref_image:
                     ref_bytes = base64.b64decode(b64)
            
             if ref_bytes:
                 files = {"init_image": ("init_image.png", ref_bytes, "image/png")}
                 data = {"text_prompts[0][text]": prompt, "init_image_mode": "IMAGE_STRENGTH", "image_strength": 0.35}
                 if str(negative_prompt or "").strip():
                     data["text_prompts[1][text]"] = str(negative_prompt).strip()
                     data["text_prompts[1][weight]"] = -1
                 
                 def _post_i2i(): return requests.post(url, headers=headers, files=files, data=data, timeout=60, verify=False)
                 resp = await asyncio.to_thread(_post_i2i)
             else:
                 return {"error": "Could not load reference image"}

        else:
             # T2I
             url = f"{endpoint}/v1/generation/{model}/text-to-image"
             headers["Content-Type"] = "application/json"
             body = {"text_prompts": [{"text": prompt}], "cfg_scale": 7, "height": 1024, "width": 1024, "samples": 1}
             if str(negative_prompt or "").strip():
                 body["text_prompts"].append({"text": str(negative_prompt).strip(), "weight": -1})
             def _post_t2i(): return requests.post(url, headers=headers, json=body, timeout=60, verify=False)
             resp = await asyncio.to_thread(_post_t2i)
        
        if resp.status_code != 200: return {"error": f"Stability Error {resp.status_code}", "details": resp.text}
        
        data = resp.json()
        artifacts = data.get("artifacts", [])
        if artifacts:
             b64 = artifacts[0].get("base64")
             # Convert to data uri for consistency or save? 
             # The system seems to expect saving to disk for `generated_url`.
             # We should probably save it.
             # _download_and_save expects a URL.
             # But here we have base64.
             # Let's save it manually.
             try:
                 img_bytes = base64.b64decode(b64)
                 filename = f"gen_sd_{uuid.uuid4().hex[:8]}.png"
                 UPLOAD_DIR = settings.UPLOAD_DIR
                 if not os.path.isabs(UPLOAD_DIR):
                     # If relative, make it absolute relative to cwd or backend root to avoid ambiguity
                     # Assuming cwd is backend root as per main.py execution
                     UPLOAD_DIR = os.path.abspath(UPLOAD_DIR)
                 
                 save_path = os.path.join(UPLOAD_DIR, filename)
                 os.makedirs(os.path.dirname(save_path), exist_ok=True)
                 with open(save_path, "wb") as f: f.write(img_bytes)
                 
                 meta = {"raw": data}
                 meta.update(base_metadata)
                 return {"url": f"/uploads/{filename}", "metadata": meta}
             except Exception as e:
                 return {"error": f"Failed to save image: {e}"}
        return {"error": "No artifacts"}

    # --- Helper to Common Requests ---
    async def _common_requests_post(self, url, payload, api_key, log_tag, timeout=60, extra_metadata=None):
        # Async wrap for requests
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        def _post(use_proxy=True):
            kwargs = {"json": payload, "headers": headers, "timeout": timeout, "verify": False}
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(url, **kwargs)
        
        try:
            try:
                resp = await asyncio.to_thread(_post, True)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # Retry without proxy if connection fails (common for domestic APIs vs Global Proxy)
                print(f"[{log_tag}] Connection Failed with Proxy ({str(e)[:50]}...). Retrying without proxy...")
                resp = await asyncio.to_thread(_post, False)

            if resp.status_code == 200:
                data = resp.json()
                print(f"[{log_tag}] API Response: {data}") # DEBUG USER REQUEST
                metadata = {"raw": data}
                if extra_metadata:
                    metadata.update(extra_metadata)

                if "data" in data and len(data["data"]) > 0:
                    return {"url": data["data"][0]["url"], "metadata": metadata}
                return {"url": data.get("url"), "metadata": metadata}
            else:
                print(f"[{log_tag}] Error {resp.status_code}: {resp.text}")
                return {"error": f"API Error {resp.status_code}", "details": resp.text, "submit_failed": True}
        except requests.exceptions.Timeout as e:
            print(f"[{log_tag}] Timeout: {e}")
            return {"error": "Upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            print(f"[{log_tag}] RequestException: {e}")
            return {"error": "Upstream request failed", "details": str(e), "submit_failed": True}
        except Exception as e:
            print(f"[{log_tag}] Exception: {e}")
            return {"error": str(e), "submit_failed": True}

    async def _submit_and_poll_video(self, url, payload, api_key, log_tag, extra_metadata=None, poll_timeout_seconds: int = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS, poll_interval_seconds: int = 2):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        print(f"[{log_tag}] Submitting to URL: {url} | Payload: {payload}")
        
        def _post(use_proxy=True, connection_close: bool = False):
            request_headers = dict(headers)
            if connection_close:
                request_headers["Connection"] = "close"
            kwargs = {"json": payload, "headers": request_headers, "timeout": 60, "verify": False}
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
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                print(f"[{log_tag}] Submit failed with proxy ({str(e)[:120]}), retrying without proxy...")
                try:
                    resp = await asyncio.to_thread(_post, False)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e2:
                    print(f"[{log_tag}] Submit retry without proxy failed ({str(e2)[:120]}), retrying with connection close...")
                    resp = await asyncio.to_thread(_post, False, True)
            if resp.status_code not in [200, 201]: 
                return {"error": f"Submission Failed {resp.status_code}", "details": resp.text, "submit_failed": True}
            
            data = resp.json()
            task_id = data.get("id") or data.get("task_id")
            if not task_id and isinstance(data.get("data"), dict):
                task_id = data.get("data", {}).get("id") or data.get("data", {}).get("task_id")
            if not task_id: return {"error": "No Task ID", "submit_failed": True}
            
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
                        content = p_data.get("content", {})
                        video_url = content.get("video_url") or content.get("url")
                        if not video_url and isinstance(p_data.get("data"), dict):
                            data_content = p_data.get("data", {}).get("content", {}) or {}
                            video_url = data_content.get("video_url") or data_content.get("url")
                        metadata = {"raw": p_data}
                        if extra_metadata:
                            metadata.update(extra_metadata)
                        return {"url": video_url, "metadata": metadata}
                    elif status_l in ["failed", "error", "canceled", "cancelled"]:
                        return {"error": "Generation Failed", "details": p_data.get("error")}
            return {"error": f"Timeout after {poll_timeout_seconds}s"}
        except requests.exceptions.Timeout as e:
            return {"error": "Upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            details = str(e)
            if "10054" in details or "ConnectionResetError" in details:
                details = f"{details}. Possible network middlebox/proxy reset on large request body; retried with no-proxy once."
            return {"error": "Upstream request failed", "details": details, "submit_failed": True}
        except Exception as e:
            return {"error": str(e), "submit_failed": True}

    async def _submit_and_poll_grsai(self, url, payload, api_key, result_url, is_video=False, extra_metadata=None, trace_id: Optional[str] = None):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        trace_id = trace_id or f"grsai-{uuid.uuid4().hex[:10]}"
        payload_digest = hashlib.md5(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]

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
                return requests.post(submit_url, json=payload, headers=headers, timeout=(15, 120), verify=False)

            def _post_no_proxy():
                return requests.post(
                    submit_url,
                    json=payload,
                    headers=headers,
                    timeout=(15, 120),
                    verify=False,
                    proxies={"http": None, "https": None},
                )

            try:
                submit_started = time.perf_counter()
                try:
                    resp = await asyncio.to_thread(_post)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                    logger.warning("[GrsaiTrace][%s] submit primary failed, retry without proxy | submit_url=%s", trace_id, submit_url)
                    resp = await asyncio.to_thread(_post_no_proxy)
                submit_ms = int((time.perf_counter() - submit_started) * 1000)
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

            for i in range(100):
                await asyncio.sleep(3)

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
                            meta = {"raw": p_data}
                            if extra_metadata:
                                meta.update(extra_metadata)
                            return {"url": media_url, "metadata": meta}
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
        prompt = self._merge_negative_prompt(prompt, negative_prompt)
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
            "flux2-pro": "flux-2/pro-text-to-image",
            "flux2-pro-i2i": "flux-2/pro-image-to-image",
            "flux2-flex": "flux-2/flex-text-to-image",
            "flux2-flex-i2i": "flux-2/flex-image-to-image",
            "gpt-image-1.5": "gpt-image/1-5-text-to-image",
            "gpt-image-1.5-i2i": "gpt-image/1-5-image-to-image",

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
        tool_conf = config.get("config", {}) or {}

        model_lower = str(model or "").strip().lower()
        use_veo_api = bool(gen_type == "video" and model_lower.startswith("veo"))
        use_runway_api = bool(gen_type == "video" and "runway" in model_lower)
        use_4o_image_api = bool(gen_type == "image" and ("gpt4o-image" in model_lower or "4o-image" in model_lower))
        use_flux_kontext_api = bool(gen_type == "image" and ("flux-kontext" in model_lower or "flux/kontext" in model_lower))
        use_suno_api = bool(gen_type == "audio" and "suno" in model_lower)
        is_kling_3_video = bool(gen_type == "video" and ("kling-3.0" in model_lower or model_lower == "kling3"))

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

        raw_ar = str(aspect_ratio or "").strip()
        normalized_ar = self._normalize_aspect_ratio_value(aspect_ratio)
        if use_veo_api and raw_ar.lower() in {"auto", "adaptive"}:
            normalized_ar = "Auto"
        if normalized_ar:
            payload_input["aspect_ratio"] = normalized_ar

        if gen_type == "image":
            normalized_image_size = self._normalize_image_size_value(
                image_size or tool_conf.get("image_size") or tool_conf.get("imageSize")
            )
            if normalized_image_size:
                payload_input["image_size"] = normalized_image_size
        else:
            duration_value = 5
            try:
                duration_value = int(float(duration if duration is not None else 5))
            except Exception:
                duration_value = 5
            payload_input["duration"] = str(max(1, duration_value))

        resolved_refs: List[str] = []
        if ref_image:
            ref_list = ref_image if isinstance(ref_image, list) else [ref_image]
            for ref in ref_list:
                if use_veo_api:
                    resolved = self._process_veo_image(ref, normalized_ar or "16:9")
                else:
                    resolved = self._resolve_ref_for_api(ref, force_data_uri_for_local=True)
                if resolved:
                    resolved_refs.append(resolved)

        if resolved_refs:
            payload_input["image_urls"] = resolved_refs
            payload_input["image_url"] = resolved_refs[0]

        if last_frame_url:
            if use_veo_api:
                last_ref = self._process_veo_image(last_frame_url, normalized_ar or "16:9")
            else:
                last_ref = self._resolve_ref_for_api(last_frame_url, force_data_uri_for_local=True)
            if last_ref:
                payload_input["last_frame_url"] = last_ref

        if not use_veo_api and gen_type == "video":
            model_lower = str(model or "").strip().lower()

            if model_lower == "bytedance/v1-pro-text-to-video":
                payload_input.setdefault("aspect_ratio", normalized_ar or "16:9")
                payload_input.setdefault("resolution", str(tool_conf.get("resolution") or "720p"))
            elif model_lower == "bytedance/v1-lite-text-to-video":
                payload_input.setdefault("aspect_ratio", normalized_ar or "16:9")
                payload_input.setdefault("resolution", str(tool_conf.get("resolution") or "720p"))
            elif model_lower == "wan/2-6-text-to-video":
                payload_input["duration"] = "10" if str(payload_input.get("duration")) not in {"5", "10", "15"} else str(payload_input.get("duration"))
                payload_input.setdefault("resolution", str(tool_conf.get("resolution") or "1080p"))
            elif model_lower == "sora-2-text-to-video":
                if "n_frames" not in payload_input:
                    payload_input["n_frames"] = "10"
                if "aspect_ratio" not in payload_input:
                    payload_input["aspect_ratio"] = "portrait" if normalized_ar == "9:16" else "landscape"
            elif model_lower == "hailuo/02-text-to-video-pro":
                if "prompt_optimizer" not in payload_input:
                    payload_input["prompt_optimizer"] = bool(tool_conf.get("prompt_optimizer", True))

        callback_url = str(
            tool_conf.get("webHook")
            or tool_conf.get("callBackUrl")
            or tool_conf.get("callback_url")
            or tool_conf.get("callbackUrl")
            or ""
        ).strip()
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

            watermark_text = str(tool_conf.get("watermark") or "").strip()
            if watermark_text:
                payload["watermark"] = watermark_text

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
                "quality": "1080p" if "1080" in str(tool_conf.get("resolution") or "") else "720p",
                "aspectRatio": normalized_ar if normalized_ar in {"16:9", "4:3", "1:1", "3:4", "9:16"} else "16:9",
                "waterMark": str(tool_conf.get("watermark") or ""),
            }
            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url
            if resolved_refs:
                payload["imageUrl"] = resolved_refs[0]
            
            logger.info("KIE Runway submit payload | endpoint=%s", submit_url)
        elif use_4o_image_api:
            # Handle 4o image payload
            payload = {
                "prompt": prompt,
                "size": tool_conf.get("size") or "1:1",
                "isEnhance": bool(tool_conf.get("isEnhance")),
                "uploadCn": bool(tool_conf.get("uploadCn")),
                "enableFallback": bool(tool_conf.get("enableFallback")),
                "fallbackModel": tool_conf.get("fallbackModel", "FLUX_MAX"),
            }
            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url
            if resolved_refs:
                payload["filesUrl"] = resolved_refs
            
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
            }
            if tool_conf.get("watermark"):
                payload["watermark"] = str(tool_conf.get("watermark"))
            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url
            if resolved_refs:
                payload["inputImage"] = resolved_refs[0]
            
            logger.info("KIE Flux Kontext submit payload | endpoint=%s model=%s", submit_url, payload["model"])
        elif use_suno_api:
            payload = {
                "prompt": prompt,
                "model": "V5" if "v5" in model_lower else ("V4_5" if "v4.5" in model_lower or "4.5" in model_lower else "V4"),
                "customMode": bool(tool_conf.get("customMode", False)),
                "instrumental": bool(tool_conf.get("instrumental", False)),
            }
            if payload["customMode"]:
                payload["style"] = tool_conf.get("style", "Pop")
                payload["title"] = tool_conf.get("title", "AI Generated Track")
            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url
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
            sound_enabled = _normalize_bool(tool_conf.get("sound"), True if multi_shots else False)

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

            configured_image_urls = tool_conf.get("image_urls")
            kling_image_urls: List[str] = []
            if isinstance(configured_image_urls, list):
                kling_image_urls = [str(item).strip() for item in configured_image_urls if str(item).strip()]
            if not kling_image_urls:
                kling_image_urls = list(resolved_refs)
                last_frame_resolved = payload_input.get("last_frame_url") or payload_input.get("lastFrameUrl")
                if last_frame_resolved:
                    last_frame_text = str(last_frame_resolved).strip()
                    if last_frame_text and last_frame_text not in kling_image_urls:
                        kling_image_urls.append(last_frame_text)

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
            if isinstance(raw_kling_elements, list):
                for element in raw_kling_elements:
                    if not isinstance(element, dict):
                        continue
                    name = str(element.get("name") or "").strip()
                    description = str(element.get("description") or "").strip()
                    if not name or not description:
                        continue

                    normalized_element: Dict[str, Any] = {
                        "name": name,
                        "description": description,
                    }

                    image_inputs = element.get("element_input_urls")
                    if isinstance(image_inputs, list):
                        urls = [str(item).strip() for item in image_inputs if str(item).strip()]
                        if urls:
                            normalized_element["element_input_urls"] = urls

                    video_inputs = element.get("element_input_video_urls")
                    if isinstance(video_inputs, list):
                        urls = [str(item).strip() for item in video_inputs if str(item).strip()]
                        if urls:
                            normalized_element["element_input_video_urls"] = urls

                    normalized_elements.append(normalized_element)

            if normalized_elements:
                kling_input["kling_elements"] = normalized_elements

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
        else:
            payload = {
                "model": model,
                "input": payload_input,
            }
            if callback_url and callback_url != "-1":
                payload["callBackUrl"] = callback_url

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
            log_payload = dict(submit_payload)
            if "input" in log_payload and "image_urls" in log_payload["input"]:
                log_payload["input"] = dict(log_payload["input"])
                log_payload["input"]["image_urls"] = ["<base64...>" for _ in log_payload["input"]["image_urls"]]
            if "imageUrls" in log_payload:
                log_payload["imageUrls"] = ["<base64...>" for _ in log_payload["imageUrls"]]
            if "images" in log_payload:
                 log_payload["images"] = [
                     "<base64...>" if isinstance(img, str) and img.startswith("data:image/") else img 
                     for img in log_payload["images"]
                 ]
            print(f"[KIE_video] Submitting to URL: {submit_url} | Model: {submit_payload.get('model')} | Payload: {log_payload}")
            
            logger.info("KIE performing HTTP Request | Method: POST | URL: %s | Payload_model: %s", submit_url, submit_payload.get('model'))
            return requests.post(submit_url, json=submit_payload, headers=headers, timeout=90, verify=False)

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

        submit_payload: Dict[str, Any] = dict(payload or {})
        submitted_model = submit_payload.get("model") if isinstance(submit_payload, dict) else model
        initial_submitted_model = str(submitted_model or "").strip()
        veo_retry_models = _build_veo_retry_models(submitted_model) if use_veo_api else []

        def _rebuild_veo_image_urls_with_limit(limit_bytes: int) -> List[str]:
            rebuilt_refs: List[str] = []
            if ref_image:
                src_list = ref_image if isinstance(ref_image, list) else [ref_image]
                for src in src_list:
                    rebuilt = self._process_veo_image(src, normalized_ar or "16:9")
                    if rebuilt:
                        rebuilt_refs.append(rebuilt)
            if last_frame_url:
                rebuilt_last = self._process_veo_image(last_frame_url, normalized_ar or "16:9")
                if rebuilt_last and rebuilt_last not in rebuilt_refs:
                    rebuilt_refs.append(rebuilt_last)
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

        try:
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
            return {
                "error": f"KIE submission failed {resp.status_code}",
                "details": _kie_response_details(resp),
                "submit_failed": True,
                "runtime_model": submitted_model,
            }

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

        base_metadata = {"provider": "kie", "model": submitted_model, "prompt": prompt}

        code = data.get("code")
        if code not in (None, 200, "200"):
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

        def _is_ok_code(value: Any) -> bool:
            if value in (None, 200, "200"):
                return True
            try:
                return int(str(value).strip()) == 200
            except Exception:
                return False

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

        def _poll_status():
            candidates = [
                {"taskId": task_id},
                {"task_id": task_id},
                {"id": task_id},
            ]
            last_resp = None
            for params in candidates:
                try:
                    resp = requests.get(query_url, params=params, headers=headers, timeout=45, verify=False)
                    last_resp = resp
                    if resp.status_code == 200:
                        return resp
                except Exception:
                    continue
            if last_resp is not None:
                return last_resp
            return requests.get(query_url, params={"taskId": task_id}, headers=headers, timeout=45, verify=False)

        for i in range(120):
            await asyncio.sleep(3)
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
            if not _is_ok_code(poll_code):
                continue

            record = poll_data.get("data") or poll_data.get("result") or poll_data
            state = str(record.get("state") or record.get("status") or "").strip().lower()
            success_flag = record.get("successFlag")
            if success_flag is None:
                success_flag = record.get("success_flag")
            if success_flag is None and isinstance(record.get("response"), dict):
                success_flag = record.get("response", {}).get("successFlag")

            if state in {"waiting", "queued", "queuing", "processing", "running", "generating", "pending"}:
                continue
            if success_flag in {0, "0"}:
                continue

            if state in {"success", "succeeded", "completed", "done"}:
                result_payload = record.get("resultJson")
                video_urls = _extract_kie_video_urls(result_payload)
                if not video_urls:
                    video_urls = _extract_kie_video_urls(record)
                if not video_urls and isinstance(record.get("response"), dict):
                    video_urls = _extract_kie_video_urls(record.get("response"))

                if gen_type == "video" or gen_type == "audio":
                    selected_video_url = _pick_preferred_kie_media_url(video_urls)
                    if selected_video_url:
                        meta = {"raw": poll_data}
                        meta.update(base_metadata)
                        return {"url": selected_video_url, "metadata": meta}

                urls = self._extract_urls_from_payload(result_payload)
                if not urls:
                    urls = self._extract_urls_from_payload(record)
                selected_url = _pick_preferred_kie_media_url(urls)
                if not selected_url:
                    return {"error": "KIE task succeeded but no media URL found", "details": poll_data}

                meta = {"raw": poll_data}
                meta.update(base_metadata)
                return {"url": selected_url, "metadata": meta}
            if success_flag in {1, "1"}:
                video_urls = _extract_kie_video_urls(record.get("resultUrls"))
                if not video_urls:
                    video_urls = _extract_kie_video_urls(record)
                if not video_urls and isinstance(record.get("response"), dict):
                    video_urls = _extract_kie_video_urls(record.get("response"))

                if gen_type == "video" or gen_type == "audio":
                    selected_video_url = _pick_preferred_kie_media_url(video_urls)
                    if selected_video_url:
                        meta = {"raw": poll_data}
                        meta.update(base_metadata)
                        return {"url": selected_video_url, "metadata": meta}

                urls = self._extract_urls_from_payload(record.get("resultUrls"))
                if not urls:
                    urls = self._extract_urls_from_payload(record)
                if not urls and isinstance(record.get("response"), dict):
                    urls = self._extract_urls_from_payload(record.get("response"))
                selected_url = _pick_preferred_kie_media_url(urls)
                if not selected_url:
                    return {"error": "KIE task succeeded but no media URL found", "details": poll_data}
                meta = {"raw": poll_data}
                meta.update(base_metadata)
                return {"url": selected_url, "metadata": meta}

            if state in {"fail", "failed", "error", "canceled", "cancelled"}:
                return {
                    "error": "KIE generation failed",
                    "details": record.get("failMsg") or record.get("message") or poll_data,
                    "runtime_model": submitted_model,
                }
            if success_flag in {2, "2", 3, "3"}:
                return {
                    "error": "KIE generation failed",
                    "details": record.get("failMsg") or record.get("message") or poll_data,
                    "runtime_model": submitted_model,
                }

        return {"error": "Timeout polling KIE task"}

    # -- Helpers --
    def _download_and_save(self, url: str, filename_base: str = None, user_id: int = 1) -> str:
        try:
             UPLOAD_DIR = settings.UPLOAD_DIR
             USER_DIR = os.path.join(UPLOAD_DIR, str(user_id))
             
             if not os.path.isabs(USER_DIR):
                 USER_DIR = os.path.abspath(USER_DIR)

             if not os.path.exists(USER_DIR): os.makedirs(USER_DIR)

             if url.startswith("/"): return url
             if "localhost" in url or "127.0.0.1" in url: return url

             response = requests.get(url, stream=True, timeout=600, headers={"User-Agent": "Mozilla/5.0"})
             if response.status_code == 200:
                ext = ".png"
                ct = response.headers.get("Content-Type", "").lower()
                if "video" in ct or ".mp4" in url: ext = ".mp4"
                elif "jpeg" in ct: ext = ".jpg"
                elif "webp" in ct: ext = ".webp"
                
                filename = f"gen_{uuid.uuid4().hex[:8]}{ext}"
                if filename_base: filename = f"{filename_base}_{filename}"
                    
                file_path = os.path.join(USER_DIR, filename)
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(4096): f.write(chunk)
                
                relative_path = f"/uploads/{user_id}/{filename}"
                if settings.RENDER_EXTERNAL_URL:
                    base = settings.RENDER_EXTERNAL_URL.rstrip('/')
                    return f"{base}{relative_path}"
                return relative_path
        except Exception as e:
            print(f"Download failed: {e}")
        return url
        
    def _process_veo_image(self, url_or_path, aspect_ratio):
        """Helper to resize/crop images to strictly match Veo aspect ratio requirements"""
        try:
            # Reuse base fetch logic
            b64_raw = self._get_image_base64_for_api(url_or_path, force_data_uri=False)
            if not b64_raw: return ""
            
            img_data = base64.b64decode(b64_raw)
            img = Image.open(io.BytesIO(img_data)).convert("RGB")
            
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

            print(f"[Veo] Ref processed size={len(best_data)} bytes target<={max_bytes} ratio={aspect_ratio}")
            b64_final = base64.b64encode(best_data).decode('utf-8')
            return f"data:image/jpeg;base64,{b64_final}"
            
        except Exception as e:
            print(f"[Veo] Image Process Error: {e}")
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

    def _resolve_ref_for_api(self, url_or_path, force_data_uri_for_local=True):
        if isinstance(url_or_path, list):
            if not url_or_path:
                return None
            url_or_path = url_or_path[0]

        raw = str(url_or_path or "").strip()
        if not raw:
            return None
        if raw.startswith("data:"):
            return raw
        if self._is_public_http_url(raw):
            return raw

        encoded = self._get_image_base64_for_api(raw, force_data_uri=force_data_uri_for_local)
        if not encoded or encoded == raw:
            return None
        return encoded

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

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=90, verify=False)
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
                return file_url
            return None
        except Exception as e:
            logger.warning("KIE file upload exception | error=%s", str(e)[:300])
            return None

    def _optimize_image_bytes_for_data_uri(self, data: bytes, mime: str = "image/png") -> tuple[bytes, str]:
        # Keep provider compatibility while avoiding very large JSON request payloads.
        max_bytes = max(512 * 1024, int(os.getenv("VIDEO_REF_DATA_URI_MAX_BYTES", str(6 * 1024 * 1024))))
        max_edge = max(512, int(os.getenv("VIDEO_REF_DATA_URI_MAX_EDGE", "2048")))

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
            print(f"[MediaService] Image optimize skipped: {e}")

        return data, mime

    def _resolve_ref_list_for_api(self, refs, force_data_uri_for_local=True):
        source = refs if isinstance(refs, list) else [refs]
        result = []
        for item in source:
            resolved = self._resolve_ref_for_api(item, force_data_uri_for_local=force_data_uri_for_local)
            if resolved:
                result.append(resolved)
        return result

    def _get_image_base64_for_api(self, url_or_path, force_data_uri=False):
        # Helper to get base64 from local or remote
        # NOTE: This only processes ONE image. If list is passed, we take the first.
        # Callers MUST handle lists if they need multiple images.
        if isinstance(url_or_path, list):
             if not url_or_path: return None
             url_or_path = url_or_path[0]

        try:
            print(f"[MediaService] Conversion: Processing ref image: {str(url_or_path)[:100]}")
            data = None
            mime = "image/png"
            if "/uploads/" in url_or_path:
                 fname = url_or_path.split("/uploads/")[-1]
                 UPLOAD_DIR = settings.UPLOAD_DIR
                 if not os.path.isabs(UPLOAD_DIR):
                     UPLOAD_DIR = os.path.abspath(UPLOAD_DIR)

                 # simplified path resolution
                 import urllib.parse
                 # Ensure fname doesn't contain query params for local file check
                 clean_fname = fname.split('?')[0]
                 path = os.path.join(UPLOAD_DIR, urllib.parse.unquote(clean_fname))
                 
                 if os.path.exists(path):
                     with open(path, "rb") as f: data = f.read()
                     if path.endswith(".jpg"): mime = "image/jpeg"
                 else:
                     print(f"[MediaService] Error: Local File Not Found: {path}")
            elif url_or_path.startswith("http"):
                 r = requests.get(url_or_path, timeout=30)
                 if r.status_code == 200: 
                     data = r.content
                     ct = r.headers.get("Content-Type", "")
                     if "jpeg" in ct: mime = "image/jpeg"
                 else:
                     print(f"[MediaService] Error: HTTP Download Failed {r.status_code}: {url_or_path}")
            
            if data:
                if force_data_uri:
                    before_size = len(data)
                    data, mime = self._optimize_image_bytes_for_data_uri(data, mime)
                    after_size = len(data)
                    if after_size < before_size:
                        print(f"[MediaService] Ref optimized for data URI: {before_size} -> {after_size} bytes ({mime})")
                b64 = base64.b64encode(data).decode("utf-8")
                if force_data_uri: return f"data:{mime};base64,{b64}"
                return b64
            else:
                print(f"[MediaService] Error: No Data retrieved for {url_or_path}")
        except Exception as e:
            print(f"[MediaService] Exception in Base64 Conversion: {e}")
        
        return url_or_path # Return original if fail

media_service = MediaGenerationService()

