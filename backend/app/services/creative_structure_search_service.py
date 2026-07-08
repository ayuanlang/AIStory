from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.story_trend_search_service import (
    DEFAULT_LIMIT_PER_QUERY,
    _collect_search_snippets_for_queries,
)


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


def build_creative_structure_search_queries(key_elements: Dict[str, Any]) -> List[str]:
    queries: List[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        q = " ".join(str(query or "").split()).strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    for term in _as_str_list(key_elements.get("classic_scene_search_terms"), limit=4):
        add(f"{term} 经典名场面 影视 短剧")
        add(f"{term} classic iconic scene film drama")
    for term in _as_str_list(key_elements.get("trope_search_terms"), limit=4):
        add(f"{term} 短剧 热门桥段 套路")
        add(f"{term} short drama popular trope plot beat")
    for term in _as_str_list(key_elements.get("hot_topic_search_terms"), limit=4):
        add(f"{term} 短剧 热门话题 热搜")
        add(f"{term} micro drama trending topic")

    for genre in _as_str_list(key_elements.get("genres"), limit=3):
        add(f"{genre} 经典名场面 电影")
        add(f"{genre} 短剧 热门桥段")
    for hook in _as_str_list(key_elements.get("conflict_hooks"), limit=3):
        add(f"{hook} 短剧 悬疑 桥段")
    for work in _as_str_list(key_elements.get("reference_works"), limit=2):
        add(f"{work} 经典名场面 热门桥段")

    tone = str(key_elements.get("tone_style") or "").strip()
    if tone:
        add(f"{tone} 短剧 热门话题 风格")

    if not queries:
        add("短剧 经典名场面 悬疑 反转")
        add("短剧 热门桥段 套路 悬疑")
        add("短剧 热门话题 热搜")

    return queries[:18]


async def collect_creative_structure_search_snippets(
    key_elements: Dict[str, Any],
    *,
    limit_per_query: int = DEFAULT_LIMIT_PER_QUERY,
) -> Dict[str, Any]:
    queries = build_creative_structure_search_queries(key_elements)
    return await _collect_search_snippets_for_queries(
        queries,
        limit_per_query=limit_per_query,
        report_kind="creative_structure",
    )


def build_creative_structure_search_user_prompt(
    search_bundle: Dict[str, Any],
    key_elements: Dict[str, Any],
    *,
    project_title: str = "",
    language: str = "",
) -> str:
    lines = [
        "Reference Research Focus: classic iconic scenes, popular drama tropes/plot beats, and hot topics relevant to the brainstorm.",
        f"Project Title: {project_title or '(none)'}",
        f"Preferred Language: {language or 'zh'}",
        "Extracted Key Elements:",
    ]
    for key in (
        "genres",
        "themes",
        "character_archetypes",
        "conflict_hooks",
        "signature_scenes",
        "tone_style",
        "reference_works",
        "classic_scene_search_terms",
        "trope_search_terms",
        "hot_topic_search_terms",
    ):
        value = key_elements.get(key)
        if isinstance(value, list):
            rendered = ", ".join(str(v).strip() for v in value if str(v).strip())
        else:
            rendered = str(value or "").strip()
        if rendered:
            lines.append(f"- {key}: {rendered}")
    lines.append("")
    lines.append("Web Search Snippets:")
    for idx, item in enumerate(search_bundle.get("snippets") or [], start=1):
        if not isinstance(item, dict):
            continue
        snippet = str(item.get("snippet") or "").strip()
        if not snippet:
            continue
        lines.extend(
            [
                f"[{idx}] Query: {item.get('query', '')}",
                f"Title: {item.get('title', '')}",
                f"Summary: {snippet}",
                f"URL: {item.get('url', '')}",
                "",
            ]
        )
    if search_bundle.get("instant_notes"):
        lines.append("")
        lines.append("Instant Search Notes:")
        for idx, note in enumerate(search_bundle.get("instant_notes") or [], start=1):
            if not isinstance(note, dict):
                continue
            lines.append(f"{idx}. [{note.get('query', '')}] {note.get('text', '')}")
    return "\n".join(lines).strip()
