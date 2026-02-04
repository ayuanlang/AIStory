import os
import uuid
import logging
from moviepy import VideoFileClip, concatenate_videoclips
from app.core.config import settings

logger = logging.getLogger(__name__)

async def create_montage(project_id: int, items: list) -> str:
    """
    Stitches clips together.
    items: List of dicts with keys: url, speed, trim_start, trim_end
    Returns: URL of generated video
    """
    clips = []
    
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
                
            file_path = os.path.join(settings.UPLOAD_DIR, filename)
            
            if not os.path.exists(file_path):
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

                # Resize to common size? Or assume same size?
                # moviepy concatenate might fail if sizes differ.
                # Let's resize everything to 720p or just the size of the first clip?
                # Safe bet: Resize to first clip's size if they differ.
                if clips:
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
        final_clip.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac",
            fps=24, 
            threads=4,
            logger=None # Suppress TQDM output to stdout
        )
        
        # Close all clips
        final_clip.close()
        for clip in clips:
            clip.close()
            
        # Return URL
        return f"/uploads/{output_filename}"

    except Exception as e:
        logger.error(f"Montage generation failed: {e}")
        # Clean up
        for clip in clips:
            try: clip.close() 
            except: pass
        raise e
