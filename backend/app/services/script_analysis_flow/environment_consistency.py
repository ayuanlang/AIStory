# -*- coding: utf-8 -*-
"""Compare an environment image with the prompt that generated it.

The check rewrites the stored prompt only when the picture and that prompt
disagree, so the opening world lock and each grid cell or derived shot still
describe one place.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.all_models import Entity
from app.services.script_analysis_flow.derived_env_ingest import (
    SOURCE_FLAG,
    extract_grid_cell_prompt,
    main_environment_quad_prompt_ready,
)
from app.services.soft_delete import _active_entity_clause

LAST_SUBMITTED_PROMPT_ATTR = "last_submitted_image_prompt"
LAST_SUBMITTED_KIND_ATTR = "last_submitted_image_prompt_kind"
STUB_MARKERS = ("只切割", "不要重切宫格")


class ConsistencyApplyError(ValueError):
    """The model reply cannot be written back without breaking the prompt contract."""


def attrs_of(entity: Any) -> Dict[str, Any]:
    raw = getattr(entity, "custom_attributes", None)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return dict(raw) if isinstance(raw, dict) else {}


def is_environment_entity(entity: Any) -> bool:
    raw = str(getattr(entity, "type", "") or "").strip().lower()
    return any(token in raw for token in ("env", "环境", "scene", "场景"))


def is_derived_environment_entity(entity: Any) -> bool:
    if not is_environment_entity(entity):
        return False
    attrs = attrs_of(entity)
    if attrs.get("derived_kind") or attrs.get("source") == SOURCE_FLAG:
        return True
    name = str(getattr(entity, "name", "") or "").strip()
    return bool(re.match(r"^\d+\s*度", name))


def is_main_environment_entity(entity: Any) -> bool:
    return is_environment_entity(entity) and not is_derived_environment_entity(entity)


def is_stub_prompt(text: str) -> bool:
    raw = str(text or "")
    return any(marker in raw for marker in STUB_MARKERS)


def resolve_checked_prompt(entity: Any, override: Optional[str] = None) -> str:
    given = str(override or "").strip()
    if given:
        return given
    saved = str(attrs_of(entity).get(LAST_SUBMITTED_PROMPT_ATTR) or "").strip()
    if saved:
        return saved
    return str(getattr(entity, "generation_prompt_cn", "") or "").strip()


def classify_checked_prompt(entity: Any, prompt: str) -> str:
    """main | crop | regen | derived."""
    if is_main_environment_entity(entity):
        return "main"
    text = str(prompt or "")
    if is_stub_prompt(text):
        return "crop"
    attrs = attrs_of(entity)
    generation = str(getattr(entity, "generation_prompt_cn", "") or "").strip()
    regen = str(attrs.get("grid_regen_prompt") or "").strip()
    saved_kind = str(attrs.get(LAST_SUBMITTED_KIND_ATTR) or "").strip()
    if saved_kind == "regen" or (regen and text == regen) or (is_stub_prompt(generation) and text != generation):
        return "regen"
    return "derived"


def derived_view_angle(entity: Any) -> Optional[int]:
    attrs = attrs_of(entity)
    try:
        angle = int(attrs.get("view_angle_from_main"))
    except (TypeError, ValueError):
        angle = None
    if angle in (0, 90, 180, 270):
        return angle
    prompt = str(getattr(entity, "generation_prompt_cn", "") or "")
    key = re.search(r"angle_key=[^|\n｜]*[|｜]\s*(0|90|180|270)", prompt)
    if key:
        return int(key.group(1))
    token = re.search(r"截取宫格=\s*(?:左上|右上|左下|右下)?\s*(0|90|180|270)", prompt)
    if token:
        return int(token.group(1))
    name = re.search(r"(?:^|[^\d])(0|90|180|270)\s*度", str(getattr(entity, "name", "") or ""))
    if name:
        return int(name.group(1))
    return None


def _clean_name(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^(?:ENV|CHAR|PROP)\s*[:：]\s*", "", text, flags=re.IGNORECASE)
    return text.strip("[]").strip()


def owning_main_names(entity: Any) -> List[str]:
    attrs = attrs_of(entity)
    names: List[str] = []
    for key in ("main_environment", "main_environment_name", "所属主环境", "owning_main_environment"):
        value = _clean_name(attrs.get(key))
        if value:
            names.append(value)
    prompt = str(getattr(entity, "generation_prompt_cn", "") or "")
    match = re.search(r"所属主环境\s*=\s*([^。\n｜|]+)", prompt)
    if match:
        value = _clean_name(match.group(1))
        if value:
            names.append(value)
    name = str(getattr(entity, "name", "") or "").strip()
    stripped = re.sub(r"^(?:\d+)\s*度\s*", "", name).strip()
    if stripped and stripped != name:
        names.append(stripped)
    seen = set()
    ordered: List[str] = []
    for item in names:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(item.strip())
    return ordered


def find_owning_main_environment(db: Session, entity: Any) -> Optional[Entity]:
    if is_main_environment_entity(entity):
        return entity
    wanted = {name.lower() for name in owning_main_names(entity)}
    if not wanted or getattr(entity, "project_id", None) is None:
        return None
    rows = (
        db.query(Entity)
        .filter(
            Entity.project_id == int(entity.project_id),
            _active_entity_clause(),
        )
        .all()
    )
    matches = []
    for row in rows:
        if int(getattr(row, "id", 0) or 0) == int(getattr(entity, "id", 0) or 0):
            continue
        if not is_main_environment_entity(row):
            continue
        row_names = {
            _clean_name(getattr(row, "name", "")).lower(),
            _clean_name(getattr(row, "name_en", "")).lower(),
        }
        row_names.discard("")
        if wanted & row_names:
            matches.append(row)
    if not matches:
        return None
    episode_id = getattr(entity, "episode_id", None)

    def _score(row: Entity) -> int:
        score = 0
        if episode_id is not None and getattr(row, "episode_id", None) == episode_id:
            score += 4
        if str(getattr(row, "generation_prompt_cn", "") or "").strip():
            score += 2
        if str(getattr(row, "image_url", "") or "").strip():
            score += 1
        return score

    matches.sort(key=_score, reverse=True)
    return matches[0]


def _extract_json_object(text: str) -> Optional[dict]:
    raw = str(text or "")
    decoder = json.JSONDecoder()
    for idx, char in enumerate(raw):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(raw[idx:])
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _blank_to_none(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text or text.lower() in {"null", "none"}:
        return None
    return text


def parse_consistency_payload(text: str) -> Dict[str, Any]:
    content = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL | re.IGNORECASE).strip()
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\s*```$", "", content).strip()
    data = _extract_json_object(content)
    if not isinstance(data, dict):
        raise ConsistencyApplyError("一致性检查没有返回可用的 JSON。")
    consistent = data.get("consistent")
    if isinstance(consistent, str):
        consistent = consistent.strip().lower() in {"true", "1", "yes", "y", "是", "一致"}
    return {
        "consistent": bool(consistent),
        "summary": str(data.get("summary") or "").strip(),
        "revised_prompt": _blank_to_none(data.get("revised_prompt")),
        "revised_main_prompt": _blank_to_none(data.get("revised_main_prompt")),
    }


def _prompt_keeps_world_lock(original: str, revised: str) -> Optional[str]:
    source = str(original or "")
    target = str(revised or "")
    if len(target) < max(80, int(len(source) * 0.45)):
        return "改写结果过短，没有保留原提示词。"
    if not main_environment_quad_prompt_ready(target):
        return "改写结果缺少开篇或四个宫格标题。"
    for key in ("占地=", "竖边="):
        if key in source and key not in target:
            return f"改写结果丢掉了开篇的{key.rstrip('=')}。"
    return None


def plan_consistency_writes(
    entity: Any,
    main_entity: Optional[Any],
    checked_prompt: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Decide which stored prompts to replace. Does not touch the database."""
    kind = classify_checked_prompt(entity, checked_prompt)
    summary = str(payload.get("summary") or "").strip()
    if payload.get("consistent"):
        return {
            "consistent": True,
            "kind": kind,
            "summary": summary or "图片与生成时的提示词一致。",
            "writes": [],
            "updated_targets": [],
        }

    revised = _blank_to_none(payload.get("revised_prompt"))
    revised_main = _blank_to_none(payload.get("revised_main_prompt"))
    writes: List[Dict[str, Any]] = []
    targets: List[str] = []
    entity_id = int(getattr(entity, "id", 0) or 0)
    main_id = int(getattr(main_entity, "id", 0) or 0) if main_entity is not None else 0
    main_prompt = str(getattr(main_entity, "generation_prompt_cn", "") or "") if main_entity is not None else ""

    def _add_main(text: str) -> None:
        if main_entity is None or main_id <= 0:
            raise ConsistencyApplyError("找不到所属主环境，无法把世界物理写回主环境提示词。")
        problem = _prompt_keeps_world_lock(main_prompt or checked_prompt, text)
        if problem:
            raise ConsistencyApplyError(problem)
        if text.strip() == main_prompt.strip():
            return
        writes.append({
            "entity_id": main_id,
            "field": "generation_prompt_cn",
            "value": text,
            "kind": "main",
        })
        writes.append({
            "entity_id": main_id,
            "field": LAST_SUBMITTED_PROMPT_ATTR,
            "value": text,
            "kind": "main",
        })
        if "主环境提示词" not in targets:
            targets.append("主环境提示词")

    if kind == "main":
        if not revised:
            raise ConsistencyApplyError("图片和提示词不一致，但没有返回改写后的主环境提示词。")
        _add_main(revised)
    elif kind == "crop":
        if not revised_main:
            raise ConsistencyApplyError("切割图和主环境提示词不一致，但没有返回改写后的主环境提示词。")
        _add_main(revised_main)
    else:
        field_name = "grid_regen_prompt" if kind == "regen" else "generation_prompt_cn"
        label = "重生修正提示词" if kind == "regen" else "衍生环境提示词"
        if revised and revised.strip() != str(checked_prompt or "").strip():
            if field_name == "generation_prompt_cn" and is_stub_prompt(getattr(entity, "generation_prompt_cn", "")):
                raise ConsistencyApplyError("切割提示词不能改成场景描写。")
            writes.append({
                "entity_id": entity_id,
                "field": field_name,
                "value": revised,
                "kind": kind,
            })
            writes.append({
                "entity_id": entity_id,
                "field": LAST_SUBMITTED_PROMPT_ATTR,
                "value": revised,
                "kind": kind,
            })
            targets.append(label)
        if revised_main:
            _add_main(revised_main)
        if not writes:
            raise ConsistencyApplyError("图片和提示词不一致，但没有返回可写回的提示词。")

    if not writes:
        return {
            "consistent": True,
            "kind": kind,
            "summary": summary or "图片与生成时的提示词一致。",
            "writes": [],
            "updated_targets": [],
        }
    return {
        "consistent": False,
        "kind": kind,
        "summary": summary or "已按图片更新提示词。",
        "writes": writes,
        "updated_targets": targets,
    }


def apply_consistency_writes(entities_by_id: Dict[int, Any], writes: List[Dict[str, Any]]) -> List[int]:
    from sqlalchemy.orm.attributes import flag_modified

    touched: List[int] = []
    for write in writes:
        entity_id = int(write["entity_id"])
        entity = entities_by_id[entity_id]
        field = str(write["field"])
        value = str(write["value"])
        if field == "generation_prompt_cn":
            entity.generation_prompt_cn = value
            entity.description = value
        else:
            attrs = attrs_of(entity)
            attrs[field] = value
            if field == LAST_SUBMITTED_PROMPT_ATTR and write.get("kind"):
                attrs[LAST_SUBMITTED_KIND_ATTR] = write["kind"]
            entity.custom_attributes = attrs
            flag_modified(entity, "custom_attributes")
        if entity_id not in touched:
            touched.append(entity_id)
    return touched


def entity_consistency_payload(entity: Any) -> Dict[str, Any]:
    return {
        "id": int(getattr(entity, "id", 0) or 0),
        "generation_prompt_cn": str(getattr(entity, "generation_prompt_cn", "") or ""),
        "description": str(getattr(entity, "description", "") or ""),
        "custom_attributes": attrs_of(entity),
    }


def build_consistency_messages(
    *,
    image_url: str,
    entity: Any,
    main_entity: Optional[Any],
    checked_prompt: str,
    kind: str,
) -> List[Dict[str, Any]]:
    system_prompt = (
        "你是环境资产一致性校对。对照这张已经生成的图片，和生成这张图时使用的提示词。\n"
        "目标：世界物理（东南西北、占地、竖边、心点、同一件家具的长短朝向）必须和图片里看见的是同一套。"
        "主环境四个宫格、以及由它切出的衍生环境，描述的是同一处空间。\n"
        "一致：空间、主要陈设的朝向和相对位置能被提示词解释。缝档、光色、材质的小差异算一致。\n"
        "不一致：同一件家具在不同宫格长短或朝向对不上；开篇占地或竖边和画面里的长边方向相反；"
        "衍生图和所属宫格、开篇不是同一处空间。\n"
        "修改：只改和图片不符的句子，保留原有段落骨架和主体名字。不要新造第二套房间。\n"
        "主环境提示词必须保留【六面一次】、【四向拼图】，以及四个宫格标题："
        "[0度格-左上、[90度格-右上、[180度格-左下、[270度格-右下。开篇的占地=和竖边=必须留下。\n"
        "看不出具体米数时，保留开篇已有米数，只改朝向、长边落到的画面轴和相对位置。"
        "桌、案、凳、椅、沙发、床、榻的宫格句只写长边落到哪条画面轴，禁止写几成、一半、占房间、一半宽。\n"
        "含「只切割」或「不要重切宫格」的提示词不要改成场景描写。这类图若和世界物理不符，只改主环境提示词，revised_prompt 必须为 null。"
        "状态衍生上的临时变化，例如沙尘、天气、破损，不要写回主环境。\n"
        "重生修正或衍生描写若和图片不符，改这份生成时提示词，并在世界物理也冲突时同时改主环境提示词。\n"
        "一致时 revised_prompt 和 revised_main_prompt 都必须为 null。\n"
        "只返回 JSON 对象，第一个字符是 {，最后一个字符是 }。不要 Markdown，不要解释。\n"
        '{"consistent": true或false, "summary": "一两句中文", "revised_prompt": null或完整提示词, "revised_main_prompt": null或完整主环境提示词}'
    )
    parts = [
        f"检查对象={kind}。主体={getattr(entity, 'name', '')}。",
        "下面是生成这张图时使用的提示词：",
        str(checked_prompt or "").strip(),
    ]
    if kind != "main" and main_entity is not None:
        angle = derived_view_angle(entity)
        main_prompt = str(getattr(main_entity, "generation_prompt_cn", "") or "").strip()
        parts.append(f"所属主环境={getattr(main_entity, 'name', '')}。")
        if angle is not None and main_prompt:
            cell = extract_grid_cell_prompt(main_prompt, angle).get("cell_prompt") or ""
            parts.append(f"这张衍生图对应 {angle} 度格。该格当前正文：")
            parts.append(cell or "（主环境提示词里没有这一格）")
        parts.append("主环境完整提示词：")
        parts.append(main_prompt or "（空）")
        if kind == "crop":
            parts.append("这次生成用的是切割提示词。不要改写切割提示词。若图片和世界物理不一致，把改正写进 revised_main_prompt。")
        else:
            parts.append("若生成时提示词本身和图片不符，把完整改正写进 revised_prompt。若开篇或对应宫格也要改，把完整主环境提示词写进 revised_main_prompt。")
    else:
        parts.append("这是主环境四宫格图。若不一致，把改正后的完整主环境提示词写进 revised_prompt，revised_main_prompt 置 null。")
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "\n".join(parts)},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]

