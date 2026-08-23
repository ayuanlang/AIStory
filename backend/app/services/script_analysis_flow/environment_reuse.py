# -*- coding: utf-8 -*-
"""Scene-split environment identification + project-library reuse helpers."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.core.prompt_injection import wrap_injection_section
from app.models.all_models import Entity, Episode
from app.services.project_episode_utils import (
    _resolve_episode_sort_number,
    _sort_project_episodes,
)
from app.services.soft_delete import _active_entity_clause, _active_episode_clause

logger = logging.getLogger("api_logger")

PROJECT_MAIN_ENV_LABEL = "项目主环境名"
REUSED_DERIVED_ENV_LABEL = "复用衍生环境"
SELECTED_GLOBAL_ENV_LABEL = "用户选定全局环境"

SCENE_ENV_IDENT_START_TOKEN = "[SCENE_ENV_IDENT_START"
SCENE_ENV_IDENT_END_TOKEN = "[SCENE_ENV_IDENT_END"
SCENE_ENV_IDENT_PATTERN = re.compile(
    r"`?\[SCENE_ENV_IDENT_START:([^\s\]]+)\]`?"
    r"(.*?)"
    r"`?\[SCENE_ENV_IDENT_END:([^\s\]]+)\]`?",
    re.IGNORECASE | re.DOTALL,
)
ENV_ITEM_PATTERN = re.compile(
    r"^\s*\[ENV\]\s*"
    r"名称\s*=\s*([^｜|\r\n]+)"
    r"(?:\s*[｜|]\s*复用\s*=\s*([^｜|\r\n]+))?"
    r"(?:\s*[｜|]\s*来源\s*=\s*([^｜|\r\n]+))?"
    r"(?:\s*[｜|]\s*匹配主环境\s*=\s*([^｜|\r\n]+))?"
    r"(?:\s*[｜|]\s*依据\s*=\s*([^\r\n]+))?",
    re.IGNORECASE | re.MULTILINE,
)
_DEGREE_NAME_PATTERN = re.compile(r"^(\d+)\s*度")
_SOURCE_REUSE = {"项目库", "上集", "本集"}
_SOURCE_NEW = {"新建", "新建设计", "无", "none", "n/a", ""}


def normalize_environment_name(value: Any) -> str:
    text = str(value or "").strip().strip("`\"'“”‘’[]")
    text = re.split(r"[｜|]", text, maxsplit=1)[0].strip()
    text = re.sub(r"^(名称|主环境|环境名|环境)\s*[=：:]\s*", "", text).strip()
    return re.sub(r"[\s_*`'\"“”‘’]+", "", text).lower()


def _clean_env_name(value: Any) -> str:
    text = str(value or "").strip().strip("`\"'“”‘’")
    text = re.split(r"[｜|]", text, maxsplit=1)[0].strip()
    if text in {"无", "空", "N/A", "n/a", "none", "None", "-"}:
        return ""
    return text


def _truthy_reuse(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"是", "yes", "y", "true", "1", "reuse", "复用"}


def _normalize_source(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("上集"):
        return "上集"
    if text.startswith("项目库") or text.startswith("全局"):
        return "项目库"
    if text.startswith("本集"):
        return "本集"
    if text.startswith("新建") or text in _SOURCE_NEW:
        return "新建"
    return text or "新建"


def parse_scene_env_ident_items(text: str, scene_id: str = "") -> List[Dict[str, Any]]:
    """Parse [SCENE_ENV_IDENT_*] items from a scene body or full script."""
    source = str(text or "")
    items: List[Dict[str, Any]] = []
    seen: set = set()
    blocks = list(SCENE_ENV_IDENT_PATTERN.finditer(source))
    search_bodies: List[Tuple[str, str]] = []
    if blocks:
        for match in blocks:
            start_id = str(match.group(1) or "").strip()
            end_id = str(match.group(3) or "").strip()
            if scene_id and start_id and start_id.lower() != str(scene_id).lower():
                continue
            if start_id and end_id and start_id.lower() != end_id.lower():
                continue
            search_bodies.append((start_id or scene_id, str(match.group(2) or "")))
    elif scene_id or ENV_ITEM_PATTERN.search(source):
        search_bodies.append((scene_id, source))

    for block_scene_id, body in search_bodies:
        for match in ENV_ITEM_PATTERN.finditer(body):
            name = _clean_env_name(match.group(1))
            if not name:
                continue
            reuse_raw = str(match.group(2) or "").strip()
            source_raw = str(match.group(3) or "").strip()
            matched = _clean_env_name(match.group(4))
            evidence = str(match.group(5) or "").strip()
            source_kind = _normalize_source(source_raw)
            reused = source_kind in _SOURCE_REUSE or _truthy_reuse(reuse_raw)
            if source_kind == "新建":
                reused = False
            key = (normalize_environment_name(matched or name), reused, source_kind)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "scene_id": block_scene_id,
                    "name": name,
                    "reuse": reused,
                    "source": source_kind,
                    "matched_name": matched or (name if reused else ""),
                    "evidence": evidence,
                    "raw": match.group(0).strip(),
                }
            )
    return items


def scene_has_new_environments(items: Sequence[Dict[str, Any]]) -> bool:
    """True when the scene must call environment planning (any non-reuse env, or missing tags)."""
    if not items:
        return True
    return any(not bool(item.get("reuse")) for item in items)


def scene_reused_environment_names(items: Sequence[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    seen: set = set()
    for item in items or []:
        if not item.get("reuse"):
            continue
        name = _clean_env_name(item.get("matched_name") or item.get("name"))
        key = normalize_environment_name(name)
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def build_scene_env_ident_block(scene_id: str, items: Sequence[Dict[str, Any]]) -> str:
    lines = [f"[SCENE_ENV_IDENT_START:{scene_id}]"]
    for item in items or []:
        name = _clean_env_name(item.get("name"))
        if not name:
            continue
        reuse = "是" if item.get("reuse") else "否"
        source = _normalize_source(item.get("source"))
        matched = _clean_env_name(item.get("matched_name")) or ("无" if reuse == "否" else name)
        evidence = str(item.get("evidence") or "").strip() or "无"
        lines.append(
            f"[ENV] 名称={name}｜复用={reuse}｜来源={source}｜匹配主环境={matched}｜依据={evidence}"
        )
    lines.append(f"[SCENE_ENV_IDENT_END:{scene_id}]")
    return "\n".join(lines)


def _is_main_environment(entity: Any) -> bool:
    from app.api.routers.entities_pkg.analyze import _entity_analysis_is_main_environment

    return bool(_entity_analysis_is_main_environment(entity))


def _episode_tag(episode: Any, fallback: str = "") -> str:
    number = _resolve_episode_sort_number(episode) if episode is not None else None
    if number:
        return f"EP{int(number):02d}"
    title = str(getattr(episode, "title", "") or "").strip()
    return title or fallback


def _extract_env_blocks_by_name(script_text: str) -> Dict[str, str]:
    from app.services.script_analysis_flow import (
        extract_env_block_from_scene_text,
        extract_environment_names_from_scene_text,
        parse_scene_units_from_markers,
    )
    from app.services.script_analysis_flow.subject_index_name_align import split_scene_subject_field

    mapped: Dict[str, str] = {}
    source = str(script_text or "").strip()
    if not source:
        return mapped
    try:
        units = parse_scene_units_from_markers(source)
    except Exception:
        units = []
    texts = [str(getattr(unit, "scene_text", "") or "") for unit in units] if units else [source]
    for text in texts:
        block = extract_env_block_from_scene_text(text)
        if not block:
            continue
        names = extract_environment_names_from_scene_text(text) or extract_environment_names_from_scene_text(block)
        for raw_name in split_scene_subject_field(names):
            name = _clean_env_name(raw_name)
            key = normalize_environment_name(name)
            if name and key and key not in mapped:
                mapped[key] = block
    return mapped


def _collect_previous_episode_env_blocks(
    db: Session,
    *,
    project_id: int,
    current_episode_id: int = 0,
) -> List[Dict[str, Any]]:
    rows = (
        db.query(Episode)
        .filter(Episode.project_id == int(project_id), _active_episode_clause())
        .all()
    )
    current = None
    if current_episode_id > 0:
        current = next((row for row in rows if int(getattr(row, "id", 0) or 0) == int(current_episode_id)), None)
    current_number = _resolve_episode_sort_number(current) if current is not None else None
    catalog: List[Dict[str, Any]] = []
    for episode in _sort_project_episodes(rows):
        episode_id = int(getattr(episode, "id", 0) or 0)
        if current_episode_id > 0 and episode_id == int(current_episode_id):
            continue
        episode_number = _resolve_episode_sort_number(episode)
        if current_number and episode_number and int(episode_number) >= int(current_number):
            continue
        adaptation = str(getattr(episode, "ai_scene_analysis_adaptation", "") or "").strip()
        if not adaptation:
            continue
        tag = _episode_tag(episode)
        for key, block in _extract_env_blocks_by_name(adaptation).items():
            names = []
            try:
                from app.services.script_analysis_flow import extract_environment_names_from_scene_text
                from app.services.script_analysis_flow.subject_index_name_align import split_scene_subject_field

                names = [
                    _clean_env_name(part)
                    for part in split_scene_subject_field(extract_environment_names_from_scene_text(block))
                    if _clean_env_name(part)
                ]
            except Exception:
                names = []
            display = names[0] if names else key
            catalog.append(
                {
                    "name": display,
                    "normalized": key,
                    "source": "上集",
                    "source_label": f"上集{tag}" if tag else "上集",
                    "episode_id": episode_id,
                    "episode_tag": tag,
                    "entity_id": 0,
                    "env_block": block,
                    "derivatives": _derivatives_from_env_block(block, display),
                }
            )
    return catalog


def _derivatives_from_env_block(env_block: str, main_name: str) -> List[Dict[str, Any]]:
    derivatives: List[Dict[str, Any]] = []
    seen: set = set()
    for match in re.finditer(r"`([^`]*度[^`]+)`", str(env_block or "")):
        name = _clean_env_name(match.group(1))
        key = normalize_environment_name(name)
        if not name or key in seen:
            continue
        if main_name and normalize_environment_name(main_name) not in key and main_name not in name:
            continue
        seen.add(key)
        angle_match = _DEGREE_NAME_PATTERN.match(name)
        derivatives.append(
            {
                "name": name,
                "view_angle_from_main": int(angle_match.group(1)) if angle_match else None,
                "generation_prompt_cn": "",
                "description": "",
            }
        )
    return derivatives


def _derivatives_from_entities(
    entities: Sequence[Any],
    main_name: str,
    main_entity_id: int = 0,
) -> List[Dict[str, Any]]:
    main_key = normalize_environment_name(main_name)
    derivatives: List[Dict[str, Any]] = []
    seen: set = set()
    for entity in entities or []:
        if _is_main_environment(entity):
            continue
        name = _clean_env_name(getattr(entity, "name", ""))
        if not name:
            continue
        deps = getattr(entity, "visual_dependencies", None)
        dep_text = " ".join(str(item or "") for item in deps) if isinstance(deps, list) else str(deps or "")
        name_key = normalize_environment_name(name)
        linked = bool(main_key and main_key in name_key) or (
            main_name and f"ENV:[{main_name}]" in dep_text.replace(" ", "")
        )
        if main_entity_id > 0 and not linked:
            continue
        if not linked:
            continue
        if name_key in seen:
            continue
        seen.add(name_key)
        angle_match = _DEGREE_NAME_PATTERN.match(name)
        derivatives.append(
            {
                "name": name,
                "view_angle_from_main": int(angle_match.group(1)) if angle_match else None,
                "generation_prompt_cn": str(getattr(entity, "generation_prompt_cn", "") or "").strip(),
                "description": str(getattr(entity, "description", "") or getattr(entity, "narrative_description", "") or "").strip(),
                "entity_id": int(getattr(entity, "id", 0) or 0),
            }
        )
    derivatives.sort(key=lambda item: (item.get("view_angle_from_main") is None, item.get("view_angle_from_main") or 0, item.get("name") or ""))
    return derivatives


def _deleted_environment_name_keys(db: Session, project_id: int) -> set:
    if not project_id:
        return set()
    rows = (
        db.query(Entity)
        .filter(
            Entity.project_id == int(project_id),
            Entity.type == "environment",
            Entity.is_deleted.is_(True),
        )
        .all()
    )
    keys = set()
    for entity in rows:
        key = normalize_environment_name(_clean_env_name(getattr(entity, "name", "")))
        if key:
            keys.add(key)
    return keys


def collect_project_main_environment_catalog(
    db: Session,
    *,
    project_id: int,
    current_episode_id: int = 0,
) -> List[Dict[str, Any]]:
    """Project-library main environments + previous-episode Stage-1 env names."""
    if not project_id:
        return []
    entities = (
        db.query(Entity)
        .filter(
            Entity.project_id == int(project_id),
            Entity.type == "environment",
            _active_entity_clause(),
        )
        .all()
    )
    deleted_keys = _deleted_environment_name_keys(db, int(project_id))
    catalog: List[Dict[str, Any]] = []
    seen: set = set()
    episode_rows = {
        int(getattr(row, "id", 0) or 0): row
        for row in db.query(Episode)
        .filter(Episode.project_id == int(project_id), _active_episode_clause())
        .all()
        if getattr(row, "id", None) is not None
    }
    for entity in entities:
        if not _is_main_environment(entity):
            continue
        name = _clean_env_name(getattr(entity, "name", ""))
        key = normalize_environment_name(name)
        if not name or key in seen:
            continue
        seen.add(key)
        episode_id = int(getattr(entity, "episode_id", 0) or 0)
        episode = episode_rows.get(episode_id)
        catalog.append(
            {
                "name": name,
                "normalized": key,
                "source": "项目库",
                "source_label": "项目库",
                "episode_id": episode_id,
                "episode_tag": _episode_tag(episode),
                "entity_id": int(getattr(entity, "id", 0) or 0),
                "env_block": "",
                "generation_prompt_cn": str(getattr(entity, "generation_prompt_cn", "") or "").strip(),
                "description": str(getattr(entity, "description", "") or getattr(entity, "narrative_description", "") or "").strip(),
                "derivatives": _derivatives_from_entities(entities, name, int(getattr(entity, "id", 0) or 0)),
            }
        )

    for item in _collect_previous_episode_env_blocks(
        db,
        project_id=int(project_id),
        current_episode_id=int(current_episode_id or 0),
    ):
        key = str(item.get("normalized") or "")
        if key and key in deleted_keys:
            continue
        if key in seen:
            existing = next((row for row in catalog if row.get("normalized") == key), None)
            if existing is not None and not existing.get("env_block") and item.get("env_block"):
                existing["env_block"] = item.get("env_block")
                if not existing.get("derivatives"):
                    existing["derivatives"] = list(item.get("derivatives") or [])
            continue
        seen.add(key)
        catalog.append(item)
    return catalog


def find_catalog_environment(
    catalog: Sequence[Dict[str, Any]],
    name: str,
) -> Optional[Dict[str, Any]]:
    key = normalize_environment_name(name)
    if not key:
        return None
    for item in catalog or []:
        if str(item.get("normalized") or "") == key:
            return item
        if normalize_environment_name(item.get("name")) == key:
            return item
    return None


def _truncate_env_text(value: Any, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _catalog_item_injection_lines(item: Dict[str, Any]) -> List[str]:
    name = _clean_env_name(item.get("name"))
    if not name:
        return []
    source_label = str(item.get("source_label") or item.get("source") or "项目库").strip()
    episode_tag = str(item.get("episode_tag") or "").strip()
    extra = f"｜集={episode_tag}" if episode_tag and "EP" not in source_label else ""
    lines = [f"- {name}｜来源={source_label}{extra}"]
    desc = _truncate_env_text(
        item.get("description") or item.get("generation_prompt_cn") or ""
    )
    if not desc:
        desc = _truncate_env_text(item.get("env_block"), 360)
    lines.append(f"  摘要={desc or '无'}")
    derived_names = [
        _clean_env_name(row.get("name"))
        for row in (item.get("derivatives") or [])
        if _clean_env_name(row.get("name"))
    ]
    lines.append(f"  已有衍生={','.join(derived_names[:12]) if derived_names else '无'}")
    return lines


def build_project_main_environment_injection(catalog: Sequence[Dict[str, Any]]) -> str:
    usable = [
        item
        for item in (catalog or [])
        if _clean_env_name(item.get("name"))
    ]
    if not usable:
        return wrap_injection_section(
            PROJECT_MAIN_ENV_LABEL,
            "\n".join(
                (
                    "可复用/可参考主环境=无",
                    "当前项目库与上集均无可用主环境（已删除的不计入）。",
                    "场景切分时不得臆造“项目库已有”或“上集已有”；本集全部主环境必须标 复用=否｜来源=新建｜匹配主环境=无。",
                    "一集之内禁止把同一连续时空拆成多个可复用 Scene——应合并为一场。本集出去再回来按闪切/闪回处理，短段并入大场。",
                )
            ),
        )
    lines = [
        "当前项目已登记的主环境（含项目库与本集之前各集；已删除的不计入）。场景切分时必须逐场评估能否复用；能复用则沿用原名并标复用。",
        "一集之内禁止把同一连续时空拆成多个可复用 Scene——应合并为一场。本集出去再回来按闪切/闪回处理，短段并入大场，禁止拆成回切场再标来源=本集。",
        "复用只对照下列清单。日夜/天气不同不另起名。禁止同空间另起近义名。",
    ]
    for item in usable:
        lines.extend(_catalog_item_injection_lines(item))
    return wrap_injection_section(PROJECT_MAIN_ENV_LABEL, "\n".join(lines))


def _default_master_derivative(main_name: str) -> Dict[str, Any]:
    return {
        "name": f"0度{main_name}",
        "view_angle_from_main": 0,
        "generation_prompt_cn": "",
        "description": "",
    }


_DERIVED_ENV_SECTION_PATTERN = re.compile(
    r"(?:\r?\n)?────【衍生环境】────.*?(?=(?:\r?\n\[ENV_BLOCK_END)|(?:\r?\n────【)|$)",
    re.IGNORECASE | re.DOTALL,
)
_ENV_COVERAGE_SUMMARY_PATTERN = re.compile(
    r"(?:\r?\n)?【ENV覆盖综合】[^\r\n]*",
    re.IGNORECASE,
)


def _strip_derived_environment_section(env_block: str) -> str:
    """Keep main-env + unplaced only; derivatives belong to the framing node."""
    stripped = _DERIVED_ENV_SECTION_PATTERN.sub("", str(env_block or ""))
    stripped = _ENV_COVERAGE_SUMMARY_PATTERN.sub("", stripped)
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


def synthesize_reused_env_block(
    *,
    main_name: str,
    catalog_item: Optional[Dict[str, Any]] = None,
) -> str:
    existing = _strip_derived_environment_section(
        str((catalog_item or {}).get("env_block") or "")
    )
    if existing:
        return existing
    return "\n".join(
        [
            "[ENV_BLOCK_START]",
            "────【主环境】────",
            f"【主环境】{main_name}｜日夜内外=继承项目库｜主环境角色=当下主线",
            "【活动空间】复用项目库主环境；0°轴/四向/固定清单继承既有资产，禁止重定坐标。",
            "0度轴=继承项目库｜四向+中心：继承项目库",
            "地面=继承项目库｜空中/屋顶=继承项目库｜通高=继承｜风格依赖=无",
            "头尾双锚=继承项目库｜固定实体=继承项目库",
            "────【未落环境实体清单】────",
            f"- 无｜依据=复用项目库｜开场在场｜归属主环境={main_name}｜全局性道具=否",
            "[ENV_BLOCK_END]",
        ]
    )


def build_reused_environment_patch(
    scene_id: str,
    items: Sequence[Dict[str, Any]],
    catalog: Sequence[Dict[str, Any]],
    *,
    episode_env_blocks: Optional[Dict[str, str]] = None,
) -> str:
    blocks: List[str] = []
    seen: set = set()
    for item in items or []:
        if not item.get("reuse"):
            continue
        name = _clean_env_name(item.get("matched_name") or item.get("name"))
        key = normalize_environment_name(name)
        if not name or key in seen:
            continue
        seen.add(key)
        local_block = str((episode_env_blocks or {}).get(key) or "").strip()
        catalog_item = find_catalog_environment(catalog, name)
        block = local_block or synthesize_reused_env_block(main_name=name, catalog_item=catalog_item)
        if block and block not in blocks:
            blocks.append(block)
    if not blocks:
        return ""
    body = "\n\n".join(blocks).strip()
    return "\n".join(
        [
            f"[ENV_SCENE_PATCH_START:{scene_id}]",
            body,
            f"[ENV_SCENE_PATCH_END:{scene_id}]",
        ]
    )


def merge_reused_and_new_env_blocks(reused_patch: str, new_patch: str) -> str:
    """Keep reused library skeletons and append newly designed ENV_BLOCKs."""
    from app.services.script_analysis_flow import extract_env_block_from_scene_text

    reused_block = extract_env_block_from_scene_text(reused_patch) if reused_patch else ""
    new_block = extract_env_block_from_scene_text(new_patch) if new_patch else ""
    if reused_block and new_block:
        return f"{reused_block}\n\n{new_block}".strip()
    return (new_block or reused_block or str(new_patch or reused_patch or "")).strip()


def build_reused_derived_environment_injection(
    items: Sequence[Dict[str, Any]],
    catalog: Sequence[Dict[str, Any]],
    *,
    episode_env_blocks: Optional[Dict[str, str]] = None,
) -> str:
    sections: List[str] = []
    for name in scene_reused_environment_names(items):
        catalog_item = find_catalog_environment(catalog, name)
        local_block = str((episode_env_blocks or {}).get(normalize_environment_name(name)) or "").strip()
        derivatives = list((catalog_item or {}).get("derivatives") or [])
        if not derivatives and local_block:
            derivatives = _derivatives_from_env_block(local_block, name)
        if not derivatives:
            derivatives = [_default_master_derivative(name)]
        lines = [
            f"所属主环境={name}",
            "景别构图节点当前 ENV 必须从下列已声明衍生名中选用或沿用；缺覆盖角可在同坐标系内补合法新行，禁止另起近义衍生名，禁止重映射角度。",
        ]
        for item in derivatives:
            derived_name = _clean_env_name(item.get("name"))
            if not derived_name:
                continue
            angle = item.get("view_angle_from_main")
            prompt = str(item.get("generation_prompt_cn") or item.get("description") or "").strip()
            if len(prompt) > 240:
                prompt = prompt[:240].rstrip() + "…"
            angle_text = f"｜view_angle_from_main={int(angle)}" if angle is not None else ""
            prompt_text = f"｜摘要={prompt}" if prompt else ""
            lines.append(f"- `{derived_name}`{angle_text}{prompt_text}")
        sections.append("\n".join(lines))
    if not sections:
        return ""
    return wrap_injection_section(
        REUSED_DERIVED_ENV_LABEL,
        "以下衍生环境来自项目库或本集已锁定主环境，只读使用。\n\n" + "\n\n".join(sections),
    )


def collect_episode_env_blocks_by_name(script_text: str) -> Dict[str, str]:
    return _extract_env_blocks_by_name(script_text)


def _is_environment_asset_type(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return (
        text in {"environment", "env", "场景", "环境"}
        or "environment" in text
        or "env" in text
        or "环境" in text
        or "场景" in text
    )


def _episode_selected_reuse_asset_ids(episode: Any) -> List[int]:
    info = getattr(episode, "episode_info", None) or {}
    if isinstance(info, str):
        try:
            info = json.loads(info)
        except Exception:
            info = {}
    if not isinstance(info, dict):
        return []
    ids: List[int] = []
    seen = set()
    for raw in info.get("reuse_subject_asset_ids") or []:
        try:
            eid = int(raw)
        except Exception:
            continue
        if eid > 0 and eid not in seen:
            seen.add(eid)
            ids.append(eid)
    return ids


def collect_selected_global_environment_catalog(
    db: Session,
    *,
    project_id: int,
    episode_id: int = 0,
    reuse_subject_assets: Optional[Sequence[Any]] = None,
) -> List[Dict[str, Any]]:
    """Main environments the user checked in 剧本页「全局资产」(deleted excluded)."""
    if not project_id:
        return []
    ids: List[int] = []
    seen_ids = set()
    payload_by_id: Dict[int, Dict[str, Any]] = {}
    for item in reuse_subject_assets or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") and not _is_environment_asset_type(item.get("type")):
            continue
        try:
            eid = int(item.get("id") or 0)
        except Exception:
            eid = 0
        if eid <= 0 or eid in seen_ids:
            continue
        seen_ids.add(eid)
        ids.append(eid)
        payload_by_id[eid] = item

    if episode_id > 0:
        episode = (
            db.query(Episode)
            .filter(Episode.id == int(episode_id), _active_episode_clause())
            .first()
        )
        for eid in _episode_selected_reuse_asset_ids(episode):
            if eid not in seen_ids:
                seen_ids.add(eid)
                ids.append(eid)

    if not ids:
        return []

    entities = (
        db.query(Entity)
        .filter(
            Entity.project_id == int(project_id),
            Entity.id.in_(ids),
            Entity.type == "environment",
            _active_entity_clause(),
        )
        .all()
    )
    entity_by_id = {int(getattr(row, "id", 0) or 0): row for row in entities}
    all_env_entities = (
        db.query(Entity)
        .filter(
            Entity.project_id == int(project_id),
            Entity.type == "environment",
            _active_entity_clause(),
        )
        .all()
    )
    catalog: List[Dict[str, Any]] = []
    seen_names = set()
    for eid in ids:
        entity = entity_by_id.get(eid)
        if entity is None or not _is_main_environment(entity):
            continue
        name = _clean_env_name(getattr(entity, "name", ""))
        if not name or _DEGREE_NAME_PATTERN.match(name):
            continue
        key = normalize_environment_name(name)
        if not key or key in seen_names:
            continue
        seen_names.add(key)
        payload = payload_by_id.get(eid) or {}
        catalog.append(
            {
                "name": name,
                "normalized": key,
                "source": "用户选定",
                "source_label": "用户选定全局资产",
                "episode_id": int(getattr(entity, "episode_id", 0) or 0),
                "episode_tag": "",
                "entity_id": eid,
                "env_block": "",
                "generation_prompt_cn": str(getattr(entity, "generation_prompt_cn", "") or "").strip(),
                "description": str(
                    getattr(entity, "description", "")
                    or getattr(entity, "narrative_description", "")
                    or payload.get("description")
                    or payload.get("anchor_description")
                    or ""
                ).strip(),
                "derivatives": _derivatives_from_entities(all_env_entities, name, eid),
            }
        )
    return catalog


def format_selected_global_environment_injection(catalog: Sequence[Dict[str, Any]]) -> str:
    usable = [item for item in (catalog or []) if _clean_env_name(item.get("name"))]
    if not usable:
        return wrap_injection_section(
            SELECTED_GLOBAL_ENV_LABEL,
            "\n".join(
                (
                    "用户选定全局环境=无",
                    "剧本页「全局资产」未勾选可用主环境（已删除的不计入）。规划时不得把未勾选资产当成用户指定复用源。",
                )
            ),
        )
    lines = [
        "以下主环境来自剧本页「全局资产」勾选（已删除不计入）。",
        "必须先把本集需要的环境（SCENE_ENV_IDENT 名称 + 情节确认空间）与本清单逐条对照，找出可对应项：",
        "名称相同、同空间别称、或摘要空间类型与本场包络同一处即命中。",
        "命中且 SCENE_ENV_IDENT 已标 复用=是 → 只锁注册名，禁止重写骨架。",
        "命中但识别为新建 → 写骨架时必须参考本条名称/摘要/已有衍生，禁止另起同义空壳。",
        "未命中才按新建设计；未对应的勾选项不得硬塞进无关场。",
    ]
    for item in usable:
        lines.extend(_catalog_item_injection_lines(item))
    return wrap_injection_section(SELECTED_GLOBAL_ENV_LABEL, "\n".join(lines))


def format_reuse_lock_instruction(
    reused_names: Iterable[str],
    catalog: Sequence[Dict[str, Any]] = (),
) -> str:
    names = [name for name in (_clean_env_name(item) for item in reused_names) if name]
    if not names:
        return (
            "【整集环境规划】待复用主环境=无。"
            "场景拆分未标任何可复用主环境；本集新建环境全部按 复用=否 写骨架。"
            "不得臆造项目库/上集复用名。"
        )
    lines = [
        "【整集环境规划】以下主环境已由场景拆分判定复用，禁止输出其【主环境】骨架；"
        "只为复用=否的新建环境写主环境补丁；全复用场不要输出补丁。复用骨架由程序按下列具体信息回填。"
        "已有衍生名只作后续景别构图节点参考，本文件不写衍生行。",
        "待复用主环境：",
    ]
    for name in names:
        item = find_catalog_environment(catalog, name)
        if item:
            lines.extend(_catalog_item_injection_lines(item))
        else:
            lines.append(f"- {name}｜来源=场景拆分锁定｜摘要=无｜已有衍生=无")
    return "\n".join(lines)
