# -*- coding: utf-8 -*-
"""Parse/audit [EMERGENCY_RECOVERY_BLOCK_*] in episode scripts."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

EMERGENCY_RECOVERY_BLOCK_START = "[EMERGENCY_RECOVERY_BLOCK_START]"
EMERGENCY_RECOVERY_BLOCK_END = "[EMERGENCY_RECOVERY_BLOCK_END]"
BRIDGE_BLOCK_START = "[BRIDGE_BLOCK_START]"
BRIDGE_BLOCK_END = "[BRIDGE_BLOCK_END]"

_START_RE = re.compile(r"\[\s*EMERGENCY_RECOVERY_BLOCK_START\s*\]", re.IGNORECASE)
_END_RE = re.compile(r"\[\s*EMERGENCY_RECOVERY_BLOCK_END\s*\]", re.IGNORECASE)
_BRIDGE_START_RE = re.compile(r"\[\s*BRIDGE_BLOCK_START\s*\]", re.IGNORECASE)
_BRIDGE_END_RE = re.compile(r"\[\s*BRIDGE_BLOCK_END\s*\]", re.IGNORECASE)
_APPLICABLE_RE = re.compile(r"适用\s*=\s*(有上集|无上集)", re.IGNORECASE)
_ITEM_RE = re.compile(r"^#项\s*\d+\s*[：:]", re.MULTILINE)
_ITEM_NA_RE = re.compile(r"^#项\s*[：:]\s*(无紧急项|N/?A)", re.MULTILINE | re.IGNORECASE)
_FULFILL_RE = re.compile(
    r"兑现\s*=\s*(EP\d{2}_SC\d{2})\s*@\s*Beat\s*\d+",
    re.IGNORECASE,
)
_STATUS_DONE_RE = re.compile(r"状态\s*=\s*已兑现")
_SUMMARY_RE = re.compile(r"^#集级\s*[：:]", re.MULTILINE)
_SELF_CHECK_PASS_RE = re.compile(r"自检\s*=\s*通过")


def _extract_marked_span(
    text: str,
    start_re: "re.Pattern[str]",
    end_re: "re.Pattern[str]",
    *,
    include_markers: bool = False,
) -> Optional[str]:
    raw = str(text or "")
    start = start_re.search(raw)
    if not start:
        return None
    end = end_re.search(raw, start.end())
    if not end:
        return None
    if include_markers:
        return raw[start.start() : end.end()].strip()
    return raw[start.end() : end.start()].strip()


def extract_emergency_recovery_block(text: str, *, include_markers: bool = False) -> Optional[str]:
    return _extract_marked_span(text, _START_RE, _END_RE, include_markers=include_markers)


def extract_bridge_block(text: str, *, include_markers: bool = False) -> Optional[str]:
    return _extract_marked_span(text, _BRIDGE_START_RE, _BRIDGE_END_RE, include_markers=include_markers)


def extract_previous_episode_tail_context(text: str, *, max_chars: int = 1200) -> str:
    """Prefer ending-hook / handoff sections; fall back to script tail."""
    raw = str(text or "").strip()
    if not raw:
        return ""

    # Prefer content after SCENES_BLOCK_END (hooks / handoff / footer blocks live there).
    scenes_end = re.search(r"\[\s*SCENES_BLOCK_END\s*\]", raw, flags=re.IGNORECASE)
    if scenes_end:
        after = raw[scenes_end.end() :].strip()
        # Drop already-extracted footer blocks from the prose tail to reduce duplication.
        after = _START_RE.sub("", after)
        after = _END_RE.sub("", after)
        after = _BRIDGE_START_RE.sub("", after)
        after = _BRIDGE_END_RE.sub("", after)
        after = re.sub(r"━{8,}", "", after)
        after = re.sub(r"\n{3,}", "\n\n", after).strip()
        if after:
            return after[-max_chars:] if len(after) > max_chars else after

    return raw[-max_chars:] if len(raw) > max_chars else raw


def build_previous_episode_handoff_prompt_block(
    previous_script: str,
    *,
    previous_episode_number: int,
    current_episode_number: int,
) -> Dict[str, Any]:
    """
    Build user-prompt handoff from previous episode footer blocks.

    Returns dict with prompt_block + presence flags for logging.
    """
    prev_n = int(previous_episode_number)
    cur_n = int(current_episode_number)
    recovery = extract_emergency_recovery_block(previous_script, include_markers=True)
    bridge = extract_bridge_block(previous_script, include_markers=True)
    tail = extract_previous_episode_tail_context(previous_script)

    missing: List[str] = []
    if not recovery:
        missing.append("EMERGENCY_RECOVERY_BLOCK")
    if not bridge:
        missing.append("BRIDGE_BLOCK")

    parts: List[str] = [
        "Previous Episode Handoff (Hard Constraint — MUST consume before writing):\n",
        f"- Source: Episode {prev_n} → writing Episode {cur_n}.\n",
        "- Read and use BOTH structured blocks below (when present):\n",
        "  1) Previous EMERGENCY_RECOVERY_BLOCK: inherit `#延后` unfinished items; do NOT re-solve already `状态=已兑现` items as if still open; "
        "combine with Previous Ending Tail / 结尾钩子 / Carry-out to build THIS episode's emergency-recovery list.\n",
        "  2) Previous BRIDGE_BLOCK: continue/contrast trope motifs; avoid mindless repeat; localize upgrades; "
        "do NOT treat its `回收=` as this episode's emergency-recovery checklist.\n",
        "- Then write THIS episode's own EMERGENCY_RECOVERY_BLOCK + BRIDGE_BLOCK at the end.\n",
    ]
    if missing:
        parts.append(
            f"- WARNING: previous episode missing structured block(s): {', '.join(missing)}. "
            "Fall back to Ending Tail + Global Story DNA Carry-in/Hook Ledger; do not invent a contradiction.\n"
        )

    parts.append("\n### Previous EMERGENCY_RECOVERY_BLOCK\n")
    if recovery:
        parts.append("```markdown\n")
        parts.append(recovery)
        parts.append("\n```\n")
    else:
        parts.append("(missing)\n")

    parts.append("\n### Previous BRIDGE_BLOCK\n")
    if bridge:
        parts.append("```markdown\n")
        parts.append(bridge)
        parts.append("\n```\n")
    else:
        parts.append("(missing)\n")

    parts.append("\n### Previous Ending Tail (hooks / Carry-out / post-scenes prose)\n")
    if tail:
        parts.append("```markdown\n")
        parts.append(tail)
        parts.append("\n```\n\n")
    else:
        parts.append("(empty)\n\n")

    return {
        "prompt_block": "".join(parts),
        "has_emergency_recovery_block": bool(recovery),
        "has_bridge_block": bool(bridge),
        "has_ending_tail": bool(tail),
        "missing_blocks": missing,
    }


def audit_emergency_recovery_block(
    text: str,
    *,
    episode_number: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Audit episode-script footer block.

    Does not raise; returns ok/issues for logging + episode_info diagnostics.
    Callers may hard-reject when episode_number >= 2 and ok is False.
    """
    issues: List[str] = []
    ep_num = int(episode_number) if episode_number else None
    has_prior_episode = bool(ep_num and ep_num > 1)
    body = extract_emergency_recovery_block(text)
    if body is None:
        raw = str(text or "")
        if _START_RE.search(raw) and not _END_RE.search(raw):
            issues.append("missing_end_marker")
        elif _END_RE.search(raw) and not _START_RE.search(raw):
            issues.append("missing_start_marker")
        else:
            issues.append("block_missing")
        return {
            "ok": False,
            "present": False,
            "applicable": None,
            "item_count": 0,
            "issues": issues,
            "expects_recovery": has_prior_episode,
            "hard_required": has_prior_episode,
        }

    applicable_match = _APPLICABLE_RE.search(body)
    applicable = applicable_match.group(1) if applicable_match else None
    if not applicable:
        issues.append("missing_applicable")

    expects_recovery = False
    if applicable == "有上集":
        expects_recovery = True
    elif applicable == "无上集":
        expects_recovery = False
        if has_prior_episode:
            # EP02+ always has a prior episode in the series; forbid N/A shortcut.
            issues.append("prior_episode_marked_none")
            expects_recovery = True
    elif has_prior_episode:
        expects_recovery = True
        issues.append("applicable_unspecified_assumed_prior_episode")

    item_lines = _ITEM_RE.findall(body)
    item_na = bool(_ITEM_NA_RE.search(body))
    item_count = len(item_lines)

    if expects_recovery:
        if item_count == 0 and not item_na:
            issues.append("missing_items")
        for m in _ITEM_RE.finditer(body):
            # take the rest of the line for field checks
            line_start = m.start()
            line_end = body.find("\n", line_start)
            line = body[line_start:] if line_end < 0 else body[line_start:line_end]
            if not _FULFILL_RE.search(line):
                issues.append("item_missing_scene_beat_fulfillment")
            if not _STATUS_DONE_RE.search(line):
                issues.append("item_not_marked_fulfilled")
        if not _SUMMARY_RE.search(body):
            issues.append("missing_summary_line")
        elif not _SELF_CHECK_PASS_RE.search(body):
            issues.append("self_check_not_pass")
    else:
        if not _SUMMARY_RE.search(body) and not item_na:
            # allow minimal N/A form
            if "N/A" not in body and "n/a" not in body.lower():
                issues.append("no_prior_episode_form_incomplete")

    # de-dupe issues while preserving order
    seen = set()
    unique_issues: List[str] = []
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            unique_issues.append(issue)

    return {
        "ok": len(unique_issues) == 0,
        "present": True,
        "applicable": applicable,
        "item_count": item_count,
        "item_na": item_na,
        "issues": unique_issues,
        "expects_recovery": expects_recovery,
        "hard_required": has_prior_episode,
    }


def format_emergency_recovery_reject_message(
    audit: Dict[str, Any],
    *,
    episode_number: int,
) -> str:
    issues = audit.get("issues") if isinstance(audit, dict) else None
    issue_text = ", ".join(str(x) for x in (issues or [])) or "unknown"
    return (
        f"EMERGENCY_RECOVERY_BLOCK rejected for episode {int(episode_number)}: {issue_text}. "
        "EP>=2 requires [EMERGENCY_RECOVERY_BLOCK_START]…[EMERGENCY_RECOVERY_BLOCK_END] "
        "with 适用=有上集 and fulfilled scene@Beat items (or #项:无紧急项). Import blocked."
    )
