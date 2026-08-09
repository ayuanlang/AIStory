# -*- coding: utf-8 -*-
"""Knowledge-base vision helpers: caption media + image-query → text for RAG."""
from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import os
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.all_models import KbEntryMedia, SystemAPISetting, User
from app.services.billing_service import billing_service
from app.services.llm_service import llm_service
from app.services.model_invocation_billing import _reservation_tx_id
from app.services.system_default_api_service import get_task_default_system_setting

logger = logging.getLogger("api_logger")

KB_CAPTION_PROMPT = """你是影视视觉资料编目员。请用简洁中文描述这张参考图，便于后续语义检索。
输出要求（纯文本，不要 JSON）：
1) 第一行：一句话总览（主体+场景+气质）
2) 随后用分号分隔关键词：人物/服饰/环境/构图/光线/色调/时代感/情绪
3) 不要编造片名或演员名；看不清就写「不清晰」
4) 总长度控制在 120–220 字。"""

KB_QUERY_PROMPT = """你是检索查询改写助手。用户上传了一张参考图，请把它改写成适合知识库混合检索的查询文本。
输出纯文本（不要 JSON）：
- 先写 1 句核心视觉意图
- 再列 8–15 个检索关键词（中文为主，可夹少量英文风格词）
- 覆盖：主体类型、服饰/妆造、场景母题、构图、光线、色调、情绪氛围
- 不要编造作品名；看不清处略过
- 总长度 80–180 字。"""


def _pick_api_key(raw: Optional[str]) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    for part in text.replace("\n", ",").split(","):
        key = part.strip()
        if key:
            return key
    return ""


def resolve_kb_vision_setting(db: Session) -> Optional[SystemAPISetting]:
    for category in ("Vision", "vision", "LLM", "llm"):
        row = get_task_default_system_setting(db, category)
        if row and _pick_api_key(getattr(row, "api_key", None)) and str(getattr(row, "model", "") or "").strip():
            return row
    return None


def vision_config_from_setting(setting: SystemAPISetting) -> Dict[str, Any]:
    return {
        "provider": str(getattr(setting, "provider", "") or "").strip(),
        "api_key": _pick_api_key(getattr(setting, "api_key", None)),
        "base_url": str(getattr(setting, "base_url", "") or "").strip(),
        "model": str(getattr(setting, "model", "") or "").strip(),
        "config": getattr(setting, "config", None) if isinstance(getattr(setting, "config", None), dict) else {},
    }


def _guess_mime(path_or_name: str) -> str:
    mime, _ = mimetypes.guess_type(path_or_name)
    if mime and mime.startswith("image/"):
        return mime
    ext = os.path.splitext(path_or_name)[1].lower()
    return {
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext, "image/jpeg")


def file_bytes_to_data_url(raw: bytes, *, filename: str = "query.jpg") -> str:
    mime = _guess_mime(filename)
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def resolve_image_url_for_vision(db: Session, image_url: str) -> str:
    """Make image reachable by remote vision APIs (base64 for localhost /uploads)."""
    url = str(image_url or "").strip()
    if not url:
        return ""
    if url.startswith("data:image"):
        return url

    base_url = (settings.RENDER_EXTERNAL_URL or "http://localhost:8000").rstrip("/")
    if url.startswith("/"):
        url = f"{base_url}{url}"

    needs_local = any(token in url for token in ("localhost", "127.0.0.1", "/uploads/"))
    if not needs_local and url.startswith("http"):
        return url

    relative = url
    for prefix in (base_url, "http://localhost:8000", "https://localhost:8000"):
        if relative.startswith(prefix):
            relative = relative[len(prefix) :]
            break
    if relative.startswith("/"):
        relative = relative[1:]
    rel_no_uploads = relative.replace("uploads/", "", 1) if relative.startswith("uploads/") else relative
    candidates = [
        os.path.join(settings.UPLOAD_DIR, rel_no_uploads),
        os.path.join(settings.UPLOAD_DIR, relative),
        os.path.join(getattr(settings, "BASE_DIR", ""), relative),
        relative,
    ]
    for path in candidates:
        if path and os.path.exists(path) and os.path.isfile(path):
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()
                if raw:
                    return file_bytes_to_data_url(raw, filename=path)
            except Exception as exc:
                logger.warning("KB vision local encode failed path=%s err=%s", path, exc)
    return url


async def describe_image_for_kb(
    db: Session,
    *,
    current_user: User,
    image_url: str,
    prompt: str,
    billing_item: str = "kb_vision",
) -> Tuple[str, Dict[str, Any]]:
    setting = resolve_kb_vision_setting(db)
    if not setting:
        raise HTTPException(status_code=400, detail="No Vision/LLM system default configured for KB image retrieval")
    llm_config = vision_config_from_setting(setting)
    provider = str(llm_config.get("provider") or "").strip() or "system"
    model = str(llm_config.get("model") or "").strip()
    if not model or not llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="Vision/LLM API key or model missing")

    vision_url = resolve_image_url_for_vision(db, image_url)
    if not vision_url:
        raise HTTPException(status_code=400, detail="image_url is required")

    reservation_tx = None
    if billing_service.is_token_pricing(db, "analysis", provider, model):
        est_messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": vision_url[:80] + "…"}},
                ],
            }
        ]
        est = billing_service.estimate_reserve_tokens_from_messages(est_messages)
        est_input = int(est.get("input_tokens", 0) or 0) + 1000
        est_output = int(max(est_input * float(billing_service.RESERVE_OUTPUT_RATIO), 200))
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "analysis",
            provider,
            model,
            {
                "item": billing_item,
                "estimation_method": "prompt_tokens_ratio",
                "estimated_image_tokens": 1000,
                "input_tokens": est_input,
                "output_tokens": est_output,
                "total_tokens": est_input + est_output,
            },
        )
    else:
        cost = billing_service.estimate_cost(db, "analysis", provider, model)
        billing_service.check_can_proceed(current_user, cost)

    try:
        response_data = await llm_service.analyze_multimodal(
            prompt=prompt,
            image_url=vision_url,
            config=llm_config,
        )
    except Exception as exc:
        if reservation_tx is not None:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(exc))
        raise

    content = str((response_data or {}).get("content") or "").strip()
    if not content or content.lower().startswith("error:"):
        if reservation_tx is not None:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), content or "empty")
        raise HTTPException(status_code=502, detail=content or "Vision model returned empty content")

    usage = (response_data or {}).get("usage") or {}
    details = {
        "item": billing_item,
        "provider": provider,
        "model": model,
        "input_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 1200),
        "output_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 200),
    }
    details["total_tokens"] = int(details["input_tokens"] + details["output_tokens"])
    if reservation_tx is not None:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), details)
    else:
        billing_service.deduct_credits(db, current_user.id, "analysis", provider, model, details)

    meta = {
        "provider": provider,
        "model": model,
        "usage": usage,
    }
    return content, meta


async def caption_kb_media(
    db: Session,
    *,
    current_user: User,
    media: KbEntryMedia,
    force: bool = False,
) -> Optional[str]:
    if str(getattr(media, "media_type", "") or "") != "image":
        return None
    existing = str(getattr(media, "caption", "") or "").strip()
    if existing and not force:
        return existing
    url = str(getattr(media, "url", "") or "").strip()
    if not url:
        return None
    text, meta = await describe_image_for_kb(
        db,
        current_user=current_user,
        image_url=url,
        prompt=KB_CAPTION_PROMPT,
        billing_item="kb_media_caption",
    )
    media.caption = text
    info = dict(media.meta_info or {})
    info["vision_caption"] = {
        "model": meta.get("model"),
        "provider": meta.get("provider"),
    }
    media.meta_info = info
    db.add(media)
    db.commit()
    db.refresh(media)
    return text


def caption_kb_media_background(media_id: int, user_id: int, *, force: bool = False) -> None:
    from app.db.session import SessionLocal
    from app.models.all_models import User as UserModel
    from app.services.kb_rag_service import rebuild_entry_index

    db = SessionLocal()
    try:
        media = (
            db.query(KbEntryMedia)
            .filter(KbEntryMedia.id == int(media_id), KbEntryMedia.is_deleted.is_(False))
            .first()
        )
        user = db.query(UserModel).filter(UserModel.id == int(user_id)).first()
        if not media or not user:
            return
        asyncio.run(caption_kb_media(db, current_user=user, media=media, force=force))
        entry = media.entry
        if entry and str(getattr(entry, "review_status", "") or "") == "approved":
            rebuild_entry_index(db, int(entry.id))
    except Exception:
        logger.exception("KB media caption background failed media_id=%s", media_id)
    finally:
        db.close()
