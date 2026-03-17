import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "docs" / "runninghub_openapi_snapshot.json"
DEFAULT_FIELD_CSV = ROOT / "docs" / "runninghub_field_catalog.csv"
DEFAULT_ENUM_CSV = ROOT / "docs" / "runninghub_enum_catalog.csv"
DEFAULT_IMPORT_JSON = ROOT / "docs" / "runninghub_system_api_import_bundle.json"


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_slug(text: Any) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return re.sub(r"-+", "-", value)


def _normalize_token(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


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


def _category_output_format(category: str) -> str:
    normalized = str(category or "").strip().lower()
    if normalized == "image":
        return "image"
    if normalized == "video":
        return "video"
    if normalized in {"voice", "music"}:
        return "audio"
    if normalized == "3d":
        return "3d"
    return "text"


def _derive_api_id(url: str) -> str:
    match = re.search(r"/(api-\d+)\.md$", str(url or "").strip(), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _derive_model_slug(api: Dict[str, Any]) -> str:
    endpoint = str(api.get("endpoint") or "").strip()
    if endpoint:
        parts = [part.strip() for part in endpoint.strip("/").split("/") if part.strip()]
        if len(parts) >= 2:
            slug = _safe_slug(f"{parts[-2]}-{parts[-1]}")
            if slug:
                return slug
        tail = parts[-1].strip() if parts else ""
        slug = _safe_slug(tail)
        if slug:
            return slug

    title = str(api.get("title") or "").strip().lower()
    ascii_hint = re.sub(r"[^a-z0-9]+", "-", title).strip("-")
    ascii_hint = re.sub(r"-+", "-", ascii_hint)
    if ascii_hint:
        return ascii_hint

    api_id = _derive_api_id(str(api.get("doc_url") or ""))
    if api_id:
        return api_id
    return "runninghub-model"


def _derive_base_model(api: Dict[str, Any], model_slug: str) -> str:
    endpoint = str(api.get("endpoint") or "").strip()
    if endpoint:
        parts = [part.strip() for part in endpoint.strip("/").split("/") if part.strip()]
        if len(parts) >= 2:
            return _safe_slug(parts[-2])

    title = str(api.get("title") or "").strip()
    tokens = re.findall(r"[A-Za-z0-9.]+", title)
    if tokens:
        return tokens[0].lower()
    if "-" in model_slug:
        return model_slug.split("-", 1)[0]
    return model_slug


def _extract_enum_values(fields: List[Dict[str, Any]], target_names: List[str]) -> List[str]:
    wanted = {_normalize_token(name) for name in target_names}
    out: List[str] = []
    for field in fields:
        token = _normalize_token(field.get("name"))
        if token not in wanted:
            continue
        values = field.get("enum_values") if isinstance(field.get("enum_values"), list) else []
        out.extend([str(item).strip() for item in values if str(item).strip()])
    return _unique_keep_order(out)


def _extract_int_enum_values(fields: List[Dict[str, Any]], target_names: List[str]) -> List[int]:
    out: List[int] = []
    for value in _extract_enum_values(fields, target_names):
        try:
            out.append(int(float(value)))
        except Exception:
            continue
    return sorted(set(out))


def _build_modality(api: Dict[str, Any]) -> Dict[str, Any]:
    category = str(api.get("category") or "").strip()
    fields = api.get("request_fields") if isinstance(api.get("request_fields"), list) else []
    modality: Dict[str, Any] = {
        "generation_modes": api.get("generation_modes") if isinstance(api.get("generation_modes"), list) else [],
        "output_format": _category_output_format(category),
    }

    aspect_ratios = _extract_enum_values(fields, ["aspectRatio"])
    if aspect_ratios:
        modality["aspect_ratios"] = aspect_ratios

    supported_resolutions = _extract_enum_values(fields, ["resolution", "size"])
    if supported_resolutions:
        modality["supported_resolutions"] = supported_resolutions

    durations = _extract_int_enum_values(fields, ["duration"])
    if durations:
        modality["durations_seconds"] = durations
        modality["max_duration"] = max(durations)

    if category == "Voice":
        voice_ids = _extract_enum_values(fields, ["voice_id", "voiceId"])
        emotions = _extract_enum_values(fields, ["emotion"])
        voice_caps: Dict[str, Any] = {"supported": True, "tasks": ["tts"]}
        if voice_ids:
            voice_caps["speakers"] = voice_ids
        if emotions:
            voice_caps["emotions"] = emotions
        modality["voice_capabilities"] = voice_caps

    return {k: v for k, v in modality.items() if v not in (None, [], {}, "")}


def _build_supplier_info(snapshot: Dict[str, Any], api: Dict[str, Any], model_slug: str, base_model: str) -> Dict[str, Any]:
    source_urls = [str(snapshot.get("source_url") or "").strip(), str(api.get("doc_url") or "").strip()]
    source_urls = [item for item in source_urls if item]
    return {
        "source_urls": _unique_keep_order(source_urls),
        "runninghub": {
            "title": api.get("title"),
            "model_slug": model_slug,
            "base_model": base_model,
            "api_id": _derive_api_id(str(api.get("doc_url") or "")),
            "service_tier": api.get("service_tier"),
            "detail_parse_status": api.get("detail_parse_status"),
            "detail_source": api.get("detail_source"),
            "endpoint": api.get("endpoint"),
            "method": api.get("method"),
            "sku_id": api.get("sku_id"),
            "async_protocol": ((api.get("response_contract") or {}).get("async_protocol") if isinstance(api.get("response_contract"), dict) else None),
        },
    }


def _build_import_item(snapshot: Dict[str, Any], api: Dict[str, Any]) -> Dict[str, Any]:
    model_slug = _derive_model_slug(api)
    base_model = _derive_base_model(api, model_slug)
    modality = _build_modality(api)
    supplier_info = _build_supplier_info(snapshot, api, model_slug, base_model)
    endpoint = str(api.get("endpoint") or "").strip()
    config = {
        "deprecated": True,
        "is_deprecated": True,
        "disable_api": True,
        "provider_api_key_strategy": "random",
        "runninghub": {
            "service_tier": api.get("service_tier"),
            "detail_parse_status": api.get("detail_parse_status"),
            "detail_source": api.get("detail_source"),
            "doc_url": api.get("doc_url"),
            "sku_id": api.get("sku_id"),
            "method": api.get("method"),
        },
    }
    if endpoint:
        config["endpoint"] = endpoint

    return {
        "name": f"RunningHub {str(api.get('title') or model_slug).strip()}",
        "category": str(api.get("category") or "Tools").strip() or "Tools",
        "provider": "runninghub",
        "base_url": "https://www.runninghub.cn",
        "model": model_slug,
        "base_model": base_model,
        "modality": modality or None,
        "tags": ["runninghub", "auto-import", "deprecated-default"],
        "supplier_info": supplier_info,
        "config": config,
        "billing_unit_type": "per_call",
        "billing_cost": 0,
        "billing_cost_input": 0,
        "billing_cost_output": 0,
        "deprecated": True,
        "is_active": False,
    }


def _build_field_catalog_rows(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for api in snapshot.get("apis") or []:
        request_fields = api.get("request_fields") if isinstance(api.get("request_fields"), list) else []
        for field in request_fields:
            rows.append(
                {
                    "provider": "runninghub",
                    "api_title": api.get("title"),
                    "doc_url": api.get("doc_url"),
                    "endpoint": api.get("endpoint"),
                    "method": api.get("method"),
                    "category": api.get("category"),
                    "generation_modes": json.dumps(api.get("generation_modes") or [], ensure_ascii=False),
                    "service_tier": api.get("service_tier"),
                    "detail_parse_status": api.get("detail_parse_status"),
                    "source_field": field.get("name"),
                    "source_type": field.get("field_type"),
                    "required": bool(field.get("required")),
                    "enum_values": json.dumps(field.get("enum_values") or [], ensure_ascii=False),
                    "default_value": field.get("default_value"),
                    "format": field.get("data_format"),
                    "description": field.get("description"),
                }
            )
    return rows


def _build_enum_catalog_rows(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for api in snapshot.get("apis") or []:
        request_fields = api.get("request_fields") if isinstance(api.get("request_fields"), list) else []
        for field in request_fields:
            enum_values = field.get("enum_values") if isinstance(field.get("enum_values"), list) else []
            for order, value in enumerate(enum_values, start=1):
                rows.append(
                    {
                        "provider": "runninghub",
                        "api_title": api.get("title"),
                        "doc_url": api.get("doc_url"),
                        "category": api.get("category"),
                        "source_field": field.get("name"),
                        "enum_value": value,
                        "value_order": order,
                        "service_tier": api.get("service_tier"),
                        "detail_parse_status": api.get("detail_parse_status"),
                    }
                )

        status_enum = ((api.get("response_contract") or {}).get("status_enum") if isinstance(api.get("response_contract"), dict) else []) or []
        for order, value in enumerate(status_enum, start=1):
            rows.append(
                {
                    "provider": "runninghub",
                    "api_title": api.get("title"),
                    "doc_url": api.get("doc_url"),
                    "category": api.get("category"),
                    "source_field": "__task_status",
                    "enum_value": value,
                    "value_order": order,
                    "service_tier": api.get("service_tier"),
                    "detail_parse_status": api.get("detail_parse_status"),
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RunningHub field catalogs and deprecated import bundle from snapshot JSON")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT), help="Path to runninghub snapshot JSON")
    parser.add_argument("--field-csv", default=str(DEFAULT_FIELD_CSV), help="Output field catalog CSV")
    parser.add_argument("--enum-csv", default=str(DEFAULT_ENUM_CSV), help="Output enum catalog CSV")
    parser.add_argument("--import-json", default=str(DEFAULT_IMPORT_JSON), help="Output system api import bundle JSON")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.is_absolute():
        snapshot_path = (ROOT / snapshot_path).resolve()
    field_csv_path = Path(args.field_csv)
    if not field_csv_path.is_absolute():
        field_csv_path = (ROOT / field_csv_path).resolve()
    enum_csv_path = Path(args.enum_csv)
    if not enum_csv_path.is_absolute():
        enum_csv_path = (ROOT / enum_csv_path).resolve()
    import_json_path = Path(args.import_json)
    if not import_json_path.is_absolute():
        import_json_path = (ROOT / import_json_path).resolve()

    snapshot = _read_json(snapshot_path)
    apis = snapshot.get("apis") if isinstance(snapshot.get("apis"), list) else []

    field_rows = _build_field_catalog_rows(snapshot)
    enum_rows = _build_enum_catalog_rows(snapshot)
    import_items = [_build_import_item(snapshot, api) for api in apis]

    _write_csv(
        field_csv_path,
        field_rows,
        [
            "provider",
            "api_title",
            "doc_url",
            "endpoint",
            "method",
            "category",
            "generation_modes",
            "service_tier",
            "detail_parse_status",
            "source_field",
            "source_type",
            "required",
            "enum_values",
            "default_value",
            "format",
            "description",
        ],
    )
    _write_csv(
        enum_csv_path,
        enum_rows,
        [
            "provider",
            "api_title",
            "doc_url",
            "category",
            "source_field",
            "enum_value",
            "value_order",
            "service_tier",
            "detail_parse_status",
        ],
    )

    import_json_path.parent.mkdir(parents=True, exist_ok=True)
    import_json_path.write_text(
        json.dumps(
            {
                "replace_all": False,
                "items": import_items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"WROTE {field_csv_path}")
    print(f"WROTE {enum_csv_path}")
    print(f"WROTE {import_json_path}")
    print(f"api_count={len(apis)} field_rows={len(field_rows)} enum_rows={len(enum_rows)} import_items={len(import_items)}")


if __name__ == "__main__":
    main()