# -*- coding: utf-8 -*-
"""Voice / Suno / KIE TTS planning helpers."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.generation import VoiceGenerationRequest
from app.services.agent_service import agent_service
from app.services.effective_api_setting import _to_bool
from app.services.llm_service import llm_service
from app.services.generation_runtime.project_generation_context import _normalize_seed_value
from app.services.prompt_resolve import _resolve_prompt_text

logger = logging.getLogger("api_logger")


def _is_suno_voice_runtime(resolved_model: Optional[str], provider_options: Optional[Dict[str, Any]] = None) -> bool:
    model_text = str(resolved_model or "").strip().lower()
    if "suno" in model_text:
        return True
    opts = provider_options if isinstance(provider_options, dict) else {}
    for key in ("customMode", "custom_mode", "suno_model", "sunoModel", "suno_style", "sunoStyle", "suno_title", "sunoTitle"):
        if opts.get(key) not in (None, ""):
            return True
    return False


def _build_voice_suno_provider_options(req: VoiceGenerationRequest) -> Dict[str, Any]:
    opts: Dict[str, Any] = {}
    raw_provider_options = getattr(req, "provider_options", None)
    if isinstance(raw_provider_options, dict):
        opts.update(raw_provider_options)

    def _set_if_present(target_key: str, *source_keys: str) -> None:
        for source_key in source_keys:
            value = getattr(req, source_key, None)
            if value not in (None, ""):
                opts[target_key] = value
                return

    _set_if_present("customMode", "customMode", "custom_mode")
    _set_if_present("instrumental", "instrumental")
    _set_if_present("suno_model", "suno_model", "sunoModel")
    _set_if_present("suno_style", "suno_style", "sunoStyle")
    _set_if_present("suno_title", "suno_title", "sunoTitle")
    _set_if_present("negativeTags", "negativeTags", "negative_tags")
    _set_if_present("vocalGender", "vocalGender", "vocal_gender")
    _set_if_present("styleWeight", "styleWeight", "style_weight")
    _set_if_present("weirdnessConstraint", "weirdnessConstraint", "weirdness_constraint")
    _set_if_present("audioWeight", "audioWeight", "audio_weight")
    _set_if_present("personaId", "personaId", "persona_id")
    _set_if_present("personaModel", "personaModel", "persona_model")

    entity_id = _normalize_seed_value(getattr(req, "entity_id", None))
    if entity_id:
        opts["entity_id"] = int(entity_id)
        opts["__entity_id"] = int(entity_id)
    return opts

def _extract_json_object_from_text(raw_text: Any) -> Dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {}

    # Prefer fenced JSON blocks when the model wraps output with reasoning text.
    fenced_matches = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
    for block in fenced_matches:
        candidate = str(block or "").strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    clean = text
    if clean.startswith("```"):
        lines = clean.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean = "\n".join(lines).strip()

    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end > start:
        candidate = clean[start:end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _build_voice_tts_planner_prompts(video_prompt: str) -> Tuple[str, str, Dict[str, Any]]:
    prompt_text = str(video_prompt or "").strip()
    supported_voices_hint = (
        "Rachel, Aria, Roger, Sarah, Laura, Charlie, George, Callum, River, Liam, Charlotte, Alice, "
        "Matilda, Will, Jessica, Eric, Chris, Brian, Daniel, Lily, Bill"
    )

    default_system_prompt = (
        "You are a TTS planning engine with two strict phases: "
        "(1) extract spoken dialogue from the video prompt, "
        "(2) infer voice parameters from character traits and scene intent. "
        "Output ONLY one JSON object. Do not include markdown, comments, or extra text."
    )

    default_user_prompt = (
        "Generate TTS planning params from a video prompt.\\n"
        "Core objective: extract dialogue text first; then tune voice parameters by character traits.\\n"
        "Rules:\\n"
        "A. Dialogue extraction (highest priority):\n"
        "1) Extract ONLY explicit spoken lines (quoted lines or speaker: line).\n"
        "2) NEVER convert action/narration/camera description into speech text.\n"
        "3) Keep wording close to original spoken content; do not rewrite plot into dialogue.\n"
        "4) If no explicit spoken dialogue exists, set text to an empty string.\n"
        "B. Parameter inference (secondary):\n"
        "5) Use character context ONLY to infer voice and style-related params: voice, stability, similarity_boost, style, speed, language_code.\n"
        "6) Character traits/context MUST NOT be copied into text.\n"
        "7) If multiple characters are present, choose one coherent voice profile that best matches dominant speaker tone in extracted dialogue.\n"
        "8) Voice must be one of the supported names (or a valid official voice id).\n"
        "9) If uncertain, use conservative defaults: voice=Rachel, stability=0.5, similarity_boost=0.75, style=0, speed=1.0, timestamps=false.\n"
        "10) language_code should be ISO 639-1 (en/zh/ja/ko/es/fr/de/it/pt/ru/ar/hi etc).\n"
        "Supported voice names include:\n"
        f"{supported_voices_hint}\n"
        "Examples:\n"
        "- Input: 伊莎贝拉向后跌倒，老板冲进大楼。 -> text: \"\"\n"
        "- Input: 老板：\"滚出去！\" -> text: \"滚出去！\"\n"
        "- Input includes [Character Context] only -> text must still be \"\" unless explicit dialogue exists.\n"
        "Return JSON schema exactly:\\n"
        "{\\n"
        "  \\\"text\\\": \\\"string\\\",\\n"
        "  \\\"voice\\\": \\\"string\\\",\\n"
        "  \\\"stability\\\": \\\"number 0..1\\\",\\n"
        "  \\\"similarity_boost\\\": \\\"number 0..1\\\",\\n"
        "  \\\"style\\\": \\\"number 0..1\\\",\\n"
        "  \\\"speed\\\": \\\"number 0.7..1.2\\\",\\n"
        "  \\\"timestamps\\\": \\\"boolean\\\",\\n"
        "  \\\"previous_text\\\": \\\"string\\\",\\n"
        "  \\\"next_text\\\": \\\"string\\\",\\n"
        "  \\\"language_code\\\": \\\"ISO 639-1 string, e.g. en zh ja\\\"\\n"
        "}\\n\\n"
        f"Video prompt:\\n{prompt_text}"
    )

    template_source = "defaults"
    try:
        system_template = _resolve_prompt_text("voice_tts_planner_system.txt")
        system_prompt = str(system_template or "").strip() or default_system_prompt
        template_source = "system_file"
    except Exception as e:
        logger.warning("[GenerateVoice] failed to load voice_tts_planner_system.txt: %s", e)
        system_prompt = default_system_prompt

    try:
        user_template = _resolve_prompt_text("voice_tts_planner_user.txt")
        user_prompt = str(user_template or "").strip()
        if user_prompt:
            user_prompt = user_prompt.replace("{{SUPPORTED_VOICES_HINT}}", supported_voices_hint)
            user_prompt = user_prompt.replace("{{VIDEO_PROMPT}}", prompt_text)
            template_source = "both_files" if template_source == "system_file" else "user_file"
        if not user_prompt:
            user_prompt = default_user_prompt
    except Exception as e:
        logger.warning("[GenerateVoice] failed to load voice_tts_planner_user.txt: %s", e)
        user_prompt = default_user_prompt

    meta = {
        "template_source": template_source,
        "system_prompt_len": len(system_prompt or ""),
        "user_prompt_len": len(user_prompt or ""),
    }
    return system_prompt, user_prompt, meta


async def _plan_voice_params_with_llm(
    user_id: int,
    video_prompt: str,
    planner_prompts: Optional[Tuple[str, str]] = None,
) -> Dict[str, Any]:
    prompt_text = str(video_prompt or "").strip()
    if not prompt_text:
        return {}

    # For voice prompt planning, prefer system-default LLM category config
    # instead of user-bound provider/model routing.
    llm_config = agent_service.get_system_default_llm_config(user_id=user_id, category="LLM")
    planning_category = "LLM"

    if not llm_config or not llm_config.get("api_key"):
        llm_config = agent_service.get_active_llm_config(user_id, category="LLM")
        planning_category = "LLM"

    if not llm_config or not llm_config.get("api_key"):
        return {}

    if planner_prompts and isinstance(planner_prompts, tuple) and len(planner_prompts) == 2:
        system_prompt = str(planner_prompts[0] or "").strip()
        user_prompt = str(planner_prompts[1] or "").strip()
    else:
        system_prompt, user_prompt, _ = _build_voice_tts_planner_prompts(prompt_text)

    try:
        cfg = (llm_config or {}).get("config") if isinstance(llm_config, dict) else {}
        logger.info(
            "[GenerateVoice] planning llm config | user_id=%s source=%s setting_id=%s provider=%s model=%s",
            user_id,
            (cfg or {}).get("__selection_source") or (cfg or {}).get("__resolved_source") or "unknown",
            (cfg or {}).get("__resolved_setting_id"),
            llm_config.get("provider") if isinstance(llm_config, dict) else None,
            llm_config.get("model") if isinstance(llm_config, dict) else None,
        )
    except Exception:
        pass

    llm_resp = await llm_service.generate_content_with_fallback(
        user_prompt,
        system_prompt,
        llm_config,
        user_id=user_id,
        category=planning_category,
        modality="text",
    )
    parsed = _extract_json_object_from_text((llm_resp or {}).get("content"))
    if not parsed:
        return {}

    def _pick_text(*keys: str) -> str:
        for key in keys:
            val = parsed.get(key)
            if val is None:
                continue
            text = str(val).strip()
            if text:
                return text
        return ""

    normalized: Dict[str, Any] = {}
    text_value = _pick_text("text", "tts_text", "voice_text", "narration")
    if text_value:
        normalized["text"] = text_value

    voice_value = _pick_text("voice", "voice_id")
    if voice_value:
        normalized["voice"] = voice_value

    language_code_value = _pick_text("language_code", "language", "lang")
    if language_code_value:
        normalized["language_code"] = language_code_value

    for key in ["previous_text", "next_text"]:
        value = _pick_text(key)
        if value:
            normalized[key] = value

    for float_key in ["stability", "similarity_boost", "style", "speed"]:
        raw = parsed.get(float_key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            normalized[float_key] = float(raw)
        except Exception:
            pass

    timestamps_raw = parsed.get("timestamps")
    if timestamps_raw is not None:
        normalized["timestamps"] = _to_bool(timestamps_raw)

    return normalized


_KIE_TTS_DEFAULT_VOICE = "Rachel"
_KIE_TTS_ALLOWED_VOICES = {
    "Rachel", "Aria", "Roger", "Sarah", "Laura", "Charlie", "George", "Callum", "River", "Liam",
    "Charlotte", "Alice", "Matilda", "Will", "Jessica", "Eric", "Chris", "Brian", "Daniel", "Lily", "Bill",
}


def _normalize_kie_voice_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    # Accept official custom voice ids (alnum) used by KIE/ElevenLabs voice catalogs.
    if re.fullmatch(r"[A-Za-z0-9]{18,32}", raw):
        return raw

    candidates = [
        raw,
        raw.split(" - ")[0].strip(),
        raw.split("|")[0].strip(),
        raw.split("（")[0].strip(),
        raw.split("(")[0].strip(),
    ]
    for candidate in candidates:
        if candidate in _KIE_TTS_ALLOWED_VOICES:
            return candidate

    return ""


def _normalize_language_code(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    # Keep main ISO 639-1 code to avoid provider errors on unsupported variants.
    base = raw.split("-")[0].strip()
    if re.fullmatch(r"[a-z]{2}", base):
        return base
    return ""


def _clamp_float(value: Any, min_val: float, max_val: float, default: float) -> float:
    try:
        num = float(value)
    except Exception:
        num = float(default)
    return max(min_val, min(max_val, num))


def _extract_dialogue_text_for_tts(value: Any) -> str:
    raw = str(value or "").replace("\r\n", "\n").strip()
    if not raw:
        return ""
    raw_lines = [str(x or "").strip() for x in raw.split("\n") if str(x or "").strip()]

    picked: List[str] = []
    seen = set()

    def _looks_like_non_dialogue_metadata(text_like: Any) -> bool:
        text = str(text_like or "").strip()
        if not text:
            return True

        low = re.sub(r"\s+", " ", text).strip().lower()
        if not low:
            return True

        if re.fullmatch(r"[a-z]{2}", low):
            return True
        if low in {"中文", "chinese", "中文 / chinese", "chinese / 中文"}:
            return True

        metadata_tokens = [
            "prompt en",
            "prompt cn",
            "prompt:",
            "viewpoint",
            "lighting",
            "wardrobe",
            "panel view",
            "panel views",
            "close-up",
            "full-body",
            "subject info",
            "aspect ratio",
            "image",
            "background",
            "no text",
            "pure white",
            "color grade",
            "camera",
            "ref:",
            "style",
            "generation_prompt_cn",
            "generation_prompt_en",
            "subjects_json",
            "existing entity inventory",
            "character context",
            "角色设定",
            "角色信息",
            "角色提示词",
            "人物提示词",
        ]
        if any(token in low for token in metadata_tokens):
            return True

        if "|" in text and ("prompt" in low or "subject" in low):
            return True

        if len(text) > 220:
            return True

        return False

    def _push(text_like: Any) -> None:
        text = str(text_like or "").strip()
        if not text:
            return
        if _looks_like_non_dialogue_metadata(text):
            return
        stable = re.sub(r"\s+", " ", text).strip()
        if not stable:
            return
        key = stable.lower()
        if key in seen:
            return
        seen.add(key)
        picked.append(stable)

    quote_patterns = [
        r'"([^"\n]{1,400})"',
        r'“([^”\n]{1,400})”',
        r'‘([^’\n]{1,400})’',
        r'「([^」\n]{1,400})」',
        r'『([^』\n]{1,400})』',
    ]
    for pattern in quote_patterns:
        for m in re.finditer(pattern, raw):
            _push(m.group(1))

    for line in raw_lines:
        tagged = re.search(r'(?:^|\s)(?:dialogue|line|lines|对白|台词)\s*[:：]\s*(.+)$', line, re.IGNORECASE)
        if tagged and tagged.group(1):
            _push(tagged.group(1))
            continue

        speaker = re.match(r'^([^:：\n|]{1,24})[:：]\s*(.+)$', line)
        if speaker and speaker.group(2):
            speaker_name = str(speaker.group(1) or "").strip().lower()
            if speaker_name and not any(k in speaker_name for k in ["prompt", "style", "view", "subject", "camera", "lighting", "character", "entity"]):
                _push(speaker.group(2))

    # Fallback: when no quoted/speaker dialogue was detected, keep short utterance-like lines only.
    if not picked:
        for line in raw_lines:
            candidate = re.sub(r"^[\-\*\d\.\)\s]+", "", str(line or "").strip())
            if not candidate:
                continue
            if _looks_like_non_dialogue_metadata(candidate):
                continue
            if "|" in candidate:
                continue
            if not re.search(r"[。！？!?]", candidate):
                continue
            if len(candidate) > 120:
                continue
            _push(candidate)

    # Final pass: keep only clean utterance-like lines.
    cleaned_lines = []
    for line in picked:
        stable_line = re.sub(r"\s+", " ", str(line or "")).strip()
        if not stable_line:
            continue
        if _looks_like_non_dialogue_metadata(stable_line):
            continue
        cleaned_lines.append(stable_line)

    return "\n".join(cleaned_lines)


def _strip_subject_prompt_context_for_voice(value: Any) -> str:
    raw = str(value or "").replace("\r\n", "\n").strip()
    if not raw:
        return ""

    lines = raw.split("\n")
    cleaned: List[str] = []

    remove_tokens = [
        "generation_prompt_cn",
        "generation_prompt_en",
        "subjects_json",
        "existing entity inventory",
        "reusable subject assets",
        "subject info",
        "subject prompt",
        "character context",
        "entity context",
        "角色设定",
        "角色信息",
        "角色提示词",
        "人物提示词",
        "prompt en:",
        "prompt cn:",
    ]

    for line in lines:
        text = str(line or "").strip()
        if not text:
            cleaned.append("")
            continue
        low = text.lower()
        if any(token in low for token in remove_tokens):
            continue
        cleaned.append(text)

    compact = "\n".join(cleaned)
    compact = re.sub(r"\n{3,}", "\n\n", compact).strip()
    return compact


def _sanitize_kie_tts_plan(raw_plan: Dict[str, Any], fallback_text: str = "") -> Dict[str, Any]:
    plan = raw_plan if isinstance(raw_plan, dict) else {}
    out: Dict[str, Any] = {}

    fallback_dialogue = _extract_dialogue_text_for_tts(fallback_text) if str(fallback_text or "").strip() else ""
    planned_text_raw = str(plan.get("text") or "").strip()
    planned_dialogue_only = _extract_dialogue_text_for_tts(planned_text_raw)
    text_value = planned_dialogue_only or fallback_dialogue
    if text_value:
        out["text"] = text_value

    voice_value = _normalize_kie_voice_name(plan.get("voice") or plan.get("voice_id"))
    out["voice"] = voice_value or _KIE_TTS_DEFAULT_VOICE

    language_code = _normalize_language_code(plan.get("language_code") or plan.get("language") or plan.get("lang"))
    if language_code:
        out["language_code"] = language_code

    out["stability"] = _clamp_float(plan.get("stability"), 0.0, 1.0, 0.5)
    out["similarity_boost"] = _clamp_float(plan.get("similarity_boost"), 0.0, 1.0, 0.75)
    out["style"] = _clamp_float(plan.get("style"), 0.0, 1.0, 0.0)
    out["speed"] = _clamp_float(plan.get("speed"), 0.7, 1.2, 1.0)

    if plan.get("timestamps") is None:
        out["timestamps"] = False
    else:
        out["timestamps"] = bool(_to_bool(plan.get("timestamps")))

    previous_text = str(plan.get("previous_text") or "").strip()
    next_text = str(plan.get("next_text") or "").strip()
    if previous_text:
        out["previous_text"] = previous_text
    if next_text:
        out["next_text"] = next_text

    return out

