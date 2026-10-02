# -*- coding: utf-8 -*-
"""Burn edited shop text, hotlines, and seals with libass.

The video model does not draw these glyphs. A real font writes the lines the
user confirmed. The seal is its own layer beside the line.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_P_HEAD_RE = re.compile(
    r"\((P\d+)\s+(\d+(?:\.\d+)?)s\s*[–—\-]\s*(\d+(?:\.\d+)?)s\)"
)
_QUOTE_RE = re.compile(r"「([^」]+)」|\"([^\"]+)\"")
_PHONE_RE = re.compile(r"\d{3,4}-?\d{5,8}")
_EN_RE = re.compile(r"英=「([^」]+)」|英文小字「([^」]+)」")
_SEAL_TEXT_RE = re.compile(r"(?:印文|印章文|闲章|朱文)=「([^」]+)」")
_GLYPH_LOCK_RE = re.compile(r"逐字=[^｜|\n]+")
_VOICE_RE = re.compile(r"(?:Voiceover|旁白|口播)\s*[:：]\s*(.+)", re.IGNORECASE)
_FONT_MAP = {
    "楷体": "KaiTi",
    "华文楷体": "KaiTi",
    "宋体": "SimSun",
    "黑体": "SimHei",
    "微软雅黑": "Microsoft YaHei",
    "kaiti": "KaiTi",
    "simsun": "SimSun",
    "simhei": "SimHei",
}
_DESIGNATED_COPY_RE = re.compile(
    r"(?:画幅叠出片内图形花字|片内图形花字|文案)\s*[=＝]?\s*「([^」]+)」"
)
_REAL_BURN_MARK_RE = re.compile(r"(?<!标记)烧录=libass")
_SIZE_RATIO = {"大": 0.068, "中": 0.046, "小": 0.030}
_ASS_FILTER_CACHE: Optional[bool] = None


def _usable_copy(quote: str) -> bool:
    text = str(quote or "").strip()
    return len(text) > 1 and text not in {"家", "无", "X家"}


def _is_hotline_copy(quote: str) -> bool:
    text = str(quote or "").strip()
    return bool(text and (_PHONE_RE.search(text) or "热线" in text or "电话" in text))


def _quote_needs_exact_burn(quote: str) -> bool:
    text = str(quote or "").strip()
    if not _usable_copy(text):
        return False
    if _is_hotline_copy(text):
        return True
    if "家" in text and "万家" not in text:
        return True
    return False


def _block_has_voiceover(block: str) -> bool:
    for match in _VOICE_RE.finditer(block or ""):
        tail = str(match.group(1) or "").strip().strip("。.")
        if tail and tail not in {"无", "空", "none", "None"}:
            return True
    return False


def _append_unique(parts: List[str], text: str) -> None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return
    for existing in parts:
        if cleaned == existing or cleaned in existing or existing in cleaned:
            return
    parts.append(cleaned)


def _block_needs_libass(block: str) -> bool:
    text = str(block or "")
    if not text.strip() or _block_has_voiceover(text):
        return False
    main, companion = _pick_main_and_companion(text)
    if not main and not companion and not _seal_text(text):
        return False
    if _DESIGNATED_COPY_RE.search(text) or "上屏=字卡专镜" in text:
        return True
    return _REAL_BURN_MARK_RE.search(text) is not None


def _iter_blocks(script: str):
    text = str(script or "")
    matches = list(_P_HEAD_RE.finditer(text))
    if not matches:
        yield 0.0, None, text
        return
    for index, match in enumerate(matches):
        start = float(match.group(2))
        end = float(match.group(3))
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        yield start, end, text[match.start():body_end]


def _parse_duration(value: Any, default: float = 4.0) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    if not match:
        return default
    try:
        return max(0.4, float(match.group(1)))
    except ValueError:
        return default


def _pick_main_and_companion(block: str) -> tuple[str, str]:
    designated = [quote.strip() for quote in _DESIGNATED_COPY_RE.findall(block) if _usable_copy(quote)]
    quotes = [a or b for a, b in _QUOTE_RE.findall(block)]
    en_quotes = [a or b for a, b in _EN_RE.findall(block) if _usable_copy(a or b)]
    phones = _PHONE_RE.findall(block)
    main = ""
    for quote in designated:
        if not _is_hotline_copy(quote):
            main = quote
            break
    if not main:
        for quote in quotes:
            cleaned = quote.strip()
            if not _usable_copy(cleaned) or _is_hotline_copy(cleaned):
                continue
            if _quote_needs_exact_burn(cleaned) and "家" in cleaned and "万家" not in cleaned:
                main = cleaned
                break
    if not main and phones and not any(_is_hotline_copy(quote) for quote in designated):
        main = phones[0]
    companion_parts: List[str] = []
    for quote in designated:
        if quote != main and _is_hotline_copy(quote):
            _append_unique(companion_parts, quote)
    for quote in en_quotes:
        if quote != main:
            _append_unique(companion_parts, quote)
    for phone in phones:
        if phone == main or any(phone in part for part in companion_parts):
            continue
        label = "垂询热线：" if ("热线" in block or "电话" in block) else ""
        _append_unique(companion_parts, f"{label}{phone}" if label else phone)
    return main, "\n".join(companion_parts)


def _place_and_size(block: str) -> tuple[str, str, bool, str]:
    place = "中"
    if "位置=画右" in block or "落位=画右" in block:
        place = "画右"
    elif "位置=画左" in block or "落位=画左" in block:
        place = "画左"
    size = "中"
    if "字级=大" in block:
        size = "大"
    elif "字级=小" in block:
        size = "小"
    font = "KaiTi"
    font_match = re.search(r"字体=([^｜|\n]+)", block)
    if font_match:
        raw_font = font_match.group(1).strip()
        font = _FONT_MAP.get(raw_font) or _FONT_MAP.get(raw_font.lower()) or "KaiTi"
    return place, size, "排向=竖" in block, font


def extract_libass_events(script: str, duration: Any = None) -> List[Dict[str, Any]]:
    """On-screen flower copy. Voiced shots and the quality-footer 「家」 stay off the burn."""
    fallback = _parse_duration(duration, 4.0)
    events: List[Dict[str, Any]] = []
    for start, end, block in _iter_blocks(script):
        if not _block_needs_libass(block):
            continue
        main, companion = _pick_main_and_companion(block)
        seal = _seal_text(block)
        if not main and not companion and not seal:
            continue
        place, size, vertical, font = _place_and_size(block)
        stop = float(end) if end is not None else float(start) + fallback
        if stop <= start:
            stop = start + fallback
        events.append({
            "text": main,
            "companion": companion,
            "seal": seal,
            "start": float(start),
            "end": float(stop),
            "place": place,
            "size": size,
            "vertical": vertical,
            "font": font,
        })
    return _dedupe_burn_events(events)


def _dedupe_burn_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One copy of the same line. A second pass must not stack the same glyphs."""
    kept: List[Dict[str, Any]] = []
    for event in events:
        text = str(event.get("text") or "").strip()
        start = float(event.get("start") or 0)
        end = float(event.get("end") or 0)
        merged = False
        for prev in kept:
            prev_text = str(prev.get("text") or "").strip()
            if text and prev_text and text != prev_text:
                continue
            prev_start = float(prev.get("start") or 0)
            prev_end = float(prev.get("end") or 0)
            if end <= prev_start or start >= prev_end:
                continue
            prev["start"] = min(prev_start, start)
            prev["end"] = max(prev_end, end)
            if not str(prev.get("companion") or "").strip():
                prev["companion"] = event.get("companion") or ""
            if not str(prev.get("seal") or "").strip():
                prev["seal"] = event.get("seal") or ""
            merged = True
            break
        if not merged:
            kept.append(dict(event))
    return kept


def _seal_text(block: str) -> str:
    match = _SEAL_TEXT_RE.search(str(block or ""))
    return match.group(1).strip() if match else ""


def _blank_burn_line(duration: Any = None) -> Dict[str, Any]:
    return {
        "text": "",
        "companion": "",
        "seal": "",
        "start": 0.0,
        "end": _parse_duration(duration, 4.0),
        "place": "中",
        "size": "大",
        "vertical": False,
        "font": "KaiTi",
    }


def suggest_flower_burn_lines(script: str, duration: Any = None) -> List[Dict[str, Any]]:
    events = extract_libass_events(script, duration)
    return events or [_blank_burn_line(duration)]


def normalize_manual_burn_lines(lines: Any, duration: Any = None) -> List[Dict[str, Any]]:
    fallback = _parse_duration(duration, 4.0)
    events: List[Dict[str, Any]] = []
    for raw in lines or []:
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        elif hasattr(raw, "dict"):
            raw = raw.dict()
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        companion = str(raw.get("companion") or "").strip()
        seal = str(raw.get("seal") or "").strip()
        if not text and not companion and not seal:
            continue
        try:
            start = max(0.0, float(raw.get("start") or 0))
        except (TypeError, ValueError):
            start = 0.0
        try:
            end = float(raw.get("end") or 0)
        except (TypeError, ValueError):
            end = 0.0
        if end <= start:
            end = start + fallback
        size = str(raw.get("size") or "大").strip()
        if size not in {"大", "中", "小"}:
            size = "大"
        place = str(raw.get("place") or "中").strip()
        if place not in {"中", "画左", "画右"}:
            place = "中"
        events.append({
            "text": text,
            "companion": companion,
            "seal": seal,
            "start": start,
            "end": end,
            "place": place,
            "size": size,
            "vertical": bool(raw.get("vertical")),
            "font": "KaiTi",
        })
    return events


def _ass_time(seconds: float) -> str:
    cs_total = int(round(max(0.0, float(seconds)) * 100))
    hours, cs_total = divmod(cs_total, 360000)
    minutes, cs_total = divmod(cs_total, 6000)
    secs, cs = divmod(cs_total, 100)
    return f"{int(hours)}:{int(minutes):02d}:{int(secs):02d}.{int(cs):02d}"


def _ass_escape(text: str) -> str:
    return str(text or "").replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _layout_text(text: str, vertical: bool) -> str:
    raw = _ass_escape(text)
    if not vertical:
        return raw.replace("\n", r"\N")
    pieces = [ch for ch in raw if ch not in {"\n", "\r"}]
    return r"\N".join(pieces)


def _pos(width: int, height: int, place: str, size: str, companion: bool) -> tuple[int, int, int]:
    ratio = _SIZE_RATIO.get(size, _SIZE_RATIO["中"])
    fontsize = max(28, int(height * ratio))
    if place == "画右":
        x = int(width * 0.78)
    elif place == "画左":
        x = int(width * 0.22)
    else:
        x = int(width / 2)
    y = int(height * 0.40)
    if companion:
        main_fs = fontsize
        fontsize = max(16, int(main_fs * 0.34))
        y = min(int(height * 0.82), y + int(main_fs * 1.45))
    return x, y, fontsize


def _glyph_span(text: str, fontsize: int, tracking: int) -> int:
    span = 0
    for ch in str(text or ""):
        if ch in {"\n", "\r"}:
            continue
        span += int(fontsize * (1.0 if ord(ch) > 127 else 0.56)) + tracking
    return span


_CJK_FONT_CANDIDATES: Tuple[Tuple[str, str], ...] = (
    ("simkai.ttf", "KaiTi"),
    ("STKAITI.TTF", "STKaiti"),
    ("wqy-microhei.ttc", "WenQuanYi Micro Hei"),
    ("simhei.ttf", "SimHei"),
    ("msyh.ttc", "Microsoft YaHei"),
    ("NotoSansCJK-Regular.ttc", "Noto Sans CJK SC"),
    ("NotoSansCJKsc-Regular.otf", "Noto Sans CJK SC"),
)


def _bundled_cjk_font_dir() -> str:
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts"))


def _cjk_font_search_dirs() -> List[str]:
    dirs: List[str] = []
    windir = os.environ.get("WINDIR")
    if windir:
        dirs.append(os.path.join(windir, "Fonts"))
    dirs.append(_bundled_cjk_font_dir())
    dirs.extend([
        "/usr/share/fonts/truetype/noto",
        "/usr/share/fonts/opentype/noto",
        "/usr/share/fonts/noto-cjk",
        "/usr/share/fonts/truetype",
        "/usr/share/fonts/truetype/wqy",
    ])
    return dirs


def stage_burn_font(work_dir: str) -> str:
    """Copy one CJK font next to the ASS file and return its family name.

    libass drops a Windows path in fontsdir: the drive colon is parsed as a
    filter separator, the font never loads, and Chinese becomes empty boxes.
    """
    fonts_dir = os.path.join(work_dir, "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    for folder in _cjk_font_search_dirs():
        for filename, family in _CJK_FONT_CANDIDATES:
            src = os.path.join(folder, filename)
            if not os.path.isfile(src):
                continue
            shutil.copyfile(src, os.path.join(fonts_dir, filename))
            return family
    raise RuntimeError("找不到可烧录的中文字体。请确认已部署 backend/app/assets/fonts/wqy-microhei.ttc")


def build_ass(
    events: List[Dict[str, Any]],
    *,
    width: int = 1920,
    height: int = 1080,
    font_name: Optional[str] = None,
) -> str:
    width = max(16, int(width or 1920))
    height = max(16, int(height or 1080))
    font = str(font_name or "").strip()
    if not font:
        font = "SimHei"
        for event in events:
            if event.get("font"):
                font = str(event["font"])
                break
    header = "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Flower,{font},64,&H00F7F5F3,&H000000FF,&H00181020,&H00000000,0,0,0,0,100,100,0,0,1,2,0,5,60,60,40,1",
        f"Style: FlowerSmall,{font},28,&H004EA4D9,&H000000FF,&H00181020,&H00000000,0,0,0,0,100,100,0,0,1,1,0,5,60,60,40,1",
        f"Style: FlowerSeal,{font},42,&H003A3AC2,&H000000FF,&H003A3AC2,&H00000000,0,0,0,0,100,100,0,0,1,3,0,5,20,20,20,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])
    lines = [header]
    for event in events:
        start = _ass_time(float(event.get("start") or 0))
        end = _ass_time(float(event.get("end") or 0))
        place = str(event.get("place") or "中")
        size = str(event.get("size") or "中")
        vertical = bool(event.get("vertical"))
        main = str(event.get("text") or "").strip()
        main_x, main_y, main_size = _pos(width, height, place, size, companion=False)
        tracking = max(8, int(main_size * 0.16))
        if main:
            shown = _layout_text(main, vertical)
            lines.append(
                f"Dialogue: 0,{start},{end},Flower,,0,0,0,,{{\\an5\\fs{main_size}\\fsp{tracking}\\bord2\\shad0\\blur0.3\\1c&H00F7F5F3&\\3c&H00181020&\\pos({main_x},{main_y})}}{shown}"
            )
            rule_w = min(_glyph_span(main, main_size, tracking), int(width * 0.46))
            rule_h = max(2, int(main_size * 0.028))
            rule_x = max(8, main_x - rule_w // 2)
            rule_y = main_y + int(main_size * 0.78)
            rule = f"m 0 0 l {rule_w} 0 l {rule_w} {rule_h} l 0 {rule_h}"
            lines.append(
                f"Dialogue: 0,{start},{end},FlowerSmall,,0,0,0,,{{\\an7\\pos({rule_x},{rule_y})\\p1\\bord0\\shad0\\1c&H004EA4D9&}}{rule}"
            )
        companion = str(event.get("companion") or "").strip()
        if companion:
            x, y, fontsize = _pos(width, height, place, size, companion=True)
            shown = _layout_text(companion, False)
            lines.append(
                f"Dialogue: 0,{start},{end},FlowerSmall,,0,0,0,,{{\\an5\\fs{fontsize}\\fsp3\\bord1\\shad0\\1c&H004EA4D9&\\3c&H00181020&\\pos({x},{y})}}{shown}"
            )
        seal = str(event.get("seal") or "").strip()
        if seal:
            chars = [ch for ch in seal if ch not in {"\n", "\r"}]
            glyph_count = max(1, len(chars))
            seal_size = max(28, int(main_size * 0.48))
            pad = max(10, int(seal_size * 0.32))
            gap = max(4, int(seal_size * 0.08))
            side = pad * 2 + seal_size * glyph_count + gap * max(0, glyph_count - 1)
            half = side // 2
            half_span = _glyph_span(main, main_size, tracking) // 2
            seal_x = min(width - half - 16, main_x + half_span + half + int(main_size * 0.55))
            seal_y = main_y
            box_x = max(8, seal_x - half)
            box_y = max(8, seal_y - half)
            chop = f"m 0 0 l {side} 0 l {side} {side} l 0 {side}"
            lines.append(
                f"Dialogue: 1,{start},{end},FlowerSeal,,0,0,0,,{{\\an7\\pos({box_x},{box_y})\\p1\\bord3\\shad0\\1a&HFF&\\3c&H003A3AC2&}}{chop}"
            )
            first_y = box_y + pad + seal_size // 2
            step = seal_size + gap
            for index, ch in enumerate(chars):
                cy = first_y + index * step
                lines.append(
                    f"Dialogue: 2,{start},{end},FlowerSeal,,0,0,0,,{{\\an5\\pos({seal_x},{cy})\\p0\\bord0\\shad0\\1c&H003A3AC2&\\fs{seal_size}}}{_ass_escape(ch)}"
                )
    return "\n".join(lines) + "\n"


def _strip_block(block: str) -> str:
    if not _block_needs_libass(block):
        return block
    main, companion = _pick_main_and_companion(block)
    text = block
    if main:
        text = text.replace(main, "")
    for part in companion.split("\n"):
        cleaned = part.replace("垂询热线：", "").strip()
        if cleaned:
            text = text.replace(cleaned, "")
        if part and part != cleaned:
            text = text.replace(part, "")
    text = _SEAL_TEXT_RE.sub(r"印文=「」", text)
    text = _GLYPH_LOCK_RE.sub("逐字=后期烧录", text)
    text = text.replace("禁何乐乐享", "禁复写")
    note = "本P店号与热线禁止生成字形，由后期烧录。"
    if note not in text:
        text = f"{text.rstrip()}{note}\n"
    return text


def strip_libass_glyphs_from_prompt(script: str) -> str:
    """Drop exact shop/hotline glyphs from the string sent to the video model."""
    text = str(script or "")
    if not text:
        return text
    matches = list(_P_HEAD_RE.finditer(text))
    if not matches:
        return _strip_block(text)
    parts = [text[:matches[0].start()]]
    for index, match in enumerate(matches):
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():body_end]
        parts.append(text[match.start():match.end()])
        parts.append(_strip_block(body))
    return "".join(parts)


def _ffmpeg_filter_path(path: str) -> str:
    normalized = os.path.abspath(path).replace("\\", "/")
    return normalized.replace(":", r"\:").replace("'", r"\'")


def ffmpeg_supports_ass() -> bool:
    global _ASS_FILTER_CACHE
    if _ASS_FILTER_CACHE is not None:
        return _ASS_FILTER_CACHE
    try:
        import subprocess

        from app.services.video_service import _resolve_ffmpeg_exe

        exe = _resolve_ffmpeg_exe()
        completed = subprocess.run(
            [exe, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        blob = f"{completed.stdout}\n{completed.stderr}"
        _ASS_FILTER_CACHE = "subtitles" in blob or re.search(r"\bass\b", blob) is not None
    except Exception as exc:
        logger.warning("libass filter probe failed: %s", exc)
        _ASS_FILTER_CACHE = False
    return bool(_ASS_FILTER_CACHE)


def resolve_cjk_font_file() -> str:
    for folder in _cjk_font_search_dirs():
        for filename, _family in _CJK_FONT_CANDIDATES:
            src = os.path.join(folder, filename)
            if os.path.isfile(src):
                return src
    raise RuntimeError("找不到可烧录的中文字体。请确认已部署 backend/app/assets/fonts/wqy-microhei.ttc")


def _open_cjk_font(font_path: str, size: int):
    from PIL import ImageFont

    size = max(12, int(size))
    return ImageFont.truetype(font_path, size, index=0)


def _glyph_advance(font: Any, ch: str, tracking: int) -> int:
    width = int(round(font.getlength(ch))) if hasattr(font, "getlength") else (font.getbbox(ch)[2] - font.getbbox(ch)[0])
    extra = tracking // 3 if ch in "，。、：:；;·,." else tracking
    return max(1, width) + max(0, extra)


def _tracked_width(font: Any, text: str, tracking: int) -> int:
    chars = [ch for ch in str(text or "") if ch not in {"\n", "\r"}]
    if not chars:
        return 0
    return sum(_glyph_advance(font, ch, tracking) for ch in chars) - (
        tracking // 3 if chars[-1] in "，。、：:；;·,." else tracking
    )


def _draw_tracked(draw: Any, text: str, font: Any, center: Tuple[int, int], fill: Tuple[int, int, int, int], tracking: int, vertical: bool = False) -> None:
    chars = [ch for ch in str(text or "") if ch not in {"\n", "\r"}]
    if not chars:
        return
    if vertical:
        step = int(getattr(font, "size", 32) * 1.05)
        top = center[1] - step * (len(chars) - 1) / 2
        for index, ch in enumerate(chars):
            draw.text((center[0], top + index * step), ch, font=font, fill=fill, anchor="mm")
        return
    cursor = center[0] - _tracked_width(font, "".join(chars), tracking) / 2
    for ch in chars:
        advance = _glyph_advance(font, ch, tracking)
        ink = advance - (tracking // 3 if ch in "，。、：:；;·,." else tracking)
        draw.text((cursor + ink / 2, center[1]), ch, font=font, fill=fill, anchor="mm")
        cursor += advance


def _paint_tracked(
    plate: Any,
    text: str,
    font: Any,
    center: Tuple[int, int],
    fill: Tuple[int, int, int, int],
    tracking: int,
    *,
    vertical: bool = False,
    shadow: bool = True,
) -> None:
    from PIL import Image, ImageDraw, ImageFilter

    if shadow and text:
        layer = Image.new("RGBA", plate.size, (0, 0, 0, 0))
        offset = max(1, int(getattr(font, "size", 32) / 22))
        _draw_tracked(
            ImageDraw.Draw(layer),
            text,
            font,
            (center[0], center[1] + offset),
            (28, 20, 14, 150),
            tracking,
            vertical,
        )
        plate.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=max(1.4, getattr(font, "size", 32) / 16))))
    _draw_tracked(ImageDraw.Draw(plate), text, font, center, fill, tracking, vertical)


def _fit_seal_font(font_path: str, cell: int, chars: List[str]) -> Any:
    size = max(12, int(cell))
    font = _open_cjk_font(font_path, size)
    for _ in range(14):
        fits = True
        for ch in chars:
            box = font.getbbox(ch)
            if (box[2] - box[0]) > cell * 0.92 or (box[3] - box[1]) > cell * 0.92:
                fits = False
                break
        if fits:
            return font
        size = max(12, int(size * 0.9))
        font = _open_cjk_font(font_path, size)
    return font


def render_title_plate(
    event: Dict[str, Any],
    *,
    width: int,
    height: int,
    font_path: str,
) -> Any:
    """Typeset one title card as a transparent image. Glyphs come from the font file."""
    from PIL import Image, ImageDraw

    width = max(16, int(width))
    height = max(16, int(height))
    plate = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    place = str(event.get("place") or "中")
    size_name = str(event.get("size") or "中")
    ratio = {"大": 0.062, "中": 0.046, "小": 0.032}.get(size_name, 0.046)
    main_size = max(28, int(height * ratio))
    if place == "画右":
        main_x = int(width * 0.72)
    elif place == "画左":
        main_x = int(width * 0.28)
    else:
        main_x = width // 2
    main_y = int(height * 0.40)
    ivory = (246, 242, 232, 255)
    gold = (184, 138, 58, 235)
    cinnabar = (168, 42, 36, 255)
    main = str(event.get("text") or "").strip()
    vertical = bool(event.get("vertical"))
    title_font = _open_cjk_font(font_path, main_size)
    tracking = max(6, int(main_size * 0.22))
    if main:
        _paint_tracked(plate, main, title_font, (main_x, main_y), ivory, tracking, vertical=vertical)
        title_w = _tracked_width(title_font, main, tracking) if not vertical else main_size
        rule_w = max(main_size, int(title_w * 0.62))
        rule_h = max(2, int(main_size * 0.018))
        rule_x = main_x - rule_w // 2
        rule_y = main_y + int(main_size * 0.70)
        ImageDraw.Draw(plate).rectangle((rule_x, rule_y, rule_x + rule_w, rule_y + rule_h), fill=gold)
    else:
        title_w = 0
        rule_y = main_y
    companion = str(event.get("companion") or "").strip()
    if companion:
        companion_size = max(16, int(main_size * 0.34))
        companion_font = _open_cjk_font(font_path, companion_size)
        companion_y = rule_y + int(main_size * 0.62)
        for line in [part.strip() for part in companion.splitlines() if part.strip()]:
            _paint_tracked(
                plate,
                line,
                companion_font,
                (main_x, companion_y),
                gold,
                max(2, int(companion_size * 0.08)),
            )
            companion_y += int(companion_size * 1.35)
    seal = str(event.get("seal") or "").strip()
    chars = [ch for ch in seal if ch not in {"\n", "\r"}]
    if chars:
        glyph_count = len(chars)
        side = int(main_size * (1.02 + 0.58 * max(0, glyph_count - 1)))
        side = max(side, int(main_size * 1.15))
        border = max(4, side // 13)
        gap = int(main_size * 0.38)
        left = min(width - side - 20, main_x + title_w // 2 + gap)
        top = max(12, main_y - side // 2)
        draw = ImageDraw.Draw(plate)
        draw.rectangle((left, top, left + side - 1, top + side - 1), outline=cinnabar, width=border)
        inner_pad = border + max(6, side // 16)
        inner_top = top + inner_pad
        inner_h = side - 2 * inner_pad
        cell = max(12, inner_h // glyph_count)
        stack = cell * glyph_count
        stack_top = inner_top + max(0, (inner_h - stack) // 2)
        seal_font = _fit_seal_font(font_path, cell, chars)
        for index, ch in enumerate(chars):
            cy = stack_top + cell * index + cell / 2
            draw.text((left + side / 2, cy), ch, font=seal_font, fill=cinnabar, anchor="mm")
    return plate


def burn_flower_text_video(
    video_url: str,
    script_text: str = "",
    *,
    duration: Any = None,
    user_id: int = 0,
    width: Optional[int] = None,
    height: Optional[int] = None,
    events: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    events = list(events) if events is not None else extract_libass_events(script_text, duration)
    if not events:
        raise ValueError("没有可烧录的文字")

    from app.services.video_service import (
        _download_or_resolve_local_video,
        _probe_video_size,
        _resolve_ffmpeg_exe,
        _run_ffmpeg,
        _upload_processed_video,
    )

    work_dir = tempfile.mkdtemp(prefix="flower_plate_")
    try:
        source_path = _download_or_resolve_local_video(video_url, work_dir)
        ffmpeg_exe = _resolve_ffmpeg_exe()
        probed_w, probed_h = _probe_video_size(source_path, ffmpeg_exe)
        frame_w = int(width or probed_w or 1920)
        frame_h = int(height or probed_h or 1080)
        font_path = resolve_cjk_font_file()
        plates: List[str] = []
        for index, event in enumerate(events):
            plate = render_title_plate(event, width=frame_w, height=frame_h, font_path=font_path)
            plate_path = os.path.join(work_dir, f"plate_{index}.png")
            plate.save(plate_path)
            plates.append(plate_path)
        output_path = os.path.join(work_dir, "burned.mp4")
        cmd = [ffmpeg_exe, "-y", "-i", source_path]
        for plate_path in plates:
            cmd.extend(["-i", plate_path])
        steps = []
        prev = "0:v"
        for index, event in enumerate(events):
            start = max(0.0, float(event.get("start") or 0))
            end = max(start, float(event.get("end") or 0))
            nxt = f"v{index}"
            steps.append(
                f"[{prev}][{index + 1}:v]overlay=0:0:enable='between(t\\,{start:.3f}\\,{end:.3f})'[{nxt}]"
            )
            prev = nxt
        cmd.extend([
            "-filter_complex", ";".join(steps),
            "-map", f"[{prev}]",
            "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path,
        ])
        _run_ffmpeg(cmd)
        import uuid

        uploaded = _upload_processed_video(output_path, f"flower_{uuid.uuid4().hex}.mp4", user_id=user_id)
        return {"url": uploaded, "events": events}
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


def _notes(shot: Any) -> Dict[str, Any]:
    raw = getattr(shot, "technical_notes", None)
    if isinstance(raw, dict):
        return dict(raw)
    try:
        parsed = json.loads(raw or "{}")
    except Exception:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _url_key(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    return raw.split("#", 1)[0].split("?", 1)[0].rstrip("/")


def _is_burn_file(url: str) -> bool:
    name = _url_key(url).rsplit("/", 1)[-1]
    return name.startswith("flower_")


def _burn_output_keys(notes: Dict[str, Any]) -> set:
    keys = set()
    output = str((notes or {}).get("flower_ass_output_url") or "").strip()
    if output:
        keys.add(_url_key(output))
    for item in (notes or {}).get("flower_ass_output_urls") or []:
        key = _url_key(str(item or ""))
        if key:
            keys.add(key)
    return {key for key in keys if key}


def resolve_burn_source(video_url: str, notes: Dict[str, Any], origin_fallback: str = "") -> str:
    """Every re-burn starts from the first clean plate, never from a burned copy."""
    current = str(video_url or "").strip()
    outputs = _burn_output_keys(notes)
    origin = str((notes or {}).get("flower_ass_origin_url") or "").strip()
    saved_source = str((notes or {}).get("flower_ass_source_url") or "").strip()
    current_key = _url_key(current)

    def usable(url: str) -> bool:
        key = _url_key(url)
        return bool(key) and key not in outputs and not _is_burn_file(url)

    if current_key and usable(current) and current_key not in {_url_key(origin), _url_key(saved_source)}:
        if origin or saved_source or outputs:
            return current
    if usable(origin):
        return origin
    if usable(saved_source):
        return saved_source
    if usable(origin_fallback):
        return origin_fallback
    if current_key and usable(current):
        return current
    return origin or saved_source or origin_fallback or current


def _earliest_clean_shot_video(db: Any, shot: Any, outputs: set) -> str:
    """Oldest non-burn asset for this shot. Burn files are named flower_*.mp4."""
    try:
        from app.models.all_models import Asset
    except Exception:
        return ""
    shot_id = str(getattr(shot, "id", "") or "").strip()
    project_id = getattr(shot, "project_id", None)
    if not shot_id:
        return ""
    query = db.query(Asset).filter(Asset.type == "video", Asset.is_deleted == False)  # noqa: E712
    if project_id:
        query = query.filter(Asset.project_id == project_id)
    rows = query.order_by(Asset.id.asc()).limit(2000).all()
    for asset in rows:
        meta = asset.meta_info if isinstance(asset.meta_info, dict) else {}
        if str(meta.get("shot_id") or "").strip() != shot_id:
            continue
        kind = str(meta.get("asset_type") or meta.get("frame_type") or "video").strip().lower()
        if kind not in {"video", "shot_video", ""}:
            continue
        url = str(asset.url or "").strip()
        name = str(asset.filename or "")
        if not url or name.startswith("flower_") or "/flower_" in url.split("?", 1)[0]:
            continue
        if _url_key(url) in outputs:
            continue
        return url
    return ""


def apply_flower_burn_to_shot(db: Any, shot: Any, user_id: int = 0, lines: Any = None) -> Optional[str]:
    """Auto burn reads the shot script. A later edit burns those lines onto the clean source."""
    video_url = str(getattr(shot, "video_url", None) or "").strip()
    if not video_url:
        return None
    duration = getattr(shot, "duration", None)
    notes = _notes(shot)
    outputs = _burn_output_keys(notes)
    origin_fallback = ""
    origin_url = str(notes.get("flower_ass_origin_url") or "")
    source_url_saved = str(notes.get("flower_ass_source_url") or "")
    origin_key = _url_key(origin_url)
    source_key = _url_key(source_url_saved)
    if (
        not origin_key
        or origin_key in outputs
        or source_key in outputs
        or _is_burn_file(origin_url)
        or _is_burn_file(source_url_saved)
    ):
        origin_fallback = _earliest_clean_shot_video(db, shot, outputs)
    source_url = resolve_burn_source(video_url, notes, origin_fallback)
    if lines is not None:
        events = normalize_manual_burn_lines(lines, duration)
    else:
        events = extract_shot_libass_events(shot)
    if not events:
        raise ValueError("没有可烧录的文字")
    result = burn_flower_text_video(
        source_url,
        duration=duration,
        user_id=user_id,
        events=events,
    )
    new_url = str((result or {}).get("url") or "").strip()
    if not new_url:
        return None
    prior_outputs = [str(item) for item in (notes.get("flower_ass_output_urls") or []) if str(item or "").strip()]
    output_urls = prior_outputs + [new_url]
    notes["flower_ass_output_urls"] = output_urls[-8:]
    notes["flower_ass_output_url"] = new_url
    source_key = _url_key(source_url)
    prior_keys = {_url_key(item) for item in prior_outputs}
    if source_key and source_key not in prior_keys and source_key != _url_key(new_url) and not _is_burn_file(source_url):
        locked_key = _url_key(str(notes.get("flower_ass_origin_url") or ""))
        if not locked_key or locked_key in prior_keys or source_key != locked_key:
            notes["flower_ass_origin_url"] = source_url
        notes["flower_ass_source_url"] = str(notes.get("flower_ass_origin_url") or source_url)
    notes["flower_ass_draft"] = events
    shot.video_url = new_url
    shot.technical_notes = json.dumps(notes, ensure_ascii=False)
    db.add(shot)
    db.commit()
    logger.info("[FlowerAss] burned shot_id=%s", getattr(shot, "id", None))
    return new_url


def _shot_copy_texts(shot: Any) -> List[str]:
    notes = _notes(shot)
    texts: List[str] = []
    for value in (
        getattr(shot, "video_content", None),
        notes.get("video_prompt_cn"),
        getattr(shot, "prompt", None),
    ):
        text = str(value or "").strip()
        if text and text not in texts:
            texts.append(text)
    return texts


def extract_shot_libass_events(shot: Any) -> List[Dict[str, Any]]:
    """Read the shot script, then the Chinese video prompt. video_content is often empty."""
    duration = getattr(shot, "duration", None)
    for text in _shot_copy_texts(shot):
        events = extract_libass_events(text, duration)
        if events:
            return events
    return []


def flower_burn_draft(shot: Any) -> Dict[str, Any]:
    notes = _notes(shot)
    saved = notes.get("flower_ass_draft")
    if isinstance(saved, list) and saved:
        lines = normalize_manual_burn_lines(saved, getattr(shot, "duration", None))
        if lines:
            return {"lines": lines, "source": "draft"}
    events = extract_shot_libass_events(shot)
    return {
        "lines": events or [_blank_burn_line(getattr(shot, "duration", None))],
        "source": "script",
    }
