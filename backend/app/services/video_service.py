import requests
import os
import uuid
import logging
import threading
from moviepy import VideoFileClip, concatenate_videoclips
from app.core.config import settings
from app.core.mp4_faststart import optimize_mp4_faststart

logger = logging.getLogger(__name__)

_MONTAGE_FFMPEG_THREADS = max(1, min(2, int(os.getenv("MONTAGE_FFMPEG_THREADS", "1") or 1)))
_MONTAGE_MAX_CONCURRENT = max(1, min(2, int(os.getenv("MONTAGE_MAX_CONCURRENT", "1") or 1)))
_MONTAGE_ACQUIRE_TIMEOUT_SECONDS = max(5, int(os.getenv("MONTAGE_ACQUIRE_TIMEOUT_SECONDS", "15") or 15))
_MONTAGE_MAX_ITEMS = max(1, int(os.getenv("MONTAGE_MAX_ITEMS", "24") or 24))
_MONTAGE_MAX_TOTAL_SECONDS = max(30.0, float(os.getenv("MONTAGE_MAX_TOTAL_SECONDS", "240") or 240.0))
_MONTAGE_RENDER_SLOTS = threading.BoundedSemaphore(_MONTAGE_MAX_CONCURRENT)

import requests
def create_montage(project_id: int, items: list) -> str:
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
        output_path = os.path.join(settings.UPLOAD_DIR, output_filename)
        
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
            
        # Return URL
        return f"/uploads/{output_filename}"

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
