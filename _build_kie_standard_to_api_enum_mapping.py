import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent
ENUM_CSV = ROOT / "_kie_input_param_enum_values_for_db.csv"
STANDARD_CSV = ROOT / "_kie_system_data_standard_dictionary.csv"

OUT_REVERSE_MAPPING = ROOT / "_kie_standard_to_api_enum_mapping.csv"
OUT_REVERSE_SUMMARY = ROOT / "_kie_standard_to_api_enum_mapping_summary.md"

EXCLUDED_STANDARD_DIMENSIONS = {"MODEL_ID", "VOICE_ID"}

# For one-to-one standard->API enum mapping, each model+dimension chooses one
# canonical source field, then every standard value maps only within that field.
FIELD_PRIORITY = {
    "ASPECT_RATIO": ["paths.post.input.aspect_ratio", "paths.post.input.size"],
    "RESOLUTION_TIER": ["paths.post.input.resolution", "paths.post.input.image_resolution"],
    "DURATION_SECONDS": ["paths.post.input.duration", "paths.post.input.n_frames"],
}

MODEL_SUFFIXES = [
    "-text-to-video",
    "-image-to-video",
    "-video-to-video",
    "-text-to-image",
    "-image-to-image",
    "-image-edit",
    "-motion-control",
]

MODEL_SEGMENTS = {
    "text-to-video",
    "image-to-video",
    "video-to-video",
    "text-to-image",
    "image-to-image",
    "image-edit",
    "motion-control",
}


def clean(v: Any) -> str:
    return str(v or "").strip()


def to_base_model(model_key: Any) -> str:
    key = clean(model_key).replace("\\", "/").strip("/")
    if not key:
        return ""

    if "/" not in key:
        return key

    provider, rest = key.split("/", 1)
    rest = rest.strip("/")
    if not rest:
        return provider

    if rest in MODEL_SEGMENTS:
        return provider

    for suffix in MODEL_SUFFIXES:
        if rest.endswith(suffix):
            base_rest = rest[: -len(suffix)].strip("-/")
            return f"{provider}/{base_rest}" if base_rest else provider

    return f"{provider}/{rest}"


def to_token(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean(v).lower())


def parse_float(v: Any) -> Optional[float]:
    text = clean(v)
    if not text:
        return None
    m = re.search(r"\d+(?:\.\d+)?", text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def parse_resolution_rank(v: Any) -> Optional[int]:
    text = clean(v).lower().replace(" ", "")
    if not text:
        return None

    m = re.match(r"^(\d+)(?:p)?$", text)
    if m:
        try:
            num = int(m.group(1))
            return num if num > 0 else None
        except Exception:
            return None

    m = re.match(r"^(\d+)[x:](\d+)$", text)
    if m:
        try:
            a = int(m.group(1))
            b = int(m.group(2))
            if a > 0 and b > 0:
                return min(a, b)
        except Exception:
            return None

    m = re.match(r"^(\d+(?:\.\d+)?)k$", text)
    if m:
        try:
            return int(float(m.group(1)) * 1000)
        except Exception:
            return None

    return None


def parse_ratio(v: Any) -> Optional[float]:
    text = clean(v).lower().replace(" ", "")
    if not text:
        return None
    if text in {"auto", "adaptive"}:
        return None

    m = re.match(r"^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$", text)
    if m:
        try:
            a = float(m.group(1))
            b = float(m.group(2))
            if a > 0 and b > 0:
                return a / b
        except Exception:
            return None

    m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", text)
    if m:
        try:
            a = float(m.group(1))
            b = float(m.group(2))
            if a > 0 and b > 0:
                return a / b
        except Exception:
            return None

    return None


def normalize_std_value(dim: str, value: str) -> str:
    text = clean(value)
    low = text.lower()

    if dim == "ASPECT_RATIO":
        alias = {
            "portrait": "9:16",
            "landscape": "16:9",
            "auto": "AUTO",
            "2.35:1": "21:9",
            "2.39:1": "21:9",
        }
        return alias.get(low, text.upper() if low == "auto" else text)

    if dim == "MODE":
        alias = {
            "std": "STANDARD",
            "standard": "STANDARD",
            "pro": "PRO",
            "fast": "FAST",
            "turbo": "TURBO",
            "master": "MASTER",
            "normal": "NORMAL",
            "fun": "FUN",
            "spicy": "SPICY",
        }
        return alias.get(low, text.upper())

    if dim == "QUALITY_LEVEL":
        alias = {
            "std": "STANDARD",
            "standard": "STANDARD",
            "high": "HIGH",
            "medium": "MEDIUM",
            "basic": "BASIC",
            "low": "LOW",
        }
        return alias.get(low, text.upper())

    if dim == "RESOLUTION_TIER":
        alias = {
            "480p": "P480",
            "512p": "P512",
            "580p": "P580",
            "720p": "P720",
            "768p": "P768",
            "1080p": "P1080",
            "1k": "K1",
            "2k": "K2",
            "4k": "K4",
        }
        return alias.get(low, text.upper())

    if dim == "OUTPUT_FORMAT":
        return text.upper()

    if dim in {"NUM_IMAGES", "UPSCALE_FACTOR", "SAFETY_TOLERANCE", "DURATION_SECONDS"}:
        n = parse_float(text)
        if n is None:
            return text
        return str(int(n)) if abs(n - int(n)) < 1e-9 else str(n)

    return text


def map_field_to_standard(field_path: str) -> Optional[str]:
    mapping = {
        "paths.post.model": "MODEL_ID",
        "paths.post.input.aspect_ratio": "ASPECT_RATIO",
        "paths.post.input.size": "ASPECT_RATIO",
        "paths.post.input.resolution": "RESOLUTION_TIER",
        "paths.post.input.image_resolution": "RESOLUTION_TIER",
        "paths.post.input.duration": "DURATION_SECONDS",
        "paths.post.input.n_frames": "DURATION_SECONDS",
        "paths.post.input.mode": "MODE",
        "paths.post.input.quality": "QUALITY_LEVEL",
        "paths.post.input.output_format": "OUTPUT_FORMAT",
        "paths.post.input.num_images": "NUM_IMAGES",
        "paths.post.input.upscale_factor": "UPSCALE_FACTOR",
        "paths.post.input.style": "STYLE",
        "paths.post.reasoning_effort": "REASONING_EFFORT",
        "paths.post.input.character_orientation": "CHARACTER_ORIENTATION",
        "paths.post.input.image_size": "IMAGE_SIZE_CLASS",
        "paths.post.input.voice": "VOICE_ID",
        "paths.post.input.safety_tolerance": "SAFETY_TOLERANCE",
    }
    std_dim = mapping.get(field_path)
    if std_dim in EXCLUDED_STANDARD_DIMENSIONS:
        return None
    return std_dim


def pick_numeric_nearest_lower(std_value: str, allowed_values: List[str], parser) -> Tuple[str, str]:
    req = parser(std_value)
    parsed: List[Tuple[str, float]] = []
    for val in allowed_values:
        num = parser(val)
        if num is None:
            continue
        parsed.append((val, float(num)))

    if not parsed:
        return allowed_values[0], "fallback_baseline"

    if req is None:
        min_val = min(parsed, key=lambda x: x[1])[0]
        return min_val, "fallback_baseline"

    le = [pair for pair in parsed if pair[1] <= float(req)]
    if le:
        best_num = max(pair[1] for pair in le)
        for val, num in le:
            if num == best_num:
                return val, "nearest_lower"

    min_val = min(parsed, key=lambda x: x[1])[0]
    return min_val, "fallback_min"


def pick_aspect_ratio(std_value: str, allowed_values: List[str]) -> Tuple[str, str]:
    exact = {clean(v).lower(): v for v in allowed_values}
    std_low = clean(std_value).lower()
    if std_low in exact:
        return exact[std_low], "exact"

    req_ratio = parse_ratio(std_value)
    candidates: List[Tuple[str, float]] = []
    for val in allowed_values:
        ratio = parse_ratio(val)
        if ratio is None:
            continue
        candidates.append((val, ratio))

    if req_ratio is not None and candidates:
        best = min(candidates, key=lambda x: abs(x[1] - req_ratio))[0]
        return best, "nearest_ratio"

    return allowed_values[0], "fallback_baseline"


def pick_enum_by_semantic(std_value: str, allowed_values: List[str], dim: str) -> Tuple[str, str]:
    std_norm = normalize_std_value(dim, std_value)
    std_token = to_token(std_norm)

    for val in allowed_values:
        if clean(val).lower() == clean(std_norm).lower():
            return val, "exact"

    token_map = {to_token(v): v for v in allowed_values}
    if std_token and std_token in token_map:
        return token_map[std_token], "semantic_token"

    alias_dict = {
        "MODE": {
            "standard": ["std", "standard"],
            "pro": ["pro"],
            "fast": ["fast", "turbo"],
            "master": ["master"],
            "normal": ["normal"],
            "fun": ["fun"],
            "spicy": ["spicy"],
        },
        "QUALITY_LEVEL": {
            "standard": ["std", "standard"],
            "high": ["high"],
            "medium": ["medium"],
            "basic": ["basic", "low"],
        },
    }

    dim_alias = alias_dict.get(dim, {})
    for target, keys in dim_alias.items():
        if std_token == to_token(target) or std_token in {to_token(k) for k in keys}:
            for val in allowed_values:
                if to_token(val) in {to_token(target)} | {to_token(k) for k in keys}:
                    return val, "semantic_alias"

    return allowed_values[0], "fallback_baseline"


def pick_model_id(std_value: str, allowed_values: List[str]) -> Tuple[str, str]:
    std = clean(std_value)
    for val in allowed_values:
        if clean(val).lower() == std.lower():
            return val, "exact"

    std_prefix = clean(std).split("/")[0].lower()
    same_prefix = [v for v in allowed_values if clean(v).lower().startswith(std_prefix + "/")]
    if same_prefix:
        return same_prefix[0], "semantic_prefix"

    return allowed_values[0], "fallback_baseline"


def choose_mapping(std_dim: str, std_value: str, allowed_values: List[str]) -> Tuple[str, str]:
    if not allowed_values:
        return "", "unmapped"

    if std_dim == "ASPECT_RATIO":
        return pick_aspect_ratio(std_value, allowed_values)
    if std_dim == "DURATION_SECONDS":
        return pick_numeric_nearest_lower(std_value, allowed_values, parse_float)
    if std_dim == "RESOLUTION_TIER":
        return pick_numeric_nearest_lower(std_value, allowed_values, parse_resolution_rank)
    if std_dim in {"NUM_IMAGES", "UPSCALE_FACTOR", "SAFETY_TOLERANCE"}:
        return pick_numeric_nearest_lower(std_value, allowed_values, parse_float)
    if std_dim == "MODEL_ID":
        return pick_model_id(std_value, allowed_values)

    return pick_enum_by_semantic(std_value, allowed_values, std_dim)


def load_standard_dictionary() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = defaultdict(list)
    with STANDARD_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            dim = clean(row.get("standard_dimension"))
            val = clean(row.get("standard_value"))
            if dim in EXCLUDED_STANDARD_DIMENSIONS:
                continue
            if dim and val:
                out[dim].append(val)
    return out


def load_api_enum_groups() -> Dict[Tuple[str, str, str, str], List[Dict[str, str]]]:
    groups: Dict[Tuple[str, str, str, str], List[Dict[str, str]]] = defaultdict(list)
    with ENUM_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            provider = clean(row.get("provider") or "kie")
            model_key_raw = clean(row.get("model_key_inferred"))
            model_key = to_base_model(model_key_raw)
            model_title = clean(row.get("model_title"))
            field_path = clean(row.get("field_path"))
            enum_value = clean(row.get("enum_value"))
            if not field_path or not enum_value:
                continue
            if not model_key:
                continue
            # Base-model granularity: variants under same base model share one mapping set.
            key = (provider, model_key, model_key, field_path)
            groups[key].append(
                {
                    "enum_value": enum_value,
                    "value_order": clean(row.get("value_order")),
                    "model_url": clean(row.get("model_url")),
                    "model_title": model_title,
                    "model_key_raw": model_key_raw,
                }
            )

    for key in list(groups.keys()):
        rows = groups[key]
        def _ord(v: Dict[str, str]) -> int:
            try:
                return int(float(clean(v.get("value_order") or "999999")))
            except Exception:
                return 999999
        rows.sort(key=lambda x: (_ord(x), clean(x.get("enum_value"))))

        deduped: List[Dict[str, str]] = []
        seen = set()
        for r in rows:
            ev = clean(r.get("enum_value"))
            if ev.lower() in seen:
                continue
            seen.add(ev.lower())
            deduped.append(r)
        groups[key] = deduped

    return groups


def select_canonical_field_groups(
    groups: Dict[Tuple[str, str, str, str], List[Dict[str, str]]]
) -> Dict[Tuple[str, str, str, str], List[Dict[str, str]]]:
    bucket: Dict[Tuple[str, str, str, str], List[Tuple[str, List[Dict[str, str]]]]] = defaultdict(list)

    for (provider, model_key, model_title, field_path), enum_rows in groups.items():
        std_dim = map_field_to_standard(field_path)
        if not std_dim:
            continue
        key = (provider, model_key, model_title, std_dim)
        bucket[key].append((field_path, enum_rows))

    selected: Dict[Tuple[str, str, str, str], List[Dict[str, str]]] = {}

    for (provider, model_key, model_title, std_dim), field_rows in bucket.items():
        priority_map = {name: idx for idx, name in enumerate(FIELD_PRIORITY.get(std_dim, []))}

        def _rank(item: Tuple[str, List[Dict[str, str]]]) -> Tuple[int, int, str]:
            field_path, enum_rows = item
            # lower is better
            priority_rank = priority_map.get(field_path, 999)
            # more enum coverage is better
            enum_count_rank = -len(enum_rows)
            return (priority_rank, enum_count_rank, field_path)

        best_field_path, best_rows = sorted(field_rows, key=_rank)[0]
        selected[(provider, model_key, model_title, best_field_path)] = best_rows

    return selected


def main() -> None:
    if not ENUM_CSV.exists():
        raise FileNotFoundError(f"Missing {ENUM_CSV}")
    if not STANDARD_CSV.exists():
        raise FileNotFoundError(f"Missing {STANDARD_CSV}")

    std_dict = load_standard_dictionary()
    enum_groups = load_api_enum_groups()
    enum_groups = select_canonical_field_groups(enum_groups)

    out_rows: List[Dict[str, str]] = []
    coverage: Dict[str, Dict[str, int]] = defaultdict(lambda: {"mapped": 0, "total": 0})

    for (provider, model_key, model_title, field_path), enum_rows in enum_groups.items():
        std_dim = map_field_to_standard(field_path)
        if not std_dim:
            continue

        std_values = sorted(set(std_dict.get(std_dim, [])))
        if not std_values:
            continue

        allowed_values = [clean(r.get("enum_value")) for r in enum_rows if clean(r.get("enum_value"))]
        model_url = clean(enum_rows[0].get("model_url")) if enum_rows else ""

        for std_value in std_values:
            coverage[std_dim]["total"] += 1
            mapped_enum, rule = choose_mapping(std_dim, std_value, allowed_values)
            if mapped_enum:
                coverage[std_dim]["mapped"] += 1

            out_rows.append(
                {
                    "provider": provider,
                    "model_key_inferred": model_key,
                    "model_title": model_title,
                    "model_url": model_url,
                    "source_field": field_path,
                    "standard_dimension": std_dim,
                    "standard_value": std_value,
                    "mapped_api_enum_value": mapped_enum,
                    "mapping_rule": rule,
                    "is_mapped": "1" if mapped_enum else "0",
                }
            )

    out_rows.sort(
        key=lambda x: (
            clean(x.get("standard_dimension")),
            clean(x.get("model_key_inferred")),
            clean(x.get("source_field")),
            clean(x.get("standard_value")),
        )
    )

    with OUT_REVERSE_MAPPING.open("w", encoding="utf-8", newline="") as f:
        fn = [
            "provider",
            "model_key_inferred",
            "model_title",
            "model_url",
            "source_field",
            "standard_dimension",
            "standard_value",
            "mapped_api_enum_value",
            "mapping_rule",
            "is_mapped",
        ]
        wr = csv.DictWriter(f, fieldnames=fn)
        wr.writeheader()
        wr.writerows(out_rows)

    lines: List[str] = []
    lines.append("# KIE 系统字典 -> API 枚举映射覆盖报告")
    lines.append("")
    lines.append(f"- API 枚举源文件: {ENUM_CSV.name}")
    lines.append(f"- 系统字典源文件: {STANDARD_CSV.name}")
    lines.append(f"- 排除维度: {', '.join(sorted(EXCLUDED_STANDARD_DIMENSIONS))}")
    lines.append(f"- 反向映射产物: {OUT_REVERSE_MAPPING.name}")
    lines.append(f"- 总映射行数: {len(out_rows)}")
    lines.append("")
    lines.append("## 维度覆盖率")

    total_mapped = 0
    total_total = 0
    for dim in sorted(coverage.keys()):
        mapped = int(coverage[dim]["mapped"])
        total = int(coverage[dim]["total"])
        pct = (mapped / total * 100.0) if total else 0.0
        total_mapped += mapped
        total_total += total
        lines.append(f"- {dim}: {mapped}/{total} ({pct:.2f}%)")

    lines.append("")
    if total_total:
        lines.append(f"- 全局覆盖率: {total_mapped}/{total_total} ({(total_mapped / total_total * 100.0):.2f}%)")
    else:
        lines.append("- 全局覆盖率: 0/0 (0.00%)")

    rule_count: Dict[str, int] = defaultdict(int)
    for row in out_rows:
        rule_count[clean(row.get("mapping_rule") or "unknown")] += 1

    lines.append("")
    lines.append("## 规则分布")
    for rule in sorted(rule_count.keys()):
        lines.append(f"- {rule}: {rule_count[rule]}")

    OUT_REVERSE_SUMMARY.write_text("\n".join(lines), encoding="utf-8")

    print(f"Generated: {OUT_REVERSE_MAPPING}")
    print(f"Generated: {OUT_REVERSE_SUMMARY}")
    print(f"rows={len(out_rows)} total_mapped={total_mapped} total_total={total_total}")


if __name__ == "__main__":
    main()
