# -*- coding: utf-8 -*-
"""Whether a place's occupancy is still open, and the last beat map to continue from.

分集大纲、分集生成、全局统筹、现场编排共用这一份判定。
角色已离场，或再开始已经是另一个时间段，就是已结束：不附分布图。
未结束，或时间还没锁死的待判，才附最近一场最后一个 beat 的【角色道具世界分布图】。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.prompt_injection import wrap_injection_section

logger = logging.getLogger("api_logger")

OCCUPANCY_LABEL = "空间占用参考"

_BEAT_START_RE = re.compile(r"`?\[BEAT_START:([^\s\]]+)\]`?", re.IGNORECASE)
_BEAT_END_RE = re.compile(r"`?\[BEAT_END:([^\s\]]+)\]`?", re.IGNORECASE)
_MAP_HEADINGS = ("【角色道具世界分布图】", "【角色道具宫格分布图】")
_CURRENT_ENV_RE = re.compile(r"当前环境\s*[=＝]\s*([^｜|\n]+)")
_BASE_ENV_RE = re.compile(r"基准\s*[=＝]\s*主环境\s*[:：]\s*([^｜|\n]+)")
_TIME_KEYS = ("季节", "时段", "光变档", "昼夜")
_PERIODS = ("清晨", "白天", "中午", "黄昏", "上半夜", "下半夜")
_DAY_PERIODS = {"清晨", "白天", "中午", "黄昏"}
_NIGHT_PERIODS = {"上半夜", "下半夜"}
_STILL_STATES = {"仍在", "开场", "入画", "入画落定"}
_SKIP_RE = re.compile(r"次日|翌日|第二天|隔了一夜|隔夜|另一日|多年后|多年前|重生前|前世|另一年代")
_SKIP_HEADER_RE = re.compile(r"^(次日|翌日|第二天|隔了一夜|隔夜|另一日|多年后|多年前|重生前|前世|另一年代)")
_PLACE_FIELD_RE = re.compile(
    r"(?:地点|#当前地点|复用地点|所属主环境|主环境|名称)\s*[=＝:：]\s*([^\n｜|;；]+)"
)
_PLACE_HEAD_RE = re.compile(r"【(?:主环境|场景名称)】[ \t]*([^\n]+)")
_SPACE_LINE_RE = re.compile(r"空间\*{0,2}[】\]]?\s*[：:]\s*(.+)")
_TIME_LINE_RE = re.compile(
    r"(【本场时地】|【时间】|时间\*{0,2}\s*[：:]|时段\s*[=＝]|光变档\s*[=＝]|季节\s*[=＝]|昼夜\s*[=＝]|跳\s*[=＝]|范围\s*[=＝]|跨季\s*[=＝])"
)
_SCENE_START_RE = re.compile(r"\[SCENE_START:([^\]]+)\]", re.IGNORECASE)
_SCENE_END_RE = re.compile(r"\[SCENE_END:", re.IGNORECASE)


@dataclass
class PlaceOccupancy:
    place: str
    place_key: str
    episode_number: int
    episode_id: int
    scene_id: str
    scene_rank: Tuple[int, str]
    beat_id: str
    beat_number: int
    distribution_map: str
    time_text: str
    still_names: List[str] = field(default_factory=list)

    @property
    def sort_key(self) -> Tuple[int, Tuple[int, str], int]:
        return (int(self.episode_number), self.scene_rank, int(self.beat_number))


def normalize_place_name(value: object) -> str:
    text = str(value or "").strip()
    text = text.replace("＝", "=")
    text = re.split(r"[｜|]", text, maxsplit=1)[0]
    text = re.sub(r"^\d+\s*度", "", text)
    text = re.sub(r"_(仰天|破后|破损|完好)$", "", text)
    text = re.split(r"[（(]", text, maxsplit=1)[0]
    text = re.sub(r"[\s_`'\"“”‘’]+", "", text)
    return text.lower()


def scene_rank(scene_id: object) -> Tuple[int, str]:
    text = str(scene_id or "").strip()
    match = re.search(r"SC(\d+)", text, flags=re.IGNORECASE)
    number = int(match.group(1)) if match else 0
    return (number, text.upper())


def _beat_number(beat_id: object) -> int:
    match = re.search(r"(\d+)", str(beat_id or ""))
    return int(match.group(1)) if match else 0


def _iter_beat_bodies(source: str) -> List[Tuple[str, str]]:
    text = str(source or "")
    starts = list(_BEAT_START_RE.finditer(text))
    bodies: List[Tuple[str, str]] = []
    for index, start in enumerate(starts):
        beat_id = str(start.group(1) or index + 1).strip() or str(index + 1)
        next_start = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        end = _BEAT_END_RE.search(text, start.end())
        if end and end.start() <= next_start:
            body = text[start.end() : end.start()]
        else:
            body = text[start.end() : next_start]
        bodies.append((beat_id, body))
    return bodies


def _map_slice(body: str) -> str:
    text = str(body or "")
    indexes = [text.find(heading) for heading in _MAP_HEADINGS if heading in text]
    if not indexes:
        return ""
    return text[min(indexes) :].strip()


def _place_from_beat(body: str, map_text: str) -> str:
    for pattern, source in (
        (_CURRENT_ENV_RE, body),
        (_BASE_ENV_RE, map_text),
        (_BASE_ENV_RE, body),
    ):
        match = pattern.search(source or "")
        if match:
            name = str(match.group(1) or "").strip()
            if normalize_place_name(name):
                return name
    return ""


def compact_distribution_map(map_text: str) -> str:
    """Keep the position rows. Camera lines are not the continuity reference."""
    kept: List[str] = []
    for raw in str(map_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(_MAP_HEADINGS) or line.startswith("基准=") or line.startswith("基准＝"):
            kept.append(line)
            continue
        if line.startswith("CHAR:") or line.startswith("PROP:"):
            kept.append(line)
    if kept:
        if not kept[0].startswith("【角色道具"):
            kept.insert(0, "【角色道具世界分布图】")
        return "\n".join(kept)
    return str(map_text or "").strip()[:4000]


def still_present_names(map_text: str) -> List[str]:
    names: List[str] = []
    seen = set()
    for raw in str(map_text or "").splitlines():
        line = raw.replace("＝", "=").strip()
        if not line.startswith("CHAR:"):
            continue
        name_match = re.search(r"CHAR:\[@([^\]]+)\]", line)
        state_match = re.search(r"在场=([^｜|\s]+)", line)
        if not name_match or not state_match:
            continue
        state = state_match.group(1).strip()
        if state not in _STILL_STATES:
            continue
        name = name_match.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def iter_place_beats(framing_text: str) -> List[Tuple[str, str, str]]:
    """Last distribution map of each place inside one framing text, in beat order."""
    found: Dict[str, Tuple[str, str, str]] = {}
    order: List[str] = []
    for beat_id, body in _iter_beat_bodies(framing_text):
        map_text = _map_slice(body)
        if not map_text:
            continue
        place = _place_from_beat(body, map_text)
        key = normalize_place_name(place)
        if not key:
            continue
        if key not in found:
            order.append(key)
        found[key] = (beat_id, place.strip(), compact_distribution_map(map_text))
    return [found[key] for key in order]


def extract_time_fields(text: str) -> Dict[str, str]:
    source = str(text or "").replace("＝", "=")
    fields: Dict[str, str] = {}
    for key in _TIME_KEYS:
        match = re.search(rf"{key}\s*=\s*([^｜|\n]+)", source)
        if not match:
            continue
        value = match.group(1).strip()
        if value:
            fields[key] = value
    if "时段" not in fields:
        match = re.search(r"范围\s*=\s*([^｜|\n→]+)", source)
        if match:
            start = match.group(1)
            for period in _PERIODS:
                if period in start:
                    fields["时段"] = period
                    break
    if re.search(r"跨季\s*=\s*是", source):
        fields["跨季"] = "是"
    if re.search(r"(?<![\w])跳\s*=\s*是", source):
        fields["跳"] = "是"
    return fields


def time_brief(text: str) -> str:
    fields = extract_time_fields(text)
    parts = [f"{key}={fields[key]}" for key in ("季节", "时段", "光变档", "昼夜") if fields.get(key)]
    return "/".join(parts) if parts else "未锁"


def _time_lines(text: str) -> List[str]:
    return [
        line.strip()
        for line in str(text or "").splitlines()
        if line.strip() and _TIME_LINE_RE.search(line)
    ]


def _skip_marks_new_segment(text: str) -> bool:
    """次日只算在时间行、地点行，或单独成行的时间抬头上。对白里提到第二天不算。"""
    source = str(text or "").strip()
    if not _SKIP_RE.search(source):
        return False
    for line in source.splitlines() or [source]:
        stripped = line.strip()
        if not stripped or not _SKIP_RE.search(stripped):
            continue
        if _TIME_LINE_RE.search(stripped) or re.search(r"(地点|空间|场景名称|主环境)", stripped):
            return True
        if _SKIP_HEADER_RE.match(stripped):
            return True
    return False


def _window_at(source: str, start: int) -> str:
    line_start = source.rfind("\n", 0, start) + 1
    prev_break = source.rfind("\n", 0, max(0, line_start - 1))
    prev_line = source[prev_break + 1 : line_start].strip()
    place_end = source.find("\n", line_start)
    if place_end < 0:
        place_end = len(source)
    place_line = source[line_start:place_end].strip()
    forward = source[line_start : start + 500]
    if prev_line and (_TIME_LINE_RE.search(prev_line) or _SKIP_HEADER_RE.match(prev_line)):
        forward = f"{prev_line} {place_line}\n{forward}"
    return forward


def compare_time(previous_text: str, current_text: str) -> Optional[str]:
    """Return '' when the same segment, '另一时间段' when it moved, None when unknown."""
    current = str(current_text or "")
    if not current.strip():
        return None
    if _skip_marks_new_segment(current) and not _skip_marks_new_segment(str(previous_text or "")):
        return "另一时间段"
    scoped = "\n".join(_time_lines(current)) or current
    previous = extract_time_fields(previous_text)
    current_fields = extract_time_fields(scoped)
    if current_fields.get("跳") == "是":
        return "另一时间段"
    comparable = False
    for key in ("季节", "时段", "光变档"):
        left = previous.get(key, "")
        right = current_fields.get(key, "")
        if not left or not right:
            continue
        comparable = True
        if left != right:
            return "另一时间段"
    prev_period = previous.get("时段", "")
    day_night = current_fields.get("昼夜", "")
    if prev_period and day_night in {"日", "夜"}:
        comparable = True
        if day_night == "日" and prev_period in _NIGHT_PERIODS:
            return "另一时间段"
        if day_night == "夜" and prev_period in _DAY_PERIODS:
            return "另一时间段"
    if comparable:
        return ""
    return None


def judge_occupancy(record: PlaceOccupancy, current_text: str) -> Tuple[str, str]:
    if not record.still_names:
        return "已结束", "角色已离场"
    relation = compare_time(record.time_text, current_text)
    if relation == "另一时间段":
        return "已结束", "另一时间段"
    if relation == "":
        return "未结束", "同一时间段且角色仍在"
    return "待判", "时间未锁"


def _head_place(raw: object) -> str:
    text = re.split(r"[｜|]", str(raw or ""), maxsplit=1)[0].strip()
    parts = [part.strip() for part in text.split("·") if part.strip()]
    markers = set(_PERIODS) | {"日", "夜", "内", "外", "晴", "阴", "雨", "雪", "雾", "风", "霾"}
    if len(parts) >= 2 and any(part in markers for part in parts[1:]):
        return parts[0]
    return text


def _remember_place(raw: object, keys: List[str], seen: set) -> None:
    key = normalize_place_name(raw)
    if not key or key in seen or key in {"无", "待定", "未写"}:
        return
    if not re.search(r"[\w]", key, flags=re.UNICODE):
        return
    seen.add(key)
    keys.append(key)


def place_keys_in_text(text: str) -> List[str]:
    keys: List[str] = []
    seen: set = set()
    source = str(text or "")
    for match in _PLACE_FIELD_RE.finditer(source):
        _remember_place(match.group(1), keys, seen)
    for match in _PLACE_HEAD_RE.finditer(source):
        _remember_place(_head_place(match.group(1)), keys, seen)
    for match in _SPACE_LINE_RE.finditer(source):
        for chunk in re.split(r"[;；]", match.group(1)):
            _remember_place(re.split(r"[｜|]", chunk, maxsplit=1)[0], keys, seen)
    for _beat_id, place, _map in iter_place_beats(source):
        _remember_place(place, keys, seen)
    return keys


def judge_windows(record: PlaceOccupancy, windows: Sequence[str]) -> Tuple[str, str]:
    if not record.still_names:
        return "已结束", "角色已离场"
    usable = [window for window in windows if str(window or "").strip()]
    if not usable:
        return judge_occupancy(record, "")
    relations = [compare_time(record.time_text, window) for window in usable]
    known = [item for item in relations if item is not None]
    if not known:
        return "待判", "时间未锁"
    if len(known) == len(relations) and all(item == "另一时间段" for item in known):
        return "已结束", "另一时间段"
    if len(known) == len(relations) and all(item == "" for item in known):
        return "未结束", "同一时间段且角色仍在"
    return "待判", "同一地点有的场换了时间段"


def _scene_regions(split_text: str) -> List[Tuple[str, str]]:
    source = str(split_text or "")
    regions: List[Tuple[str, str]] = []
    for start in _SCENE_START_RE.finditer(source):
        scene_id = str(start.group(1) or "").strip()
        rest = source[start.end() :]
        end = _SCENE_END_RE.search(rest)
        body = rest[: end.start()] if end else rest[:4000]
        if scene_id:
            regions.append((scene_id, body))
    return regions


def scene_time_text(split_text: str, scene_id: str) -> str:
    wanted = str(scene_id or "").strip().lower()
    for sid, body in _scene_regions(split_text):
        if sid.lower() != wanted and wanted not in sid.lower():
            continue
        parts: List[str] = []
        for label in ("【场景名称】", "【本场时地】"):
            match = re.search(rf"{label}[^\n]+", body)
            if match:
                parts.append(match.group(0))
        return "\n".join(parts)
    return ""


def records_from_framing(
    *,
    framing_text: str,
    time_text: str,
    episode_number: int,
    episode_id: int,
    scene_id: str,
) -> List[PlaceOccupancy]:
    rank = scene_rank(scene_id)
    records: List[PlaceOccupancy] = []
    for beat_id, place, map_text in iter_place_beats(framing_text):
        key = normalize_place_name(place)
        if not key:
            continue
        records.append(
            PlaceOccupancy(
                place=re.sub(r"^\d+\s*度", "", str(place or "")).strip(),
                place_key=key,
                episode_number=int(episode_number or 0),
                episode_id=int(episode_id or 0),
                scene_id=str(scene_id or "").strip(),
                scene_rank=rank,
                beat_id=str(beat_id or "").strip(),
                beat_number=_beat_number(beat_id),
                distribution_map=map_text,
                time_text=str(time_text or ""),
                still_names=still_present_names(map_text),
            )
        )
    return records


def latest_per_place(
    records: Sequence[PlaceOccupancy],
    *,
    before_episode: Optional[int] = None,
    earlier_than: Optional[Tuple[int, Tuple[int, str]]] = None,
) -> List[PlaceOccupancy]:
    """Latest beat of each place.

    before_episode keeps earlier episodes.
    earlier_than is (episode_number, scene_rank) and also keeps earlier scenes
    of that same episode.
    """
    best: Dict[str, PlaceOccupancy] = {}
    for record in records:
        if before_episode is not None and record.episode_number > int(before_episode):
            continue
        if before_episode is not None and record.episode_number == int(before_episode):
            if earlier_than is None or earlier_than[0] != record.episode_number:
                continue
            if record.scene_rank >= earlier_than[1]:
                continue
        current = best.get(record.place_key)
        if current is None or record.sort_key > current.sort_key:
            best[record.place_key] = record
    return sorted(best.values(), key=lambda item: (item.place, item.sort_key))


def last_per_place_per_episode(records: Sequence[PlaceOccupancy]) -> List[PlaceOccupancy]:
    best: Dict[Tuple[str, int], PlaceOccupancy] = {}
    for record in records:
        key = (record.place_key, int(record.episode_number))
        current = best.get(key)
        if current is None or record.sort_key > current.sort_key:
            best[key] = record
    return sorted(best.values(), key=lambda item: (item.place, item.episode_number, item.sort_key))


def _format_names(names: Sequence[str]) -> str:
    cleaned = [f"CHAR:[@{name}]" for name in names if str(name or "").strip()]
    return "，".join(cleaned) if cleaned else "无"


def _section(
    record: PlaceOccupancy,
    current_text: str,
    *,
    chain: bool,
    judgment: Optional[Tuple[str, str]] = None,
) -> str:
    verdict, reason = judgment or judge_occupancy(record, current_text)
    head = (
        f"地点={record.place}｜来源集=EP{int(record.episode_number):02d}"
        f"｜场景={record.scene_id}｜末拍={record.beat_id}"
        f"｜上一时地={time_brief(record.time_text)}"
        f"｜仍在={_format_names(record.still_names)}"
        f"｜判定={verdict}｜因={reason}"
    )
    if verdict == "已结束":
        tail = "不附分布图。这一处重新初始化或重新入场，不继承上一场站位。"
    else:
        tail = record.distribution_map.strip() or "分布图为空。时间未锁时先判，判成已结束就不要沿用站位。"
    if chain:
        head += "｜用法=只供更后的集"
    return f"{head}\n{tail}"


def render_occupancy_reference(
    records: Sequence[PlaceOccupancy],
    *,
    current_text: str = "",
    current_by_place: Optional[Dict[str, str]] = None,
    judgments: Optional[Dict[Tuple[str, int, str, str], Tuple[str, str]]] = None,
    mode: str = "scene",
) -> str:
    if not records:
        return ""
    chain = mode == "outline"
    per_place = dict(current_by_place or {})
    decided = judgments or {}
    sections = []
    for record in records:
        key = (record.place_key, record.episode_number, record.scene_id, record.beat_id)
        sections.append(
            _section(
                record,
                per_place.get(record.place_key, current_text),
                chain=chain,
                judgment=decided.get(key),
            )
        )
    if mode == "outline":
        usage = "写第 N 集时，只读来源集小于 N、同一地点最近的一条。"
    elif mode == "script":
        usage = "本集只读来源集早于本集、同一地点最近的一条。场头地点行写占用=。"
    elif mode == "framing":
        usage = "同一主环境只读最近一条。未结束时开场锚、X、Y、Z、朝向、姿态、手持照抄仍在的人和独立道具。不抄机位、景别、望向。"
    else:
        usage = "每一场只读同一地点、早于本场的最近一条。空间占用写入【场景衔接】。"
    intro = (
        "先判这一处环境是否已经结束。角色已离场，或再开始已经是另一个时间段，就是已结束："
        "重新初始化，或让人重新入场，不抄坐标。"
        "未结束才用下面最近一集、最近一场、最后一个 beat 的【角色道具世界分布图】，开场站位与仍在的人、独立道具连续。"
        "判定=待判时先按本场时间判完：判成已结束就当这张图不存在。"
        "大纲和剧本不把坐标写进正文。"
        f"{usage}"
    )
    return wrap_injection_section(OCCUPANCY_LABEL, intro + "\n\n" + "\n\n".join(sections))


def _windows_for_place(text: str, place_key: str) -> List[str]:
    source = str(text or "")
    windows: List[str] = []
    for match in _PLACE_FIELD_RE.finditer(source):
        if normalize_place_name(match.group(1)) != place_key:
            continue
        windows.append(_window_at(source, match.start()))
    for match in _PLACE_HEAD_RE.finditer(source):
        if normalize_place_name(_head_place(match.group(1))) != place_key:
            continue
        windows.append(_window_at(source, match.start()))
    for match in _SPACE_LINE_RE.finditer(source):
        body = match.group(1)
        offset = match.start(1)
        cursor = 0
        for chunk in re.split(r"[;；]", body):
            found = body.find(chunk, cursor)
            cursor = found + len(chunk) if found >= 0 else cursor + len(chunk)
            if normalize_place_name(re.split(r"[｜|]", chunk, maxsplit=1)[0]) != place_key:
                continue
            at = offset + max(found, 0)
            windows.append(_window_at(source, at) if found >= 0 else chunk)
    return windows


def judge_against_text(
    record: PlaceOccupancy,
    text: str,
    *,
    episode_time: bool = False,
) -> Tuple[str, str]:
    """Judge one place from the windows that name it, not from the whole script."""
    windows = _windows_for_place(text, record.place_key)
    decisive = [window for window in windows if compare_time(record.time_text, window) is not None]
    if not decisive and episode_time:
        lines = _time_lines(text)
        if lines:
            decisive = ["\n".join(lines)]
    if decisive:
        return judge_windows(record, decisive)
    if windows:
        return judge_windows(record, windows)
    if episode_time:
        return judge_occupancy(record, "\n".join(_time_lines(text)))
    return judge_occupancy(record, "")


def load_occupancy_records(db: object, project_id: int) -> List[PlaceOccupancy]:
    from app.models.all_models import Episode
    from app.services.project_episode_utils import (
        _resolve_episode_sort_number,
        _sort_project_episodes,
    )
    from app.services.script_analysis_flow.analyze_scene_stages import (
        load_scene_subskill_results_map,
        load_stage1_output_text,
    )
    from app.services.soft_delete import _active_episode_clause

    project = int(project_id or 0)
    if project <= 0 or db is None:
        return []
    episodes = (
        db.query(Episode)
        .filter(Episode.project_id == project, _active_episode_clause())
        .all()
    )
    records: List[PlaceOccupancy] = []
    for episode in _sort_project_episodes(list(episodes)):
        number = int(_resolve_episode_sort_number(episode) or 0)
        episode_id = int(getattr(episode, "id", 0) or 0)
        try:
            result_map = load_scene_subskill_results_map(db, episode_id)
            split_text = load_stage1_output_text(db, episode_id, "scene_split")
        except Exception as exc:
            logger.warning(
                "[space_occupancy] skip episode_id=%s: %s",
                episode_id,
                exc,
            )
            continue
        if not isinstance(result_map, dict):
            continue
        for scene_id, scene_map in result_map.items():
            if not isinstance(scene_map, dict):
                continue
            framing = str(scene_map.get("framing") or "").strip()
            if not framing:
                continue
            records.extend(
                records_from_framing(
                    framing_text=framing,
                    time_text=scene_time_text(split_text, str(scene_id)),
                    episode_number=number,
                    episode_id=episode_id,
                    scene_id=str(scene_id),
                )
            )
    return records


def _episode_number(db: object, episode_id: int) -> int:
    from app.models.all_models import Episode
    from app.services.project_episode_utils import _resolve_episode_sort_number

    episode = db.query(Episode).filter(Episode.id == int(episode_id or 0)).first()
    return int(_resolve_episode_sort_number(episode) or 0)


def build_outline_occupancy_injection(db: object, project_id: int) -> str:
    records = last_per_place_per_episode(load_occupancy_records(db, project_id))
    block = render_occupancy_reference(records, mode="outline")
    if block:
        logger.info(
            "[space_occupancy] outline project=%s places=%s",
            project_id,
            len(records),
        )
    return block


def build_episode_script_occupancy_injection(
    db: object,
    project_id: int,
    episode_number: int,
    outline_text: str = "",
) -> str:
    records = latest_per_place(
        load_occupancy_records(db, project_id),
        before_episode=int(episode_number or 0),
    )
    named = place_keys_in_text(outline_text)
    if named:
        records = [record for record in records if record.place_key in named]
    judgments = {
        (record.place_key, record.episode_number, record.scene_id, record.beat_id): judge_against_text(
            record,
            str(outline_text or ""),
            episode_time=True,
        )
        for record in records
    }
    block = render_occupancy_reference(
        records,
        judgments=judgments,
        mode="script",
    )
    if block:
        logger.info(
            "[space_occupancy] script project=%s episode=%s places=%s",
            project_id,
            episode_number,
            len(records),
        )
    return block


def _matching(records: Iterable[PlaceOccupancy], keys: Sequence[str]) -> List[PlaceOccupancy]:
    wanted = {key for key in keys if key}
    if not wanted:
        return []
    return [record for record in records if record.place_key in wanted]


def build_scene_split_occupancy_injection(
    db: object,
    project_id: int,
    episode_id: int,
    script_text: str,
) -> str:
    number = _episode_number(db, episode_id) if int(episode_id or 0) > 0 else 0
    records = latest_per_place(
        load_occupancy_records(db, project_id),
        before_episode=number,
    )
    matched = _matching(records, place_keys_in_text(script_text))
    judgments = {
        (record.place_key, record.episode_number, record.scene_id, record.beat_id): judge_against_text(
            record,
            script_text,
            episode_time=True,
        )
        for record in matched
    }
    block = render_occupancy_reference(
        matched,
        judgments=judgments,
        mode="split",
    )
    if block:
        logger.info(
            "[space_occupancy] scene_split project=%s episode=%s places=%s",
            project_id,
            number,
            len(matched),
        )
    return block


def build_framing_occupancy_injection(
    db: object,
    project_id: int,
    episode_id: int,
    scene_id: str,
    scene_text: str,
) -> str:
    number = _episode_number(db, episode_id) if int(episode_id or 0) > 0 else 0
    records = latest_per_place(
        load_occupancy_records(db, project_id),
        before_episode=number,
        earlier_than=(number, scene_rank(scene_id)),
    )
    matched = _matching(records, place_keys_in_text(scene_text))
    judgments = {
        (record.place_key, record.episode_number, record.scene_id, record.beat_id): judge_against_text(
            record,
            scene_text,
            episode_time=True,
        )
        for record in matched
    }
    block = render_occupancy_reference(
        matched,
        judgments=judgments,
        mode="framing",
    )
    if block:
        logger.info(
            "[space_occupancy] framing project=%s episode=%s scene=%s places=%s",
            project_id,
            number,
            scene_id,
            len(matched),
        )
    return block
