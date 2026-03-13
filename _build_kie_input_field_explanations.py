import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "_kie_input_enum_values_catalog_purified.csv"
OUT_CSV = ROOT / "_kie_input_enum_field_explanations.csv"
OUT_MD = ROOT / "_kie_input_enum_field_explanations.md"

FIELD_EXPLANATIONS = {
    "paths.post.model": "模型标识。用于指定调用的具体模型路由，直接决定能力、价格和可用参数集合。",
    "paths.post.reasoning_effort": "推理强度档位。用于控制模型在回答时的推理深度与耗时，通常在速度与质量之间做权衡。",
    "paths.post.input.aspect_ratio": "画面宽高比。决定输出画面的构图比例，例如 16:9、9:16、1:1。",
    "paths.post.input.character_orientation": "角色朝向或人物方向控制。用于约束角色在画面中的朝向表现。",
    "paths.post.input.duration": "时长参数（秒）。用于控制生成内容的持续时长。",
    "paths.post.input.image_resolution": "图像分辨率档位。用于指定输出图像清晰度等级。",
    "paths.post.input.image_size": "图像尺寸参数。用于控制输出图像尺寸或比例档位。",
    "paths.post.input.mode": "生成模式。用于切换不同生成策略或风格行为（如标准/创意等模式）。",
    "paths.post.input.n_frames": "帧数参数。通常用于视频生成，决定输出的视频帧数档位。",
    "paths.post.input.num_images": "输出图片数量。控制一次请求返回的图片张数。",
    "paths.post.input.output_format": "输出格式。指定结果文件或返回体格式（如 png、jpg、webp 等）。",
    "paths.post.input.quality": "质量档位。控制生成质量与速度成本的平衡。",
    "paths.post.input.resolution": "视频/图像分辨率。决定输出清晰度（如 720p、1080p）。",
    "paths.post.input.safety_tolerance": "安全容忍度。控制内容安全过滤的严格程度。",
    "paths.post.input.size": "通用尺寸参数。用于指定输出大小或比例。",
    "paths.post.input.style": "风格参数。用于约束输出的视觉或叙事风格。",
    "paths.post.input.upscale_factor": "放大倍数。用于上采样或超分，控制分辨率提升比例。",
    "paths.post.input.voice": "音色/语音选择。用于指定语音合成时使用的声音 ID 或音色标签。",
}


def load_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split_values(raw: str):
    if not raw:
        return []
    return [x.strip() for x in raw.split(";") if x.strip()]


def main():
    rows = load_rows(SRC)

    agg = {}
    pages = defaultdict(set)
    vals = defaultdict(set)

    for r in rows:
        field = (r.get("field_path") or "").strip()
        title = (r.get("title") or "").strip()
        if not field:
            continue
        pages[field].add(title)
        for v in split_values(r.get("enum_values") or ""):
            vals[field].add(v)

    fields = sorted(pages.keys())

    out_rows = []
    for field in fields:
        enum_values = sorted(vals[field])
        sample = "; ".join(enum_values[:12])
        if len(enum_values) > 12:
            sample += f"; ...(+{len(enum_values)-12})"

        out_rows.append(
            {
                "field_path": field,
                "page_count": len(pages[field]),
                "enum_value_count": len(enum_values),
                "sample_enum_values": sample,
                "explanation": FIELD_EXPLANATIONS.get(field, "待补充说明"),
            }
        )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "field_path",
                "page_count",
                "enum_value_count",
                "sample_enum_values",
                "explanation",
            ],
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(out_rows)

    lines = []
    lines.append("# KIE Input Enum Fields Explanations")
    lines.append("")
    lines.append(f"- Total deduplicated fields: {len(out_rows)}")
    lines.append("")
    lines.append("| field_path | page_count | enum_value_count | sample_enum_values | explanation |")
    lines.append("|---|---:|---:|---|---|")
    for r in out_rows:
        row = [
            r["field_path"],
            str(r["page_count"]),
            str(r["enum_value_count"]),
            r["sample_enum_values"],
            r["explanation"],
        ]
        row = [x.replace("|", "/") for x in row]
        lines.append("| " + " | ".join(row) + " |")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"WROTE {OUT_CSV}")
    print(f"WROTE {OUT_MD}")
    print(f"FIELDS {len(out_rows)}")


if __name__ == "__main__":
    main()
