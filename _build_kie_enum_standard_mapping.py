import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent
ENUM_CSV = ROOT / "_kie_input_param_enum_values_for_db.csv"
MATRIX_CSV = ROOT / "_kie_all_models_param_matrix_vetted_clean.csv"

OUT_STANDARD = ROOT / "_kie_system_data_standard_dictionary.csv"
OUT_MAPPING = ROOT / "_kie_system_to_model_enum_mapping.csv"
OUT_SUMMARY = ROOT / "_kie_system_data_standard_summary.md"


def clean(v: str) -> str:
    return str(v or "").strip()


def parse_bool(v: str) -> Optional[bool]:
    text = clean(v).lower()
    if not text:
        return None
    if text in {"true", "1", "yes", "y", "on", "supported"}:
        return True
    if text in {"false", "0", "no", "n", "off", "unsupported"}:
        return False
    return None


def normalize_resolution(v: str) -> str:
    text = clean(v).lower().replace(" ", "")
    text = text.replace("k", "k")
    mapping = {
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
    return mapping.get(text, text.upper())


def normalize_aspect_ratio(v: str) -> Tuple[str, str]:
    text = clean(v).lower()
    if text == "landscape":
        return "16:9", "alias(landscape->16:9)"
    if text == "portrait":
        return "9:16", "alias(portrait->9:16)"
    if text == "auto":
        return "AUTO", "native"
    if re.fullmatch(r"\d{1,2}:\d{1,2}", text):
        return text, "native"
    return text.upper(), "native"


def normalize_mode(v: str) -> str:
    text = clean(v).lower()
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
    return mapping.get(text, text.upper())


def normalize_quality(v: str) -> str:
    text = clean(v).lower()
    mapping = {
        "basic": "BASIC",
        "medium": "MEDIUM",
        "high": "HIGH",
        "std": "STANDARD",
        "standard": "STANDARD",
    }
    return mapping.get(text, text.upper())


def normalize_int_like(v: str) -> str:
    text = clean(v)
    if not text:
        return ""
    m = re.search(r"\d+(?:\.\d+)?", text)
    if not m:
        return text
    num = float(m.group(0))
    if abs(num - int(num)) < 1e-9:
        return str(int(num))
    return str(num)


def normalize_output_format(v: str) -> str:
    return clean(v).upper()


def normalize_style(v: str) -> str:
    return clean(v).upper()


def normalize_reasoning(v: str) -> str:
    return clean(v).upper()


def normalize_character_orientation(v: str) -> str:
    return clean(v).upper()


def normalize_image_size(v: str) -> str:
    text = clean(v).lower()
    mapping = {
        "square": "SQUARE",
    }
    return mapping.get(text, text.upper())


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
    return mapping.get(field_path)


def normalize_value(standard_dim: str, raw_value: str) -> Tuple[str, str]:
    if standard_dim == "ASPECT_RATIO":
        v, note = normalize_aspect_ratio(raw_value)
        return v, note
    if standard_dim == "RESOLUTION_TIER":
        return normalize_resolution(raw_value), "native"
    if standard_dim == "DURATION_SECONDS":
        return normalize_int_like(raw_value), "native"
    if standard_dim == "MODE":
        return normalize_mode(raw_value), "native"
    if standard_dim == "QUALITY_LEVEL":
        return normalize_quality(raw_value), "native"
    if standard_dim == "OUTPUT_FORMAT":
        return normalize_output_format(raw_value), "native"
    if standard_dim in {"NUM_IMAGES", "UPSCALE_FACTOR", "SAFETY_TOLERANCE"}:
        return normalize_int_like(raw_value), "native"
    if standard_dim == "STYLE":
        return normalize_style(raw_value), "native"
    if standard_dim == "REASONING_EFFORT":
        return normalize_reasoning(raw_value), "native"
    if standard_dim == "CHARACTER_ORIENTATION":
        return normalize_character_orientation(raw_value), "native"
    if standard_dim == "IMAGE_SIZE_CLASS":
        return normalize_image_size(raw_value), "native"
    return clean(raw_value), "native"


def dimension_metadata() -> Dict[str, Tuple[str, str]]:
    return {
        "MODEL_ID": ("string", "模型唯一标识"),
        "ASPECT_RATIO": ("enum", "画面宽高比标准值"),
        "RESOLUTION_TIER": ("enum", "分辨率标准档位"),
        "DURATION_SECONDS": ("number", "时长（秒）"),
        "MODE": ("enum", "生成模式标准值"),
        "QUALITY_LEVEL": ("enum", "质量档位标准值"),
        "OUTPUT_FORMAT": ("enum", "输出格式标准值"),
        "IMAGE_SIZE_CLASS": ("enum", "图像尺寸类别"),
        "SOUND_SUPPORTED": ("boolean", "是否支持声音"),
        "MULTI_SHOTS_SUPPORTED": ("boolean", "是否支持多镜头"),
        "NUM_IMAGES": ("number", "单次输出图片数量"),
        "UPSCALE_FACTOR": ("number", "放大倍数"),
        "STYLE": ("enum", "风格标准值"),
        "REASONING_EFFORT": ("enum", "推理强度"),
        "CHARACTER_ORIENTATION": ("enum", "角色朝向"),
        "VOICE_ID": ("string", "音色/voice 标识"),
        "SAFETY_TOLERANCE": ("number", "安全容忍度"),
    }


def main() -> None:
    if not ENUM_CSV.exists():
        raise FileNotFoundError(f"Missing input: {ENUM_CSV}")
    if not MATRIX_CSV.exists():
        raise FileNotFoundError(f"Missing input: {MATRIX_CSV}")

    mapping_rows: List[Dict[str, str]] = []
    standard_values: Dict[str, set] = defaultdict(set)
    aliases: Dict[Tuple[str, str], set] = defaultdict(set)

    with ENUM_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            field_path = clean(r.get("field_path"))
            raw_value = clean(r.get("enum_value"))
            standard_dim = map_field_to_standard(field_path)
            if not standard_dim or not raw_value:
                continue

            std_val, norm_note = normalize_value(standard_dim, raw_value)
            if not std_val:
                continue

            confidence = "HIGH"
            if "alias(" in norm_note:
                confidence = "MEDIUM"

            row = {
                "provider": clean(r.get("provider")) or "kie",
                "model_title": clean(r.get("model_title")),
                "model_url": clean(r.get("model_url")),
                "model_key_inferred": clean(r.get("model_key_inferred")),
                "source_field": field_path,
                "source_enum_value": raw_value,
                "standard_dimension": standard_dim,
                "standard_value": std_val,
                "confidence": confidence,
                "note": norm_note,
            }
            mapping_rows.append(row)
            standard_values[standard_dim].add(std_val)
            if raw_value.lower() != std_val.lower():
                aliases[(standard_dim, std_val)].add(raw_value)

    with MATRIX_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            model = clean(r.get("model"))
            title = clean(r.get("title"))
            url = clean(r.get("url"))
            provider = "kie"

            for field, dim in [("sound", "SOUND_SUPPORTED"), ("multi_shots", "MULTI_SHOTS_SUPPORTED")]:
                raw = clean(r.get(field))
                b = parse_bool(raw)
                if b is None:
                    continue
                std_val = "TRUE" if b else "FALSE"
                mapping_rows.append(
                    {
                        "provider": provider,
                        "model_title": title,
                        "model_url": url,
                        "model_key_inferred": model,
                        "source_field": field,
                        "source_enum_value": raw,
                        "standard_dimension": dim,
                        "standard_value": std_val,
                        "confidence": "HIGH",
                        "note": "matrix_bool",
                    }
                )
                standard_values[dim].add(std_val)

    mapping_rows.sort(
        key=lambda x: (
            x["standard_dimension"],
            x["model_key_inferred"],
            x["model_title"],
            x["source_field"],
            x["source_enum_value"],
        )
    )

    with OUT_MAPPING.open("w", encoding="utf-8", newline="") as f:
        fn = [
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
        wr = csv.DictWriter(f, fieldnames=fn)
        wr.writeheader()
        wr.writerows(mapping_rows)

    meta = dimension_metadata()
    standard_rows: List[Dict[str, str]] = []
    for dim in sorted(standard_values.keys()):
        vtype, definition = meta.get(dim, ("enum", ""))
        for val in sorted(standard_values[dim]):
            alias_values = "; ".join(sorted(aliases.get((dim, val), set())))
            standard_rows.append(
                {
                    "standard_dimension": dim,
                    "standard_value": val,
                    "value_type": vtype,
                    "definition": definition,
                    "alias_values": alias_values,
                }
            )

    with OUT_STANDARD.open("w", encoding="utf-8", newline="") as f:
        fn = ["standard_dimension", "standard_value", "value_type", "definition", "alias_values"]
        wr = csv.DictWriter(f, fieldnames=fn)
        wr.writeheader()
        wr.writerows(standard_rows)

    dim_count = defaultdict(int)
    for r in mapping_rows:
        dim_count[r["standard_dimension"]] += 1

    lines = []
    lines.append("# KIE 枚举值统一标准与映射总结")
    lines.append("")
    lines.append(f"- 标准维度数: {len(standard_values)}")
    lines.append(f"- 标准值总数: {len(standard_rows)}")
    lines.append(f"- 映射关系总数: {len(mapping_rows)}")
    lines.append("")
    lines.append("## 标准维度覆盖")
    for dim in sorted(standard_values.keys()):
        lines.append(f"- {dim}: {len(standard_values[dim])} 个标准值, {dim_count[dim]} 条映射")
    lines.append("")
    lines.append("## 关键同义归一示例")
    lines.append("- ASPECT_RATIO: portrait -> 9:16, landscape -> 16:9")
    lines.append("- MODE: std/standard -> STANDARD")
    lines.append("- RESOLUTION_TIER: 720p -> P720, 1080p -> P1080, 1k -> K1")
    lines.append("")
    lines.append("## 产物文件")
    lines.append(f"- {OUT_STANDARD.name}: 系统统一数据标准字典")
    lines.append(f"- {OUT_MAPPING.name}: 标准与模型字段枚举值映射关系")
    lines.append(f"- {OUT_SUMMARY.name}: 本总结")

    OUT_SUMMARY.write_text("\n".join(lines), encoding="utf-8")

    print(f"Generated: {OUT_STANDARD}")
    print(f"Generated: {OUT_MAPPING}")
    print(f"Generated: {OUT_SUMMARY}")
    print(f"standard_dimensions={len(standard_values)} standard_values={len(standard_rows)} mappings={len(mapping_rows)}")


if __name__ == "__main__":
    main()
