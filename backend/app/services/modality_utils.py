"""
Utilities for the new JSON-based modality field on SystemAPISetting.

Modality JSON schema (v2):
{
    "generation_modes": ["t2i", "i2i"],           # 生成方式(缩写列表)，筛选匹配核心字段
    "max_resolution": "2048x2048",                 # 支持的最高输出分辨率
    "aspect_ratios": ["1:1", "16:9", "9:16"],     # 支持的画幅/宽高比列表
    "has_audio": false,                             # 是否支持音频(视频模型区分有声/无声)
    "max_duration": 10,                             # 最大生成时长(秒), null表示不限
    "base_model": "seedream-4.5",                  # 基础模型名称
    "model_version": "v4.5",                       # 模型版本号
    "model_type": "diffusion",                     # 架构: diffusion / transformer / autoregressive
    "input_formats": ["text", "image"],            # 可接受的输入格式
    "output_format": "image"                       # 输出格式: image / video / audio / text
}

generation_modes 缩写对照:
    t2i = text-to-image   (文生图)
    i2i = image-to-image  (图生图)
    t2v = text-to-video   (文生视频)
    i2v = image-to-video  (图生视频)
    v2v = video-to-video  (视频转视频)
    t2a = text-to-audio   (文生音频)
    a2t = audio-to-text   (语音识别)
    a2a = audio-to-audio  (音频转音频)
    s2v = speech-to-video (语音驱动视频/数字人)
    i2t = image-to-text   (图像理解/描述)

Tags JSON schema (独立 tags 列, string[]):
    ["真人写实", "局部重绘", "高清", "快速生成", "anime", "3D"]
    用途: 前端按标签筛选、AI Assistant推荐参考、管理员标注模型特点。
"""

from typing import Dict, Any, Optional, List

# ── Long-form ↔ abbreviation mapping ──
MODALITY_LONG_TO_SHORT = {
    "text-to-image": "t2i",
    "image-to-image": "i2i",
    "text-to-video": "t2v",
    "image-to-video": "i2v",
    "video-to-video": "v2v",
    "text-to-audio": "t2a",
    "audio-to-text": "a2t",
    "audio-to-audio": "a2a",
    "speech-to-video": "s2v",
    "image-to-text": "i2t",
}
MODALITY_SHORT_TO_LONG = {v: k for k, v in MODALITY_LONG_TO_SHORT.items()}


def normalize_modality_query(modality: str) -> str:
    """Normalize a modality query to short form (e.g. 'text-to-image' → 't2i')."""
    m = modality.strip().lower()
    return MODALITY_LONG_TO_SHORT.get(m, m)


def get_generation_modes(modality_json: Any) -> List[str]:
    """Extract generation_modes list from a modality JSON value.

    Handles:
    - dict with "generation_modes" key  → returns the list
    - legacy string "text-to-image,image-to-image" → converts to ["t2i", "i2i"]
    - None / empty → returns []
    """
    if modality_json is None:
        return []
    if isinstance(modality_json, dict):
        modes = modality_json.get("generation_modes") or []
        return [m.strip().lower() for m in modes if m and str(m).strip()]
    if isinstance(modality_json, str):
        raw = modality_json.strip()
        if not raw:
            return []
        tokens = [t.strip().lower() for t in raw.split(",") if t.strip()]
        return [MODALITY_LONG_TO_SHORT.get(t, t) for t in tokens]
    return []


def modality_matches(row_modality: Any, requested_modality: str) -> bool:
    """Check if a row's modality is compatible with the requested modality.

    Rules:
    - If the row has no generation_modes (empty/null), it is compatible with ALL.
    - Otherwise the requested modality (long or short form) must appear in the list.
    """
    modes = get_generation_modes(row_modality)
    if not modes:
        return True
    query = normalize_modality_query(requested_modality)
    return query in modes


def migrate_legacy_modality_string(old_value: Optional[str]) -> Optional[Dict[str, Any]]:
    """Convert a legacy string modality value to the new JSON structure.

    Example: "text-to-image,image-to-image"
        → {"generation_modes": ["t2i", "i2i"]}
    """
    if old_value is None:
        return None

    raw = old_value.strip()
    if not raw:
        return None

    tokens = [t.strip().lower() for t in raw.split(",") if t.strip()]
    modes = [MODALITY_LONG_TO_SHORT.get(t, t) for t in tokens]

    return {"generation_modes": modes} if modes else None
