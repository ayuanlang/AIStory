# -*- coding: utf-8 -*-
"""Extract reference-plot keywords, then let the generation call search them."""
from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.billing_service import billing_service
from app.services.db_session_utils import _release_db_connection
from app.services.model_invocation_billing import (
    _apply_llm_routing_to_billing_details,
    _reservation_tx_id,
)

logger = logging.getLogger("api_logger")

_SOURCE_CHAR_LIMIT = 12000
_EMPTY_KEYWORDS: Dict[str, List[str]] = {
    "works": [],
    "plot_keywords": [],
    "queries": [],
}
_STAGE_LABEL = {
    "framework": "剧本框架",
    "outline": "分集大纲",
    "episode": "剧本生成",
}
_SEARCH_OPEN = (
    "搜索保持开放。这些关键字是入口，不是封闭名单。"
    "重点补当前模型训练集里可能没有的新内容：近年新出现的经典，以及正在流行的影视、游戏、文学和短剧。"
    "顺着入口再往外搜同类新作品和新场面，不要只用训练集里已经熟悉的旧名片把检索填满。"
    "搜到的新内容按本阶段的侧重取用，符合本剧背景和主题后再改写。不抄人名、地名和原句。"
)
_STAGE_FOCUS = {
    "framework": (
        "搜索保持开放，侧重整体架构，用来补训练集里可能没有的新经典和流行作品。"
        "抽整部怎么起、怎么加压、价值怎么转到反面、危机怎么把选择逼出来、怎么收束。"
        "关键字只写结构功能，不写对白原句、动作招式、表情或某一场的细节。"
        "作品种子优先近年新出现的经典和正在流行的作品，再留开放查询去搜更多新架构。"
    ),
    "outline": (
        "搜索保持开放，侧重整体架构如何分成连续的集，用来补训练集里可能没有的新经典和流行作品。"
        "抽每一段承接上一段的哪一截结构、转折落在哪一段、这一段的出怎样打开下一段。"
        "关键字只写分集架构，不写某一场的对白、动作或表情。"
        "不抄框架已经锁死的那一部当唯一答案。来源是近年文学作品、影视、游戏和正在流行的连续叙事。"
    ),
    "episode": (
        "搜索保持开放，侧重这一集每一场可演的细节，用来补训练集里可能没有的新经典和流行内容。不把整部架构再搜一遍。"
        "四样都要能检索到：对白细节、动作细节、表情驱动、具体剧情的驱动细节。"
        "对白写怎么顶、怎么接、怎么留白。动作写这一下怎么起、怎么落到下一状态。"
        "表情写眉、眼、嘴和微动作怎么把下一步逼出来。剧情驱动写这一下凭什么让因为、所以、但是发生。"
        "按这一场的场景留开放查询，去搜近年新片、热播和流行短剧里的同类细节。大纲那一部和这场对不上就换。"
        "不写原句，不写原招的外形。"
    ),
}
_STAGE_KEYS = {
    "framework": (
        "works：字符串数组，能对上本剧整体架构的真实作品名，最多 6 部。优先近年新经典和正在流行的作品，不要用几部老名片占满。\n"
        "plot_keywords：字符串数组，整体架构功能，最多 8 条。只写起势、加压、价值转向、危机抉择、收束。不要对白、动作招式或表情。\n"
        "queries：字符串数组，短查询，最多 6 条。至少 4 条不点死一部旧作，写成「近年或热播或流行 + 类型或场面 + 结构或架构」，用来搜出训练集里可能没有的新架构。其余可以带一部近年作品名。"
    ),
    "outline": (
        "works：字符串数组，和本剧分集架构同类的真实作品名，最多 6 部。优先近年新经典和正在流行的连续叙事，不要只重复框架主框架，也不要用老名片占满。\n"
        "plot_keywords：字符串数组，分集架构功能，最多 8 条。只写段与段怎么接、转折落在哪一段、钩子怎么打开下一段。不要某一场的对白、动作或表情。\n"
        "queries：字符串数组，短查询，最多 6 条。至少 4 条不点死一部旧作，写成「近年或热播或流行 + 类型 + 分集或结构」，用来搜出新的分集架构。其余可以带一部近年作品名。"
    ),
    "episode": (
        "works：字符串数组，和这一场场面同类的真实作品名，最多 6 部。优先近年新片、热播和流行短剧。对不上这场就换。不要用老名片占满。\n"
        "plot_keywords：字符串数组，这场的可演细节，最多 8 条。必须能分开检索这四样：对白细节、动作细节、表情驱动、具体剧情的驱动细节。不要整部架构，不要原句。\n"
        "queries：字符串数组，短查询，最多 6 条。至少 4 条不点死一部旧作，分别落到「对白」「动作」「表情」「剧情驱动」，并带上近年、新片、热播或流行短剧，用来搜出新的可演细节。其余可以带一部近年作品名。"
    ),
}
_STAGE_SEARCH_USE = {
    "framework": (
        "搜索侧重整体架构。用这些关键字检索整部怎么起、怎么加压、价值怎么转向、危机怎么逼出选择、怎么收束。"
        "只把检索到的结构功能转译进本剧因果骨架。"
        "不要用这次搜索去找对白原句、动作招式或表情。"
        "可以参考检索到的架构，必须符合本剧背景和主题，按本剧因果融合。不抄人名、地名和原句。"
    ),
    "outline": (
        "搜索侧重整体架构如何分成连续的集。用这些关键字检索每一段承接哪一截结构、转折落在哪一段、这一段的出怎样打开下一段。"
        "只把检索到的分集架构转译进本剧的集与集。"
        "不要用这次搜索去找某一场的对白、动作或表情。"
        "基本点仍按本集场面另选。可以参考检索到的架构，必须符合本剧背景和主题。不抄人名、地名和原句。"
    ),
    "episode": (
        "搜索侧重这一场可演的细节，不把整部架构再搜一遍。"
        "用这些关键字分别检索四样：对白细节、动作细节、表情驱动、具体剧情的驱动细节。"
        "对白只借怎么顶、怎么接、怎么留白。动作只借这一下怎么起、怎么落到下一状态。"
        "表情只借眉、眼、嘴和微动作怎么把下一步逼出来。剧情驱动只借这一下凭什么让因为、所以、但是发生。"
        "先对上角色的情感冲突和这一场的剧情，再按背景、实际剧情、角色特征改写。"
        "可以参考检索到的细节，必须符合本剧背景和主题，按本剧因果融合。不抄人名、地名、原句和原招外形。"
    ),
}


def _extract_system(stage: str) -> str:
    keys = _STAGE_KEYS.get(str(stage or "").strip()) or (
        "works：字符串数组，真实作品名，最多 6 部。\n"
        "plot_keywords：字符串数组，可检索的剧情功能，最多 8 条。不写原句。\n"
        "queries：字符串数组，短查询，最多 6 条。每条带作品名或剧情功能。"
    )
    return (
        "你是剧情借鉴检索员。只输出一个 JSON 对象，不要 markdown，不要解释。\n"
        "搜索要开放，用来补当前模型训练集里可能没有的新经典和正在流行的内容。关键字是入口，不是封闭名单。\n"
        "键只用这三个：\n"
        f"{keys}\n"
        "没有把握的新名字不要编。材料里没有可借鉴的点时，三个数组都用 []。"
    )
_LIST_LIMIT = {"works": 6, "plot_keywords": 8, "queries": 6}
_LIST_ALIASES = {
    "works": ("works", "reference_works", "作品", "作品名"),
    "plot_keywords": ("plot_keywords", "keywords", "剧情关键字", "关键字"),
    "queries": ("queries", "search_queries", "检索", "搜索"),
}


def empty_reference_plot_keywords() -> Dict[str, List[str]]:
    return {key: [] for key in _EMPTY_KEYWORDS}


def _clip_source(text: str) -> str:
    source = str(text or "").strip()
    if len(source) <= _SOURCE_CHAR_LIMIT:
        return source
    return source[:_SOURCE_CHAR_LIMIT]


def _as_keyword_list(value: Any, *, limit: int) -> List[str]:
    if isinstance(value, str):
        parts = re.split(r"[;\n；、|]", value)
    elif isinstance(value, list):
        parts = value
    else:
        return []
    out: List[str] = []
    for item in parts:
        text = " ".join(str(item or "").split()).strip()
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _json_object_from_text(raw: str) -> Optional[Dict[str, Any]]:
    text = str(raw or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except Exception:
            return None
    return parsed if isinstance(parsed, dict) else None


def parse_reference_plot_keywords(raw: str) -> Dict[str, List[str]]:
    data = _json_object_from_text(raw) or {}
    parsed = empty_reference_plot_keywords()
    for key, aliases in _LIST_ALIASES.items():
        value = None
        for alias in aliases:
            if alias in data:
                value = data.get(alias)
                break
        parsed[key] = _as_keyword_list(value, limit=_LIST_LIMIT[key])
    return parsed


def format_reference_plot_block(keywords: Dict[str, Any], *, stage: str) -> str:
    works = _as_keyword_list((keywords or {}).get("works"), limit=_LIST_LIMIT["works"])
    plots = _as_keyword_list((keywords or {}).get("plot_keywords"), limit=_LIST_LIMIT["plot_keywords"])
    queries = _as_keyword_list((keywords or {}).get("queries"), limit=_LIST_LIMIT["queries"])
    if not works and not plots and not queries:
        return ""
    label = _STAGE_LABEL.get(str(stage or "").strip(), str(stage or "").strip() or "本阶段")
    lines = [
        "【借鉴剧情检索】",
        (
            f"阶段={label}。这些关键字已经抽好。"
            "提交这一次时，若模型带搜索，就用这些关键字同时检索，不要另等一份检索稿。"
        ),
        _SEARCH_OPEN,
        _STAGE_SEARCH_USE.get(
            str(stage or "").strip(),
            "用这些关键字在本次提交里检索。可以参考检索到的剧情，必须符合本剧背景和主题，按本剧因果融合。不抄人名、地名和原句。",
        ),
    ]
    if works:
        lines.append("作品=" + "；".join(works))
    if plots:
        lines.append("剧情关键字=" + "；".join(plots))
    if queries:
        lines.append("检索=" + "；".join(queries))
    return "\n".join(lines).strip() + "\n"


def keywords_have_terms(keywords: Dict[str, Any]) -> bool:
    return bool(format_reference_plot_block(keywords, stage="framework"))


def _model_is_gemini_text(model: Any) -> bool:
    name = str(model or "").strip().lower()
    if "gemini" not in name:
        return False
    blocked = ("image", "omni", "tts", "video", "audio", "embedding")
    return not any(token in name for token in blocked)


def _explicit_search_enabled(extra_config: Dict[str, Any]) -> bool:
    if extra_config.get("has_google_search") or extra_config.get("web_search"):
        return True
    text_caps = extra_config.get("text_capabilities")
    if not isinstance(text_caps, dict):
        return False
    return any(bool(text_caps.get(key)) for key in ("web_search", "google_search", "has_google_search"))


def search_tools_for_submission(
    provider: Any,
    model: Any,
    extra_config: Optional[Dict[str, Any]],
    transport: str = "",
) -> List[Dict[str, Any]]:
    """Tool payload for this submission. Gemini searches even without an admin flag."""
    cfg = extra_config if isinstance(extra_config, dict) else {}
    if not cfg.get("__reference_plot_search"):
        return []
    gemini = _model_is_gemini_text(model)
    if not gemini and not _explicit_search_enabled(cfg):
        return []
    transport_text = str(transport or "").strip().lower()
    if gemini and transport_text == "gemini":
        return [{"googleSearch": {}}]
    if gemini:
        return [{"google_search": {}}]
    provider_text = str(provider or "").strip().lower()
    model_text = str(model or "").strip().lower()
    if "claude" in model_text or provider_text in {"anthropic", "claude"} or transport_text == "claude":
        return [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]
    return [{"type": "web_search"}]


def apply_reference_plot_search_tools(
    payload: Dict[str, Any],
    *,
    provider: Any,
    model: Any,
    extra_config: Optional[Dict[str, Any]],
    transport: str = "",
) -> Dict[str, Any]:
    tools = search_tools_for_submission(provider, model, extra_config, transport=transport)
    if not tools or not isinstance(payload, dict):
        return payload
    existing = payload.get("tools")
    merged: List[Any] = list(existing) if isinstance(existing, list) else []
    blob = json.dumps(merged, ensure_ascii=False).lower()
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_type = str(tool.get("type") or "").strip().lower()
        tool_key = next(iter(tool), "")
        if tool_type and tool_type in blob:
            continue
        if tool_key and str(tool_key).lower() in blob:
            continue
        merged.append(tool)
    if merged:
        payload["tools"] = merged
    return payload


def search_tool_was_rejected(error: BaseException) -> bool:
    text = str(error or "").lower()
    if not text:
        return False
    mentions_search = any(
        token in text
        for token in ("google_search", "googlesearch", "web_search", "\"tools\"", "tools")
    )
    rejected = any(
        token in text
        for token in ("400", "422", "invalid", "unsupported", "unknown", "not supported", "unrecognized", "unexpected")
    )
    return mentions_search and rejected


def attach_reference_plot_search(
    llm_config: Optional[Dict[str, Any]],
    keywords: Dict[str, Any],
) -> Dict[str, Any]:
    bound = copy.deepcopy(llm_config) if isinstance(llm_config, dict) else {}
    inner = dict(bound.get("config") or {}) if isinstance(bound.get("config"), dict) else {}
    queries = _as_keyword_list((keywords or {}).get("queries"), limit=_LIST_LIMIT["queries"])
    inner["__reference_plot_search"] = keywords_have_terms(keywords or {})
    inner["__reference_plot_queries"] = queries
    bound["config"] = inner
    return bound


def _billing_details(item: str, usage: Dict[str, Any], resp: Dict[str, Any]) -> Dict[str, Any]:
    prompt_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
    completion_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
    total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
    details = {
        "item": item,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
    }
    _apply_llm_routing_to_billing_details(details, resp)
    return details


async def extract_reference_plot_keywords(
    *,
    db: Optional[Session],
    user_id: int,
    llm_config: Optional[Dict[str, Any]],
    stage: str,
    source_text: str,
    billing_item: str,
) -> Dict[str, List[str]]:
    """One short call before the stage. Failure leaves the stage free to continue."""
    source = _clip_source(source_text)
    if not source:
        return empty_reference_plot_keywords()
    if not isinstance(llm_config, dict) or not str(llm_config.get("api_key") or "").strip():
        logger.warning("[reference_plot] skip stage=%s reason=no_llm_config", stage)
        return empty_reference_plot_keywords()

    extract_cfg = copy.deepcopy(llm_config)
    inner = dict(extract_cfg.get("config") or {}) if isinstance(extract_cfg.get("config"), dict) else {}
    inner["__reference_plot_search"] = False
    inner.pop("tools", None)
    inner["__resolved_action"] = "借鉴剧情关键字"
    extract_cfg["config"] = inner

    stage_key = str(stage or "").strip()
    extract_system = _extract_system(stage_key)
    user_prompt = (
        f"阶段: {_STAGE_LABEL.get(stage_key, stage_key or '本阶段')}\n"
        f"{_STAGE_FOCUS.get(stage_key, '抽出可检索的借鉴剧情关键字。')}\n\n"
        f"材料:\n{source}"
    )
    provider = extract_cfg.get("provider")
    model = extract_cfg.get("model")
    reservation_tx = None
    try:
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            estimate = billing_service.estimate_reserve_tokens_from_messages(
                [
                    {"role": "system", "content": extract_system},
                    {"role": "user", "content": user_prompt},
                ],
            )
            reservation_tx = billing_service.reserve_credits(
                db,
                user_id,
                "llm_chat",
                provider,
                model,
                {
                    "item": billing_item,
                    "estimation_method": "prompt_tokens_ratio",
                    "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                    "input_tokens": estimate.get("input_tokens", 0),
                    "output_tokens": estimate.get("output_tokens", 0),
                    "total_tokens": estimate.get("total_tokens", 0),
                },
            )
        else:
            billing_service.check_balance(db, user_id, "llm_chat", provider, model)
    except HTTPException:
        raise
    except Exception:
        logger.warning("[reference_plot] billing skipped stage=%s", stage, exc_info=True)
        return empty_reference_plot_keywords()

    _release_db_connection(db, f"reference_plot_keywords_{stage_key or 'stage'}")
    from app.services.llm_service import llm_service

    try:
        resp = await llm_service.generate_content_with_fallback(
            user_prompt,
            extract_system,
            extract_cfg,
            image_urls=None,
            video_urls=None,
        )
    except Exception as exc:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(exc))
        logger.warning("[reference_plot] extract failed stage=%s err=%s", stage, exc)
        return empty_reference_plot_keywords()

    raw = str((resp or {}).get("content") or "").strip()
    if not raw or raw.lower().startswith("error:"):
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), raw or "empty keyword extract")
        logger.warning("[reference_plot] extract empty stage=%s", stage)
        return empty_reference_plot_keywords()

    usage = (resp or {}).get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": extract_system},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
            ],
            output_ratio=1.0,
        )
    details = _billing_details(billing_item, usage if isinstance(usage, dict) else {}, resp if isinstance(resp, dict) else {})
    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), details)
    else:
        billing_service.deduct_credits(db, user_id, "llm_chat", provider, model, details)

    keywords = parse_reference_plot_keywords(raw)
    logger.info(
        "[reference_plot] stage=%s works=%s plot_keywords=%s queries=%s",
        stage_key,
        len(keywords["works"]),
        len(keywords["plot_keywords"]),
        len(keywords["queries"]),
    )
    return keywords


async def prepare_reference_plot_submission(
    *,
    db: Optional[Session],
    user_id: int,
    llm_config: Optional[Dict[str, Any]],
    stage: str,
    source_text: str,
    billing_item: str,
) -> Tuple[str, Dict[str, Any], Dict[str, List[str]]]:
    """Extract keywords first. The returned config searches on the same generation submit."""
    keywords = await extract_reference_plot_keywords(
        db=db,
        user_id=user_id,
        llm_config=llm_config,
        stage=stage,
        source_text=source_text,
        billing_item=billing_item,
    )
    block = format_reference_plot_block(keywords, stage=stage)
    bound = attach_reference_plot_search(llm_config, keywords)
    logger.info(
        "[reference_plot] bind stage=%s search=%s provider=%s model=%s",
        stage,
        bool((bound.get("config") or {}).get("__reference_plot_search")),
        (bound or {}).get("provider"),
        (bound or {}).get("model"),
    )
    return block, bound, keywords
