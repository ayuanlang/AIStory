# -*- coding: utf-8 -*-
"""Prompt-block helpers for episode-script generation."""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from app.services.story_generator_llm import (
    _PREFILL_TEXT_KEYS,
    _field_text,
    format_outline_registry_block,
    format_story_creative_input_block,
    structured_prefill_has_text,
)


def build_episode_generation_guidance_prompt_block(guidance: Optional[str]) -> str:
    """Build the high-priority user-prompt block for this-episode writing guidance.

    Empty / whitespace-only input yields an empty string so callers can prepend safely.
    """
    text = str(guidance or "").strip()
    if not text:
        return ""
    return (
        "【本集生成指导 / Episode Generation Guidance — HIGHEST PRIORITY】\n"
        "The following is the user's explicit high-priority writing brief for THIS episode only.\n"
        "You MUST fulfill it in the episode script. It outranks Extra Notes, optional flavor, and default stylistic preferences.\n"
        "It MUST NOT violate hard format contracts, previous-episode handoff, character-canon identity, or safety constraints.\n"
        "If a request conflicts with those hard constraints, keep the hard constraint and fulfill the rest of the guidance.\n"
        "这条指导只约束正文。标题不抄这条指导，也不抄预告片侧重点、取材范围或其他指导原句。标题是不超过 8 字的剧情名。\n\n"
        f"{text}\n\n"
    )


def build_structured_prefill_prompt_block(source: Any, *, trailer: bool) -> str:
    """Inject the structured prefill as a required source for episode and trailer writing.

    A blank prefill yields an empty string. Trailer length is the 8000 字 scale. 核心建置,
    人物弧光, and the foundational worldview ride inside 建置, 娱乐时间, and 反派逼近.
    """
    if not structured_prefill_has_text(source):
        return ""
    body = format_story_creative_input_block(source).strip()
    from app.services.script_mode_helpers import is_emotion_driven_script_mode

    emotion_driven = is_emotion_driven_script_mode(_field_text(source, "script_mode")) or (
        not _field_text(source, "script_mode") and "上升冲突八阶" in body
    )
    if trailer:
        rules = (
            "【剧本框架 — 预告片重要依据】\n"
            "注入链是项目信息 → 剧本框架 → 分集大纲 → 剧本生成。预告落实这份剧本框架。概念、思想、对抗、人物弧光、节拍事件、对白种子、世界背景和剧情背景以剧本框架为准。分集大纲只提供某一段落在哪一集、时间和在场名。大纲把同一件事写成另一套时，改回剧本框架。预告必须把核心建置、人物弧光和基础世界观演进已有短拍，让没看过正片的观众读得出来。\n"
            "核心建置＝概念=I1 高概念、思想=I2 主控思想、对抗=I3、I3b 三幕价值弧、I4 故事世界。人物弧光＝I5。基础世界观＝世界背景＋剧情背景，并含 I4。\n"
            "节奏与篇幅：按 8000 字写，不超过 8000 字。高光短拍 16–32 拍。不另开说明拍，不口播。不得为了少于 16 拍把多人多空间写回一句，也不得拆过 32 拍。末拍停在大危机和大转折已经落到画面上的那一下，这一拍之后的胜负、揭秘和收束不写。每一拍都选中或创作一句高光对白和一下高光动作，同一个人写在同一拍；只有对白或只有动作的拍不合格。动作写到哪一只手、哪一件物、哪一处可见变化，不写通报、下令、安排。新写的对白是口语短句，不写因此、然而、我必须让你知道。跑、追、飞、掠、行驶的主体仍写从哪到哪、跨距和用时，速度由这两数读出；这段路落在宿主，不落在驾驶舱。\n"
            "概念=I1：同一拍里一句高光对白加一下高光动作，点出谁要什么、谁在挡、失败失去什么。"
            "思想=I2：同一拍里一句高光对白加一下高光动作，点出价值加原因，不宣布成主题。"
            "对抗=I3：落在娱乐时间，并在反派逼近顶一下，两句相反的原则当场相撞。"
            "I3b 只演取材范围内各幕的价值方向，不演谁胜谁负。"
            "I4 与世界背景落在建置：时代、制度、礼法、能力边界里，缺了就看不懂这一拍选择的那一句，用动作或对白演出来。\n"
            "人物弧光要能读出极性：旧的自己、被这套世界逼着要改的那一下、弧光往哪边走。用动作或对白演。终场的胜负和秘密答案不说破。取材范围内节拍上的对话种子，针对主控思想、对抗鸿沟危机、价值弧、压力场、人物前提弧光的，原句入短拍，并写出说者的微动作和表情；对白再写听者的。自白只写说者。\n"
            "预填里的 11–15 拍和谁胜谁负不入选材。空字段不另造一套故事。"
            "AI优势应用与劣势回避若点了本段要演的拍，短拍里写出那一层特效画面；回避项保持改写，不把风险动作写回。"
            "取材拍所在集若有专业行，高光动作和高光对白按那个领域的规程来，不改成外行做法。领域=无或没有这行时，不硬塞术语。\n"
            "预告还要单独写「本集AI优势应用与劣势回避」：继承上游已经点给这些拍的条目，再只针对本条预告的场面新分析一次，并在短拍里演出来。\n\n"
        )
    else:
        if emotion_driven:
            rules = (
                "【剧本框架 — 分集重要依据】\n"
                "注入链是项目信息 → 剧本框架 → 分集大纲 → 剧本生成。这一份是剧本框架，全局只写一次。情绪驱动类的骨架是埃格里《编剧的艺术》的上升冲突，不是救猫咪。\n"
                "前提、统一的对立面、社会与人性、八阶事件、故事环总表、经典借鉴的整体逻辑、世界背景、剧情背景、人物、时间节点、专业领域和对白种子，以剧本框架为准。本集只演分集大纲冲突阶里已锁的那一阶或连续几阶，并演该集已锁的故事环步。环步落在这一阶里，不另写一件事。不把证明和结局提前演完。禁止改写成救猫咪拍。大纲的基本点是本集经典借鉴的最底下一处，必须先落地，不得换成另一部或另一下。可以再加借鉴点，经典或流行热点都可以，与基本点综合起来实现本集大纲的目标。符合本集背景和主题后按本集剧情融合，不能硬拼。\n"
                "针对=前提、统一的对立面、社会层、人性层、过渡、危机、证明的对话种子，原句入戏，并写出说者与听者的微动作和表情。自白只写说者。\n"
                "本集落在哪一阶、时间、环境和在场名用分集大纲。场景以简单为先。四壁每壁只有封闭面再加一具贴附，中部只有一个主体加必须的配套和必要配饰。大纲空间行写明本集涉及的每一处，可以多处，并锁了每一处主体。正文这些地方都用上。这一处出现之后先用已有主体，能落在桌面的全息控制不另起立式台。做不到或再加就超负载，就换大纲里的另一处，不在旧环境加主体。非封闭远景不计负载。大纲把同一阶写成另一件事时，改回剧本框架。空字段不另造一套故事。"
                "AI优势应用与劣势回避和大纲本集 AI 行点名了本集的特效时，正文写出那一层形状、规模或季节介质；回避项保持改写。"
                "另外必须单独写「本集AI优势应用与劣势回避」：继承行登记上游已经点给本集的条目，本集分析只看本集场面再写一次，两段都要在 Beat 里演出来，不能只抄上游。\n\n"
            )
        else:
            rules = (
            "【剧本框架 — 分集重要依据】\n"
            "注入链是项目信息 → 剧本框架 → 分集大纲 → 剧本生成。这一份是剧本框架，全局只写一次。概念=I1，思想=I2，对抗=I3，人物弧光=I5，节拍事件、对白种子、世界背景、剧情背景、时间节点和专业领域以剧本框架为准，都是本集必须回指的依据。\n"
            "本集只演落在分集大纲已锁救猫咪拍里的那一层。不把全剧弧光和结局提前演完。专名、对白种子、设定句要进本集相关场面。落到本集拍上、针对主控思想、对抗鸿沟危机、价值弧、压力场、人物前提弧光的对话种子，原句入戏，并写出说者与听者的微动作和表情。自白只写说者。大纲的基本点是本集经典借鉴的最底下一处，必须先落地，不得换成另一部或另一下。可以再加借鉴点，经典或流行热点都可以，与基本点综合起来实现本集大纲的目标。符合本集背景和主题后按本集剧情融合，不能硬拼。\n"
            "本集落在哪一拍、时间、环境和在场名用分集大纲。场景以简单为先。四壁每壁只有封闭面再加一具贴附，中部只有一个主体加必须的配套和必要配饰。大纲空间行写明本集涉及的每一处，可以多处，并锁了每一处主体。正文这些地方都用上。这一处出现之后先用已有主体，能落在桌面的全息控制不另起立式台。做不到或再加就超负载，就换大纲里的另一处，不在旧环境加主体。非封闭远景不计负载。大纲专业行写了领域时，这一下的动作按规程做完，对白按这个身份说出权限、顺序或后果。领域=无的集不硬塞术语。这一拍的事件、概念、思想、对抗、弧光以剧本框架为准。大纲把同一拍写成另一件事时，改回剧本框架。空字段不另造一套故事。"
            "AI优势应用与劣势回避和大纲本集 AI 行点名了本集的特效时，正文写出那一层形状、规模或季节介质；回避项保持改写。"
            "另外必须单独写「本集AI优势应用与劣势回避」：继承行登记上游已经点给本集的条目，本集分析只看本集场面再写一次，两段都要在 Beat 里演出来，不能只抄上游。\n\n"
        )
    return f"{rules}{body}\n\n{format_outline_registry_block(source)}\n\n"


_SENTENCE_SPLIT = re.compile(r"([。！？；])")
_SENTENCE_NORM = re.compile(r"[\s，。！？；、,.!?;:：\"“”'‘’「」【】（）()|｜\-—#*]+")
_LABEL_PREFIX = re.compile(r"^(?:[#*\-]+\s*)?(?:[^。！？；:：\n]{1,24}[:：]\s*)")
_MIN_DUP_CHARS = 8


def _norm_sentence(text: str) -> str:
    return _SENTENCE_NORM.sub("", str(text or ""))


def _compare_body(text: str) -> str:
    return _norm_sentence(_LABEL_PREFIX.sub("", str(text or "").strip(), count=1))


def _prefill_sentence_norms(source: Any) -> set[str]:
    norms: set[str] = set()
    for key in _PREFILL_TEXT_KEYS:
        raw = _field_text(source, key)
        if not raw:
            continue
        for part in re.split(r"[。！？；\n]+", raw):
            norm = _norm_sentence(part)
            if len(norm) >= _MIN_DUP_CHARS:
                norms.add(norm)
        whole = _norm_sentence(raw)
        if len(whole) >= _MIN_DUP_CHARS:
            norms.add(whole)
    return norms


def _sentence_repeats_prefill(text: str, norms: set[str]) -> bool:
    norm = _compare_body(text)
    if len(norm) < _MIN_DUP_CHARS:
        return False
    if norm in norms:
        return True
    return any(_near_copy(norm, other) for other in norms)


def _near_copy(left: str, right: str) -> bool:
    if left == right:
        return True
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    if len(short) < _MIN_DUP_CHARS or short not in long:
        return False
    return len(short) / len(long) >= 0.9


def _framework_line_is_structural(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("##"):
        return True
    markers = (
        "[STORY_DNA_",
        "[SCRIPT_TITLE:",
        "Episode Coverage",
        "Planned:",
        "时间节点",
        "世界背景",
        "剧情背景",
        "专业领域",
        "#功能",
        "#身份",
    )
    return any(marker in line for marker in markers)


def _drop_duplicate_sentences(line: str, norms: set[str]) -> str:
    pieces = _SENTENCE_SPLIT.split(line)
    kept: list[str] = []
    index = 0
    while index < len(pieces):
        text = pieces[index]
        delim = ""
        step = 1
        if index + 1 < len(pieces) and pieces[index + 1] in "。！？；":
            delim = pieces[index + 1]
            step = 2
        if text.strip() and _sentence_repeats_prefill(text, norms):
            index += step
            continue
        kept.append(text + delim)
        index += step
    return "".join(kept).strip()


def dedupe_framework_against_prefill(framework_md: str, source: Any) -> str:
    """Drop framework sentences that already appear in the structured prefill.

    Episode blocks stay whole: they place a beat in an episode and add the
    because/so/but chain plus listener detail. Headings, time nodes, world
    lines, and registered entities stay whole for the same reason.
    """
    raw = str(framework_md or "")
    if not raw.strip() or not structured_prefill_has_text(source):
        return raw
    norms = _prefill_sentence_norms(source)
    if not norms:
        return raw
    kept_lines: list[str] = []
    in_episode = False
    for line in raw.splitlines():
        if "[EPISODE_BLOCK_START" in line:
            in_episode = True
            kept_lines.append(line)
            continue
        if "[EPISODE_BLOCK_END" in line:
            in_episode = False
            kept_lines.append(line)
            continue
        if in_episode or _framework_line_is_structural(line):
            kept_lines.append(line)
            continue
        kept = _drop_duplicate_sentences(line, norms)
        if kept:
            kept_lines.append(kept)
    return "\n".join(kept_lines)


def build_framework_prompt_block(framework_md: str, source: Any) -> str:
    """Framework input for script generation, with prefill repeats removed."""
    raw = str(framework_md or "").strip()
    if not raw:
        return ""
    if not structured_prefill_has_text(source):
        return f"{raw}\n\n"
    body = dedupe_framework_against_prefill(raw, source).strip() or raw
    return (
        "【分集大纲 — 只保留第 9 节】\n"
        "剧本框架和这份分集大纲都要落实。全局事实以剧本框架为准。和剧本框架重复的句子已经从这里删去。\n"
        "这里只使用第 9 节：本集盖住哪一段、入和出、本集时间、在场名、摘要里的因为所以但是、说者和听者的微动作、本集 AI 行、本集专业行、本集驱动行，以及本集基本点。专业行写了领域时，动作和对白按这一行来。驱动行的最大项是角色弧光和冲突，正文里要演出来。基本点必须先落地，可以再加借鉴点。\n"
        "这些落点必须符合剧本框架。大纲若把同一段写成另一件事、另一个人或另一季，改回剧本框架，分集落点仍用大纲。\n\n"
        f"{body}\n\n"
    )


def resolve_trailer_sample_range(
    *,
    episode_from: Optional[int],
    episode_to: Optional[int],
    series_episode_count: int,
) -> tuple[int, int]:
    """Lock the inclusive episode span this trailer may sample.

    Missing bounds mean the whole series: episode 1 through series_episode_count.
    """
    try:
        total = int(series_episode_count)
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        raise ValueError("episodes_count is required to place the trailer range")

    def _parse(value: Optional[int], label: str) -> Optional[int]:
        if value is None or str(value).strip() == "":
            return None
        try:
            num = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be an integer")
        if num <= 0:
            raise ValueError(f"{label} must be greater than 0")
        return num

    start = _parse(episode_from, "trailer_episode_from")
    end = _parse(episode_to, "trailer_episode_to")
    if start is None:
        start = 1
    if end is None:
        end = total
    if start > total:
        raise ValueError(f"trailer_episode_from must be within 1..{total}")
    if end > total:
        raise ValueError(f"trailer_episode_to must be within 1..{total}")
    if start > end:
        raise ValueError("trailer_episode_from must be less than or equal to trailer_episode_to")
    return start, end


PLOT_TITLE_MAX = 8
TRAILER_LIST_TITLE_MAX = 24

_TITLE_INSTRUCTION_LABELS = (
    "本集生成指导",
    "生成指导",
    "预告片侧重点",
    "预告片重点",
    "侧重点",
    "取材范围",
    "结构化预填",
)


def clamp_plot_title(
    raw: str,
    *,
    limit: int = PLOT_TITLE_MAX,
    instructions: Optional[Iterable[str]] = None,
) -> str:
    """Short plot name. Guidance, focus, and other briefs never become the title."""
    text = " ".join(str(raw or "").split())
    if not text:
        return ""
    text = re.split(r"[。！？!?；;\n]", text, maxsplit=1)[0].strip()
    for label in _TITLE_INSTRUCTION_LABELS:
        if text.startswith(label):
            text = text[len(label):].lstrip("：:，, ")
            break
    if "·" in text and text.startswith("预告"):
        text = text.split("·")[-1].strip()
    text = re.sub(r"^预告(?:片)?\s*[-—:：]\s*", "", text).strip()
    text = text.strip("·-— ")
    if re.fullmatch(r"第\d+-\d+集", text):
        return ""
    compact = re.sub(r"\s+", "", text)
    for brief in instructions or ():
        blob = re.sub(r"\s+", "", str(brief or ""))
        if not compact or not blob:
            continue
        if compact == blob or (len(compact) >= 5 and compact in blob):
            return ""
    for sep in ("：", ":"):
        if sep not in text:
            continue
        left, right = text.split(sep, 1)
        left = left.strip()
        if left and len(left) <= limit and len(right.strip()) > limit:
            text = left
        break
    if len(text) > limit:
        text = text[:limit].rstrip()
    return text


def rewrite_script_heading(
    content: str,
    plot_title: str,
    *,
    trailer: bool,
    episode_number: int = 0,
) -> str:
    """Make the saved H1 match the short list title."""
    title = str(plot_title or "").strip()
    if trailer:
        replacement = f"# 预告-{title}" if title else "# 预告"
    elif title:
        replacement = f"# {int(episode_number)}-{title}"
    else:
        return content
    lines = str(content or "").splitlines()
    for index, line in enumerate(lines):
        if not line.strip().startswith("#"):
            continue
        lines[index] = replacement
        return "\n".join(lines)
    return content


def format_trailer_episode_title(
    *,
    seq: int,
    episode_title: str = "",
    episode_from: int,
    episode_to: int,
    series_episode_count: int,
    focus: Optional[str] = None,
) -> str:
    """List title. Sequence and range stay; focus and briefs stay out."""
    parts = [f"预告片{int(seq)}"]
    if int(episode_from) != 1 or int(episode_to) != int(series_episode_count):
        parts.append(f"第{int(episode_from)}-{int(episode_to)}集")
    title = clamp_plot_title(
        episode_title,
        instructions=(focus,) if str(focus or "").strip() else (),
    )
    if title:
        parts.append(title)
    composed = "·".join(parts)
    if len(composed) <= TRAILER_LIST_TITLE_MAX or not title:
        return composed
    prefix_len = len(composed) - len(title)
    room = TRAILER_LIST_TITLE_MAX - prefix_len
    if room < 2:
        parts.pop()
        return "·".join(parts)
    parts[-1] = title[:room].rstrip()
    return "·".join(parts)


def build_trailer_generation_prompt_block(
    *,
    focus: Optional[str] = None,
    episode_from: Optional[int] = None,
    episode_to: Optional[int] = None,
) -> str:
    """Highest-priority brief when this call writes a trailer, not a series episode."""
    focus_text = str(focus or "").strip()
    has_range = episode_from is not None and episode_to is not None
    if has_range:
        range_block = (
            f"取材范围=第{int(episode_from)}集到第{int(episode_to)}集。\n"
            "只从全局框架里属于这一段的剧情取样，按这一段的故事顺序演来龙去脉。\n"
            "这一段之外的集只可当作已经发生的公开背景，不把范围外的高光、转折和结局当成这条预告的主体。\n"
            "范围内也只取建置、娱乐时间、反派逼近。范围外的最终揭秘仍然不演，范围内的结局拍也不演。\n"
            "The pieces come from 建置 (beats 01–05: Opening, Theme Stated, Set-up, Catalyst, Debate), 娱乐时间 (Fun and Games), and 反派逼近 (Bad Guys Close In) inside this episode range, in that order. "
            "When the range covers more than one episode, locking the trailer to one episode's story circle fails. "
            "When the range is a single episode, play only those three beats from it and leave its ending unplayed.\n"
        )
        span_sentence = (
            "Because the selection spans different stages inside the locked episode range, those plot-matched locations "
            "become multiple main environments that carry the trailer. "
            "If the range really happens in only one registered space, use that one space. "
        )
    else:
        range_block = (
            "取材范围=全剧，从头到尾。\n"
            "贯穿全剧仍只取三段，按故事顺序：建置（01–05：Opening、ThemeStated、铺垫、Inciting、Debate）、娱乐时间（FunGames）、反派逼近（BadGuysCloseIn）。建置含这五拍，不收成只有铺垫。\n"
            "Sample beats 01–05, Fun and Games, and Bad Guys Close In across the series, in that order. Do not sample the ending. "
            "Locking the trailer to one episode's story circle fails.\n"
        )
        span_sentence = (
            "Because the selection spans different stages of the whole series, those plot-matched locations "
            "become multiple main environments that carry the trailer. "
        )
    if focus_text:
        focus_block = (
            f"侧重点={focus_text}\n"
            "选材、高光比重和收口都围着这一侧重，但只在建置、娱乐时间、反派逼近里加重。侧重点不改取材范围，不改去结局，也不许因此揭秘最终 Boss 或终极秘密。侧重点不写进标题。\n"
        )
    else:
        focus_block = "侧重点=未指定。比重按建置、娱乐时间、反派逼近来分，娱乐时间最重。不取结局。\n"
    return (
        "【预告片生成 / Trailer — HIGHEST PRIORITY】\n"
        "This call writes ONE new trailer. It does not replace any earlier trailer or any series episode. "
        "It is not a compressed episode, and not a highlight reel pasted without a throughline.\n"
        "Story-circle completeness, previous-episode handoff, and next-episode setup do not apply.\n"
        f"{range_block}"
        f"{focus_block}"
        "交代剧情又留悬疑: a viewer who has not seen the series must still grasp the story's 来龙去脉: "
        "who wants what, what starts the trouble, how the conflict escalates, and where the pressure is heading. "
        "Join the pieces with cause and result (因为 / 于是). "
        "Keep a question open: stop on the big crisis and the big turn, once both are visible, and leave the result unplayed. "
        "The throughline must be followable, and the ending must stay unspoiled. "
        "A pile of unrelated cool shots fails. A trailer too cryptic to follow also fails.\n"
        "剧情背景: the trailer must also play the story background. "
        "Read the framework lines whose text starts with 剧情背景. "
        "Those lines are the public situation already in force, the relationship history the audience needs, "
        "and why this conflict cannot wait. "
        "When the framework has no per-episode blocks, take those same three from the basic story thread's public situation. "
        "Play them in an early beat with a visible action or a spoken line, "
        "so a viewer who has not seen the series knows what bind these people are already in. "
        "Do not paste the Lore sentence as narration. "
        "Do not use that beat to state later plot, the ending, the final boss, or an unrevealed secret. "
        "When 取材范围 does not start at episode 1, that background is the public situation already in force "
        "at the first episode of the range.\n"
        "世界背景: the trailer must also play the world background, the other half of the foundational worldview. "
        "Read the framework lines whose text starts with 世界背景. "
        "That line is the rule, institution, rite, or ability boundary without which the opening choice cannot be understood. "
        "Play it in 建置 with a visible action or a spoken line, in the same stretch as I4 故事世界. "
        "Do not paste the Lore sentence as narration. "
        "Do not use that beat to state later plot, the ending, the final boss, or an unrevealed secret.\n"
        "核心建置与人物弧光: the trailer must embody both, inside the beats it already plays. "
        "核心建置 is who wants what and who blocks it (I1), the value plus its because (I2), "
        "the opposing principle and the costly choice (I3), the value direction of each act inside the locked range (I3b), "
        "and the story world that forces the choice (I4). "
        "人物弧光 (I5) must be readable as a polarity: the old self, the moment this world forces a change, and which way the arc turns. "
        "Play each with an action or a spoken line. Do not announce them as a theme. "
        "Leave who wins, and any secret answer, unsaid.\n"
        "选材重点锁三段，按故事顺序：建置（01–05：Opening、ThemeStated、铺垫、Inciting、Debate）→ 娱乐时间（FunGames）→ 反派逼近（BadGuysCloseIn）。建置含这五拍，不收成只有铺垫。\n"
        "建置 includes all five beats. Do not collapse it to Set-up alone. "
        "It plays the opening image, the stated theme, who these people are, the catalyst, and the debate. "
        "娱乐时间 plays how the conflict escalates and carries the highlights. "
        "The last beat is the big crisis and the big turn together: the opponent closes in, the situation turns, and the result stays unplayed. When 反派逼近 falls inside the range, the trailer stops on that crest. "
        "When any of beats 01–05, Fun and Games, or Bad Guys Close In falls inside the locked 取材范围, the trailer must include that beat. "
        "When it falls outside the range, do not reach outside the range, and do not replace it with an ending beat.\n"
        "不涉及结局: do not play AllIsLost, DarkNight, BreakThree, Finale, or FinalImage. "
        "Do not play ChoicePrice or ThemeProof. Do not show who wins. "
        "一无所有、灵魂黑夜、进入终章、终场、终场画面都不入选材。\n"
        "地点由选材决定: first lock the 建置, 娱乐时间, and 反派逼近 pieces this trailer plays. "
        "Then each piece's place is the §8 registered location where that actual plot happens "
        "in the global framework (§9 Episode Scene Environments / Scene-Event Continuity of the episode that owns the turn), "
        "copied character-for-character. "
        "The events in the beat are the events the framework already places in that environment. "
        "Choosing a location first, then fitting plot into it, fails. "
        f"{span_sentence}"
        "Two selected turns that really happen in the same registered space share it. "
        "Adding a place only to raise the environment count, a new location, a near-synonym rename, "
        "or moving a turn into a prettier space fails. "
        "Different §8 places are different scenes. Each scene header `地点=` is the place its beats use. Do not write 主环境.\n"
        "信念对撞与底层进具体 Beat: the selected pieces must play the global framework's "
        "`#信念对撞` (主角信念 vs 对手信念) and `#底层=社会|哲学|道德` inside the beat text. "
        "Read §3 `#信念对撞` / `#对位价值`, §4 `#信念对撞` / `#底层` / `#两难引擎`, "
        "and §2 `#底层冲突:主攻=`. "
        "In the beat, a visible action or a spoken line shows the protagonist refusing to drop that belief "
        "while the opponent refuses to drop the opposite belief. "
        "The locked layer is what makes that choice costly in the same beat: "
        "`社会` = institution, class, or public opinion; "
        "`哲学` = what counts as real, free, or fated; "
        "`道德` = what is right, who is owed, and whether the aim excuses the harm. "
        "Play the framework's 主攻 layer. A layer the framework already stacks may enter the same beat. "
        "Do not give 社会, 哲学, and 道德 one slogan each. "
        "Remove the collision and the beat still works as a task: that beat fails. "
        "Remove the layer and the cost gets lighter: that beat fails. "
        "Do not have a character announce the belief or the theme. "
        "Leave `#ThemeProof` unplayed.\n"
        "不能揭秘最终 Boss 与终极秘密: the final boss is the §8 `#隐藏反派` with 体量=幕后, "
        "the 真身 on §6 `#Boss可见层`, and the person named by `#隐藏反派揭露`. "
        "The ultimate secret is the author-layer answer on §8 核心秘密揭秘轨, its 关键揭 and 收束, and L4 终局真相. "
        "The trailer may show that person's public face, plus subordinates, proxies, and event pressure, "
        "and may keep an early fragment that does not answer the secret. "
        "It must not play the reveal beat. Dialogue, action, narration, on-screen text, 核心重点, and the visible entity ledger "
        "must not state who the final boss is or what the ultimate secret is. "
        "Selecting the reveal scene or the secret's 收束 as trailer material fails.\n"
        "The body is 高光剧情. The trailer must play all three kinds, each as a scene fragment:\n"
        "1) 动作: a visible action with a clear result.\n"
        "2) 对白: lines spoken in the scene, including the framework's iconic and conflict lines.\n"
        "3) 情节: a plot turn the audience can follow — what changes, and why the next piece follows.\n"
        "每一拍的高光对白与高光动作: every beat selects or creates both. "
        "Select the framework's iconic or conflict line and the action already in that moment when they land as highlights. "
        "If that moment has no highlight line, or no highlight action, write the missing one for the same person in the same moment. "
        "The line is spoken. The action has a visible result. Both stay in that one beat. "
        "Another person's line or action is another beat, and that beat also has its own highlight line and highlight action. "
        "A beat with only a line, or only an action, fails. "
        "The action is one visible move: which hand, which object already in the scene, what changes on screen. "
        "通报了所有人, 下令, 安排好了 are not actions. "
        "The new line is something this person would say to this listener in one breath. "
        "因此, 然而, 我必须让你知道 are not dialogue. "
        "A framework dialogue seed stays word for word. "
        "Do not add a character, a prop, or a place in order to make the highlight.\n"
        "收口: the last beat is the moment the big crisis and the big turn have both landed on screen. "
        "Do not play the result, who wins, the reveal, or the button after that beat.\n"
        "娱乐时间 (Fun and Games / FunGames) is the highlight body when that beat falls inside the locked 取材范围: "
        "at least three highlight fragments come from it in that case. "
        "建置 contributes the 01–05 beats that fall inside the range, in that order, not a single Set-up shot. "
        "反派逼近 contributes at least one fragment when it falls inside the range. "
        "When any of beats 01–05, Fun and Games, or Bad Guys Close In falls outside the locked range, do not reach outside the range to collect it.\n"
        "核心看点 (Audience Hook, TOP anchors, iconic lines, 四美, spectacle) "
        "must be seen or heard inside those fragments, not only named in a selling-point list.\n"
        "Shape: open on 建置; cut the 娱乐时间 highlights in story order; "
        "stop when the big crisis and the big turn are both on screen, and leave the result unplayed. "
        "Do not reveal the final boss or the ultimate secret.\n"
        "核心建置、人物弧光与基础世界观进已有短拍: when 【结构化预填】 is in the user message, "
        "embody 核心建置 and 人物弧光 inside the existing beats, together with the foundational worldview. "
        "核心建置 is 概念 (I1), 思想 (I2), 对抗 (I3), the three-act value direction (I3b), and the story world (I4). "
        "人物弧光 (I5) must be readable: the old self, the pressure that forces a change, and which way the arc turns. "
        "基础世界观 is 世界背景 plus 剧情背景, and includes I4. "
        "概念 (I1) and 思想 (I2) each land as one highlight line and one highlight action in the same beat. "
        "对抗 (I3) runs through 娱乐时间 and crests at 反派逼近. "
        "I3b plays only the value direction of the acts inside the locked range, and does not show who wins. "
        "I4 and 世界背景 land in 建置 as the rule without which this choice cannot be understood. "
        "A dialogue seed on a sampled beat, aimed at the controlling idea, the gap and crisis, the value arc, the pressure field, or the character premise and arc, is spoken in those words, with the speaker's micro-action and expression, and the listener's when the line is spoken to someone. A 自白 writes the speaker only. "
        "Do not announce the theme. Do not add a lecture beat. Write at the 8000 字 scale, and do not exceed 8000 字. Do not play prefill beats 11–15.\n"
        "思考稿先写规划落点: inside `[EPISODE_SCRIPT_THINKING_START]`, before the type summary, "
        "write `## 预告片框架规划落点`. Read the script framework and list what was planned, why this trailer uses it, "
        "and which Beat it lands on. 核心建置 covers I1 高概念, I2 主控思想, I3 对抗, I3 主控危机, I3b, I4 故事世界, "
        "世界背景, and 剧情背景. 人物弧光 covers the old self, the forced change, and which way the arc turns. "
        "救猫咪十五拍 is one row each: Opening, ThemeStated, 铺垫, Inciting, Debate, BreakTwo, BStory, FunGames, "
        "Midpoint, BadGuysCloseIn, AllIsLost, DarkNight, BreakThree, Finale, FinalImage. "
        "A selected row uses `规划=框架原句｜逻辑=…｜落点=Beat n`. A beat outside the range, or an ending beat, uses `落点=未选`. "
        "主控危机 lands on the last beat, where the big crisis is already visible and the result stays unplayed. "
        "Beats inside the range that are Opening through Debate, FunGames, or BadGuysCloseIn must name a Beat. "
        "Do not write the body until every selected row has a Beat. This section stays in THINKING and does not enter OUTPUT.\n"
        "Length: 8000 字. Short beats stay within 16–32. Each beat has one highlight line and one highlight action. Do not compress different people or spaces back into one beat to stay under 16, and do not split past 32.\n"
        "A running, chasing, flying, or driving subject still states where it starts, where it ends, how far, and how long. Speed is that distance over that time. The span belongs to the host space (street, road, sea, sky, building gap, or airway), not the cabin.\n"
        "The first non-empty OUTPUT line MUST be: # 预告-{short title}\n"
        "短题不超过 8 字，从这段预告的剧情起名。不把侧重点、取材范围、本集生成指导或其他指导原句写进短题。\n"
        "Keep the formal script blocks. 卖点 are the highlights this trailer actually plays. "
        "重要情节 must state the locked 取材范围, the 侧重点, that the trailer plays 建置, 娱乐时间, and 反派逼近, "
        "which beats embody 核心建置 (I1–I4) and 人物弧光 (I5), "
        "the 世界背景 it plays (the rule, institution, or ability boundary), "
        "the 剧情背景 it plays "
        "(public situation, relationship history, why this conflict cannot wait), the ending beats it leaves unplayed, "
        "and which beats play `#信念对撞` plus the locked `#底层`. "
        "It must leave the final boss and the ultimate secret unrevealed.\n\n"
    )


def resolve_episode_generation_guidance_for_prompt(
    *,
    single_episode_mode: bool,
    request_guidance: Optional[str] = None,
    persisted_guidance: Optional[str] = None,
) -> str:
    """Inject this-episode guidance only for single-episode generation."""
    if not single_episode_mode:
        return ""
    text = str(request_guidance or "").strip() or str(persisted_guidance or "").strip()
    return build_episode_generation_guidance_prompt_block(text)
