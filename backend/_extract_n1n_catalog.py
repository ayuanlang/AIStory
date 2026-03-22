import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LLMS = ROOT / "docs" / "n1n_llms.txt"
DEFAULT_PROXY = ROOT / "docs" / "n1n_llm-api-proxy-address.md"
DEFAULT_REQUEST = ROOT / "docs" / "n1n_llm-api-request.md"
DEFAULT_PRICE = ROOT / "docs" / "n1n_llm-api-price.md"
DEFAULT_PRICE_GROUP = ROOT / "docs" / "n1n_llm-api-price-group.md"
DEFAULT_GATEWAY = ROOT / "docs" / "n1n_llm-api.md"
DEFAULT_OUTPUT = ROOT / "docs" / "n1n_catalog_snapshot.protocol_baseline.json"
DEFAULT_SCAN_MD = ROOT / "docs" / "n1n_llms_full_scan_20260320.md"

LINK_RE = re.compile(r"^-\s*(?:(?P<crumb>.+?)\s+)?\[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\):\s*(?P<desc>.*)$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _safe_slug(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return re.sub(r"-+", "-", text)


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _unique_keep_order(items: List[Any]) -> List[Any]:
    seen = set()
    out: List[Any] = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _classify_category(breadcrumb: str, title: str, desc: str) -> str:
    text = f"{breadcrumb} {title} {desc}".lower()
    if "suno" in text or "文生音乐" in text or "音乐" in text:
        return "Music"
    if "视频" in text or "video" in text:
        return "Video"
    if any(token in text for token in ["音频", "语音", "speech", "audio", "transcribe", "tts", "whisper"]):
        return "Voice"
    if any(token in text for token in ["绘画", "图片", "图像", "image", "dall", "ideogram", "flux", "midjourney", "gpt-image"]):
        return "Image"
    if "rerank" in text or "重排序" in text:
        return "Tools"
    return "LLM"


def _infer_generation_modes(category: str, breadcrumb: str, title: str, desc: str) -> List[str]:
    text = f"{breadcrumb} {title} {desc}".lower()
    modes: List[str] = []
    if category == "Image":
        if any(token in text for token in ["图生图", "edit", "编辑", "mask", "remix", "reframe", "replace background", "inpainting"]):
            modes.append("i2i")
        if any(token in text for token in ["文生图", "创建", "generate", "图片生成", "创作图", "dall", "gpt-image", "ideogram"]):
            modes.append("t2i")
        if "describe" in text or "描述" in text:
            modes.append("i2t")
    elif category == "Video":
        if any(token in text for token in ["图生视频", "带图片", "image to video", "参考图", "首尾帧"]):
            modes.append("i2v")
        if any(token in text for token in ["文生视频", "创建视频", "video generation", "text to video"]):
            modes.append("t2v")
        if any(token in text for token in ["扩展视频", "编辑视频", "延长", "连续修改", "video edit"]):
            modes.append("v2v")
    elif category == "Voice":
        if any(token in text for token in ["转文字", "transcribe", "speech to text", "识别"]):
            modes.append("a2t")
        if any(token in text for token in ["tts", "文本转语音", "语音合成", "文生音效", "文生音频", "text to speech"]):
            modes.append("t2a")
        if any(token in text for token in ["复刻", "clone"]):
            modes.append("a2a")
    elif category == "Music":
        modes.append("t2a")
    return sorted(set(modes))


def _infer_family_key(breadcrumb: str, title: str) -> str:
    text = f"{breadcrumb} {title}".lower()
    rules = [
        ("聊天（responses）", "openai_responses"),
        ("chatgpt 接口", "openai"),
        ("anthropic claude 接口", "claude"),
        ("gemini 接口", "gemini"),
        ("midjourney", "midjourney"),
        ("ideogram", "ideogram"),
        ("gpt image", "gpt_image"),
        ("grok image", "grok_image"),
        ("grok 视频", "grok_video"),
        ("flux 系列", "flux"),
        ("fal.ai 平台", "fal_ai"),
        ("fal-ai 聚合平台", "fal_ai"),
        ("qwen 千问系列", "qwen_image"),
        ("即梦绘画", "jimeng_image"),
        ("豆包系列", "doubao_image"),
        ("腾讯 aigc 视频生成", "tencent_video"),
        ("腾讯 aigc", "tencent_image"),
        ("sora 视频生成", "sora"),
        ("luma 视频生成", "luma"),
        ("runway 视频生成", "runway"),
        ("veo 视频生成", "veo"),
        ("即梦 视频生成", "jimeng_video"),
        ("海螺 视频生成", "hailuo_video"),
        ("豆包 视频生成", "doubao_video"),
        ("通义万象 视频生成", "tongyi_video"),
        ("kling 可灵平台", "kling"),
        ("minimax 海螺平台", "minimax"),
        ("vidu 视频/图片/音频生成", "vidu"),
        ("suno 文生音乐", "suno"),
        ("replicate 聚合平台", "replicate"),
        ("rerank 重排序模型", "rerank"),
    ]
    for pattern, family in rules:
        if pattern in text:
            return family
    top = str(breadcrumb or "").split(">", 1)[0].strip()
    return _safe_slug(top) or "misc"


def _profile_metadata(family_key: str, category: str, breadcrumb: str, title: str) -> Dict[str, Any]:
    crumb = str(breadcrumb or "")
    crumb_lower = crumb.lower()
    title_lower = str(title or "").lower()
    if family_key == "openai_responses":
        return {
            "protocol_key": "openai_responses",
            "protocol_label": "OpenAI Compatible Responses",
            "api_style": "openai_compatible",
            "endpoint_hint": "/v1/responses",
            "billing_unit_type": "per_million_tokens",
            "family_label": "OpenAI Compatible",
        }
    if family_key == "openai":
        if "音频（audio）" in crumb_lower or "audio" in crumb_lower:
            if any(token in title_lower for token in ["whisper", "transcribe", "转文字"]):
                return {
                    "protocol_key": "openai_audio_transcriptions",
                    "protocol_label": "OpenAI Compatible Audio Transcriptions",
                    "api_style": "openai_compatible",
                    "endpoint_hint": "/v1/audio/transcriptions",
                    "billing_unit_type": "per_call",
                    "family_label": "OpenAI Compatible",
                }
            if any(token in title_lower for token in ["tts", "创建语音", "文本转语音"]):
                return {
                    "protocol_key": "openai_audio_speech",
                    "protocol_label": "OpenAI Compatible Text To Speech",
                    "api_style": "openai_compatible",
                    "endpoint_hint": "/v1/audio/speech",
                    "billing_unit_type": "per_call",
                    "family_label": "OpenAI Compatible",
                }
            return {
                "protocol_key": "openai_audio_chat_completions",
                "protocol_label": "OpenAI Compatible Audio Chat",
                "api_style": "openai_compatible",
                "endpoint_hint": "/v1/chat/completions",
                "billing_unit_type": "per_million_tokens",
                "family_label": "OpenAI Compatible",
            }
        if any(token in title_lower for token in ["whisper", "transcribe", "转文字"]):
            return {
                "protocol_key": "openai_audio_transcriptions",
                "protocol_label": "OpenAI Compatible Audio Transcriptions",
                "api_style": "openai_compatible",
                "endpoint_hint": "/v1/audio/transcriptions",
                "billing_unit_type": "per_call",
                "family_label": "OpenAI Compatible",
            }
        if any(token in title_lower for token in ["tts", "创建语音", "文本转语音"]):
            return {
                "protocol_key": "openai_audio_speech",
                "protocol_label": "OpenAI Compatible Text To Speech",
                "api_style": "openai_compatible",
                "endpoint_hint": "/v1/audio/speech",
                "billing_unit_type": "per_call",
                "family_label": "OpenAI Compatible",
            }
        if "embeddings" in crumb.lower() or "嵌入" in crumb:
            return {
                "protocol_key": "openai_embeddings",
                "protocol_label": "OpenAI Compatible Embeddings",
                "api_style": "openai_compatible",
                "endpoint_hint": "/v1/embeddings",
                "billing_unit_type": "per_million_tokens",
                "family_label": "OpenAI Compatible",
            }
        return {
            "protocol_key": "openai_chat_completions",
            "protocol_label": "OpenAI Compatible Chat Completions",
            "api_style": "openai_compatible",
            "endpoint_hint": "/v1/chat/completions",
            "billing_unit_type": "per_million_tokens",
            "family_label": "OpenAI Compatible",
        }
    if family_key == "claude":
        if "chat 兼容格式" in crumb.lower():
            return {
                "protocol_key": "claude_chat_compatible",
                "protocol_label": "Claude Chat Compatible",
                "api_style": "chat_compatible",
                "endpoint_hint": "/v1/chat/completions",
                "billing_unit_type": "per_million_tokens",
                "family_label": "Anthropic Claude",
            }
        return {
            "protocol_key": "claude_native_messages",
            "protocol_label": "Claude Native Messages",
            "api_style": "native",
            "endpoint_hint": "/v1/messages",
            "billing_unit_type": "per_million_tokens",
            "family_label": "Anthropic Claude",
        }
    if family_key == "gemini":
        if "chat 兼容格式" in crumb.lower():
            return {
                "protocol_key": "gemini_chat_compatible",
                "protocol_label": "Gemini Chat Compatible",
                "api_style": "chat_compatible",
                "endpoint_hint": "/v1/chat/completions",
                "billing_unit_type": "per_million_tokens",
                "family_label": "Google Gemini",
            }
        if "embeddings" in title_lower or "文本嵌入" in title_lower:
            return {
                "protocol_key": "gemini_native_embeddings",
                "protocol_label": "Gemini Native Embeddings",
                "api_style": "native",
                "endpoint_hint": "/v1beta/models/{model}:embedContent",
                "billing_unit_type": "per_million_tokens",
                "family_label": "Google Gemini",
            }
        if category == "Image":
            return {
                "protocol_key": "gemini_native_image",
                "protocol_label": "Gemini Native Image Generation",
                "api_style": "native",
                "endpoint_hint": "/v1beta/models/{model}:generateContent",
                "billing_unit_type": "per_call",
                "family_label": "Google Gemini",
            }
        return {
            "protocol_key": "gemini_native_generate_content",
            "protocol_label": "Gemini Native Generate Content",
            "api_style": "native",
            "endpoint_hint": "/v1beta/models/{model}:generateContent",
            "billing_unit_type": "per_million_tokens",
            "family_label": "Google Gemini",
        }
    family_label = {
        "midjourney": "Midjourney",
        "ideogram": "Ideogram",
        "gpt_image": "GPT Image",
        "grok_image": "Grok Image",
        "grok_video": "Grok Video",
        "flux": "FLUX",
        "fal_ai": "Fal.ai",
        "qwen_image": "Qwen Image",
        "jimeng_image": "Jimeng Image",
        "doubao_image": "Doubao Image",
        "tencent_image": "Tencent AIGC Image",
        "sora": "Sora Video",
        "luma": "Luma Video",
        "runway": "Runway Video",
        "veo": "Veo Video",
        "jimeng_video": "Jimeng Video",
        "hailuo_video": "Hailuo Video",
        "doubao_video": "Doubao Video",
        "tongyi_video": "Tongyi Video",
        "tencent_video": "Tencent AIGC Video",
        "kling": "Kling Platform",
        "minimax": "MiniMax Platform",
        "vidu": "Vidu Platform",
        "suno": "Suno Music",
        "replicate": "Replicate Platform",
        "rerank": "Rerank",
    }.get(family_key, family_key.replace("_", " ").title())
    unit_type = {
        "LLM": "per_million_tokens",
        "Image": "per_call",
        "Video": "per_second",
        "Voice": "per_call",
        "Music": "per_call",
        "Tools": "per_call",
    }.get(category, "per_call")
    return {
        "protocol_key": f"{family_key}_{category.lower()}",
        "protocol_label": f"{family_label} {category}",
        "api_style": "async_task" if category in {"Image", "Video", "Voice", "Music"} else "provider_specific",
        "endpoint_hint": None,
        "billing_unit_type": unit_type,
        "family_label": family_label,
    }


def _infer_input_formats(category: str, breadcrumb: str, title: str, desc: str) -> List[str]:
    text = f"{breadcrumb} {title} {desc}".lower()
    formats: List[str] = []
    if category == "LLM":
        formats.append("text")
        if any(token in text for token in ["识图", "image", "图片", "pdf", "音频", "audio", "video", "联网搜索", "web 搜索"]):
            if any(token in text for token in ["识图", "image", "图片"]):
                formats.append("image")
            if "pdf" in text:
                formats.append("pdf")
            if any(token in text for token in ["音频", "audio"]):
                formats.append("audio")
            if any(token in text for token in ["video", "视频"]):
                formats.append("video")
            if any(token in text for token in ["web 搜索", "联网搜索"]):
                formats.append("web")
    elif category == "Image":
        if any(token in text for token in ["图生图", "edit", "编辑", "mask", "图片编辑", "remix", "reframe", "replace background"]):
            formats.extend(["text", "image"])
        else:
            formats.append("text")
    elif category == "Video":
        if any(token in text for token in ["带图片", "图生视频", "image", "参考图", "首尾帧"]):
            formats.extend(["text", "image"])
        elif any(token in text for token in ["编辑视频", "扩展视频", "连续修改"]):
            formats.append("video")
        else:
            formats.append("text")
    elif category == "Voice":
        if any(token in text for token in ["转文字", "transcribe", "识别"]):
            formats.append("audio")
        else:
            formats.append("text")
    elif category == "Music":
        formats.append("text")
    return sorted(set(formats))


def _extract_model_hints(title: str, desc: str) -> List[str]:
    text = f"{title} {desc}"
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9./:_-]{2,}", text)
    keep: List[str] = []
    prefixes = ("gpt", "claude", "gemini", "whisper", "flux", "sora", "veo", "vidu", "runway", "luma", "ideogram", "qwen", "deepseek", "grok", "seed", "minimax")
    for candidate in candidates:
        lowered = candidate.lower()
        if any(lowered.startswith(prefix) for prefix in prefixes) or any(char.isdigit() for char in candidate):
            keep.append(candidate)
    return _unique_keep_order(keep)[:8]


def _parse_llms_index(text: str) -> List[Dict[str, Any]]:
    section = ""
    entries: List[Dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        match = LINK_RE.match(line)
        if not match:
            continue
        breadcrumb = str(match.group("crumb") or "").strip()
        title = str(match.group("title") or "").strip()
        url = str(match.group("url") or "").strip()
        desc = str(match.group("desc") or "").strip()
        category = _classify_category(breadcrumb, title, desc)
        family_key = _infer_family_key(breadcrumb, title)
        profile = _profile_metadata(family_key, category, breadcrumb, title)
        entries.append(
            {
                "section": section,
                "breadcrumb": breadcrumb,
                "title": title,
                "url": url,
                "description": desc,
                "category": category,
                "family_key": family_key,
                "family_label": profile["family_label"],
                "protocol_key": profile["protocol_key"],
                "protocol_label": profile["protocol_label"],
                "api_style": profile["api_style"],
                "endpoint_hint": profile["endpoint_hint"],
                "billing_unit_type": profile["billing_unit_type"],
                "generation_modes": _infer_generation_modes(category, breadcrumb, title, desc),
                "input_formats": _infer_input_formats(category, breadcrumb, title, desc),
                "model_hints": _extract_model_hints(title, desc),
            }
        )
    return entries


def _extract_base_urls(proxy_text: str) -> Dict[str, Any]:
    urls = _unique_keep_order(re.findall(r"https://(?:api|hk)\.n1n\.ai(?:/[A-Za-z0-9._:/-]+)?", proxy_text))
    endpoint_paths = _unique_keep_order(re.findall(r"https://(?:api|hk)\.n1n\.ai(/v1(?:/[A-Za-z0-9._/-]+)?)", proxy_text))
    return {
        "primary_base_url": "https://api.n1n.ai",
        "mirror_base_url": "https://hk.n1n.ai",
        "documented_urls": urls,
        "documented_endpoint_paths": endpoint_paths,
    }


def _parse_pricing_groups(text: str, price_url: str) -> Dict[str, Any]:
    groups: List[Dict[str, Any]] = []
    fixed_prices: List[Dict[str, Any]] = []
    current_section = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue
        if current_section != "分组类型及特点":
            continue
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) < 4:
            continue
        if cells[0] in {"分组", ":---", "特点", "模型类型"}:
            continue
        group_name = cells[0]
        group_type = cells[1]
        rate_text = cells[2]
        supported_models = cells[3]
        if group_name.startswith("**") or group_name.startswith("-"):
            continue
        if "官方费率" in supported_models or str(group_type).startswith("官方费率"):
            continue
        multiplier = None
        match = re.search(r"\*\s*([0-9]+(?:\.[0-9]+)?)", rate_text)
        if match:
            multiplier = float(match.group(1))
        direct_price = None
        direct_match = re.search(r"\$\s*([0-9]+(?:\.[0-9]+)?)", rate_text)
        if direct_match:
            direct_price = float(direct_match.group(1))
        record = {
            "group_name": group_name,
            "group_type": group_type,
            "rate_text": rate_text,
            "official_rate_multiplier": multiplier,
            "supported_models": supported_models,
            "source_url": price_url,
        }
        groups.append(record)
        if direct_price is not None:
            fixed_prices.append(
                {
                    "group_name": group_name,
                    "unit_type": "per_call",
                    "price_usd": direct_price,
                    "source_url": price_url,
                }
            )
    return {
        "pricing_basis": "official_rate_x_group_multiplier",
        "groups": _unique_keep_order(groups),
        "known_fixed_prices": fixed_prices,
        "notes": [
            "n1n docs publish group multipliers, not a full machine-readable per-model price table.",
            "Actual charge is documented as upstream official price multiplied by the selected token group rate.",
            "Direct billing import should stay blocked until model-specific official baselines are sourced.",
        ],
    }


def _build_profiles(entries: List[Dict[str, Any]], base_urls: Dict[str, Any]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        if str(entry.get("family_key") or "") in {"misc", "gpts"}:
            continue
        protocol_key = str(entry.get("protocol_key") or "").strip()
        if not protocol_key:
            continue
        profile = grouped.get(protocol_key)
        if profile is None:
            profile = {
                "protocol_key": protocol_key,
                "protocol_label": entry.get("protocol_label"),
                "family_key": entry.get("family_key"),
                "family_label": entry.get("family_label"),
                "category": entry.get("category"),
                "api_style": entry.get("api_style"),
                "endpoint_hint": entry.get("endpoint_hint"),
                "base_url": base_urls.get("primary_base_url"),
                "mirror_base_url": base_urls.get("mirror_base_url"),
                "billing_unit_type": entry.get("billing_unit_type"),
                "generation_modes": [],
                "input_formats": [],
                "sample_titles": [],
                "source_urls": [],
                "model_hints": [],
                "doc_count": 0,
                "import_posture": "staging_only",
            }
            grouped[protocol_key] = profile
        profile["doc_count"] += 1
        profile["generation_modes"] = _unique_keep_order(list(profile.get("generation_modes") or []) + list(entry.get("generation_modes") or []))
        profile["input_formats"] = _unique_keep_order(list(profile.get("input_formats") or []) + list(entry.get("input_formats") or []))
        profile["sample_titles"] = _unique_keep_order(list(profile.get("sample_titles") or []) + [entry.get("title")])[:10]
        profile["source_urls"] = _unique_keep_order(list(profile.get("source_urls") or []) + [entry.get("url")])
        profile["model_hints"] = _unique_keep_order(list(profile.get("model_hints") or []) + list(entry.get("model_hints") or []))[:16]
    return sorted(grouped.values(), key=lambda item: (str(item.get("category") or ""), str(item.get("protocol_key") or "")))


def _build_snapshot(entries: List[Dict[str, Any]], base_urls: Dict[str, Any], pricing: Dict[str, Any], source_urls: List[str]) -> Dict[str, Any]:
    api_docs_entries = [item for item in entries if str(item.get("section") or "") == "API Docs"]
    profiles = _build_profiles(api_docs_entries, base_urls)
    section_counts = Counter(str(item.get("section") or "unknown") for item in entries)
    category_counts = Counter(str(item.get("category") or "unknown") for item in api_docs_entries)
    family_counts = Counter(str(item.get("family_label") or "unknown") for item in api_docs_entries)
    protocol_counts = Counter(str(item.get("protocol_key") or "unknown") for item in api_docs_entries)
    return {
        "generated_at": _now_iso(),
        "source_urls": source_urls,
        "base_urls": base_urls,
        "request_contract": {
            "auth_header": "Authorization: Bearer <API_KEY>",
            "content_type": "application/json",
            "default_openai_endpoint": "/v1/chat/completions",
            "notes": [
                "n1n gateway is documented as OpenAI-compatible for the default path.",
                "Docs also advertise Claude native, Gemini native, and multiple provider-specific async APIs.",
            ],
        },
        "pricing_model": pricing,
        "section_counts": dict(section_counts),
        "category_counts": dict(category_counts),
        "family_counts": dict(family_counts),
        "protocol_counts": dict(protocol_counts),
        "profiles": profiles,
        "api_docs": entries,
    }


def _render_scan(snapshot: Dict[str, Any]) -> str:
    lines = [
        "# n1n llms.txt Full Scan 2026-03-20",
        "",
        "Source: https://docs.n1n.ai/llms.txt",
        "",
        "This document is a protocol-level scan of n1n docs derived from llms.txt and supporting pricing/base-url pages.",
        "It intentionally distinguishes documented protocol families from importable model inventory, because n1n llms.txt is primarily a capability index rather than a machine-readable model list.",
        "",
        "## Scan Result",
        "",
        f"- Indexed docs entries: {len(snapshot.get('api_docs') or [])}",
        f"- API Docs entries: {snapshot.get('section_counts', {}).get('API Docs', 0)}",
        f"- Protocol profiles prepared: {len(snapshot.get('profiles') or [])}",
        "",
        "## Base URLs",
        "",
        f"- Primary: {((snapshot.get('base_urls') or {}).get('primary_base_url') or '')}",
        f"- Mirror: {((snapshot.get('base_urls') or {}).get('mirror_base_url') or '')}",
        f"- Documented endpoint paths: {', '.join(((snapshot.get('base_urls') or {}).get('documented_endpoint_paths') or [])[:6])}",
        "",
        "## Category Counts",
        "",
    ]
    for category, count in sorted((snapshot.get("category_counts") or {}).items()):
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Protocol Profiles", ""])
    for profile in snapshot.get("profiles") or []:
        endpoint_hint = str(profile.get("endpoint_hint") or "").strip() or "undocumented in base pages"
        lines.append(f"- {profile.get('protocol_label')}: category={profile.get('category')}, style={profile.get('api_style')}, docs={profile.get('doc_count')}, endpoint={endpoint_hint}")
    lines.extend(
        [
            "",
            "## Import Guidance",
            "",
            "- Safe default: import n1n as staging-only protocol rows, not as active model inventory.",
            "- The docs clearly publish base URLs, protocol families, and group-based pricing logic, but they do not expose a complete machine-readable per-model price table.",
            "- Direct billing import should stay blocked until model-level official baselines are sourced, or until a separate public price table is captured.",
            "- OpenAI-compatible, Claude native, and Gemini native subsets are the most suitable future runtime activation candidates once a provider adapter is added.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract protocol-level n1n API catalog from llms.txt and supporting docs")
    parser.add_argument("--llms", default=str(DEFAULT_LLMS), help="n1n llms.txt path")
    parser.add_argument("--proxy", default=str(DEFAULT_PROXY), help="Proxy/base-url doc path")
    parser.add_argument("--request", default=str(DEFAULT_REQUEST), help="Request example doc path")
    parser.add_argument("--price", default=str(DEFAULT_PRICE), help="Pricing explanation doc path")
    parser.add_argument("--price-group", default=str(DEFAULT_PRICE_GROUP), help="Pricing group doc path")
    parser.add_argument("--gateway", default=str(DEFAULT_GATEWAY), help="Gateway overview doc path")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Snapshot JSON output path")
    parser.add_argument("--scan-md", default=str(DEFAULT_SCAN_MD), help="Scan markdown output path")
    args = parser.parse_args()

    llms_path = Path(args.llms)
    proxy_path = Path(args.proxy)
    request_path = Path(args.request)
    price_path = Path(args.price)
    price_group_path = Path(args.price_group)
    gateway_path = Path(args.gateway)
    out_path = Path(args.out)
    scan_md_path = Path(args.scan_md)

    llms_text = _read_text(llms_path)
    proxy_text = _read_text(proxy_path)
    request_text = _read_text(request_path)
    price_text = _read_text(price_path)
    price_group_text = _read_text(price_group_path)
    gateway_text = _read_text(gateway_path)

    entries = _parse_llms_index(llms_text)
    base_urls = _extract_base_urls(proxy_text)
    pricing = _parse_pricing_groups(price_group_text, "https://docs.n1n.ai/llm-api-price-group.md")
    pricing.setdefault("pricing_explanation_excerpt", request_text[:0])
    snapshot = _build_snapshot(
        entries,
        base_urls,
        pricing,
        [
            "https://docs.n1n.ai/llms.txt",
            "https://docs.n1n.ai/llm-api-proxy-address.md",
            "https://docs.n1n.ai/llm-api-request.md",
            "https://docs.n1n.ai/llm-api-price.md",
            "https://docs.n1n.ai/llm-api-price-group.md",
            "https://docs.n1n.ai/llm-api.md",
        ],
    )
    overview_notes = list(((snapshot.get("request_contract") or {}).get("notes") or []))
    if "一个 LLM API Key 通用所有模型" in gateway_text:
        overview_notes.append("Gateway overview states that one API key can address all documented model families.")
    if "按量计费" in gateway_text:
        overview_notes.append("Gateway overview states that the platform uses usage-based billing rather than fixed monthly plans.")
    snapshot["request_contract"]["notes"] = _unique_keep_order(overview_notes)

    _write_json(out_path, snapshot)
    _write_text(scan_md_path, _render_scan(snapshot))

    print(f"WROTE {out_path}")
    print(f"WROTE {scan_md_path}")
    print(json.dumps({"api_docs": len(entries), "profiles": len(snapshot.get('profiles') or [])}, ensure_ascii=False))


if __name__ == "__main__":
    main()