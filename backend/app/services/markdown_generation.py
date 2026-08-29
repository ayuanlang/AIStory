# -*- coding: utf-8 -*-
"""Markdown validation and LLM markdown generation with retries."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.episode_script_output import (
    extract_official_episode_script,
    is_acceptable_episode_script_markdown,
)
from app.services.episode_script_reference_service import (
    extract_story_dna_output_for_validation,
    is_acceptable_story_dna_markdown,
)
from app.services.llm_markdown_sanitize import sanitize_llm_markdown_output
from app.services.llm_service import llm_service
from app.services.model_invocation_billing import _extract_llm_routing_metadata

logger = logging.getLogger("api_logger")

def _extract_md_section(md: str, start_header_regex: str) -> Tuple[str, str]:
    """Return (section_text, remainder) where section_text starts at the first header matching regex.

    Section is from matching header line up to (but not including) the next '## ' header.
    If not found, returns ("", md).
    """
    if not md:
        return "", md
    m = re.search(start_header_regex, md, flags=re.MULTILINE)
    if not m:
        return "", md
    start = m.start()
    after = md[m.end():]
    m2 = re.search(r"^##\s+", after, flags=re.MULTILINE)
    if m2:
        end = m.end() + m2.start()
        return md[start:end].strip(), (md[:start] + md[end:]).strip()
    return md[start:].strip(), md[:start].strip()


def is_valid_markdown_output(text: str, require_h1: bool = True) -> bool:
    if not text:
        return False

    content = str(text).strip()
    if not content:
        return False

    lower = content.lower()
    if "<think>" in lower or "```" in content:
        return False

    lines = [ln for ln in content.splitlines() if ln.strip()]
    if not lines:
        return False

    first = lines[0].lstrip()
    # Story DNA contract: machine title marker may lead the deliverable block.
    has_script_title_marker = bool(re.match(r"^\[\s*SCRIPT_TITLE\s*[：:]", first, flags=re.IGNORECASE))
    if require_h1 and not first.startswith("#") and not has_script_title_marker:
        return False

    # Basic markdown structure presence
    has_md_structure = any(
        ln.lstrip().startswith(("#", "- ", "* ", "|", ">", "1. ", "2. ", "3. "))
        or bool(re.match(r"^\[\s*SCRIPT_TITLE\s*[：:]", ln.lstrip(), flags=re.IGNORECASE))
        or bool(re.match(r"^\[\s*EPISODE_BLOCK_START", ln.lstrip(), flags=re.IGNORECASE))
        for ln in lines
    )
    return has_md_structure


def _parse_episode_heading_from_markdown(text: str) -> Dict[str, Any]:
    content = extract_official_episode_script(text) or str(text or "").strip()
    if not content:
        return {}

    non_empty_lines: List[str] = []
    first_line = ""
    for line in content.splitlines():
        candidate = str(line or "").strip()
        if candidate:
            non_empty_lines.append(candidate)
            if not first_line:
                first_line = candidate

    if not first_line:
        return {}

    has_markdown_h1 = first_line.startswith("#")
    second_line = non_empty_lines[1] if len(non_empty_lines) > 1 else ""
    looks_like_episode_heading = bool(
        re.match(r"^(?:#\s*)?(?:(?:EP(?:ISODE)?\s*)?0*\d+|第\s*\d+\s*[集话章回]|0*\d+)(?:\s*[-:：|｜]\s*|\s+).+$", first_line, flags=re.IGNORECASE)
    )
    looks_like_script_structure = bool(
        second_line and re.match(
            r"^(?:##\s*)?(?:-?1\)|核心内容纲要|本集卖点|娱乐化段子|Logline|Scenes|Ending Hook)\b",
            second_line,
            flags=re.IGNORECASE,
        )
    )
    if not has_markdown_h1 and not (looks_like_episode_heading and looks_like_script_structure):
        return {}

    heading = first_line.lstrip("#").strip()
    if not heading:
        return {"raw_heading": first_line}

    heading = re.sub(r"^[`*_~\s]+|[`*_~\s]+$", "", heading).strip()

    patterns = (
        r"^(?:EP(?:ISODE)?\s*)?0*(\d+)\s*[-:：|｜]\s*(.+)$",
        r"^第\s*(\d+)\s*[集话章回]\s*[-:：|｜]\s*(.+)$",
        r"^(?:EP(?:ISODE)?\s*)?0*(\d+)\s+(.+)$",
        r"^第\s*(\d+)\s*[集话章回]\s+(.+)$",
        r"^0*(\d+)\s*[-:：|｜]\s*(.+)$",
        r"^0*(\d+)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, heading, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            episode_number = int(match.group(1))
        except Exception:
            episode_number = None
        episode_title = str(match.group(2) or "").strip().strip("-:： ")
        return {
            "raw_heading": first_line,
            "episode_number": episode_number,
            "episode_title": episode_title,
        }

    return {
        "raw_heading": first_line,
        "episode_title": heading,
    }


async def generate_markdown_with_retry(
    user_prompt: str,
    sys_prompt: str,
    llm_config: Optional[Dict[str, Any]],
    strict_markdown: bool = True,
    require_h1: bool = True,
    return_meta: bool = False,
) -> Any:
    def _is_prohibited_marker(text: str) -> bool:
        if not text:
            return False
        t = text.strip().upper()
        t = t.lstrip("=").strip()
        return t == "PROHIBITED_CONTENT"

    def _looks_like_error_text(text: str) -> bool:
        if not text:
            return False
        t = text.strip().lower()
        return (
            t.startswith("error:")
            or "api error" in t
            or "no llm configuration" in t
            or "please configure your llm api key" in t
            or "prohibited_content" in t
        )

    async def _call_once(tag: str, up: str, sp: str) -> Tuple[str, str, Dict[str, Any]]:
        # Script / Story DNA generation is text-only — never attach reference images.
        resp = await llm_service.generate_content_with_fallback(
            up, sp, llm_config, image_urls=None, video_urls=None
        )
        raw = str(resp.get("content") or "")
        cleaned = sanitize_llm_markdown_output(raw)
        finish_reason = str(resp.get("finish_reason") or "")
        usage = resp.get("usage") or {}
        routing_meta = _extract_llm_routing_metadata(resp)
        logger.info(
            f"[generate_markdown_with_retry] tag={tag} raw_len={len(raw)} clean_len={len(cleaned)} "
            f"finish_reason={finish_reason or '-'} usage={usage} is_error_like={_looks_like_error_text(cleaned)}"
        )
        return raw, cleaned, {
            "tag": tag,
            "finish_reason": finish_reason,
            "usage": usage,
            "routing_metadata": routing_meta,
            "raw_len": len(raw),
            "clean_len": len(cleaned),
        }

    def _result_payload(content: str, meta: Optional[Dict[str, Any]]) -> Any:
        if not return_meta:
            return content
        return {
            "content": content,
            "usage": ((meta or {}).get("usage") if isinstance(meta, dict) else {}) or {},
            "routing_metadata": ((meta or {}).get("routing_metadata") if isinstance(meta, dict) else {}) or {},
            "finish_reason": ((meta or {}).get("finish_reason") if isinstance(meta, dict) else None),
        }

    def _is_truncated(meta: Optional[Dict[str, Any]]) -> bool:
        reason = str((meta or {}).get("finish_reason") or "").strip().lower()
        return reason == "length"

    def _validation_view(content: str, tag: str) -> str:
        """Prefer STORY_DNA_OUTPUT / episode-script OUTPUT so reasoning cannot fail validation."""
        episode_official = extract_official_episode_script(content)
        if episode_official and is_acceptable_episode_script_markdown(content):
            return episode_official
        info = extract_story_dna_output_for_validation(content)
        view = str(info.get("content") or content or "").strip()
        if info.get("had_output_markers") or info.get("truncated_thinking") or info.get("output_source"):
            logger.info(
                "[generate_markdown_with_retry] story_dna_truncate tag=%s "
                "had_output=%s had_thinking=%s truncated_thinking=%s "
                "output_source=%s output_score=%s "
                "full_len=%s validate_len=%s thinking_len=%s",
                tag,
                bool(info.get("had_output_markers")),
                bool(info.get("had_thinking_markers")),
                bool(info.get("truncated_thinking")),
                info.get("output_source"),
                info.get("output_score"),
                len(str(info.get("full") or "")),
                len(view),
                len(str(info.get("thinking") or "")),
            )
        return view

    def _passes_markdown(content: str, tag: str) -> bool:
        if not content or _looks_like_error_text(content):
            return False
        # Official episode script: OUTPUT markers (or extractable official body) pass.
        if is_acceptable_episode_script_markdown(content):
            view = _validation_view(content, tag)
            logger.info(
                "[generate_markdown_with_retry] episode_script_output_markers_accept tag=%s "
                "view_len=%s full_len=%s",
                tag,
                len(view),
                len(content),
            )
            return True
        # Story DNA hard rule: both OUTPUT_START and OUTPUT_END → middle slice passes.
        if is_acceptable_story_dna_markdown(content):
            view = _validation_view(content, tag)
            logger.info(
                "[generate_markdown_with_retry] story_dna_output_markers_accept tag=%s "
                "view_len=%s full_len=%s",
                tag,
                len(view),
                len(content),
            )
            return True
        view = _validation_view(content, tag)
        if is_valid_markdown_output(view, require_h1=require_h1):
            return True
        if is_acceptable_story_dna_markdown(view):
            logger.info(
                "[generate_markdown_with_retry] story_dna_lenient_accept tag=%s "
                "view_len=%s full_len=%s require_h1=%s",
                tag,
                len(view),
                len(content),
                require_h1,
            )
            return True
        return False

    raw_1, content_1, meta_1 = await _call_once("initial", user_prompt, sys_prompt)
    if _is_prohibited_marker(raw_1) or _is_prohibited_marker(content_1):
        logger.error("[generate_markdown_with_retry] provider returned PROHIBITED_CONTENT on initial attempt")
        raise RuntimeError("LLM content blocked by provider (PROHIBITED_CONTENT)")
    if _looks_like_error_text(content_1):
        lowered = (content_1 or "").strip().lower()
        if "please configure your llm api key" in lowered or "no llm configuration" in lowered:
            raise RuntimeError("No valid LLM API key configured in active settings")

    if not strict_markdown:
        if _is_truncated(meta_1):
            raise RuntimeError("LLM output appears truncated (finish_reason=length) in non-strict mode")
        if content_1 and not _looks_like_error_text(content_1):
            return _result_payload(content_1, meta_1)
        raise RuntimeError("LLM returned empty/error content in non-strict mode")

    if content_1 and _passes_markdown(content_1, "initial") and not _is_truncated(meta_1):
        return _result_payload(content_1, meta_1)

    retry_sys_prompt = (
        f"{sys_prompt}\n\n"
        "[FORMAT RETRY - STRICT]\n"
        "Return ONLY final valid Markdown.\n"
        "Do NOT output reasoning, preface text, or chain-of-thought outside truncatable markers.\n"
        "Do NOT output code fences.\n"
        "If this is Story DNA: wrap Part 1 in [STORY_DNA_THINKING_START]/[STORY_DNA_THINKING_END], "
        "and wrap §0–§9 (including [SCRIPT_TITLE:…]) in [STORY_DNA_OUTPUT_START]/[STORY_DNA_OUTPUT_END]. "
        "If this is an episode script: wrap analysis in [EPISODE_SCRIPT_THINKING_START]/[EPISODE_SCRIPT_THINKING_END], "
        "and wrap the official script (H1 + 核心内容纲要 + 卖点 + scenes + hooks) in "
        "[EPISODE_SCRIPT_OUTPUT_START]/[EPISODE_SCRIPT_OUTPUT_END]. "
        "OUTPUT block first non-empty line must be [SCRIPT_TITLE:…] or a markdown header starting with '# '.\n"
        "Otherwise: the first non-empty line must be an H1 markdown header starting with '# '."
    )
    retry_user_prompt = (
        f"{user_prompt}\n\n"
        "[RETRY INSTRUCTION]\n"
        "Only return corrected final markdown now. Put any reasoning inside THINKING markers; "
        "formal deliverable must be inside OUTPUT markers when Story DNA or episode-script tags apply."
    )
    raw_2, content_2, meta_2 = await _call_once("strict_retry", retry_user_prompt, retry_sys_prompt)
    if _is_prohibited_marker(raw_2) or _is_prohibited_marker(content_2):
        logger.error("[generate_markdown_with_retry] provider returned PROHIBITED_CONTENT on strict retry")
        raise RuntimeError("LLM content blocked by provider (PROHIBITED_CONTENT)")
    if content_2 and _passes_markdown(content_2, "strict_retry") and not _is_truncated(meta_2):
        return _result_payload(content_2, meta_2)

    final_retry_sys_prompt = (
        f"{sys_prompt}\n\n"
        "[FINAL RETRY - STRICT MARKDOWN ONLY]\n"
        "Return ONLY complete final markdown that fully satisfies the requested structure.\n"
        "Do NOT output a partial draft.\n"
        "Do NOT output placeholder sections.\n"
        "Do NOT output reasoning, analysis text, or code fences outside truncatable markers.\n"
        "If this is Story DNA: include [STORY_DNA_THINKING_START]/[STORY_DNA_THINKING_END] and "
        "[STORY_DNA_OUTPUT_START]/[STORY_DNA_OUTPUT_END]; OUTPUT must begin with [SCRIPT_TITLE:…] "
        "or a markdown header starting with '# '.\n"
        "If this is an episode script: include [EPISODE_SCRIPT_THINKING_START]/[EPISODE_SCRIPT_THINKING_END] and "
        "[EPISODE_SCRIPT_OUTPUT_START]/[EPISODE_SCRIPT_OUTPUT_END]; OUTPUT must begin with `# {n}-{title}` "
        "and include 核心内容纲要, 卖点, and [SCENES_BLOCK_START].\n"
        "Otherwise: the first non-empty line must be an H1 markdown header starting with '# '."
    )
    final_retry_user_prompt = (
        f"{user_prompt}\n\n"
        "[FINAL STRICT RETRY]\n"
        "Return only the fully valid final markdown now. If you cannot satisfy the required structure, do not emit a partial draft."
    )
    raw_3, content_3, meta_3 = await _call_once("final_strict_retry", final_retry_user_prompt, final_retry_sys_prompt)
    if _is_prohibited_marker(raw_3) or _is_prohibited_marker(content_3):
        logger.error("[generate_markdown_with_retry] provider returned PROHIBITED_CONTENT on final strict retry")
        raise RuntimeError("LLM content blocked by provider (PROHIBITED_CONTENT)")
    if content_3 and _passes_markdown(content_3, "final_strict_retry") and not _is_truncated(meta_3):
        return _result_payload(content_3, meta_3)

    diagnostics = {
        "initial_finish_reason": meta_1.get("finish_reason"),
        "strict_retry_finish_reason": meta_2.get("finish_reason"),
        "final_strict_retry_finish_reason": meta_3.get("finish_reason"),
        "initial_usage": meta_1.get("usage"),
        "strict_retry_usage": meta_2.get("usage"),
        "final_strict_retry_usage": meta_3.get("usage"),
        "initial_clean_len": len(content_1 or ""),
        "strict_retry_clean_len": len(content_2 or ""),
        "final_strict_retry_clean_len": len(content_3 or ""),
        "initial_error_like": _looks_like_error_text(content_1),
        "strict_retry_error_like": _looks_like_error_text(content_2),
        "final_strict_retry_error_like": _looks_like_error_text(content_3),
        "initial_raw_sample": (raw_1 or "")[:120],
        "strict_retry_raw_sample": (raw_2 or "")[:120],
        "final_strict_retry_raw_sample": (raw_3 or "")[:120],
    }
    logger.error(f"[generate_markdown_with_retry] exhausted retries. {json.dumps(diagnostics, ensure_ascii=False)}")
    if _is_truncated(meta_1) or _is_truncated(meta_2) or _is_truncated(meta_3):
        raise RuntimeError("LLM output appears truncated (finish_reason=length). Check model max_tokens/context and retry.")
    raise RuntimeError("LLM returned empty/invalid content after retries")
