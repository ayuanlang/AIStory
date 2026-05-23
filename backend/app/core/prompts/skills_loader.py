import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_PROMPTS_ROOT = Path(settings.BASE_DIR) / "app" / "core" / "prompts"
_SKILLS_ROOT = _PROMPTS_ROOT / "skills"
_REGISTRY_PATH = _SKILLS_ROOT / "skills_registry.json"


@lru_cache(maxsize=1)
def load_skills_registry() -> Dict[str, Any]:
    if not _REGISTRY_PATH.exists():
        logger.warning("skills registry not found: %s", _REGISTRY_PATH)
        return {"version": 1, "skills": []}

    try:
        with _REGISTRY_PATH.open("r", encoding="utf-8") as handle:
            parsed = json.load(handle)
        if isinstance(parsed, dict):
            skills = parsed.get("skills") if isinstance(parsed.get("skills"), list) else []
            return {
                "version": parsed.get("version", 1),
                "skills": [item for item in skills if isinstance(item, dict)],
            }
    except Exception as exc:
        logger.error("failed to load skills registry: %s", exc)

    return {"version": 1, "skills": []}


def list_skill_ids() -> List[str]:
    out: List[str] = []
    for item in load_skills_registry().get("skills", []):
        skill_id = str(item.get("id") or "").strip()
        if skill_id:
            out.append(skill_id)
    return out


def get_skill_meta(skill_id: str) -> Optional[Dict[str, Any]]:
    target = str(skill_id or "").strip()
    if not target:
        return None
    for item in load_skills_registry().get("skills", []):
        if str(item.get("id") or "").strip() == target:
            return item
    return None


def get_skill_prompt_text(skill_id: str, prompt_name: str = "system_prompt.txt") -> Optional[str]:
    target = str(skill_id or "").strip()
    file_name = str(prompt_name or "").strip() or "system_prompt.txt"
    if not target:
        return None

    skill_file = _SKILLS_ROOT / target / file_name
    if skill_file.exists():
        try:
            return skill_file.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("failed reading skill prompt %s: %s", skill_file, exc)

    meta = get_skill_meta(target)
    if not meta:
        return None

    prompt_refs = meta.get("prompts") if isinstance(meta.get("prompts"), list) else []

    # Prefer refs that match requested prompt_name, then fall back to other refs.
    requested_name = Path(file_name).name.lower()
    prioritized_refs: List[str] = []
    fallback_refs: List[str] = []
    for ref in prompt_refs:
        ref_text = str(ref or "").strip()
        if not ref_text:
            continue
        ref_name = Path(ref_text).name.lower()
        if ref_name == requested_name:
            prioritized_refs.append(ref_text)
        else:
            fallback_refs.append(ref_text)

    for ref_text in prioritized_refs + fallback_refs:
        ref_text = str(ref_text or "").strip()
        if not ref_text:
            continue

        candidate = _PROMPTS_ROOT / ref_text
        if not candidate.exists() and "/" not in ref_text and "\\" not in ref_text:
            candidate = _PROMPTS_ROOT / ref_text

        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except Exception as exc:
                logger.error("failed reading fallback prompt %s: %s", candidate, exc)

    return None
