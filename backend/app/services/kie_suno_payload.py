# -*- coding: utf-8 -*-
"""KIE Suno music task body for POST /api/v1/jobs/createTask."""
from __future__ import annotations

from typing import Any, Dict, Optional

SUNO_JOB_MODEL = "ai-music-api/generate"
SUNO_SUBMIT_PATH = "/api/v1/jobs/createTask"
SUNO_QUERY_PATH = "/api/v1/jobs/recordInfo"
_LIVE_MODELS = {"V6", "V6_MINI", "V6_WILD"}


def _conf_value(tool_conf: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key and key in tool_conf and tool_conf.get(key) not in (None, ""):
            return tool_conf.get(key)
    return default


def _conf_bool(tool_conf: Dict[str, Any], *keys: str, default: bool = False) -> bool:
    raw = _conf_value(tool_conf, *keys, default=default)
    if isinstance(raw, bool):
        return raw
    text = str(raw or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _conf_float(tool_conf: Dict[str, Any], *keys: str) -> Optional[float]:
    raw = _conf_value(tool_conf, *keys, default=None)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except Exception:
        return None


def resolve_suno_model(raw: Any) -> str:
    version = str(raw or "").strip().upper().replace(".", "_").replace("-", "_")
    if version in _LIVE_MODELS:
        return version
    return "V6"


def clamp_suno_duration(raw: Any) -> Optional[int]:
    if raw in (None, ""):
        return None
    try:
        seconds = int(round(float(raw)))
    except Exception:
        return None
    if seconds <= 0:
        return None
    return max(10, min(360, seconds))


def build_suno_generate_body(
    *,
    prompt: str,
    tool_conf: Dict[str, Any],
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Music generation. `prompt` is a listening brief, not lyrics."""
    conf = tool_conf if isinstance(tool_conf, dict) else {}
    version = resolve_suno_model(_conf_value(conf, "suno_model", "sunoModel", "model_version", "modelVersion", default=""))
    custom_mode = _conf_bool(conf, "customMode", "custom_mode", default=True)
    instrumental = _conf_bool(conf, "instrumental", default=True)
    brief = str(prompt or "").strip()
    style_val = str(_conf_value(conf, "suno_style", "music_style", "style", default="") or "").strip()
    if len(brief) > len(style_val):
        style_val = brief
    title_val = str(
        _conf_value(conf, "suno_title", "music_title", "title", default="AI Generated Track")
        or "AI Generated Track"
    ).strip()
    music: Dict[str, Any] = {
        "custom_mode": custom_mode,
        "instrumental": instrumental,
        "model": version,
        "style": (style_val or "Classical")[:1000],
        "title": (title_val or "AI Generated Track")[:80],
    }
    lyrics = str(_conf_value(conf, "suno_lyrics", "lyrics", default="") or "").strip()
    if lyrics and not instrumental:
        music["lyrics"] = lyrics[:5000]
    negative_tags = str(_conf_value(conf, "negativeTags", "negative_tags", default="") or "").strip()
    if negative_tags:
        music["negative_tags"] = negative_tags
    vocal_gender = str(_conf_value(conf, "vocalGender", "vocal_gender", default="") or "").strip().lower()
    if vocal_gender in {"m", "f", "male", "female"} and custom_mode and not instrumental:
        music["vocal_gender"] = "m" if vocal_gender in {"m", "male"} else "f"
    for target_key, source_keys in (
        ("style_weight", ("styleWeight", "style_weight")),
        ("weirdness_constraint", ("weirdnessConstraint", "weirdness_constraint")),
        ("audio_weight", ("audioWeight", "audio_weight")),
    ):
        numeric_val = _conf_float(conf, *source_keys)
        if numeric_val is None or not custom_mode:
            continue
        if target_key == "audio_weight" and instrumental:
            continue
        music[target_key] = max(0.0, min(1.0, float(numeric_val)))
    persona_id = str(_conf_value(conf, "personaId", "persona_id", default="") or "").strip()
    if persona_id:
        music["persona_id"] = persona_id
    persona_model = str(_conf_value(conf, "personaModel", "persona_model", default="") or "").strip()
    if persona_model:
        music["persona_model"] = persona_model
    duration = clamp_suno_duration(_conf_value(conf, "suno_duration", "sunoDuration", "music_duration", default=None))
    if duration is not None and custom_mode:
        music["duration"] = duration
    body: Dict[str, Any] = {
        "model": SUNO_JOB_MODEL,
        "input": music,
    }
    callback = str(callback_url or "").strip()
    if callback and callback != "-1":
        body["callBackUrl"] = callback
    return body
