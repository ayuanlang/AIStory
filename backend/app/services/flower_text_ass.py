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
_CTA_RE = re.compile(r"CTA\s*[=＝]\s*「([^」]+)」")
_SEAL_TEXT_RE = re.compile(r"(?:印文|印章文|闲章|朱文)=「([^」]+)」")
_GLYPH_LOCK_RE = re.compile(r"逐字=[^｜|\n]+")
_VOICE_RE = re.compile(r"(?:Voiceover|旁白|口播)\s*[:：]\s*(.+)", re.IGNORECASE)
_FONT_MAP = {
    "楷体": "KaiTi",
    "华文楷体": "KaiTi",
    "宋体": "SimSun",
    "黑体": "SimHei",
    "微软雅黑": "Microsoft YaHei",
    "魏碑": "KaiTi",
    "宋": "SimSun",
    "kaiti": "KaiTi",
    "simsun": "SimSun",
    "simhei": "SimHei",
}
_DESIGNATED_COPY_RE = re.compile(
    r"(?:画幅叠出片内图形花字|片内图形花字|(?<!名牌)文案)\s*[=＝]?\s*「([^」]+)」"
)
_NAMEPLATE_COPY_RE = re.compile(r"名牌字样\s*[=＝]\s*「([^」]*)」")
_NAMEPLATE_PAINT_RE = re.compile(
    r"(?:画幅顶部中央叠出片内图形名牌|画幅叠出片内图形名牌|画面打出物理文字标签：)\s*"
    r"【[^】]*】(?:[^，。\n]*】)?"
)
_REAL_BURN_MARK_RE = re.compile(r"(?<!标记)烧录=libass")
_SIZE_RATIO = {"大": 0.20, "中": 0.13, "小": 0.08}
_TITLE_TRACKING = 0.14
_ASS_FILTER_CACHE: Optional[bool] = None


def _usable_copy(quote: str) -> bool:
    text = str(quote or "").strip()
    return len(text) > 1 and text not in {"家", "无", "X家"}


def _is_hotline_copy(quote: str) -> bool:
    text = str(quote or "").strip()
    return bool(text and (_PHONE_RE.search(text) or "热线" in text or "电话" in text or "订座" in text))


def _split_contact_lines(text: str) -> List[str]:
    parts = [part.strip() for part in re.split(r"[｜|]", str(text or "")) if part.strip()]
    return parts or ([text.strip()] if str(text or "").strip() else [])


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


def _flower_output_mode(block: str) -> str:
    """burn = post composite, model = video model paints, drop = no on-screen flower text."""
    text = str(block or "")
    flower = text.replace("名牌出字=", "")
    if "出字=舍" in flower:
        return "drop"
    if "出字=模型直出" in flower and "出字=后期烧录" not in flower:
        return "model"
    if (
        "出字=后期烧录" in flower
        or _REAL_BURN_MARK_RE.search(text) is not None
        or "手写=禁" in text
        or "上屏=字卡专镜" in text
    ):
        return "burn"
    if "画幅叠出" in text or "片内图形花字" in text or _DESIGNATED_COPY_RE.search(text):
        return "model"
    return ""


def _nameplate_output_mode(block: str) -> str:
    """burn = post composite, model = video model paints the nameplate.

    The quality footer mentions both modes as instructions
    (``名牌出字=后期烧录时`` / ``名牌出字=模型直出（含未写``). Those are not a choice.
    """
    text = str(block or "")
    if re.search(r"名牌出字=后期烧录(?!时)", text):
        return "burn"
    if re.search(r"名牌出字=模型直出(?![(（])", text):
        return "model"
    if re.search(r"画幅(?:顶部中央)?叠出片内图形名牌|画面打出物理文字标签|名牌字样\s*[=＝]", text):
        return "model"
    return ""


def _nameplate_burn_events(block: str, start: float, stop: float) -> List[Dict[str, Any]]:
    if _nameplate_output_mode(block) != "burn":
        return []
    events: List[Dict[str, Any]] = []
    for match in _NAMEPLATE_COPY_RE.finditer(block or ""):
        raw = str(match.group(1) or "").strip()
        if not raw:
            continue
        parts = [part.strip() for part in re.split(r"[｜|]", raw) if part.strip()]
        tail = (block or "")[match.end():match.end() + 220]
        place = "顶" if ("落位=顶部中央" in tail or "画幅顶部中央" in tail) else "名牌"
        font = "KaiTi"
        font_match = re.search(r"字体=([^｜|\n，,]+)", tail)
        if font_match:
            raw_font = font_match.group(1).strip()
            font = _FONT_MAP.get(raw_font) or _FONT_MAP.get(raw_font.lower()) or "KaiTi"
        size = "中"
        if "字级=大" in tail:
            size = "大"
        elif "字级=小" in tail:
            size = "小"
        look = script_flower_look(tail)
        if not _mark(tail, "点缀色"):
            look["companion_color"] = look["title_color"]
        events.append({
            "text": parts[0],
            "companion": parts[1] if len(parts) > 1 else "",
            "seal": "",
            "start": float(start),
            "end": float(stop),
            "place": place,
            "size": size,
            "vertical": False,
            "font": font,
            "font_kind": look.get("font_kind") or "",
            "look": look,
            "kind": "nameplate",
        })
    return events


def _strip_nameplates(block: str) -> str:
    if _nameplate_output_mode(block) != "burn":
        return block
    text = _NAMEPLATE_PAINT_RE.sub("", block)
    text = _NAMEPLATE_COPY_RE.sub("名牌字样=「」", text)
    note = "本P禁止生成角色名牌与环境名牌字形，字由后期烧录。"
    if note not in text:
        text = f"{text.rstrip()}{note}\n"
    return text


def _block_needs_libass(block: str) -> bool:
    text = str(block or "")
    if not text.strip() or _block_has_voiceover(text) or _flower_output_mode(text) != "burn":
        return False
    main, companion = _pick_main_and_companion(text)
    return bool(main or companion or _seal_text(text))


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
    for quote in _CTA_RE.findall(block):
        if not _usable_copy(quote) or quote.strip() == main:
            continue
        for part in _split_contact_lines(quote):
            if part != main:
                _append_unique(companion_parts, part)
    for phone in phones:
        if phone == main or any(phone in part for part in companion_parts):
            continue
        label = "垂询热线：" if ("热线" in block or "电话" in block) else ""
        _append_unique(companion_parts, f"{label}{phone}" if label else phone)
    return main, "\n".join(companion_parts)


_NAMED_COLORS = {
    "象牙白": (252, 246, 230, 255),
    "象牙": (252, 246, 230, 255),
    "米白": (248, 240, 220, 255),
    "浅金": (232, 196, 122, 255),
    "鎏金": (212, 168, 74, 255),
    "金色": (196, 148, 62, 255),
    "金": (196, 148, 62, 255),
    "朱红": (168, 42, 36, 255),
    "朱": (168, 42, 36, 255),
    "红": (176, 48, 40, 255),
    "青": (120, 168, 170, 255),
    "霓虹": (120, 220, 210, 255),
    "墨": (36, 32, 28, 255),
    "黑": (28, 28, 28, 255),
    "白": (248, 248, 246, 255),
}
_FONT_KIND_FILES = {
    "brush": ("MaShanZheng-Regular.ttf", "STXINGKA.TTF", "simkai.ttf"),
    "kai": ("simkai.ttf", "STKAITI.TTF", "wqy-microhei.ttc"),
    "song": ("simsun.ttc", "STSONG.TTF", "simkai.ttf"),
    "hei": ("simhei.ttf", "msyh.ttc", "wqy-microhei.ttc"),
    "clerical": ("SIMLI.TTF", "STLITI.TTF", "simkai.ttf"),
    "weibei": ("STXINWEI.TTF", "simkai.ttf"),
    "seal": ("simkai.ttf", "STKAITI.TTF"),
}


def _mark(text: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}\s*=\s*([^｜|\n]+)", str(text or ""))
    return match.group(1).strip() if match else ""


def _color_from_script(value: str, fallback: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    text = str(value or "").strip()
    if not text:
        return fallback
    if re.search(r"#?[0-9A-Fa-f]{6}", text):
        parsed = _hex_color(text, fallback)
        if parsed != fallback or re.search(r"[0-9A-Fa-f]{6}", text):
            if re.search(r"[0-9A-Fa-f]{6}", text):
                return _hex_color(text, fallback)
    for name, color in sorted(_NAMED_COLORS.items(), key=lambda item: len(item[0]), reverse=True):
        if name in text:
            return color
    return fallback


def script_flower_look(block: str, spec: str = "") -> Dict[str, Any]:
    """Font, color, and art treatment locked by script generation and optimization."""
    def taken(name: str) -> str:
        return _mark(block, name) or _mark(spec, name)

    face = taken("字体")
    emphasis = taken("强调体")
    exhibit = taken("展示")
    art = " ".join((taken("艺术化") or taken("艺术"), emphasis, exhibit))
    color_text = _mark(block, "字色") or _mark(spec, "字色")
    accent_text = _mark(block, "点缀色") or _mark(spec, "点缀色")
    blob = " ".join((face, emphasis, exhibit, art))
    if any(token in blob for token in ("书法", "毛笔", "行楷", "飞白")):
        font_kind = "brush"
    elif "隶" in blob:
        font_kind = "clerical"
    elif "魏" in blob or "碑" in blob:
        font_kind = "weibei"
    elif "黑" in face or "雅黑" in face:
        font_kind = "hei"
    elif "宋" in face:
        font_kind = "song"
    elif "印章" in blob:
        font_kind = "seal"
    elif "楷" in face:
        font_kind = "kai"
    else:
        font_kind = ""
    title = _color_from_script(color_text, _DEFAULT_FLOWER_STYLE["title_color"])
    if not color_text and any(token in art for token in ("烫金", "鎏金", "浅金")):
        title = _NAMED_COLORS["浅金"]
    if not color_text and "水墨" in art:
        title = _NAMED_COLORS["墨"]
    companion = _color_from_script(accent_text, _DEFAULT_FLOWER_STYLE["companion_color"])
    if not accent_text and any(token in art for token in ("烫金", "鎏金", "浅金")):
        companion = _NAMED_COLORS["鎏金"]
    return {
        "font_kind": font_kind,
        "title_color": title,
        "companion_color": companion,
        "seal_color": _DEFAULT_FLOWER_STYLE["seal_color"],
        "shadow": 0.85 if any(token in art for token in ("光晕", "霓虹", "发光")) else _DEFAULT_FLOWER_STYLE["shadow"],
        "rule": False,
        "seal_scale": 1.15 if "印章" in blob else 1.0,
        "painted": any(token in blob for token in ("书法", "毛笔", "水墨", "飞白")),
        "glow": any(token in art for token in ("光晕", "霓虹", "发光")),
        "duotone": "套印" in art,
        "gradient": "渐变" in art,
        "wide": "宽" in face,
        "locked": bool(face or color_text or art.strip()),
    }


def _style_context(script: str) -> str:
    """Style may sit on a sibling sentence, not only on the burn quote."""
    spec = _spec_context(script)
    return spec or str(script or "")


def _spec_context(script: str) -> str:
    match = re.search(r"花字规范\s*[=：:]?\s*([^\n]+)", str(script or ""))
    return match.group(1).strip() if match else ""


def _place_and_size(block: str) -> tuple[str, str, bool, str]:
    place = "中"
    if "位置=画右" in block or "落位=画右" in block:
        place = "画右"
    elif "位置=画左" in block or "落位=画左" in block:
        place = "画左"
    size = "中"
    size_body = _CTA_RE.sub("", block).replace("｜字级=小｜落位=句下", "").replace("字级=小｜落位=句下", "")
    if "字级=大" in size_body or "字级=大" in block:
        size = "大"
    elif "字级=小" in size_body:
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
        stop = float(end) if end is not None else float(start) + fallback
        if stop <= start:
            stop = start + fallback
        if _block_needs_libass(block):
            main, companion = _pick_main_and_companion(block)
            seal = _seal_text(block)
            if main or companion or seal:
                place, size, vertical, font = _place_and_size(block)
                look = script_flower_look(block, _style_context(script))
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
                    "font_kind": look.get("font_kind") or "",
                    "look": look,
                })
        events.extend(_nameplate_burn_events(block, float(start), stop))
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
        if place not in {"中", "画左", "画右", "顶", "名牌"}:
            place = "中"
        event = {
            "text": text,
            "companion": companion,
            "seal": seal,
            "start": start,
            "end": end,
            "place": place,
            "size": size,
            "vertical": bool(raw.get("vertical")),
            "font": str(raw.get("font") or "KaiTi"),
        }
        if isinstance(raw.get("look"), dict):
            event["look"] = raw["look"]
        if str(raw.get("font_kind") or "").strip():
            event["font_kind"] = str(raw.get("font_kind")).strip()
        events.append(event)
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


def _plate_anchor(width: int, height: int, place: str) -> Tuple[int, int]:
    """Screen point for a burned line. Nameplates use the same card as flower text, at their own seat."""
    if place == "画右":
        x = int(width * 0.68)
    elif place == "画左":
        x = int(width * 0.32)
    else:
        x = int(width) // 2
    if place == "顶":
        y = int(height * 0.14)
    elif place == "名牌":
        y = int(height * 0.72)
    else:
        y = int(height * 0.46)
    return x, y


def _pos(width: int, height: int, place: str, size: str, companion: bool) -> tuple[int, int, int]:
    ratio = _SIZE_RATIO.get(size, _SIZE_RATIO["中"])
    fontsize = max(28, int(height * ratio))
    if place == "画右":
        x = int(width * 0.78)
    elif place == "画左":
        x = int(width * 0.22)
    else:
        x = int(width / 2)
    if place == "顶":
        y = int(height * 0.12)
    elif place == "名牌":
        y = int(height * 0.70)
    else:
        y = int(height * 0.40)
    if companion:
        main_fs = fontsize
        if place in {"顶", "名牌"}:
            fontsize = max(16, int(main_fs * 0.55))
            y = min(int(height * 0.78), y + int(main_fs * 1.05))
        else:
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


_PAINT_CUE_RE = re.compile(
    r"(?:画幅(?:顶部中央)?叠出|中部叠出|满幅黑场，中部叠出)片内图形花字「[^」]*」[，,]?"
)


def _strip_block(block: str) -> str:
    mode = _flower_output_mode(block)
    if mode not in {"burn", "drop"}:
        return _strip_nameplates(block)
    main, companion = _pick_main_and_companion(block)
    text = _PAINT_CUE_RE.sub("", block)
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
    note = (
        "本P禁止生成花字、店号、热线、地址与任何字幕字形，字由后期烧录。"
        if mode == "burn"
        else "本P花字已舍，禁止生成花字字形。"
    )
    if note not in text:
        text = f"{text.rstrip()}{note}\n"
    return _strip_nameplates(text)


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


def resolve_font_kind(kind: str) -> str:
    """Pick the face named by the script. An empty kind stays on the body font."""
    files = _FONT_KIND_FILES.get(str(kind or "").strip())
    if not files:
        return ""
    for folder in _cjk_font_search_dirs():
        for filename in files:
            src = os.path.join(folder, filename)
            if os.path.isfile(src):
                return src
    bundled = os.path.join(_bundled_cjk_font_dir(), "MaShanZheng-Regular.ttf")
    if kind == "brush" and os.path.isfile(bundled):
        return bundled
    return ""


def resolve_title_font_file() -> str:
    """Brush face for the large title. Hotline and seal stay on the body font."""
    bundled = os.path.join(_bundled_cjk_font_dir(), "MaShanZheng-Regular.ttf")
    if os.path.isfile(bundled):
        return bundled
    windir = os.environ.get("WINDIR")
    if windir:
        for filename in ("STXINGKA.TTF", "simkai.ttf", "STKAITI.TTF"):
            src = os.path.join(windir, "Fonts", filename)
            if os.path.isfile(src):
                return src
    return resolve_cjk_font_file()


def _fit_title_font(
    font_path: str,
    text: str,
    *,
    width: int,
    height: int,
    size_name: str,
    vertical: bool,
    budget: int,
    tracking_scale: float = 1.0,
) -> Tuple[Any, int]:
    ratio = _TITLE_TRACKING * max(1.0, float(tracking_scale or 1))
    target = max(36, int(height * _SIZE_RATIO.get(size_name, _SIZE_RATIO["中"])))
    size = target
    font = _open_cjk_font(font_path, size)
    line = "".join(ch for ch in str(text or "") if ch not in {"\n", "\r"})
    if not line:
        return font, max(4, int(size * ratio))
    for _ in range(16):
        tracking = max(4, int(size * ratio))
        span = _tracked_width(font, line, tracking) if not vertical else int(size * 1.05) * len(line)
        if span <= budget:
            break
        size = max(36, int(size * 0.92))
        font = _open_cjk_font(font_path, size)
        if size == 36:
            break
    return font, max(4, int(getattr(font, "size", size) * ratio))


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
    shadow_alpha: int = 150,
    painted: bool = False,
    glow: bool = False,
) -> None:
    from PIL import Image, ImageDraw, ImageFilter

    size = int(getattr(font, "size", 32) or 32)
    if shadow and text and shadow_alpha > 0:
        layer = Image.new("RGBA", plate.size, (0, 0, 0, 0))
        offset = max(2, int(size / (12 if painted else 22)))
        _draw_tracked(
            ImageDraw.Draw(layer),
            text,
            font,
            (center[0], center[1] + offset),
            (42, 28, 16, max(1, min(255, int(shadow_alpha)))),
            tracking,
            vertical,
        )
        blur = max(2.0, size / (8 if painted else 16))
        plate.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=blur)))
    if not text:
        return
    if glow and text:
        layer = Image.new("RGBA", plate.size, (0, 0, 0, 0))
        _draw_tracked(ImageDraw.Draw(layer), text, font, center, (*fill[:3], 150), tracking, vertical)
        plate.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=max(6.0, size / 5))))
    if painted and size >= 64:
        glyph = Image.new("RGBA", plate.size, (0, 0, 0, 0))
        _draw_tracked(ImageDraw.Draw(glyph), text, font, center, fill, tracking, vertical)
        glyph = glyph.effect_spread(1)
        plate.alpha_composite(glyph)
        return
    _draw_tracked(ImageDraw.Draw(plate), text, font, center, fill, tracking, vertical)


def _paint_art_title(
    plate: Any,
    text: str,
    font: Any,
    center: Tuple[int, int],
    fill: Tuple[int, int, int, int],
    tracking: int,
    *,
    vertical: bool,
    look: Dict[str, Any],
    shadow_alpha: int,
) -> None:
    """Gold plate sits under the glyphs. The face itself carries the gradient."""
    from PIL import Image, ImageDraw, ImageFilter

    if not text:
        return
    size = int(getattr(font, "size", 32) or 32)
    gold = _NAMED_COLORS["浅金"]
    if shadow_alpha > 0:
        layer = Image.new("RGBA", plate.size, (0, 0, 0, 0))
        offset = max(3, int(size / 10))
        _draw_tracked(
            ImageDraw.Draw(layer),
            text,
            font,
            (center[0], center[1] + offset),
            (42, 28, 16, max(1, min(255, int(shadow_alpha)))),
            tracking,
            vertical,
        )
        plate.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=max(3.0, size / 7))))
    if look.get("glow"):
        layer = Image.new("RGBA", plate.size, (0, 0, 0, 0))
        _draw_tracked(ImageDraw.Draw(layer), text, font, center, (*fill[:3], 150), tracking, vertical)
        plate.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=max(6.0, size / 5))))
    if look.get("duotone"):
        shift = max(6, int(size * 0.12))
        plate_gold = _NAMED_COLORS["鎏金"]
        _draw_tracked(
            ImageDraw.Draw(plate),
            text,
            font,
            (center[0] + shift, center[1] + int(shift * 0.55)),
            (*plate_gold[:3], 245),
            tracking,
            vertical,
        )
    mask_layer = Image.new("RGBA", plate.size, (0, 0, 0, 0))
    _draw_tracked(ImageDraw.Draw(mask_layer), text, font, center, (255, 255, 255, 255), tracking, vertical)
    if look.get("painted") and size >= 48:
        mask_layer = mask_layer.effect_spread(1)
    alpha = mask_layer.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return
    if not look.get("gradient"):
        solid = Image.new("RGBA", plate.size, (*fill[:3], 0))
        solid.putalpha(alpha)
        plate.alpha_composite(solid)
        return
    top = fill
    bottom = gold
    span = max(1, bbox[3] - bbox[1])
    grad = Image.new("RGBA", plate.size, (0, 0, 0, 0))
    pixels = grad.load()
    for y in range(bbox[1], bbox[3] + 1):
        blend = (y - bbox[1]) / span
        color = tuple(int(top[channel] * (1 - blend) + bottom[channel] * blend) for channel in range(3))
        for x in range(bbox[0], bbox[2] + 1):
            pixels[x, y] = (*color, 255)
    grad.putalpha(alpha)
    plate.alpha_composite(grad)


_DEFAULT_FLOWER_STYLE: Dict[str, Any] = {
    "title_color": (252, 246, 230, 255),
    "companion_color": (196, 148, 62, 235),
    "seal_color": (168, 42, 36, 255),
    "shadow": 0.72,
    "rule": False,
    "seal_scale": 1.0,
}


def _hex_color(value: Any, fallback: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    match = re.search(r"#?([0-9A-Fa-f]{6})", str(value or ""))
    if not match:
        return fallback
    hex_text = match.group(1)
    rgb = tuple(int(hex_text[index:index + 2], 16) for index in (0, 2, 4))
    return (rgb[0], rgb[1], rgb[2], fallback[3])


def parse_flower_style(raw: str) -> Dict[str, Any]:
    """Read colors and seal size from a model JSON object. Copy fields are ignored."""
    style = dict(_DEFAULT_FLOWER_STYLE)
    text = str(raw or "").strip()
    if not text or text.lower().startswith("error"):
        return style
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return style
    try:
        payload = json.loads(match.group(0))
    except Exception:
        return style
    if not isinstance(payload, dict):
        return style
    style["title_color"] = _hex_color(payload.get("title_color"), style["title_color"])
    style["companion_color"] = _hex_color(payload.get("companion_color"), style["companion_color"])
    style["seal_color"] = _hex_color(payload.get("seal_color"), style["seal_color"])
    try:
        style["shadow"] = min(1.0, max(0.0, float(payload.get("shadow", style["shadow"]))))
    except (TypeError, ValueError):
        pass
    if "rule" in payload:
        style["rule"] = bool(payload.get("rule"))
    try:
        style["seal_scale"] = min(1.3, max(0.8, float(payload.get("seal_scale", style["seal_scale"]))))
    except (TypeError, ValueError):
        pass
    return style


def _style_public(style: Dict[str, Any], decor: bool) -> Dict[str, Any]:
    def hex_of(color: Tuple[int, int, int, int]) -> str:
        return "#{:02X}{:02X}{:02X}".format(color[0], color[1], color[2])

    return {
        "title_color": hex_of(style["title_color"]),
        "companion_color": hex_of(style["companion_color"]),
        "seal_color": hex_of(style["seal_color"]),
        "shadow": style["shadow"],
        "rule": bool(style["rule"]),
        "seal_scale": style["seal_scale"],
        "decor": bool(decor),
    }


def _jpeg_data_url(path: str) -> str:
    import base64
    import io

    from PIL import Image

    image = Image.open(path).convert("RGB")
    image.thumbnail((768, 768))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _run_coro(coro: Any) -> Any:
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _extract_still(ffmpeg_exe: str, source_path: str, work_dir: str, second: float) -> str:
    from app.services.video_service import _run_ffmpeg

    still_path = os.path.join(work_dir, "still.jpg")
    _run_ffmpeg([
        ffmpeg_exe, "-y",
        "-ss", f"{max(0.0, float(second)):.3f}",
        "-i", source_path,
        "-frames:v", "1",
        "-q:v", "3",
        still_path,
    ])
    return still_path


def _resolve_image_file(url: str, work_dir: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    from urllib.parse import urlparse

    from app.core.config import settings

    path_part = urlparse(raw).path or raw
    if "/uploads/" in path_part:
        relative = path_part.split("/uploads/", 1)[1]
        local_path = os.path.join(settings.UPLOAD_DIR, relative.replace("/", os.sep))
        if os.path.isfile(local_path):
            return local_path
    if raw.startswith(("http://", "https://")):
        import requests

        dest = os.path.join(work_dir, "decor_src.png")
        with requests.get(raw, stream=True, timeout=60) as response:
            response.raise_for_status()
            with open(dest, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        handle.write(chunk)
        return dest
    if os.path.isfile(raw):
        return raw
    return ""


def _mist_from_image(path: str) -> Any:
    from PIL import Image

    image = Image.open(path).convert("RGB")
    gray = image.convert("L")
    hist = gray.histogram()
    total = max(1, sum(hist))
    if sum(hist[:48]) / total < 0.45:
        return None
    rgba = image.convert("RGBA")
    rgba.putalpha(gray)
    return rgba


_STYLE_PROMPT = (
    "看这张视频静帧，只决定叠在画面上的花字样式。"
    "不要改写文案，不要输出任何汉字句子。"
    "只返回一个 JSON 对象，不要 markdown："
    '{"title_color":"#FCF6E6","companion_color":"#C4943E","seal_color":"#A82A24","shadow":0.72,"rule":false,"seal_scale":1.0}。'
    "title_color 是主文颜色，companion_color 是热线颜色，seal_color 是印章颜色。"
    "颜色必须能在这帧的天空、墙或景物上读清。shadow 取 0 到 1。rule 保持 false，主文下面不加线。"
    "seal_scale 取 0.8 到 1.3。"
)

_DECOR_PROMPT = (
    "Pure black background, 16:9. A soft warm mist and a faint antique-gold glow across the middle, "
    "like empty atmosphere behind a title. No letters, no digits, no Chinese characters, no words, "
    "no logo, no square, no border, no people, no building, no sign."
)


async def _lookup_flower_style(still_path: str, user_id: int) -> Dict[str, Any]:
    from app.services.agent_service import agent_service
    from app.services.llm_service import llm_service

    config = agent_service.get_active_llm_config(int(user_id), category="LLM", function_name="script_analysis")
    result = await llm_service.analyze_multimodal(_STYLE_PROMPT, _jpeg_data_url(still_path), config or {})
    return parse_flower_style(str((result or {}).get("content") or ""))


async def _lookup_flower_decor(user_id: int, work_dir: str) -> Any:
    from app.services.agent_service import agent_service
    from app.services.media_service import media_service

    config = agent_service.get_active_llm_config(
        int(user_id),
        category="Image",
        function_name="generate_subjects_t2i",
    )
    result = await media_service.generate_image(
        _DECOR_PROMPT,
        negative_prompt="text, letters, digits, Chinese characters, logo, watermark, border, frame, people",
        llm_config=config or {},
        aspect_ratio="16:9",
        user_id=int(user_id),
        filename_base="flower_decor",
        asset_type="flower_decor",
    )
    if not isinstance(result, dict) or result.get("error"):
        logger.warning("[FlowerAss] decor image skipped: %s", (result or {}).get("error") if isinstance(result, dict) else result)
        return None
    local_path = _resolve_image_file(str(result.get("url") or ""), work_dir)
    if not local_path:
        return None
    return _mist_from_image(local_path)


def prepare_flower_plate_look(
    ffmpeg_exe: str,
    source_path: str,
    work_dir: str,
    events: List[Dict[str, Any]],
    user_id: int,
) -> Tuple[Dict[str, Any], Any]:
    """Use the script's locked face and color. A still is only a fallback when the script named neither."""
    style = dict(_DEFAULT_FLOWER_STYLE)
    decor = None
    locked = next(
        (
            event.get("look")
            for event in events
            if isinstance(event.get("look"), dict) and event["look"].get("locked")
        ),
        None,
    )
    if isinstance(locked, dict):
        for key in ("title_color", "companion_color", "seal_color", "shadow", "rule", "seal_scale"):
            if key in locked:
                style[key] = locked[key]
        return style, decor
    if int(user_id or 0) <= 0:
        return style, decor
    try:
        second = float((events[0] or {}).get("start") or 0.2) if events else 0.2
        still_path = _extract_still(ffmpeg_exe, source_path, work_dir, second)

        async def _styled():
            import asyncio
            return await asyncio.wait_for(_lookup_flower_style(still_path, int(user_id)), timeout=40)

        style = _run_coro(_styled())
    except Exception as exc:
        logger.warning("[FlowerAss] still style skipped: %s", exc)
        style = dict(_DEFAULT_FLOWER_STYLE)
    try:
        async def _decor():
            import asyncio
            return await asyncio.wait_for(_lookup_flower_decor(int(user_id), work_dir), timeout=90)

        decor = _run_coro(_decor())
    except Exception as exc:
        logger.warning("[FlowerAss] decor image skipped: %s", exc)
        decor = None
    return style, decor


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
    title_font_path: str = "",
    style: Optional[Dict[str, Any]] = None,
    decoration: Any = None,
) -> Any:
    """Typeset one title card as a transparent image. Glyphs come from the font file."""
    from PIL import Image, ImageDraw

    width = max(16, int(width))
    height = max(16, int(height))
    plate = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    place = str(event.get("place") or "中")
    size_name = str(event.get("size") or "中")
    seal = str(event.get("seal") or "").strip()
    seal_chars = [ch for ch in seal if ch not in {"\n", "\r"}]
    main_x, main_y = _plate_anchor(width, height, place)
    if place in {"画右", "画左"}:
        budget = int(width * 0.42)
    else:
        budget = int(width * (0.72 if seal_chars else 0.84))
    look = dict(style or _DEFAULT_FLOWER_STYLE)
    event_look = event.get("look") if isinstance(event.get("look"), dict) else {}
    for key in ("title_color", "companion_color", "seal_color", "shadow", "rule", "seal_scale"):
        if key in event_look:
            look[key] = event_look[key]
    kind_font = resolve_font_kind(str(event.get("font_kind") or event_look.get("font_kind") or ""))
    if kind_font:
        title_font_path = kind_font
    ivory = look["title_color"]
    gold = look["companion_color"]
    cinnabar = look["seal_color"]
    shadow_alpha = int(250 * float(look.get("shadow") or 0))
    main = str(event.get("text") or "").strip()
    vertical = bool(event.get("vertical"))
    if vertical:
        budget = int(height * 0.62)
    title_font, tracking = _fit_title_font(
        title_font_path or font_path,
        main,
        width=width,
        height=height,
        size_name=size_name,
        vertical=vertical,
        budget=budget,
        tracking_scale=1.55 if event_look.get("wide") else 1.0,
    )
    main_size = int(getattr(title_font, "size", 36) or 36)
    if decoration is not None:
        from PIL import Image

        mist = decoration.convert("RGBA")
        mist_w = int(width * 0.86)
        mist_h = max(1, int(mist.height * mist_w / max(1, mist.width)))
        mist = mist.resize((mist_w, mist_h))
        layer = Image.new("RGBA", plate.size, (0, 0, 0, 0))
        layer.paste(mist, (main_x - mist_w // 2, main_y - mist_h // 2), mist)
        plate.alpha_composite(layer)
    if main:
        if event_look.get("duotone") or event_look.get("gradient"):
            _paint_art_title(
                plate,
                main,
                title_font,
                (main_x, main_y),
                ivory,
                tracking,
                vertical=vertical,
                look=event_look,
                shadow_alpha=shadow_alpha,
            )
        else:
            _paint_tracked(
                plate,
                main,
                title_font,
                (main_x, main_y),
                ivory,
                tracking,
                vertical=vertical,
                shadow_alpha=shadow_alpha,
                painted=bool(event_look.get("painted")),
                glow=bool(event_look.get("glow")),
            )
        title_w = _tracked_width(title_font, main, tracking) if not vertical else main_size
        rule_w = max(main_size, int(title_w * 0.62))
        rule_h = max(2, int(main_size * 0.012))
        rule_x = main_x - rule_w // 2
        rule_y = main_y + int(main_size * 0.62)
        if look.get("rule", False):
            ImageDraw.Draw(plate).rectangle((rule_x, rule_y, rule_x + rule_w, rule_y + rule_h), fill=gold)
    else:
        title_w = 0
        rule_y = main_y
    companion = str(event.get("companion") or "").strip()
    if companion:
        companion_size = max(18, min(int(height * 0.048), int(main_size * 0.36)))
        companion_font = _open_cjk_font(title_font_path or font_path, companion_size)
        companion_y = rule_y + int(main_size * 0.42)
        for line in [part.strip() for part in companion.splitlines() if part.strip()]:
            _paint_tracked(
                plate,
                line,
                companion_font,
                (main_x, companion_y),
                gold,
                max(2, int(companion_size * 0.06)),
                shadow_alpha=max(40, shadow_alpha // 2),
            )
            companion_y += int(companion_size * 1.35)
    chars = seal_chars
    if chars:
        glyph_count = len(chars)
        scale = float(look.get("seal_scale") or 1)
        side = int(main_size * (0.46 + 0.16 * max(0, glyph_count - 1)) * scale)
        side = max(side, int(main_size * 0.58 * scale))
        side = min(side, int(height * 0.22))
        border = max(3, side // 14)
        gap = int(main_size * 0.16)
        left = min(width - side - 12, main_x + title_w // 2 + gap)
        top = max(12, main_y - int(main_size * 0.15) - side // 2)
        draw = ImageDraw.Draw(plate)
        draw.rectangle((left, top, left + side - 1, top + side - 1), outline=cinnabar, width=border)
        inner_pad = border + max(4, side // 18)
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
        title_font_path = font_path
        style, decoration = prepare_flower_plate_look(
            ffmpeg_exe,
            source_path,
            work_dir,
            events,
            int(user_id or 0),
        )
        plates: List[str] = []
        for index, event in enumerate(events):
            plate = render_title_plate(
                event,
                width=frame_w,
                height=frame_h,
                font_path=font_path,
                title_font_path=title_font_path,
                style=style,
                decoration=decoration,
            )
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
        return {"url": uploaded, "events": events, "style": _style_public(style, decoration is not None)}
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


def _is_ephemeral_burn_url(url: str) -> bool:
    """Provider task links such as dubai /content.mp4 are not a finished video file."""
    try:
        from app.services.generation_runtime.media_persist import _is_ephemeral_provider_media_url

        return bool(_is_ephemeral_provider_media_url(url))
    except Exception:
        host = ""
        try:
            from urllib.parse import urlparse

            host = str(urlparse(str(url or "")).hostname or "").lower()
        except Exception:
            host = ""
        return host.endswith("dubai3000.xyz")


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
    """Re-burn uses the newest clean plate. A burned file is never the source."""
    current = str(video_url or "").strip()
    outputs = _burn_output_keys(notes)
    origin = str((notes or {}).get("flower_ass_origin_url") or "").strip()
    saved_source = str((notes or {}).get("flower_ass_source_url") or "").strip()

    def usable(url: str) -> bool:
        key = _url_key(url)
        return bool(key) and key not in outputs and not _is_burn_file(url) and not _is_ephemeral_burn_url(url)

    if usable(current):
        return current
    if usable(origin_fallback):
        return origin_fallback
    if usable(origin):
        return origin
    if usable(saved_source):
        return saved_source
    return origin or saved_source or origin_fallback or current


def _latest_clean_shot_video(db: Any, shot: Any, outputs: set) -> str:
    """Newest non-burn asset for this shot. Burn files are named flower_*.mp4."""
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
    rows = query.order_by(Asset.id.desc()).limit(2000).all()
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
        if _url_key(url) in outputs or _is_ephemeral_burn_url(url):
            continue
        return url
    return ""


def _refresh_burn_url(url: str, db: Any) -> str:
    raw = str(url or "").strip()
    if not raw:
        return raw
    try:
        from app.services.generation_runtime.media_persist import _refresh_managed_media_url

        return str(_refresh_managed_media_url(raw, db) or raw)
    except Exception as exc:
        logger.warning("[FlowerAss] refresh video url skipped: %s", exc)
        return raw


def apply_flower_burn_to_shot(db: Any, shot: Any, user_id: int = 0, lines: Any = None) -> Optional[str]:
    """Auto burn reads the shot script. A later edit burns those lines onto the clean source."""
    video_url = _refresh_burn_url(str(getattr(shot, "video_url", None) or "").strip(), db)
    if not video_url:
        return None
    duration = getattr(shot, "duration", None)
    notes = _notes(shot)
    for key in ("flower_ass_origin_url", "flower_ass_source_url"):
        saved = str(notes.get(key) or "").strip()
        if saved:
            notes[key] = _refresh_burn_url(saved, db)
    outputs = _burn_output_keys(notes)
    latest_clean = _refresh_burn_url(_latest_clean_shot_video(db, shot, outputs), db)
    source_url = resolve_burn_source(video_url, notes, latest_clean)
    if _is_ephemeral_burn_url(source_url) or not source_url:
        raise ValueError("当前视频还是生成任务的临时地址，文件不完整，无法烧录。请等成片保存后再烧录。")
    script_events = extract_shot_libass_events(shot)
    if lines is not None:
        events = normalize_manual_burn_lines(lines, duration)
        by_text = {str(item.get("text") or ""): item for item in script_events}
        fallback = next((item for item in script_events if item.get("look")), None)
        for event in events:
            source = by_text.get(str(event.get("text") or "")) or fallback
            if not source:
                continue
            if source.get("look") and not event.get("look"):
                event["look"] = source["look"]
            if source.get("font_kind") and not event.get("font_kind"):
                event["font_kind"] = source["font_kind"]
    else:
        events = script_events
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
        notes["flower_ass_origin_url"] = source_url
        notes["flower_ass_source_url"] = source_url
    notes["flower_ass_draft"] = events
    if isinstance((result or {}).get("style"), dict):
        notes["flower_ass_style"] = result["style"]
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
