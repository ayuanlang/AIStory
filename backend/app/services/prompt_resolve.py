# -*- coding: utf-8 -*-
"""Prompt file / skill resolution helpers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.prompt_injection import attach_skill_watermarks
from app.core.prompts.skills_loader import get_skill_meta, get_skill_prompt_text

_PROMPT_SKILL_ALIAS = {
    "scene_analysis.txt": "skill:scene_analysis/scene_analysis.txt",
    "subject_generation.txt": "subject_generation.txt",
    "story_generator_global.txt": "skill:story_generation/story_generator_global.txt",
    "story_generator_episode.txt": "skill:story_generation/story_generator_episode.txt",
    "story_generator_analyze_novel.txt": "skill:story_generation/story_generator_analyze_novel.txt",
    "story_generator_structure_creative_input.txt": "skill:story_generation/story_generator_structure_creative_input.txt",
    "story_generator_structure_extract_key_elements.txt": "skill:story_generation/story_generator_structure_extract_key_elements.txt",
    "story_generator_trending_ai_short_dramas.txt": "skill:story_generation/story_generator_trending_ai_short_dramas.txt",
    "story_generator_industry_analysis_ai_short_dramas.txt": "skill:story_generation/story_generator_industry_analysis_ai_short_dramas.txt",
    "script_generator_scenes.txt": "skill:script_generation/script_generator_scenes.txt",
    "script_generator_episode_script.txt": "master_episode_writer.md",
    "scene_regenerate.txt": "skill:script_generation/scene_regenerate.txt",
    "shot_generator.txt": "skills/shot_generation.md",
    "shot_regenerate.txt": "shot_regenerate.txt",
    "promo_generator_global.txt": "skill:promo_generation/promo_generator_global.txt",
    "promo_generator_episode_script.txt": "master_episode_writer.md",
    "image_style_extractor.txt": "skill:image_style_extraction/image_style_extractor.txt",
    "voice_tts_planner_system.txt": "voice_tts_planner_system.txt",
    "voice_tts_planner_user.txt": "voice_tts_planner_user.txt",
    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_vfx.md": (
        "skills/scene_analysis_feature_stack/scene_planning_1_subskill_combat.md"
    ),
    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_xian_attack.md": (
        "skills/scene_analysis_feature_stack/scene_planning_1_subskill_combat.md"
    ),
    "scene_planning_1_subskill_vfx.md": "skills/scene_analysis_feature_stack/scene_planning_1_subskill_combat.md",
    "scene_planning_1_subskill_xian_attack.md": "skills/scene_analysis_feature_stack/scene_planning_1_subskill_combat.md",
    "skills/scene_analysis_feature_stack/scene_planning_2_1_assets_extraction.md": (
        "skills/scene_analysis_feature_stack/_archive/2026-09-05-retired/scene_planning_2_1_assets_extraction.md"
    ),
    "skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation.md": (
        "skills/scene_analysis_feature_stack/_archive/2026-09-05-retired/scene_planning_2_2_beats_generation.md"
    ),
    "scene_planning_2_1_assets_extraction.md": (
        "skills/scene_analysis_feature_stack/_archive/2026-09-05-retired/scene_planning_2_1_assets_extraction.md"
    ),
    "scene_planning_2_2_beats_generation.md": (
        "skills/scene_analysis_feature_stack/_archive/2026-09-05-retired/scene_planning_2_2_beats_generation.md"
    ),
}

def _prompt_alias(prompt_ref: str) -> str:
    ref = str(prompt_ref or "").strip()
    return str(
        _PROMPT_SKILL_ALIAS.get(ref)
        or _PROMPT_SKILL_ALIAS.get(Path(ref.replace("\\", "/")).name)
        or ""
    ).strip()


def _resolve_prompt_text(prompt_ref: str) -> str:
    ref = str(prompt_ref or "").strip()
    if not ref:
        raise FileNotFoundError("prompt ref is empty")

    candidates = [ref]
    alias = _prompt_alias(ref)
    if alias:
        candidates.append(alias)

    for item in candidates:
        item_text = str(item or "").strip()
        if not item_text:
            continue

        if item_text.startswith("skill:"):
            raw = item_text[len("skill:"):]
            parts = [piece for piece in raw.split("/") if piece]
            skill_id = parts[0] if parts else ""
            prompt_name = parts[1] if len(parts) > 1 else "system_prompt.txt"
            content = get_skill_prompt_text(skill_id, prompt_name)
            if content:
                return attach_skill_watermarks(content, item_text or ref)
            continue

        prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
        prompt_path = os.path.join(prompt_dir, item_text)
        if os.path.isfile(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as handle:
                return attach_skill_watermarks(handle.read(), item_text or ref)

    raise FileNotFoundError(f"Prompt '{prompt_ref}' not found")

def _resolve_prompt_file_path(prompt_ref: str) -> Path:
    ref = str(prompt_ref or "").strip()
    if not ref:
        raise FileNotFoundError("prompt ref is empty")

    prompt_root = Path(settings.BASE_DIR) / "app" / "core" / "prompts"
    skill_root = prompt_root / "skills"
    candidates = [ref]
    alias = _prompt_alias(ref)
    if alias:
        candidates.append(alias)

    prompt_root_resolved = prompt_root.resolve()

    def _ensure_under_prompt_root(candidate: Path) -> Path:
        resolved = candidate.resolve()
        if resolved != prompt_root_resolved and prompt_root_resolved not in resolved.parents:
            raise FileNotFoundError(f"Prompt '{prompt_ref}' resolved outside prompt directory")
        return resolved

    for item in candidates:
        item_text = str(item or "").strip()
        if not item_text:
            continue

        if item_text.startswith("skill:"):
            raw = item_text[len("skill:"):]
            parts = [piece for piece in raw.split("/") if piece]
            skill_id = parts[0] if parts else ""
            prompt_name = parts[1] if len(parts) > 1 else "system_prompt.txt"
            if not skill_id:
                continue

            direct_skill_file = skill_root / skill_id / prompt_name
            if direct_skill_file.is_file():
                return _ensure_under_prompt_root(direct_skill_file)

            meta = get_skill_meta(skill_id)
            prompt_refs = meta.get("prompts") if isinstance(meta, dict) and isinstance(meta.get("prompts"), list) else []
            for fallback_ref in prompt_refs:
                fallback_text = str(fallback_ref or "").strip()
                if not fallback_text:
                    continue
                fallback_path = prompt_root / fallback_text
                if fallback_path.is_file() and (
                    fallback_text == prompt_name
                    or Path(fallback_text).name == prompt_name
                    or fallback_text == raw
                ):
                    return _ensure_under_prompt_root(fallback_path)
            continue

        prompt_path = prompt_root / item_text
        if prompt_path.is_file():
            return _ensure_under_prompt_root(prompt_path)

    raise FileNotFoundError(f"Prompt '{prompt_ref}' not found")

def _build_prompt_resolution_debug(prompt_ref: str) -> Dict[str, Any]:
    ref = str(prompt_ref or "").strip()
    alias = _prompt_alias(ref)
    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    skill_root = os.path.join(prompt_dir, "skills")

    candidates: List[str] = []
    for item in [ref, alias]:
        item_text = str(item or "").strip()
        if item_text and item_text not in candidates:
            candidates.append(item_text)

    out: Dict[str, Any] = {
        "prompt_ref": ref,
        "alias": alias,
        "prompt_dir": prompt_dir,
        "candidates": [],
    }

    for item_text in candidates:
        candidate_info: Dict[str, Any] = {"ref": item_text}
        if item_text.startswith("skill:"):
            raw = item_text[len("skill:"):]
            parts = [piece for piece in raw.split("/") if piece]
            skill_id = parts[0] if parts else ""
            prompt_name = parts[1] if len(parts) > 1 else "system_prompt.txt"
            skill_file = os.path.join(skill_root, skill_id, prompt_name)
            meta = get_skill_meta(skill_id)
            prompt_refs = meta.get("prompts") if isinstance(meta, dict) and isinstance(meta.get("prompts"), list) else []

            fallback_candidates = []
            for fallback_ref in prompt_refs:
                fallback_text = str(fallback_ref or "").strip()
                if not fallback_text:
                    continue
                fallback_path = os.path.join(prompt_dir, fallback_text)
                fallback_candidates.append({
                    "ref": fallback_text,
                    "path": fallback_path,
                    "exists": os.path.isfile(fallback_path),
                })

            candidate_info.update({
                "type": "skill",
                "skill_id": skill_id,
                "prompt_name": prompt_name,
                "direct_path": skill_file,
                "direct_exists": os.path.isfile(skill_file),
                "registry_skill_found": bool(meta),
                "registry_prompt_refs": prompt_refs,
                "fallback_candidates": fallback_candidates,
            })
        else:
            prompt_path = os.path.join(prompt_dir, item_text)
            candidate_info.update({
                "type": "file",
                "path": prompt_path,
                "exists": os.path.isfile(prompt_path),
            })
        out["candidates"].append(candidate_info)

    return out


