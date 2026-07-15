import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from moviepy import VideoFileClip, concatenate_videoclips

from app.core.config import settings
from app.core.mp4_faststart import optimize_mp4_faststart
from app.services.oss_storage_service import oss_storage_service

logger = logging.getLogger(__name__)

_MONTAGE_FFMPEG_THREADS = max(1, min(2, int(os.getenv("MONTAGE_FFMPEG_THREADS", "1") or 1)))
_MONTAGE_MAX_CONCURRENT = max(1, min(2, int(os.getenv("MONTAGE_MAX_CONCURRENT", "1") or 1)))
_MONTAGE_ACQUIRE_TIMEOUT_SECONDS = max(5, int(os.getenv("MONTAGE_ACQUIRE_TIMEOUT_SECONDS", "15") or 15))
_MONTAGE_MAX_ITEMS = max(1, int(os.getenv("MONTAGE_MAX_ITEMS", "24") or 24))
_MONTAGE_MAX_TOTAL_SECONDS = max(30.0, float(os.getenv("MONTAGE_MAX_TOTAL_SECONDS", "240") or 240.0))
_MONTAGE_RENDER_SLOTS = threading.BoundedSemaphore(_MONTAGE_MAX_CONCURRENT)

_CLEANUP_MAX_CONCURRENT = max(1, min(2, int(os.getenv("VIDEO_CLEANUP_MAX_CONCURRENT", "1") or 1)))
_CLEANUP_ACQUIRE_TIMEOUT_SECONDS = max(5, int(os.getenv("VIDEO_CLEANUP_ACQUIRE_TIMEOUT_SECONDS", "30") or 30))
_CLEANUP_RENDER_SLOTS = threading.BoundedSemaphore(_CLEANUP_MAX_CONCURRENT)
_CLEANUP_DOWNLOAD_TIMEOUT_SECONDS = max(30, int(os.getenv("VIDEO_CLEANUP_DOWNLOAD_TIMEOUT_SECONDS", "120") or 120))
# Bottom band used for burned-in subtitle delogo (relative to frame height).
_SUBTITLE_DELOGO_TOP_RATIO = float(os.getenv("VIDEO_CLEANUP_SUBTITLE_TOP_RATIO", "0.82") or 0.82)
_SUBTITLE_DELOGO_SIDE_RATIO = float(os.getenv("VIDEO_CLEANUP_SUBTITLE_SIDE_RATIO", "0.05") or 0.05)


def _resolve_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        exe = str(imageio_ffmpeg.get_ffmpeg_exe() or "").strip()
        if exe and os.path.exists(exe):
            return exe
    except Exception as exc:
        logger.warning("imageio-ffmpeg resolve failed: %s", exc)
    for candidate in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError("ffmpeg executable not found")


def _resolve_ffprobe_exe(ffmpeg_exe: Optional[str] = None) -> Optional[str]:
    try:
        import imageio_ffmpeg

        probe = str(getattr(imageio_ffmpeg, "get_ffprobe_exe", lambda: "")() or "").strip()
        if probe and os.path.exists(probe):
            return probe
    except Exception:
        pass
    for candidate in ("ffprobe", "ffprobe.exe"):
        found = shutil.which(candidate)
        if found:
            return found
    ffmpeg_path = str(ffmpeg_exe or "").strip()
    if ffmpeg_path:
        base = os.path.dirname(ffmpeg_path)
        name = os.path.basename(ffmpeg_path).lower()
        probe_name = "ffprobe.exe" if name.endswith(".exe") else "ffprobe"
        candidate = os.path.join(base, probe_name)
        if os.path.exists(candidate):
            return candidate
    return None


def _run_ffmpeg(cmd: list, timeout_seconds: int = 600) -> None:
    logger.info("ffmpeg cmd: %s", " ".join(str(part) for part in cmd))
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"ffmpeg failed (code={completed.returncode}): {stderr[-2000:]}")


def _probe_video_size(file_path: str, ffmpeg_exe: str) -> Tuple[int, int]:
    probe_exe = _resolve_ffprobe_exe(ffmpeg_exe)
    if probe_exe:
        try:
            completed = subprocess.run(
                [
                    probe_exe,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "json",
                    file_path,
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if completed.returncode == 0:
                payload = json.loads(completed.stdout or "{}")
                streams = payload.get("streams") if isinstance(payload, dict) else None
                if isinstance(streams, list) and streams:
                    width = int(streams[0].get("width") or 0)
                    height = int(streams[0].get("height") or 0)
                    if width > 0 and height > 0:
                        return width, height
        except Exception as exc:
            logger.warning("ffprobe size probe failed path=%s err=%s", file_path, exc)

    clip = None
    try:
        clip = VideoFileClip(file_path)
        width, height = clip.size
        return int(width), int(height)
    finally:
        if clip is not None:
            try:
                clip.close()
            except Exception:
                pass


def _download_or_resolve_local_video(video_url: str, work_dir: str) -> str:
    raw = str(video_url or "").strip()
    if not raw:
        raise ValueError("video_url is required")

    parsed = urlparse(raw)
    path_part = parsed.path or raw

    if "/uploads/" in path_part:
        relative = path_part.split("/uploads/", 1)[1]
        local_path = os.path.join(settings.UPLOAD_DIR, relative.replace("/", os.sep))
        if os.path.exists(local_path):
            return local_path

    if parsed.scheme in {"http", "https"}:
        ext = os.path.splitext(path_part)[1] or ".mp4"
        if len(ext) > 8:
            ext = ".mp4"
        local_path = os.path.join(work_dir, f"source_{uuid.uuid4().hex}{ext}")
        logger.info("Downloading video for cleanup: %s -> %s", raw, local_path)
        with requests.get(raw, stream=True, timeout=_CLEANUP_DOWNLOAD_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            with open(local_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        handle.write(chunk)
        return local_path

    candidate = raw if os.path.isabs(raw) else os.path.join(settings.UPLOAD_DIR, raw.lstrip("/\\"))
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(f"Video file not found for cleanup: {raw}")


def _upload_processed_video(output_path: str, output_filename: str, user_id: int = 0) -> str:
    try:
        optimize_mp4_faststart(output_path)
    except Exception as faststart_error:
        logger.warning("MP4 faststart skipped for cleanup %s: %s", output_filename, faststart_error)

    try:
        uploaded = oss_storage_service.upload_file(
            output_path,
            user_id=user_id,
            filename=output_filename,
            content_type="video/mp4",
            category="video_cleanup",
        )
        oss_url = str((uploaded or {}).get("url") or "").strip()
        if oss_url:
            try:
                os.remove(output_path)
            except Exception as remove_err:
                logger.warning("Failed to remove local cleanup file %s: %s", output_path, remove_err)
            return oss_url
    except Exception as oss_err:
        logger.error("Failed to upload cleanup video to OSS: %s", oss_err)

    relative_name = output_filename
    if user_id:
        relative_name = f"{user_id}/{output_filename}"
        dest_dir = os.path.join(settings.UPLOAD_DIR, str(user_id))
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, output_filename)
        if os.path.abspath(output_path) != os.path.abspath(dest_path):
            shutil.move(output_path, dest_path)
    return f"/uploads/{relative_name}"


def process_video_cleanup_local(
    video_url: str,
    *,
    remove_subtitle: bool = False,
    remove_bgm: bool = False,
    user_id: int = 0,
) -> Dict[str, Any]:
    """
    Local ffmpeg cleanup for a shot video.
    - remove_bgm: drop audio track
    - remove_subtitle: strip soft subtitle streams and delogo the bottom burned-in caption band
    """
    if not remove_subtitle and not remove_bgm:
        raise ValueError("At least one of remove_subtitle / remove_bgm must be enabled")

    acquired = _CLEANUP_RENDER_SLOTS.acquire(timeout=_CLEANUP_ACQUIRE_TIMEOUT_SECONDS)
    if not acquired:
        raise RuntimeError("Video cleanup renderer is busy, please retry shortly")

    work_dir = tempfile.mkdtemp(prefix="video_cleanup_")
    output_path = ""
    try:
        source_path = _download_or_resolve_local_video(video_url, work_dir)
        ffmpeg_exe = _resolve_ffmpeg_exe()
        output_filename = f"cleanup_{uuid.uuid4().hex}.mp4"
        output_dir = settings.UPLOAD_DIR
        if user_id:
            output_dir = os.path.join(settings.UPLOAD_DIR, str(user_id))
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)

        cmd = [ffmpeg_exe, "-y", "-i", source_path]

        if remove_subtitle:
            width, height = _probe_video_size(source_path, ffmpeg_exe)
            top_ratio = min(0.95, max(0.5, _SUBTITLE_DELOGO_TOP_RATIO))
            side_ratio = min(0.25, max(0.0, _SUBTITLE_DELOGO_SIDE_RATIO))
            x = max(0, int(width * side_ratio))
            y = max(0, int(height * top_ratio))
            w = max(8, int(width - (2 * x)))
            h = max(8, int(height - y))
            # Keep delogo box inside frame with a small margin.
            if x + w >= width:
                w = max(8, width - x - 2)
            if y + h >= height:
                h = max(8, height - y - 2)
            vf = f"delogo=x={x}:y={y}:w={w}:h={h}:show=0"
            cmd.extend([
                "-map", "0:v:0",
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "18",
            ])
            if remove_bgm:
                cmd.append("-an")
            else:
                cmd.extend(["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"])
            cmd.extend(["-sn", "-movflags", "+faststart", output_path])
        elif remove_bgm:
            # Fast path: copy video bitstream and drop audio / soft subs.
            cmd.extend(["-c:v", "copy", "-an", "-sn", "-movflags", "+faststart", output_path])
        else:
            raise ValueError("Unsupported cleanup combination")

        _run_ffmpeg(cmd, timeout_seconds=900)
        if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
            raise RuntimeError("Cleanup produced an empty video file")

        result_url = _upload_processed_video(output_path, output_filename, user_id=user_id)
        return {
            "url": result_url,
            "remove_subtitle": bool(remove_subtitle),
            "remove_bgm": bool(remove_bgm),
        }
    finally:
        _CLEANUP_RENDER_SLOTS.release()
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass
        if output_path and os.path.exists(output_path):
            # Kept only when OSS upload failed and file was moved under uploads/.
            pass


def create_montage(project_id: int, items: list, user_id: int = 0) -> str:
    """
    Stitches clips together.
    items: List of dicts with keys: url, speed, trim_start, trim_end
    Returns: URL of generated video
    """
    if not isinstance(items, list) or not items:
        raise ValueError("No montage clips submitted")
    if len(items) > _MONTAGE_MAX_ITEMS:
        raise ValueError(f"Too many montage clips (max={_MONTAGE_MAX_ITEMS})")

    acquired = _MONTAGE_RENDER_SLOTS.acquire(timeout=_MONTAGE_ACQUIRE_TIMEOUT_SECONDS)
    if not acquired:
        raise RuntimeError("Montage renderer is busy, please retry shortly")

    clips = []
    final_clip = None
    total_duration_seconds = 0.0
    
    try:
        for item in items:
            url = item.get("url")
            if not url: continue

            # Extract filename from URL
            # URL is likely http://.../uploads/filename.mp4 or /uploads/filename.mp4
            if "/uploads/" in url:
                filename = url.split("/uploads/")[1]
            else:
                # Assuming simple filename if not url
                filename = os.path.basename(url)
                
            # Remove any query parameters from filename
            from urllib.parse import urlparse
            filename = urlparse(filename).path
                
            file_path = os.path.join(settings.UPLOAD_DIR, filename)

            if not os.path.exists(file_path):
                if url.startswith("http://") or url.startswith("https://"):
                    try:
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        logger.info(f"Downloading remote video: {url} to {file_path}")
                        with requests.get(url, stream=True, timeout=60) as r:
                            r.raise_for_status()
                            with open(file_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    f.write(chunk)
                    except Exception as e:
                        logger.error(f"Failed to download remote video {url}: {e}")
                        continue
                else:
                    logger.warning(f"Video file not found: {file_path}")
                    continue
                
            try:
                clip = VideoFileClip(file_path)
                
                # Apply Trim
                trim_start = float(item.get("trim_start", 0))
                trim_end = float(item.get("trim_end", 0))
                
                # Check bounds
                if trim_start < 0: trim_start = 0
                if trim_end < 0: trim_end = 0
                
                duration = clip.duration
                end_time = duration - trim_end
                
                if trim_start >= end_time:
                    logger.warning(f"Clip trimmed to nothing: {filename}. Duration: {duration}, Start: {trim_start}, End: {end_time}")
                    # If trim invalid, just use whole clip or skip? Skip for now.
                    continue
                
                # Robustness fix: Shave off a tiny bit (0.05s) from end if using full duration
                # to prevent "Accessing time t=duration" errors due to metadata/stream mismatch.
                if end_time > duration - 0.05:
                    end_time = max(trim_start + 0.1, duration - 0.05)

                # Always subclip to enforce safe boundaries
                clip = clip.subclipped(trim_start, end_time)
                
                # Apply Speed
                speed = float(item.get("speed", 1.0))
                if speed != 1.0 and speed > 0:
                    clip = clip.with_speed_scaled(speed)

                effective_duration = max(0.0, float(end_time - trim_start)) / max(speed, 0.001)
                total_duration_seconds += effective_duration
                if total_duration_seconds > _MONTAGE_MAX_TOTAL_SECONDS:
                    raise ValueError(
                        f"Montage total duration exceeded limit ({_MONTAGE_MAX_TOTAL_SECONDS:.0f}s)"
                    )

                # Resize to common size? Or assume same size?
                # moviepy concatenate might fail if sizes differ.
                # Let's resize everything to 720p or just the size of the first clip?
                # Safe bet: Resize to first clip's size if they differ.
                if not clips:
                    first_w, first_h = clip.size
                else:
                    first_w, first_h = clips[0].size

                if clip.size != (first_w, first_h):
                    clip = clip.resized(new_size=(first_w, first_h))
                    
                clips.append(clip)
            except Exception as e:
                logger.error(f"Error processing clip {filename}: {e}")
                continue

        if not clips:
            raise ValueError("No valid clips found to stitch.")

        final_clip = concatenate_videoclips(clips, method="compose")
        
        output_filename = f"montage_{project_id}_{uuid.uuid4().hex}.mp4"
        output_dir = settings.UPLOAD_DIR
        if user_id:
            output_dir = os.path.join(settings.UPLOAD_DIR, str(user_id))
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
        
        # Write file
        write_kwargs = {
            "codec": "libx264",
            "audio_codec": "aac",
            "fps": 24,
            "threads": _MONTAGE_FFMPEG_THREADS,
            "logger": None # Suppress TQDM output to stdout
        }
            
        final_clip.write_videofile(
            output_path, 
            **write_kwargs
        )

        try:
            optimize_mp4_faststart(output_path)
        except Exception as faststart_error:
            logger.warning(f"MP4 faststart optimization skipped for montage {output_filename}: {faststart_error}")
        
        # Close all clips
        final_clip.close()
        for clip in clips:
            clip.close()
            
        # Upload to OSS
        try:
            uploaded = oss_storage_service.upload_file(
                output_path,
                user_id=user_id,
                filename=output_filename,
                content_type="video/mp4",
                category="montage"
            )
            oss_url = str((uploaded or {}).get("url") or "").strip()
            if oss_url:
                try:
                    os.remove(output_path)
                    logger.info(
                        "Montage uploaded to OSS | user_id=%s key=%s url=%s",
                        user_id,
                        (uploaded or {}).get("key"),
                        oss_url,
                    )
                except Exception as ex:
                    logger.warning(f"Failed to remove local montage file {output_path}: {ex}")
                return oss_url
        except Exception as oss_err:
            logger.error(f"Failed to upload montage to OSS: {oss_err}")

        relative_name = output_filename
        if user_id:
            relative_name = f"{user_id}/{output_filename}"
        return f"/uploads/{relative_name}"

    except Exception as e:
        logger.error(f"Montage generation failed: {e}")
        # Clean up
        if final_clip is not None:
            try:
                final_clip.close()
            except Exception:
                pass
        for clip in clips:
            try: clip.close() 
            except: pass
        raise e
    finally:
        _MONTAGE_RENDER_SLOTS.release()
