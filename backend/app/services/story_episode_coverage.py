# -*- coding: utf-8 -*-
"""Force global story frameworks to contain one block per requested episode."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.episode_script_reference_service import extract_story_dna_delimited_block
from app.services.llm_service import llm_service

logger = logging.getLogger("api_logger")

_START_RE = re.compile(r"\[\s*EPISODE_BLOCK_START\s*:\s*EP(\d+)\s*\]", re.IGNORECASE)
_AUDIT_RE = re.compile(r"(?im)^#{1,3}\s*Episode\s+Coverage\s+Audit\b")
_OUTPUT_END_RE = re.compile(r"\[\s*STORY_DNA_OUTPUT_END\s*\]", re.IGNORECASE)

_FILL_SYSTEM = (
    "你在补全已经写好的全局故事框架里缺掉的集。只输出本次点名的集。\n"
    "每一集一对独占行 [EPISODE_BLOCK_START:EPxx] 与 [EPISODE_BLOCK_END:EPxx]，集号用两位。\n"
    "每集只有五行：标题、摘要（因为/所以/但是）、交接（入/出/钩子）、时间（绝对或相对节点的范围，含季节、昼夜、气候）、在场名。\n"
    "不写故事环、卖点、金句、场表、选场逻辑、多线表、AI放大、戏份。\n"
    "不写思考过程，不写用户原文保留区，不写逐字落实映射，不回抄用户原文，不重写 §0–§8，不写 Episode Coverage Audit。\n"
    "人物、场景、道具只用已有名字和已有功能。\n"
)


def _end_re(episode_number: int) -> re.Pattern[str]:
    return re.compile(rf"\[\s*EPISODE_BLOCK_END\s*:\s*EP0*{int(episode_number)}\s*\]", re.IGNORECASE)


def complete_episode_blocks(text: str) -> Dict[int, str]:
    """Map episode number to a closed START…END block. Later duplicates do not replace the first."""
    source = str(text or "")
    found: Dict[int, str] = {}
    for match in _START_RE.finditer(source):
        number = int(match.group(1))
        if number in found:
            continue
        end = _end_re(number).search(source, match.end())
        if not end:
            continue
        found[number] = source[match.start() : end.end()].strip()
    return found


def missing_episode_numbers(text: str, planned: int) -> List[int]:
    try:
        total = int(planned)
    except (TypeError, ValueError):
        return []
    if total <= 0:
        return []
    have = set(complete_episode_blocks(text))
    return [number for number in range(1, total + 1) if number not in have]


def drop_incomplete_episode_tail(text: str) -> str:
    """Remove a trailing episode that has START but no END, and keep a later audit or output end."""
    source = str(text or "")
    starts = list(_START_RE.finditer(source))
    if not starts:
        return source
    last = starts[-1]
    number = int(last.group(1))
    if _end_re(number).search(source, last.end()):
        return source
    end_at = len(source)
    for marker in (_AUDIT_RE, _OUTPUT_END_RE):
        found = marker.search(source, last.start())
        if found:
            end_at = min(end_at, found.start())
    return source[: last.start()].rstrip() + "\n\n" + source[end_at:].lstrip()


def splice_episode_blocks(base: str, addition: str) -> str:
    """Insert closed blocks from addition into base, in episode order, without duplicating."""
    cleaned = drop_incomplete_episode_tail(base)
    merged = complete_episode_blocks(cleaned)
    for number, block in complete_episode_blocks(addition).items():
        merged.setdefault(number, block)
    if not merged:
        return cleaned
    stripped = cleaned
    for block in complete_episode_blocks(cleaned).values():
        stripped = stripped.replace(block, "", 1)
    chunk = "\n\n".join(merged[number] for number in sorted(merged))
    audit = _AUDIT_RE.search(stripped)
    if audit:
        return stripped[: audit.start()].rstrip() + "\n\n" + chunk + "\n\n" + stripped[audit.start() :]
    output_end = _OUTPUT_END_RE.search(stripped)
    if output_end:
        return stripped[: output_end.start()].rstrip() + "\n\n" + chunk + "\n\n" + stripped[output_end.start() :]
    return stripped.rstrip() + "\n\n" + chunk + "\n"


def framework_context_for_fill(markdown: str, *, limit: int = 12000) -> str:
    output = extract_story_dna_delimited_block(markdown, "OUTPUT") or str(markdown or "")
    section9 = re.search(r"(?im)^##\s*9\)", output)
    head = output[: section9.start()] if section9 else output
    blocks = complete_episode_blocks(output)
    titles: List[str] = []
    for number in sorted(blocks):
        for line in blocks[number].splitlines():
            stripped = line.strip()
            if stripped and "EPISODE_BLOCK_" not in stripped:
                titles.append(stripped[:180])
                break
    last = blocks[max(blocks)] if blocks else ""
    text = head.strip()[:6000]
    if titles:
        text += "\n\n已完成集:\n" + "\n".join(titles)
    if last:
        text += "\n\n紧邻上一集:\n" + last
    return text[:limit]


def _usage_pair(usage: Any) -> Tuple[int, int]:
    if not isinstance(usage, dict):
        return 0, 0
    prompt = usage.get("prompt_tokens")
    if prompt is None:
        prompt = usage.get("input_tokens") or 0
    completion = usage.get("completion_tokens")
    if completion is None:
        completion = usage.get("output_tokens") or 0
    return int(prompt or 0), int(completion or 0)


def merge_usage(base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    prompt, completion = _usage_pair(base)
    extra_prompt, extra_completion = _usage_pair(extra)
    prompt += extra_prompt
    completion += extra_completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "input_tokens": prompt,
        "output_tokens": completion,
        "total_tokens": prompt + completion,
    }


def _fill_user_prompt(context: str, batch: List[int], planned: int) -> str:
    labels = ", ".join(f"EP{number:02d}" for number in batch)
    return (
        f"计划集数 = {planned}。这次只补：{labels}。\n"
        "每集单独成块，含本集冲突、转折、Continuity 和集末钩子。不要用总述代替。\n\n"
        f"{context}"
    )


async def ensure_story_episode_blocks(
    markdown: str,
    *,
    episodes_count: int,
    llm_config: Optional[Dict[str, Any]],
    user_id: Optional[int] = None,
    batch_size: int = 4,
    max_rounds: int = 8,
) -> Tuple[str, Dict[str, Any]]:
    """Append any missing EP01–EPN blocks. Raises if they are still missing after the fill rounds."""
    current = str(markdown or "")
    added_usage: Dict[str, Any] = {}
    try:
        planned = int(episodes_count)
    except (TypeError, ValueError):
        return current, added_usage
    if planned <= 0:
        return current, added_usage

    missing = missing_episode_numbers(current, planned)
    if not missing:
        return current, added_usage

    stalls = 0
    for _round in range(max_rounds):
        if not missing:
            break
        batch = missing[: max(1, int(batch_size))]
        context = framework_context_for_fill(current)
        response = await llm_service.generate_content_with_fallback(
            _fill_user_prompt(context, batch, planned),
            _FILL_SYSTEM,
            llm_config or {},
            image_urls=None,
            video_urls=None,
            user_id=user_id,
            category="LLM",
        )
        added_usage = merge_usage(added_usage, (response or {}).get("usage"))
        addition = str((response or {}).get("content") or "")
        updated = splice_episode_blocks(current, addition)
        still_missing = missing_episode_numbers(updated, planned)
        logger.info(
            "[ensure_story_episode_blocks] planned=%s batch=%s before=%s after=%s",
            planned,
            batch,
            missing,
            still_missing,
        )
        if len(still_missing) >= len(missing):
            stalls += 1
            if stalls >= 2:
                break
        else:
            stalls = 0
            current = updated
            missing = still_missing

    if missing:
        raise RuntimeError(
            "故事框架未写齐全部分集，缺："
            + ", ".join(f"EP{number:02d}" for number in missing)
        )
    return current, added_usage
