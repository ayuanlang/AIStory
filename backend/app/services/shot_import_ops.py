# -*- coding: utf-8 -*-
"""Import validated shot markdown rows into the Shot table."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.all_models import Entity, Episode, Project, Scene, Shot
from app.services.deletion_ops import _soft_delete_shots
from app.services.shot_markdown import (
    SHOT_MARKDOWN_COLUMN_WHITELIST,
    _dedupe_active_shot_records_for_display,
    _dedupe_shot_rows_for_import,
    _find_active_shot_by_business_id,
    _normalize_shot_business_id,
    _normalize_shot_markdown_col_key,
    _pick_shot_cell,
    _soft_delete_duplicate_active_shots_in_db,
)
from app.services.soft_delete import _active_shot_clause

logger = logging.getLogger("api_logger")

def _import_scene_shot_rows_to_db(
    *,
    scene_id: int,
    db: Session,
    scene: Scene,
    episode: Episode,
    project: Project,
    shots_data: List[Dict[str, Any]],
    skipped_row_errors: Optional[List[str]] = None,
    replace_existing: bool = False,
) -> List[Shot]:
    """
    Import validated shot rows into Shot table.
    This method is DB-import only and does NOT call LLM or write staged LLM markdown.

    Default policy: if the scene already has active shots, abandon the import
    (unless replace_existing=True for intentional UI replace).
    """
    skipped_row_errors = list(skipped_row_errors or [])

    locked_scene = db.query(Scene).filter(Scene.id == scene_id).with_for_update().first()
    if not locked_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    existing_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()
    existing_count = len(existing_shots or [])
    if existing_count > 0 and not replace_existing:
        logger.info(
            "[apply_scene_ai_result] abandon_import scene already has shots | scene_id=%s count=%s",
            scene_id,
            existing_count,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Scene already has {existing_count} shot(s); import abandoned. "
                "Delete existing shots first, or pass replace_existing=true to overwrite."
            ),
        )

    deduped_shots_data, dedupe_warnings = _dedupe_shot_rows_for_import(
        list(shots_data or []),
        scene_id=scene_id,
    )
    for warning in dedupe_warnings:
        skipped_row_errors.append(f"dedupe: {warning}")
    shots_data = deduped_shots_data

    # Episode-scoped uniqueness: project + episode + Shot ID (active rows only).
    # Blocks duplicate-scene imports from writing the same EP##_SC##_SH## twice.
    conflicting: List[str] = []
    for idx, row in enumerate(shots_data or [], start=1):
        raw_shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
        business_id = _normalize_shot_business_id(raw_shot_id)
        if not business_id:
            continue
        if isinstance(row, dict):
            # Persist normalized business id so unique index compares consistently.
            for key in ("Shot ID", "shot_id", "镜头ID"):
                if key in row:
                    row[key] = business_id
                    break
            else:
                row["Shot ID"] = business_id
        # When replacing, this scene's actives will be soft-deleted first — only other scenes conflict.
        dup = _find_active_shot_by_business_id(
            db,
            project_id=int(project.id),
            episode_id=int(episode.id),
            shot_id=business_id,
            exclude_scene_id=int(scene_id) if replace_existing else None,
        )
        if dup is not None:
            conflicting.append(
                f"{business_id} (existing scene_id={getattr(dup, 'scene_id', None)} db_id={getattr(dup, 'id', None)})"
            )
    if conflicting:
        sample = "; ".join(conflicting[:5])
        more = f"; and {len(conflicting) - 5} more" if len(conflicting) > 5 else ""
        logger.info(
            "[apply_scene_ai_result] abandon_import episode-unique Shot ID conflict | scene_id=%s episode_id=%s conflicts=%s",
            scene_id,
            getattr(episode, "id", None),
            len(conflicting),
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Shot ID already exists in this project/episode; import abandoned. "
                f"Conflicts: {sample}{more}"
            ),
        )

    # 1) Extract and normalize associated entities text only (no auto-create).
    try:
        if shots_data:
            existing_entities = db.query(Entity).filter(Entity.project_id == project.id).all()
            entity_map = {e.name: e for e in existing_entities}
            new_entities_buffer = set()

            for s_data in shots_data:
                assoc_str = s_data.get("Associated Entities", "")
                if assoc_str and assoc_str.lower() != "none" and assoc_str.strip():
                    potential_names = [n.strip() for n in re.split(r'[,\uff0c]', assoc_str) if n.strip()]
                    cleaned_names = []
                    for name in potential_names:
                        if name in entity_map:
                            cleaned_names.append(name)
                        elif name in new_entities_buffer:
                            cleaned_names.append(name)
                        else:
                            cleaned_names.append(name)
                    s_data["Associated Entities"] = ", ".join(cleaned_names)
    except Exception as e:
        logger.error(f"[Import] Entity auto-linking failed: {e}")

    # 2) Replace scene shots with imported rows (only when empty or replace_existing).
    old_shot_map = {(str(s.shot_id or "").strip()): s for s in existing_shots if str(s.shot_id or "").strip()}
    _soft_delete_shots(db, scene_id=scene_id)

    def _split_combined_cn_prompt(raw_text: str) -> Tuple[str, str, str, str]:
        text = str(raw_text or "").strip()
        if not text:
            return "", "", "", ""
        lines = [ln.strip() for ln in re.split(r"\n|<br\\s*/?>", text) if ln and ln.strip()]
        start_cn = ""
        video_cn = ""
        keyframes_cn = ""
        end_cn = ""
        for ln in lines:
            lower_ln = ln.lower()
            if (
                lower_ln.startswith("start frame:")
                or lower_ln.startswith("start frame cn:")
                or lower_ln.startswith("start:")
                or ln.startswith("起始帧:")
                or ln.startswith("起始帧：")
            ):
                start_cn = re.sub(r"^(start\s*frame\s*(cn)?\s*:|start\s*:|起始帧\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue
            if lower_ln.startswith("video:") or lower_ln.startswith("video cn:") or ln.startswith("视频:") or ln.startswith("视频提示词:"):
                video_cn = re.sub(r"^(video\s*(cn)?\s*:|视频提示词\s*[:：]|视频\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue
            if (
                lower_ln.startswith("keyframes:")
                or lower_ln.startswith("keyframes cn:")
                or lower_ln.startswith("keyframe:")
                or ln.startswith("关键帧:")
                or ln.startswith("关键帧：")
            ):
                keyframes_cn = re.sub(r"^(key\s*frames?\s*(cn)?\s*:|关键帧\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue
            if (
                lower_ln.startswith("end frame:")
                or lower_ln.startswith("end frame cn:")
                or lower_ln.startswith("end:")
                or ln.startswith("收尾帧:")
                or ln.startswith("收尾帧：")
                or ln.startswith("结束帧:")
                or ln.startswith("结束帧：")
            ):
                end_cn = re.sub(r"^(end\s*frame\s*(cn)?\s*:|end\s*:|收尾帧\s*[:：]|结束帧\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue

        if not start_cn and not video_cn and not keyframes_cn and not end_cn:
            return text, text, text, text
        if not end_cn and start_cn:
            end_cn = start_cn
        return start_cn, video_cn, keyframes_cn, end_cn

    known_col_aliases = [
        "Shot ID", "shot_id", "镜头ID",
        "Shot Name", "shot_name", "镜头名称",
        "Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场次号",
        "Start Frame", "start_frame", "起始帧",
        "End Frame", "end_frame", "结束帧",
        "Video Content", "video_content", "视频内容",
        "Duration (s)", "Duration", "duration", "时长", "时长(s)",
        "Associated Entities", "associated_entities", "关联实体",
        "Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）",
        "Keyframes", "keyframes", "关键帧",
        "Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词",
        "Start Frame (CN)", "start_frame_cn", "起始帧（中文）",
        "Video Content (CN)", "video_prompt_cn", "视频内容（中文）",
        "Keyframes (CN)", "keyframes_cn", "关键帧（中文）", "关键帧中文",
        "End Frame (CN)", "end_frame_cn", "结束帧（中文）",
    ]
    known_col_norm_set = {_normalize_shot_markdown_col_key(k) for k in known_col_aliases}

    for idx, s_data in enumerate(shots_data):
        try:
            dur_val = 2.0
            raw_duration = _pick_shot_cell(s_data, ["Duration (s)", "Duration", "duration", "时长", "时长(s)"], "")
            if raw_duration:
                match = re.search(r"[\d\.]+", str(raw_duration))
                dur_val = float(match.group()) if match else 2.0
        except Exception:
            dur_val = 2.0

        start_frame_text = _pick_shot_cell(s_data, ["Start Frame", "start_frame", "起始帧"], "")
        end_frame_text = _pick_shot_cell(s_data, ["End Frame", "end_frame", "结束帧"], "")
        video_content_text = _pick_shot_cell(s_data, ["Video Content", "video_content", "视频内容"], "")
        associated_entities_text = _pick_shot_cell(s_data, ["Associated Entities", "associated_entities", "关联实体"], "")
        shot_logic_cn_text = _pick_shot_cell(s_data, ["Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）"], "")
        keyframes_text = _pick_shot_cell(s_data, ["Keyframes", "keyframes", "关键帧"], "NO")
        scene_code_text = _pick_shot_cell(s_data, ["Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场次号"], scene.scene_no or "")
        shot_id_text = _pick_shot_cell(s_data, ["Shot ID", "shot_id", "镜头ID"], str(idx + 1))
        shot_name_text = _pick_shot_cell(s_data, ["Shot Name", "shot_name", "镜头名称"], "Shot")

        prompt_cn_combined = _pick_shot_cell(
            s_data,
            ["Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词"],
            "",
        )
        start_frame_cn_text = _pick_shot_cell(s_data, ["Start Frame (CN)", "start_frame_cn", "起始帧（中文）"], "")
        video_prompt_cn_text = _pick_shot_cell(s_data, ["Video Content (CN)", "video_prompt_cn", "视频内容（中文）"], "")
        keyframes_cn_text = _pick_shot_cell(s_data, ["Keyframes (CN)", "keyframes_cn", "关键帧（中文）", "关键帧中文"], "")
        end_frame_cn_text = _pick_shot_cell(s_data, ["End Frame (CN)", "end_frame_cn", "结束帧（中文）"], "")

        if prompt_cn_combined:
            start_cn_fallback, video_cn_fallback, keyframes_cn_fallback, end_cn_fallback = _split_combined_cn_prompt(prompt_cn_combined)
            if not start_frame_cn_text:
                start_frame_cn_text = start_cn_fallback
            if not end_frame_cn_text:
                end_frame_cn_text = end_cn_fallback
            if not video_prompt_cn_text:
                video_prompt_cn_text = video_cn_fallback
            if not keyframes_cn_text:
                keyframes_cn_text = keyframes_cn_fallback

        technical_notes_payload: Dict[str, Any] = {}
        if start_frame_cn_text:
            technical_notes_payload["start_frame_cn"] = start_frame_cn_text
        if video_prompt_cn_text:
            technical_notes_payload["video_prompt_cn"] = video_prompt_cn_text
        if keyframes_cn_text:
            technical_notes_payload["keyframes_cn"] = keyframes_cn_text
        if end_frame_cn_text:
            technical_notes_payload["end_frame_cn"] = end_frame_cn_text
        if start_frame_cn_text or video_prompt_cn_text or keyframes_cn_text or end_frame_cn_text:
            technical_notes_payload["shot_prompt_cn"] = "<br>".join([
                f"起始帧：{start_frame_cn_text or ''}",
                f"视频：{video_prompt_cn_text or ''}",
                f"关键帧：{keyframes_cn_text or ''}",
                f"收尾帧：{end_frame_cn_text or ''}",
            ])

        extra_columns: Dict[str, str] = {}
        if isinstance(s_data, dict):
            for raw_key, raw_val in s_data.items():
                nk = _normalize_shot_markdown_col_key(raw_key)
                if nk in known_col_norm_set:
                    continue
                val = str(raw_val or "").strip()
                if not val:
                    continue
                rule = SHOT_MARKDOWN_COLUMN_WHITELIST.get(nk)
                if rule and rule.get("target") == "tech_field":
                    tech_key = str(rule.get("field") or "").strip()
                    if tech_key:
                        technical_notes_payload[tech_key] = val
                        continue
                extra_columns[str(raw_key)] = val
        if extra_columns:
            technical_notes_payload["shot_extra_columns"] = extra_columns

        normalized_shot_id = _normalize_shot_business_id(shot_id_text) or str(shot_id_text or "").strip()
        old_shot = old_shot_map.get(normalized_shot_id) or old_shot_map.get(str(shot_id_text).strip())
        preserved_image_url = None
        preserved_video_url = None
        if old_shot:
            preserved_image_url = old_shot.image_url
            preserved_video_url = old_shot.video_url
            try:
                old_tech = json.loads(old_shot.technical_notes) if old_shot.technical_notes else {}
                for k, v in old_tech.items():
                    if k.endswith("_url") or k.endswith("_urls") or k in {"start_frame_supported", "supports_start_frame"}:
                        if k not in technical_notes_payload:
                            technical_notes_payload[k] = v
            except Exception:
                pass

        shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            shot_id=normalized_shot_id,
            shot_name=shot_name_text,
            scene_code=scene_code_text,
            start_frame=start_frame_text,
            end_frame=end_frame_text,
            video_content=video_content_text,
            duration=str(dur_val),
            associated_entities=associated_entities_text,
            shot_logic_cn=shot_logic_cn_text,
            keyframes=keyframes_text,
            prompt=video_content_text,
            image_url=preserved_image_url,
            video_url=preserved_video_url,
            technical_notes=(json.dumps(technical_notes_payload, ensure_ascii=False) if technical_notes_payload else None),
        )
        db.add(shot)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "[shot_import.apply] unique constraint conflict scene_id=%s episode_id=%s err=%s",
            scene_id,
            getattr(episode, "id", None),
            exc,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Shot ID already exists for this project/episode (unique index); import abandoned."
            ),
        ) from exc
    _soft_delete_duplicate_active_shots_in_db(
        db,
        episode_id=int(episode.id),
        project_id=int(project.id),
        scope="episode",
    )
    db.commit()

    applied_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()
    applied_shots = _dedupe_active_shot_records_for_display(applied_shots)
    if skipped_row_errors:
        try:
            for shot in applied_shots:
                notes_obj = {}
                if getattr(shot, "technical_notes", None):
                    try:
                        notes_obj = json.loads(shot.technical_notes) if isinstance(shot.technical_notes, str) else {}
                    except Exception:
                        notes_obj = {}
                notes_obj["import_warnings"] = list(
                    dict.fromkeys([str(x or "").strip() for x in skipped_row_errors if str(x or "").strip()])
                )
                shot.technical_notes = json.dumps(notes_obj, ensure_ascii=False)
            db.commit()
            applied_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()
        except Exception:
            db.rollback()
            applied_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()

    logger.info(
        "[shot_import.apply] applied scene_id=%s episode_id=%s project_id=%s rows=%s skipped=%s",
        scene_id,
        getattr(episode, "id", None),
        getattr(project, "id", None),
        len(applied_shots),
        len(skipped_row_errors),
    )
    return applied_shots
