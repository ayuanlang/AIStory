import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "docs" / "n1n_catalog_snapshot.protocol_baseline.json"
DEFAULT_IMPORT_JSON = ROOT / "docs" / "n1n_system_api_import_bundle.protocol_baseline.json"
DEFAULT_MAPPING_MD = ROOT / "docs" / "n1n_protocol_mapping_20260320.md"
DEFAULT_REVIEW_MD = ROOT / "docs" / "n1n_import_readiness_review_20260320.md"
DEFAULT_PRICING_MD = ROOT / "docs" / "n1n_billing_rule_guide_20260320.md"


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _category_output_format(category: str) -> str:
    mapping = {
        "LLM": "text",
        "Image": "image",
        "Video": "video",
        "Voice": "audio",
        "Music": "audio",
        "Tools": "json",
    }
    return mapping.get(str(category or "").strip(), "text")


def _build_modality(profile: Dict[str, Any]) -> Dict[str, Any]:
    category = str(profile.get("category") or "").strip() or "LLM"
    modality: Dict[str, Any] = {
        "output_format": _category_output_format(category),
    }
    generation_modes = list(profile.get("generation_modes") or [])
    if generation_modes:
        modality["generation_modes"] = generation_modes
    input_formats = list(profile.get("input_formats") or [])
    if input_formats:
        modality["input_formats"] = input_formats
    return modality


def _build_import_item(snapshot: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    base_urls = snapshot.get("base_urls") if isinstance(snapshot.get("base_urls"), dict) else {}
    primary_base_url = str(base_urls.get("primary_base_url") or "https://api.n1n.ai").strip()
    mirror_base_url = str(base_urls.get("mirror_base_url") or "https://hk.n1n.ai").strip()
    protocol_key = str(profile.get("protocol_key") or "n1n-protocol").strip()
    endpoint_hint = str(profile.get("endpoint_hint") or "").strip() or None
    billing_unit_type = str(profile.get("billing_unit_type") or "per_call").strip() or "per_call"
    source_urls = list(profile.get("source_urls") or [])
    source_urls = [str(item).strip() for item in source_urls if str(item).strip()]

    supplier_info = {
        "source_urls": source_urls,
        "n1n": {
            "protocol_key": protocol_key,
            "protocol_label": profile.get("protocol_label"),
            "family_key": profile.get("family_key"),
            "family_label": profile.get("family_label"),
            "api_style": profile.get("api_style"),
            "endpoint_hint": endpoint_hint,
            "mirror_base_url": mirror_base_url,
            "doc_count": profile.get("doc_count"),
            "sample_titles": list(profile.get("sample_titles") or []),
            "model_hints": list(profile.get("model_hints") or []),
            "pricing_basis": ((snapshot.get("pricing_model") or {}).get("pricing_basis") if isinstance(snapshot.get("pricing_model"), dict) else None),
            "known_fixed_prices": ((snapshot.get("pricing_model") or {}).get("known_fixed_prices") if isinstance(snapshot.get("pricing_model"), dict) else []),
        },
    }

    config = {
        "deprecated": True,
        "is_deprecated": True,
        "disable_api": True,
        "provider_api_key_strategy": "random",
        "endpoint_hint": endpoint_hint,
        "n1n": {
            "api_style": profile.get("api_style"),
            "family_key": profile.get("family_key"),
            "family_label": profile.get("family_label"),
            "mirror_base_url": mirror_base_url,
            "pricing_basis": "official_rate_x_group_multiplier",
            "billing_ready": False,
            "runtime_ready": False,
        },
    }

    return {
        "name": f"n1n {str(profile.get('protocol_label') or protocol_key).strip()}",
        "category": str(profile.get("category") or "LLM").strip() or "LLM",
        "provider": "n1n",
        "base_url": primary_base_url,
        "model": protocol_key,
        "base_model": str(profile.get("family_key") or "n1n").strip() or "n1n",
        "modality": _build_modality(profile),
        "tags": ["n1n", "auto-import", "staging-only", str(profile.get("api_style") or "provider_specific")],
        "supplier_info": supplier_info,
        "config": config,
        "billing_unit_type": billing_unit_type,
        "billing_cost": 0,
        "billing_cost_input": 0,
        "billing_cost_output": 0,
        "deprecated": True,
        "is_active": False,
    }


def _render_mapping(snapshot: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    lines = [
        "# n1n API Mapping 2026-03-20",
        "",
        "This mapping normalizes n1n protocol families into internal provider/category rows. Because n1n llms.txt is a protocol index rather than a clean model inventory, these rows are synthetic staging entries intended for later adapter work.",
        "",
        "## Base URLs",
        "",
        f"- Primary: {((snapshot.get('base_urls') or {}).get('primary_base_url') or '')}",
        f"- Mirror: {((snapshot.get('base_urls') or {}).get('mirror_base_url') or '')}",
        "",
        "## Canonical Mapping",
        "",
    ]
    for item in items:
        n1n_info = ((item.get("supplier_info") or {}).get("n1n") or {}) if isinstance(item.get("supplier_info"), dict) else {}
        modality = item.get("modality") if isinstance(item.get("modality"), dict) else {}
        line = (
            f"- {item.get('model')}: category={item.get('category')}, style={n1n_info.get('api_style')}, "
            f"endpoint_hint={n1n_info.get('endpoint_hint') or 'undocumented'}, "
            f"generation_modes={','.join(modality.get('generation_modes') or []) or 'n/a'}, "
            f"input_formats={','.join(modality.get('input_formats') or []) or 'n/a'}, "
            f"billing_unit_type={item.get('billing_unit_type')}"
        )
        lines.append(line)
    lines.extend(
        [
            "",
            "## Mapping Notes",
            "",
            "- OpenAI-compatible chat, responses, embeddings, images, and audio families are mapped to explicit endpoint hints because the base docs publish those paths.",
            "- Claude native and Gemini native rows are mapped as protocol families, not model inventory rows.",
            "- Provider-specific async families such as Midjourney, Kling, Vidu, Suno, Runway, and Luma remain endpoint-undocumented staging rows until detail pages are captured more systematically.",
            "- All n1n rows are imported as deprecated/inactive staging rows in this bundle.",
        ]
    )
    return "\n".join(lines)


def _render_review(snapshot: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    category_counts: Dict[str, int] = {}
    for item in items:
        category = str(item.get("category") or "Unknown")
        category_counts[category] = category_counts.get(category, 0) + 1
    pricing_model = snapshot.get("pricing_model") if isinstance(snapshot.get("pricing_model"), dict) else {}
    pricing_groups = list(pricing_model.get("groups") or [])
    fixed_prices = list(pricing_model.get("known_fixed_prices") or [])
    lines = [
        "# n1n Import Readiness Review",
        "",
        f"Generated at: {snapshot.get('generated_at')}",
        "",
        "## Extraction Coverage",
        "",
        f"- llms.txt API Docs entries parsed: {snapshot.get('section_counts', {}).get('API Docs', 0)}",
        f"- Protocol profiles normalized: {len(snapshot.get('profiles') or [])}",
        f"- Import rows prepared: {len(items)}",
        f"- Pricing groups captured: {len(pricing_groups)}",
        f"- Known fixed-price exceptions: {len(fixed_prices)}",
        "",
        "## Category Counts",
        "",
    ]
    for category, count in sorted(category_counts.items()):
        lines.append(f"- {category}: {count}")
    lines.extend(
        [
            "",
            "## Import Posture",
            "",
            "- All n1n rows are kept deprecated/inactive staging rows.",
            "- No n1n runtime activation is enabled in this bundle because the repo does not yet contain a provider adapter or provider-name promotion logic for n1n.",
            "- OpenAI-compatible, Claude native, and Gemini native subsets are identified as future activation candidates once adapter work is done.",
            "- Provider-specific async families are kept as documentation-backed inventory hints only.",
            "",
            "## Billing Posture",
            "",
            "- No billing JSON bundle is emitted in this pass.",
            "- The docs expose group multipliers and at least one fixed-price exception, but not a complete per-model price table that can be safely converted into credits.",
            "- The generated billing guide documents the correct pricing rule formula and the gating conditions required before direct billing import.",
            "",
            "## Recommended Next Step",
            "",
            "1. Import the n1n bundle as staging-only rows so provider/category inventory and source URLs are tracked in the admin system.",
            "2. Add a dedicated n1n provider adapter or generic OpenAI-compatible promotion path if you want selected LLM/Image rows to become runnable.",
            "3. Capture a per-model public pricing source before generating direct billing rows.",
        ]
    )
    return "\n".join(lines)


def _render_pricing(snapshot: Dict[str, Any]) -> str:
    pricing_model = snapshot.get("pricing_model") if isinstance(snapshot.get("pricing_model"), dict) else {}
    groups = list(pricing_model.get("groups") or [])
    fixed_prices = list(pricing_model.get("known_fixed_prices") or [])
    lines = [
        "# n1n Billing Rule Guide 2026-03-20",
        "",
        "## Billing Formula",
        "",
        "- Primary rule: `actual_price = upstream_official_price x selected_group_multiplier`",
        "- n1n docs explicitly describe pricing by group multiplier rather than a unified model price table.",
        "- The selected token group is part of the billing identity and can change the price of the same upstream model.",
        "",
        "## Captured Group Multipliers",
        "",
    ]
    for group in groups:
        rate_text = str(group.get("rate_text") or "").strip() or "undocumented"
        lines.append(f"- {group.get('group_name')}: {rate_text} | supports={group.get('supported_models')}")
    if fixed_prices:
        lines.extend(["", "## Fixed-Price Exceptions", ""])
        for item in fixed_prices:
            lines.append(f"- {item.get('group_name')}: ${item.get('price_usd')} per call")
    lines.extend(
        [
            "",
            "## Internal Mapping Guidance",
            "",
            "- LLM / Chat / Responses / Embeddings: default to `per_million_tokens` once upstream official token prices are sourced.",
            "- Image families: default to `per_call` once the upstream official image price is sourced.",
            "- Video families: keep unresolved until upstream billing basis is confirmed; many upstream providers are `per_second`, but this is not uniformly documented by n1n.",
            "- Voice / Music families: keep unresolved or temporary `per_call` staging until official upstream billing units are captured.",
            "",
            "## Import Guardrail",
            "",
            "- Do not apply zero-cost placeholder billing rows to production settings.",
            "- Generate direct pricing rules only after a model-level official price baseline is available for the exact group/provider pairing.",
            "- If you need an interim admin view, store the multiplier logic in `supplier_info` only and keep billing inactive.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build n1n staging import bundle and supporting docs from extracted snapshot")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT), help="Snapshot JSON path")
    parser.add_argument("--import-json", default=str(DEFAULT_IMPORT_JSON), help="Output import bundle JSON")
    parser.add_argument("--mapping-md", default=str(DEFAULT_MAPPING_MD), help="Output mapping markdown")
    parser.add_argument("--review-md", default=str(DEFAULT_REVIEW_MD), help="Output review markdown")
    parser.add_argument("--pricing-md", default=str(DEFAULT_PRICING_MD), help="Output pricing markdown")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    import_json_path = Path(args.import_json)
    mapping_md_path = Path(args.mapping_md)
    review_md_path = Path(args.review_md)
    pricing_md_path = Path(args.pricing_md)

    snapshot = _read_json(snapshot_path)
    profiles = list(snapshot.get("profiles") or [])
    items = [_build_import_item(snapshot, profile) for profile in profiles]

    _write_json(import_json_path, {"replace_all": False, "items": items})
    _write_text(mapping_md_path, _render_mapping(snapshot, items))
    _write_text(review_md_path, _render_review(snapshot, items))
    _write_text(pricing_md_path, _render_pricing(snapshot))

    print(f"WROTE {import_json_path}")
    print(f"WROTE {mapping_md_path}")
    print(f"WROTE {review_md_path}")
    print(f"WROTE {pricing_md_path}")
    print(json.dumps({"import_items": len(items)}, ensure_ascii=False))


if __name__ == "__main__":
    main()