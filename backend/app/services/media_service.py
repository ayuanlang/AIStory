
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
from PIL import Image
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from app.db.session import SessionLocal
from app.models.all_models import APISetting, SystemAPISetting
from app.core.config import settings
from sqlalchemy import cast, String

# Suppress InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import logging
logger = logging.getLogger("media_service")
# ... imports ...

class MediaGenerationService:
# ...
    DOUBAO_MIN_IMAGE_PIXELS = 3_686_400
    SMART_ROUTER_PROVIDER = "smart_router"

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
            if isinstance(raw, str) and raw.strip() and not self._safe_json_dict(raw):
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
            q = q.filter(SystemAPISetting.provider == provider)

        bad_ids: List[int] = []
        for row in q.all():
            raw = getattr(row, "config_raw", None)
            if isinstance(raw, str) and raw.strip() and not self._safe_json_dict(raw):
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
            SystemAPISetting.provider == provider,
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
        return session.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.category == category,
            APISetting.is_active == True,
        ).order_by(APISetting.id.desc()).first()

    def _normalize_provider_name(self, provider: Optional[str], category: Optional[str] = None) -> str:
        raw = str(provider or "").strip().lower()
        mapping = {
            "grsai-image": "grsai",
            "grsai-video": "grsai",
            "grsai": "grsai",
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
            "tencent": {"base_url": "https://aiart.tencentcloudapi.com", "model": "hunyuan-vision"},
            "wanxiang": {"base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis", "model": "wanx2.1-i2v-plus"},
            "vidu": {"base_url": "https://api.vidu.studio/open/v1/creation/video", "model": "vidu2.0"},
        }

        rows = session.query(SystemAPISetting).filter(
            SystemAPISetting.category == category,
        ).order_by(SystemAPISetting.id.asc()).all()

        candidates: List[Dict[str, Any]] = []
        for row in rows:
            provider = self._normalize_provider_name(row.provider, category)
            if not provider:
                continue
            cfg = self._safe_json_dict(row.config)
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
                "config": self._setting_to_config(row, provider, defaults),
            })

        return candidates

    async def _execute_generation_by_provider(
        self,
        category: str,
        provider: str,
        prompt: str,
        api_config: Dict[str, Any],
        reference_image_url: Optional[Union[str, List[str]]],
        width: Optional[int] = None,
        height: Optional[int] = None,
        aspect_ratio: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        duration: int = 5,
        keyframes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if category == "Image":
            if width and height:
                if not api_config.get("config"):
                    api_config["config"] = {}
                api_config["config"]["width"] = width
                api_config["config"]["height"] = height

            if provider in ["doubao", "ark"]:
                return await self._handle_doubao_generation("image", prompt, api_config, reference_image_url, aspect_ratio=aspect_ratio)
            if provider == "grsai":
                return await self._handle_grsai_generation("image", prompt, api_config, reference_image_url, aspect_ratio=aspect_ratio)
            if provider == "tencent":
                return await self._handle_tencent_generation("image", prompt, api_config, reference_image_url)
            if provider in ["stability", "stable diffusion"]:
                return await self._handle_stability_generation("image", prompt, api_config, reference_image_url)

            print(f"Mocking Image Gen for {provider}")
            return {
                "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/generated_image.png",
                "metadata": {"provider": provider, "model": api_config.get("model", "default")}
            }

        if category == "Video":
            if provider in ["doubao", "ark"]:
                return await self._handle_doubao_generation("video", prompt, api_config, reference_image_url, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio)
            if provider == "grsai":
                return await self._handle_grsai_generation("video", prompt, api_config, reference_image_url, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio)
            if provider == "tencent":
                return await self._handle_tencent_generation("video", prompt, api_config, reference_image_url, duration=duration)
            if provider in ["wanxiang", "wanx"]:
                return await self._handle_wanxiang_generation("video", prompt, api_config, reference_image_url, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio)
            if provider == "vidu":
                return await self._handle_vidu_generation("video", prompt, api_config, reference_image_url, last_frame_url=last_frame_url, duration=duration, aspect_ratio=aspect_ratio, keyframes=keyframes)

            print(f"Mocking Video Gen for {provider}")
            return {
                "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/generated_video.mp4",
                "metadata": {"provider": provider, "duration": duration}
            }

        return {"error": f"Unsupported category: {category}"}

    async def _generate_with_smart_routing(
        self,
        category: str,
        prompt: str,
        provider: str,
        api_config: Dict[str, Any],
        user_id: int,
        reference_image_url: Optional[Union[str, List[str]]],
        width: Optional[int] = None,
        height: Optional[int] = None,
        aspect_ratio: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        duration: int = 5,
        keyframes: Optional[List[str]] = None,
        requested_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        with SessionLocal() as session:
            smart_enabled = self._is_smart_routing_enabled(session, user_id)
            candidates = self._get_system_candidates(session, category)

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

        for index, attempt in enumerate(deduped_attempts, start=1):
            selected_provider = self._normalize_provider_name(attempt.get("provider"), category)
            selected_config = dict(attempt.get("config") or {})
            if not selected_provider:
                continue

            logger.info(
                "Smart routing attempt | category=%s user_id=%s attempt=%s/%s provider=%s model=%s tag=%s smart_enabled=%s",
                category,
                user_id,
                index,
                len(deduped_attempts),
                selected_provider,
                selected_config.get("model"),
                attempt.get("tag"),
                smart_enabled,
            )

            result = await self._execute_generation_by_provider(
                category=category,
                provider=selected_provider,
                prompt=prompt,
                api_config=selected_config,
                reference_image_url=reference_image_url,
                width=width,
                height=height,
                aspect_ratio=aspect_ratio,
                last_frame_url=last_frame_url,
                duration=duration,
                keyframes=keyframes,
            )

            if result and not result.get("error"):
                metadata = result.get("metadata") or {}
                metadata["smart_routing"] = {
                    "enabled": smart_enabled,
                    "attempt": index,
                    "attempt_tag": attempt.get("tag"),
                    "provider": selected_provider,
                }
                result["metadata"] = metadata
                return result

            final_error = result or {"error": "Generation failed"}

        return final_error

    def get_api_config(
        self,
        provider: str,
        user_id: int = 1,
        category: str = None,
        requested_model: Optional[str] = None,
        user_credits: int = 0,
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
                if not user_setting:
                    logger.warning(
                        "No active user api setting found in media service | user_id=%s category=%s",
                        user_id,
                        resolved_category,
                    )
                    return {}

                target_provider = str(user_setting.provider or "").strip()
                target_model = str(user_setting.model or "").strip()
                if not target_provider or not target_model:
                    logger.warning(
                        "Active user setting missing provider/model in media service | user_id=%s category=%s setting_id=%s provider=%s model=%s",
                        user_id,
                        resolved_category,
                        user_setting.id,
                        user_setting.provider,
                        user_setting.model,
                    )
                    return {}

                system_setting = session.query(SystemAPISetting).filter(
                    SystemAPISetting.category == resolved_category,
                    SystemAPISetting.provider == target_provider,
                    SystemAPISetting.model == target_model,
                ).order_by(SystemAPISetting.id.desc()).first()

                resolved_source = f"system_by_user_provider_model:{target_provider}/{target_model}"

                if system_setting:
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
                        "api_key": system_setting.api_key,
                        "base_url": system_setting.base_url or defaults.get(target_provider, {}).get("base_url"),
                        "model": system_setting.model or defaults.get(target_provider, {}).get("model"),
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

    async def generate_image(self, prompt: str, llm_config: Optional[Dict[str, Any]] = None, reference_image_url: Optional[Union[str, List[str]]] = None, width: int = None, height: int = None, aspect_ratio: str = None, user_id: int = 1, user_credits: int = 0, filename_base: Optional[str] = None):
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
        )

        print(f"[MediaService] Generating Image. Provider: {provider}, Refs Type: {type(reference_image_url)}, Refs: {reference_image_url}, W: {width}, H: {height}, AR: {aspect_ratio}")

        result = await self._generate_with_smart_routing(
            category="Image",
            prompt=prompt,
            provider=provider,
            api_config=api_config,
            user_id=user_id,
            reference_image_url=reference_image_url,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            requested_model=(llm_config or {}).get("model"),
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
            result["error"] = self._vendor_failed_message(provider, result.get("error"))
        return result

    async def generate_video(self, prompt: str, llm_config: Optional[Dict[str, Any]] = None, reference_image_url: Optional[Union[str, List[str]]] = None, last_frame_url: Optional[str] = None, duration: int = 5, aspect_ratio: Optional[str] = None, keyframes: Optional[List[str]] = None, user_id: int = 1, user_credits: int = 0, filename_base: Optional[str] = None):
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
        )

        print(f"[MediaService] Generating Video. Provider: {provider}, Refs: {reference_image_url}, LastFrame: {last_frame_url}, Ratio: {aspect_ratio}, Keyframes: {len(keyframes) if keyframes else 0}")

        result = await self._generate_with_smart_routing(
            category="Video",
            prompt=prompt,
            provider=provider,
            api_config=api_config,
            user_id=user_id,
            reference_image_url=reference_image_url,
            aspect_ratio=aspect_ratio,
            last_frame_url=last_frame_url,
            duration=duration,
            keyframes=keyframes,
            requested_model=(llm_config or {}).get("model"),
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
            result["error"] = self._vendor_failed_message(provider, result.get("error"))
        
        return result
    
    # --- Provider Implementations ---
    
    async def _handle_doubao_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None):
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
                
                base64_refs = []
                for ref_url in ref_list:
                    # Doubao API requires Data URI format if not using http URL
                    b64 = self._get_image_base64_for_api(ref_url, force_data_uri=True)
                    if b64: base64_refs.append(b64)
                    
                if base64_refs:
                    model_name = model or "doubao-seedream-4-5-251128"
                    payload = {
                        "model": model_name, "prompt": prompt, "response_format": "url",
                        # USER FEEDBACK: Field name must be "image", not "image_urls" for Doubao image-to-image
                        "image": base64_refs,
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
                content_payload.append({
                    "type": "image_url", 
                    "image_url": {"url": self._get_image_base64_for_api(start_img_url, force_data_uri=True)},
                    "role": "first_frame"
                })
                content_payload.append({
                    "type": "image_url", 
                    "image_url": {"url": self._get_image_base64_for_api(last_frame_url, force_data_uri=True)},
                    "role": "last_frame"
                })
            elif start_img_url:
                # Start Frame Only - Strict 'first_frame' role required for newer models (1.5 Pro)
                content_payload.append({
                    "type": "image_url", 
                    "image_url": {"url": self._get_image_base64_for_api(start_img_url, force_data_uri=True)},
                     "role": "first_frame"
                })
            elif last_frame_url:
                # Last Frame Only (Rare, but use role if strictly End frame)
                 content_payload.append({
                    "type": "image_url", 
                    "image_url": {"url": self._get_image_base64_for_api(last_frame_url, force_data_uri=True)},
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

            poll_timeout_seconds = 600
            poll_interval_seconds = 2
            try:
                if tool_conf.get("poll_timeout_seconds") is not None:
                    poll_timeout_seconds = max(60, int(tool_conf.get("poll_timeout_seconds")))
                elif tool_conf.get("timeout") is not None:
                    poll_timeout_seconds = max(60, int(tool_conf.get("timeout")))
            except Exception:
                poll_timeout_seconds = 600

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

    async def _handle_vidu_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, keyframes=None):
        """
        Vidu API Support (Images + Text -> Video)
        """
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
                 
            start_b64 = self._get_image_base64_for_api(start_img_src, force_data_uri=True)
            if not start_b64: return {"error": "Failed to load Start Image"}
            
            payload["start_image"] = start_b64
            
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
                b64 = self._get_image_base64_for_api(kf, force_data_uri=True)
                if b64:
                     # Attempt generic structure. 
                     # If backend rejects, we will know.
                     # Vidu Character Consistency uses "characters".
                     # This "image_settings" is likely for timeline control.
                     settings_arr.append({"image": b64})
            
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
                    start_b64 = self._get_image_base64_for_api(refs[0], force_data_uri=True)
                    if start_b64: images.append(start_b64)
            
            if last_frame_url:
                end_b64 = self._get_image_base64_for_api(last_frame_url, force_data_uri=True)
                if end_b64:
                     if not images: images.append(end_b64) # Use as start if no start
                     else: images.append(end_b64) # Use as end
            
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
             print(f"[Vidu] Polling Task {task_id}...")
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
             
    async def _handle_grsai_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None):
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

            if ref_image:
                # Force base64 conversion for Image references
                ref_list = [ref_image] if isinstance(ref_image, str) else ref_image
                base64_refs = []
                print(f"[Grsai] Processing {len(ref_list)} reference images...")
                for i, r in enumerate(ref_list):
                    # Pass force_data_uri=True if API expects data URI
                    b64 = self._get_image_base64_for_api(r, force_data_uri=True)
                    if b64: 
                        base64_refs.append(b64)
                    else:
                        print(f"[Grsai] Error: Failed to convert ref image {i} ({r}) to base64. Dropping.")
                
                print(f"[Grsai] Final Base64 Refs Count: {len(base64_refs)}")
                payload["urls"] = base64_refs
            
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

            if is_banana:
                # Banana might expect "1K" or specific strings.
                # If specialized model, maybe fallback to defaults unless sure.
                # Assuming Banana supports size param or defaults to 1K
                payload["imageSize"] = "1K" # simplification (Custom logic for Banana if needed)
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
                    val = self._get_image_base64_for_api(ref_image, force_data_uri=True)
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
                    val = self._get_image_base64_for_api(last_frame_url, force_data_uri=True)
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
            
            print(f"[Grsai] Task {task_id} submitted. Polling...")
            
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


    async def _handle_tencent_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5):
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
            b64_img = self._get_image_base64_for_api(ref_image)
            if not b64_img: 
                print("Failed to load reference image for Tencent I2I")
                return {"error": "Failed to load reference image for Tencent I2I"}
            payload["InputImage"] = b64_img
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

    async def _handle_wanxiang_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None):
        if gen_type != "video": return {"error": "Wanxiang only supports video"}
        
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
        
        first_img = self._get_image_base64_for_api(ref_image, force_data_uri=True)
        
        # Validations
        if is_i2v and not first_img:
             return {"error": "Wanxiang I2V model requires a reference image."}
        
        input_data = {"prompt": prompt}
        if config.get("negative_prompt"):
             input_data["negative_prompt"] = config.get("negative_prompt")
        
        if is_i2v:
            input_data["image_url"] = first_img
        elif first_img:
            # T2V with start frame (if supported)
            input_data["first_frame_url"] = first_img

        if last_frame_url:
            last_img = self._get_image_base64_for_api(last_frame_url, force_data_uri=True)
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

    async def _handle_stability_generation(self, gen_type, prompt, config, ref_image=None):
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
             # Need bytes for FormData
             # Re-read or download
             if "/uploads/" in ref_image:
                  # .. simplified ..
                  pass
             
             # For now, let's use the helper to get bytes, but helper returns base64. 
             # decode base64 back to bytes
             b64 = self._get_image_base64_for_api(ref_image)
             if b64:
                 ref_bytes = base64.b64decode(b64)
            
             if ref_bytes:
                 files = {"init_image": ("init_image.png", ref_bytes, "image/png")}
                 data = {"text_prompts[0][text]": prompt, "init_image_mode": "IMAGE_STRENGTH", "image_strength": 0.35}
                 
                 def _post_i2i(): return requests.post(url, headers=headers, files=files, data=data, timeout=60, verify=False)
                 resp = await asyncio.to_thread(_post_i2i)
             else:
                 return {"error": "Could not load reference image"}

        else:
             # T2I
             url = f"{endpoint}/v1/generation/{model}/text-to-image"
             headers["Content-Type"] = "application/json"
             body = {"text_prompts": [{"text": prompt}], "cfg_scale": 7, "height": 1024, "width": 1024, "samples": 1}
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
                return {"error": f"API Error {resp.status_code}", "details": resp.text}
        except requests.exceptions.Timeout as e:
            print(f"[{log_tag}] Timeout: {e}")
            return {"error": "Upstream request timeout", "details": str(e)}
        except requests.exceptions.RequestException as e:
            print(f"[{log_tag}] RequestException: {e}")
            return {"error": "Upstream request failed", "details": str(e)}
        except Exception as e:
            print(f"[{log_tag}] Exception: {e}")
            return {"error": str(e)}

    async def _submit_and_poll_video(self, url, payload, api_key, log_tag, extra_metadata=None, poll_timeout_seconds: int = 600, poll_interval_seconds: int = 2):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        def _post(): return requests.post(url, json=payload, headers=headers, timeout=60, verify=False)
        
        try:
            print(f"[{log_tag}] POST Payload Length: {len(json.dumps(payload))}") 
            try:
                resp = await asyncio.to_thread(_post)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                resp = await asyncio.to_thread(_post)
            print(f"[{log_tag}] Submission Response: {resp.text[:500]}...") # DEBUG USER REQUEST
            if resp.status_code not in [200, 201]: 
                print(f"[{log_tag}] Error {resp.status_code}: {resp.text}")
                return {"error": f"Submission Failed {resp.status_code}", "details": resp.text}
            
            data = resp.json()
            task_id = data.get("id") or data.get("task_id")
            if not task_id and isinstance(data.get("data"), dict):
                task_id = data.get("data", {}).get("id") or data.get("data", {}).get("task_id")
            if not task_id: return {"error": "No Task ID"}
            
            print(f"[{log_tag}] Task {task_id} submitted. Polling... timeout={poll_timeout_seconds}s interval={poll_interval_seconds}s")
            
            # Poll
            max_attempts = max(1, int(poll_timeout_seconds / max(1, poll_interval_seconds)))
            for _ in range(max_attempts):
                await asyncio.sleep(poll_interval_seconds)
                def _poll(): return requests.get(f"{url}/{task_id}", headers=headers, timeout=30, verify=False)
                try:
                    p_resp = await asyncio.to_thread(_poll)
                except requests.exceptions.Timeout:
                    continue
                if p_resp.status_code == 200:
                    p_data = p_resp.json()
                    print(f"[{log_tag}] Poll Response: {p_data}") # DEBUG USER REQUEST
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
            return {"error": "Upstream request timeout", "details": str(e)}
        except requests.exceptions.RequestException as e:
            return {"error": "Upstream request failed", "details": str(e)}
        except Exception as e:
            return {"error": str(e)}

    async def _submit_and_poll_grsai(self, url, payload, api_key, result_url, is_video=False, extra_metadata=None, trace_id: Optional[str] = None):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        trace_id = trace_id or f"grsai-{uuid.uuid4().hex[:10]}"
        payload_digest = hashlib.md5(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        print(f"[Grsai] Debug - POST URL: {url}")
        logger.info(
            "[GrsaiTrace][%s] submit start | submit_url=%s result_url=%s is_video=%s payload_digest=%s",
            trace_id,
            url,
            result_url,
            is_video,
            payload_digest,
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
            print(f"[Grsai] Upstream Try {index + 1}/{len(upstream_candidates)} -> {submit_url}")
            logger.info(
                "[GrsaiTrace][%s] upstream_try | idx=%s total=%s submit_url=%s poll_url=%s",
                trace_id,
                index + 1,
                len(upstream_candidates),
                submit_url,
                poll_url,
            )

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
                print(f"[Grsai] Submission network error on {submit_url}: {last_error}")
                logger.error("[GrsaiTrace][%s] submit network_error | submit_url=%s error=%s", trace_id, submit_url, last_error)
                continue

            print(f"[Grsai] API Returned: {resp.text[:1000]}")
            logger.info(
                "[GrsaiTrace][%s] submit response | submit_url=%s status=%s elapsed_ms=%s body_preview=%s",
                trace_id,
                submit_url,
                resp.status_code,
                submit_ms,
                (resp.text or "")[:300],
            )
            if resp.status_code != 200:
                print(f"[Grsai] API Error {resp.status_code}: {resp.text}")
                if resp.status_code == 429 or self._is_grsai_quota_or_throttle_error(resp.text):
                    logger.error("[GrsaiTrace][%s] submit throttled_or_quota | status=%s body=%s", trace_id, resp.status_code, (resp.text or "")[:500])
                    return {
                        "error": "Veo/Grsai 配额或频率受限",
                        "details": "上游返回 429 RESOURCE_EXHAUSTED（请求过于频繁或额度耗尽）。请降低并发、等待冷却或提升配额后重试。",
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
                return {"error": f"Submission Failed {resp.status_code}", "details": resp.text}

            try:
                data = resp.json()
            except Exception:
                return {"error": "Invalid Grsai response", "details": resp.text[:1000]}

            data_obj = data.get("data")
            if data_obj is None:
                print(f"[Grsai] API Logic Failure: {data}")
                msg = data.get("msg") or data.get("message") or "Unknown Error"
                return {"error": f"API Error {data.get('code')}", "details": msg}

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
                print(f"[Grsai] No Task ID in response: {data}")
                logger.error("[GrsaiTrace][%s] submit missing_task_id | response=%s", trace_id, str(data)[:1000])
                return {"error": "No Task ID", "details": data}

            print(f"[Grsai] Task {task_id} submitted. Polling via {poll_url}...")
            logger.info("[GrsaiTrace][%s] polling start | task_id=%s poll_url=%s", trace_id, task_id, poll_url)

            for i in range(100):
                await asyncio.sleep(3)

                def _poll():
                    return requests.post(poll_url, json={"id": task_id}, headers=headers, timeout=(10, 30), verify=False)

                try:
                    poll_started = time.perf_counter()
                    p_resp = await asyncio.to_thread(_poll)
                    poll_ms = int((time.perf_counter() - poll_started) * 1000)
                except requests.exceptions.Timeout:
                    logger.warning("[GrsaiTrace][%s] poll timeout | task_id=%s poll_idx=%s", trace_id, task_id, i + 1)
                    continue
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    logger.warning("[GrsaiTrace][%s] poll request_exception | task_id=%s poll_idx=%s error=%s", trace_id, task_id, i + 1, last_error)
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
                    if i in {0, 1, 2, 4, 9, 19, 39, 69, 99}:
                        logger.info(
                            "[GrsaiTrace][%s] poll response | task_id=%s poll_idx=%s status=%s elapsed_ms=%s has_url=%s",
                            trace_id,
                            task_id,
                            i + 1,
                            status_l,
                            poll_ms,
                            bool(media_url),
                        )
                    if status_l in {"succeeded", "success", "completed", "done"} or (not status_l and media_url):
                        if media_url:
                            logger.info("[GrsaiTrace][%s] completed | task_id=%s poll_idx=%s media_url=%s", trace_id, task_id, i + 1, media_url)
                            meta = {"raw": p_data}
                            if extra_metadata:
                                meta.update(extra_metadata)
                            return {"url": media_url, "metadata": meta}
                    elif status_l in {"failed", "error", "canceled", "cancelled"}:
                        print(f"[Grsai] Task Failed: {p_data}")
                        if self._is_grsai_quota_or_throttle_error(p_data):
                            logger.error("[GrsaiTrace][%s] task throttled_or_quota | task_id=%s poll_idx=%s detail=%s", trace_id, task_id, i + 1, str(p_data)[:1000])
                            return {
                                "error": "Veo/Grsai 配额或频率受限",
                                "details": "任务失败原因为 429 RESOURCE_EXHAUSTED（上传图片或生成请求被限流/额度不足）。请稍后重试或调整账号配额。",
                            }
                        logger.error("[GrsaiTrace][%s] task failed | task_id=%s poll_idx=%s detail=%s", trace_id, task_id, i + 1, str(p_data)[:1000])
                        return {"error": "Generation Failed", "details": p_data}
                else:
                    print(f"[Grsai] Poll Failed {p_resp.status_code}: {p_resp.text}")
                    logger.warning(
                        "[GrsaiTrace][%s] poll non_200 | task_id=%s poll_idx=%s status=%s elapsed_ms=%s body_preview=%s",
                        trace_id,
                        task_id,
                        i + 1,
                        p_resp.status_code,
                        poll_ms,
                        (p_resp.text or "")[:300],
                    )

            last_error = "Timeout"
            logger.error("[GrsaiTrace][%s] task timeout | task_id=%s", trace_id, task_id)

        if last_error:
            logger.error("[GrsaiTrace][%s] all upstream failed | last_error=%s", trace_id, last_error)
            return {"error": "Grsai request failed", "details": last_error}
        logger.error("[GrsaiTrace][%s] all upstream failed | no last_error", trace_id)
        return {"error": "Grsai request failed", "details": "All upstream endpoints failed"}

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
                
            out = io.BytesIO()
            img.save(out, format='PNG')
            b64_final = base64.b64encode(out.getvalue()).decode('utf-8')
            return f"data:image/png;base64,{b64_final}"
            
        except Exception as e:
            print(f"[Veo] Image Process Error: {e}")
            import traceback
            traceback.print_exc()
            return ""

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
                b64 = base64.b64encode(data).decode("utf-8")
                if force_data_uri: return f"data:{mime};base64,{b64}"
                return b64
            else:
                print(f"[MediaService] Error: No Data retrieved for {url_or_path}")
        except Exception as e:
            print(f"[MediaService] Exception in Base64 Conversion: {e}")
        
        return url_or_path # Return original if fail

media_service = MediaGenerationService()

