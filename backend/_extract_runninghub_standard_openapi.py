import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "runninghub_openapi_snapshot.json"
LLMS_TXT_URL = "https://www.runninghub.cn/runninghub-api-doc-cn/llms.txt"


@dataclass
class IndexEntry:
    section: str
    title: str
    url: str
    summary: str
    category: str
    generation_modes: List[str]
    service_tier: str


@dataclass
class FieldSpec:
    name: str
    field_type: Optional[str] = None
    required: bool = False
    enum_values: List[str] = field(default_factory=list)
    default_value: Optional[str] = None
    data_format: Optional[str] = None
    description: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_token(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _safe_slug(text: Any) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return re.sub(r"-+", "-", value)


def _fetch_text(url: str, timeout: int = 40) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text or ""


def _is_apifox_shell(text: str) -> bool:
    blob = str(text or "")
    if not ("cdn.apifox.com/docs-site/assets" in blob and "__remixContext" in blob):
        return False
    rendered_markers = [
        "请求参数",
        "返回响应",
        "JsonSchemaViewer",
        "request-schema-card",
        "/openapi/v2/",
    ]
    return not any(marker in blob for marker in rendered_markers)


def _derive_api_id(url: str) -> str:
    match = re.search(r"/(api-\d+)\.md$", str(url or "").strip(), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _combined_index_blob(section: str, title: str, summary: str = "", url: str = "") -> str:
    return f"{section} {title} {summary} {url}".lower()


def _infer_category(section: str, title: str, summary: str = "", url: str = "") -> str:
    blob = _combined_index_blob(section, title, summary, url)
    if "音频生成与处理" in blob or "text-to-audio" in blob:
        if any(token in blob for token in ["music", "音乐"]):
            return "Music"
        return "Voice"
    if any(
        token in blob
        for token in [
            "视频生成与处理",
            "text-to-video",
            "image-to-video",
            "reference-to-video",
            "文生视频",
            "图生视频",
            "参考生视频",
            "video-edit",
            "编辑视频",
            "motion-control",
            "动作控制",
            "video-tools",
        ]
    ):
        return "Video"
    if any(
        token in blob
        for token in [
            "图像生成与处理",
            "text-to-image",
            "image-to-image",
            "reference-to-image",
            "文生图",
            "图生图",
            "图像编辑",
        ]
    ):
        return "Image"
    if "3d" in blob:
        return "3D"
    return "Unknown"


def _infer_generation_modes(section: str, title: str, summary: str) -> List[str]:
    blob = _combined_index_blob(section, title, summary)
    modes: List[str] = []
    if "text-to-image" in blob or "文生图" in blob:
        modes.append("t2i")
    if "image-to-image" in blob or "图生图" in blob or "图像编辑" in blob:
        modes.append("i2i")
    if "reference-to-image" in blob:
        modes.append("i2i")
    if "text-to-video" in blob or "文生视频" in blob:
        modes.append("t2v")
    if "image-to-video" in blob or "图生视频" in blob or "reference-to-video" in blob:
        modes.append("i2v")
    if "video-edit" in blob or "编辑视频" in blob:
        modes.append("video_edit")
    if "motion-control" in blob or "动作控制" in blob:
        modes.append("motion_control")
    if "text-to-audio" in blob or "文生语音" in blob or "speech" in blob:
        modes.append("t2a")
    if "voice-clone" in blob:
        modes.append("a2a")
    if "text-to-3d" in blob:
        modes.append("t2_3d")
    if "image-to-3d" in blob:
        modes.append("i2_3d")
    return _unique_keep_order(modes)


def _infer_service_tier(title: str, summary: str) -> str:
    blob = f"{title} {summary}"
    if "官方稳定版" in blob:
        return "official_stable"
    if "低价渠道版" in blob:
        return "low_cost_channel"
    return "unknown"


def _build_index_only_api(entry: IndexEntry) -> Dict[str, Any]:
    return {
        "section": entry.section,
        "title": entry.title,
        "doc_url": entry.url,
        "summary": entry.summary,
        "category": entry.category,
        "generation_modes": entry.generation_modes,
        "service_tier": entry.service_tier,
        "detail_source": "index",
        "detail_parse_status": "index_only",
        "warning": "Index-only candidate generated from llms.txt without detail-page fetch.",
        "endpoint": None,
        "method": None,
        "sku_id": None,
        "request_fields": [],
        "response_contract": {
            "top_level_fields": [],
            "status_enum": [],
            "async_protocol": "task_submit_query",
        },
        "standard_mapping_candidates": _build_standard_mapping_candidates(entry, []),
    }


def _resolve_page_cache_file(page_cache_dir: Optional[str], entry: IndexEntry) -> Optional[Path]:
    cache_dir = str(page_cache_dir or "").strip()
    if not cache_dir:
        return None
    base_dir = Path(cache_dir)
    if not base_dir.is_absolute():
        base_dir = (ROOT / base_dir).resolve()
    api_id = _derive_api_id(entry.url)
    title_slug = _safe_slug(entry.title)
    candidates = [
        api_id,
        title_slug,
        f"{api_id}-{title_slug}" if api_id and title_slug else "",
    ]
    suffixes = [".md", ".txt", ".html"]
    for stem in candidates:
        if not stem:
            continue
        for suffix in suffixes:
            candidate = base_dir / f"{stem}{suffix}"
            if candidate.exists():
                return candidate
    return None


def _load_page_text(entry: IndexEntry, page_cache_dir: Optional[str]) -> Tuple[str, str]:
    cached = _resolve_page_cache_file(page_cache_dir, entry)
    if cached is not None:
        return cached.read_text(encoding="utf-8"), f"cache:{cached}"
    return _fetch_text(entry.url), "remote"


def parse_llms_index(text: str) -> List[IndexEntry]:
    entries: List[IndexEntry] = []
    current_section = ""
    item_re = re.compile(r"^\s*-\s*(.*?)\[(.*?)\]\((https?://[^)]+)\)\s*:\s*(.*)$")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue
        match = item_re.match(line)
        if not match:
            continue
        section = (match.group(1) or "").strip() or current_section
        title = (match.group(2) or "").strip()
        url = (match.group(3) or "").strip()
        summary = (match.group(4) or "").strip()
        if "标准模型API" not in section:
            continue
        category = _infer_category(section, title, summary, url)
        generation_modes = _infer_generation_modes(section, title, summary)
        service_tier = _infer_service_tier(title, summary)
        entries.append(
            IndexEntry(
                section=section,
                title=title,
                url=url,
                summary=summary,
                category=category,
                generation_modes=generation_modes,
                service_tier=service_tier,
            )
        )
    return entries


def _load_index_text(index_file: str) -> str:
    if index_file:
        path = Path(index_file)
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        return path.read_text(encoding="utf-8")

    fetched = _fetch_text(LLMS_TXT_URL)
    if _is_apifox_shell(fetched):
        raise RuntimeError(
            "Fetching llms.txt returned the Apifox SPA shell. Provide a browser-exported index with --index-file or use a rendered fetch pipeline."
        )
    return fetched


def _extract_yaml_block(markdown_text: str) -> str:
    match = re.search(r"```yaml\s*(.*?)```", markdown_text, flags=re.DOTALL | re.IGNORECASE)
    return (match.group(1) if match else "").strip()


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _clean_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _class_list(tag: Optional[Tag]) -> List[str]:
    if not isinstance(tag, Tag):
        return []
    return [str(value) for value in (tag.get("class") or []) if str(value).strip()]


def _has_class_prefix(tag: Optional[Tag], prefix: str) -> bool:
    return any(value.startswith(prefix) for value in _class_list(tag))


def _has_class_fragment(tag: Optional[Tag], fragment: str) -> bool:
    return any(fragment in value for value in _class_list(tag))


def _looks_like_rendered_html(text: str) -> bool:
    blob = str(text or "")
    return "<html" in blob.lower() or "JsonSchemaViewer" in blob or "request-schema-card" in blob


def _extract_endpoint(yaml_text: str) -> Tuple[Optional[str], Optional[str]]:
    lines = yaml_text.splitlines()
    in_paths = False
    path_value: Optional[str] = None
    method_value: Optional[str] = None
    path_indent: Optional[int] = None

    for raw_line in lines:
        if not raw_line.strip():
            continue
        stripped = raw_line.strip()
        indent = _leading_spaces(raw_line)
        if stripped == "paths:":
            in_paths = True
            continue
        if not in_paths:
            continue
        if indent == 0 and stripped != "paths:":
            break
        if stripped.startswith("/") and stripped.endswith(":"):
            path_value = stripped[:-1]
            path_indent = indent
            continue
        if path_value and path_indent is not None and indent == path_indent + 2 and stripped.rstrip(":") in {"get", "post", "put", "delete", "patch"}:
            method_value = stripped.rstrip(":")
            break
    return path_value, method_value


def _extract_x_sku_id(yaml_text: str) -> Optional[str]:
    match = re.search(r"^\s*x-sku-id:\s*['\"]?([^'\"\n]+)['\"]?\s*$", yaml_text, flags=re.MULTILINE)
    return (match.group(1).strip() if match else None)


def _extract_required_field_names(lines: List[str], start_index: int, end_index: int) -> List[str]:
    required: List[str] = []
    idx = start_index
    while idx < end_index:
        stripped = lines[idx].strip()
        if stripped == "required:":
            req_indent = _leading_spaces(lines[idx])
            idx += 1
            while idx < end_index:
                current = lines[idx]
                current_strip = current.strip()
                if not current_strip:
                    idx += 1
                    continue
                current_indent = _leading_spaces(current)
                if current_indent <= req_indent:
                    break
                if current_strip.startswith("-"):
                    required.append(current_strip[1:].strip().strip("'\""))
                idx += 1
            break
        idx += 1
    return _unique_keep_order(required)


def _extract_field_specs_from_request(yaml_text: str) -> List[FieldSpec]:
    lines = yaml_text.splitlines()
    request_start = None
    response_start = len(lines)
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "requestBody:":
            request_start = idx
        elif stripped == "responses:" and request_start is not None:
            response_start = idx
            break
    if request_start is None:
        return []

    properties_idx = None
    for idx in range(request_start, response_start):
        if lines[idx].strip() == "properties:":
            properties_idx = idx
            break
    if properties_idx is None:
        return []

    prop_indent = None
    fields: List[FieldSpec] = []
    idx = properties_idx + 1
    while idx < response_start:
        raw_line = lines[idx]
        stripped = raw_line.strip()
        if not stripped:
            idx += 1
            continue
        indent = _leading_spaces(raw_line)
        if indent <= _leading_spaces(lines[properties_idx]):
            break
        if stripped.endswith(":") and not stripped.startswith("-"):
            if prop_indent is None:
                prop_indent = indent
            if indent == prop_indent:
                field_name = stripped[:-1]
                block_start = idx + 1
                block_end = response_start
                probe = idx + 1
                while probe < response_start:
                    probe_line = lines[probe]
                    probe_strip = probe_line.strip()
                    if probe_strip and _leading_spaces(probe_line) == prop_indent and probe_strip.endswith(":") and not probe_strip.startswith("-"):
                        block_end = probe
                        break
                    if probe_strip and _leading_spaces(probe_line) <= _leading_spaces(lines[properties_idx]):
                        block_end = probe
                        break
                    probe += 1

                block_lines = lines[block_start:block_end]
                field_type = None
                default_value = None
                data_format = None
                description = None
                enum_values: List[str] = []
                block_idx = 0
                while block_idx < len(block_lines):
                    block_line = block_lines[block_idx]
                    block_strip = block_line.strip()
                    if block_strip.startswith("type:"):
                        field_type = block_strip.split(":", 1)[1].strip().strip("'\"")
                    elif block_strip.startswith("format:"):
                        data_format = block_strip.split(":", 1)[1].strip().strip("'\"")
                    elif block_strip.startswith("default:"):
                        default_value = block_strip.split(":", 1)[1].strip().strip("'\"")
                    elif block_strip.startswith("description:"):
                        description = block_strip.split(":", 1)[1].strip().strip("'\"")
                    elif block_strip == "enum:":
                        enum_indent = _leading_spaces(block_line)
                        block_idx += 1
                        while block_idx < len(block_lines):
                            enum_line = block_lines[block_idx]
                            enum_strip = enum_line.strip()
                            if not enum_strip:
                                block_idx += 1
                                continue
                            if _leading_spaces(enum_line) <= enum_indent:
                                block_idx -= 1
                                break
                            if enum_strip.startswith("-"):
                                enum_values.append(enum_strip[1:].strip().strip("'\""))
                            block_idx += 1
                    block_idx += 1

                fields.append(
                    FieldSpec(
                        name=field_name,
                        field_type=field_type,
                        enum_values=_unique_keep_order(enum_values),
                        default_value=default_value,
                        data_format=data_format,
                        description=description,
                    )
                )
                idx = block_end
                continue
        idx += 1

    required_names = set(_extract_required_field_names(lines, properties_idx + 1, response_start))
    for field in fields:
        field.required = field.name in required_names
    return fields


def _extract_response_fields(yaml_text: str) -> List[str]:
    lines = yaml_text.splitlines()
    response_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == "responses:":
            response_idx = idx
            break
    if response_idx is None:
        return []

    properties_idx = None
    for idx in range(response_idx, len(lines)):
        if lines[idx].strip() == "properties:":
            properties_idx = idx
            break
    if properties_idx is None:
        return []

    fields: List[str] = []
    base_indent = _leading_spaces(lines[properties_idx])
    prop_indent: Optional[int] = None
    for idx in range(properties_idx + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped:
            continue
        indent = _leading_spaces(lines[idx])
        if indent <= base_indent:
            break
        if stripped.endswith(":") and not stripped.startswith("-"):
            if prop_indent is None:
                prop_indent = indent
            if indent == prop_indent:
                fields.append(stripped[:-1])
    return _unique_keep_order(fields)


def _extract_status_enum(yaml_text: str) -> List[str]:
    match = re.search(r"status:\s*\n(?:\s+type:\s*string\s*\n)?\s*enum:\s*\n((?:\s+-\s*[^\n]+\n)+)", yaml_text, flags=re.IGNORECASE)
    if not match:
        return []
    return _unique_keep_order([item.strip().strip("'\"") for item in re.findall(r"-\s*([^\n]+)", match.group(1))])


def _extract_submit_endpoint_from_rendered_html(rendered_html: str) -> Optional[str]:
    matches = re.findall(r"(?:https?://www\.runninghub\.cn)?(/openapi/v2/[A-Za-z0-9._/\-]+)", rendered_html or "")
    preferred = []
    for match in matches:
        candidate = str(match or "").strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered.startswith("/openapi/v2/query"):
            continue
        if "/media/upload/" in lowered:
            continue
        preferred.append(candidate)
    return preferred[0] if preferred else None


def _extract_method_from_rendered_html(soup: BeautifulSoup, endpoint: Optional[str]) -> Optional[str]:
    blob = _clean_text(soup.get_text(" ", strip=True))
    if endpoint:
        endpoint_index = blob.find(endpoint)
        if endpoint_index >= 0:
            window = blob[max(0, endpoint_index - 80): endpoint_index + len(endpoint)]
            method_match = re.search(r"\b(GET|POST|PUT|DELETE|PATCH)\b", window, flags=re.IGNORECASE)
            if method_match:
                return method_match.group(1).lower()
    method_match = re.search(r"\b(GET|POST|PUT|DELETE|PATCH)\b", blob, flags=re.IGNORECASE)
    if method_match:
        return method_match.group(1).lower()
    return "post" if endpoint else None


def _find_request_schema_root(soup: BeautifulSoup) -> Optional[Tag]:
    candidates: List[Tag] = []
    for tag in soup.find_all(True):
        if _has_class_fragment(tag, "request-schema-card"):
            candidates.append(tag)
    if not candidates:
        return None
    return max(candidates, key=lambda tag: len(tag.get_text(" ", strip=True)))


def _find_field_container(property_name_node: Tag, root: Tag) -> Tag:
    container = property_name_node
    while isinstance(container.parent, Tag) and container.parent != root:
        descendant_count = len([tag for tag in container.parent.find_all(True) if _has_class_prefix(tag, "_propertyName_")])
        if descendant_count > 1:
            break
        container = container.parent
    return container


def _normalize_rendered_field_type(raw_type: str) -> Optional[str]:
    value = _clean_text(raw_type).lower()
    if not value:
        return None
    enum_match = re.match(r"enum\s*<\s*([^>]+)\s*>", value)
    if enum_match:
        return enum_match.group(1).strip()
    array_match = re.match(r"array\s*<\s*([^>]+)\s*>", value)
    if array_match:
        return "array"
    return value


def _extract_field_type_and_format(field_container: Tag, field_name: str) -> Tuple[Optional[str], Optional[str]]:
    header = field_container.find(
        lambda tag: isinstance(tag, Tag) and tag.name == "div" and "sl-text-base" in _class_list(tag) and "sl-truncate" in _class_list(tag)
    )
    if not isinstance(header, Tag):
        return None, None

    raw_type = None
    for node in header.find_all(True):
        if not _has_class_fragment(node, "sl-type"):
            continue
        text = _clean_text(node.get_text(" ", strip=True))
        if not text or text == field_name:
            continue
        if re.match(r"^(enum\s*<[^>]+>|array\s*<[^>]+>|string|integer|number|boolean|object|array)$", text, flags=re.IGNORECASE):
            raw_type = text
            break

    data_format = None
    for node in header.find_all(True):
        text = _clean_text(node.get_text(" ", strip=True))
        if text.startswith("<") and text.endswith(">"):
            data_format = text[1:-1].strip() or None
            break

    return _normalize_rendered_field_type(raw_type or ""), data_format


def _extract_field_metadata_row(field_container: Tag, key_fragment: str) -> List[str]:
    for row in field_container.find_all(
        lambda tag: isinstance(tag, Tag) and tag.name == "div" and "sl-flex" in _class_list(tag) and "sl-flex-row" in _class_list(tag)
    ):
        label_text = ""
        for label_node in row.find_all(True):
            if _has_class_prefix(label_node, "key-"):
                label_text = _clean_text(label_node.get_text(" ", strip=True))
                break
        if not label_text or key_fragment not in label_text:
            continue
        values = [_clean_text(node.get_text(" ", strip=True)) for node in row.find_all(True) if _has_class_prefix(node, "value-")]
        values = [value for value in values if value]
        return _unique_keep_order(values)
    return []


def _extract_field_description(field_container: Tag, field_name: str) -> Optional[str]:
    desc_node = field_container.find(lambda tag: isinstance(tag, Tag) and _has_class_fragment(tag, "json-schema-viewer__description"))
    if not isinstance(desc_node, Tag):
        return None
    parts = [_clean_text(text) for text in desc_node.stripped_strings]
    parts = [part for part in parts if part and part != field_name]
    return " ".join(parts) or None


def _extract_field_specs_from_rendered_html(rendered_html: str) -> List[FieldSpec]:
    soup = BeautifulSoup(rendered_html, "html.parser")
    root = _find_request_schema_root(soup)
    if not isinstance(root, Tag):
        return []

    fields: List[FieldSpec] = []
    seen_names = set()
    for property_node in root.find_all(lambda tag: isinstance(tag, Tag) and _has_class_prefix(tag, "_propertyName_")):
        field_name = _clean_text(property_node.get_text(" ", strip=True))
        if not field_name or field_name in seen_names:
            continue
        container = _find_field_container(property_node, root)
        field_type, data_format = _extract_field_type_and_format(container, field_name)
        enum_values = _extract_field_metadata_row(container, "枚举")
        default_values = _extract_field_metadata_row(container, "默认")
        if not enum_values:
            enum_values = _extract_field_metadata_row(container, "Enum")
        if not default_values:
            default_values = _extract_field_metadata_row(container, "Default")
        fields.append(
            FieldSpec(
                name=field_name,
                field_type=field_type,
                required=container.find(lambda tag: isinstance(tag, Tag) and _has_class_prefix(tag, "required-")) is not None,
                enum_values=enum_values,
                default_value=(default_values[0] if default_values else None),
                data_format=data_format,
                description=_extract_field_description(container, field_name),
            )
        )
        seen_names.add(field_name)
    return fields


def _extract_json_objects_from_rendered_html(rendered_html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(rendered_html, "html.parser")
    objects: List[Dict[str, Any]] = []
    for pre in soup.find_all("pre"):
        text = (pre.get_text("\n", strip=True) or "").strip()
        if not (text.startswith("{") and text.endswith("}")):
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if isinstance(payload, dict):
            objects.append(payload)
    return objects


def _extract_response_contract_from_rendered_html(rendered_html: str) -> Tuple[List[str], List[str]]:
    objects = _extract_json_objects_from_rendered_html(rendered_html)
    response_sample = None
    for payload in reversed(objects):
        if any(key in payload for key in ["taskId", "status", "results", "promptTips"]):
            response_sample = payload
            break
    if not isinstance(response_sample, dict):
        return [], []
    top_level_fields = _unique_keep_order([str(key).strip() for key in response_sample.keys() if str(key).strip()])
    status_enum = ["QUEUED", "RUNNING", "SUCCESS", "FAILED"] if "status" in response_sample else []
    return top_level_fields, status_enum


def _extract_sku_id_from_rendered_html(rendered_html: str) -> Optional[str]:
    patterns = [
        r'"skuId"\s*:\s*"([^"\n]+)"',
        r'"sku_id"\s*:\s*"([^"\n]+)"',
        r'x-sku-id\s*[:=]\s*["\']?([^"\'\s<]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, rendered_html or "", flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _build_standard_mapping_candidates(entry: IndexEntry, fields: List[FieldSpec]) -> List[Dict[str, Any]]:
    direct_map = {
        "prompt": "TEXT_INPUT",
        "aspectratio": "ASPECT_RATIO",
        "resolution": "RESOLUTION_TIER",
        "size": "FRAME_SIZE",
        "imagesize": "IMAGE_SIZE_CLASS",
        "duration": "DURATION_SECONDS",
        "mode": "MODE",
        "quality": "QUALITY_LEVEL",
        "outputformat": "OUTPUT_FORMAT",
        "imageurl": "REFERENCE_IMAGE_URL",
        "imageurls": "REFERENCE_IMAGE_URLS",
        "text": "TEXT_INPUT",
        "sound": "SOUND_SUPPORTED",
        "multishots": "MULTI_SHOTS_SUPPORTED",
        "voiceid": "VOICE_ID",
        "emotion": "EMOTION",
        "enablebase64output": "RETURN_BASE64",
        "englishnormalization": "ENGLISH_NORMALIZATION",
    }
    candidates: List[Dict[str, Any]] = []
    for field in fields:
        token = _normalize_token(field.name)
        mapped_dimension = direct_map.get(token)
        if not mapped_dimension:
            continue
        candidates.append(
            {
                "source_field": field.name,
                "standard_dimension": mapped_dimension,
                "confidence": "HIGH",
                "note": "runninghub_openapi_direct",
            }
        )

    if entry.generation_modes:
        candidates.append(
            {
                "source_field": "__derived_generation_mode",
                "standard_dimension": "GENERATION_MODE",
                "standard_value": entry.generation_modes[0],
                "confidence": "HIGH",
                "note": "derived_from_breadcrumb",
            }
        )
    if entry.service_tier != "unknown":
        candidates.append(
            {
                "source_field": "__derived_service_tier",
                "standard_dimension": "SERVICE_TIER",
                "standard_value": entry.service_tier,
                "confidence": "HIGH",
                "note": "derived_from_title_summary",
            }
        )
    return candidates


def _parse_single_api(entry: IndexEntry) -> Dict[str, Any]:
    return _parse_single_api_with_source(entry, None)


def _parse_single_api_with_source(entry: IndexEntry, page_cache_dir: Optional[str]) -> Dict[str, Any]:
    markdown_text, detail_source = _load_page_text(entry, page_cache_dir)
    if _is_apifox_shell(markdown_text):
        return {
            "section": entry.section,
            "title": entry.title,
            "doc_url": entry.url,
            "summary": entry.summary,
            "category": entry.category,
            "generation_modes": entry.generation_modes,
            "service_tier": entry.service_tier,
            "detail_source": detail_source,
            "detail_parse_status": "client_rendered_shell",
            "warning": "Raw HTTP fetch returned the Apifox SPA shell. Use a browser-rendered fetch or an Apifox content API for full request/response extraction.",
            "endpoint": None,
            "method": None,
            "sku_id": None,
            "request_fields": [],
            "response_contract": {
                "top_level_fields": [],
                "status_enum": [],
                "async_protocol": "task_submit_query",
            },
            "standard_mapping_candidates": _build_standard_mapping_candidates(entry, []),
        }
    yaml_text = _extract_yaml_block(markdown_text)
    endpoint = None
    method = None
    request_fields: List[FieldSpec] = []
    response_fields: List[str] = []
    status_enum: List[str] = []
    sku_id = None
    detail_parse_status = "no_yaml_found"

    if yaml_text:
        endpoint, method = _extract_endpoint(yaml_text)
        request_fields = _extract_field_specs_from_request(yaml_text)
        response_fields = _extract_response_fields(yaml_text)
        status_enum = _extract_status_enum(yaml_text)
        sku_id = _extract_x_sku_id(yaml_text)
        detail_parse_status = "parsed"
    elif _looks_like_rendered_html(markdown_text):
        soup = BeautifulSoup(markdown_text, "html.parser")
        endpoint = _extract_submit_endpoint_from_rendered_html(markdown_text)
        method = _extract_method_from_rendered_html(soup, endpoint)
        request_fields = _extract_field_specs_from_rendered_html(markdown_text)
        response_fields, status_enum = _extract_response_contract_from_rendered_html(markdown_text)
        sku_id = _extract_sku_id_from_rendered_html(markdown_text)
        if endpoint or request_fields or response_fields:
            detail_parse_status = "parsed_html"

    mapping_candidates = _build_standard_mapping_candidates(entry, request_fields)

    return {
        "section": entry.section,
        "title": entry.title,
        "doc_url": entry.url,
        "summary": entry.summary,
        "category": entry.category,
        "generation_modes": entry.generation_modes,
        "service_tier": entry.service_tier,
        "detail_source": detail_source,
        "detail_parse_status": detail_parse_status,
        "endpoint": endpoint,
        "method": method,
        "sku_id": sku_id,
        "request_fields": [asdict(field) for field in request_fields],
        "response_contract": {
            "top_level_fields": response_fields,
            "status_enum": status_enum,
            "async_protocol": "task_submit_query",
        },
        "standard_mapping_candidates": mapping_candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract RunningHub standard model OpenAPI metadata from llms.txt")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    parser.add_argument("--index-file", default="", help="Optional local llms index file captured from a browser-rendered fetch")
    parser.add_argument("--page-cache-dir", default="", help="Optional directory containing browser-rendered detail pages saved as api-id/title slug files")
    parser.add_argument("--index-only", action="store_true", help="Build an index-only snapshot without fetching detail pages")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for number of model pages to fetch")
    parser.add_argument("--category", default="", help="Optional category filter: Image, Video, Voice, Music, 3D")
    parser.add_argument("--service-tier", default="", help="Optional service tier filter: official_stable, low_cost_channel, unknown")
    args = parser.parse_args()

    output_path = Path(args.out)
    if not output_path.is_absolute():
        output_path = (ROOT / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    index_text = _load_index_text(args.index_file)
    entries = parse_llms_index(index_text)
    if args.category:
        category_filter = args.category.strip().lower()
        entries = [entry for entry in entries if entry.category.lower() == category_filter]
    if args.service_tier:
        service_tier_filter = args.service_tier.strip().lower()
        entries = [entry for entry in entries if entry.service_tier.lower() == service_tier_filter]
    if args.limit and args.limit > 0:
        entries = entries[: args.limit]

    payload = {
        "provider": "runninghub",
        "source_url": LLMS_TXT_URL,
        "generated_at": _now_iso(),
        "api_count": len(entries),
        "apis": [],
    }

    for index, entry in enumerate(entries, start=1):
        action = "indexing" if args.index_only else "fetching"
        print(f"[{index}/{len(entries)}] {action} {entry.title}")
        try:
            if args.index_only:
                payload["apis"].append(_build_index_only_api(entry))
            else:
                payload["apis"].append(_parse_single_api_with_source(entry, args.page_cache_dir))
        except Exception as exc:
            payload["apis"].append(
                {
                    **asdict(entry),
                    "error": str(exc),
                }
            )

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {output_path}")


if __name__ == "__main__":
    main()