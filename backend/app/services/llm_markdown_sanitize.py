# -*- coding: utf-8 -*-
"""LLM markdown sanitize helpers shared by API routes and script-analysis flow.

Kept outside app.api.endpoints so services never import the megamodule.
"""
from __future__ import annotations

import re
from typing import Any, List


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


def sanitize_subject_index_text(text: Any) -> str:
    """Keep only Subject Index content and strip common LLM reasoning leakage.

    This is intentionally conservative: if a clear Subject Index section is found,
    return that section; otherwise fall back to the cleaned original text.
    """
    cleaned = sanitize_llm_markdown_output(str(text or ""))
    if not cleaned:
        return ""

    delimiter = "----------------*****--------------"
    delimiter_idx = cleaned.find(delimiter)
    if delimiter_idx >= 0:
        cleaned = cleaned[delimiter_idx + len(delimiter):].strip()
        if not cleaned:
            return ""

    lines = [str(line or "") for line in cleaned.splitlines()]
    if not lines:
        return ""

    subject_header_re = re.compile(
        r"(?i)^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:subject\s*index|subjects\s*index|资产清单|实体清单|设计资产索引)\b"
    )
    subject_hint_re = re.compile(r"(?i)subject_no|subject_type|script_entity_coverage")
    row_start_re = re.compile(r"(?i)^\s*\|?\s*S\d+\s*\|")
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
        return ""

    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        stripped = lines[idx].strip()
        if re.match(r"^#{1,6}\s+", stripped):
            end_idx = idx
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

    result = "\n".join(filtered_lines).strip()
    if result:
        # Normalize glued rows like: ...S001...S002... into one row per line.
        result = re.sub(r"(?<!^)\s*(?=S\d{3,})", "\n", result)
        result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result or ""
