# -*- coding: utf-8 -*-
"""Knowledge-base ingest: web search + LLM structured extraction (P2)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models.all_models import KbEntry, KbWork, User
from app.services.billing_service import billing_service
from app.services.llm_service import llm_service
from app.services.model_invocation_billing import _reservation_tx_id
from app.services.story_generator_llm import _normalize_llm_json_object
from app.services.story_trend_search_service import _collect_search_snippets_for_queries

logger = logging.getLogger("api_logger")

KB_CATEGORIES = {"portrait", "costume", "scenery", "plot"}
PLOT_SUBTYPES = {"trope", "dialogue", "action"}

CATEGORY_HINTS = {
    "portrait": "角色肖像/定妆/脸型气质/经典造型参考",
    "costume": "服饰/戏服/材质配饰/时代造型参考",
    "scenery": "美景/场景空间/空镜氛围/取景参考",
    "plot": "经典桥段/对白范本/动作调度节拍参考",
}


def build_kb_search_queries(
    *,
    category: str,
    topic: str,
    work_title: Optional[str] = None,
    language: str = "zh",
) -> List[str]:
    topic = str(topic or "").strip()
    work = str(work_title or "").strip()
    cat = str(category or "").strip().lower()
    hint = CATEGORY_HINTS.get(cat, "创作参考")
    base = f"{work} {topic}".strip() if work else topic
    if not base:
        return []

    if language.lower().startswith("en"):
        templates = {
            "portrait": [
                f"{base} iconic character look costume design film",
                f"{base} classic portrait styling cinema character",
                f"{base} character visual design makeup wardrobe",
            ],
            "costume": [
                f"{base} costume design film wardrobe",
                f"{base} iconic outfit fashion in movie series",
                f"{base} period costume fabric accessories screen",
            ],
            "scenery": [
                f"{base} iconic film location scenery empty shot",
                f"{base} cinematic environment set design atmosphere",
                f"{base} famous movie landscape establishing shot",
            ],
            "plot": [
                f"{base} classic trope dialogue scene film",
                f"{base} iconic dialogue exchange movie",
                f"{base} action choreography set piece cinema",
            ],
        }
    else:
        templates = {
            "portrait": [
                f"{base} 经典角色造型 定妆 肖像",
                f"{base} 电影剧集 角色外形 气质参考",
                f"{base} {hint} 名场面人物造型",
            ],
            "costume": [
                f"{base} 服饰 戏服 服装设计",
                f"{base} 造型 材质 配饰 影视",
                f"{base} {hint} 经典穿搭",
            ],
            "scenery": [
                f"{base} 场景 取景 美景 空镜",
                f"{base} 电影场景 空间氛围 建立镜头",
                f"{base} {hint} 经典环境",
            ],
            "plot": [
                f"{base} 经典桥段 名场面",
                f"{base} 经典对白 对话场面",
                f"{base} 动作戏 调度 节拍",
            ],
        }
    return list(templates.get(cat) or [
        f"{base} {hint}",
        f"{base} 经典流行作品 参考",
    ])


def _format_snippets_for_prompt(snippets: List[Dict[str, Any]], *, limit: int = 18) -> str:
    lines: List[str] = []
    for idx, item in enumerate((snippets or [])[:limit], start=1):
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or item.get("body") or item.get("content") or "").strip()
        lines.append(f"[{idx}] {title}\nURL: {url}\n{snippet}")
    return "\n\n".join(lines).strip()


def _build_extract_system_prompt(category: str, language: str) -> str:
    subtype_rule = (
        'For category "plot", each entry MUST include plot_subtype as one of: trope, dialogue, action.'
        if category == "plot"
        else 'For non-plot categories, set plot_subtype to null.'
    )
    lang = "Chinese" if not str(language or "").lower().startswith("en") else "English"
    return f"""You are a knowledge-base curator for film/TV/short-drama creative references.
Extract high-quality reusable reference entries for category="{category}".
{subtype_rule}

Rules:
1) Use ONLY the provided source evidence. Do not invent plot facts or private bios.
2) Prefer classic/popular works that creators can reuse as style/structure references.
3) Each entry needs concrete, searchable body_text (visual details / beat / dialogue points).
4) Mark uncertain items briefly in copyright_note.
5) Output language: {lang}.
6) Return STRICT JSON object only:
{{
  "entries": [
    {{
      "title": "string",
      "summary": "string",
      "body_text": "string",
      "tags": ["string"],
      "style_keywords": ["string"],
      "plot_subtype": "trope|dialogue|action|null",
      "work_title": "string|null",
      "work_year": "string|null",
      "source_url": "string|null",
      "copyright_note": "string|null",
      "license_tier": "reference_ok|restricted"
    }}
  ]
}}
"""


def _normalize_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _find_or_create_work(
    db: Session,
    *,
    title: Optional[str],
    year: Optional[str],
    user_id: int,
) -> Optional[int]:
    work_title = str(title or "").strip()
    if not work_title:
        return None
    existing = (
        db.query(KbWork)
        .filter(KbWork.is_deleted.is_(False), KbWork.title == work_title)
        .order_by(KbWork.id.desc())
        .first()
    )
    if existing:
        if year and not existing.year:
            existing.year = str(year).strip()
            existing.updated_at = now_bj_iso()
        return int(existing.id)
    now = now_bj_iso()
    row = KbWork(
        title=work_title,
        year=(str(year).strip() if year else None),
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    return int(row.id)


def persist_extracted_entries(
    db: Session,
    *,
    category: str,
    extracted: List[Dict[str, Any]],
    user_id: int,
    source_type: str,
    default_work_title: Optional[str] = None,
    default_work_year: Optional[str] = None,
    source_meta: Optional[Dict[str, Any]] = None,
    max_entries: int = 8,
) -> List[KbEntry]:
    created: List[KbEntry] = []
    now = now_bj_iso()
    for raw in (extracted or [])[: max(1, int(max_entries or 8))]:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        plot_subtype = str(raw.get("plot_subtype") or "").strip().lower() or None
        if category != "plot":
            plot_subtype = None
        elif plot_subtype not in PLOT_SUBTYPES:
            plot_subtype = "trope"

        work_title = str(raw.get("work_title") or default_work_title or "").strip() or None
        work_year = str(raw.get("work_year") or default_work_year or "").strip() or None
        work_id = _find_or_create_work(db, title=work_title, year=work_year, user_id=user_id)

        license_tier = str(raw.get("license_tier") or "reference_ok").strip().lower()
        if license_tier not in {"public_domain", "reference_ok", "fair_use_ref", "restricted", "blocked"}:
            license_tier = "reference_ok"

        entry = KbEntry(
            work_id=work_id,
            category=category,
            plot_subtype=plot_subtype,
            title=title,
            summary=(str(raw.get("summary") or "").strip() or None),
            body_text=(str(raw.get("body_text") or "").strip() or None),
            tags=_normalize_list(raw.get("tags")),
            style_keywords=_normalize_list(raw.get("style_keywords")),
            license_tier=license_tier,
            copyright_note=(str(raw.get("copyright_note") or "").strip() or None),
            source_type=source_type,
            source_url=(str(raw.get("source_url") or "").strip() or None),
            source_meta=dict(source_meta or {}),
            review_status="pending",
            index_status="none",
            created_by_user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        db.add(entry)
        created.append(entry)
    db.commit()
    for row in created:
        db.refresh(row)
    return created


async def _run_extract_llm(
    db: Session,
    *,
    current_user: User,
    system_prompt: str,
    user_prompt: str,
    system_api_id: Optional[int] = None,
    billing_item: str = "kb_ingest",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    from app.services.agent_service import agent_service
    from app.services.script_analysis_llm_config import _resolve_story_generator_script_analysis_llm_config

    llm_config = None
    if system_api_id:
        try:
            llm_config = _resolve_story_generator_script_analysis_llm_config(
                db,
                int(current_user.id),
                function_name="script_analysis",
                system_api_id=system_api_id,
                context="kb_ingest",
                project_global_info=None,
            )
        except Exception as exc:
            logger.warning("KB ingest system_api_id resolve failed: %s", exc)
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        llm_config = agent_service.get_active_llm_config(int(current_user.id), category="LLM")
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured")

    cfg = dict(llm_config.get("config") or {})
    cfg.setdefault("response_format", {"type": "json_object"})
    llm_config = {**llm_config, "config": cfg}
    provider = llm_config.get("provider")
    model = llm_config.get("model")

    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "llm_chat",
            provider,
            model,
            {
                "item": billing_item,
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    try:
        resp = await llm_service.generate_content_with_fallback(user_prompt, system_prompt, llm_config)
    except Exception as exc:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(exc))
        raise

    raw = str((resp or {}).get("content") or "").strip()
    if not raw:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = (resp or {}).get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
            ],
            output_ratio=1.0,
        )
    details = {
        "item": billing_item,
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
    }
    details["total_tokens"] = details["prompt_tokens"] + details["completion_tokens"]
    details["input_tokens"] = details["prompt_tokens"]
    details["output_tokens"] = details["completion_tokens"]
    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), details)
    else:
        try:
            billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, details)
        except Exception as exc:
            logger.warning("KB ingest charge failed: %s", exc)

    data = _normalize_llm_json_object(raw, context="kb_ingest")
    return data, {"provider": provider, "model": model, "usage": details}


async def ingest_from_web(
    db: Session,
    *,
    current_user: User,
    category: str,
    topic: str,
    work_title: Optional[str] = None,
    work_year: Optional[str] = None,
    language: str = "zh",
    max_entries: int = 6,
    system_api_id: Optional[int] = None,
) -> Dict[str, Any]:
    cat = str(category or "").strip().lower()
    if cat not in KB_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    topic_text = str(topic or "").strip()
    if not topic_text:
        raise HTTPException(status_code=400, detail="topic is required")

    queries = build_kb_search_queries(
        category=cat,
        topic=topic_text,
        work_title=work_title,
        language=language,
    )
    search_bundle = await _collect_search_snippets_for_queries(
        queries,
        limit_per_query=6,
        max_enrich_per_query=2,
        require_informative_snippet=False,
        report_kind=f"kb_ingest_{cat}",
    )
    snippets = list(search_bundle.get("snippets") or [])
    if not snippets:
        raise HTTPException(status_code=502, detail="Web search returned no snippets")

    evidence = _format_snippets_for_prompt(snippets)
    sys_prompt = _build_extract_system_prompt(cat, language)
    user_prompt = (
        f"Category: {cat}\n"
        f"Topic: {topic_text}\n"
        f"Preferred work: {work_title or '(none)'}\n"
        f"Max entries: {max(1, min(int(max_entries or 6), 12))}\n\n"
        f"SOURCE EVIDENCE:\n{evidence}\n\n"
        f"Extract reusable knowledge-base entries now."
    )
    data, llm_meta = await _run_extract_llm(
        db,
        current_user=current_user,
        system_prompt=sys_prompt,
        user_prompt=user_prompt,
        system_api_id=system_api_id,
        billing_item="kb_ingest_web",
    )
    entries_raw = data.get("entries") if isinstance(data.get("entries"), list) else []
    source_meta = {
        "ingest_mode": "web",
        "topic": topic_text,
        "queries": queries,
        "snippet_count": len(snippets),
        "source_stats": search_bundle.get("source_stats") or {},
        "urls": [str(s.get("url") or "") for s in snippets[:12] if s.get("url")],
        "llm": llm_meta,
    }
    created = persist_extracted_entries(
        db,
        category=cat,
        extracted=entries_raw,
        user_id=int(current_user.id),
        source_type="web",
        default_work_title=work_title,
        default_work_year=work_year,
        source_meta=source_meta,
        max_entries=max_entries,
    )
    if not created:
        raise HTTPException(status_code=500, detail="LLM produced no usable entries")
    return {
        "ok": True,
        "created_count": len(created),
        "entry_ids": [int(e.id) for e in created],
        "search_meta": {
            "query_count": len(queries),
            "snippet_count": len(snippets),
            "source_stats": search_bundle.get("source_stats") or {},
        },
        "llm": llm_meta,
    }


async def ingest_from_text(
    db: Session,
    *,
    current_user: User,
    category: str,
    source_text: str,
    work_title: Optional[str] = None,
    work_year: Optional[str] = None,
    language: str = "zh",
    max_entries: int = 6,
    system_api_id: Optional[int] = None,
) -> Dict[str, Any]:
    cat = str(category or "").strip().lower()
    if cat not in KB_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    text = str(source_text or "").strip()
    if len(text) < 20:
        raise HTTPException(status_code=400, detail="source_text is too short")

    sys_prompt = _build_extract_system_prompt(cat, language)
    user_prompt = (
        f"Category: {cat}\n"
        f"Preferred work: {work_title or '(none)'}\n"
        f"Max entries: {max(1, min(int(max_entries or 6), 12))}\n\n"
        f"SOURCE TEXT:\n{text[:12000]}\n\n"
        f"Extract reusable knowledge-base entries now."
    )
    data, llm_meta = await _run_extract_llm(
        db,
        current_user=current_user,
        system_prompt=sys_prompt,
        user_prompt=user_prompt,
        system_api_id=system_api_id,
        billing_item="kb_ingest_llm",
    )
    entries_raw = data.get("entries") if isinstance(data.get("entries"), list) else []
    source_meta = {
        "ingest_mode": "llm",
        "source_chars": len(text),
        "llm": llm_meta,
    }
    created = persist_extracted_entries(
        db,
        category=cat,
        extracted=entries_raw,
        user_id=int(current_user.id),
        source_type="llm",
        default_work_title=work_title,
        default_work_year=work_year,
        source_meta=source_meta,
        max_entries=max_entries,
    )
    if not created:
        raise HTTPException(status_code=500, detail="LLM produced no usable entries")
    return {
        "ok": True,
        "created_count": len(created),
        "entry_ids": [int(e.id) for e in created],
        "llm": llm_meta,
    }
