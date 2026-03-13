import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent
INPUT_CSV = ROOT / "_kie_billing_rule_candidates_system_api_integrated.csv"
OUT_SQL = ROOT / "_kie_standard_billing_rules_auto.sql"


def esc(v: object) -> str:
    return str(v or "").replace("'", "''")


def normalize_mode(v: str) -> Optional[str]:
    raw = str(v or "").strip().lower()
    if not raw:
        return None
    mapping = {
        "std": "STANDARD",
        "standard": "STANDARD",
        "pro": "PRO",
        "fast": "FAST",
        "turbo": "TURBO",
        "master": "MASTER",
        "fun": "FUN",
        "normal": "NORMAL",
        "spicy": "SPICY",
    }
    return mapping.get(raw, raw.upper())


def normalize_resolution(v: str) -> Optional[str]:
    raw = str(v or "").strip().lower().replace(" ", "")
    if not raw:
        return None
    mapping = {
        "1k": "K1",
        "2k": "K2",
        "4k": "K4",
        "480p": "P480",
        "512p": "P512",
        "580p": "P580",
        "720p": "P720",
        "768p": "P768",
        "1080p": "P1080",
    }
    return mapping.get(raw)


def normalize_aspect(v: str) -> Optional[str]:
    raw = str(v or "").strip().lower()
    if not raw:
        return None
    if raw == "portrait":
        return "9:16"
    if raw == "landscape":
        return "16:9"
    if raw == "auto":
        return "AUTO"
    if ":" in raw:
        return raw
    return None


def normalize_bool(v: str) -> Optional[bool]:
    raw = str(v or "").strip().lower()
    if not raw:
        return None
    if raw in {"1", "true", "yes", "y", "on", "supported"}:
        return True
    if raw in {"0", "false", "no", "n", "off", "unsupported"}:
        return False
    return None


def parse_standard_values(row: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}

    mode_raw = str(row.get("mode") or "").strip()
    # Some rows use comma-separated mode candidates. Keep first as representative pricing split.
    if mode_raw:
        mode_first = mode_raw.split(",", 1)[0].strip()
        mode_std = normalize_mode(mode_first)
        if mode_std:
            out["MODE"] = mode_std

    res_std = normalize_resolution(str(row.get("resolution") or ""))
    if res_std:
        out["RESOLUTION_TIER"] = res_std

    ar_std = normalize_aspect(str(row.get("aspect_ratio") or ""))
    if ar_std:
        out["ASPECT_RATIO"] = ar_std

    sound_std = normalize_bool(str(row.get("source_sound") or ""))
    if sound_std is not None:
        out["SOUND_SUPPORTED"] = "TRUE" if sound_std else "FALSE"

    ms_std = normalize_bool(str(row.get("source_multi_shots") or ""))
    if ms_std is not None:
        out["MULTI_SHOTS_SUPPORTED"] = "TRUE" if ms_std else "FALSE"

    return out


def estimate_rule_price(category: str, standard_values: Dict[str, str]) -> Tuple[str, int]:
    cat = str(category or "").strip().lower()
    if cat == "video":
        unit = "per_second"
        price = 30
        res = standard_values.get("RESOLUTION_TIER")
        if res in {"P1080", "K2"}:
            price += 12
        elif res in {"K4"}:
            price += 20
        elif res in {"P720", "K1"}:
            price += 6
        mode = standard_values.get("MODE")
        if mode in {"PRO", "MASTER", "TURBO"}:
            price += 10
        elif mode in {"FAST"}:
            price += 4
        if standard_values.get("SOUND_SUPPORTED") == "TRUE":
            price += 8
        if standard_values.get("MULTI_SHOTS_SUPPORTED") == "TRUE":
            price += 10
        return unit, price

    if cat == "image":
        unit = "per_call"
        price = 10
        res = standard_values.get("RESOLUTION_TIER")
        if res in {"K2", "P1080"}:
            price += 6
        elif res in {"K4"}:
            price += 10
        mode = standard_values.get("MODE")
        if mode in {"PRO", "MASTER", "TURBO"}:
            price += 5
        elif mode in {"FAST"}:
            price += 2
        return unit, price

    return "per_call", 5


def build_name(model: str, idx: int) -> str:
    core = str(model or "").strip() or "unknown-model"
    return f"KIE Auto Std {core} #{idx}"


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing input: {INPUT_CSV}")

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    grouped: Dict[int, Dict[str, object]] = {}
    combos_by_api: Dict[int, Dict[Tuple[Tuple[str, str], ...], Dict[str, str]]] = defaultdict(dict)

    for row in rows:
        api_id_raw = str(row.get("matched_system_api_id") or "").strip()
        if not api_id_raw.isdigit():
            continue
        api_id = int(api_id_raw)

        category = str(row.get("category") or "").strip().lower()
        if category not in {"video", "image"}:
            continue

        model = str(row.get("matched_system_api_model") or "").strip()
        if not model:
            continue

        grouped.setdefault(api_id, {"category": category, "model": model})

        std = parse_standard_values(row)
        if not std:
            continue

        key = tuple(sorted(std.items()))
        if key not in combos_by_api[api_id]:
            combos_by_api[api_id][key] = std

    lines: List[str] = []
    lines.append("-- Auto-generated KIE standard billing rules (idempotent)")
    lines.append("BEGIN TRANSACTION;")
    lines.append("")
    lines.append("DELETE FROM system_api_billing_rules WHERE name LIKE 'KIE Auto Std %';")
    lines.append("")

    base_count = 0
    specific_count = 0

    for api_id in sorted(grouped.keys()):
        meta = grouped[api_id]
        category = str(meta["category"])
        model = str(meta["model"])

        base_unit, base_cost = estimate_rule_price(category, {})
        applies_text = 1 if category == "chat" else 0
        applies_image = 1 if category == "image" else 0
        applies_video = 1 if category == "video" else 0

        base_name = f"KIE Auto Std {model} Base"
        lines.append(
            "INSERT INTO system_api_billing_rules "
            "(system_api_id, name, description, is_active, priority, applies_to_text, applies_to_image, applies_to_video, "
            "billing_unit_type, billing_cost, billing_cost_input, billing_cost_output, charge_multiplier, extra_conditions, created_at, updated_at) VALUES "
            f"({api_id}, '{esc(base_name)}', 'Auto base rule generated from category fallback', 1, -100000, "
            f"{applies_text}, {applies_image}, {applies_video}, '{base_unit}', {base_cost}, 0, 0, 2.0, "
            "'{\"rule_kind\":\"base_pricing\"}', datetime('now'), datetime('now'));"
        )
        base_count += 1

        idx = 1
        for key in sorted(combos_by_api.get(api_id, {}).keys()):
            std = dict(key)
            unit, price = estimate_rule_price(category, std)
            priority = 80 + (len(std) * 10)
            name = build_name(model, idx)
            desc = f"Auto std rule for {model}: " + ", ".join([f"{k}={v}" for k, v in sorted(std.items())])
            extra = json.dumps({"standard_values": std}, ensure_ascii=False, separators=(",", ":"))

            lines.append(
                "INSERT INTO system_api_billing_rules "
                "(system_api_id, name, description, is_active, priority, applies_to_text, applies_to_image, applies_to_video, "
                "billing_unit_type, billing_cost, billing_cost_input, billing_cost_output, charge_multiplier, extra_conditions, created_at, updated_at) VALUES "
                f"({api_id}, '{esc(name)}', '{esc(desc)}', 1, {priority}, "
                f"{applies_text}, {applies_image}, {applies_video}, '{unit}', {price}, 0, 0, 2.0, "
                f"'{esc(extra)}', datetime('now'), datetime('now'));"
            )
            specific_count += 1
            idx += 1

        lines.append("")

    lines.append("COMMIT;")
    OUT_SQL.write_text("\n".join(lines), encoding="utf-8")

    print(f"Generated: {OUT_SQL}")
    print(f"System APIs covered: {len(grouped)}")
    print(f"Base rules: {base_count}")
    print(f"Specific standard rules: {specific_count}")


if __name__ == "__main__":
    main()
