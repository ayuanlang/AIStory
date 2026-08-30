# -*- coding: utf-8 -*-
"""Parse/audit [EMERGENCY_RECOVERY_BLOCK_*] in episode scripts.

Semantics (episode writer contract):
- Footer EMERGENCY_RECOVERY_BLOCK = pending items for the NEXT episode to urgently resolve
  (handoff inject). Not proof of what THIS episode already solved.
- Proof of resolving previous pending items lives in 类型执行摘要「上集紧急回收核销块」.
"""
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
# New contract: 有下集|末集无下集. Legacy 有上集|无上集 still parsed for migration diagnostics.
_APPLICABLE_RE = re.compile(r"适用\s*=\s*(有下集|末集无下集|有上集|无上集)", re.IGNORECASE)
_ITEM_RE = re.compile(r"^#项\s*\d+\s*[：:]", re.MULTILINE)
_ITEM_NA_RE = re.compile(
    r"^#项\s*[：:]\s*(无紧急待核销|无紧急项|N/?A)",
    re.MULTILINE | re.IGNORECASE,
)
_STATUS_PENDING_RE = re.compile(r"状态\s*=\s*待下集核销")
_STATUS_DONE_RE = re.compile(r"状态\s*=\s*已兑现")
_SUMMARY_RE = re.compile(r"^#集级\s*[：:]", re.MULTILINE)
_SELF_CHECK_PASS_RE = re.compile(r"自检\s*=\s*通过")
_PENDING_FIELD_RE = re.compile(r"紧急待核销\s*=")
_LOGLINE_RE = re.compile(r"^#剧情一句话(?:与交接)?\s*[：:]", re.MULTILINE)
_HOOK_RE = re.compile(r"^#结尾钩子\s*[：:]", re.MULTILINE)
_SCENE_RE = re.compile(r"^#当前场景\s*[=＝：:]", re.MULTILINE)
_ENV_RE = re.compile(r"^#当前主环境\s*[=＝：:]", re.MULTILINE)
_COMBINED_SCENE_ENV_RE = re.compile(
    r"^#当前场景\s*[=＝：:].*(?:主环境|当前主环境)\s*[=＝：:]",
    re.MULTILINE,
)
_OPENING_RE = re.compile(r"^#下集开局\s*[=＝：:]", re.MULTILINE)
_OPENING_MODE_RE = re.compile(
    r"^#下集开局\s*[=＝：:]\s*(开新场景|复场续完|N/?A|末集收束)",
    re.MULTILINE | re.IGNORECASE,
)
_REUSE_ENV_RE = re.compile(r"复用主环境\s*[=＝：:]\s*\S+")


def _keyed_line_has_substance(body: str, pattern: "re.Pattern[str]") -> bool:
    for match in pattern.finditer(body):
        line_end = body.find("\n", match.start())
        rest = (body[match.end() :] if line_end < 0 else body[match.end() : line_end]).strip()
        if len(rest) >= 2 and rest not in {"...", "…"}:
            return True
    return False


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
        recovery_full = extract_emergency_recovery_block(after, include_markers=True)
        if recovery_full:
            after = after.replace(recovery_full, "")
        bridge_full = extract_bridge_block(after, include_markers=True)
        if bridge_full:
            after = after.replace(bridge_full, "")
        after = _START_RE.sub("", after)
        after = _END_RE.sub("", after)
        after = _BRIDGE_START_RE.sub("", after)
        after = _BRIDGE_END_RE.sub("", after)
        after = re.sub(r"━{8,}", "", after)
        after = re.sub(r"\n{3,}", "\n\n", after).strip()
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
        "  1) Previous EMERGENCY_RECOVERY_BLOCK = THIS episode's opening handoff container. "
        "It includes `#剧情一句话与交接`, `#结尾钩子`, `#当前场景`, `#当前主环境`, `#下集开局`, plus PENDING `#项` "
        "THIS episode must resolve in opening/early scenes (待本集紧急核销). "
        "Opening scene rule (Hard Constraint): `#下集开局` defaults to `开新场景` — "
        "first Scene MUST be a NEW scene (new EPxx_SCyy; prefer a new space/cut), not a silent continuation of the previous Scene. "
        "ONLY if `#下集开局=复场续完` may the first Scene stay in the same space, and then "
        "`主环境=` MUST reuse `#当前主环境` / `复用主环境=` character-for-character (`复用=复场续完`). "
        "Prove `#项` resolution in 类型执行摘要「上集紧急回收核销块」 "
        "with `兑现=scene_id@Beat` + `状态=已兑现`. Do NOT treat `#项` as 'already solved'.\n",
        "  2) Previous BRIDGE_BLOCK (optional; newer drafts omit it from the script page): "
        "if present, continue/contrast trope motifs; do NOT treat its `回收=` as emergency-recovery.\n",
        "- Then: (a) write resolved proof in 类型执行摘要; "
        "(b) write THIS episode's footer EMERGENCY_RECOVERY_BLOCK = 剧情一句话与交接 + 结尾钩子 + "
        "当前场景/主环境 + `#下集开局=开新场景|复场续完` + NEW pending `#项` for the NEXT episode "
        "(`状态=待下集核销`). Prefer `开新场景`. Do not write BRIDGE_BLOCK into the official script page.\n",
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

    parts.append(
        "\n### Previous Ending Tail (legacy standalone 剧情一句话 / 结尾钩子 if still outside the block)\n"
    )
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
    Audit episode-script footer pending-handoff block.

    Does not raise; returns ok/issues for logging + episode_info diagnostics.
    Callers may hard-reject when episode_number >= 2 and ok is False.
    """
    issues: List[str] = []
    ep_num = int(episode_number) if episode_number else None
    # EP>=2 always has a prior episode; footer must still exist as outgoing handoff.
    hard_required = bool(ep_num and ep_num > 1)
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
            "expects_pending_handoff": True,
            "hard_required": hard_required,
        }

    applicable_match = _APPLICABLE_RE.search(body)
    applicable = applicable_match.group(1) if applicable_match else None
    if not applicable:
        issues.append("missing_applicable")

    # Legacy footer wrote resolved-proof (有上集 + 已兑现). Reject that shape for the footer.
    legacy_resolved_shape = applicable in {"有上集", "无上集"} or bool(_STATUS_DONE_RE.search(body))
    if legacy_resolved_shape and applicable not in {"有下集", "末集无下集"}:
        issues.append("legacy_resolved_proof_in_footer")

    expects_pending_items = False
    if applicable == "有下集":
        expects_pending_items = True
    elif applicable == "末集无下集":
        expects_pending_items = False
    elif applicable == "无上集":
        # Old EP01 form — treat as incomplete under new contract.
        expects_pending_items = True
        issues.append("legacy_applicable_no_prior")
    elif applicable == "有上集":
        expects_pending_items = True
        issues.append("legacy_applicable_has_prior")
    else:
        # Unspecified: still require a pending-handoff shape.
        expects_pending_items = True

    item_lines = _ITEM_RE.findall(body)
    item_na = bool(_ITEM_NA_RE.search(body))
    item_count = len(item_lines)

    if not _keyed_line_has_substance(body, _LOGLINE_RE):
        issues.append("missing_logline_handoff")
    if not _keyed_line_has_substance(body, _HOOK_RE):
        issues.append("missing_ending_hook")
    if not _keyed_line_has_substance(body, _SCENE_RE):
        issues.append("missing_current_scene")
    if not (
        _keyed_line_has_substance(body, _ENV_RE)
        or _keyed_line_has_substance(body, _COMBINED_SCENE_ENV_RE)
    ):
        issues.append("missing_current_env")

    opening_match = _OPENING_MODE_RE.search(body)
    opening_mode = (opening_match.group(1) if opening_match else "").strip()

    if expects_pending_items:
        if not _keyed_line_has_substance(body, _OPENING_RE):
            issues.append("missing_next_opening")
        elif not opening_mode:
            issues.append("invalid_next_opening")
        elif opening_mode == "复场续完" and not _REUSE_ENV_RE.search(body):
            issues.append("missing_reuse_env_on_continue")
        if item_count == 0 and not item_na:
            issues.append("missing_items")
        for m in _ITEM_RE.finditer(body):
            line_start = m.start()
            line_end = body.find("\n", line_start)
            line = body[line_start:] if line_end < 0 else body[line_start:line_end]
            if _STATUS_DONE_RE.search(line):
                issues.append("item_marked_fulfilled_in_pending_block")
            if not _STATUS_PENDING_RE.search(line) and not _PENDING_FIELD_RE.search(line):
                # Allow `#项:无紧急待核销` via item_na path; numbered items need pending markers.
                issues.append("item_missing_pending_markers")
        if not _SUMMARY_RE.search(body):
            issues.append("missing_summary_line")
        elif not _SELF_CHECK_PASS_RE.search(body):
            issues.append("self_check_not_pass")
    else:
        if not _SUMMARY_RE.search(body) and not item_na:
            if "N/A" not in body and "n/a" not in body.lower():
                issues.append("finale_form_incomplete")

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
        "expects_pending_handoff": expects_pending_items,
        "hard_required": hard_required,
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
        "Footer block must include #剧情一句话与交接, #结尾钩子, #当前场景, #当前主环境, "
        "#下集开局=开新场景|复场续完 (复场续完须锁 复用主环境=), "
        "and pending items for the NEXT episode "
        "([EMERGENCY_RECOVERY_BLOCK_START]…END, 适用=有下集|末集无下集, "
        "状态=待下集核销 or #项:无紧急待核销). "
        "Resolved proof belongs in 类型执行摘要, not this footer. Import blocked."
    )
