#!/usr/bin/env python3
"""Prompt parity checker for scene/subject prompt contracts.

Checks that high-priority environment rules stay synchronized between:
- app/core/prompts/scene_analysis.txt
- app/core/prompts/subject_generation.txt

Exit codes:
- 0: all required checks passed
- 1: one or more checks failed
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import List


SCENE_PATH = Path("app/core/prompts/scene_analysis.txt")
SUBJECT_PATH = Path("app/core/prompts/subject_generation.txt")


@dataclass(frozen=True)
class ClauseCheck:
    name: str
    pattern: str


REQUIRED_CLAUSES: List[ClauseCheck] = [
    ClauseCheck("channel_isolation", r"通道隔离硬规则"),
    ClauseCheck("existing_subject_reuse", r"现有 Subjects 复用硬规则"),
    ClauseCheck("language_payload_rule", r"文字载荷语言规则|生成提示词语言载荷规则"),
    ClauseCheck("environment_variant_specificity", r"环境变体具体化规则"),
    ClauseCheck("environment_state_detailing", r"环境状态细节落点规则"),
    ClauseCheck("wardrobe_state_split", r"着装重大状态变化前置规则"),
    ClauseCheck("wardrobe_implied_signal", r"服装暗示识别规则"),
    ClauseCheck("wardrobe_entity_split", r"换装独立实体强制"),
    ClauseCheck("wardrobe_multi_outfit_ban", r"一角双衣绝对禁令"),
    ClauseCheck("clothing_other_outfits_flag", r"clothing\s*外部衣着声明规则|clothing\s*字段必须同时"),
    ClauseCheck("ots_leakage_guard", r"OTS\s*污染防护"),
    ClauseCheck("ots_environment_isolation", r"OTS\s*环境隔离规则"),
    ClauseCheck("ots_occluder_ban", r"OTS\s*前景遮挡禁令"),
    ClauseCheck("leakage_root_cause_hint", r"泄漏根因提示"),
    ClauseCheck("environment_gate_self_check", r"门禁词自检"),
    ClauseCheck("no_character_hard_rule", r"禁止角色信息（Hard Rule）"),
    ClauseCheck("no_story_hard_rule", r"禁止剧情信息（Hard Rule）"),
    ClauseCheck("environment_no_human_scope", r"No-Human Writing"),
]

# Legacy anti-patterns we do not want in Environment guidance.
FORBIDDEN_PATTERNS: List[ClauseCheck] = [
    ClauseCheck(
        "dynamic_parts_reason",
        r"Dynamic\s+Parts\s+State\s*:[^\n]*(reason\s*:|because|因为)",
    ),
    ClauseCheck(
        "ots_phrase_in_env_example",
        r"generation_prompt_(?:cn|en)[^\n]*over\s*-?the\s*-?shoulder",
    ),
]


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def _count_matches(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def main() -> int:
    try:
        scene_text = _read(SCENE_PATH)
        subject_text = _read(SUBJECT_PATH)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 1

    errors: List[str] = []
    warnings: List[str] = []

    print("Prompt sync check")
    print(f"- Scene:   {SCENE_PATH}")
    print(f"- Subject: {SUBJECT_PATH}")

    for clause in REQUIRED_CLAUSES:
        scene_count = _count_matches(scene_text, clause.pattern)
        subject_count = _count_matches(subject_text, clause.pattern)

        if scene_count == 0:
            errors.append(f"Missing in scene_analysis: {clause.name}")
        if subject_count == 0:
            errors.append(f"Missing in subject_generation: {clause.name}")
        if scene_count > 0 and subject_count > 0 and scene_count != subject_count:
            warnings.append(
                f"Count mismatch for {clause.name}: scene={scene_count}, subject={subject_count}"
            )

    for bad in FORBIDDEN_PATTERNS:
        scene_count = _count_matches(scene_text, bad.pattern)
        subject_count = _count_matches(subject_text, bad.pattern)
        if scene_count > 0:
            errors.append(
                f"Forbidden pattern found in scene_analysis ({bad.name}): {scene_count}"
            )
        if subject_count > 0:
            errors.append(
                f"Forbidden pattern found in subject_generation ({bad.name}): {subject_count}"
            )

    if warnings:
        print("\n[WARNINGS]")
        for item in warnings:
            print(f"- {item}")

    if errors:
        print("\n[FAILED]")
        for item in errors:
            print(f"- {item}")
        return 1

    print("\n[PASS] Required scene/subject prompt sync checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
