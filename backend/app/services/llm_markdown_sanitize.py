# -*- coding: utf-8 -*-
"""LLM markdown sanitize helpers shared by API routes and script-analysis flow.

Kept outside app.api.endpoints so services never import the megamodule.
"""
from __future__ import annotations

import re
from typing import Any, List, Pattern


def sanitize_llm_markdown_output(text: str) -> str:
    """Best-effort cleanup for markdown endpoints.

    Removes common reasoning leakage (<think> blocks)
    and fenced wrappers when models ignore format instructions.
    """
    if not text:
        return ""

    content = str(text)
    content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
    content = content.replace("```markdown", "").replace("```md", "").replace("```", "").strip()
    # Remove common safety/moderation marker leakage from upstream providers.
    content = re.sub(r"^\s*=*\s*PROHIBITED_CONTENT\s*$", "", content, flags=re.IGNORECASE | re.MULTILINE)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    lines = content.splitlines()
    if not lines:
        return ""

    # Keep Story DNA truncatable markers intact for later OUTPUT/THINKING extraction.
    has_story_dna_markers = bool(
        re.search(r"\[\s*STORY_DNA_(THINKING|OUTPUT)_START\s*\]", content, flags=re.IGNORECASE)
    )

    reasoning_prefix_re = re.compile(
        r"^\s*(i will|let me|let's|analysis|reasoning|thought process|"
        r"分析|思路|推理|下面|我将|我认为|先来)\b",
        flags=re.IGNORECASE,
    )
    markdown_start_re = re.compile(
        r"^\s*(#|\||-\s|\d+\.\s|>\s|\*\s|\[\s*STORY_DNA_(?:THINKING|OUTPUT)_START\s*\]|\[\s*SCRIPT_TITLE\s*[：:])",
        flags=re.IGNORECASE,
    )

    # Trim leading blank lines first.
    while lines and not lines[0].strip():
        lines.pop(0)

    # Remove obvious leading reasoning lines.
    while lines and reasoning_prefix_re.match(lines[0]) and not markdown_start_re.match(lines[0]):
        lines.pop(0)

    # If a markdown-looking start exists later and the preface looks like reasoning,
    # cut to the markdown start. Skip when Story DNA markers are present so THINKING/OUTPUT
    # boundaries are not destroyed.
    if not has_story_dna_markers:
        first_md_index = None
        for idx, line in enumerate(lines):
            if markdown_start_re.match(line):
                first_md_index = idx
                break
        if first_md_index is not None and first_md_index > 0:
            preface = "\n".join(lines[:first_md_index]).lower()
            if any(token in preface for token in ["analysis", "reasoning", "推理", "思路", "我将", "我认为"]):
                lines = lines[first_md_index:]

    return "\n".join(lines).strip()


def _subject_index_row_markers_present(text: str) -> bool:
    """True when text looks like it contains at least one Subject Index entity row."""
    sample = str(text or "")
    if not sample.strip():
        return False
    return bool(
        re.search(r"(?im)^\s*\|?\s*S\d{3,}\s*\|", sample)
        or re.search(r"(?i)subject_no\s*=\s*[A-Za-z]?\d+\b", sample)
        or re.search(
            r"(?im)^\s*\|?\s*S\d{3,}\s*\|\s*(?:character|prop|environment|cover_poster|角色|道具|环境|封面)",
            sample,
        )
    )


def _is_subject_index_table_header_line(stripped: str) -> bool:
    sample = str(stripped or "").strip()
    if not sample:
        return False
    return bool(
        re.search(r"(?i)\bsubject_no\b", sample)
        and re.search(r"(?i)\bsubject_type\b", sample)
        and sample.count("|") >= 2
    )


def _is_subject_index_cover_poster_row(stripped: str) -> bool:
    sample = str(stripped or "").strip()
    if not sample or not re.search(r"(?i)^\s*\|?\s*S\d+\s*\|", sample):
        return False
    return bool(
        re.search(r"(?i)\|\s*cover_poster\s*\|", sample)
        or re.search(r"(?i)\|\s*(?:封面|海报|封面海报)\s*\|", sample)
    )


def _trim_duplicate_subject_index_lines(
    lines: List[str],
    *,
    delimiter: str,
    subject_header_re: Pattern[str],
    row_start_re: Pattern[str],
) -> List[str]:
    """Keep the first Subject Index table; drop repeated copies LLMs sometimes append."""
    out: List[str] = []
    seen_table_header = False
    seen_entity_row = False
    seen_subject_nos: set[str] = set()
    finished_cover_poster = False

    for line in lines:
        stripped = str(line or "").strip()
        if not stripped:
            if finished_cover_poster:
                continue
            out.append(line)
            continue

        if stripped == delimiter:
            if seen_table_header or seen_entity_row:
                break
            continue

        if subject_header_re.search(stripped):
            if seen_table_header or seen_entity_row:
                break
            out.append(line)
            continue

        if _is_subject_index_table_header_line(stripped):
            if seen_table_header and seen_entity_row:
                break
            seen_table_header = True
            out.append(line)
            continue

        row_match = row_start_re.match(stripped)
        if row_match:
            subject_no = str(row_match.group(1) or "").upper()
            if finished_cover_poster:
                break
            # Whole-table replay usually restarts at S001 after other rows were emitted.
            if (
                seen_entity_row
                and subject_no == "S001"
                and "S001" in seen_subject_nos
                and len(seen_subject_nos) > 1
            ):
                break
            if subject_no in seen_subject_nos and subject_no == "S001" and len(seen_subject_nos) == 1:
                # Immediate twin of the opening row before the table progressed.
                continue

            if subject_no:
                seen_subject_nos.add(subject_no)
            seen_entity_row = True
            out.append(line)
            if _is_subject_index_cover_poster_row(stripped):
                finished_cover_poster = True
            continue

        if finished_cover_poster:
            # Prompt contract: cover_poster is the last data row; ignore postscript / replay.
            break

        out.append(line)

    return out


def sanitize_subject_index_text(text: Any) -> str:
    """Keep only Subject Index content and strip common LLM reasoning leakage.

    This is intentionally conservative: if a clear Subject Index section is found,
    return that section; otherwise fall back to the cleaned original text.
    Also collapses occasional duplicate full Subject Index emits from the model.
    """
    cleaned = sanitize_llm_markdown_output(str(text or ""))
    if not cleaned:
        return ""

    # Chinese models often emit fullwidth pipes / spaces; normalize early for row detection.
    cleaned = (
        cleaned.replace("\uFF5C", "|")  # fullwidth vertical line
        .replace("\u2502", "|")  # box drawings light vertical
        .replace("\u00A0", " ")
    )

    delimiter = "----------------*****--------------"
    raw_cleaned = cleaned
    delimiter_matches = list(re.finditer(re.escape(delimiter), cleaned))
    if delimiter_matches:
        first = delimiter_matches[0]
        after = cleaned[first.end() :].strip()
        before = cleaned[: first.start()].strip()
        chose_between = False
        # Prefer the segment between the first and second delimiter when models emit
        # the required marker twice around duplicate tables.
        if len(delimiter_matches) > 1:
            between = cleaned[first.end() : delimiter_matches[1].start()].strip()
            if between and (
                _subject_index_row_markers_present(between)
                or re.search(r"(?i)subject\s*index|subject_no|subject_type", between)
            ):
                cleaned = between
                chose_between = True
        if not chose_between:
            # Prefer content after the required delimiter when it has rows/headers.
            # If the model put the table before the delimiter (or truncated after it),
            # keep whichever side still looks like a Subject Index.
            if after and (
                _subject_index_row_markers_present(after)
                or re.search(r"(?i)subject\s*index|subject_no|subject_type", after)
            ):
                cleaned = after
            elif before and _subject_index_row_markers_present(before):
                cleaned = before
            elif after:
                cleaned = after
            elif before:
                cleaned = before
            else:
                return ""

    lines = [str(line or "") for line in cleaned.splitlines()]
    if not lines:
        return ""

    subject_header_re = re.compile(
        r"(?i)^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:subject\s*index|subjects\s*index|"
        r"资产清单|实体清单|设计资产索引|资产索引|主体索引|实体索引)\b"
    )
    subject_hint_re = re.compile(r"(?i)subject_no|subject_type|script_entity_coverage")
    row_start_re = re.compile(r"(?i)^\s*\|?\s*(S\d+)\s*\|")
    row_token_re = re.compile(r"(?i)S\d{3,}")

    start_idx = -1
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if subject_header_re.search(stripped):
            start_idx = idx
            break
    if start_idx < 0:
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if subject_hint_re.search(stripped) or row_start_re.match(stripped):
                start_idx = idx
                break

    if start_idx < 0:
        # Docstring contract: fall back to cleaned original when no clear section marker.
        # Prefer the delimiter-adjusted cleaned text; else the pre-delimiter cleaned body.
        return cleaned.strip() or raw_cleaned.strip()

    end_idx = len(lines)
    seen_table_header = False
    seen_entity_row = False
    for idx in range(start_idx + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped:
            continue
        if stripped == delimiter and (seen_table_header or seen_entity_row):
            end_idx = idx
            break
        if subject_header_re.search(stripped) and (seen_table_header or seen_entity_row):
            end_idx = idx
            break
        if re.match(r"^#{1,6}\s+", stripped):
            end_idx = idx
            break
        if _is_subject_index_table_header_line(stripped):
            if seen_table_header and seen_entity_row:
                end_idx = idx
                break
            seen_table_header = True
            continue
        if row_start_re.match(stripped):
            seen_entity_row = True
            if _is_subject_index_cover_poster_row(stripped):
                # cover_poster is contractually the last data row; drop replay after it.
                end_idx = idx + 1
                break

    block_lines = lines[start_idx:end_idx]

    # Remove obvious non-index reasoning lines inside the candidate block.
    reasoning_line_re = re.compile(
        r"(?i)^\s*(i\s+am\s+now|i\s+will|let\s+me|let's|analysis|reasoning|thought\s+process|"
        r"我将|我会|下面|推理|思路)\b"
    )
    filtered_lines: List[str] = []
    for line in block_lines:
        stripped = line.strip()
        if stripped == delimiter:
            continue
        if reasoning_line_re.match(stripped) and not subject_hint_re.search(stripped):
            continue
        if stripped.startswith("**") and "finalizing" in stripped.lower():
            continue
        if "finalizing index" in stripped.lower() or "output is finalized" in stripped.lower():
            continue
        # Compact outputs may glue header + first row in one line; keep only row part.
        if re.search(r"(?i)subject_no.*subject_type.*subject_name", stripped) and row_token_re.search(stripped):
            m = row_token_re.search(stripped)
            if m:
                line = stripped[m.start():]
        filtered_lines.append(line)

    filtered_lines = _trim_duplicate_subject_index_lines(
        filtered_lines,
        delimiter=delimiter,
        subject_header_re=subject_header_re,
        row_start_re=row_start_re,
    )

    result = "\n".join(filtered_lines).strip()
    if result:
        # Normalize glued rows like: "...S001|...S002|..." into one row per line.
        # Do not split ordinary markdown cells that already start with "| S00x |".
        result = re.sub(r"(?<=\S)(?<![|\n])[ \t]*(?=S\d{3,}\s*\|)", "\n| ", result)
        result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result or cleaned.strip() or raw_cleaned.strip()
