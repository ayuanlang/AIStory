import csv
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parent
REVERSE_CSV = ROOT / "_kie_standard_to_api_enum_mapping.csv"
OUT_MAPPING_CSV = ROOT / "_kie_system_to_model_enum_mapping.csv"
OUT_SUMMARY_MD = ROOT / "_kie_existing_table_mapping_update_summary.md"

EXCLUDED_STANDARD_DIMENSIONS = {"MODEL_ID", "VOICE_ID"}


def clean(v: Any) -> str:
    return str(v or "").strip()


def confidence_from_rule(rule: str) -> str:
    r = clean(rule).lower()
    if r in {"exact", "semantic_token", "semantic_alias"}:
        return "HIGH"
    if r in {"nearest_lower", "nearest_ratio", "semantic_prefix"}:
        return "MEDIUM"
    if r.startswith("fallback"):
        return "LOW"
    return "MEDIUM"


def main() -> None:
    if not REVERSE_CSV.exists():
        raise FileNotFoundError(f"Missing reverse mapping file: {REVERSE_CSV}")

    rows: List[Dict[str, str]] = []
    seen: set[Tuple[str, str, str, str, str, str]] = set()

    with REVERSE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            is_mapped = clean(r.get("is_mapped"))
            if is_mapped != "1":
                continue

            provider = clean(r.get("provider") or "kie")
            model_key = clean(r.get("model_key_inferred"))
            model_title = clean(r.get("model_title"))
            model_url = clean(r.get("model_url"))
            source_field = clean(r.get("source_field"))
            source_enum_value = clean(r.get("mapped_api_enum_value"))
            standard_dimension = clean(r.get("standard_dimension")).upper()
            standard_value = clean(r.get("standard_value"))
            mapping_rule = clean(r.get("mapping_rule"))

            if standard_dimension in EXCLUDED_STANDARD_DIMENSIONS:
                continue

            if not source_field or not source_enum_value or not standard_dimension or not standard_value:
                continue

            key = (
                provider.lower(),
                model_key.lower(),
                source_field.lower(),
                source_enum_value.lower(),
                standard_dimension.upper(),
                standard_value.lower(),
            )
            if key in seen:
                continue
            seen.add(key)

            rows.append(
                {
                    "provider": provider,
                    "model_title": model_title,
                    "model_url": model_url,
                    "model_key_inferred": model_key,
                    "source_field": source_field,
                    "source_enum_value": source_enum_value,
                    "standard_dimension": standard_dimension,
                    "standard_value": standard_value,
                    "confidence": confidence_from_rule(mapping_rule),
                    "note": f"std_to_api:{mapping_rule}",
                }
            )

    rows.sort(
        key=lambda x: (
            clean(x.get("standard_dimension")),
            clean(x.get("model_key_inferred")),
            clean(x.get("source_field")),
            clean(x.get("standard_value")),
            clean(x.get("source_enum_value")),
        )
    )

    with OUT_MAPPING_CSV.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "provider",
            "model_title",
            "model_url",
            "model_key_inferred",
            "source_field",
            "source_enum_value",
            "standard_dimension",
            "standard_value",
            "confidence",
            "note",
        ]
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        wr.writerows(rows)

    high = sum(1 for r in rows if clean(r.get("confidence")) == "HIGH")
    medium = sum(1 for r in rows if clean(r.get("confidence")) == "MEDIUM")
    low = sum(1 for r in rows if clean(r.get("confidence")) == "LOW")

    lines = [
        "# Existing Table Mapping Update Summary",
        "",
        f"- Source reverse mapping: {REVERSE_CSV.name}",
        f"- Updated existing-table mapping csv: {OUT_MAPPING_CSV.name}",
        f"- Excluded dimensions: {', '.join(sorted(EXCLUDED_STANDARD_DIMENSIONS))}",
        f"- Total rows written: {len(rows)}",
        "",
        "## Confidence distribution",
        f"- HIGH: {high}",
        f"- MEDIUM: {medium}",
        f"- LOW: {low}",
        "",
        "## Note",
        "- `note` column uses `std_to_api:<rule>` to preserve mapping rule traceability.",
    ]
    OUT_SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Updated: {OUT_MAPPING_CSV}")
    print(f"Summary: {OUT_SUMMARY_MD}")
    print(f"rows={len(rows)} high={high} medium={medium} low={low}")


if __name__ == "__main__":
    main()
