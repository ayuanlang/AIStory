import csv
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SRC_ENUM = ROOT / "_kie_input_enum_values_catalog_purified.csv"
SRC_EXPLAIN = ROOT / "_kie_input_enum_field_explanations.csv"

OUT_FIELD_DIM = ROOT / "_kie_input_param_field_dim_for_db.csv"
OUT_ENUM_FACT = ROOT / "_kie_input_param_enum_values_for_db.csv"


def split_vals(raw: str):
    if not raw:
        return []
    return [x.strip() for x in raw.split(";") if x.strip()]


def guess_model_key_from_url(url: str) -> str:
    p = urlparse(url).path.strip("/")
    if p.startswith("market/") and p.endswith(".md"):
        return p[len("market/") : -3]
    if p.endswith(".md"):
        return p[:-3]
    return p


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    enum_rows = read_csv(SRC_ENUM)
    explain_rows = read_csv(SRC_EXPLAIN)

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    # Build field description lookup.
    explain_by_field = {r["field_path"].strip(): r for r in explain_rows if r.get("field_path")}

    # File 1: field dimension table (deduplicated fields).
    field_paths = sorted({r["field_path"].strip() for r in enum_rows if r.get("field_path")})
    field_dim_rows = []
    for i, fp in enumerate(field_paths, start=1):
        ex = explain_by_field.get(fp, {})
        field_dim_rows.append(
            {
                "field_id": i,
                "provider": "kie",
                "field_path": fp,
                "field_name": fp.split(".")[-1],
                "field_description": ex.get("explanation", ""),
                "sample_enum_values": ex.get("sample_enum_values", ""),
                "page_count": ex.get("page_count", ""),
                "enum_value_count": ex.get("enum_value_count", ""),
                "is_active": 1,
                "updated_at": now,
            }
        )

    # File 2: enum fact table (one row per model/page + field + enum value).
    # Also attach a stable model_key inferred from URL and optional model enum on page.
    page_model_values = defaultdict(list)
    for r in enum_rows:
        if r.get("field_path") == "paths.post.model":
            page_model_values[(r.get("title", "").strip(), r.get("url", "").strip())].extend(split_vals(r.get("enum_values", "")))

    fact_rows = []
    fact_id = 1
    for r in enum_rows:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        field_path = (r.get("field_path") or "").strip()
        values = split_vals(r.get("enum_values") or "")
        if not values:
            continue

        inferred_model_key = guess_model_key_from_url(url)
        model_candidates = sorted(set(page_model_values.get((title, url), [])))
        model_enum_on_page = "; ".join(model_candidates)

        for idx, v in enumerate(values, start=1):
            fact_rows.append(
                {
                    "enum_row_id": fact_id,
                    "provider": "kie",
                    "model_title": title,
                    "model_url": url,
                    "model_key_inferred": inferred_model_key,
                    "model_enum_on_page": model_enum_on_page,
                    "field_path": field_path,
                    "enum_value": v,
                    "value_order": idx,
                    "is_active": 1,
                    "updated_at": now,
                }
            )
            fact_id += 1

    with OUT_FIELD_DIM.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(field_dim_rows[0].keys()), quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(field_dim_rows)

    with OUT_ENUM_FACT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fact_rows[0].keys()), quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(fact_rows)

    print(f"WROTE {OUT_FIELD_DIM}")
    print(f"WROTE {OUT_ENUM_FACT}")
    print(f"FIELD_DIM_ROWS {len(field_dim_rows)}")
    print(f"ENUM_FACT_ROWS {len(fact_rows)}")


if __name__ == "__main__":
    main()
