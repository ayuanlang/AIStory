from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.story_trend_search_service import (
    _attach_priority_fields,
    _collect_search_snippets_for_queries,
    _row_evidence_text,
    format_search_evidence_lines,
    is_informative_search_snippet,
    resolve_excerpt_max_len,
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


# Closed OUTPUT shorter than this is treated as a false/premature closure (e.g. copied "…" skeleton).
_STORY_DNA_MIN_OUTPUT_LEN = 200


def _story_dna_marker_re(kind: str, side: str):
    kind_key = str(kind or "").strip().upper()
    side_key = str(side or "").strip().upper()
    return re.compile(rf"\[\s*STORY_DNA_{kind_key}_{side_key}\s*\]", flags=re.IGNORECASE)


def iter_story_dna_delimited_blocks(text: str, kind: str) -> List[Dict[str, Any]]:
    """Return all START/END pairs for a kind (non-greedy, scanned left-to-right)."""
    source = str(text or "")
    kind_key = str(kind or "").strip().upper()
    if kind_key not in {"INPUT", "THINKING", "OUTPUT"} or not source:
        return []
    start_re = _story_dna_marker_re(kind_key, "START")
    end_re = _story_dna_marker_re(kind_key, "END")
    blocks: List[Dict[str, Any]] = []
    pos = 0
    while True:
        start_match = start_re.search(source, pos)
        if not start_match:
            break
        content_start = start_match.end()
        end_match = end_re.search(source, content_start)
        if not end_match:
            inner = source[content_start:].strip()
            blocks.append(
                {
                    "content": inner,
                    "start": start_match.start(),
                    "content_start": content_start,
                    "end": len(source),
                    "closed": False,
                }
            )
            break
        inner = source[content_start : end_match.start()].strip()
        blocks.append(
            {
                "content": inner,
                "start": start_match.start(),
                "content_start": content_start,
                "end": end_match.end(),
                "closed": True,
            }
        )
        pos = end_match.end()
    return blocks


def extract_story_dna_delimited_block(text: str, kind: str) -> str:
    """Extract preferred inner content between STORY_DNA_{KIND}_START/END."""
    blocks = iter_story_dna_delimited_blocks(text, kind)
    if not blocks:
        return ""
    if str(kind or "").strip().upper() != "OUTPUT":
        return str(blocks[0].get("content") or "").strip()
    # For OUTPUT, prefer the highest-quality candidate (not necessarily the first).
    ranked = sorted(blocks, key=lambda b: _score_story_dna_output_candidate(str(b.get("content") or "")), reverse=True)
    return str(ranked[0].get("content") or "").strip()


def _trim_story_dna_placeholder_preamble(content: str) -> str:
    """Drop leading ellipsis/skeleton lines so validation sees SCRIPT_TITLE / headings."""
    lines = str(content or "").splitlines()
    idx = 0
    placeholder_re = re.compile(r"^[.…\s\-—_*]+$")
    while idx < len(lines):
        stripped = lines[idx].strip()
        if not stripped:
            idx += 1
            continue
        if placeholder_re.fullmatch(stripped):
            idx += 1
            continue
        break
    return "\n".join(lines[idx:]).strip()


def _score_story_dna_output_candidate(content: str) -> int:
    text = _trim_story_dna_placeholder_preamble(content)
    if not text:
        return -1
    # Pure ellipsis / placeholder skeletons from prompt examples.
    if re.fullmatch(r"[.…\s\-—_]+", text):
        return -1
    score = len(text)
    if re.search(r"\[\s*SCRIPT_TITLE\s*[：:]", text, flags=re.IGNORECASE):
        score += 50_000
    if re.search(r"(?im)^(?:##\s*)?9\)\s*", text) or re.search(r"分集规划", text):
        score += 20_000
    if re.search(r"\[\s*EPISODE_BLOCK_START", text, flags=re.IGNORECASE):
        score += 20_000
    if re.search(r"(?im)^(?:##\s*)?0\)\s*", text):
        score += 5_000
    if re.search(r"(?im)^(?:##\s*)?Part\s*2\b", text):
        score += 2_000
    if re.search(r"(?im)\bVerdict\s*[：:]\s*通过", text) or re.search(r"Episode\s+Coverage\s+Audit", text, flags=re.I):
        score += 15_000
    if re.search(r"(?im)^(?:##\s*)?Part\s*1\b", text):
        score += 500
    return score


def extract_story_dna_output_between_markers(text: str) -> Dict[str, Any]:
    """If both OUTPUT_START and OUTPUT_END exist, return the slice between them.

    Prefer the longest closed START…END pair when multiple pairs appear (avoids
    empty skeleton pairs copied from the prompt).
    """
    source = str(text or "")
    start_re = _story_dna_marker_re("OUTPUT", "START")
    end_re = _story_dna_marker_re("OUTPUT", "END")
    has_start = bool(start_re.search(source))
    has_end = bool(end_re.search(source))
    if not (has_start and has_end):
        return {
            "found": False,
            "content": "",
            "has_start": has_start,
            "has_end": has_end,
        }

    best_inner = ""
    best_len = -1
    pos = 0
    while True:
        start_match = start_re.search(source, pos)
        if not start_match:
            break
        end_match = end_re.search(source, start_match.end())
        if not end_match:
            break
        inner = source[start_match.end() : end_match.start()]
        # Keep raw middle (only strip outer whitespace) — validation does not
        # require H1 / SCRIPT_TITLE when both markers are present.
        inner_stripped = inner.strip()
        if len(inner_stripped) > best_len:
            best_len = len(inner_stripped)
            best_inner = inner_stripped
        pos = end_match.end()

    return {
        "found": best_len >= 0,
        "content": best_inner,
        "has_start": True,
        "has_end": True,
    }


def is_acceptable_story_dna_markdown(text: str) -> bool:
    """Pass when both OUTPUT markers exist — middle slice is the deliverable.

    Contract (hard, minimal):
      [STORY_DNA_OUTPUT_START] … [STORY_DNA_OUTPUT_END]
    Presence of both markers is enough to pass validation; content between them
    is what we keep / check. Falls back to a light length+signal check only when
    markers are missing (legacy / malformed streams).
    """
    marked = extract_story_dna_output_between_markers(text)
    if marked.get("found"):
        return True

    content = _trim_story_dna_placeholder_preamble(_strip_all_story_dna_markers(text))
    if len(content) < 800:
        return False
    lower = content.lower()
    if lower.startswith("error:") or "prohibited_content" in lower:
        return False
    signals = 0
    if re.search(r"\[\s*SCRIPT_TITLE\s*[：:]", content, flags=re.IGNORECASE):
        signals += 2
    if re.search(r"\[\s*EPISODE_BLOCK_START", content, flags=re.IGNORECASE):
        signals += 2
    if re.search(r"(?im)\bVerdict\b", content) or "分集规划" in content:
        signals += 1
    if re.search(r"(?im)^(?:##\s*)?(?:Part\s*[12]\b|\d+\))", content):
        signals += 1
    if len(content) >= 5000 and signals >= 1:
        return True
    return signals >= 2


def _recover_output_after_premature_close(full: str) -> str:
    """If first OUTPUT pair is a tiny skeleton, return body after that premature END."""
    start_re = _story_dna_marker_re("OUTPUT", "START")
    end_re = _story_dna_marker_re("OUTPUT", "END")
    start_match = start_re.search(full)
    if not start_match:
        return ""
    rest = full[start_match.end() :]
    end_match = end_re.search(rest)
    if not end_match:
        return _trim_story_dna_placeholder_preamble(end_re.sub("", rest))
    first_inner = rest[: end_match.start()].strip()
    if (
        len(first_inner) >= _STORY_DNA_MIN_OUTPUT_LEN
        and _score_story_dna_output_candidate(first_inner) > 0
    ):
        # First closed block looks real; still allow EOF candidate separately.
        to_eof = end_re.sub("", rest).strip()
        return _trim_story_dna_placeholder_preamble(to_eof)
    # Premature close: keep everything after the bad END (may include more OUTPUT markers).
    after = rest[end_match.end() :]
    after = start_re.sub("", after)
    after = end_re.sub("", after)
    return _trim_story_dna_placeholder_preamble(after)


def _strip_all_story_dna_markers(text: str) -> str:
    cleaned = str(text or "")
    for kind in ("INPUT", "THINKING", "OUTPUT"):
        cleaned = _story_dna_marker_re(kind, "START").sub("", cleaned)
        cleaned = _story_dna_marker_re(kind, "END").sub("", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


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
    # orphan START without END: keep body (do NOT wipe to EOF — models often omit THINKING_END).
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
            # Malformed: THINKING_START … [OUTPUT_END] with no OUTPUT_START / THINKING_END.
            # Drop only the START marker; keep the body for recovery.
            cleaned = cleaned[: orphan.start()] + cleaned[orphan.end() :]
    cleaned = _story_dna_marker_re("OUTPUT", "START").sub("", cleaned)
    cleaned = _story_dna_marker_re("OUTPUT", "END").sub("", cleaned)
    cleaned = _story_dna_marker_re("THINKING", "END").sub("", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _recover_malformed_story_dna_stream(full: str) -> str:
    """Recover body when model emits THINKING_START … OUTPUT_END without middle markers."""
    source = str(full or "")
    think_start = _story_dna_marker_re("THINKING", "START").search(source)
    out_end = None
    for match in _story_dna_marker_re("OUTPUT", "END").finditer(source):
        out_end = match
    if think_start and out_end and out_end.start() > think_start.end():
        inner = source[think_start.end() : out_end.start()]
        return _strip_all_story_dna_markers(inner)
    if out_end:
        return _strip_all_story_dna_markers(source[: out_end.start()])
    return ""


def extract_story_dna_output_for_validation(text: str) -> Dict[str, Any]:
    """Prefer OUTPUT_START…OUTPUT_END middle; fall back for malformed streams.

    Primary contract: both markers present → middle slice is the deliverable.
    When multiple pairs exist, keep the longest middle (skip empty skeletons).
    """
    full = str(text or "")
    thinking_blocks = iter_story_dna_delimited_blocks(full, "THINKING")
    thinking = str((thinking_blocks[0].get("content") if thinking_blocks else "") or "").strip()
    if len(thinking_blocks) > 1:
        thinking = max(
            (str(b.get("content") or "").strip() for b in thinking_blocks),
            key=len,
            default=thinking,
        )
    if thinking_blocks and not thinking_blocks[0].get("closed") and len(thinking) > _STORY_DNA_MIN_OUTPUT_LEN:
        split_m = re.search(
            r"(?im)^(?:##\s*)?(?:Part\s*2\b|0\)\s*|9\)\s*分集|[\[\s]*SCRIPT_TITLE\s*[：:])",
            thinking,
        )
        if split_m and split_m.start() > 40:
            thinking = thinking[: split_m.start()].strip()
        else:
            thinking = ""
    had_thinking = bool(
        re.search(r"\[\s*STORY_DNA_THINKING_START\s*\]", full, flags=re.IGNORECASE)
    )

    # Hard rule: both OUTPUT markers → middle content wins (longest pair).
    marked = extract_story_dna_output_between_markers(full)
    if marked.get("found"):
        middle = str(marked.get("content") or "")
        # If the longest closed middle is still a tiny placeholder, try recovery
        # candidates so we do not persist an empty "…" skeleton.
        if len(middle) >= _STORY_DNA_MIN_OUTPUT_LEN or _score_story_dna_output_candidate(middle) > 0:
            return {
                "content": middle,
                "full": full,
                "thinking": thinking,
                "had_output_markers": True,
                "had_thinking_markers": had_thinking,
                "truncated_thinking": had_thinking,
                "output_source": "output_markers_middle",
                "output_score": max(len(middle), _score_story_dna_output_candidate(middle)),
            }

    output_blocks = iter_story_dna_delimited_blocks(full, "OUTPUT")
    candidates: List[tuple[int, str, str]] = []

    if marked.get("found"):
        middle = str(marked.get("content") or "")
        candidates.append((len(middle), middle, "output_markers_middle"))

    for block in output_blocks:
        if not block.get("closed") and not _story_dna_marker_re("OUTPUT", "START").search(full):
            continue
        inner = str(block.get("content") or "").strip()
        candidates.append((_score_story_dna_output_candidate(inner), inner, "closed_or_open_block"))

    first_out_start = _story_dna_marker_re("OUTPUT", "START").search(full)
    if first_out_start:
        to_eof = full[first_out_start.end() :]
        to_eof = _story_dna_marker_re("OUTPUT", "END").sub("", to_eof).strip()
        candidates.append((_score_story_dna_output_candidate(to_eof), to_eof, "output_start_to_eof"))
        premature = _recover_output_after_premature_close(full)
        if premature:
            candidates.append(
                (_score_story_dna_output_candidate(premature), premature, "after_premature_output_end")
            )

    stripped = strip_story_dna_thinking_blocks(full)
    if stripped:
        candidates.append((_score_story_dna_output_candidate(stripped), stripped, "strip_thinking"))

    last_thinking_end = None
    for match in _story_dna_marker_re("THINKING", "END").finditer(full):
        last_thinking_end = match
    if last_thinking_end:
        after = _strip_all_story_dna_markers(full[last_thinking_end.end() :])
        if after:
            candidates.append((_score_story_dna_output_candidate(after), after, "after_thinking_end"))

    malformed = _recover_malformed_story_dna_stream(full)
    if malformed:
        candidates.append(
            (_score_story_dna_output_candidate(malformed), malformed, "malformed_thinking_to_output_end")
        )

    markerless = _strip_all_story_dna_markers(full)
    if markerless:
        candidates.append((_score_story_dna_output_candidate(markerless), markerless, "strip_all_markers"))

    best_score = -1
    best_content = ""
    best_source = "full"
    for score, content, source_tag in candidates:
        content = str(content or "").strip()
        score = _score_story_dna_output_candidate(content) if source_tag != "output_markers_middle" else max(score, len(content))
        if score > best_score:
            best_score = score
            best_content = content
            best_source = source_tag

    had_output = bool(marked.get("found"))
    if best_score < 0 or not best_content:
        best_content = stripped or markerless or full
        best_source = "fallback_full"
        truncated_thinking = bool(stripped) and stripped != full.strip()
        had_output = False
    else:
        truncated_thinking = had_thinking and best_source != "full"

    return {
        "content": str(best_content or "").strip(),
        "full": full,
        "thinking": thinking,
        "had_output_markers": had_output,
        "had_thinking_markers": had_thinking,
        "truncated_thinking": truncated_thinking,
        "output_source": best_source,
        "output_score": best_score,
    }


def normalize_story_dna_markdown_for_persist(text: str) -> str:
    """Keep markers for inspection; ensure OUTPUT body is the authoritative slice when present."""
    info = extract_story_dna_output_for_validation(text)
    full = str(info.get("full") or "")
    output = str(info.get("content") or "").strip()
    thinking = str(info.get("thinking") or "").strip()
    # Rebuild when we recovered a real deliverable (even if the model closed OUTPUT too early).
    if output and (
        info.get("had_output_markers")
        or info.get("output_source")
        in {
            "output_start_to_eof",
            "after_thinking_end",
            "strip_thinking",
            "after_premature_output_end",
            "malformed_thinking_to_output_end",
            "strip_all_markers",
            "fallback_full",
        }
        or (info.get("had_thinking_markers") and len(output) >= _STORY_DNA_MIN_OUTPUT_LEN)
    ):
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


def _filter_informative_snippets(snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in snippets:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        evidence = _row_evidence_text(row)
        url = str(row.get("url") or "").strip()
        if is_informative_search_snippet(evidence, title=title, url=url):
            out.append(row)
    return out


def _cap_snippets(
    snippets: List[Dict[str, Any]],
    *,
    max_snippets: int = EPISODE_SCRIPT_MAX_SNIPPETS,
    reference_query: str = "",
) -> List[Dict[str, Any]]:
    if not snippets:
        return []
    usable = _filter_informative_snippets(snippets)
    ranked: List[Dict[str, Any]] = []
    for row in usable:
        ranked.append(
            _attach_priority_fields(
                dict(row),
                query=reference_query or str(row.get("query") or ""),
            )
        )
    ranked.sort(key=lambda row: (int(row.get("priority") or 0), len(_row_evidence_text(row))), reverse=True)
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
        "Use these priority-ordered web evidence blocks as reference for trope rhythm, iconic staging, dialogue punch, and climax beats.",
        "Consume P0 first, then P1, then P2. Prefer Evidence body over titles. Localize and recombine; do NOT copy plots, character names, or verbatim lines.",
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
    evidence_cap = int(search_bundle.get("snippet_cap") or EPISODE_SCRIPT_MAX_SNIPPETS)
    evidence_chars = min(resolve_excerpt_max_len(), 1500)
    usable = [
        item
        for item in (search_bundle.get("snippets") or [])
        if isinstance(item, dict)
        and is_informative_search_snippet(
            _row_evidence_text(item),
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
        )
    ][:evidence_cap]
    lines.extend(
        format_search_evidence_lines(
            usable,
            include_url=False,
            max_chars_per_item=evidence_chars,
            heading=f"Web Search Evidence (max {evidence_cap}, text-only, priority-ordered):",
        )
    )
    rendered_snippets = sum(1 for item in usable if _row_evidence_text(item))
    if rendered_snippets <= 0:
        lines.append("(No informative web evidence returned; rely on Extracted Search Key Elements and Episode Framework above.)")
    lines.append("[EPISODE_REFERENCE_RESEARCH_END]")
    search_bundle["rendered_snippet_count"] = rendered_snippets
    return "\n".join(lines).strip()
