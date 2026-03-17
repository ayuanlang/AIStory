import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "docs" / "apiyi_catalog_snapshot.full_catalog.json"
DEFAULT_IMPORT_JSON = ROOT / "docs" / "apiyi_system_api_import_bundle.full_catalog.json"
DEFAULT_BILLING_JSON = ROOT / "docs" / "apiyi_system_api_billing_bundle.full_catalog.json"
DEFAULT_REVIEW_MD = ROOT / "docs" / "apiyi_import_readiness_review_20260317.md"


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _credit(value: Any) -> int:
    try:
        numeric = float(value)
    except Exception:
        return 0
    return int(math.ceil(max(0.0, numeric) * 100.0))


def _is_runtime_ready_subset(model: Dict[str, Any]) -> bool:
    return False


def _build_import_item(model: Dict[str, Any]) -> Dict[str, Any]:
    category = str(model.get("category") or "LLM")
    endpoint_hint = str(model.get("endpoint_hint") or "").strip() or None
    runtime_ready = _is_runtime_ready_subset(model)
    supplier_info = {
        "source_urls": list(model.get("doc_urls") or []),
        "apiyi": {
            "upstream_provider": model.get("upstream_provider"),
            "endpoint_hint": endpoint_hint,
            "detail_source": model.get("detail_source"),
            "pricing": model.get("pricing"),
            "notes": list(model.get("notes") or []),
        },
    }
    config = {
        "provider_api_key_strategy": "random",
        "endpoint_hint": endpoint_hint,
        "apiyi": {
            "upstream_provider": model.get("upstream_provider"),
            "detail_source": model.get("detail_source"),
            "pricing_source": ((model.get("pricing") or {}).get("source") if isinstance(model.get("pricing"), dict) else None),
        },
    }
    if runtime_ready and endpoint_hint:
        config["endpoint"] = endpoint_hint
        if category == "Image":
            config["runtime_activation"] = "image_openai_compatible"
        elif category == "Video":
            config["runtime_activation"] = "video_openai_compatible"
    else:
        config["deprecated"] = True
        config["is_deprecated"] = True
        config["disable_api"] = True
    pricing = model.get("pricing") if isinstance(model.get("pricing"), dict) else {}
    return {
        "name": f"APIYI {str(model.get('name') or model.get('model') or 'Model').strip()}",
        "category": category,
        "provider": "apiyi",
        "base_url": "https://api.apiyi.com",
        "model": model.get("model"),
        "base_model": model.get("base_model"),
        "modality": model.get("modality") or None,
        "tags": list(model.get("tags") or []),
        "supplier_info": supplier_info,
        "config": config,
        "billing_unit_type": pricing.get("unit_type"),
        "billing_cost": _credit(pricing.get("call_usd")),
        "billing_cost_input": _credit(pricing.get("input_usd")),
        "billing_cost_output": _credit(pricing.get("output_usd")),
        "deprecated": (not runtime_ready),
        "is_active": False,
    }


def _build_billing_item(model: Dict[str, Any]) -> Dict[str, Any]:
    pricing = model.get("pricing") if isinstance(model.get("pricing"), dict) else {}
    unit_type = str(pricing.get("unit_type") or "").strip()
    return {
        "provider": "apiyi",
        "category": model.get("category"),
        "model": model.get("model"),
        "name": f"APIYI {str(model.get('name') or model.get('model') or 'Model').strip()} Base Pricing",
        "billing_unit_type": unit_type,
        "billing_cost": _credit(pricing.get("call_usd")),
        "billing_cost_input": _credit(pricing.get("input_usd")),
        "billing_cost_output": _credit(pricing.get("output_usd")),
        "charge_multiplier": 1.0,
        "source_url": pricing.get("source"),
        "notes": list(model.get("notes") or []),
    }


def _render_review(snapshot: Dict[str, Any], import_items: List[Dict[str, Any]], billing_items: List[Dict[str, Any]]) -> str:
    category_counts = snapshot.get("category_counts") or {}
    priced_counts = snapshot.get("priced_counts") or {}
    public_rows = int(snapshot.get("public_pricing_row_count") or 0)
    docs_only = [item for item in import_items if not any(url == "https://api.apiyi.com/modelPricing" for url in ((item.get("supplier_info") or {}).get("source_urls") or []))]
    token_rules = [item for item in billing_items if item.get("billing_unit_type") == "per_million_tokens"]
    call_rules = [item for item in billing_items if item.get("billing_unit_type") == "per_call"]
    second_rules = [item for item in billing_items if item.get("billing_unit_type") == "per_second"]
    unresolved = [item for item in import_items if not str(item.get("billing_unit_type") or "").strip()]

    lines = [
        "# APIYI Import Readiness Review",
        "",
        f"Generated at: {snapshot.get('generated_at')}",
        "",
        "## Extraction Coverage",
        "",
        f"- Public `modelPricing` rows scraped: {public_rows}",
        f"- Catalog models after docs merge: {len(import_items)}",
        f"- Docs-only models added beyond public pricing: {len(docs_only)}",
        "",
        "## Category Counts",
        "",
    ]
    for category in sorted(category_counts):
        lines.append(f"- {category}: {category_counts[category]} models ({priced_counts.get(category, 0)} priced)")

    lines.extend(
        [
            "",
            "## Billing Rules",
            "",
            f"- Base billing rules prepared: {len(billing_items)}",
            f"- `per_million_tokens`: {len(token_rules)}",
            f"- `per_call`: {len(call_rules)}",
            f"- `per_second`: {len(second_rules)}",
            f"- Unresolved pricing rows skipped: {len(unresolved)}",
            "",
            "## Import Posture",
            "",
            "- All APIYI system API rows are kept as deprecated/inactive staging rows.",
            "- No APIYI Image, Video, or LLM subset is imported as runtime-ready in this bundle.",
            "- Endpoint hints and pricing metadata are retained for future adapter work, but runtime activation remains fully blocked.",
            "- Billing rules use public APIYI sell prices directly, converted as `USD * 100 -> credits` with no extra multiplier.",
            "- Hybrid-pricing docs are normalized to a single base rule when one primary public/default price exists; alternate billing modes stay in supplier notes only.",
            "- Runtime activation remains blocked for all APIYI endpoint families until they are explicitly re-enabled.",
            "",
            "## Recommended Next Step",
            "",
            "1. Import the APIYI bundle so all rows stay synchronized as deprecated staging data.",
            "2. Apply the prepared base billing rules to the imported rows.",
            "3. Re-enable specific APIYI subsets only after dedicated runtime adapter validation.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build APIYI system import and billing bundles from the extracted snapshot")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT), help="Snapshot JSON path")
    parser.add_argument("--import-json", default=str(DEFAULT_IMPORT_JSON), help="Output import bundle JSON")
    parser.add_argument("--billing-json", default=str(DEFAULT_BILLING_JSON), help="Output billing bundle JSON")
    parser.add_argument("--review-md", default=str(DEFAULT_REVIEW_MD), help="Output review markdown")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.is_absolute():
        snapshot_path = (ROOT / snapshot_path).resolve()
    import_json_path = Path(args.import_json)
    if not import_json_path.is_absolute():
        import_json_path = (ROOT / import_json_path).resolve()
    billing_json_path = Path(args.billing_json)
    if not billing_json_path.is_absolute():
        billing_json_path = (ROOT / billing_json_path).resolve()
    review_md_path = Path(args.review_md)
    if not review_md_path.is_absolute():
        review_md_path = (ROOT / review_md_path).resolve()

    snapshot = _read_json(snapshot_path)
    models = snapshot.get("models") if isinstance(snapshot.get("models"), list) else []
    import_items = [_build_import_item(model) for model in models]
    billing_items = []
    for model in models:
        pricing = model.get("pricing") if isinstance(model.get("pricing"), dict) else {}
        if not str(pricing.get("unit_type") or "").strip():
            continue
        if pricing.get("call_usd") is None and pricing.get("input_usd") is None and pricing.get("output_usd") is None:
            continue
        billing_items.append(_build_billing_item(model))

    import_json_path.parent.mkdir(parents=True, exist_ok=True)
    billing_json_path.parent.mkdir(parents=True, exist_ok=True)
    review_md_path.parent.mkdir(parents=True, exist_ok=True)

    import_json_path.write_text(json.dumps({"replace_all": False, "items": import_items}, ensure_ascii=False, indent=2), encoding="utf-8")
    billing_json_path.write_text(json.dumps({"provider": "apiyi", "items": billing_items}, ensure_ascii=False, indent=2), encoding="utf-8")
    review_md_path.write_text(_render_review(snapshot, import_items, billing_items), encoding="utf-8")

    print(f"WROTE {import_json_path}")
    print(f"WROTE {billing_json_path}")
    print(f"WROTE {review_md_path}")
    print(json.dumps({"import_items": len(import_items), "billing_items": len(billing_items)}, ensure_ascii=False))


if __name__ == "__main__":
    main()