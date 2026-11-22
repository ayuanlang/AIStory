# -*- coding: utf-8 -*-
"""Submit a shot's storyboard-preview grid as a video reference image."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

PANEL_LAYOUTS: Dict[str, Dict[str, str]] = {
    "2panel": {
        "label": "二画格",
        "reading": "从左到右：左边第1格，右边第2格",
        "sequence": "1→2",
        "last_cn": "第2格",
        "last_en": "2",
    },
    "4panel": {
        "label": "四宫格",
        "reading": "从左到右、从上到下：左上第1格，右上第2格，左下第3格，右下第4格",
        "sequence": "1→2→3→4",
        "last_cn": "第4格",
        "last_en": "4",
    },
    "6panel": {
        "label": "六画格",
        "reading": "从左到右、从上到下：上排从左到右是第1、2、3格，下排从左到右是第4、5、6格",
        "sequence": "1→2→3→4→5→6",
        "last_cn": "第6格",
        "last_en": "6",
    },
    "9panel": {
        "label": "九宫格",
        "reading": "从左到右、从上到下：上排第1、2、3格，中排第4、5、6格，下排第7、8、9格",
        "sequence": "1→2→3→4→5→6→7→8→9",
        "last_cn": "第9格",
        "last_en": "9",
    },
}

_GENERIC_LAYOUT = {
    "label": "多画格",
    "reading": "从左到右、再从上到下，以每一格上方的阿拉伯数字为准",
    "sequence": "数字从小到大",
    "last_cn": "数字最大的那一格",
    "last_en": "the highest number",
}

_NOTE_RE = re.compile(
    r"\n*【分镜预览多画格】[\s\S]*?Do not output a split-screen, grid lines, or the panel numbers\.",
    re.IGNORECASE,
)


def resolve_multi_panel_preview(tech: Any) -> Tuple[str, str]:
    """Return (image url, preset key). Preset is empty when it is not a known grid."""
    notes = tech if isinstance(tech, dict) else {}
    url = str(notes.get("multi_panel_image_url") or notes.get("storyboard_url") or "").strip()
    preset = str(notes.get("multi_panel_image_preset") or "").strip()
    if preset not in PANEL_LAYOUTS:
        preset = ""
    return url, preset


def _dedupe_urls(urls: Sequence[str]) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for raw in urls or []:
        url = str(raw or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        cleaned.append(url)
    return cleaned


def append_preview_ref(urls: Sequence[str], preview_url: str) -> List[str]:
    cleaned = _dedupe_urls(urls)
    preview = str(preview_url or "").strip()
    if preview and preview not in cleaned:
        cleaned.append(preview)
    return cleaned


def limit_refs_keeping_preview(
    urls: Sequence[str],
    limit: Optional[int],
    preview_url: str,
) -> List[str]:
    """Keep the storyboard grid when the provider cap would otherwise drop the tail."""
    cleaned = _dedupe_urls(urls)
    preview = str(preview_url or "").strip()
    if limit is None:
        return cleaned
    try:
        cap = int(limit)
    except (TypeError, ValueError):
        return cleaned
    if cap <= 0:
        return []
    if not preview or preview not in cleaned or len(cleaned) <= cap:
        return cleaned[:cap]
    others = [url for url in cleaned if url != preview]
    return others[: cap - 1] + [preview]


def build_multi_panel_order_note(index: int, preset: str) -> str:
    layout = PANEL_LAYOUTS.get(str(preset or "").strip()) or _GENERIC_LAYOUT
    image_tag = f"@Image{int(index)}"
    return (
        f"【分镜预览多画格】参考{image_tag}是本镜头的分镜预览{layout['label']}，不是要原样输出的拼图。"
        f"阅读顺序{layout['reading']}。"
        f"第1格是镜头起始，{layout['last_cn']}是镜头结束。"
        f"按{layout['sequence']}把动作做成一条连续视频，不要输出分格、格线、数字或分屏。"
        f" Reference image {image_tag} is this shot's storyboard grid. "
        f"Read the panels left to right, then top to bottom, in the order {layout['sequence']}. "
        f"Panel 1 is the opening and panel {layout['last_en']} is the ending. "
        f"Animate that order as one continuous shot. "
        f"Do not output a split-screen, grid lines, or the panel numbers."
    )


def append_multi_panel_order_note(
    prompt: str,
    image_urls: Sequence[str],
    preview_url: str,
    preset: str,
) -> Tuple[str, int]:
    """Attach the reading-order note when the grid is in the submitted image list.

    Returns (prompt, 1-based index). Index is 0 when the grid was not submitted.
    """
    preview = str(preview_url or "").strip()
    urls = _dedupe_urls(image_urls)
    text = _NOTE_RE.sub("", str(prompt or "")).strip()
    if not preview or preview not in urls:
        return text, 0
    index = urls.index(preview) + 1
    note = build_multi_panel_order_note(index, preset)
    if not text:
        return note, index
    return f"{text}\n\n{note}", index
