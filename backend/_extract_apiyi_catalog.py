import argparse
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "apiyi_catalog_snapshot.full_catalog.json"
MODEL_PRICING_URL = "https://api.apiyi.com/modelPricing"

DOC_URLS = {
    "model_info": "https://docs.apiyi.com/api-capabilities/model-info",
    "image_video_models": "https://docs.apiyi.com/api-capabilities/image-video-models",
    "nano_banana": "https://docs.apiyi.com/api-capabilities/nano-banana-image",
    "nano_banana_2": "https://docs.apiyi.com/api-capabilities/nano-banana-2-image",
    "flux": "https://docs.apiyi.com/api-capabilities/flux-image-generation",
    "seedream": "https://docs.apiyi.com/api-capabilities/seedream-image",
    "sora_image": "https://docs.apiyi.com/api-capabilities/sora-image-generation",
    "sora_2_reverse": "https://docs.apiyi.com/api-capabilities/sora-2-video",
    "sora_2_official": "https://docs.apiyi.com/api-capabilities/sora-2-video-official",
    "veo_overview": "https://docs.apiyi.com/api-capabilities/veo/overview",
    "gpt_image_1": "https://docs.apiyi.com/api-capabilities/gpt-image-1",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _safe_slug(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return re.sub(r"-+", "-", text)


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


def _fetch_html(url: str, timeout: int = 30) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text or ""


def _fetch_soup(url: str) -> BeautifulSoup:
    return BeautifulSoup(_fetch_html(url), "html.parser")


def _extract_float(value: str) -> Optional[float]:
    match = re.search(r"\$\s*([0-9]+(?:\.[0-9]+)?)", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _usd_to_credit(value: Optional[float]) -> int:
    if value is None:
        return 0
    return int(math.ceil(float(value) * 100.0))


def _infer_base_model(model: str) -> str:
    text = str(model or "").strip()
    if not text:
        return "unknown"
    if "/" in text:
        return text.split("/", 1)[0].strip().lower() or "unknown"
    match = re.match(r"([a-z]+)", text.lower())
    if match:
        return match.group(1)
    return _safe_slug(text) or "unknown"


def _default_category_for_model(model: str) -> str:
    token = str(model or "").lower()
    image_markers = [
        "image",
        "flux-",
        "seedream",
        "sora_image",
        "sora-image",
        "gemini-3-pro-image-preview",
        "gemini-3.1-flash-image-preview",
        "gemini-2.5-flash-image",
    ]
    video_markers = [
        "sora_video",
        "sora-2",
        "veo-",
        "veo3",
        "video",
    ]
    if any(marker in token for marker in image_markers):
        return "Image"
    if any(marker in token for marker in video_markers):
        return "Video"
    return "LLM"


def _default_endpoint_hint(category: str, model: str) -> str:
    category_norm = str(category or "").strip().lower()
    model_norm = str(model or "").strip().lower()
    if category_norm == "image":
        if model_norm in {"sora_image", "sora-image", "gpt-4o-image"}:
            return "/v1/chat/completions"
        if model_norm.startswith("gemini-") and "image" in model_norm:
            return f"/v1beta/models/{model}:generateContent"
        return "/v1/images/generations"
    if category_norm == "video":
        return "/v1/videos"
    return "/v1/chat/completions"


def _base_modality(category: str) -> Dict[str, Any]:
    category_norm = str(category or "").strip().lower()
    if category_norm == "image":
        return {"generation_modes": ["t2i"], "output_format": "image"}
    if category_norm == "video":
        return {"generation_modes": ["t2v"], "output_format": "video"}
    return {"output_format": "text"}


def _ensure_catalog_model(models_by_id: Dict[str, Dict[str, Any]], model: str) -> Dict[str, Any]:
    item = models_by_id.get(model)
    if item is not None:
        return item
    model_norm = _normalize_token(model)
    for existing_model, existing_item in models_by_id.items():
        if _normalize_token(existing_model) == model_norm:
            return existing_item
    category = _default_category_for_model(model)
    item = {
        "model": model,
        "name": model,
        "category": category,
        "base_model": _infer_base_model(model),
        "provider": "apiyi",
        "upstream_provider": None,
        "context_window": None,
        "endpoint_hint": _default_endpoint_hint(category, model),
        "modality": _base_modality(category),
        "doc_urls": [],
        "notes": [],
        "tags": [],
        "pricing": None,
        "detail_source": "heuristic",
    }
    models_by_id[model] = item
    return item


def _merge_doc_url(item: Dict[str, Any], url: str) -> None:
    urls = list(item.get("doc_urls") or [])
    if url and url not in urls:
        urls.append(url)
    item["doc_urls"] = urls


def _merge_note(item: Dict[str, Any], note: str) -> None:
    notes = list(item.get("notes") or [])
    if note and note not in notes:
        notes.append(note)
    item["notes"] = notes


def _merge_tag(item: Dict[str, Any], tag: str) -> None:
    tags = list(item.get("tags") or [])
    if tag and tag not in tags:
        tags.append(tag)
    item["tags"] = tags


def _set_pricing(item: Dict[str, Any], pricing: Dict[str, Any], *, source_priority: int) -> None:
    current = item.get("pricing") if isinstance(item.get("pricing"), dict) else None
    current_priority = int((current or {}).get("source_priority") or -1)
    if current is not None and current_priority > source_priority:
        return
    pricing_copy = dict(pricing)
    pricing_copy["source_priority"] = source_priority
    item["pricing"] = pricing_copy


def _parse_model_pricing_rows(wait_seconds: int = 8, max_pages: int = 0) -> List[Dict[str, Any]]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Edge(options=options)
    wait = WebDriverWait(driver, 20)
    rows: List[Dict[str, Any]] = []
    seen = set()

    def _extract_rows() -> List[Dict[str, Any]]:
        table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        items: List[Dict[str, Any]] = []
        for tr in table.find_elements(By.CSS_SELECTOR, "tr")[2:]:
            cells = tr.find_elements(By.CSS_SELECTOR, "td")
            if len(cells) != 8:
                continue
            model = (tr.get_attribute("data-row-key") or cells[2].text or "").strip()
            if not model:
                continue
            provider = (cells[3].text or "").strip() or None
            status = (cells[5].text or "").strip() or None
            ratio_values = [str(el.text or "").strip() for el in tr.find_elements(By.CSS_SELECTOR, "div.ModelPricingTable_ratioItem__SOO-M")]
            ratio_values = [value for value in ratio_values if value]
            price_values = [str(el.text or "").strip() for el in tr.find_elements(By.CSS_SELECTOR, "div.ModelPricingTable_priceItem__MJvgO")]
            price_values = [value for value in price_values if value]
            unit_type = "per_call"
            input_usd = None
            output_usd = None
            call_usd = None
            if price_values and all("1M token" in value or "1m token" in value.lower() for value in price_values):
                unit_type = "per_million_tokens"
                if len(price_values) >= 1:
                    input_usd = _extract_float(price_values[0])
                if len(price_values) >= 2:
                    output_usd = _extract_float(price_values[1])
            elif price_values:
                call_usd = _extract_float(price_values[0])

            items.append(
                {
                    "model": model,
                    "upstream_provider": provider,
                    "status": status,
                    "ratio_values": ratio_values,
                    "price_values": price_values,
                    "pricing": {
                        "unit_type": unit_type,
                        "input_usd": input_usd,
                        "output_usd": output_usd,
                        "call_usd": call_usd,
                        "source": MODEL_PRICING_URL,
                    },
                }
            )
        return items

    try:
        driver.get(MODEL_PRICING_URL)
        time.sleep(max(1, wait_seconds))
        page_index = 1
        while True:
            page_rows = _extract_rows()
            for row in page_rows:
                key = row["model"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)

            if max_pages and page_index >= max_pages:
                break
            next_li = driver.find_element(By.CSS_SELECTOR, "li.ant-pagination-next")
            classes = str(next_li.get_attribute("class") or "")
            if "ant-pagination-disabled" in classes:
                break

            first_model = page_rows[0]["model"] if page_rows else ""
            button = next_li.find_element(By.CSS_SELECTOR, "button")
            driver.execute_script("arguments[0].click();", button)

            def _changed(_driver: webdriver.Edge) -> bool:
                try:
                    changed_rows = _extract_rows()
                except Exception:
                    return False
                return bool(changed_rows) and changed_rows[0]["model"] != first_model

            wait.until(_changed)
            time.sleep(1)
            page_index += 1
    finally:
        driver.quit()

    return rows


def _add_model_info_context(models_by_id: Dict[str, Dict[str, Any]]) -> None:
    soup = _fetch_soup(DOC_URLS["model_info"])
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        for tr in rows[1:]:
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
            if len(cells) < 2:
                continue
            model = str(cells[1] or "").strip()
            if not model:
                continue
            item = _ensure_catalog_model(models_by_id, model)
            item["name"] = str(cells[0] or model).strip()
            if len(cells) >= 3:
                item["context_window"] = str(cells[2] or "").strip() or item.get("context_window")
            if len(cells) >= 4 and str(cells[3] or "").strip():
                _merge_note(item, str(cells[3]).strip())
            _merge_doc_url(item, DOC_URLS["model_info"])
            if item.get("detail_source") == "heuristic":
                item["detail_source"] = "docs_model_info"


def _apply_image_or_video_override(
    models_by_id: Dict[str, Dict[str, Any]],
    *,
    model: str,
    name: str,
    category: str,
    doc_url: str,
    endpoint_hint: str,
    pricing: Optional[Dict[str, Any]] = None,
    modality: Optional[Dict[str, Any]] = None,
    upstream_provider: Optional[str] = None,
    notes: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> None:
    item = _ensure_catalog_model(models_by_id, model)
    item["name"] = name
    item["category"] = category
    item["base_model"] = _infer_base_model(model)
    item["endpoint_hint"] = endpoint_hint
    item["modality"] = modality or _base_modality(category)
    if upstream_provider:
        item["upstream_provider"] = upstream_provider
    _merge_doc_url(item, doc_url)
    if notes:
        for note in notes:
            _merge_note(item, note)
    if tags:
        for tag in tags:
            _merge_tag(item, tag)
    if pricing:
        _set_pricing(item, pricing, source_priority=100)
    item["detail_source"] = "docs_detail"


def _add_nano_banana_overrides(models_by_id: Dict[str, Dict[str, Any]]) -> None:
    common_modality = {
        "generation_modes": ["t2i", "i2i"],
        "output_format": "image",
    }
    _apply_image_or_video_override(
        models_by_id,
        model="gemini-3.1-flash-image-preview",
        name="Nano Banana 2",
        category="Image",
        doc_url=DOC_URLS["nano_banana_2"],
        endpoint_hint="/v1beta/models/gemini-3.1-flash-image-preview:generateContent",
        pricing={
            "unit_type": "per_call",
            "call_usd": 0.045,
            "input_usd": 0.07,
            "output_usd": 16.8,
            "source": DOC_URLS["nano_banana_2"],
            "pricing_mode": "pay_per_request_primary",
        },
        modality={
            **common_modality,
            "supported_resolutions": ["512px", "1K", "2K", "4K"],
            "aspect_ratios": ["1:1", "1:4", "4:1", "1:8", "8:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
        },
        upstream_provider="Google",
        notes=[
            "Docs also publish alternate pay-as-you-go pricing: input $0.07/M tokens, output $16.8/M tokens.",
            "Preview status in docs; keep staging rows deprecated/inactive.",
        ],
        tags=["google", "nano-banana", "image"],
    )
    _apply_image_or_video_override(
        models_by_id,
        model="gemini-3-pro-image-preview",
        name="Nano Banana Pro",
        category="Image",
        doc_url=DOC_URLS["nano_banana"],
        endpoint_hint="/v1beta/models/gemini-3-pro-image-preview:generateContent",
        pricing={
            "unit_type": "per_call",
            "call_usd": 0.05,
            "source": DOC_URLS["nano_banana"],
        },
        modality={
            **common_modality,
            "supported_resolutions": ["1K", "2K", "4K"],
            "aspect_ratios": ["21:9", "16:9", "4:3", "3:2", "1:1", "9:16", "3:4", "2:3", "5:4", "4:5"],
        },
        upstream_provider="Google",
        tags=["google", "nano-banana", "image"],
    )
    _apply_image_or_video_override(
        models_by_id,
        model="gemini-2.5-flash-image",
        name="Nano Banana",
        category="Image",
        doc_url=DOC_URLS["nano_banana"],
        endpoint_hint="/v1/chat/completions",
        pricing={
            "unit_type": "per_call",
            "call_usd": 0.02,
            "source": DOC_URLS["nano_banana"],
        },
        modality={
            **common_modality,
            "supported_resolutions": ["1K"],
            "aspect_ratios": ["21:9", "16:9", "4:3", "3:2", "1:1", "9:16", "3:4", "2:3", "5:4", "4:5"],
        },
        upstream_provider="Google",
        tags=["google", "nano-banana", "image"],
    )


def _add_flux_overrides(models_by_id: Dict[str, Dict[str, Any]]) -> None:
    shared_modality = {
        "generation_modes": ["t2i", "i2i"],
        "output_format": "image",
        "aspect_ratio_range": "3:7_to_7:3",
        "output_formats": ["jpeg", "png"],
        "supports_seed": True,
    }
    _apply_image_or_video_override(
        models_by_id,
        model="flux-kontext-pro",
        name="Flux Kontext Pro",
        category="Image",
        doc_url=DOC_URLS["flux"],
        endpoint_hint="/v1/images/generations",
        pricing={"unit_type": "per_call", "call_usd": 0.035, "source": DOC_URLS["flux"]},
        modality=shared_modality,
        upstream_provider="Flux",
        tags=["flux", "image"],
    )
    _apply_image_or_video_override(
        models_by_id,
        model="flux-kontext-max",
        name="Flux Kontext Max",
        category="Image",
        doc_url=DOC_URLS["flux"],
        endpoint_hint="/v1/images/generations",
        pricing={"unit_type": "per_call", "call_usd": 0.07, "source": DOC_URLS["flux"]},
        modality=shared_modality,
        upstream_provider="Flux",
        tags=["flux", "image"],
    )


def _add_seedream_overrides(models_by_id: Dict[str, Dict[str, Any]]) -> None:
    shared_modality = {
        "generation_modes": ["t2i"],
        "output_format": "image",
        "supported_resolutions": ["1K", "2K", "4K", "2048x2048", "1920x1080", "3840x2160", "1080x1920", "2560x1440"],
        "quality_values": ["standard", "hd"],
    }
    _apply_image_or_video_override(
        models_by_id,
        model="seedream-4-5-251128",
        name="SeeDream 4.5",
        category="Image",
        doc_url=DOC_URLS["seedream"],
        endpoint_hint="/v1/images/generations",
        pricing={"unit_type": "per_call", "call_usd": 0.035, "source": DOC_URLS["seedream"]},
        modality=shared_modality,
        upstream_provider="BytePlus",
        notes=["Summary page shows a higher 4.5 price; detail page used as authoritative source."],
        tags=["seedream", "image", "byteplus"],
    )
    _apply_image_or_video_override(
        models_by_id,
        model="seedream-4-0-250828",
        name="SeeDream 4.0",
        category="Image",
        doc_url=DOC_URLS["seedream"],
        endpoint_hint="/v1/images/generations",
        pricing={"unit_type": "per_call", "call_usd": 0.03, "source": DOC_URLS["seedream"]},
        modality=shared_modality,
        upstream_provider="BytePlus",
        notes=["Summary page shows a higher 4.0 price; detail page used as authoritative source."],
        tags=["seedream", "image", "byteplus"],
    )


def _add_sora_image_overrides(models_by_id: Dict[str, Dict[str, Any]]) -> None:
    modality = {
        "generation_modes": ["t2i"],
        "output_format": "image",
        "aspect_ratios": ["2:3", "3:2", "1:1"],
    }
    _apply_image_or_video_override(
        models_by_id,
        model="sora_image",
        name="Sora Image",
        category="Image",
        doc_url=DOC_URLS["sora_image"],
        endpoint_hint="/v1/chat/completions",
        pricing={"unit_type": "per_call", "call_usd": 0.01, "source": DOC_URLS["sora_image"]},
        modality=modality,
        upstream_provider="OpenAI",
        tags=["sora", "image"],
    )
    _apply_image_or_video_override(
        models_by_id,
        model="gpt-4o-image",
        name="GPT-4o Image",
        category="Image",
        doc_url=DOC_URLS["sora_image"],
        endpoint_hint="/v1/chat/completions",
        pricing={"unit_type": "per_call", "call_usd": 0.01, "source": DOC_URLS["sora_image"]},
        modality=modality,
        upstream_provider="OpenAI",
        tags=["openai", "image"],
    )


def _add_gpt_image_overrides(models_by_id: Dict[str, Dict[str, Any]]) -> None:
    _apply_image_or_video_override(
        models_by_id,
        model="gpt-image-1",
        name="GPT-Image-1",
        category="Image",
        doc_url=DOC_URLS["gpt_image_1"],
        endpoint_hint="/v1/images/generations",
        pricing={
            "unit_type": "per_million_tokens",
            "input_usd": 2.5,
            "output_usd": 8.0,
            "source": DOC_URLS["gpt_image_1"],
        },
        modality={
            "generation_modes": ["t2i"],
            "output_format": "image",
            "supported_resolutions": ["1024x1024", "1536x1024", "1024x1536", "auto"],
            "quality_values": ["low", "medium", "high", "auto"],
            "output_formats": ["png", "jpeg", "webp"],
            "background_values": ["transparent", "opaque", "auto"],
        },
        upstream_provider="OpenAI",
        notes=["Docs also describe per-image charging ($0.005-$0.052/image); token pricing used for a single base billing rule."],
        tags=["openai", "image"],
    )


def _add_sora_video_reverse_overrides(models_by_id: Dict[str, Dict[str, Any]]) -> None:
    common = {
        "generation_modes": ["t2v", "i2v"],
        "output_format": "video",
        "streaming_progress": True,
    }
    reverse_rows = [
        ("sora_video2", "Sora 2 Reverse Vertical", ["720x1280"], [10]),
        ("sora_video2-landscape", "Sora 2 Reverse Landscape", ["1280x720"], [10]),
        ("sora_video2-15s", "Sora 2 Reverse Vertical 15s", ["720x1280"], [15]),
        ("sora_video2-landscape-15s", "Sora 2 Reverse Landscape 15s", ["1280x720"], [15]),
    ]
    for model, name, resolutions, durations in reverse_rows:
        _apply_image_or_video_override(
            models_by_id,
            model=model,
            name=name,
            category="Video",
            doc_url=DOC_URLS["sora_2_reverse"],
            endpoint_hint="/v1/chat/completions",
            pricing={"unit_type": "per_call", "call_usd": 0.12, "source": DOC_URLS["sora_2_reverse"]},
            modality={**common, "supported_resolutions": resolutions, "durations_seconds": durations},
            upstream_provider="OpenAI",
            tags=["sora", "video"],
        )


def _add_veo_overrides(models_by_id: Dict[str, Dict[str, Any]]) -> None:
    rows = [
        ("veo-3.1", 0.25, False, False),
        ("veo-3.1-fl", 0.25, True, False),
        ("veo-3.1-fast", 0.15, False, True),
        ("veo-3.1-fast-fl", 0.15, True, True),
        ("veo-3.1-landscape", 0.25, False, False),
        ("veo-3.1-landscape-fl", 0.25, True, False),
        ("veo-3.1-landscape-fast", 0.15, False, True),
        ("veo-3.1-landscape-fast-fl", 0.15, True, True),
    ]
    for model, price, has_frame_ref, is_fast in rows:
        resolutions = ["1280x720"] if "landscape" in model else ["720x1280"]
        notes: List[str] = []
        if has_frame_ref:
            notes.append("Supports frame-to-video mode.")
        if is_fast:
            notes.append("Fast tier documented as lower cost / lower latency.")
        _apply_image_or_video_override(
            models_by_id,
            model=model,
            name=model.upper().replace("-FL", " Frame-to-Video").replace("-FAST", " Fast"),
            category="Video",
            doc_url=DOC_URLS["veo_overview"],
            endpoint_hint="/v1/videos",
            pricing={"unit_type": "per_call", "call_usd": price, "source": DOC_URLS["veo_overview"]},
            modality={
                "generation_modes": ["i2v"] if has_frame_ref else ["t2v"],
                "output_format": "video",
                "supported_resolutions": resolutions,
                "durations_seconds": [8],
                "has_audio": True,
            },
            upstream_provider="Google",
            notes=notes,
            tags=["veo", "video"],
        )


def _build_snapshot() -> Dict[str, Any]:
    models_by_id: Dict[str, Dict[str, Any]] = {}
    pricing_rows = _parse_model_pricing_rows()
    for row in pricing_rows:
        model = row["model"]
        item = _ensure_catalog_model(models_by_id, model)
        item["upstream_provider"] = row.get("upstream_provider") or item.get("upstream_provider")
        _merge_doc_url(item, MODEL_PRICING_URL)
        if row.get("status"):
            _merge_note(item, f"Pricing page status: {row['status']}")
        price_payload = dict(row.get("pricing") or {})
        price_payload["ratio_values"] = row.get("ratio_values") or []
        _set_pricing(item, price_payload, source_priority=10)
        item["detail_source"] = "public_model_pricing"

    _add_model_info_context(models_by_id)
    _add_nano_banana_overrides(models_by_id)
    _add_flux_overrides(models_by_id)
    _add_seedream_overrides(models_by_id)
    _add_sora_image_overrides(models_by_id)
    _add_gpt_image_overrides(models_by_id)
    _add_sora_video_reverse_overrides(models_by_id)
    _add_veo_overrides(models_by_id)

    models = sorted(models_by_id.values(), key=lambda item: (str(item.get("category") or ""), str(item.get("model") or "")))
    for item in models:
        item["doc_urls"] = _unique_keep_order(list(item.get("doc_urls") or []))
        item["notes"] = _unique_keep_order(list(item.get("notes") or []))
        item["tags"] = _unique_keep_order(["apiyi", "auto-import", *list(item.get("tags") or [])])

    category_counts: Dict[str, int] = {}
    priced_counts: Dict[str, int] = {}
    for item in models:
        category = str(item.get("category") or "Unknown")
        category_counts[category] = category_counts.get(category, 0) + 1
        if isinstance(item.get("pricing"), dict):
            priced_counts[category] = priced_counts.get(category, 0) + 1

    return {
        "generated_at": _now_iso(),
        "source_urls": [MODEL_PRICING_URL, *DOC_URLS.values()],
        "public_pricing_row_count": len(pricing_rows),
        "category_counts": category_counts,
        "priced_counts": priced_counts,
        "models": models,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract APIYI public catalog and pricing into a snapshot JSON")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output snapshot JSON path")
    args = parser.parse_args()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (ROOT / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = _build_snapshot()
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {output_path}")
    print(json.dumps({
        "models": len(snapshot.get("models") or []),
        "public_pricing_rows": snapshot.get("public_pricing_row_count"),
        "category_counts": snapshot.get("category_counts"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()