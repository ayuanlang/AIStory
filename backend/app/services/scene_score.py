# -*- coding: utf-8 -*-
"""One post-production score per scene, timed to the storyboard."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.all_models import (
    Episode,
    Project,
    Scene,
    ScriptProgressPipelineNode,
    Shot,
    SystemAPISetting,
    User,
)
from app.schemas.generation import VoiceGenerationRequest
from app.services.scene_no_utils import _find_active_scene_by_scene_no, _scene_no_lookup_keys
from app.services.soft_delete import _active_shot_clause
from app.services.video_service import _resolve_ffmpeg_exe, _resolve_ffprobe_exe, _run_ffmpeg

logger = logging.getLogger("api_logger")

_P_RE = re.compile(
    r"P\d+\(\s*(\d+(?:\.\d+)?)s\s*[–\-]\s*(\d+(?:\.\d+)?)s\s*\)\s*=\s*(起|续|变|收)\s*[·．.]\s*(弱|中|强)"
)
_STATE_RE = re.compile(r"态\s*=\s*(起|续|变|收)")
_VOLUME_RE = re.compile(r"音量\s*=\s*(弱|中|强)")
_STYLE_RE = re.compile(r"风格\s*=\s*([^｜|\n]+)")
_VOCAL_RE = re.compile(r"梵唱|体系人声|合唱|吟唱|步虚|哼唱")
_CUE_RE = re.compile(r"【声画综合】([^\n【]{0,800})")
_GAIN = {"弱": "0.28", "中": "0.62", "强": "1"}


def parse_duration_seconds(raw: Any) -> Optional[float]:
    text = str(raw or "").strip().lower().replace("秒", "s")
    text = text.replace(" ", "")
    if not text:
        return None
    matched = re.fullmatch(r"(\d+(?:\.\d+)?)s?", text)
    if matched:
        value = float(matched.group(1))
        return value if value > 0 else None
    clock = re.fullmatch(r"(\d+):(\d{1,2})(?:\.(\d+))?", text)
    if clock:
        seconds = int(clock.group(1)) * 60 + int(clock.group(2))
        if clock.group(3):
            seconds += float(f"0.{clock.group(3)}")
        return float(seconds) if seconds > 0 else None
    return None


def _shot_sort_key(shot_id: str) -> tuple:
    nums = tuple(int(item) for item in re.findall(r"\d+", str(shot_id or "")))
    return (nums, str(shot_id or ""))


def _parse_logic_pieces(logic: str) -> List[Dict[str, Any]]:
    pieces: List[Dict[str, Any]] = []
    for match in _P_RE.finditer(str(logic or "")):
        start = float(match.group(1))
        end = float(match.group(2))
        if end <= start:
            continue
        pieces.append({
            "start": start,
            "end": end,
            "state": match.group(3),
            "volume": match.group(4),
        })
    pieces.sort(key=lambda item: (item["start"], item["end"]))
    return pieces


def _loose_state_volume(logic: str) -> Tuple[str, str]:
    state_match = _STATE_RE.search(str(logic or ""))
    volume_match = _VOLUME_RE.search(str(logic or ""))
    return (
        state_match.group(1) if state_match else "续",
        volume_match.group(1) if volume_match else "中",
    )


def build_scene_score_timeline(shots: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], float, List[str]]:
    """Picture length is the sum of shot durations. Score states sit on that timeline."""
    ordered = sorted(shots, key=lambda item: _shot_sort_key(str(item.get("shot_id") or "")))
    segments: List[Dict[str, Any]] = []
    missing: List[str] = []
    cursor = 0.0
    for shot in ordered:
        shot_id = str(shot.get("shot_id") or "").strip() or "未编号"
        duration = parse_duration_seconds(shot.get("duration"))
        pieces = _parse_logic_pieces(str(shot.get("logic") or ""))
        if duration is None and pieces:
            duration = float(pieces[-1]["end"] - pieces[0]["start"])
        if duration is None or duration <= 0:
            missing.append(shot_id)
            continue
        if pieces:
            origin = float(pieces[0]["start"])
            span = float(pieces[-1]["end"] - origin)
            scale = (duration / span) if span > 0.05 and abs(span - duration) > 0.4 else 1.0
            for piece in pieces:
                start = cursor + (float(piece["start"]) - origin) * scale
                end = cursor + (float(piece["end"]) - origin) * scale
                if end - start < 0.05:
                    continue
                segments.append({
                    "start": round(start, 3),
                    "end": round(min(cursor + duration, end), 3),
                    "state": piece["state"],
                    "volume": piece["volume"],
                    "shot_id": shot_id,
                })
        else:
            state, volume = _loose_state_volume(str(shot.get("logic") or ""))
            segments.append({
                "start": round(cursor, 3),
                "end": round(cursor + duration, 3),
                "state": state,
                "volume": volume,
                "shot_id": shot_id,
            })
        cursor += duration
    if segments:
        segments[-1]["end"] = round(cursor, 3)
    return segments, round(cursor, 3), missing


def build_volume_expr(segments: List[Dict[str, Any]]) -> str:
    if not segments:
        return "0.62"
    expr = _GAIN.get(str(segments[-1].get("volume") or ""), "0.62")
    for segment in reversed(segments[:-1]):
        gain = _GAIN.get(str(segment.get("volume") or ""), "0.62")
        end = float(segment.get("end") or 0)
        expr = f"if(lt(t,{end:.3f}),{gain},{expr})"
    return expr


def extract_score_cue(scene_block: str) -> str:
    match = _CUE_RE.search(str(scene_block or ""))
    return str(match.group(1) or "").strip() if match else ""


def score_needs_vocals(*parts: str) -> bool:
    blob = "\n".join(str(part or "") for part in parts)
    return bool(_VOCAL_RE.search(blob))


def extract_score_style(*parts: str) -> str:
    blob = "\n".join(str(part or "") for part in parts)
    match = _STYLE_RE.search(blob)
    style = str(match.group(1) or "").strip() if match else ""
    return style or "Classical"


def build_scene_score_prompt(
    *,
    total_seconds: float,
    segments: List[Dict[str, Any]],
    music_recommendation: str,
    cue: str,
    instrumental: bool,
) -> str:
    groups: List[Dict[str, Any]] = []
    for segment in segments:
        if (
            groups
            and groups[-1]["state"] == segment["state"]
            and groups[-1]["volume"] == segment["volume"]
        ):
            groups[-1]["end"] = segment["end"]
            continue
        groups.append({
            "start": segment["start"],
            "end": segment["end"],
            "state": segment["state"],
            "volume": segment["volume"],
        })
    structure = "；".join(
        f"{float(group['start']):.0f}秒{group['state']}，音量{group['volume']}"
        for group in groups
    )
    lines = [
        f"一首连续配乐，总长约{total_seconds:.0f}秒。同一首从起到收，不要另起一首，不要对白。",
    ]
    music = str(music_recommendation or "").strip()
    if music:
        lines.append(f"项目配乐：{music[:500]}")
    cue_text = str(cue or "").strip()
    if cue_text:
        lines.append(f"本场：{cue_text[:500]}")
    if structure:
        lines.append(f"结构：{structure}。")
    if instrumental:
        lines.append("纯器乐，不要歌词，不要人声。")
    else:
        lines.append("可以有体系人声，不要对白台词。")
    return "\n".join(lines)


def _json_object(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _music_recommendation(project: Optional[Project], episode: Episode) -> str:
    episode_info = _json_object(getattr(episode, "episode_info", None))
    project_info = _json_object(getattr(project, "global_info", None) if project else None)
    for source in (episode_info, project_info):
        text = str(source.get("music_recommendation") or source.get("配乐推荐") or "").strip()
        if text:
            return text
    return ""


def _scene_block_for_marker(db: Session, episode_id: int, scene_marker: str) -> str:
    rows = (
        db.query(ScriptProgressPipelineNode)
        .filter(
            ScriptProgressPipelineNode.episode_id == int(episode_id),
            ScriptProgressPipelineNode.node_name == "scene_subskill_scene",
        )
        .all()
    )
    wanted = str(scene_marker or "").strip().lower()
    for row in rows:
        sid = str(getattr(row, "scene_id", "") or "").strip().lower()
        if sid != wanted:
            continue
        meta = getattr(row, "runtime_meta", None)
        if isinstance(meta, dict):
            return str(meta.get("scene_block") or "")
    return ""


def _load_scene_shots(db: Session, episode_id: int, scene: Scene, scene_marker: str) -> List[Shot]:
    keys = _scene_no_lookup_keys(scene.scene_no, scene_id=scene_marker)
    by_id: Dict[int, Shot] = {}
    linked = (
        db.query(Shot)
        .filter(
            Shot.episode_id == int(episode_id),
            Shot.scene_id == int(scene.id),
            _active_shot_clause(),
        )
        .all()
    )
    for shot in linked:
        by_id[int(shot.id)] = shot
    if keys:
        coded = (
            db.query(Shot)
            .filter(
                Shot.episode_id == int(episode_id),
                Shot.scene_code.in_(keys),
                _active_shot_clause(),
            )
            .all()
        )
        for shot in coded:
            by_id[int(shot.id)] = shot
    return list(by_id.values())


def is_suno_system_api(db: Session, system_api_id: int) -> bool:
    row = db.query(SystemAPISetting).filter(SystemAPISetting.id == int(system_api_id)).first()
    if row is None or bool(getattr(row, "deprecated", False)):
        return False
    blob = f"{getattr(row, 'model', '') or ''} {getattr(row, 'name', '') or ''}".lower()
    return "suno" in blob


def find_suno_system_api_id(db: Session) -> Optional[int]:
    rows = db.query(SystemAPISetting).all()
    fallback: Optional[int] = None
    for row in rows:
        if bool(getattr(row, "deprecated", False)):
            continue
        model = str(getattr(row, "model", "") or "").strip().lower()
        name = str(getattr(row, "name", "") or "").strip().lower()
        if "suno" not in model and "suno" not in name:
            continue
        row_id = int(row.id)
        if model == "suno" or name == "kie suno":
            return row_id
        fallback = fallback or row_id
    return fallback


def _download_audio(url: str, work_dir: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        raise RuntimeError("配乐文件地址为空")
    parsed = urlparse(raw)
    path_part = parsed.path or raw
    if "/uploads/" in path_part:
        relative = path_part.split("/uploads/", 1)[1]
        local_path = os.path.join(settings.UPLOAD_DIR, relative.replace("/", os.sep))
        if os.path.exists(local_path):
            return local_path
    if parsed.scheme in {"http", "https"}:
        ext = os.path.splitext(path_part)[1] or ".mp3"
        if len(ext) > 8:
            ext = ".mp3"
        local_path = os.path.join(work_dir, f"source_{uuid.uuid4().hex}{ext}")
        with requests.get(raw, stream=True, timeout=120) as response:
            response.raise_for_status()
            with open(local_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        handle.write(chunk)
        return local_path
    candidate = raw if os.path.isabs(raw) else os.path.join(settings.UPLOAD_DIR, raw.lstrip("/\\"))
    if os.path.exists(candidate):
        return candidate
    raise RuntimeError("配乐文件不在本地，也不是可下载的地址")


def _probe_audio_seconds(path: str) -> Optional[float]:
    probe = _resolve_ffprobe_exe(_resolve_ffmpeg_exe())
    if not probe:
        return None
    completed = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        value = float(str(completed.stdout or "").strip())
    except Exception:
        return None
    return value if value > 0 else None


def fit_score_audio(
    source_url: str,
    *,
    target_seconds: float,
    segments: List[Dict[str, Any]],
    user_id: int,
    filename: str,
) -> Tuple[str, Optional[float]]:
    work_dir = tempfile.mkdtemp(prefix="scene_score_")
    try:
        source_path = _download_audio(source_url, work_dir)
        output_path = os.path.join(work_dir, filename)
        expr = build_volume_expr(segments)
        _run_ffmpeg([
            _resolve_ffmpeg_exe(),
            "-y",
            "-stream_loop", "-1",
            "-i", source_path,
            "-t", f"{float(target_seconds):.3f}",
            "-af", f"volume='{expr}':eval=frame",
            "-c:a", "libmp3lame",
            "-q:a", "2",
            output_path,
        ])
        probed = _probe_audio_seconds(output_path)
        try:
            from app.services.oss_storage_service import oss_storage_service

            uploaded = oss_storage_service.upload_file(
                output_path,
                user_id=int(user_id or 0),
                filename=filename,
                content_type="audio/mpeg",
                category="scene_score",
            )
            oss_url = str((uploaded or {}).get("url") or "").strip()
            if oss_url:
                return oss_url, probed
        except Exception as exc:
            logger.warning("scene score OSS upload failed: %s", exc)

        relative_name = filename
        if user_id:
            relative_name = f"{user_id}/{filename}"
            dest_dir = os.path.join(settings.UPLOAD_DIR, str(user_id))
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, filename)
            shutil.copyfile(output_path, dest_path)
        else:
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            shutil.copyfile(output_path, os.path.join(settings.UPLOAD_DIR, filename))
        return f"/uploads/{relative_name}", probed
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def score_plan_public(scene: Scene) -> Dict[str, Any]:
    plan = _json_object(getattr(scene, "score_plan", None))
    return {
        "scene_db_id": int(scene.id),
        "scene_no": str(scene.scene_no or ""),
        "scene_marker": str(plan.get("scene_marker") or ""),
        "audio_url": str(getattr(scene, "score_audio_url", None) or plan.get("audio_url") or ""),
        "duration_seconds": plan.get("duration_seconds"),
        "target_seconds": plan.get("target_seconds"),
        "status": str(plan.get("status") or ""),
        "fit_error": str(plan.get("fit_error") or ""),
        "segments": plan.get("segments") if isinstance(plan.get("segments"), list) else [],
    }


def list_scene_scores(db: Session, episode_id: int) -> List[Dict[str, Any]]:
    rows = (
        db.query(Scene)
        .filter(Scene.episode_id == int(episode_id))
        .all()
    )
    items = []
    for scene in rows:
        if bool(getattr(scene, "is_deleted", False)):
            continue
        if not str(getattr(scene, "score_audio_url", None) or "").strip() and not str(getattr(scene, "score_plan", None) or "").strip():
            continue
        items.append(score_plan_public(scene))
    return items


async def generate_scene_score(
    db: Session,
    *,
    episode: Episode,
    scene_marker: str,
    current_user: User,
    system_api_id: Optional[int] = None,
    function_name: Optional[str] = None,
) -> Dict[str, Any]:
    marker = str(scene_marker or "").strip()
    if not marker:
        raise HTTPException(status_code=400, detail="缺少场次")
    scene = _find_active_scene_by_scene_no(db, episode_id=int(episode.id), scene_no=marker, scene_id=marker)
    if scene is None:
        raise HTTPException(status_code=404, detail="这一场还没有导入场景，无法保存配乐")
    shots = _load_scene_shots(db, int(episode.id), scene, marker)
    if not shots:
        raise HTTPException(status_code=400, detail="本场还没有分镜。配乐时长按各镜秒数相加，请先生成分镜。")
    timeline_shots = [
        {
            "shot_id": str(shot.shot_id or ""),
            "duration": shot.duration,
            "logic": str(shot.shot_logic_cn or ""),
        }
        for shot in shots
    ]
    segments, total_seconds, missing = build_scene_score_timeline(timeline_shots)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"这些分镜没有时长，配乐对不齐：{'、'.join(missing)}",
        )
    if total_seconds < 1:
        raise HTTPException(status_code=400, detail="本场分镜总时长不足 1 秒")

    project = db.query(Project).filter(Project.id == int(episode.project_id)).first() if episode.project_id else None
    music = _music_recommendation(project, episode)
    cue = extract_score_cue(_scene_block_for_marker(db, int(episode.id), marker))
    instrumental = not score_needs_vocals(music, cue)
    prompt = build_scene_score_prompt(
        total_seconds=total_seconds,
        segments=segments,
        music_recommendation=music,
        cue=cue,
        instrumental=instrumental,
    )
    style = extract_score_style(music, cue)
    resolved_api_id = int(system_api_id) if system_api_id and is_suno_system_api(db, int(system_api_id)) else None
    if not resolved_api_id:
        resolved_api_id = find_suno_system_api_id(db)
    if not resolved_api_id:
        raise HTTPException(status_code=400, detail="系统里还没有 Suno 音频模型，请先启用 Kie Suno")
    user_id = int(getattr(current_user, "id", 0) or 0)
    project_id = int(episode.project_id) if episode.project_id else None
    scene_db_id = int(scene.id)
    episode_id = int(episode.id)

    from app.services.generation_runtime.voice_generation_runner import _run_generate_voice

    request = VoiceGenerationRequest(
        prompt=prompt,
        function_name=str(function_name or "").strip() or "generate_entity_reference_audio_audio",
        system_api_id=int(resolved_api_id),
        project_id=project_id,
        asset_type="scene_score",
        customMode=True,
        custom_mode=True,
        instrumental=instrumental,
        suno_style=style,
        sunoStyle=style,
        suno_title=f"{marker}配乐"[:80],
        sunoTitle=f"{marker}配乐"[:80],
        negativeTags="lyrics, vocals, speech, dialogue" if instrumental else "speech, dialogue",
        negative_tags="lyrics, vocals, speech, dialogue" if instrumental else "speech, dialogue",
        use_llm_param_planning=False,
    )
    result = await _run_generate_voice(request, current_user, db)
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="配乐生成没有返回结果")
    if result.get("error"):
        raise HTTPException(status_code=502, detail=str(result.get("error")))
    source_url = str(result.get("url") or "").strip()
    if not source_url:
        raise HTTPException(status_code=502, detail="配乐生成没有返回音频地址")

    scene = db.query(Scene).filter(Scene.id == scene_db_id).first()
    if scene is None:
        raise HTTPException(status_code=404, detail="场景在生成过程中不见了")

    fitted_url = source_url
    probed: Optional[float] = None
    fit_error = ""
    status = "raw"
    safe_marker = re.sub(r"[^0-9A-Za-z_-]+", "_", marker)[:40] or "scene"
    filename = f"scene_score_{episode_id}_{safe_marker}_{uuid.uuid4().hex[:8]}.mp3"
    try:
        fitted_url, probed = fit_score_audio(
            source_url,
            target_seconds=total_seconds,
            segments=segments,
            user_id=user_id,
            filename=filename,
        )
        status = "ready"
    except Exception as exc:
        fit_error = str(exc)
        logger.warning("scene score fit failed episode=%s scene=%s: %s", episode_id, marker, exc)
        status = "raw"

    plan = {
        "scene_marker": marker,
        "audio_url": fitted_url,
        "source_url": source_url,
        "target_seconds": total_seconds,
        "duration_seconds": probed if probed is not None else total_seconds,
        "status": status,
        "fit_error": fit_error,
        "prompt": prompt,
        "style": style,
        "instrumental": instrumental,
        "segments": segments,
        "shot_count": len(timeline_shots),
    }
    scene.score_audio_url = fitted_url
    scene.score_plan = json.dumps(plan, ensure_ascii=False)
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return score_plan_public(scene)
