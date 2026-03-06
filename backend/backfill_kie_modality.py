"""Backfill modality column for all KIE models in system_api_settings."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

# model -> modality mapping
MODALITY_MAP = {
    # Image — text-to-image
    "seedream/4.5-text-to-image": "text-to-image",
    "google/imagen4-fast": "text-to-image",
    "google/imagen4-ultra": "text-to-image",
    "google/imagen4": "text-to-image",
    "google/nano-banana": "text-to-image",
    "grok-imagine/text-to-image": "text-to-image",
    "qwen/text-to-image": "text-to-image",
    "flux-2/pro-text-to-image": "text-to-image",
    "flux-2/flex-text-to-image": "text-to-image",
    "gpt-image/1.5-text-to-image": "text-to-image",
    "ideogram/character": "text-to-image",

    # Image — image-to-image
    "seedream/4.5-edit": "image-to-image",
    "google/nano-banana-edit": "image-to-image",
    "grok-imagine/image-to-image": "image-to-image",
    "grok-imagine/upscale": "image-to-image",
    "qwen/image-to-image": "image-to-image",
    "qwen/image-edit": "image-to-image",
    "flux-2/pro-image-to-image": "image-to-image",
    "flux-2/flex-image-to-image": "image-to-image",
    "gpt-image/1.5-image-to-image": "image-to-image",
    "topaz/image-upscale": "image-to-image",
    "recraft/remove-background": "image-to-image",
    "recraft/crisp-upscale": "image-to-image",
    "ideogram/v3-reframe": "image-to-image",
    "ideogram/character-edit": "image-to-image",
    "ideogram/character-remix": "image-to-image",

    # Image — multi-modal
    "gpt4o-image": "text-to-image,image-to-image",
    "flux/kontext": "text-to-image,image-to-image",

    # Video — text-to-video
    "kling-2.6/text-to-video": "text-to-video",
    "kling/v2-5-turbo-text-to-video-pro": "text-to-video",
    "kling/v2-1-master-text-to-video": "text-to-video",
    "bytedance/v1-pro-text-to-video": "text-to-video",
    "bytedance/v1-lite-text-to-video": "text-to-video",
    "hailuo/02-text-to-video-pro": "text-to-video",
    "hailuo/02-text-to-video-standard": "text-to-video",
    "wan/2-6-text-to-video": "text-to-video",
    "wan/2-2-a14b-text-to-video-turbo": "text-to-video",
    "sora-2-text-to-video": "text-to-video",
    "sora-2-pro-text-to-video": "text-to-video",
    "grok-imagine/text-to-video": "text-to-video",
    "runwayml/gen3a-turbo": "text-to-video",

    # Video — image-to-video
    "kling-2.6/image-to-video": "image-to-video",
    "kling-2.6/motion-control": "image-to-video",
    "kling/v2-5-turbo-image-to-video-pro": "image-to-video",
    "kling/v2-1-master-image-to-video": "image-to-video",
    "bytedance/v1-pro-image-to-video": "image-to-video",
    "bytedance/v1-pro-fast-image-to-video": "image-to-video",
    "bytedance/v1-lite-image-to-video": "image-to-video",
    "hailuo/02-image-to-video-pro": "image-to-video",
    "hailuo/02-image-to-video-standard": "image-to-video",
    "hailuo/2-3-image-to-video-pro": "image-to-video",
    "hailuo/2-3-image-to-video-standard": "image-to-video",
    "wan/2-6-image-to-video": "image-to-video",
    "wan/2-2-a14b-image-to-video-turbo": "image-to-video",
    "wan/2-2-animate-move": "image-to-video",
    "wan/2-2-animate-replace": "image-to-video",
    "wan/2-6-flash-image-to-video": "image-to-video",
    "sora-2-image-to-video": "image-to-video",
    "sora-2-pro-image-to-video": "image-to-video",
    "grok-imagine/image-to-video": "image-to-video",
    "runwayml/gen3a-turbo-image-to-video": "image-to-video",

    # Video — video-to-video
    "wan/2-6-video-to-video": "video-to-video",
    "wan/2-6-flash-video-to-video": "video-to-video",
    "sora-watermark-remover": "video-to-video",
    "topaz/video-upscale": "video-to-video",

    # Video — multi-modal
    "kling-3.0/video": "text-to-video,image-to-video",
    "kling/v2-1-pro": "text-to-video,image-to-video",
    "kling/v2-1-standard": "text-to-video,image-to-video",
    "sora-2-pro-storyboard": "text-to-video,image-to-video",
    "sora-2-characters": "text-to-video,image-to-video",
    "sora-2-characters-pro": "text-to-video,image-to-video",

    # Video — special
    "wan/2-2-a14b-speech-to-video-turbo": "speech-to-video",
    "infinitalk/from-audio": "audio-to-video",

    # Tools — audio
    "elevenlabs/text-to-dialogue-v3": "text-to-audio",
    "elevenlabs/text-to-speech-turbo-2-5": "text-to-audio",
    "elevenlabs/text-to-speech-multilingual-v2": "text-to-audio",
    "elevenlabs/speech-to-text": "audio-to-text",
    "elevenlabs/sound-effect-v2": "text-to-audio",
    "elevenlabs/audio-isolation": "audio-to-audio",

    # Audio
    "suno": "text-to-audio",

    # LLM — NULL (no restriction)
    # gemini-2.5-flash, gemini-2.5-pro, gemini-3-pro, gpt-5-2,
    # claude-sonnet-4-5, claude-opus-4-5 => keep NULL
}

def main():
    db = SessionLocal()
    try:
        rows = db.query(SystemAPISetting).filter(
            SystemAPISetting.provider == "kie"
        ).all()
        updated = 0
        skipped = 0
        for row in rows:
            model_key = (row.model or "").strip()
            if model_key in MODALITY_MAP:
                new_val = MODALITY_MAP[model_key]
                if row.modality != new_val:
                    row.modality = new_val
                    updated += 1
                else:
                    skipped += 1
            else:
                skipped += 1
        db.commit()
        print(f"Done. Updated: {updated}, Skipped/LLM: {skipped}, Total KIE rows: {len(rows)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
