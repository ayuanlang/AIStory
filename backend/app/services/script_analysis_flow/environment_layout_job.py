# -*- coding: utf-8 -*-
"""After 现场编排, render one white model per main environment without blocking staging.

The text model writes the room script. Characters and props from 【白模测算】
are appended at the locked meters. Blender renders the sheet in its own process.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_BLOCK_RE = re.compile(r"【白模测算】([\s\S]*?)【/白模测算】")
_COMPASS = {"东", "南", "西", "北", "上"}
_WAIT_TRIES = 24
_WAIT_SECONDS = 5.0


def _compass(fields: Dict[str, str]) -> str:
    for key in ("罗盘朝向", "朝向"):
        token = str(fields.get(key) or "").strip()
        if token in _COMPASS:
            return token
    return ""


def white_model_groups(text: str) -> List[Dict[str, Any]]:
    """Opening boxes for each 环境= block. People and props stay with that room."""
    from app.services.script_analysis_flow.framing_visibility import _box_from, _fields, parse_framing

    groups: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    def ensure() -> Dict[str, Any]:
        nonlocal current
        if current is None:
            current = {"name": "", "fixtures": [], "people": [], "props": []}
            groups.append(current)
        return current

    for block in _BLOCK_RE.findall(str(text or "")):
        for raw in block.splitlines():
            fields = _fields(raw)
            if not fields:
                continue
            if "环境" in fields and not any(key in fields for key in ("具", "人", "件")):
                current = {
                    "name": str(fields.get("环境") or "").strip(),
                    "fixtures": [],
                    "people": [],
                    "props": [],
                }
                groups.append(current)
                continue
            beat = str(fields.get("拍") or "开场").strip() or "开场"
            for kind, bucket in (("具", "fixtures"), ("人", "people"), ("件", "props")):
                if kind not in fields:
                    continue
                if kind != "具" and beat not in {"开场", ""}:
                    continue
                box = _box_from(kind, fields)
                if box is None:
                    continue
                box["face"] = _compass(fields)
                ensure()[bucket].append(box)
    if len(groups) == 1 and not groups[0]["people"] and not groups[0]["props"]:
        parsed = parse_framing(text)
        extra = [
            box
            for box in parsed.get("boxes") or []
            if box.get("kind") in {"人", "件"} and str(box.get("beat") or "开场") in {"开场", ""}
        ]
        if not extra:
            for rows in (parsed.get("beat_boxes") or {}).values():
                extra = [box for box in rows if box.get("kind") in {"人", "件"}]
                if extra:
                    break
        for box in extra:
            bucket = "people" if box.get("kind") == "人" else "props"
            groups[0][bucket].append(box)
    return [
        group
        for group in groups
        if group["name"] or group["fixtures"] or group["people"] or group["props"]
    ]


def _group_name(group: Dict[str, Any], main_names: Sequence[str]) -> str:
    name = str(group.get("name") or "").strip()
    if name:
        return name
    names = [str(item or "").strip() for item in main_names if str(item or "").strip()]
    if len(names) == 1:
        return names[0]
    return ""


def _fixture_opening(fixtures: Sequence[Dict[str, Any]]) -> str:
    lines = ["【白模测算】"]
    for box in fixtures:
        lines.append(
            "具={name}｜东={east}｜北={north}｜底={bottom}｜沿东={along_east}｜沿北={along_north}｜高={height}".format(
                name=box.get("name") or "",
                east=box.get("east") or 0,
                north=box.get("north") or 0,
                bottom=box.get("bottom") or 0,
                along_east=box.get("along_east") or 0.4,
                along_north=box.get("along_north") or 0.4,
                height=box.get("height") or 0.2,
            )
        )
    return "\n".join(lines) if len(lines) > 1 else ""


def schedule_scene_white_model(
    *,
    project_id: int,
    episode_id: int,
    scene_id: str,
    user_id: int,
    username: str,
    framing_text: str,
    main_names: Sequence[str],
) -> None:
    """Start the white-model job and return. Staging does not wait."""
    if int(project_id or 0) <= 0 or int(user_id or 0) <= 0:
        return
    groups = white_model_groups(framing_text)
    if not groups:
        logger.info("[scene_white_model] skip scene=%s no boxes", scene_id or "-")
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.info("[scene_white_model] skip scene=%s no running loop", scene_id or "-")
        return
    task = loop.create_task(
        run_scene_white_model(
            project_id=int(project_id),
            episode_id=int(episode_id or 0),
            scene_id=str(scene_id or ""),
            user_id=int(user_id),
            username=str(username or ""),
            groups=groups,
            main_names=list(main_names or []),
        )
    )

    def _done(done: asyncio.Task) -> None:
        try:
            exc = done.exception()
        except asyncio.CancelledError:
            return
        if exc:
            logger.warning("[scene_white_model] scene=%s err=%s", scene_id or "-", exc)

    task.add_done_callback(_done)
    logger.info(
        "[scene_white_model] scheduled scene=%s groups=%s",
        scene_id or "-",
        len(groups),
    )


_CELL_BY_ANGLE = {0: "左上", 90: "右上", 180: "左下", 270: "右下"}


def _quad_cell_url(entity: Any, angle: int) -> str:
    if entity is None:
        return ""
    import json

    from app.services.script_analysis_flow.derived_env_ingest import _quad_cell_record
    from app.services.script_analysis_flow.environment_consistency import attrs_of

    record = _quad_cell_record(attrs_of(entity))
    cells = record.get("cells")
    if isinstance(cells, str) and cells.strip():
        try:
            cells = json.loads(cells)
        except json.JSONDecodeError:
            cells = None
    if not isinstance(cells, dict):
        return ""
    value = cells.get(_CELL_BY_ANGLE.get(int(angle), ""))
    if isinstance(value, dict):
        value = value.get("url") or value.get("image_url") or value.get("href")
    return str(value or "").strip()


def _find_named_environment(db: Any, project_id: int, name: str) -> Any:
    from app.models.all_models import Entity
    from app.services.script_analysis_flow.environment_consistency import is_environment_entity
    from app.services.script_analysis_flow.environment_reuse import normalize_environment_name
    from app.services.soft_delete import _active_entity_clause

    key = normalize_environment_name(name)
    if not key:
        return None
    rows = (
        db.query(Entity)
        .filter(Entity.project_id == int(project_id), _active_entity_clause())
        .all()
    )
    found = None
    for row in rows:
        if not is_environment_entity(row):
            continue
        if normalize_environment_name(getattr(row, "name", "")) != key:
            continue
        if str(getattr(row, "image_url", "") or "").strip():
            return row
        found = row
    return found


def derived_environment_image_url(db: Any, project_id: int, name: str, angle: int, main_entity: Any = None) -> str:
    """The picture of this derived view. A cropped cell wins over the four-grid sheet."""
    row = _find_named_environment(db, int(project_id), name)
    cell = _quad_cell_url(row, angle) or _quad_cell_url(main_entity, angle)
    if cell:
        return cell
    return str(getattr(row, "image_url", "") or "").strip() if row is not None else ""


def _find_main_environment(db: Any, project_id: int, name: str) -> Any:
    from app.models.all_models import Entity
    from app.services.script_analysis_flow.environment_consistency import is_main_environment_entity
    from app.services.script_analysis_flow.environment_reuse import normalize_environment_name
    from app.services.soft_delete import _active_entity_clause

    key = normalize_environment_name(name)
    if not key:
        return None
    rows = (
        db.query(Entity)
        .filter(Entity.project_id == int(project_id), _active_entity_clause())
        .all()
    )
    for row in rows:
        if not is_main_environment_entity(row):
            continue
        if normalize_environment_name(getattr(row, "name", "")) == key:
            return row
    return None


async def _wait_opening(project_id: int, name: str) -> tuple[int, str]:
    from app.db.session import SessionLocal
    from app.services.script_analysis_flow.environment_consistency import main_environment_opening_text

    found_id = 0
    opening = ""
    for _ in range(_WAIT_TRIES):
        db = SessionLocal()
        try:
            entity = _find_main_environment(db, project_id, name)
            if entity is not None:
                found_id = int(entity.id)
                opening = str(main_environment_opening_text(entity) or "").strip()
                if opening:
                    return found_id, opening
        finally:
            db.close()
        await asyncio.sleep(_WAIT_SECONDS)
    return found_id, opening


def _upload_layout_bytes(binary: bytes, user_id: int, suffix: str = "png", content_type: str = "image/png") -> str:
    from app.core.config import settings
    from app.services.oss_storage_service import oss_storage_service

    filename = f"env_layout_{uuid.uuid4().hex[:16]}.{suffix}"
    uploaded = oss_storage_service.upload_bytes(
        binary,
        user_id=int(user_id),
        filename=filename,
        content_type=content_type,
        category="generated",
        cache_control="public, max-age=31536000",
    )
    url = str((uploaded or {}).get("url") or "").strip()
    if url:
        return url
    user_dir = os.path.join(settings.UPLOAD_DIR, str(user_id))
    if not os.path.isabs(user_dir):
        user_dir = os.path.abspath(user_dir)
    os.makedirs(user_dir, exist_ok=True)
    with open(os.path.join(user_dir, filename), "wb") as handle:
        handle.write(binary)
    relative = f"/uploads/{user_id}/{filename}"
    external = str(getattr(settings, "RENDER_EXTERNAL_URL", "") or "").rstrip("/")
    return f"{external}{relative}" if external else relative


def _store_layout(
    db: Any,
    entity: Any,
    binary: bytes,
    boxes: Sequence[Any],
    user_id: int,
    script: str = "",
    opening_digest: str = "",
) -> str:
    from sqlalchemy.orm.attributes import flag_modified

    from app.services.script_analysis_flow.environment_layout import layout_box_records

    url = _upload_layout_bytes(binary, int(user_id))
    attrs = dict(entity.custom_attributes) if isinstance(entity.custom_attributes, dict) else {}
    attrs["layout_image_url"] = url
    attrs["layout_boxes"] = layout_box_records(boxes)
    if str(script or "").strip():
        attrs["layout_script"] = str(script).strip()
    if str(opening_digest or "").strip():
        attrs["layout_opening_digest"] = str(opening_digest).strip()
    entity.custom_attributes = attrs
    flag_modified(entity, "custom_attributes")
    db.commit()
    return url


def _fallback_script(fixtures: Sequence[Dict[str, Any]], occupants: str) -> str:
    from app.services.script_analysis_flow.environment_layout import merge_occupant_script

    lines = ["FOCAL_MM = 35"]
    for box in fixtures:
        name = str(box.get("name") or "").strip()
        if not name:
            continue
        lines.append(
            "mass({name}, \"furniture\", east={east}, north={north}, along_east={along_east}, along_north={along_north}, height={height}, bottom={bottom})".format(
                name=json_name(name),
                east=_num(box.get("east")),
                north=_num(box.get("north")),
                along_east=_num(box.get("along_east"), 0.4),
                along_north=_num(box.get("along_north"), 0.4),
                height=_num(box.get("height"), 0.2),
                bottom=_num(box.get("bottom")),
            )
        )
    body = "\n".join(lines)
    if body.count("mass(") == 0 and not str(occupants or "").strip():
        return ""
    return merge_occupant_script(body, occupants)


def json_name(name: str) -> str:
    import json

    return json.dumps(name, ensure_ascii=False)


def _num(value: Any, default: float = 0.0) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    text = f"{number:.4f}".rstrip("0").rstrip(".")
    return text or "0"


async def _render_group(
    *,
    project_id: int,
    user_id: int,
    username: str,
    name: str,
    opening: str,
    occupants: str,
    fixtures: Sequence[Dict[str, Any]],
    entity_id: int,
    views: Optional[Sequence[str]] = None,
    view_images: Optional[Dict[str, str]] = None,
    animate_prompt: str = "",
    animate_seconds: float = 4.0,
) -> Dict[str, Any]:
    from app.db.session import SessionLocal
    from app.models.all_models import User
    from app.services.billing_service import billing_service
    from app.services.llm_service import llm_service
    from app.services.model_invocation_billing import (
        _cancel_reservation_quietly,
        _finalize_model_invocation_billing,
    )
    from app.services.script_analysis_flow.environment_layout import (
        LayoutError,
        apply_facing,
        boxes_from_layout_script,
        layout_messages,
        layout_script_from_model_text,
        layout_script_gaps,
        merge_occupant_script,
    )
    from app.services.script_analysis_flow.environment_layout_blender import (
        LayoutRenderError,
        render_white_model,
    )
    from app.services.script_analysis_llm_config import _resolve_script_analysis_dropdown_llm_config

    db = SessionLocal()
    reservation_tx_id: Optional[int] = None
    chosen_views = []
    for item in views or []:
        view = str(item or "").strip().lower()
        if view and view not in chosen_views:
            chosen_views.append(view)
    pictures: Dict[str, str] = {}
    for view, url in (view_images or {}).items():
        key = str(view or "").strip().lower()
        link = str(url or "").strip()
        if key and link:
            pictures[key] = link

    def view_picture_list() -> List[str]:
        found: List[str] = []
        for view in chosen_views:
            link = pictures.get(view, "")
            if link and link not in found:
                found.append(link)
        return found
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None:
            logger.info("[scene_white_model] skip name=%s no user", name)
            return {"name": name, "entity_id": int(entity_id), "image_url": "", "error": "没有用户"}
        llm_config, selected_dropdown_id, _, _ = _resolve_script_analysis_dropdown_llm_config(
            db,
            int(user_id),
            "script_analysis",
            None,
            context="environment_layout",
        )
        provider = str(llm_config.get("provider") or "").strip()
        model = str(llm_config.get("model") or "").strip()
        if not provider or not model:
            logger.info("[scene_white_model] skip name=%s no model", name)
            return {"name": name, "entity_id": int(entity_id), "image_url": "", "error": "没有可用模型"}
        raw_config = llm_config.get("config")
        api_config = dict(raw_config) if isinstance(raw_config, dict) else {}
        room_text = "" if view_picture_list() else opening
        messages = layout_messages(room_text, occupants=occupants, images=view_picture_list())
        call_config = {
            "provider": provider,
            "api_key": str(llm_config.get("api_key") or "").strip() or None,
            "base_url": str(llm_config.get("base_url") or "").strip() or None,
            "model": model,
            "config": {
                **api_config,
                "__resolved_user_id": int(user_id),
                "__resolved_user_name": username,
                "__resolved_project_id": int(project_id),
                "__resolved_action": "环境布局",
                "__selected_system_api_id": selected_dropdown_id,
            },
        }
        if billing_service.is_token_pricing(db, "analysis_character", provider, model):
            estimate = billing_service.estimate_reserve_tokens_from_messages(messages)
            est_input = int(estimate.get("input_tokens", 0) or 0)
            est_output = int(math.ceil(float(est_input) * billing_service.RESERVE_OUTPUT_RATIO)) if est_input > 0 else 0
            reservation = billing_service.reserve_credits(
                db,
                int(user_id),
                "analysis_character",
                provider,
                model,
                {
                    "item": "environment_layout",
                    "estimation_method": "prompt_tokens_ratio",
                    "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                    "input_tokens": est_input,
                    "output_tokens": est_output,
                    "total_tokens": int(est_input + est_output),
                },
            )
            try:
                reservation_tx_id = int(getattr(reservation, "id", 0) or 0) or None
            except Exception:
                reservation_tx_id = None
        else:
            cost = billing_service.estimate_cost(db, "analysis_character", provider, model)
            billing_service.check_can_proceed(user, cost)
        db.close()
        db = None

        response = await llm_service.chat_completion_with_fallback(messages, call_config)
        usage = (response or {}).get("usage", {}) if isinstance(response, dict) else {}

        def read_layout(content: str) -> tuple[str, list]:
            script_text, layout_boxes = layout_script_from_model_text(content)
            if str(room_text or "").strip():
                gap = layout_script_gaps(room_text, layout_boxes)
                if gap:
                    raise LayoutError(gap)
                script_text = apply_facing(script_text, room_text)
            elif view_picture_list():
                from app.services.script_analysis_flow.environment_layout import image_room_gaps

                gap = image_room_gaps(layout_boxes)
                if gap:
                    raise LayoutError(gap)
            script_text = merge_occupant_script(script_text, occupants)
            layout_boxes, _meta = boxes_from_layout_script(script_text)
            return script_text, layout_boxes

        try:
            script, boxes = read_layout(str((response or {}).get("content", "") or ""))
        except LayoutError as first_error:
            try:
                retry = await llm_service.chat_completion_with_fallback(
                    layout_messages(room_text, str(first_error), occupants=occupants, images=view_picture_list()),
                    call_config,
                )
                if isinstance(retry, dict):
                    response = retry
                script, boxes = read_layout(str((retry or {}).get("content", "") or ""))
            except LayoutError:
                if view_picture_list():
                    raise
                script = _fallback_script(fixtures, occupants)
                if not script:
                    raise
                boxes = boxes_from_layout_script(script)[0]

        async def motion_for(script_text: str, view: str) -> str:
            from app.services.script_analysis_flow.environment_layout import (
                animation_messages,
                animation_script_from_model_text,
                fallback_motion,
                mass_names,
                missing_occupant_moves,
            )

            names = mass_names(script_text)

            async def ask(missing: str = "") -> str:
                reply = await llm_service.chat_completion_with_fallback(
                    animation_messages(
                        animate_prompt,
                        script_text,
                        view,
                        animate_seconds,
                        missing,
                        images=[pictures[view]] if pictures.get(view) else [],
                    ),
                    call_config,
                )
                extra = (reply or {}).get("usage", {}) if isinstance(reply, dict) else {}
                if isinstance(usage, dict) and isinstance(extra, dict):
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
                        if key in extra:
                            try:
                                usage[key] = int(usage.get(key, 0) or 0) + int(extra.get(key, 0) or 0)
                            except (TypeError, ValueError):
                                pass
                return animation_script_from_model_text(
                    str((reply or {}).get("content", "") or ""),
                    view=view,
                    names=names,
                    seconds=animate_seconds,
                )

            try:
                motion = await ask()
            except LayoutError:
                return fallback_motion(view, animate_seconds)
            gap = missing_occupant_moves(motion, names)
            if not gap:
                return motion
            try:
                return await ask(gap)
            except LayoutError:
                return motion

        async def paint(script_text: str) -> List[tuple]:
            if not chosen_views:
                binary = await asyncio.to_thread(render_white_model, script_text)
                return [("", binary, "image")]
            frames = []
            for view in chosen_views:
                if str(animate_prompt or "").strip():
                    motion = await motion_for(script_text, view)
                    binary = await asyncio.to_thread(render_white_model, script_text, view, motion)
                    frames.append((view, binary, "video"))
                else:
                    binary = await asyncio.to_thread(render_white_model, script_text, view)
                    frames.append((view, binary, "image"))
            return frames

        try:
            frames = await paint(script)
        except LayoutRenderError as render_error:
            tail = " ".join(str(render_error).split())[:500]
            revised = await llm_service.chat_completion_with_fallback(
                layout_messages(room_text, f"白模渲染报错：{tail}", script, occupants=occupants, images=view_picture_list()),
                call_config,
            )
            if isinstance(revised, dict):
                response = revised
            script, boxes = read_layout(str((revised or {}).get("content", "") or ""))
            frames = await paint(script)

        from app.models.all_models import Entity

        db = SessionLocal()
        if chosen_views:
            sheets = []
            for frame in frames:
                view, binary = frame[0], frame[1]
                kind = frame[2] if len(frame) > 2 else "image"
                if not binary:
                    continue
                if kind == "video":
                    url = _upload_layout_bytes(binary, int(user_id), suffix="mp4", content_type="video/mp4")
                    sheets.append({"view": view, "image_url": url, "video_url": url})
                else:
                    sheets.append({"view": view, "image_url": _upload_layout_bytes(binary, int(user_id))})
            url = str(sheets[0]["image_url"]) if sheets else ""
        else:
            entity = db.query(Entity).filter(Entity.id == int(entity_id)).first()
            if entity is None:
                _cancel_reservation_quietly(db, reservation_tx_id, "entity missing")
                return {"name": name, "entity_id": int(entity_id), "image_url": "", "error": "环境不在库里"}
            binary = frames[0][1]
            from app.services.script_analysis_flow.environment_quad_facing import opening_digest

            url = _store_layout(
                db,
                entity,
                binary,
                boxes,
                int(user_id),
                script=script,
                opening_digest=opening_digest(opening),
            )
            sheets = []
        fresh_user = db.query(User).filter(User.id == int(user_id)).first()
        if fresh_user is not None:
            _finalize_model_invocation_billing(
                db=db,
                current_user=fresh_user,
                task_type="analysis_character",
                provider=provider,
                model=model,
                reservation_tx=None,
                reservation_tx_id=reservation_tx_id,
                item="environment_layout",
                usage_payload=usage if isinstance(usage, dict) else None,
                extra_details={
                    "entity_id": int(entity_id),
                    "project_id": int(project_id),
                    "request_scope": "environment_layout",
                    "box_count": len(boxes),
                },
                routing_payload=response if isinstance(response, dict) else None,
            )
        logger.info("[scene_white_model] stored name=%s entity=%s url=%s", name, entity_id, url[:80])
        return {
            "name": name,
            "entity_id": int(entity_id),
            "image_url": url,
            "box_count": len(boxes),
            "sheets": sheets,
            "script": script,
            "error": "",
        }
    except Exception as exc:
        logger.warning("[scene_white_model] name=%s failed: %s", name, exc)
        cancel_db = db
        opened = False
        if cancel_db is None and reservation_tx_id:
            cancel_db = SessionLocal()
            opened = True
        if cancel_db is not None and reservation_tx_id:
            _cancel_reservation_quietly(cancel_db, reservation_tx_id, str(exc))
        if opened and cancel_db is not None:
            cancel_db.close()
        return {"name": name, "entity_id": int(entity_id), "image_url": "", "error": str(exc)}
    finally:
        if db is not None:
            db.close()


async def run_scene_white_model(
    *,
    project_id: int,
    episode_id: int,
    scene_id: str,
    user_id: int,
    username: str,
    groups: Sequence[Dict[str, Any]],
    main_names: Sequence[str],
) -> None:
    from app.services.script_analysis_flow.environment_layout import occupant_mass_script

    del episode_id
    for group in groups:
        name = _group_name(group, main_names)
        if not name:
            logger.info("[scene_white_model] skip scene=%s unnamed group", scene_id or "-")
            continue
        occupants = occupant_mass_script([*(group.get("people") or []), *(group.get("props") or [])])
        entity_id, opening = await _wait_opening(project_id, name)
        source = opening or _fixture_opening(group.get("fixtures") or [])
        if entity_id <= 0 or not source:
            logger.info("[scene_white_model] skip scene=%s name=%s no opening", scene_id or "-", name)
            continue
        logger.info(
            "[scene_white_model] render scene=%s name=%s people=%s",
            scene_id or "-",
            name,
            occupants.count("person"),
        )
        await _render_group(
            project_id=project_id,
            user_id=user_id,
            username=username,
            name=name,
            opening=source,
            occupants=occupants,
            fixtures=list(group.get("fixtures") or []),
            entity_id=entity_id,
        )


async def generate_scene_white_model(
    *,
    project_id: int,
    episode_id: int,
    scene_id: str,
    user_id: int,
    username: str,
    framing_text: str,
) -> Dict[str, Any]:
    """Render this scene's white models now. Characters and props stay on the sheet."""
    from app.db.session import SessionLocal
    from app.services.script_analysis_flow.environment_consistency import main_environment_opening_text
    from app.services.script_analysis_flow.environment_layout import occupant_mass_script

    groups = white_model_groups(framing_text)
    if not groups:
        raise ValueError("现场编排里没有白模盒")
    sheets: List[Dict[str, Any]] = []
    for group in groups:
        name = _group_name(group, [])
        if not name:
            sheets.append({"name": "", "entity_id": 0, "image_url": "", "error": "白模没有环境名"})
            continue
        occupants = occupant_mass_script([*(group.get("people") or []), *(group.get("props") or [])])
        db = SessionLocal()
        try:
            entity = _find_main_environment(db, int(project_id), name)
            entity_id = int(entity.id) if entity is not None else 0
            opening = str(main_environment_opening_text(entity) or "").strip() if entity is not None else ""
        finally:
            db.close()
        source = opening or _fixture_opening(group.get("fixtures") or [])
        if entity_id <= 0:
            sheets.append({"name": name, "entity_id": 0, "image_url": "", "error": "主环境还没有入库"})
            continue
        if not source:
            sheets.append({"name": name, "entity_id": entity_id, "image_url": "", "error": "没有开篇"})
            continue
        sheets.append(
            await _render_group(
                project_id=int(project_id),
                user_id=int(user_id),
                username=str(username or ""),
                name=name,
                opening=source,
                occupants=occupants,
                fixtures=list(group.get("fixtures") or []),
                entity_id=entity_id,
            )
        )
    return {"scene_id": str(scene_id or ""), "episode_id": int(episode_id or 0), "sheets": sheets}


def framing_text_for_scene(
    result_map: Optional[Dict[str, Any]],
    scene_id: str,
    pipeline_rows: Optional[Dict[str, Any]] = None,
) -> str:
    """Framing draft for this scene, including a bare scene number stored under another key."""
    from app.services.script_analysis_flow.analyze_scene_stages import same_scene_result_keys

    mapping = result_map if isinstance(result_map, dict) else {}
    keys: List[str] = []
    for key in [str(scene_id or "").strip(), *same_scene_result_keys(mapping, scene_id)]:
        if key and key not in keys:
            keys.append(key)
    for key in keys:
        steps = mapping.get(key)
        if not isinstance(steps, dict):
            continue
        for name in ("framing", "derived_framing"):
            text = str(steps.get(name) or "").strip()
            if text:
                return text
    rows = pipeline_rows if isinstance(pipeline_rows, dict) else {}
    for key in same_scene_result_keys(rows, scene_id):
        row = rows.get(key)
        block = str((row or {}).get("scene_block") or "").strip() if isinstance(row, dict) else ""
        if "【白模测算】" in block:
            return block
    return ""


def shot_pose_boxes(framing_text: str, beat_ids: Sequence[int]) -> Dict[str, Any]:
    """People and props for this shot. The first listed beat wins; otherwise the opening pose."""
    from app.services.script_analysis_flow.framing_visibility import parse_framing

    groups = white_model_groups(framing_text)
    parsed = parse_framing(framing_text)
    beat_boxes = parsed.get("beat_boxes") or {}
    for beat_id in beat_ids or []:
        key = str(int(beat_id))
        rows = beat_boxes.get(key) or []
        if not rows:
            continue
        return {
            "beat": key,
            "people": [box for box in rows if box.get("kind") == "人"],
            "props": [box for box in rows if box.get("kind") == "件"],
            "fixtures": [box for box in rows if box.get("kind") == "具"],
            "groups": groups,
        }
    return {
        "beat": "开场",
        "people": [box for group in groups for box in group.get("people") or []],
        "props": [box for group in groups for box in group.get("props") or []],
        "fixtures": [box for group in groups for box in group.get("fixtures") or []],
        "groups": groups,
    }


_ENV_TAG_RE = re.compile(r"ENV\s*:\s*\[\s*@?([^\]\n]+?)\s*\]", re.IGNORECASE)
_SHOT_VIEW = {0: "north", 90: "east", 180: "south", 270: "west"}


def shot_derived_targets(hint: str) -> List[Dict[str, Any]]:
    """Derived environments this shot names. Each one is a single camera."""
    from app.services.script_analysis_flow.derived_env_ingest import _angle_from_name, _main_from_name

    found: List[Dict[str, Any]] = []
    seen = set()
    for match in _ENV_TAG_RE.finditer(str(hint or "")):
        name = str(match.group(1) or "").strip()
        if not name or name in seen:
            continue
        angle = _angle_from_name(name)
        if angle not in _SHOT_VIEW:
            continue
        main = str(_main_from_name(name) or "").strip()
        if not main:
            continue
        seen.add(name)
        found.append({
            "name": name,
            "angle": int(angle),
            "view": _SHOT_VIEW[int(angle)],
            "main": main,
        })
    return found


async def generate_shot_white_model(
    *,
    project_id: int,
    shot_id: int,
    user_id: int,
    username: str,
    framing_text: str,
    beat_ids: Sequence[int],
    hint: str,
    prompt: str = "",
    duration: str = "",
) -> Dict[str, Any]:
    """Render one white-model clip per derived environment, moving with this shot's prompt."""
    from app.services.script_analysis_flow.environment_layout import shot_anim_seconds

    story = str(prompt or "").strip()
    if not story:
        raise ValueError("这一镜没有分镜提示词")
    seconds = shot_anim_seconds(duration, story)
    import json

    from app.db.session import SessionLocal
    from app.models.all_models import Shot
    from app.services.script_analysis_flow.environment_layout import occupant_mass_script

    targets = shot_derived_targets(hint)
    if not targets:
        raise ValueError("这一镜没有选定衍生环境")
    pose = shot_pose_boxes(framing_text, beat_ids)
    occupants = occupant_mass_script([*(pose.get("people") or []), *(pose.get("props") or [])])
    by_main: Dict[str, List[Dict[str, Any]]] = {}
    for target in targets:
        by_main.setdefault(str(target["main"]), []).append(target)
    sheets: List[Dict[str, Any]] = []
    errors: List[str] = []
    for main, items in by_main.items():
        views: List[str] = []
        for item in items:
            if item["view"] not in views:
                views.append(str(item["view"]))
        db = SessionLocal()
        try:
            entity = _find_main_environment(db, int(project_id), main)
            entity_id = int(entity.id) if entity is not None else 0
            view_images = {
                str(item["view"]): derived_environment_image_url(
                    db, int(project_id), str(item["name"]), int(item["angle"]), entity,
                )
                for item in items
            }
        finally:
            db.close()
        if not any(str(url or "").strip() for url in view_images.values()):
            errors.append(f"{main}：没有衍生环境图")
            continue
        rendered = await _render_group(
            project_id=int(project_id),
            user_id=int(user_id),
            username=str(username or ""),
            name=main,
            opening="",
            occupants=occupants,
            fixtures=list(pose.get("fixtures") or []),
            entity_id=entity_id,
            views=views,
            view_images=view_images,
            animate_prompt=story,
            animate_seconds=seconds,
        )
        by_view = {
            str(row.get("view") or ""): str(row.get("video_url") or row.get("image_url") or "").strip()
            for row in (rendered or {}).get("sheets") or []
        }
        if not by_view:
            errors.append(f"{main}：{str((rendered or {}).get('error') or '白模没有返回图片')}")
            continue
        for item in items:
            url = by_view.get(str(item["view"]) or "")
            if not url:
                errors.append(f"{item['name']}：白模没有返回图片")
                continue
            sheets.append({
                "name": str(item["name"]),
                "angle": int(item["angle"]),
                "image_url": url,
                "video_url": url,
            })
    if not sheets:
        raise ValueError(errors[0] if errors else "白模没有返回图片")
    db = SessionLocal()
    try:
        shot = db.query(Shot).filter(Shot.id == int(shot_id)).first()
        if shot is None:
            raise ValueError("分镜不在库里")
        try:
            notes = json.loads(shot.technical_notes or "{}")
        except json.JSONDecodeError:
            notes = {}
        if not isinstance(notes, dict):
            notes = {}
        notes.pop("white_model_url", None)
        notes["white_model_sheets"] = sheets
        notes["white_model_beat"] = str(pose.get("beat") or "")
        shot.technical_notes = json.dumps(notes, ensure_ascii=False)
        db.commit()
        stored_notes = shot.technical_notes
    finally:
        db.close()
    return {
        "shot_id": int(shot_id),
        "beat": str(pose.get("beat") or ""),
        "image_url": sheets[0]["image_url"],
        "sheets": sheets,
        "errors": errors,
        "technical_notes": stored_notes,
    }


def _main_environment_entity(db: Any, project_id: int, episode_id: int, name: str) -> Any:
    from app.models.all_models import Entity
    from app.services.script_analysis_flow.environment_consistency import (
        is_derived_environment_entity,
        is_environment_entity,
    )
    from app.services.script_analysis_flow.environment_reuse import normalize_environment_name
    from app.services.soft_delete import _active_entity_clause

    target = normalize_environment_name(name)
    if not target or int(project_id) <= 0 or int(episode_id) <= 0:
        return None
    rows = (
        db.query(Entity)
        .filter(
            Entity.project_id == int(project_id),
            Entity.episode_id == int(episode_id),
            _active_entity_clause(),
        )
        .all()
    )
    for row in rows:
        if not is_environment_entity(row) or is_derived_environment_entity(row):
            continue
        if normalize_environment_name(getattr(row, "name", "")) == target:
            return row
    return None


async def prepare_quad_facing_locks(
    db: Any,
    *,
    project_id: int,
    episode_id: int,
    user_id: int,
    username: str,
    source_text: str,
) -> str:
    """Render each main environment's white model, then return the facing locks.

    A stored script is reused when it was built from this same opening.
    Characters and props are not included.
    """
    from app.services.script_analysis_flow.derived_env_ingest import (
        extract_named_design_openings,
        list_main_environment_draft_names,
    )
    from app.services.script_analysis_flow.environment_layout import LayoutError
    from app.services.script_analysis_flow.environment_quad_facing import (
        opening_digest,
        quad_facing_lock,
    )

    names = list_main_environment_draft_names(source_text)
    if not names:
        return ""
    openings = extract_named_design_openings(source_text)
    try:
        db.commit()
    except Exception:
        db.rollback()
    blocks: List[str] = []
    for name in names:
        opening = str(openings.get(name.lower()) or "").strip()
        if not opening:
            raise LayoutError(f"{name}：没有开篇，不能先出白模。")
        entity = _main_environment_entity(db, int(project_id), int(episode_id), name)
        if entity is None:
            raise LayoutError(f"{name}：没有这块主环境，不能先出白模。")
        entity_id = int(getattr(entity, "id", 0) or 0)
        attrs = dict(entity.custom_attributes) if isinstance(entity.custom_attributes, dict) else {}
        try:
            db.commit()
        except Exception:
            db.rollback()
        digest = opening_digest(opening)
        script = str(attrs.get("layout_script") or "").strip()
        if str(attrs.get("layout_opening_digest") or "") != digest or not script:
            logger.info("[quad_white_model] render name=%s entity=%s", name, entity_id)
            rendered = await _render_group(
                project_id=int(project_id),
                user_id=int(user_id),
                username=str(username or ""),
                name=name,
                opening=opening,
                occupants="",
                fixtures=[],
                entity_id=entity_id,
            )
            error = str((rendered or {}).get("error") or "").strip()
            script = str((rendered or {}).get("script") or "").strip()
            if error or not script:
                raise LayoutError(f"{name}：白模没有生成，四宫提示词先不写。{error}")
        lock = quad_facing_lock(name, script)
        if lock:
            blocks.append(lock)
    db.expire_all()
    return "\n\n".join(blocks)
