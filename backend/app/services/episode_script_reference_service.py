from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.story_trend_search_service import (
    _collect_search_snippets_for_queries,
    _result_relevance_score,
    is_informative_search_snippet,
)

EPISODE_SCRIPT_MAX_SNIPPETS = 10
EPISODE_SCRIPT_MAX_QUERIES = 12
EPISODE_SCRIPT_LIMIT_PER_QUERY = 4
EPISODE_SCRIPT_MAX_ENRICH = 8

STORY_DNA_INPUT_START = "[STORY_DNA_INPUT_START]"
STORY_DNA_INPUT_END = "[STORY_DNA_INPUT_END]"
STORY_DNA_THINKING_START = "[STORY_DNA_THINKING_START]"
STORY_DNA_THINKING_END = "[STORY_DNA_THINKING_END]"
STORY_DNA_OUTPUT_START = "[STORY_DNA_OUTPUT_START]"
STORY_DNA_OUTPUT_END = "[STORY_DNA_OUTPUT_END]"

_EPISODE_HEADING_RE = re.compile(
    r"(?im)^(?:-\s*\*\*)?\s*EP0*(\d+)\b",
)
_EPISODE_AUDIT_RE = re.compile(r"(?im)^#{1,3}\s*Episode\s+Coverage\s+Audit\b")
def _episode_tag(episode_number: int) -> str:
    return f"EP{int(episode_number):02d}"


def episode_block_start_token(episode_number: int) -> str:
    return f"[EPISODE_BLOCK_START:{_episode_tag(episode_number)}]"


def episode_block_end_token(episode_number: int) -> str:
    return f"[EPISODE_BLOCK_END:{_episode_tag(episode_number)}]"


def wrap_story_dna_input_block(text: str) -> str:
    """Wrap creative/user payload so models and logs can truncate at INPUT markers."""
    body = str(text or "").strip()
    if not body:
        return f"{STORY_DNA_INPUT_START}\n{STORY_DNA_INPUT_END}"
    if STORY_DNA_INPUT_START in body and STORY_DNA_INPUT_END in body:
        return body
    return f"{STORY_DNA_INPUT_START}\n{body}\n{STORY_DNA_INPUT_END}"


def extract_story_dna_delimited_block(text: str, kind: str) -> str:
    """Extract inner content between STORY_DNA_{KIND}_START/END (exclusive of markers)."""
    source = str(text or "")
    kind_key = str(kind or "").strip().upper()
    if kind_key not in {"INPUT", "THINKING", "OUTPUT"}:
        return ""
    start_match = re.search(
        rf"\[\s*STORY_DNA_{kind_key}_START\s*\]",
        source,
        flags=re.IGNORECASE,
    )
    if not start_match:
        return ""
    content_start = start_match.end()
    end_match = re.search(
        rf"\[\s*STORY_DNA_{kind_key}_END\s*\]",
        source[content_start:],
        flags=re.IGNORECASE,
    )
    if not end_match:
        return source[content_start:].strip()
    return source[content_start : content_start + end_match.start()].strip()


def strip_story_dna_thinking_blocks(text: str) -> str:
    """Remove THINKING blocks (markers + inner) so reasoning does not affect validation."""
    source = str(text or "")
    if not source:
        return ""
    pattern = re.compile(
        r"\[\s*STORY_DNA_THINKING_START\s*\][\s\S]*?\[\s*STORY_DNA_THINKING_END\s*\]",
        flags=re.IGNORECASE,
    )
    cleaned = pattern.sub("", source)
    # orphan START without END: drop from START to EOF / next OUTPUT start
    orphan = re.search(r"\[\s*STORY_DNA_THINKING_START\s*\]", cleaned, flags=re.IGNORECASE)
    if orphan:
        next_output = re.search(
            r"\[\s*STORY_DNA_OUTPUT_START\s*\]",
            cleaned[orphan.start() :],
            flags=re.IGNORECASE,
        )
        if next_output:
            cut_at = orphan.start() + next_output.start()
            cleaned = cleaned[: orphan.start()] + cleaned[cut_at:]
        else:
            cleaned = cleaned[: orphan.start()]
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def extract_story_dna_output_for_validation(text: str) -> Dict[str, Any]:
    """Prefer OUTPUT block for checks; fall back to text with THINKING stripped.

    Returns:
      content: markdown used for validation / preferred deliverable body
      full: original text
      thinking: extracted THINKING inner (may be empty)
      had_output_markers / had_thinking_markers: bool
      truncated_thinking: bool
    """
    full = str(text or "")
    thinking = extract_story_dna_delimited_block(full, "THINKING")
    output = extract_story_dna_delimited_block(full, "OUTPUT")
    had_output = bool(output)
    had_thinking = bool(thinking) or bool(
        re.search(r"\[\s*STORY_DNA_THINKING_START\s*\]", full, flags=re.IGNORECASE)
    )
    if had_output:
        content = output
        truncated_thinking = had_thinking
    else:
        stripped = strip_story_dna_thinking_blocks(full)
        content = stripped or full
        truncated_thinking = bool(stripped) and stripped != full.strip()
    return {
        "content": str(content or "").strip(),
        "full": full,
        "thinking": thinking,
        "had_output_markers": had_output,
        "had_thinking_markers": had_thinking,
        "truncated_thinking": truncated_thinking,
    }


def normalize_story_dna_markdown_for_persist(text: str) -> str:
    """Keep markers for inspection; ensure OUTPUT body is the authoritative slice when present."""
    info = extract_story_dna_output_for_validation(text)
    full = str(info.get("full") or "")
    output = str(info.get("content") or "").strip()
    thinking = str(info.get("thinking") or "").strip()
    if info.get("had_output_markers"):
        parts: List[str] = []
        if thinking or info.get("had_thinking_markers"):
            parts.append(STORY_DNA_THINKING_START)
            parts.append(thinking)
            parts.append(STORY_DNA_THINKING_END)
            parts.append("")
        parts.append(STORY_DNA_OUTPUT_START)
        parts.append(output)
        parts.append(STORY_DNA_OUTPUT_END)
        return "\n".join(parts).strip()
    if info.get("truncated_thinking"):
        return output
    return full.strip()


def _extract_episode_block_by_delimiters(md: str, episode_number: int) -> str:
    text = str(md or "")
    if not text.strip():
        return ""

    start_token = episode_block_start_token(episode_number)
    end_token = episode_block_end_token(episode_number)
    start_idx = text.find(start_token)
    if start_idx < 0:
        return ""

    content_start = start_idx + len(start_token)
    end_idx = text.find(end_token, content_start)
    if end_idx < 0:
        return text[content_start:].strip()
    return text[content_start:end_idx].strip()


def _extract_episode_block_by_heading(md: str, episode_number: int) -> str:
    text = str(md or "")
    if not text.strip():
        return ""

    target = int(episode_number)
    section9_match = re.search(r"(?im)^##\s*9\)\s*分集规划", text)
    search_text = text[section9_match.start():] if section9_match else text

    audit_match = _EPISODE_AUDIT_RE.search(search_text)
    if audit_match:
        search_text = search_text[: audit_match.start()]

    starts: List[tuple[int, int]] = []
    for match in _EPISODE_HEADING_RE.finditer(search_text):
        try:
            ep_num = int(match.group(1))
        except Exception:
            continue
        if ep_num == target:
            starts.append((ep_num, match.start()))

    if not starts:
        return ""

    _, start_pos = starts[0]
    block = search_text[start_pos:]
    next_ep = None
    for match in _EPISODE_HEADING_RE.finditer(search_text, pos=start_pos + 1):
        try:
            ep_num = int(match.group(1))
        except Exception:
            continue
        if ep_num != target:
            next_ep = match.start()
            break
    if next_ep is not None:
        block = search_text[start_pos:next_ep]
    return block.strip()


def extract_episode_block_from_global_framework(md: str, episode_number: int) -> str:
    """Extract one episode's planning block from the global story framework."""
    # Prefer formal OUTPUT block so THINKING/reasoning cannot pollute episode slices.
    output = extract_story_dna_delimited_block(md, "OUTPUT")
    search_md = output or str(md or "")
    by_delimiters = _extract_episode_block_by_delimiters(search_md, episode_number)
    if by_delimiters:
        return by_delimiters
    return _extract_episode_block_by_heading(search_md, episode_number)


def _as_str_list(value: Any, *, limit: int = 6) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def build_episode_script_search_queries(
    key_elements: Dict[str, Any],
    *,
    episode_number: Optional[int] = None,
) -> List[str]:
    queries: List[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        q = " ".join(str(query or "").split()).strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    def add_reference_pack(term: str) -> None:
        add(f"{term} 短剧 名场面 剧情 桥段 解析")
        add(f"{term} 经典台词 对白 高光场面 分析")
        add(f"{term} 高潮场面 反转 场景描写")

    ep_prefix = f"第{int(episode_number)}集 " if episode_number else ""

    for term in _as_str_list(key_elements.get("iconic_scene_search_terms"), limit=3):
        add_reference_pack(f"{ep_prefix}{term}".strip())
    for term in _as_str_list(key_elements.get("climax_search_terms"), limit=3):
        add(f"{ep_prefix}{term} 高潮场面 经典 短剧".strip())
    for term in _as_str_list(key_elements.get("dialogue_search_terms"), limit=2):
        add(f"{ep_prefix}{term} 经典台词 对白 名场面".strip())
    for term in _as_str_list(key_elements.get("action_visual_search_terms"), limit=2):
        add(f"{ep_prefix}{term} 经典动作场面 镜头".strip())
    for term in _as_str_list(key_elements.get("trope_search_terms"), limit=2):
        add(f"{ep_prefix}{term} 热门桥段 反转 高潮".strip())

    for scene in _as_str_list(key_elements.get("climax_moments"), limit=2):
        add_reference_pack(f"{ep_prefix}{scene}".strip())
    for scene in _as_str_list(key_elements.get("signature_scenes"), limit=2):
        add_reference_pack(f"{ep_prefix}{scene}".strip())
    for hook in _as_str_list(key_elements.get("conflict_hooks"), limit=2):
        add_reference_pack(f"{ep_prefix}{hook}".strip())
    for work in _as_str_list(key_elements.get("reference_works"), limit=2):
        add(f"{work} 经典名场面 高潮 对白")

    if not queries:
        add("短剧 经典名场面 高潮 反转 桥段")
        add("微短剧 高光场面 经典对白")

    return queries[:EPISODE_SCRIPT_MAX_QUERIES]


def _filter_informative_snippets(snippets: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for row in snippets:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        url = str(row.get("url") or "").strip()
        if is_informative_search_snippet(snippet, title=title, url=url):
            out.append(row)
    return out


def _cap_snippets(
    snippets: List[Dict[str, str]],
    *,
    max_snippets: int = EPISODE_SCRIPT_MAX_SNIPPETS,
    reference_query: str = "",
) -> List[Dict[str, str]]:
    if not snippets:
        return []
    usable = _filter_informative_snippets(snippets)
    ranked = sorted(
        usable,
        key=lambda row: _result_relevance_score(
            reference_query,
            str(row.get("title") or ""),
            str(row.get("snippet") or ""),
            str(row.get("url") or ""),
        ),
        reverse=True,
    )
    return ranked[: max(1, int(max_snippets or EPISODE_SCRIPT_MAX_SNIPPETS))]


async def collect_episode_script_reference_snippets(
    key_elements: Dict[str, Any],
    *,
    episode_number: Optional[int] = None,
    max_snippets: int = EPISODE_SCRIPT_MAX_SNIPPETS,
) -> Dict[str, Any]:
    queries = build_episode_script_search_queries(key_elements, episode_number=episode_number)
    bundle = await _collect_search_snippets_for_queries(
        queries,
        limit_per_query=EPISODE_SCRIPT_LIMIT_PER_QUERY,
        max_enrich_per_query=EPISODE_SCRIPT_MAX_ENRICH,
        require_informative_snippet=True,
        report_kind="episode_script_reference",
    )
    reference_query = " ".join(
        _as_str_list(key_elements.get("iconic_scene_search_terms"), limit=2)
        + _as_str_list(key_elements.get("climax_search_terms"), limit=2)
        + _as_str_list(key_elements.get("conflict_hooks"), limit=1)
    )
    capped = _cap_snippets(
        bundle.get("snippets") or [],
        max_snippets=max_snippets,
        reference_query=reference_query,
    )
    bundle["snippets"] = capped
    bundle["snippet_cap"] = max_snippets
    return bundle


def build_episode_script_reference_user_prompt(
    search_bundle: Dict[str, Any],
    key_elements: Dict[str, Any],
    *,
    episode_number: int,
    episode_block: str = "",
    project_title: str = "",
    language: str = "",
) -> str:
    lines = [
        "[EPISODE_REFERENCE_RESEARCH_START]",
        "【分集参考检索 / Episode Reference Research】",
        "Use these web snippets as reference for trope rhythm, iconic staging, dialogue punch, and climax beats.",
        "Localize and recombine; do NOT copy plots, character names, or verbatim lines.",
        f"Episode Number: {episode_number}",
        f"Project Title: {project_title or '(none)'}",
        f"Preferred Language: {language or 'zh'}",
    ]
    if episode_block.strip():
        lines.append("")
        lines.append("Current Episode Framework Excerpt (from Global Story DNA section 9):")
        lines.append(episode_block.strip()[:2400])
    lines.append("")
    lines.append("Extracted Search Key Elements:")
    for key in (
        "genres",
        "themes",
        "conflict_hooks",
        "signature_scenes",
        "climax_moments",
        "iconic_scene_search_terms",
        "climax_search_terms",
        "dialogue_search_terms",
        "action_visual_search_terms",
        "trope_search_terms",
        "reference_works",
    ):
        value = key_elements.get(key)
        if isinstance(value, list):
            rendered = ", ".join(str(v).strip() for v in value if str(v).strip())
        else:
            rendered = str(value or "").strip()
        if rendered:
            lines.append(f"- {key}: {rendered}")

    lines.append("")
    lines.append(f"Web Search Snippets (max {search_bundle.get('snippet_cap', EPISODE_SCRIPT_MAX_SNIPPETS)}, text-only):")
    rendered_snippets = 0
    for idx, item in enumerate(search_bundle.get("snippets") or [], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        if not is_informative_search_snippet(snippet, title=title, url=str(item.get("url") or "")):
            continue
        rendered_snippets += 1
        lines.extend(
            [
                f"[{idx}] Query: {item.get('query', '')}",
                f"Title: {title}",
                f"Summary: {snippet[:480]}",
                "",
            ]
        )
    if rendered_snippets <= 0:
        lines.append("(No informative web snippets returned; rely on Extracted Search Key Elements and Episode Framework above.)")
    lines.append("[EPISODE_REFERENCE_RESEARCH_END]")
    search_bundle["rendered_snippet_count"] = rendered_snippets
    return "\n".join(lines).strip()
