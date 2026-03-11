import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

LLMS_TXT_URL = "https://docs.kie.ai/llms.txt"
PARSER_VERSION = "kie-llmstxt-v2"

_DOC_CACHE: Dict[str, str] = {}


@dataclass
class DocEntry:
    section: str
    title: str
    url: str
    summary: str
    category: str
    generation_modes: List[str]
    text_caps: Dict[str, Any]
    voice_caps: Dict[str, Any]
    music_caps: Dict[str, Any]


def _safe_json_dict(obj: Any) -> Dict[str, Any]:
    return obj if isinstance(obj, dict) else {}


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _derive_base_model_from_model(model_value: Any) -> Optional[str]:
    model_text = str(model_value or "").strip()
    if not model_text:
        return None
    normalized = model_text.replace("\\", "/").strip("/")
    if not normalized:
        return None
    if "/" in normalized:
        head = normalized.split("/", 1)[0].strip()
        if head:
            return head
    return normalized


def _token_contains(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    if len(needle) < 4:
        return False
    return needle in haystack


def _unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        t = str(item or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _model_alias_tokens(model: str) -> List[str]:
    m = str(model or "").strip().lower()
    if not m:
        return []

    raw_parts = re.split(r"[^a-z0-9]+", m)
    compact = _normalize_token(m)
    aliases: List[str] = [compact]

    # Common fragments from model names.
    aliases.extend([p for p in raw_parts if len(p) >= 3])

    # Remove common version noise to improve matching.
    compact_no_ver = re.sub(r"v\d+\d*", "", compact)
    compact_no_ver = re.sub(r"\d{2,}", "", compact_no_ver)
    if compact_no_ver and len(compact_no_ver) >= 5:
        aliases.append(compact_no_ver)

    # Targeted aliases for known KIE naming mismatches.
    if "fluxkontext" in compact:
        aliases.extend(["fluxkontext", "kontext", "fluxkontextapi"])
    if "veo" in compact:
        aliases.extend(["veo3", "veo31", "veo3api"])
    if "zimage" in compact:
        aliases.extend(["zimage"])
    if "runway" in compact:
        aliases.extend(["runway", "runwayapi", "aleph"])
    if "gpt4oimage" in compact or ("gpt" in compact and "image" in compact):
        aliases.extend(["gptimage", "4oimage", "gptimage15"])
    if "wan" in compact:
        aliases.extend(["wan", "flash", "turbo"])
    if "gemini" in compact:
        aliases.extend(["gemini", "gemini25flash", "gemini25pro", "gemini3pro"])
    if "unknownllm" in compact:
        aliases.extend(["chatmodels", "gpt", "claude", "gemini", "chat"])

    normalized = [_normalize_token(x) for x in aliases]
    normalized = [x for x in normalized if len(x) >= 3]
    return _unique_keep_order(normalized)


def _fetch_doc_text(url: str) -> str:
    u = str(url or "").strip()
    if not u:
        return ""
    if u in _DOC_CACHE:
        return _DOC_CACHE[u]
    try:
        resp = requests.get(u, timeout=25)
        resp.raise_for_status()
        txt = resp.text or ""
    except Exception:
        txt = ""
    _DOC_CACHE[u] = txt
    return txt


def _extract_related_doc_urls(base_url: str, text: str) -> List[str]:
    out: List[str] = []
    if not text:
        return out

    # Absolute links.
    abs_urls = re.findall(r"https?://docs\.kie\.ai/[A-Za-z0-9_./\-]+", text)
    out.extend(abs_urls)

    # Markdown relative links: [xx](/path/to/doc)
    rel_urls = re.findall(r"\]\((/[A-Za-z0-9_./\-]+)\)", text)
    for ru in rel_urls:
        out.append(urljoin(base_url, ru))

    # Raw relative tokens that appear in docs snippets.
    rel_tokens = re.findall(r"\s(/[a-z0-9][A-Za-z0-9_./\-]+)", text)
    for tok in rel_tokens:
        if tok.startswith("//"):
            continue
        out.append(urljoin(base_url, tok))

    filtered: List[str] = []
    for u in out:
        s = str(u or "").strip()
        if not s.startswith("https://docs.kie.ai/"):
            continue
        if "/api-key" in s:
            continue
        filtered.append(s)

    return _unique_keep_order(filtered)


def _extract_aspect_ratios(text: str) -> List[str]:
    vals = re.findall(r"\b\d{1,2}:\d{1,2}\b|\bAuto\b", text, flags=re.IGNORECASE)
    normalized = []
    for v in vals:
        token = str(v).strip()
        if token.lower() == "auto":
            token = "Auto"
        elif ":" in token:
            try:
                a, b = token.split(":", 1)
                ai = int(a)
                bi = int(b)
                # Keep only realistic image/video aspect ratios.
                if ai < 1 or bi < 1 or ai > 21 or bi > 21:
                    continue
            except Exception:
                continue
        normalized.append(token)
    return _unique_keep_order(normalized)


def _extract_resolutions(text: str) -> List[str]:
    vals = re.findall(r"\b\d{3,4}\s*[x×]\s*\d{3,4}\b|\b(?:720p|1080p|2k|4k)\b", text, flags=re.IGNORECASE)
    out: List[str] = []
    for v in vals:
        t = str(v).lower().replace(" ", "")
        t = t.replace("×", "x")
        out.append(t)
    return _unique_keep_order(out)


def _extract_max_duration_seconds(text: str) -> Optional[int]:
    candidates: List[int] = []

    for m in re.finditer(r"(?:duration|video duration|total duration|shot duration|时长)[^\n]{0,40}?(\d{1,3})\s*(?:to|-|~)\s*(\d{1,3})\s*(?:seconds|s|秒)", text, flags=re.IGNORECASE):
        candidates.append(int(m.group(2)))
    for m in re.finditer(r"(?:max(?:imum)?\s*duration|maximum duration|max duration|duration max|最大时长)[^\n]{0,20}?(\d{1,3})\s*(?:seconds|s|秒)", text, flags=re.IGNORECASE):
        candidates.append(int(m.group(1)))

    # Keep only plausible media duration values (seconds).
    candidates = [c for c in candidates if 1 <= int(c) <= 180]
    if not candidates:
        return None
    return max(candidates)


def _extract_reference_image_limit(text: str) -> Optional[str]:
    patterns = [
        r"supports\s*(\d+)\s*(?:or\s*(\d+))?\s*images",
        r"requires\s*(\d+)\s*[-~to]{1,3}\s*(\d+)\s*images",
        r"(\d+)\s*[-~to]{1,3}\s*(\d+)\s*files\s*per\s*element",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if not m:
            continue
        a = m.group(1)
        b = m.group(2)
        if b:
            return f"{a}-{b} images"
        return f"{a} images"
    return None


def _extract_mode_values(text: str) -> List[str]:
    modes: List[str] = []
    for m in re.finditer(r"\bmode\b[^\n]{0,150}\benum\b([\s\S]{0,220})", text, flags=re.IGNORECASE):
        block = m.group(1)
        modes.extend(re.findall(r"-\s*([a-zA-Z0-9_\-]+)", block))
    for m in re.finditer(r"\bgenerationType\b[^\n]{0,200}\benum\b([\s\S]{0,260})", text, flags=re.IGNORECASE):
        block = m.group(1)
        modes.extend(re.findall(r"-\s*([A-Z0-9_\-]+)", block))

    low = text.lower()
    for kw in ["std", "pro", "fast", "quality", "turbo", "basic", "high"]:
        if re.search(rf"\b{re.escape(kw)}\b", low):
            modes.append(kw)

    modes.extend(re.findall(r"\b(?:TEXT_2_VIDEO|FIRST_AND_LAST_FRAMES_2_VIDEO|REFERENCE_2_VIDEO)\b", text))
    return _unique_keep_order([str(x).strip() for x in modes if str(x).strip()])


def _extract_doc_capability_fields(urls: List[str]) -> Dict[str, Any]:
    seed_urls = _unique_keep_order([str(u or "").strip() for u in urls if str(u or "").strip()])
    expanded_urls: List[str] = []
    merged_text_parts: List[str] = []

    # Depth-1 crawl for related docs to improve field coverage.
    for seed in seed_urls[:4]:
        expanded_urls.append(seed)
        txt = _fetch_doc_text(seed)
        if txt:
            merged_text_parts.append(txt)
            related = _extract_related_doc_urls(seed, txt)
            for ru in related[:6]:
                expanded_urls.append(ru)

    for u in _unique_keep_order(expanded_urls)[:14]:
        txt = _fetch_doc_text(u)
        if txt:
            merged_text_parts.append(txt)

    merged = "\n\n".join(merged_text_parts)
    if not merged:
        return {}

    aspects = _extract_aspect_ratios(merged)
    resolutions = _extract_resolutions(merged)
    max_duration = _extract_max_duration_seconds(merged)
    ref_limit = _extract_reference_image_limit(merged)
    mode_values = _extract_mode_values(merged)

    out: Dict[str, Any] = {}
    if aspects:
        out["aspect_ratios"] = aspects[:12]
    if resolutions:
        out["supported_resolutions"] = resolutions[:16]
    if max_duration is not None:
        out["max_duration"] = int(max_duration)
    if ref_limit:
        out["reference_image_limit"] = ref_limit
    if mode_values:
        out["mode_values"] = mode_values[:16]
    if "audio" in merged.lower():
        out["has_audio"] = True

    out["crawl_source_count"] = len(_unique_keep_order(expanded_urls))

    return out


def _infer_category(section: str, title: str) -> str:
    s = f"{section} {title}".lower()
    if "chat  models" in s or "chat models" in s:
        return "LLM"
    if "image" in s:
        return "Image"
    if "video" in s:
        return "Video"
    if "music models" in s:
        if any(k in s for k in ["speech", "text-to-speech", "speech-to-text", "dialogue", "voice", "audio-isolation"]):
            return "Voice"
        return "Music"
    if "suno api" in s:
        return "Music"
    return "Image"


def _infer_generation_modes(section: str, title: str, summary: str) -> List[str]:
    s = f"{section} {title} {summary}".lower()
    modes: List[str] = []
    if "text to image" in s or "文生图" in s:
        modes.append("t2i")
    if "image to image" in s or "图生图" in s or "edit" in s or "编辑" in s:
        modes.append("i2i")
    if "text to video" in s or "文生视频" in s:
        modes.append("t2v")
    if "image to video" in s or "图生视频" in s:
        modes.append("i2v")
    if "video to video" in s or "视频转视频" in s:
        modes.append("v2v")
    if "speech to video" in s or "语音转视频" in s:
        modes.append("s2v")
    if "text-to-speech" in s or "文生语音" in s or "dialogue" in s:
        modes.append("t2a")
    if "speech-to-text" in s or "语音转文字" in s:
        modes.append("a2t")
    if "audio-isolation" in s or "vocal" in s or "分离" in s:
        modes.append("a2a")
    if "chat" in s or "completion" in s or "streaming support" in s:
        modes.append("chat")
    return _unique_keep_order(modes)


def _infer_voice_caps(text: str) -> Dict[str, Any]:
    s = text.lower()
    caps: Dict[str, Any] = {}
    if any(k in s for k in ["text-to-speech", "文生语音", "dialogue"]):
        caps["supports_tts"] = True
    if any(k in s for k in ["speech-to-text", "语音转文字"]):
        caps["supports_asr"] = True
    if any(k in s for k in ["audio-isolation", "separate", "分离"]):
        caps["supports_audio_separation"] = True
    return caps


def _infer_music_caps(text: str) -> Dict[str, Any]:
    s = text.lower()
    caps: Dict[str, Any] = {}
    if any(k in s for k in ["music", "suno", "lyrics", "midi", "mashup", "cover", "bgm", "音乐"]):
        caps["supports_music_generation"] = True
    if any(k in s for k in ["lyrics", "歌词"]):
        caps["supports_lyrics"] = True
    if any(k in s for k in ["midi"]):
        caps["supports_midi"] = True
    return caps


def parse_llms_txt(content: str) -> List[DocEntry]:
    entries: List[DocEntry] = []
    current_section = ""
    # Example line:
    # - Chat  Models > GPT [GPT-5-2](https://docs.kie.ai/market/chat/gpt-5-2.md): ...
    item_re = re.compile(r"^\s*-\s*(.*?)\s*\[(.*?)\]\((https?://[^)]+)\)\s*:?\s*(.*)$")

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue
        m = item_re.match(line)
        if not m:
            continue

        section_path = (m.group(1) or "").strip()
        title = (m.group(2) or "").strip()
        url = (m.group(3) or "").strip()
        summary = (m.group(4) or "").strip()

        merged_section = section_path or current_section
        blob = f"{merged_section} {title} {summary}"
        category = _infer_category(merged_section, title)
        generation_modes = _infer_generation_modes(merged_section, title, summary)
        voice_caps = _infer_voice_caps(blob)
        music_caps = _infer_music_caps(blob)
        text_caps: Dict[str, Any] = {}
        if category == "LLM":
            text_caps["supports_chat"] = True
            if "stream" in blob.lower() or "流式" in blob.lower():
                text_caps["supports_streaming"] = True

        entries.append(
            DocEntry(
                section=merged_section,
                title=title,
                url=url,
                summary=summary,
                category=category,
                generation_modes=generation_modes,
                text_caps=text_caps,
                voice_caps=voice_caps,
                music_caps=music_caps,
            )
        )

    return entries


def score_match(row: SystemAPISetting, entry: DocEntry) -> int:
    model = str(getattr(row, "model", "") or "").strip().lower()
    base_model = str(getattr(row, "base_model", "") or "").strip().lower() or str(_derive_base_model_from_model(model) or "").lower()
    if not model:
        return 0

    blob = " ".join([entry.section, entry.title, entry.url, entry.summary]).lower()
    blob_n = _normalize_token(blob)
    model_n = _normalize_token(model)
    base_n = _normalize_token(base_model)

    score = 0
    if _token_contains(blob_n, model_n):
        score += 100
    model_tail = model.split("/")[-1]
    model_tail_n = _normalize_token(model_tail)
    if model_tail_n and _token_contains(blob_n, model_tail_n):
        score += 40
    if base_n and _token_contains(blob_n, base_n):
        score += 20

    row_category = str(getattr(row, "category", "") or "")
    if row_category == entry.category:
        score += 15

    # Light fuzzy fallback by provider/model vendor prefix keywords.
    vendor_hint = model.split("/")[0]
    vendor_n = _normalize_token(vendor_hint)
    if vendor_n and len(vendor_n) >= 4 and _token_contains(blob_n, vendor_n):
        score += 10

    for alias in _model_alias_tokens(model):
        if _token_contains(blob_n, alias):
            score += 14
            break

    # Prefer same-category entries for weak alias matches.
    if row_category == entry.category and score > 0:
        score += 5

    return score


def build_best_matches(rows: List[SystemAPISetting], entries: List[DocEntry]) -> Dict[int, List[DocEntry]]:
    mapping: Dict[int, List[DocEntry]] = {}
    for row in rows:
        scored: List[tuple[int, DocEntry]] = []
        for entry in entries:
            s = score_match(row, entry)
            if s > 0:
                scored.append((s, entry))
        scored.sort(key=lambda x: x[0], reverse=True)

        strong = [pair for pair in scored if pair[0] >= 60]
        if strong:
            mapping[int(row.id)] = [e for _, e in strong[:12]]
            continue

        medium = [pair for pair in scored if pair[0] >= 30]
        if medium:
            mapping[int(row.id)] = [e for _, e in medium[:8]]
            continue

        row_category = str(getattr(row, "category", "") or "")
        if row_category == "LLM":
            llm_entries = [e for e in entries if e.category == "LLM"]
            mapping[int(row.id)] = llm_entries[:3]
            continue

        mapping[int(row.id)] = []
    return mapping


def main() -> None:
    response = requests.get(LLMS_TXT_URL, timeout=40)
    response.raise_for_status()
    content = response.text

    entries = parse_llms_txt(content)
    if not entries:
        raise RuntimeError("No parseable entries found in llms.txt")

    db = SessionLocal()
    try:
        rows = (
            db.query(SystemAPISetting)
            .filter(SystemAPISetting.provider == "kie")
            .filter(~SystemAPISetting.category.like("System_%"))
            .all()
        )

        matches = build_best_matches(rows, entries)
        now_iso = now_bj_iso()

        updated_rows = 0
        matched_rows = 0
        unmatched_rows = 0

        for row in rows:
            row_id = int(row.id)
            row_matches = matches.get(row_id, [])
            row_category = str(getattr(row, "category", "") or "")

            modality = dict(_safe_json_dict(row.modality))
            supplier_info = dict(_safe_json_dict(row.supplier_info))

            # Remove stale invalid duration values from previous runs.
            if "max_duration" in modality:
                try:
                    cur_d = int(modality.get("max_duration"))
                    if cur_d < 1 or cur_d > 180:
                        modality.pop("max_duration", None)
                except Exception:
                    modality.pop("max_duration", None)

            if row_matches:
                matched_rows += 1
                gm: List[str] = []
                text_caps: Dict[str, Any] = _safe_json_dict(modality.get("text_capabilities"))
                voice_caps: Dict[str, Any] = _safe_json_dict(modality.get("voice_capabilities"))
                music_caps: Dict[str, Any] = _safe_json_dict(modality.get("music_capabilities"))
                refs: List[Dict[str, Any]] = []
                ref_urls: List[str] = []

                for e in row_matches:
                    gm.extend(e.generation_modes)
                    text_caps.update(e.text_caps)
                    voice_caps.update(e.voice_caps)
                    music_caps.update(e.music_caps)
                    refs.append(
                        {
                            "section": e.section,
                            "title": e.title,
                            "url": e.url,
                            "summary": e.summary,
                            "category": e.category,
                        }
                    )
                    if e.url:
                        ref_urls.append(e.url)

                doc_caps = _extract_doc_capability_fields(ref_urls)

                modality["generation_modes"] = _unique_keep_order((modality.get("generation_modes") or []) + gm)
                if text_caps:
                    modality["text_capabilities"] = text_caps
                if voice_caps:
                    modality["voice_capabilities"] = voice_caps
                if music_caps:
                    modality["music_capabilities"] = music_caps
                if doc_caps.get("aspect_ratios"):
                    modality["aspect_ratios"] = _unique_keep_order((modality.get("aspect_ratios") or []) + doc_caps.get("aspect_ratios", []))
                if doc_caps.get("supported_resolutions"):
                    modality["supported_resolutions"] = _unique_keep_order((modality.get("supported_resolutions") or []) + doc_caps.get("supported_resolutions", []))
                if row_category in {"Video", "Music", "Voice", "DigitalHuman"} and doc_caps.get("max_duration") is not None:
                    existing_max = modality.get("max_duration")
                    try:
                        existing_max = int(existing_max) if existing_max is not None else None
                    except Exception:
                        existing_max = None
                    incoming_max = int(doc_caps.get("max_duration"))
                    modality["max_duration"] = max(existing_max or 0, incoming_max)
                elif row_category not in {"Video", "Music", "Voice", "DigitalHuman"}:
                    modality.pop("max_duration", None)
                if doc_caps.get("has_audio") is True:
                    modality["has_audio"] = True
                if doc_caps.get("mode_values"):
                    modality["mode_values"] = _unique_keep_order((modality.get("mode_values") or []) + doc_caps.get("mode_values", []))
                if doc_caps.get("reference_image_limit"):
                    modality["reference_image_limit"] = str(doc_caps.get("reference_image_limit"))

                if "input_formats" not in modality:
                    modality["input_formats"] = []
                if "output_format" not in modality:
                    if row_category == "Image":
                        modality["output_format"] = "image"
                    elif row_category == "Video":
                        modality["output_format"] = "video"
                    elif row_category == "Voice":
                        modality["output_format"] = "audio"
                    elif row_category == "Music":
                        modality["output_format"] = "audio"
                    else:
                        modality["output_format"] = "text"
                if "base_model" not in modality:
                    base_model = str(getattr(row, "base_model", "") or "").strip() or str(_derive_base_model_from_model(getattr(row, "model", "")) or "").strip()
                    modality["base_model"] = base_model or str(getattr(row, "model", "") or "").strip()

                supplier_info["llms_txt_preupdate"] = {
                    "updated_at": now_iso,
                    "parser_version": PARSER_VERSION,
                    "source_url": LLMS_TXT_URL,
                    "match_count": len(refs),
                    "matched_entries": refs,
                    "doc_extracted": doc_caps,
                    "note": "Deterministic parse from llms.txt without LLM inference",
                }
                source_urls = supplier_info.get("source_urls") if isinstance(supplier_info.get("source_urls"), list) else []
                if LLMS_TXT_URL not in source_urls:
                    source_urls.append(LLMS_TXT_URL)
                supplier_info["source_urls"] = source_urls
            else:
                unmatched_rows += 1
                supplier_info["llms_txt_preupdate"] = {
                    "updated_at": now_iso,
                    "parser_version": PARSER_VERSION,
                    "source_url": LLMS_TXT_URL,
                    "match_count": 0,
                    "matched_entries": [],
                    "note": "No deterministic match from llms.txt index",
                }

            row.modality = modality
            row.supplier_info = supplier_info

            # Keep wide columns in sync with legacy modality JSON.
            row.generation_modes = modality.get("generation_modes")
            row.input_formats = modality.get("input_formats")
            row.output_format = modality.get("output_format")
            row.supported_resolutions = modality.get("supported_resolutions")
            row.aspect_ratios = modality.get("aspect_ratios")
            row.max_images_per_call = modality.get("max_images_per_call")
            row.reference_image_limit = modality.get("reference_image_limit")
            row.reference_video_limit = modality.get("reference_video_limit")
            row.durations_seconds = modality.get("durations_seconds")
            row.max_duration = modality.get("max_duration")
            row.fps_options = modality.get("fps_options")
            row.has_audio = modality.get("has_audio")
            row.mode_values = modality.get("mode_values")
            row.text_capabilities = modality.get("text_capabilities")
            row.image_capabilities = modality.get("image_capabilities")
            row.video_capabilities = modality.get("video_capabilities")
            row.digital_human_capabilities = modality.get("digital_human_capabilities")
            row.voice_capabilities = modality.get("voice_capabilities")
            row.music_capabilities = modality.get("music_capabilities")

            if not getattr(row, "base_model", None):
                row.base_model = str(modality.get("base_model") or "").strip() or _derive_base_model_from_model(getattr(row, "model", ""))

            updated_rows += 1

        db.commit()

        print("=== KIE_LLMSTXT_PREUPDATE_RESULT ===")
        print(f"llms_entries_parsed={len(entries)}")
        print(f"kie_rows_total={len(rows)}")
        print(f"rows_updated={updated_rows}")
        print(f"rows_matched={matched_rows}")
        print(f"rows_unmatched={unmatched_rows}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
