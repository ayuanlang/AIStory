import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASELINE_PATH = Path(settings.BASE_DIR) / "app" / "data" / "agent_tool_billing_baseline.json"

_AGENT_TOOL_TO_BASELINE_KEY: Dict[str, str] = {
    "generate_project_asset": "image.generate.sync",
    "generate_image_text_to_image": "image.generate.sync",
    "generate_image_image_to_image": "image.generate.sync",
    "generate_video_text_to_video": "video.generate.sync",
    "generate_video_image_to_video": "video.generate.sync",
    "analyze_script": "story.script.llm_ops",
    "update_project_metadata": "project.metadata.update",
    "search_project_data": "tool.search_project_data",
    "internet_search": "tool.internet_search",
    "visualize_user_requirement": "tool.visualize_user_requirement",
}


class ToolBillingTaxonomyService:
    @lru_cache(maxsize=1)
    def _load_entries_cached(self) -> List[Dict[str, Any]]:
        if not _BASELINE_PATH.exists():
            logger.warning("Tool billing baseline file not found: %s", _BASELINE_PATH)
            return []

        try:
            with _BASELINE_PATH.open("r", encoding="utf-8") as handle:
                parsed = json.load(handle)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
        except Exception as exc:
            logger.error("Failed to load tool billing baseline from %s: %s", _BASELINE_PATH, exc)

        return []

    def get_entries(self) -> List[Dict[str, Any]]:
        return self._load_entries_cached()

    def get_entry_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        target = str(key or "").strip()
        if not target:
            return None
        for item in self.get_entries():
            if str(item.get("key") or "").strip() == target:
                return item
        return None

    def get_billable_source_categories_by_task_type(self) -> Dict[str, List[str]]:
        out: Dict[str, set] = {}
        for item in self.get_entries():
            if not bool(item.get("billable")):
                continue
            task_type = str(item.get("default_task_type") or "").strip()
            if not task_type or task_type.lower() == "none":
                continue
            out.setdefault(task_type, set())
            for category in item.get("source_categories") or []:
                category_text = str(category or "").strip()
                if category_text:
                    out[task_type].add(category_text)

        return {task_type: sorted(list(categories)) for task_type, categories in out.items()}

    def get_billable_task_types_for_source_category(self, category: str) -> List[str]:
        target = str(category or "").strip().lower()
        if not target:
            return []

        source_by_task = self.get_billable_source_categories_by_task_type()
        task_types: List[str] = []
        for task_type, categories in source_by_task.items():
            normalized_categories = {str(item or "").strip().lower() for item in (categories or [])}
            if target in normalized_categories:
                task_types.append(task_type)

        return sorted(list(dict.fromkeys(task_types)))

    def resolve_agent_tool_task_type(self, tool_name: str, fallback: Optional[str] = None) -> Optional[str]:
        baseline_key = _AGENT_TOOL_TO_BASELINE_KEY.get(str(tool_name or "").strip())
        if baseline_key:
            entry = self.get_entry_by_key(baseline_key)
            if entry:
                task_type = str(entry.get("default_task_type") or "").strip()
                if task_type and task_type.lower() != "none":
                    return task_type
        return fallback


tool_billing_taxonomy_service = ToolBillingTaxonomyService()
