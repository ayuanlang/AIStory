# -*- coding: utf-8 -*-
"""Compare environment grids and derived assets with the main-environment opening.

The opening is the authority for subject count, facing, and position. When a
grid cell or a derived-environment prompt disagrees with it, rewrite that cell
or derived prompt. The opening stays verbatim unless the checker marks an
internal contradiction in the opening itself.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.all_models import Entity
from app.services.script_analysis_flow.derived_env_ingest import (
    SOURCE_FLAG,
    extract_grid_cell_prompt,
    main_environment_quad_prompt_ready,
    quad_cells_prompt_ready,
    strip_main_environment_draft_wrapper,
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
        "image_edit_instruction": _blank_to_none(data.get("image_edit_instruction")),
    }


QUAD_MARK = "【四向拼图】"
OPENING_ERROR_PREFIX = "开篇有误"
PIECE_COUNT_PREFIX = "件数核销未通过"
_CELL_HEAD = re.compile(r"\[(0|90|180|270)度格")
_FACE_HEAD = re.compile(r"(正面|左侧面|右侧面|中部|上)：")
_SUBJECT_CODE = re.compile(r"\[@[^\]]+\]（([^）]+)）")
_LEDGER_FACE = re.compile(
    r"(正面|左侧面|右侧面|中部|上)点名=(\d+)开篇=(\d+)划出=(\d+)"
    r"(?:改入=(\d+))?(?:划出名=([^｜。\n]*))?"
)
_FACE_ORDER = ("正面", "左侧面", "右侧面", "中部", "上")


def _unique_codes(chunk: str) -> List[str]:
    seen = []
    for match in _SUBJECT_CODE.finditer(chunk or ""):
        code = match.group(1).strip()
        if code and code not in seen:
            seen.append(code)
    return seen


def _ledger_names(raw: Optional[str]) -> List[str]:
    text = str(raw or "").strip()
    if not text or text == "无":
        return []
    return _unique_codes(text)


def audit_piece_count_reconciliation(text: str) -> List[str]:
    """Confirm each cell's 件数核销 against the names actually written in that cell.

    Arithmetic alone does not pass. 划出 greater than zero must name the omitted
    codes, and a center subject named in any cell stays named in the other cells.
    """
    raw = str(text or "")
    if "件数核销" not in raw and "件数=" not in raw:
        return []
    cells = []
    for part in re.split(r"(?=\[[0-9]+度格)", raw):
        head = _CELL_HEAD.search(part)
        if head:
            cells.append((head.group(1), part))
    if not cells:
        return []

    issues: List[str] = []
    center_codes: Dict[str, List[str]] = {}
    for angle, body in cells:
        ledger_at = body.find("件数核销")
        if ledger_at < 0:
            issues.append(f"{angle}度格缺少件数核销。")
            continue
        faces_blob = body[:ledger_at]
        ledger = body[ledger_at:].split("\n", 1)[0]
        face_marks = list(_FACE_HEAD.finditer(faces_blob))
        face_codes: Dict[str, List[str]] = {}
        for index, mark in enumerate(face_marks):
            end = face_marks[index + 1].start() if index + 1 < len(face_marks) else len(faces_blob)
            chunk = faces_blob[mark.end():end]
            name = mark.group(1)
            codes = _unique_codes(chunk)
            face_codes[name] = codes
            declared = re.match(r"\s*件数=(\d+)", chunk)
            if declared and int(declared.group(1)) != len(codes):
                issues.append(
                    f"{angle}度格{name}件数={declared.group(1)}，正文点名{len(codes)}件。"
                )
        if "中部" in face_codes:
            center_codes[angle] = face_codes["中部"]
        parsed = {match.group(1): match for match in _LEDGER_FACE.finditer(ledger)}
        for face in _FACE_ORDER:
            codes = face_codes.get(face, [])
            row = parsed.get(face)
            if row is None:
                issues.append(f"{angle}度格件数核销缺少{face}。")
                continue
            named = int(row.group(2))
            opening = int(row.group(3))
            struck = int(row.group(4))
            moved_in = int(row.group(5) or 0)
            struck_codes = _ledger_names(row.group(6))
            if named != len(codes):
                issues.append(
                    f"{angle}度格{face}点名={named}，正文是{len(codes)}件。"
                )
            expected = named + struck - (moved_in if face == "中部" else 0)
            if expected != opening:
                issues.append(
                    f"{angle}度格{face}点名+划出与开篇对不上。"
                )
            if struck > 0 and len(struck_codes) != struck:
                issues.append(
                    f"{angle}度格{face}划出={struck}，划出名没有逐件列出。"
                )
            overlap = [code for code in struck_codes if code in codes]
            if overlap:
                issues.append(
                    f"{angle}度格{face}划出名仍写在正文里。"
                )
    if len(center_codes) >= 2:
        union = []
        for codes in center_codes.values():
            for code in codes:
                if code not in union:
                    union.append(code)
        for angle, codes in center_codes.items():
            missing = [code for code in union if code not in codes]
            if missing:
                issues.append(
                    f"{angle}度格中部少了{'、'.join(missing)}，邻格已经点名，不能划出。"
                )
    return issues


def piece_count_block(summary: str, issues: List[str]) -> str:
    detail = "；".join(issues)
    prefix = f"{PIECE_COUNT_PREFIX}：{detail}"
    rest = str(summary or "").strip()
    if not rest or rest.startswith(PIECE_COUNT_PREFIX):
        return prefix
    return f"{prefix}。{rest}"


def split_opening_and_quad(text: str) -> tuple:
    raw = str(text or "")
    index = raw.find(QUAD_MARK)
    if index < 0:
        return raw, ""
    return raw[:index], raw[index:]


def opening_error_claimed(summary: str) -> bool:
    """True when the checker says the opening contradicts itself."""
    return str(summary or "").strip().startswith(OPENING_ERROR_PREFIX)


def _stored_opening(text: str) -> str:
    opening, _quad = split_opening_and_quad(text)
    return strip_main_environment_draft_wrapper(opening)


def graft_quad_onto_opening(original: str, revised: str) -> str:
    """Keep a stored opening when the asset still has one, and take only the rewritten grids.

    The asset Chinese prompt is the four cells. An older row may still have the
    opening in front; that opening stays. A cells-only row is replaced with the cells.
    """
    opening = _stored_opening(original)
    _revised_opening, revised_quad = split_opening_and_quad(revised)
    revised_quad = strip_main_environment_draft_wrapper(revised_quad)
    if QUAD_MARK not in str(original or ""):
        raise ConsistencyApplyError("主环境提示词没有可保留的开篇。")
    if not revised_quad.strip():
        raise ConsistencyApplyError("改写结果缺少【四向拼图】，不能改开篇。")
    if not opening.strip():
        return revised_quad
    grafted = f"{opening.rstrip()}\n{revised_quad.lstrip()}"
    problem = _prompt_keeps_world_lock(original, grafted)
    if problem:
        raise ConsistencyApplyError(problem)
    kept, _quad = split_opening_and_quad(grafted)
    if kept.strip() != opening.strip():
        raise ConsistencyApplyError("开篇被改动了。")
    return grafted


def accept_revised_main_prompt(original: str, revised: str) -> str:
    """Keep an opening correction the checker explicitly marked as 开篇有误."""
    source = str(original or "")
    target = str(revised or "").strip()
    if QUAD_MARK not in source:
        raise ConsistencyApplyError("主环境提示词没有可保留的开篇。")
    if QUAD_MARK not in target:
        raise ConsistencyApplyError("改写结果缺少【四向拼图】，不能改开篇。")
    problem = _prompt_keeps_world_lock(source, target)
    if problem:
        raise ConsistencyApplyError(problem)
    return target


def _prompt_keeps_world_lock(original: str, revised: str) -> Optional[str]:
    source = str(original or "")
    target = str(revised or "")
    if len(target) < max(80, int(len(source) * 0.45)):
        return "改写结果过短，没有保留原提示词。"
    source_opening = _stored_opening(source)
    if source_opening.strip():
        if not main_environment_quad_prompt_ready(target):
            return "改写结果缺少开篇或四个宫格标题。"
    elif not quad_cells_prompt_ready(target):
        return "改写结果缺少四个宫格标题。"
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
    """Decide which stored prompts to replace. Does not touch the database.

    The main-environment opening is kept verbatim unless the summary starts
    with 开篇有误, meaning the opening contradicts itself. A main or crop
    check then keeps that corrected opening together with the grids. Otherwise
    it replaces only the four grid cells. A derived or regen check replaces
    that derived asset's prompt and does not write the main environment.
    """
    kind = classify_checked_prompt(entity, checked_prompt)
    summary = str(payload.get("summary") or "").strip()
    image_edit_instruction = _blank_to_none(payload.get("image_edit_instruction"))
    main_prompt = str(getattr(main_entity, "generation_prompt_cn", "") or "") if main_entity is not None else ""
    source_quad = main_prompt or checked_prompt
    revised = _blank_to_none(payload.get("revised_prompt"))
    revised_main = _blank_to_none(payload.get("revised_main_prompt"))
    revised_quad = revised_main or revised or ""
    audit_target = revised_quad if ("件数核销" in revised_quad or "件数=" in revised_quad) else source_quad
    piece_issues = audit_piece_count_reconciliation(audit_target)
    if piece_issues:
        return {
            "consistent": False,
            "kind": kind,
            "summary": piece_count_block(summary, piece_issues),
            "writes": [],
            "updated_targets": [],
            "image_edit_instruction": image_edit_instruction,
        }
    if payload.get("consistent"):
        return {
            "consistent": True,
            "kind": kind,
            "summary": summary or "宫格和衍生环境与主环境开篇一致。",
            "writes": [],
            "updated_targets": [],
            "image_edit_instruction": image_edit_instruction,
        }

    writes: List[Dict[str, Any]] = []
    targets: List[str] = []
    entity_id = int(getattr(entity, "id", 0) or 0)
    main_id = int(getattr(main_entity, "id", 0) or 0) if main_entity is not None else 0
    def _add_grids(source_prompt: str, revised_text: str, remember_submitted: bool) -> None:
        if main_entity is None or main_id <= 0:
            raise ConsistencyApplyError("找不到所属主环境，无法按开篇改正宫格。")
        if opening_error_claimed(summary):
            grafted = accept_revised_main_prompt(source_prompt, revised_text)
        else:
            grafted = graft_quad_onto_opening(source_prompt, revised_text)
        if grafted.strip() == source_prompt.strip():
            return
        writes.append({
            "entity_id": main_id,
            "field": "generation_prompt_cn",
            "value": grafted,
            "kind": "main",
        })
        if remember_submitted:
            writes.append({
                "entity_id": main_id,
                "field": LAST_SUBMITTED_PROMPT_ATTR,
                "value": grafted,
                "kind": "main",
            })
        if "四向拼图" not in targets:
            targets.append("四向拼图")

    if kind == "main":
        if not revised:
            raise ConsistencyApplyError("宫格和开篇不一致，但没有返回改写后的四向拼图。")
        _add_grids(main_prompt or checked_prompt, revised, True)
    elif kind == "crop":
        if not revised_main:
            raise ConsistencyApplyError("切割图对应的宫格和开篇不一致，但没有返回改写后的四向拼图。")
        _add_grids(main_prompt, revised_main, False)
    else:
        field_name = "grid_regen_prompt" if kind == "regen" else "generation_prompt_cn"
        label = "重生修正提示词" if kind == "regen" else "衍生环境提示词"
        if not revised or revised.strip() == str(checked_prompt or "").strip():
            raise ConsistencyApplyError("衍生环境和开篇不一致，但没有返回改写后的衍生提示词。")
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

    if not writes:
        return {
            "consistent": True,
            "kind": kind,
            "summary": summary or "宫格已与主环境开篇一致。",
            "writes": [],
            "updated_targets": [],
            "image_edit_instruction": image_edit_instruction,
        }
    return {
        "consistent": False,
        "kind": kind,
        "summary": summary or "已按主环境开篇更新宫格或衍生提示词。",
        "writes": writes,
        "updated_targets": targets,
        "image_edit_instruction": image_edit_instruction,
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


def remote_vision_image_link(url: str) -> str:
    """Public http(s) address a vision model can fetch itself.

    Consistency checks pass this link instead of a base64 data URL. Inlining the
    image makes the request body large enough to hit the stream write timeout.
    """
    raw = str(url or "").strip()
    if not raw or raw.lower().startswith("data:"):
        return ""
    if not raw.startswith(("http://", "https://")):
        return ""
    host = (urlparse(raw).hostname or "").strip().lower()
    if not host or host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return ""
    return raw


def build_consistency_messages(
    *,
    image_url: str,
    entity: Any,
    main_entity: Optional[Any],
    checked_prompt: str,
    kind: str,
) -> List[Dict[str, Any]]:
    system_prompt = (
        "你是环境资产一致性校对。主环境开篇在【四向拼图】之前，是权威。"
        "按开篇核对四个宫格正文，以及图片里同一格的主体个数、朝向、位置。\n"
        "图片对格：左上是0度格望北，右上是90度格望东，左下是180度格望南，右下是270度格望西。"
        "衍生图、切割图、重生图只核对自己的那一个角度。\n"
        "个数：开篇点名并且这一格该看见的主体，正文写一次，图片里出现一次。"
        "多一件、少一件、同一个名字变成两个身体，都不一致。"
        "开篇写了镜后不入画的，这一格正文不点名，图片里也不出现。\n"
        "件数核销：每一格的正面、左侧面、右侧面、中部、上都要核对。"
        "件数=和点名=必须等于这一面正文里不同主体的个数。"
        "点名+划出等于开篇；中部再减去改入。算式对上还不够。"
        "划出大于 0 必须写划出名，逐个列出本面没有的主体，个数等于划出。"
        "只写划出数字、没有划出名，就是不一致。"
        "镜头脚停在后壁近面之前。原点与后壁之间的桌、案、椅、凳在镜头脚前面。"
        "望北写在远离镜头的公案和椅，望南必须写成靠近镜头并点名，禁止划出。"
        "某一格中部点过的主体，另外三格中部仍要点名。少一件就改这一格的正文和件数核销。\n"
        "朝向：先用开篇竖边推出这一格的长边画面轴。"
        "南北走向时，0度和180度的长边从靠近镜头伸向远离镜头，90度和270度的长边从画面左铺到画面右。"
        "东西走向把这两类对调。0度与180度对调两端，90度与270度对调左右。"
        "椅面朝向、床头和床尾按同一格旋转，四格各写各的。"
        "正文或图片和这个结果相反，就是朝向不一致。\n"
        "位置：开篇的南北差，在望北和望南写成靠近镜头或远离镜头，在望东和望西写成画面左或画面右。"
        "东西差对调。0度与180度、90度与270度都要左右对调，并且近远对调。"
        "心点或在桌侧旋反了，就是位置不一致。\n"
        "一致：宫格正文和衍生正文都能被开篇解释，图片里的个数、朝向、位置也和这个结果相同。"
        "缝档、光色、材质的小差异算一致。"
        "正文已经对齐开篇、只有图片画错时，也算一致，summary 写明哪一格的图片错在个数、朝向或位置。"
        "revised_prompt 和 revised_main_prompt 都为 null。提示词保持对齐开篇。"
        "这时 image_edit_instruction 仍要写出怎么改这张图。\n"
        "不一致：同一件的宫格长边或朝向和开篇竖边旋出的画面轴相反；件数和开篇不同；"
        "左右或远近和开篇心点、在桌侧旋出的结果相反；衍生正文和开篇不是同一处空间。\n"
        "修改：只改宫格或衍生里和开篇不符的句子，保留主体名字。不要新造第二套房间。\n"
        "开篇默认保持原句，东南西北、占地、竖边、心点和朝向保持原值。"
        "只有开篇内部互相矛盾时才改开篇：同一件写出两个相反的竖边；"
        "竖边是东西走向而两端写成北端和南端；主体编号表的件数和正文点名的件数不同；椅面朝向和在桌侧相反。"
        "图片或宫格和开篇不同，保持开篇，改宫格或衍生。"
        "开篇内部矛盾时，consistent 为 false，summary 以「开篇有误：」开头。"
        "主环境图把含改正开篇的完整提示词写进 revised_prompt；切割图写进 revised_main_prompt。"
        "开篇里只改正互相矛盾的那几句，并改正受影响的宫格。"
        "summary 不以「开篇有误：」开头时，改过的开篇会被丢掉，只采用【四向拼图】。\n"
        "四向拼图必须保留四个宫格标题：[0度格-左上、[90度格-右上、[180度格-左下、[270度格-右下。\n"
        "桌、案、凳、椅、沙发、床、榻的宫格句只写长边落到哪条画面轴，禁止写几成、一半、占房间、一半宽。\n"
        "含「只切割」或「不要重切宫格」的提示词不要改成场景描写。这类图若宫格和开篇不符，"
        "只在 revised_main_prompt 里给出改后的完整主环境提示词，revised_prompt 必须为 null。\n"
        "状态衍生上的临时变化，例如沙尘、天气、破损，留在衍生正文里，不要写回主环境。\n"
        "重生修正或衍生描写和开篇不符时，只改这份衍生提示词，revised_main_prompt 必须为 null。\n"
        "一致时 revised_prompt 和 revised_main_prompt 都必须为 null。\n"
        "改图指令：图片里某一格的主体个数、朝向或位置和开篇旋出的结果不同时，"
        "image_edit_instruction 写给改图模型的中文指令。点名哪一格、哪一件、要改成的个数或朝向或位置，"
        "并写明其余画面保持不动。用画面左、画面右、靠近镜头、远离镜头，不要写东南西北，不要重写整段环境提示词。"
        "图片已经相符时，image_edit_instruction 必须为 null。\n"
        "只返回 JSON 对象，第一个字符是 {，最后一个字符是 }。不要 Markdown，不要解释。\n"
        '{"consistent": true或false, "summary": "一两句中文", "revised_prompt": null或完整提示词, "revised_main_prompt": null或完整主环境提示词, "image_edit_instruction": null或改图指令}'
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
            parts.append(
                "这次生成用的是切割提示词。不要改写切割提示词。"
                "核对该角度图片和该格正文的主体个数、件数核销、朝向、位置。"
                "和开篇不符时，把完整主环境提示词写进 revised_main_prompt，只改【四向拼图】。"
                "只有开篇内部互相矛盾时，summary 以「开篇有误：」开头，并在 revised_main_prompt 里改正开篇。"
            )
        else:
            parts.append(
                "核对该角度图片和这份衍生正文的主体个数、件数核销、朝向、位置。"
                "和开篇不符时，把对齐开篇后的完整衍生提示词写进 revised_prompt。revised_main_prompt 置 null。"
                "重生和衍生检查不改开篇，也不改主环境。"
            )
    else:
        parts.append(
            "这是主环境四宫格图。按左上0度、右上90度、左下180度、右下270度，逐格核对正文和图片的主体个数、件数核销、朝向、位置。"
            "和开篇不符时，把完整主环境提示词写进 revised_prompt，只改【四向拼图】，revised_main_prompt 置 null。"
            "只有开篇内部互相矛盾时，summary 以「开篇有误：」开头，并在 revised_prompt 里改正开篇。"
        )
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

