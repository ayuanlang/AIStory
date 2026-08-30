from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.story_trend_search_service import (
    DEFAULT_LIMIT_PER_QUERY,
    MAX_ENRICH_PER_QUERY,
    _collect_search_snippets_for_queries,
    format_search_evidence_lines,
    resolve_enrich_top_k,
)

CREATIVE_STRUCTURE_LIMIT_PER_QUERY = max(DEFAULT_LIMIT_PER_QUERY, 12)
CREATIVE_STRUCTURE_MAX_QUERIES = 36
CREATIVE_STRUCTURE_MAX_ENRICH = max(MAX_ENRICH_PER_QUERY, 6)


def _as_str_list(value: Any, *, limit: int = 8) -> List[str]:
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

    def add_iconic_climax_pack(term: str) -> None:
        add(f"{term} 经典名场面 高潮 影视")
        add(f"{term} 短剧 名场面 反转 高潮")
        add(f"{term} 经典镜头 画面 构图 电影")
        add(f"{term} 经典对白 台词 名场面")
        add(f"{term} 动作场面 走位 冲突 影视")
        add(f"{term} iconic climax scene film drama")

    def add_classic_work_pack(work: str) -> None:
        add(f"{work} 核心剧情 经典桥段 名场面")
        add(f"{work} 特效 视觉风格 动作场面 经典对白")
        add(f"{work} plot summary iconic scene style dialogue")

    for work in _as_str_list(key_elements.get("plot_framework_candidates"), limit=3):
        add_classic_work_pack(work)
    for work in _as_str_list(key_elements.get("auxiliary_reference_works"), limit=3):
        add(f"{work} 经典桥段 风格 对白 动作")
        add(f"{work} iconic set piece style dialogue action")
    for term in _as_str_list(key_elements.get("plot_framework_search_terms"), limit=4):
        add(f"{term} 当代 现代 电影 电视剧 小说 游戏 剧情框架")
        add(f"{term} 近二十年 经典 影视 剧情逻辑")
        add(f"{term} 跨类型 古代 宫廷 仙侠 改编 剧情逻辑")
        add(f"{term} contemporary modern film tv novel game plot framework")
        add(f"{term} plot structure transplanted period palace xianxia")
    for term in _as_str_list(key_elements.get("classic_content_search_terms"), limit=3):
        add(f"{term} 经典作品 核心剧情 桥段 特效 风格")
        add(f"{term} 剧情逻辑 桥段功能 跨风格转译")
        add(f"{term} classic work plot set piece vfx style dialogue")

    for term in _as_str_list(key_elements.get("iconic_scene_search_terms"), limit=5):
        add_iconic_climax_pack(term)
    for term in _as_str_list(key_elements.get("climax_search_terms"), limit=5):
        add(f"{term} 高潮场面 经典 电影 短剧")
        add(f"{term} climax scene iconic moment drama")
    for term in _as_str_list(key_elements.get("dialogue_search_terms"), limit=4):
        add(f"{term} 经典台词 对白 名场面 电影")
        add(f"{term} famous dialogue line film scene")
    for term in _as_str_list(key_elements.get("action_visual_search_terms"), limit=4):
        add(f"{term} 经典动作场面 镜头 影视")
        add(f"{term} visual composition iconic shot film")

    for scene in _as_str_list(key_elements.get("climax_moments"), limit=4):
        add_iconic_climax_pack(scene)
    for scene in _as_str_list(key_elements.get("signature_scenes"), limit=4):
        add_iconic_climax_pack(scene)

    for term in _as_str_list(key_elements.get("classic_scene_search_terms"), limit=4):
        add_iconic_climax_pack(term)
    for term in _as_str_list(key_elements.get("trope_search_terms"), limit=4):
        add(f"{term} 短剧 热门桥段 高潮 名场面")
        add(f"{term} short drama trope climax beat")
    for term in _as_str_list(key_elements.get("entertainment_search_terms"), limit=4):
        add(f"{term} 经典搞笑 名场面 娱乐化 桥段")
        add(f"{term} funny entertaining trope comedic moments")
    for term in _as_str_list(key_elements.get("hot_topic_search_terms"), limit=3):
        add(f"{term} 短剧 热门话题 名场面")
        add(f"{term} micro drama trending iconic scene")

    for genre in _as_str_list(key_elements.get("genres"), limit=3):
        add(f"{genre} 经典名场面 高潮 电影")
        add(f"{genre} 短剧 名场面 对白 动作")
    for hook in _as_str_list(key_elements.get("conflict_hooks"), limit=3):
        add_iconic_climax_pack(hook)
    for work in _as_str_list(key_elements.get("reference_works"), limit=3):
        add(f"{work} 经典名场面 高潮 对白")
        add(f"{work} iconic scene climax dialogue")

    tone = str(key_elements.get("tone_style") or "").strip()
    if tone:
        add(f"{tone} 影视 名场面 高潮 镜头")

    if not queries:
        add("短剧 经典名场面 高潮 反转")
        add("电影 经典对白 名场面")
        add("影视 经典动作场面 镜头")
        add("短剧 热门桥段 高潮 名场面")

    return queries[:CREATIVE_STRUCTURE_MAX_QUERIES]


async def collect_creative_structure_search_snippets(
    key_elements: Dict[str, Any],
    *,
    limit_per_query: int = CREATIVE_STRUCTURE_LIMIT_PER_QUERY,
) -> Dict[str, Any]:
    queries = build_creative_structure_search_queries(key_elements)
    return await _collect_search_snippets_for_queries(
        queries,
        limit_per_query=limit_per_query,
        max_enrich_per_query=resolve_enrich_top_k(CREATIVE_STRUCTURE_MAX_ENRICH),
        require_informative_snippet=True,
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
        "Reference Research Focus: first lock ONE primary MODERN/CONTEMPORARY work as the PLOT-LOGIC framework (literature / film / TV / game; prefer recent decades, not pre-modern classics as default primary). Cross-style transfer is required: a modern/contemporary engine may serve an ancient/palace/xianxia story. Then auxiliary works (older classics OK only as auxiliaries) with transferable functions. Then climax and iconic scenes; then visuals, dialogue, action blocking, and tropes.",
        "When structuring I10, name real works, extract plot logic (not costumes/era), and write 转译 (source logic → this story's era/style). When structuring I7a/I6c, synthesize image composition, dialogue lines, physical action, emotional peak staging — transcoded to this story, not copied from the source skin.",
        "Consume evidence in priority order: P0 first, then P1, then P2. Prefer Evidence body over URLs.",
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
        "climax_moments",
        "tone_style",
        "reference_works",
        "plot_framework_candidates",
        "auxiliary_reference_works",
        "plot_framework_search_terms",
        "classic_content_search_terms",
        "iconic_scene_search_terms",
        "climax_search_terms",
        "dialogue_search_terms",
        "action_visual_search_terms",
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
    lines.extend(
        format_search_evidence_lines(
            search_bundle.get("snippets") or [],
            include_url=True,
        )
    )
    if search_bundle.get("instant_notes"):
        lines.append("")
        lines.append("Instant Search Notes:")
        for idx, note in enumerate(search_bundle.get("instant_notes") or [], start=1):
            if not isinstance(note, dict):
                continue
            lines.append(f"{idx}. [{note.get('query', '')}] {note.get('text', '')}")
    return "\n".join(lines).strip()
