# -*- coding: utf-8 -*-
"""Episode edit bay: subtitle cues, burn handoff, and a merged cut with score."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence
import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.all_models import Episode, Scene, Shot, SystemAPISetting, User
from app.services.scene_score import parse_duration_seconds
from app.services.soft_delete import _active_scene_clause, _active_shot_clause
from app.services.video_service import (
    _download_or_resolve_local_video,
    _resolve_ffmpeg_exe,
    _resolve_ffprobe_exe,
    _run_ffmpeg,
    _upload_processed_video,
)

logger = logging.getLogger("api_logger")

_DIALOGUE_RE = re.compile(r"\{([^{}\n]{1,80})\}")
_MAX_RECOGNIZE = 8
_MAX_MERGE = 500


def extract_dialogue_lines(*texts: Any) -> List[str]:
    lines: List[str] = []
    seen = set()
    for text in texts:
        for match in _DIALOGUE_RE.finditer(str(text or "")):
            line = str(match.group(1) or "").strip()
            if not line or line in {"闭嘴"} or line.startswith("闭嘴"):
                continue
            if line in seen:
                continue
            seen.add(line)
            lines.append(line)
    if lines:
        return lines
    try:
        from app.services.flower_text_ass import extract_libass_events

        blob = "\n".join(str(text or "") for text in texts)
        for event in extract_libass_events(blob, None):
            line = str(event.get("text") or "").strip()
            if not line or line in seen:
                continue
            seen.add(line)
            lines.append(line)
    except Exception:
        return lines
    return lines


def split_subtitle_cues(lines: Sequence[str], duration: float) -> List[Dict[str, Any]]:
    clean = [str(line or "").strip() for line in lines if str(line or "").strip()]
    total = float(duration or 0)
    if not clean or total <= 0:
        return []
    step = total / len(clean)
    cues: List[Dict[str, Any]] = []
    for index, line in enumerate(clean):
        start = round(index * step, 2)
        end = round(total if index == len(clean) - 1 else (index + 1) * step, 2)
        if end <= start:
            end = round(min(total, start + 0.4), 2)
        cues.append({"start": start, "end": end, "text": line})
    return cues


def parse_subtitle_cue_json(raw: str, duration: float) -> List[Dict[str, Any]]:
    text = str(raw or "").strip()
    match = re.search(r"\[[\s\S]*\]", text)
    payload = json.loads(match.group(0) if match else text)
    if not isinstance(payload, list):
        return []
    total = float(duration or 0)
    cues: List[Dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        line = str(item.get("text") or "").strip()
        if not line:
            continue
        try:
            start = max(0.0, float(item.get("start") or 0))
            end = float(item.get("end") or 0)
        except (TypeError, ValueError):
            continue
        if total > 0:
            end = min(total, end)
        if end <= start:
            continue
        cues.append({"start": round(start, 2), "end": round(end, 2), "text": line[:80]})
    return cues


def _notes(shot: Shot) -> Dict[str, Any]:
    raw = getattr(shot, "technical_notes", None)
    if isinstance(raw, dict):
        return dict(raw)
    try:
        parsed = json.loads(raw or "{}")
    except Exception:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _save_cues(shot: Shot, cues: List[Dict[str, Any]], source: str, notice: str) -> None:
    notes = _notes(shot)
    notes["edit_subtitles"] = cues
    notes["edit_subtitle_source"] = source
    notes["edit_subtitle_notice"] = notice
    shot.technical_notes = json.dumps(notes, ensure_ascii=False)


def _shot_duration(shot: Shot) -> float:
    return float(parse_duration_seconds(getattr(shot, "duration", None)) or 4.0)


def _find_stt_setting(db: Session) -> Optional[SystemAPISetting]:
    rows = db.query(SystemAPISetting).all()
    for row in rows:
        if bool(getattr(row, "deprecated", False)):
            continue
        blob = f"{getattr(row, 'model', '') or ''} {getattr(row, 'name', '') or ''}".lower()
        modality = getattr(row, "modality", None)
        if isinstance(modality, (dict, list)):
            blob = f"{blob} {json.dumps(modality, ensure_ascii=False)}".lower()
        else:
            blob = f"{blob} {modality or ''}".lower()
        if "speech-to-text" in blob or "speech_to_text" in blob or "stt" in blob:
            return row
    return None


def _extract_audio(video_url: str, work_dir: str) -> str:
    source = _download_or_resolve_local_video(video_url, work_dir)
    output = os.path.join(work_dir, f"speech_{uuid.uuid4().hex}.mp3")
    _run_ffmpeg([
        _resolve_ffmpeg_exe(),
        "-y",
        "-i", source,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-t", "120",
        output,
    ])
    return output


def _public_audio_url(path: str, user_id: int) -> str:
    from app.services.oss_storage_service import oss_storage_service

    uploaded = oss_storage_service.upload_file(
        path,
        user_id=int(user_id or 0),
        filename=os.path.basename(path),
        content_type="audio/mpeg",
        category="edit_stt",
    )
    return str((uploaded or {}).get("url") or "").strip()


def _kie_transcribe(setting: SystemAPISetting, audio_url: str) -> str:
    base = str(getattr(setting, "base_url", None) or "https://api.kie.ai").rstrip("/")
    api_key = str(getattr(setting, "api_key", None) or "").split(",")[0].strip()
    model = str(getattr(setting, "model", None) or "elevenlabs/speech-to-text").strip()
    if not api_key or not audio_url.startswith("http"):
        return ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    submitted = requests.post(
        f"{base}/api/v1/jobs/createTask",
        json={"model": model, "input": {"audio_url": audio_url}},
        headers=headers,
        timeout=60,
    )
    submitted.raise_for_status()
    body = submitted.json() if submitted.content else {}
    data = body.get("data") if isinstance(body, dict) else {}
    task_id = ""
    if isinstance(data, dict):
        task_id = str(data.get("taskId") or data.get("task_id") or "").strip()
    if not task_id and isinstance(body, dict):
        task_id = str(body.get("taskId") or "").strip()
    if not task_id:
        return ""
    for _ in range(30):
        time.sleep(2)
        polled = requests.get(
            f"{base}/api/v1/jobs/recordInfo",
            params={"taskId": task_id},
            headers=headers,
            timeout=30,
        )
        polled.raise_for_status()
        payload = polled.json() if polled.content else {}
        record = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        if not isinstance(record, dict):
            continue
        state = str(record.get("state") or record.get("status") or "").lower()
        if state in {"waiting", "queuing", "generating", "processing", "pending", "running"}:
            continue
        result = record.get("resultJson") or record.get("result") or record.get("output") or record
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                return result.strip()
        if isinstance(result, dict):
            text = result.get("text") or result.get("transcript") or result.get("result")
            if isinstance(text, str) and text.strip():
                return text.strip()
        if state in {"success", "succeeded", "completed", "fail", "failed", "error"}:
            break
    return ""


def _transcribe_shot(db: Session, shot: Shot, user_id: int) -> str:
    video_url = str(getattr(shot, "video_url", None) or "").strip()
    if not video_url:
        return ""
    setting = _find_stt_setting(db)
    if setting is None:
        return ""
    work_dir = tempfile.mkdtemp(prefix="edit_stt_")
    try:
        audio_path = _extract_audio(video_url, work_dir)
        public_url = _public_audio_url(audio_path, user_id)
        if not public_url.startswith("http"):
            return ""
        return _kie_transcribe(setting, public_url)
    except Exception as exc:
        logger.warning("edit stt failed shot=%s: %s", getattr(shot, "id", None), exc)
        return ""
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


async def _llm_time_cues(
    db: Session,
    user: User,
    *,
    duration: float,
    dialogue: List[str],
    transcript: str,
    system_api_id: Optional[int],
) -> List[Dict[str, Any]]:
    from app.services.llm_service import llm_service
    from app.services.script_analysis_llm_config import _resolve_script_analysis_dropdown_llm_config

    try:
        config, _, _, _ = _resolve_script_analysis_dropdown_llm_config(
            db,
            int(user.id),
            "script_analysis",
            system_api_id,
            context="edit_subtitles",
        )
    except Exception as exc:
        logger.info("edit subtitle llm config unavailable: %s", exc)
        return []
    messages = [
        {
            "role": "system",
            "content": (
                "你是字幕编辑。只输出 JSON 数组，每项含 start、end、text，单位秒。"
                "text 只能使用给出的识别文本或分镜对白，不要新写句子。"
                "时间落在镜头时长之内，按说话顺序排布，句与句不重叠。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"镜头时长 {duration:.1f} 秒。\n"
                f"语音识别：{transcript or '无'}\n"
                f"分镜对白：{' / '.join(dialogue) or '无'}"
            ),
        },
    ]
    try:
        response = await llm_service.chat_completion_with_fallback(
            messages,
            config,
            user_id=int(user.id),
            category="LLM",
        )
    except Exception as exc:
        logger.warning("edit subtitle llm failed: %s", exc)
        return []
    content = ""
    if isinstance(response, dict):
        content = str(response.get("content") or "")
    try:
        return parse_subtitle_cue_json(content, duration)
    except Exception:
        return []


def _episode_shots(db: Session, episode_id: int, shot_ids: Sequence[int]) -> List[Shot]:
    wanted = [int(item) for item in shot_ids if int(item) > 0]
    if not wanted:
        return []
    rows = (
        db.query(Shot)
        .filter(
            Shot.episode_id == int(episode_id),
            Shot.id.in_(wanted),
            _active_shot_clause(),
        )
        .all()
    )
    order = {shot_id: index for index, shot_id in enumerate(wanted)}
    return sorted(rows, key=lambda shot: order.get(int(shot.id), 9999))


async def recognize_shot_subtitles(
    db: Session,
    *,
    episode: Episode,
    shot_ids: Sequence[int],
    user: User,
    system_api_id: Optional[int] = None,
) -> Dict[str, Any]:
    shots = _episode_shots(db, int(episode.id), shot_ids)
    if not shots:
        raise HTTPException(status_code=400, detail="没有可识别的分镜")
    if len(shots) > _MAX_RECOGNIZE:
        raise HTTPException(status_code=400, detail=f"一次最多识别 {_MAX_RECOGNIZE} 镜")
    user_id = int(getattr(user, "id", 0) or 0)
    results = []
    for shot in shots:
        duration = _shot_duration(shot)
        dialogue = extract_dialogue_lines(shot.video_content, shot.shot_logic_cn, shot.prompt)
        transcript = _transcribe_shot(db, shot, user_id)
        source_lines = dialogue
        if transcript:
            source_lines = [part.strip() for part in re.split(r"[。！？\n]", transcript) if part.strip()] or dialogue
        cues = await _llm_time_cues(
            db,
            user,
            duration=duration,
            dialogue=dialogue,
            transcript=transcript,
            system_api_id=system_api_id,
        )
        if cues:
            source = "stt+llm" if transcript else "script+llm"
            notice = ""
        else:
            cues = split_subtitle_cues(source_lines or dialogue, duration)
            source = "stt" if transcript else "script"
            notice = "" if cues else "这一镜没有识别文本，也没有分镜对白"
        if not transcript and source.startswith("script"):
            notice = notice or "未拿到语音识别结果，字幕来自分镜对白"
        _save_cues(shot, cues, source, notice)
        db.add(shot)
        results.append({
            "id": int(shot.id),
            "shot_id": str(shot.shot_id or ""),
            "source": source,
            "notice": notice,
            "cues": cues,
        })
    db.commit()
    return {"shots": results}


def _score_url_for_shot(db: Session, shot: Shot) -> str:
    if not shot.scene_id:
        return ""
    scene = (
        db.query(Scene)
        .filter(Scene.id == int(shot.scene_id), _active_scene_clause())
        .first()
    )
    return str(getattr(scene, "score_audio_url", None) or "").strip() if scene else ""


def _has_audio(path: str) -> bool:
    probe = _resolve_ffprobe_exe(_resolve_ffmpeg_exe())
    if not probe:
        return True
    completed = subprocess.run(
        [probe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(str(completed.stdout or "").strip())


def _mix_score(video_url: str, score_parts: List[Dict[str, Any]], user_id: int) -> str:
    work_dir = tempfile.mkdtemp(prefix="edit_mix_")
    try:
        video_path = _download_or_resolve_local_video(video_url, work_dir)
        beds = []
        for index, part in enumerate(score_parts):
            duration = float(part.get("duration") or 0)
            if duration <= 0:
                continue
            piece = os.path.join(work_dir, f"bed_{index}.mp3")
            source_url = str(part.get("url") or "").strip()
            if source_url:
                from app.services.scene_score import _download_audio

                audio_path = _download_audio(source_url, work_dir)
                _run_ffmpeg([
                    _resolve_ffmpeg_exe(), "-y",
                    "-stream_loop", "-1", "-i", audio_path,
                    "-t", f"{duration:.3f}",
                    "-c:a", "libmp3lame", "-q:a", "4",
                    piece,
                ])
            else:
                _run_ffmpeg([
                    _resolve_ffmpeg_exe(), "-y",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", f"{duration:.3f}",
                    "-c:a", "libmp3lame", "-q:a", "6",
                    piece,
                ])
            beds.append(piece)
        if not beds:
            return video_url
        list_path = os.path.join(work_dir, "beds.txt")
        with open(list_path, "w", encoding="utf-8") as handle:
            for piece in beds:
                handle.write(f"file '{piece.replace(chr(92), '/')}'\n")
        bed_path = os.path.join(work_dir, "bed.mp3")
        _run_ffmpeg([
            _resolve_ffmpeg_exe(), "-y",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-c:a", "libmp3lame", "-q:a", "4",
            bed_path,
        ])
        output = os.path.join(work_dir, f"edit_{uuid.uuid4().hex}.mp4")
        if _has_audio(video_path):
            _run_ffmpeg([
                _resolve_ffmpeg_exe(), "-y",
                "-i", video_path, "-i", bed_path,
                "-filter_complex", "[1:a]volume=0.35[sc];[0:a][sc]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-shortest",
                output,
            ])
        else:
            _run_ffmpeg([
                _resolve_ffmpeg_exe(), "-y",
                "-i", video_path, "-i", bed_path,
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-shortest",
                output,
            ])
        return _upload_processed_video(output, os.path.basename(output), user_id=user_id)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _even_dimension(value: int) -> int:
    size = max(2, int(value or 2))
    return size if size % 2 == 0 else size - 1


def _probe_video_size(path: str) -> tuple:
    probe = _resolve_ffprobe_exe(_resolve_ffmpeg_exe())
    if not probe:
        return 1280, 720
    completed = subprocess.run(
        [
            probe, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    parts = str(completed.stdout or "").strip().split(",")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return _even_dimension(int(parts[0])), _even_dimension(int(parts[1]))
    return 1280, 720


def _concat_videos(urls: List[str], user_id: int) -> str:
    """Join shot videos without the short-montage duration cap."""
    clean = [str(url or "").strip() for url in urls if str(url or "").strip()]
    if len(clean) == 1:
        return clean[0]
    work_dir = tempfile.mkdtemp(prefix="edit_concat_")
    try:
        local_paths = [_download_or_resolve_local_video(url, work_dir) for url in clean]
        width, height = _probe_video_size(local_paths[0])
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
        )
        normalized = []
        for index, path in enumerate(local_paths):
            dest = os.path.join(work_dir, f"norm_{index:04d}.mp4")
            if _has_audio(path):
                _run_ffmpeg([
                    _resolve_ffmpeg_exe(), "-y", "-i", path,
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2",
                    "-movflags", "+faststart",
                    dest,
                ])
            else:
                _run_ffmpeg([
                    _resolve_ffmpeg_exe(), "-y",
                    "-i", path,
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-vf", vf,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2",
                    "-shortest",
                    "-movflags", "+faststart",
                    dest,
                ])
            normalized.append(dest)
        list_path = os.path.join(work_dir, "concat.txt")
        with open(list_path, "w", encoding="utf-8") as handle:
            for piece in normalized:
                handle.write(f"file '{os.path.basename(piece)}'\n")
        output = os.path.join(work_dir, f"edit_{uuid.uuid4().hex}.mp4")
        _run_ffmpeg([
            _resolve_ffmpeg_exe(), "-y",
            "-f", "concat", "-safe", "0", "-i", "concat.txt",
            "-c", "copy",
            "-movflags", "+faststart",
            output,
        ], cwd=work_dir)
        return _upload_processed_video(output, os.path.basename(output), user_id=user_id)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def merge_episode_cut(
    db: Session,
    *,
    episode: Episode,
    project_id: int,
    shot_ids: Sequence[int],
    user: User,
    with_score: bool = False,
) -> Dict[str, Any]:
    shots = _episode_shots(db, int(episode.id), shot_ids)
    if len(shots) < 1:
        raise HTTPException(status_code=400, detail="没有可合并的分镜")
    if len(shots) > _MAX_MERGE:
        raise HTTPException(status_code=400, detail=f"一次最多合并 {_MAX_MERGE} 镜")
    items = []
    missing = []
    for shot in shots:
        url = str(shot.video_url or "").strip()
        if not url:
            missing.append(str(shot.shot_id or shot.id))
            continue
        items.append({"url": url, "speed": 1.0, "trim_start": 0.0, "trim_end": 0.0})
    if len(items) < 1:
        raise HTTPException(status_code=400, detail="所选分镜都还没有成片")
    try:
        merged = _concat_videos([item["url"] for item in items], int(user.id or 0))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        detail = str(exc)
        status = 429 if "busy" in detail.lower() else 500
        raise HTTPException(status_code=status, detail=detail)
    notice = ""
    score_mixed = False
    if missing:
        notice = f"这些镜没有成片，未进入成片：{'、'.join(missing)}"
    if with_score:
        parts = []
        for shot in shots:
            if not str(shot.video_url or "").strip():
                continue
            parts.append({
                "url": _score_url_for_shot(db, shot),
                "duration": _shot_duration(shot),
            })
        if any(part.get("url") for part in parts):
            try:
                merged = _mix_score(merged, parts, int(user.id or 0))
                score_mixed = True
            except Exception as exc:
                logger.warning("edit score mix failed episode=%s: %s", episode.id, exc)
                notice = (notice + " " if notice else "") + f"成片已合并，配乐没有铺上：{exc}"
        else:
            notice = (notice + " " if notice else "") + "所选场次还没有配乐，成片只合并了画面"
    return {"url": merged, "score_mixed": score_mixed, "notice": notice.strip()}
