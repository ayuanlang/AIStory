# -*- coding: utf-8 -*-
"""Commercial promo brief for 全局统筹 injection and single-scene lock."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.core.prompt_injection import wrap_injection_section

logger = logging.getLogger("api_logger")

PROMO_INJECTION_LABEL = "商业宣传片"
PROMO_TYPE_LABEL = "商业宣传片"
PROMO_RHYTHM = "吸睛-共鸣-价值-收口"
PROMO_SCENE_RULE = "禁止｜全剧恰好一场"
STAGE_KEYS = ("hook", "empathy", "value", "close")
STAGE_NAMES = {
    "hook": "吸睛",
    "empathy": "共鸣",
    "value": "价值",
    "close": "收口",
}
_SCENE_START_RE = re.compile(r"\[SCENE_START:", re.IGNORECASE)
_DERIVED_ENV_NAME_RE = re.compile(r"^\d+\s*度")


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    return text in {"1", "true", "yes", "y", "on", "是"}


def _string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,，;；\n]", value) if part.strip()]
    return []


FLOWER_TEXT_SPEC_FIELDS = (
    ("font", "字体"),
    ("script", "字形"),
    ("emphasis_font", "强调体"),
    ("weight", "字重"),
    ("color", "字色"),
    ("accent_color", "点缀色"),
    ("stroke", "描边"),
    ("body_size", "正文级"),
    ("emphasis_size", "收口级"),
    ("body_position", "正文位"),
    ("emphasis_position", "收口位"),
    ("align", "对齐"),
    ("max_line_chars", "单行"),
    ("en_companion", "英配"),
    ("en_size", "英级"),
    ("mid_display", "中屏展示"),
    ("product_name_layout", "产品名"),
    ("cut_fusion", "切镜融合"),
    ("cta_hold", "CTA停留"),
    ("vo_xor", "旁白优先"),
    ("glyph_lock", "逐字锁"),
    ("seal_clear", "印章不压字"),
    ("card_shot", "字卡专镜"),
    ("unity", "统一"),
)


def extract_promo_music_volume(value: Any) -> str:
    text = _text(value)
    match = re.search(r"音量=([^｜|]+)", text)
    volume = _text(match.group(1) if match else "")
    if volume in {"并重", "压过"}:
        return volume
    return "并重"


def compose_flower_text_spec_line(spec: Any) -> str:
    data = _as_dict(spec)
    if _text(data.get("spec_line")):
        return _text(data.get("spec_line"))
    parts: List[str] = []
    for key, label in FLOWER_TEXT_SPEC_FIELDS:
        value = _text(data.get(key))
        if not value:
            continue
        if key == "max_line_chars" and not value.startswith("≤") and "字" not in value:
            value = f"≤{value}字"
        parts.append(f"{label}={value}")
    return "｜".join(parts)


def _stage_source_map(stages: Any) -> Dict[str, Dict[str, Any]]:
    mapped: Dict[str, Dict[str, Any]] = {}
    if isinstance(stages, list):
        leftovers: List[Dict[str, Any]] = []
        for item in stages:
            data = _as_dict(item)
            key = _text(data.get("key"))
            if key in STAGE_KEYS:
                mapped[key] = data
            elif data:
                leftovers.append(data)
        if leftovers:
            unused = [key for key in STAGE_KEYS if key not in mapped]
            for key, data in zip(unused, leftovers):
                mapped[key] = data
        return mapped
    data = _as_dict(stages)
    for key in STAGE_KEYS:
        mapped[key] = _as_dict(data.get(key))
    return mapped


def _collect_stage_rows(stages: Any) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    mapped = _stage_source_map(stages)
    for key in STAGE_KEYS:
        row = _as_dict(mapped.get(key))
        name = _text(row.get("name")) or STAGE_NAMES[key]
        duration = _text(row.get("duration"))
        content = _text(row.get("content"))
        sensory = _text(row.get("sensory"))
        copy = _text(row.get("copy"))
        flower_text = _text(row.get("flower_text"))
        cta = _text(row.get("cta"))
        if any((duration, content, sensory, copy, flower_text, cta)):
            rows.append(
                {
                    "key": key,
                    "name": name,
                    "duration": duration,
                    "content": content,
                    "sensory": sensory,
                    "copy": copy,
                    "flower_text": flower_text,
                    "cta": cta,
                }
            )
    return rows


SOURCE_KIND_FROM_TYPE = {
    "character": "character",
    "scene": "environment",
    "environment": "environment",
    "prop": "prop",
    "product": "prop",
}
SOURCE_KIND_PREFIX = {
    "character": "CHAR",
    "environment": "ENV",
    "prop": "PROP",
}


def _normalize_source_name(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).lower()


def _is_usable_source_image_url(url: Any, media_kind: Any = "") -> bool:
    text = _text(url)
    if not text:
        return False
    kind = _text(media_kind).lower()
    if kind in {"video", "video_frame"}:
        return False
    path = text.lower().split("?", 1)[0]
    if path.endswith((".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v")):
        return False
    return True


def _source_kind_from_type(value: Any) -> str:
    raw = _text(value).lower().replace(":", "")
    if raw in {"char", "character"}:
        return "character"
    if raw in {"env", "environment", "scene"}:
        return "environment"
    if raw in {"prop", "product"}:
        return "prop"
    return SOURCE_KIND_FROM_TYPE.get(raw, "")


def _merge_source_image_row(bucket: Dict[tuple, Dict[str, Any]], *, kind: str, name: str, url: str, aliases: Any = None) -> None:
    if not kind or not _is_usable_source_image_url(url) or not _text(name):
        return
    key = (kind, _normalize_source_name(name))
    row = bucket.get(key)
    if row is None:
        row = {
            "kind": kind,
            "prefix": SOURCE_KIND_PREFIX.get(kind, "PROP"),
            "name": _text(name),
            "aliases": [],
            "urls": [],
        }
        bucket[key] = row
    alias_set = {_normalize_source_name(item) for item in row.get("aliases") or []}
    for alias in [_text(name), *(_string_list(aliases))]:
        if not alias:
            continue
        if _normalize_source_name(alias) in alias_set:
            continue
        row["aliases"].append(alias)
        alias_set.add(_normalize_source_name(alias))
    if url not in row["urls"]:
        row["urls"].append(url)


def selected_image_asset_keys(image_assets: Any) -> tuple:
    ids = set()
    urls = set()
    names = set()
    for item in image_assets if isinstance(image_assets, list) else []:
        if not isinstance(item, dict):
            continue
        image_id = _text(item.get("image_id"))
        url = _text(item.get("img_url") or item.get("file_url"))
        name = _text(item.get("object_name"))
        if image_id:
            ids.add(image_id)
        if url:
            urls.add(url)
        if name:
            names.add(name)
    return ids, urls, names


def asset_belongs_to_selection(item: Any, ids: Any, urls: Any, names: Any = None) -> bool:
    data = _as_dict(item)
    image_id = _text(data.get("image_id"))
    url = _text(data.get("img_url") or data.get("file_url"))
    name = _text(data.get("object_name") or data.get("reference_name") or data.get("name_for_script"))
    if image_id and image_id in (ids or set()):
        return True
    if url and url in (urls or set()):
        return True
    if name and name in (names or set()):
        return True
    source_ids = [_text(value) for value in (data.get("source_image_ids") or []) if _text(value)]
    if source_ids and any(source_id in (ids or set()) for source_id in source_ids):
        return True
    return False


def filter_analysis_to_selected_assets(analysis: Any, image_assets: Any) -> Dict[str, Any]:
    """Drop catalog leftovers. Project injection only sees this project's selected assets."""
    data = dict(_as_dict(analysis))
    ids, urls, names = selected_image_asset_keys(image_assets)
    original_list = [row for row in (data.get("image_list") or []) if isinstance(row, dict)]
    original_subjects = [
        subject
        for subject in (data.get("rebuild_subjects") if isinstance(data.get("rebuild_subjects"), list) else [])
        if isinstance(subject, dict) or subject
    ]
    if not ids and not urls and not names:
        data["image_list"] = []
        data["rebuild_subjects"] = []
        data["global_visual_summary"] = ""
        return data
    data["image_list"] = [
        row
        for row in original_list
        if asset_belongs_to_selection(row, ids, urls, names)
    ]
    data["rebuild_subjects"] = [
        subject
        for subject in original_subjects
        if asset_belongs_to_selection(subject, ids, urls, names)
    ]
    if len(data["image_list"]) != len(original_list) or len(data["rebuild_subjects"]) != len(original_subjects):
        data["global_visual_summary"] = ""
    return data


def build_promo_source_images(image_assets: Any = None, analysis: Any = None) -> List[Dict[str, Any]]:
    assets = [item for item in image_assets if isinstance(item, dict)] if isinstance(image_assets, list) else []
    ids, urls, names = selected_image_asset_keys(assets)
    data = filter_analysis_to_selected_assets(analysis, assets)
    image_list = [
        item
        for item in (data.get("image_list") or [])
        if isinstance(item, dict) and asset_belongs_to_selection(item, ids, urls, names)
    ]
    by_id = {_text(item.get("image_id")): item for item in assets + image_list if _text(item.get("image_id"))}
    id_to_url: Dict[str, str] = {}
    for item in assets:
        image_id = _text(item.get("image_id"))
        url = _text(item.get("img_url") or item.get("file_url"))
        if image_id and _is_usable_source_image_url(url, item.get("media_kind")):
            id_to_url[image_id] = url
    bucket: Dict[tuple, Dict[str, Any]] = {}
    for item in assets:
        url = _text(item.get("img_url") or item.get("file_url"))
        kind = _source_kind_from_type(item.get("image_type") or item.get("asset_type"))
        name = _text(item.get("object_name"))
        _merge_source_image_row(bucket, kind=kind, name=name, url=url, aliases=[item.get("object_name")])
    for row in image_list:
        image_id = _text(row.get("image_id"))
        url = _text(row.get("img_url") or id_to_url.get(image_id) or _as_dict(by_id.get(image_id)).get("img_url"))
        kind = _source_kind_from_type(row.get("image_type") or row.get("kind"))
        name = _text(row.get("object_name") or row.get("reference_name") or row.get("name_for_script"))
        _merge_source_image_row(
            bucket,
            kind=kind,
            name=name,
            url=url,
            aliases=[row.get("object_name"), row.get("reference_name"), row.get("name_for_script")],
        )
    for subject in data.get("rebuild_subjects") if isinstance(data.get("rebuild_subjects"), list) else []:
        item = _as_dict(subject)
        kind = _source_kind_from_type(item.get("kind") or item.get("image_type"))
        name = _text(item.get("name_for_script") or item.get("object_name"))
        urls: List[str] = []
        for sid in item.get("source_image_ids") if isinstance(item.get("source_image_ids"), list) else []:
            url = id_to_url.get(_text(sid)) or _text(_as_dict(by_id.get(_text(sid))).get("img_url"))
            if url:
                urls.append(url)
        if not urls:
            continue
        for url in urls:
            _merge_source_image_row(
                bucket,
                kind=kind,
                name=name,
                url=url,
                aliases=[item.get("object_name"), item.get("name_for_script")],
            )
    return [row for row in bucket.values() if row.get("urls")]


def match_promo_source_image_urls(
    name: Any,
    entity_type: Any,
    source_images: Any,
    extra_names: Any = None,
) -> List[str]:
    kind = _source_kind_from_type(entity_type)
    names = {_normalize_source_name(name)}
    for extra in extra_names if isinstance(extra_names, (list, tuple)) else []:
        token = _normalize_source_name(extra)
        if token:
            names.add(token)
    names.discard("")
    if not names:
        return []
    urls: List[str] = []
    seen = set()
    for row in source_images if isinstance(source_images, list) else []:
        item = _as_dict(row)
        row_kind = _source_kind_from_type(item.get("kind") or item.get("prefix"))
        if kind and row_kind and kind != row_kind:
            continue
        aliases = [
            item.get("name"),
            *(item.get("aliases") if isinstance(item.get("aliases"), list) else []),
        ]
        if not any(_normalize_source_name(alias) in names for alias in aliases):
            continue
        for url in item.get("urls") if isinstance(item.get("urls"), list) else []:
            text = _text(url)
            if not text or text in seen:
                continue
            seen.add(text)
            urls.append(text)
    return urls


def format_promo_source_image_lines(source_images: Any) -> str:
    lines: List[str] = []
    for row in source_images if isinstance(source_images, list) else []:
        item = _as_dict(row)
        name = _text(item.get("name"))
        prefix = _text(item.get("prefix")) or SOURCE_KIND_PREFIX.get(_source_kind_from_type(item.get("kind")), "PROP")
        urls = [_text(url) for url in (item.get("urls") if isinstance(item.get("urls"), list) else []) if _text(url)]
        if not name or not urls:
            continue
        lines.append(f"- {prefix}:{name}｜{'；'.join(urls)}")
    return "\n".join(lines)


def is_derived_environment_name(name: Any) -> bool:
    return bool(_DERIVED_ENV_NAME_RE.match(_text(name)))


def drop_promo_source_images_from_derived_env_attrs(custom_attributes: Any) -> Dict[str, Any]:
    attrs = dict(custom_attributes) if isinstance(custom_attributes, dict) else {}
    if attrs.get("source_images_overridden"):
        return attrs
    attrs.pop("source_image_urls", None)
    attrs.pop("promo_source_attached", None)
    return attrs


def attach_promo_source_images_to_attrs(
    custom_attributes: Any,
    *,
    name: Any,
    entity_type: Any,
    source_images: Any,
    extra_names: Any = None,
) -> Dict[str, Any]:
    attrs = dict(custom_attributes) if isinstance(custom_attributes, dict) else {}
    if attrs.get("source_images_overridden"):
        return attrs
    if _source_kind_from_type(entity_type) == "environment" and is_derived_environment_name(name):
        return drop_promo_source_images_from_derived_env_attrs(attrs)
    urls = match_promo_source_image_urls(name, entity_type, source_images, extra_names=extra_names)
    if not urls:
        return attrs
    existing = [_text(item) for item in (attrs.get("source_image_urls") if isinstance(attrs.get("source_image_urls"), list) else []) if _text(item)]
    merged: List[str] = []
    seen = set()
    for url in [*existing, *urls]:
        if url in seen:
            continue
        seen.add(url)
        merged.append(url)
    attrs["source_image_urls"] = merged
    attrs["promo_source_attached"] = True
    return attrs


def is_promo_project(metadata: Any) -> bool:
    info = _as_dict(metadata)
    if _positive_int(info.get("source_promo_project_id")):
        return True
    if _truthy(info.get("promo_single_scene")):
        return True
    type_blob = " ".join(
        [
            _text(info.get("type")),
            _text(info.get("kind")),
            _text(info.get("film_type")),
            _text(info.get("project_type")),
        ]
    )
    if "商业宣传片" in type_blob or type_blob.strip().lower() == "promo":
        return True
    if _text(info.get("promo_goal_type")) or _text(info.get("promo_rhythm")):
        return True
    return False


def collect_promo_brief(
    metadata: Any = None,
    planner_input: Any = None,
    planner_result: Any = None,
) -> Dict[str, Any]:
    info = _as_dict(metadata)
    incoming = _as_dict(planner_input)
    result = _as_dict(planner_result)
    enterprise = _as_dict(incoming.get("enterprise_info") or info.get("enterprise_info"))
    demand = _as_dict(incoming.get("campaign_demand") or info.get("campaign_demand"))
    overall = _as_dict(result.get("overall_scheme") or info.get("overall_scheme"))
    positioning = _as_dict(result.get("video_positioning") or info.get("video_positioning"))
    presentation = _as_dict(result.get("presentation_plan") or info.get("presentation_plan"))
    visual = _as_dict(result.get("project_visual_backfill") or info.get("project_visual_backfill"))
    preview = _as_dict(result.get("script_preview") or info.get("script_preview"))
    biz = _as_dict(result.get("structured_business_info") or info.get("structured_business_info"))
    films = result.get("benchmark_films") if isinstance(result.get("benchmark_films"), list) else []
    borrowed = visual.get("borrowed_films") if isinstance(visual.get("borrowed_films"), list) else []
    if not borrowed:
        borrowed = _string_list(info.get("borrowed_films"))
    is_source_promo = bool(
        _positive_int(info.get("source_promo_project_id"))
        or _truthy(info.get("promo_single_scene"))
        or _text(info.get("promo_goal_type"))
        or _text(info.get("promo_rhythm"))
        or "商业宣传片" in " ".join(
            [_text(info.get("type")), _text(info.get("kind")), _text(info.get("film_type"))]
        )
        or incoming
        or result
    )
    image_assets = [
        item
        for item in (enterprise.get("image_assets") if isinstance(enterprise.get("image_assets"), list) else [])
        if isinstance(item, dict) and (_text(item.get("img_url")) or _text(item.get("file_url")))
    ]
    named_asset_count = sum(
        1
        for item in image_assets
        if _text(item.get("img_url")) or _text(item.get("object_name"))
    )
    analysis = filter_analysis_to_selected_assets(
        result.get("image_asset_analysis") or info.get("image_asset_analysis"),
        image_assets,
    )
    from app.services.promo_planner import backfill_existing_material

    existing_material = backfill_existing_material(
        result.get("existing_material")
        or demand.get("existing_material")
        or info.get("promo_existing_material")
        or info.get("existing_material"),
        analysis,
        image_assets,
    )
    has_uploaded_assets = named_asset_count > 0 or bool(existing_material)
    fresh_rebuild = format_visual_rebuild_lines(analysis)
    visual_rebuild = fresh_rebuild or _text(info.get("promo_visual_rebuild"))
    source_images = build_promo_source_images(image_assets, analysis)
    if not source_images:
        source_images = [
            item
            for item in (info.get("promo_source_images") if isinstance(info.get("promo_source_images"), list) else [])
            if isinstance(item, dict)
        ]

    stage_rows = _collect_stage_rows(
        result.get("stage_plan") or info.get("promo_stage_plan") or info.get("stage_plan")
    )
    flower_spec = visual.get("flower_text_spec") if isinstance(visual.get("flower_text_spec"), dict) else {}
    if not flower_spec and isinstance(info.get("promo_flower_text_spec"), dict):
        flower_spec = info.get("promo_flower_text_spec")
    flower_spec_line = compose_flower_text_spec_line(flower_spec) or _text(info.get("promo_flower_text_spec"))
    music_rec = _text(visual.get("music_recommendation") or info.get("music_recommendation"))
    music_volume = extract_promo_music_volume(music_rec) or _text(info.get("promo_music_volume")) or "并重"

    brief = {
        "source_promo_project_id": _positive_int(
            info.get("source_promo_project_id") or result.get("source_promo_project_id")
        ),
        "type": _text(info.get("type")),
        "promo_kind": PROMO_TYPE_LABEL if is_source_promo else "",
        "promo_single_scene": True if is_source_promo else False,
        "promo_rhythm": PROMO_RHYTHM if is_source_promo else "",
        "promo_goal_type": _text(
            info.get("promo_goal_type")
            or positioning.get("goal_type")
            or demand.get("goal_type")
            or overall.get("main_goal_type")
        ),
        "promo_expect_duration": _text(
            info.get("promo_expect_duration")
            or overall.get("target_duration")
            or demand.get("expect_duration")
            or positioning.get("duration")
        ),
        "promo_duration_budget": _text(
            info.get("promo_duration_budget") or overall.get("duration_budget")
        ),
        "promo_presentation_form": _text(
            info.get("promo_presentation_form")
            or demand.get("presentation_form")
            or presentation.get("primary_form")
        ),
        "promo_one_liner": _text(
            info.get("promo_one_liner") or overall.get("one_liner") or preview.get("logline")
        ),
        "promo_visual_core": _text(
            info.get("promo_visual_core") or overall.get("visual_core")
        ),
        "promo_focus": _text(
            info.get("promo_focus") or overall.get("promo_focus")
        ),
        "promo_selling_points": _text(
            info.get("promo_selling_points") or overall.get("selling_points")
        ),
        "promo_cta": _text(
            info.get("promo_cta") or demand.get("cta") or biz.get("suggested_cta")
        ),
        "promo_enterprise": _text(
            info.get("promo_enterprise") or enterprise.get("enterprise_name")
        ),
        "promo_brand": _text(info.get("promo_brand") or enterprise.get("brand_name")),
        "promo_product": _text(info.get("promo_product") or enterprise.get("product_name") or "无"),
        "promo_target_audience": _text(
            info.get("promo_target_audience")
            or demand.get("target_audience")
            or enterprise.get("target_user")
            or biz.get("target_user")
        ),
        "Global_Style": _text(info.get("Global_Style") or info.get("global_style") or visual.get("Global_Style")),
        "style_mode": _text(info.get("style_mode") or visual.get("style_mode")),
        "tone": _text(info.get("tone") or visual.get("tone")),
        "lighting": _text(info.get("lighting") or visual.get("lighting")),
        "color_palette": _text(info.get("color_palette") or visual.get("color_palette")),
        "color_spectrum": _text(info.get("color_spectrum") or visual.get("color_spectrum")),
        "music_recommendation": music_rec,
        "promo_music_volume": music_volume,
        "promo_voiceover_style": _text(
            info.get("promo_voiceover_style") or visual.get("voiceover_style")
        ),
        "promo_sfx_style": _text(info.get("promo_sfx_style") or visual.get("sfx_style")),
        "promo_flower_text_spec": flower_spec_line,
        "borrowed_films": borrowed
        or [_text(item.get("title")) for item in films if isinstance(item, dict) and _text(item.get("title"))],
        "promo_stage_plan": stage_rows,
        "promo_has_uploaded_assets": has_uploaded_assets,
        "promo_named_asset_count": named_asset_count,
        "promo_asset_strategy": (
            "有上传素材：已有素材不作场面约束，只作家形参考；入镜外形只抄已有素材资源描述；效果优先，可新起宏观大场面与精密特写（AI生成）。"
            if has_uploaded_assets
            else "无上传素材：按剧本新构思抽取 CHAR/PROP/ENV，效果优先，宏观大场面与精密拍摄走AI生成，禁止因无图停抽或空剧情。"
        ),
        "promo_visual_rebuild": visual_rebuild,
        "promo_existing_material": existing_material,
        "image_asset_analysis": analysis,
        "promo_source_images": source_images,
    }
    return brief


def apply_promo_fields_to_global_info(current: Any, brief: Any) -> Dict[str, Any]:
    payload = dict(current) if isinstance(current, dict) else {}
    data = collect_promo_brief(payload, planner_result=None) if not brief else dict(brief)
    user_type = _text(payload.get("type") or data.get("type"))
    if user_type and user_type != PROMO_TYPE_LABEL:
        payload["type"] = user_type
    payload["source_promo_project_id"] = _positive_int(
        data.get("source_promo_project_id") or payload.get("source_promo_project_id")
    )
    payload["promo_single_scene"] = True
    payload["promo_rhythm"] = PROMO_RHYTHM
    copy_keys = (
        "promo_goal_type",
        "promo_expect_duration",
        "promo_duration_budget",
        "promo_presentation_form",
        "promo_one_liner",
        "promo_visual_core",
        "promo_focus",
        "promo_selling_points",
        "promo_cta",
        "promo_enterprise",
        "promo_brand",
        "promo_product",
        "promo_target_audience",
        "promo_voiceover_style",
        "promo_sfx_style",
        "promo_flower_text_spec",
        "promo_music_volume",
        "promo_asset_strategy",
        "promo_visual_rebuild",
        "promo_existing_material",
    )
    overwrite_keys = {
        "promo_asset_strategy",
        "promo_visual_rebuild",
        "promo_existing_material",
        "promo_flower_text_spec",
        "promo_music_volume",
    }
    for key in copy_keys:
        value = _text(data.get(key))
        if not value:
            continue
        if key in overwrite_keys or not _text(payload.get(key)):
            payload[key] = value
    analysis = data.get("image_asset_analysis")
    if isinstance(analysis, dict) and analysis:
        payload["image_asset_analysis"] = analysis
    inherit_keys = (
        "Global_Style",
        "style_mode",
        "tone",
        "lighting",
        "color_palette",
        "color_spectrum",
        "music_recommendation",
    )
    for key in inherit_keys:
        value = _text(data.get(key))
        if not value:
            continue
        if key == "music_recommendation" or not _text(payload.get(key)):
            payload[key] = value
    films = data.get("borrowed_films") if isinstance(data.get("borrowed_films"), list) else []
    if films and not _string_list(payload.get("borrowed_films")):
        payload["borrowed_films"] = films
    stages = data.get("promo_stage_plan") if isinstance(data.get("promo_stage_plan"), list) else []
    if stages:
        payload["promo_stage_plan"] = stages
    sources = data.get("promo_source_images") if isinstance(data.get("promo_source_images"), list) else []
    if sources:
        payload["promo_source_images"] = [item for item in sources if isinstance(item, dict)]
    return payload


KIND_PREFIX = {
    "character": "CHAR",
    "prop": "PROP",
    "product": "PROP",
    "environment": "ENV",
    "scene": "ENV",
}
_EMPTY_VISUAL = frozenset({"", "无", "未见", "none", "n/a", "null"})


def _visual_clause(value: Any) -> str:
    text = _text(value)
    if not text or text.lower() in _EMPTY_VISUAL or text.startswith("识别失败"):
        return ""
    return text


def merge_visual_text(*parts: Any) -> str:
    out: List[str] = []
    for part in parts:
        if isinstance(part, (list, tuple)):
            text = merge_visual_text(*part)
        else:
            text = _visual_clause(part)
        if not text:
            continue
        if any(text == existing or text in existing for existing in out):
            continue
        out = [existing for existing in out if existing not in text]
        out.append(text)
    return "；".join(out)


def _kind_from_image_type(image_type: Any) -> str:
    return {
        "character": "character",
        "scene": "environment",
        "environment": "environment",
        "prop": "prop",
        "product": "product",
    }.get(_text(image_type).lower(), "prop")


def _asset_media_type(row: Any) -> str:
    raw = _text(_as_dict(row).get("image_type")).lower()
    mapping = {
        "scene": "scene",
        "environment": "scene",
        "场景": "scene",
        "环境": "scene",
        "character": "character",
        "角色": "character",
        "prop": "prop",
        "道具": "prop",
        "product": "product",
        "产品": "product",
    }
    return mapping.get(raw, raw or "product")


def _sanitize_scene_image_row(row: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(row)
    if _asset_media_type(item) != "scene":
        return item
    item["character_detail"] = "无"
    item["prop_detail"] = "无"
    name = _text(item.get("object_name") or item.get("reference_name"))
    subjects = item.get("subjects_in_frame") if isinstance(item.get("subjects_in_frame"), list) else []
    kept = [_text(x) for x in subjects if _text(x) and _text(x) == name]
    item["subjects_in_frame"] = kept or ([name] if name else [])
    return item


def _subject_kind_key(item: Dict[str, Any]) -> str:
    kind = _text(item.get("kind")).lower()
    if kind in {"environment", "scene"}:
        return "environment"
    if kind in {"character"}:
        return "character"
    if kind in {"product"}:
        return "product"
    return "prop"


def _subject_has_typed_upload(item: Dict[str, Any], image_list: List[Dict[str, Any]]) -> bool:
    kind = _subject_kind_key(item)
    if kind == "environment":
        return True
    if not image_list:
        return True
    if not any(_asset_media_type(row) == "scene" for row in image_list):
        return True
    names = {
        _text(item.get("object_name")),
        _text(item.get("name_for_script")),
        _text(item.get("reference_name")),
    }
    names.discard("")
    ids = {_text(x) for x in (item.get("source_image_ids") or []) if _text(x)}
    for row in image_list:
        row_type = _asset_media_type(row)
        if row_type == "scene":
            continue
        row_id = _text(row.get("image_id"))
        row_name = _text(row.get("object_name") or row.get("reference_name"))
        id_hit = bool(row_id and row_id in ids)
        name_hit = bool(row_name and row_name in names)
        if not (id_hit or name_hit):
            continue
        if kind == "character" and row_type == "character":
            return True
        if kind in {"prop", "product"} and row_type in {"prop", "product"}:
            return True
    return False


def _matching_image_rows(item: Dict[str, Any], image_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    name = _text(item.get("name_for_script") or item.get("object_name"))
    ids = {_text(x) for x in (item.get("source_image_ids") or []) if _text(x)}
    kind = _subject_kind_key(item)
    matches: List[Dict[str, Any]] = []
    for row in image_list:
        row_id = _text(row.get("image_id"))
        row_name = _text(row.get("object_name") or row.get("reference_name"))
        subjects = row.get("subjects_in_frame") if isinstance(row.get("subjects_in_frame"), list) else []
        subject_names = {_text(x) for x in subjects if _text(x)}
        if (ids and row_id in ids) or (name and name == row_name) or (name and name in subject_names):
            if kind in {"character", "prop", "product"} and _asset_media_type(row) == "scene":
                continue
            matches.append(row)
    return matches


def _rebuild_slot_pairs(item: Dict[str, Any]) -> List[tuple]:
    kind = _text(item.get("kind")).lower()
    prefix = KIND_PREFIX.get(kind, "PROP")
    remark = _visual_clause(item.get("user_remark"))
    appearance = _visual_clause(item.get("appearance"))
    brief = _visual_clause(item.get("rebuild_brief"))
    if brief and "｜" not in brief and brief not in (appearance or ""):
        appearance = merge_visual_text(appearance, brief)
    clothing = _visual_clause(item.get("clothing_or_material"))
    color = _visual_clause(item.get("color_and_markings"))
    scale = _visual_clause(item.get("scale_and_shape"))
    space = _visual_clause(item.get("space_layout"))
    lighting = _visual_clause(item.get("lighting"))
    motion = _visual_clause(item.get("motion_from_video"))
    style = _visual_clause(item.get("style_desc"))
    composition = _visual_clause(item.get("composition"))
    do_not = _visual_clause(item.get("do_not_invent"))
    pairs: List[tuple] = []
    if remark:
        pairs.append(("说明", remark))
    if prefix == "CHAR":
        pairs.append(("外形", appearance or "未见"))
        pairs.append(("衣着", clothing or "未见"))
        if lighting:
            pairs.append(("光色", lighting))
    elif prefix == "ENV":
        pairs.append(("空间", space or appearance or "未见"))
        pairs.append(("光色", lighting or "未见"))
        if appearance and appearance != space:
            pairs.append(("外形", appearance))
        elif not space:
            pairs.append(("外形", appearance or "未见"))
    else:
        pairs.append(("外形", appearance or "未见"))
        pairs.append(("材质", clothing or "未见"))
        pairs.append(("形态", scale or "未见"))
        pairs.append(("标识", color or "未见"))
        if lighting:
            pairs.append(("光色", lighting))
    if motion:
        pairs.append(("动作", motion))
    if style:
        pairs.append(("风格", style))
    if composition:
        pairs.append(("构图", composition))
    if do_not:
        pairs.append(("未见禁补", do_not))
    return pairs


def compose_rebuild_brief(item: Dict[str, Any]) -> str:
    pairs = _rebuild_slot_pairs(item)
    composed = "｜".join(f"{key}={value}" for key, value in pairs)
    current = _visual_clause(item.get("rebuild_brief"))
    if current and "｜" in current and len(current) > len(composed):
        return current
    return composed


def compose_visual_rebuild_line(item: Dict[str, Any]) -> str:
    name = _text(item.get("name_for_script") or item.get("object_name"))
    if not name:
        return ""
    prefix = KIND_PREFIX.get(_text(item.get("kind")).lower(), "PROP")
    return f"{prefix}:{name}｜{compose_rebuild_brief(item)}"


def fatten_rebuild_subject(item: Dict[str, Any], matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    kind = _text(item.get("kind")).lower()
    remark = merge_visual_text(item.get("user_remark"), *[row.get("user_remark") for row in matches])
    if remark:
        item["user_remark"] = remark
    style = merge_visual_text(item.get("style_desc"), *[row.get("style_desc") for row in matches])
    if style:
        item["style_desc"] = style
    composition = merge_visual_text(item.get("composition"), *[row.get("composition") for row in matches])
    if composition:
        item["composition"] = composition
    char_detail = merge_visual_text(*[row.get("character_detail") for row in matches])
    prop_detail = merge_visual_text(*[row.get("prop_detail") for row in matches])
    env_detail = merge_visual_text(*[row.get("environment_detail") for row in matches])
    content_desc = merge_visual_text(*[row.get("content_desc") for row in matches])
    own_brief = item.get("rebuild_brief") if "｜" not in _text(item.get("rebuild_brief")) else ""
    row_brief = merge_visual_text(
        *[row.get("rebuild_brief") for row in matches if "｜" not in _text(row.get("rebuild_brief"))]
    )
    lighting = merge_visual_text(item.get("lighting"), *[row.get("light_info") for row in matches])
    motion = merge_visual_text(item.get("motion_from_video"), *[row.get("video_motion") for row in matches])
    if kind == "character":
        item["appearance"] = merge_visual_text(item.get("appearance"), char_detail, own_brief, row_brief)
        item["clothing_or_material"] = merge_visual_text(item.get("clothing_or_material"))
        if not _visual_clause(item.get("clothing_or_material")) and char_detail and char_detail != _visual_clause(item.get("appearance")):
            item["clothing_or_material"] = char_detail
    elif kind in {"environment", "scene"}:
        item["space_layout"] = merge_visual_text(item.get("space_layout"), env_detail)
        item["appearance"] = merge_visual_text(item.get("appearance"), own_brief, row_brief, content_desc)
        if not _visual_clause(item.get("appearance")):
            item["appearance"] = _visual_clause(item.get("space_layout"))
        item["kind"] = "environment"
    else:
        item["appearance"] = merge_visual_text(item.get("appearance"), prop_detail, own_brief, row_brief, content_desc)
        item["clothing_or_material"] = merge_visual_text(item.get("clothing_or_material"))
        if not _visual_clause(item.get("clothing_or_material")):
            item["clothing_or_material"] = prop_detail
    if lighting:
        item["lighting"] = lighting
    if motion:
        item["motion_from_video"] = motion
    item["rebuild_brief"] = compose_rebuild_brief(item)
    return item


def _subject_from_image_row(row: Dict[str, Any]) -> Dict[str, Any]:
    name = _text(row.get("object_name") or row.get("reference_name"))
    kind = _kind_from_image_type(row.get("image_type"))
    item = {
        "kind": kind,
        "object_name": name,
        "source_image_ids": [_text(row.get("image_id"))] if _text(row.get("image_id")) else [],
        "name_for_script": name,
        "rebuild_brief": _text(row.get("rebuild_brief")),
        "appearance": "",
        "clothing_or_material": "",
        "color_and_markings": "",
        "scale_and_shape": "",
        "space_layout": _text(row.get("environment_detail")) if kind == "environment" else "无",
        "lighting": _text(row.get("light_info")),
        "motion_from_video": _text(row.get("video_motion")) or "无",
        "do_not_invent": "未见处禁止补造",
        "user_remark": _text(row.get("user_remark")),
        "style_desc": _text(row.get("style_desc")),
        "composition": _text(row.get("composition")),
    }
    return fatten_rebuild_subject(item, [row])


_WATERMARK_KEEP_KEYS = {
    "image_id",
    "object_name",
    "reference_name",
    "name_for_script",
    "user_remark",
    "image_type",
    "media_kind",
    "kind",
    "source_image_ids",
}
_WATERMARK_CLAUSE_RE = re.compile(
    r"水印|watermark|shutterstock|getty(?:\s*images)?|istock(?:photo)?|"
    r"adobe\s*stock|unsplash|pexels|pixabay|depositphotos|123rf|dreamstime|"
    r"preview\s*only|sample\s*image|fotolia|alamy",
    re.IGNORECASE,
)
_WATERMARK_SPLIT_RE = re.compile(r"([。！？；;｜|\n]+|，|,|、)")


def _is_watermark_clause(text: Any) -> bool:
    blob = _text(text)
    if not blob:
        return False
    if "水印纹" in blob or "水印纸" in blob:
        return False
    return bool(_WATERMARK_CLAUSE_RE.search(blob))


def strip_visual_watermark_text(value: Any) -> str:
    text = _text(value)
    if not text or not _WATERMARK_CLAUSE_RE.search(text):
        return text
    parts = _WATERMARK_SPLIT_RE.split(text)
    kept: List[str] = []
    pending_delim = ""
    for part in parts:
        if not part:
            continue
        if _WATERMARK_SPLIT_RE.fullmatch(part):
            if kept:
                pending_delim = part
            continue
        if _is_watermark_clause(part):
            pending_delim = ""
            continue
        if pending_delim and kept:
            kept.append(pending_delim)
        pending_delim = ""
        kept.append(part)
    return re.sub(r"[，,、；;｜|\s]+$", "", "".join(kept)).strip(" ，,;；|｜、")


def _strip_analysis_value(value: Any) -> Any:
    if isinstance(value, str):
        return strip_visual_watermark_text(value)
    if isinstance(value, list):
        cleaned = []
        for item in value:
            if isinstance(item, str):
                text = strip_visual_watermark_text(item)
                if text:
                    cleaned.append(text)
            elif isinstance(item, dict):
                cleaned.append(_strip_analysis_node(item))
            else:
                cleaned.append(item)
        return cleaned
    if isinstance(value, dict):
        return _strip_analysis_node(value)
    return value


def _strip_analysis_node(node: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(node)
    for key, value in list(out.items()):
        if key in _WATERMARK_KEEP_KEYS:
            continue
        out[key] = _strip_analysis_value(value)
    return out


def strip_analysis_watermarks(analysis: Any) -> Dict[str, Any]:
    return _strip_analysis_node(_as_dict(analysis))


def enrich_rebuild_analysis(analysis: Any) -> Dict[str, Any]:
    data = strip_analysis_watermarks(analysis)
    image_list = [
        _sanitize_scene_image_row(_as_dict(row))
        for row in data.get("image_list") or []
        if isinstance(row, dict)
    ]
    data["image_list"] = image_list
    cleaned: List[Dict[str, Any]] = []
    seen = set()
    for row in data.get("rebuild_subjects") if isinstance(data.get("rebuild_subjects"), list) else []:
        item = _as_dict(row)
        name = _text(item.get("object_name") or item.get("name_for_script"))
        if not name:
            continue
        if not _subject_has_typed_upload(item, image_list):
            continue
        kind = _text(item.get("kind")) or "prop"
        key = (kind.lower(), name)
        if key in seen:
            continue
        seen.add(key)
        item["object_name"] = name
        item["name_for_script"] = _text(item.get("name_for_script")) or name
        item["kind"] = kind
        cleaned.append(fatten_rebuild_subject(item, _matching_image_rows(item, image_list)))
    for row in image_list:
        name = _text(row.get("object_name") or row.get("reference_name"))
        if not name:
            continue
        kind = _kind_from_image_type(row.get("image_type"))
        key = (kind, name)
        alt_key = ("environment", name) if kind == "environment" else key
        if key in seen or alt_key in seen:
            continue
        brief = merge_visual_text(
            row.get("rebuild_brief"),
            row.get("environment_detail"),
            row.get("prop_detail"),
            row.get("character_detail"),
            row.get("content_desc"),
        )
        if not brief:
            continue
        seen.add(key)
        cleaned.append(_subject_from_image_row(row))
    data["rebuild_subjects"] = cleaned
    return data


def format_visual_rebuild_lines(analysis: Any) -> str:
    data = enrich_rebuild_analysis(analysis)
    lines: List[str] = []
    seen = set()
    for row in data.get("rebuild_subjects") if isinstance(data.get("rebuild_subjects"), list) else []:
        item = _as_dict(row)
        line = compose_visual_rebuild_line(item)
        if not line:
            continue
        prefix = KIND_PREFIX.get(_text(item.get("kind")).lower(), "PROP")
        name = _text(item.get("name_for_script") or item.get("object_name"))
        key = f"{prefix}:{name}"
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    return "\n".join(f"- {line}" for line in lines if _text(line))


def format_promo_injection_body(brief: Any) -> str:
    raw = _as_dict(brief)
    data = raw if raw.get("promo_rhythm") or raw.get("promo_single_scene") else collect_promo_brief(raw)
    if not is_promo_project(data):
        return ""
    lines = [
        "片种=商业宣传片",
    ]
    user_type = _text(data.get("type"))
    if user_type and user_type != PROMO_TYPE_LABEL:
        lines.append(f"类型={user_type}")
    lines.extend([
        f"切场={PROMO_SCENE_RULE}",
        f"节奏={PROMO_RHYTHM}",
        "四段=场内节拍，不是四场。跨空间/跨时段仍包在同一场。",
        "花字闸=有旁白时不出花字，花字低于旁白，禁同步以免分心；只挂无声开镜/段末/黑屏专镜/字卡专镜。含「X家」须逐字见家，禁漏家、禁复写邻字、禁何乐乐享。印章不压字：印=句外旁侧｜压字=禁｜替字=禁。店号/品牌/热线走字卡专镜：场景底+字层由后期libass按引号逐字烧录（烧录=libass｜手写=禁），场景底只出画面，禁止视频模型描字；印章另层不进字盒；字卡不是CHAR/PROP/ENV。企业素材产品出镜须花字=产品名，位置=画右|画左｜排向=竖，挂无声切镜。",
        f"素材策略={_text(data.get('promo_asset_strategy')) or '无上传素材时按剧本新构思抽取角色/道具/环境，后续补充或由AI生成。'}",
    ])
    material = _text(data.get("promo_existing_material"))
    if material:
        lines.append("已有素材资源描述=")
        lines.append(material)
        lines.append("抽取外形必须逐字抄已有素材资源描述，禁止另起近义，禁止使用未写入该段的主体库素材。")
    source_lines = format_promo_source_image_lines(data.get("promo_source_images"))
    if source_lines:
        lines.append("素材依赖图=")
        lines.append(source_lines)
        lines.append("名称对上的场景/道具/角色生图必须把对应链接当依赖图片，禁止丢掉。")
    pairs = (
        ("核心诉求", data.get("promo_goal_type")),
        ("预期时长", data.get("promo_expect_duration")),
        ("时长分配", data.get("promo_duration_budget")),
        ("表现形式", data.get("promo_presentation_form")),
        ("一句话策略", data.get("promo_one_liner")),
        ("宣传要点", data.get("promo_focus")),
        ("主要卖点", data.get("promo_selling_points")),
        ("画面核", data.get("promo_visual_core")),
        ("企业", data.get("promo_enterprise")),
        ("品牌", data.get("promo_brand")),
        ("产品", data.get("promo_product")),
        ("目标客群", data.get("promo_target_audience")),
        ("CTA", data.get("promo_cta")),
        ("Global_Style", data.get("Global_Style")),
        ("style_mode", data.get("style_mode")),
        ("tone", data.get("tone")),
        ("lighting", data.get("lighting")),
        ("color_palette", data.get("color_palette")),
        ("color_spectrum", data.get("color_spectrum")),
        ("music_recommendation", data.get("music_recommendation")),
        ("配乐音量", data.get("promo_music_volume")),
        ("配音", data.get("promo_voiceover_style")),
        ("音效", data.get("promo_sfx_style")),
        ("花字规范", data.get("promo_flower_text_spec")),
    )
    for label, value in pairs:
        text = _text(value)
        if text:
            lines.append(f"{label}={text}")
    films = data.get("borrowed_films") if isinstance(data.get("borrowed_films"), list) else []
    if films:
        lines.append(f"对标片={'；'.join(_text(item) for item in films if _text(item))}")
    stages = data.get("promo_stage_plan") if isinstance(data.get("promo_stage_plan"), list) else []
    if stages:
        lines.append("四段规划=")
        for row in stages:
            item = _as_dict(row)
            name = _text(item.get("name")) or STAGE_NAMES.get(_text(item.get("key")), "段")
            duration = _text(item.get("duration"))
            content = _text(item.get("content"))
            sensory = _text(item.get("sensory"))
            copy = _text(item.get("copy"))
            flower_text = _text(item.get("flower_text"))
            cta = _text(item.get("cta"))
            detail = "｜".join(
                part
                for part in (
                    f"{name}（{duration}）" if duration else name,
                    f"内容={content}" if content else "",
                    f"感官={sensory}" if sensory else "",
                    f"文案={copy}" if copy else "",
                    f"花字={flower_text}" if flower_text else "",
                    f"CTA={cta}" if cta else "",
                )
                if part
            )
            lines.append(f"- {detail}")
    return "\n".join(lines).strip()


def build_promo_injection_section(brief: Any) -> str:
    body = format_promo_injection_body(brief)
    if not body:
        return ""
    return wrap_injection_section(PROMO_INJECTION_LABEL, body)


def user_content_has_promo_injection(text: Any) -> bool:
    source = str(text or "")
    return f"[{PROMO_INJECTION_LABEL}开始]" in source or "片种=商业宣传片" in source


def count_scene_starts(text: Any) -> int:
    return len(_SCENE_START_RE.findall(str(text or "")))


def promo_scene_split_is_valid(result_text: Any, metadata: Any) -> bool:
    if not is_promo_project(metadata):
        return True
    return count_scene_starts(result_text) == 1


def resolve_promo_brief(
    db: Any = None,
    metadata: Any = None,
    *,
    project_id: Optional[int] = None,
) -> Dict[str, Any]:
    info = _as_dict(metadata)
    if not is_promo_project(info):
        return {}
    brief = collect_promo_brief(info)
    promo_id = _positive_int(brief.get("source_promo_project_id") or info.get("source_promo_project_id"))
    if not promo_id or db is None:
        return brief
    try:
        from app.services.promo_planner import load_planner_state, rebind_promo_project

        project = rebind_promo_project(db, project_id=promo_id)
        state = load_planner_state(db, project)
        return collect_promo_brief(
            {
                **info,
                "source_promo_project_id": promo_id,
            },
            state.get("promo_planner_input"),
            state.get("promo_planner_result"),
        )
    except Exception as exc:
        logger.warning("[promo_context] failed to enrich promo brief from project %s: %s", promo_id, exc)
        return brief
