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
            "注入链是项目信息 → 剧本框架 → 分集大纲 → 剧本生成。预告落实这份剧本框架。写法与剧本生成相同，内容是高潮选段。段落可以简洁跳跃。每一节要有基本短情节，让人看懂这一节：谁在场、要什么、这一下发生了什么、结果停在哪。禁止画面式描述。概念、思想、对抗、人物弧光、节拍事件、对白种子、世界背景、剧情背景和麦格芬以剧本框架为准。麦格芬有名字就逐字沿用，时限和过期用同一行，不另造一件，不另起一个截止。分集大纲只提供某一节高潮在哪一集、时间和在场名。大纲把同一件事写成另一套时，改回剧本框架。\n"
            "核心建置＝概念=I1 高概念、思想=I2 主控思想、对抗=I3、I3b 三幕价值弧、I4 故事世界。人物弧光＝I5。基础世界观＝世界背景＋剧情背景，并含 I4。这些若这一节高潮里已经在演，用对白和动作读出来，不另开说明节，不贴成旁白。\n"
            "节奏与篇幅：按 8000 字写，不超过 8000 字。段落可以简洁，也可以从这一节跳到另一节。每一节的拍数只够看懂这一节的短情节，不按画面条数凑。同一节内部要接得上。换节不把上节的问硬接成下节的答。动作写到哪一只手、哪一件物、哪一处可见变化，不写通报、下令、安排。新写的对白是口语短句，不写因此、然而、我必须让你知道。跑、追、飞、掠、行驶的主体仍写从哪到哪、跨距和用时，速度由这两数读出；这段路落在宿主，不落在驾驶舱。\n"
            "概念=I1、思想=I2、对抗=I3 和人物弧光都落在选中的高潮节里，用短情节演，不收成一张画面。"
            "对话种子针对主控思想、对抗鸿沟危机、价值弧、压力场、人物前提弧光的，原句开口，并写出说者的微动作和表情；这一节里有听者、而且下一句是看懂所必需的，再写听者。自白只写说者。\n"
            "揭秘、胜负、收束和最终 Boss 的真面目可以入选。空字段不另造一套故事。范围内建置、娱乐时间和反派逼近仍要有落点。也可以选全集高光。高光部分优先选择 AI 优势，仍写成短情节。选中的节要演信念对撞和已锁底层，不口播。成片留哪些，由剪辑裁。"
            "取材节所在集若有专业行，这一节的动作和对白按那个领域的规程来。领域必须是实际学科，或已有的技术技巧。举例是物理、化学、法律、哲学、机械、武器、数学、医学（含中医），以及野外生存、工具制作、企业管理这类已有的技术技巧。同类已有学科和技术技巧同样可以，不限于这几门。工具制作符合本剧时代或剧情背景。设想和科幻仍守所挂那一门的基础框架。领域=无或没有这行时，不硬塞术语。"
            "借鉴同正片。先把角色的情感冲突和这一节剧情对上，再按背景、实际剧情、角色特征逐句改写，不抄原句。框架已锁的对白种子仍用原句。\n"
            "预告的优势和回避写在 THINKING，不另开一节进剧本页。短情节里用动作演出来，不另开画面。\n\n"
        )

    else:
        if emotion_driven:
            rules = (
                "【剧本框架 — 分集重要依据】\n"
                "注入链是项目信息 → 剧本框架 → 分集大纲 → 剧本生成。这一份是剧本框架，全局只写一次。情绪驱动类的骨架是埃格里《编剧的艺术》的上升冲突，不是救猫咪。\n"
                "前提、统一的对立面、社会与人性、八阶事件、故事环总表、经典借鉴的整体逻辑、世界背景、剧情背景、人物、时间节点、专业领域、麦格芬和对白种子，以剧本框架为准。麦格芬有名字就逐字沿用，时限和过期用同一行，不另造一件，不另起一个截止。本集只演分集大纲冲突阶里已锁的那一阶或连续几阶，并演该集已锁的故事环步。环步落在这一阶里，不另写一件事。不把证明和结局提前演完。禁止改写成救猫咪拍。大纲基本点是上一环的标记，不限制本场参考。可以再加借鉴点。每一场主要参考与这一场场景一致的作品，从经典影视、游戏、文学作品、流行短剧取动作逻辑和对白逻辑。大纲那一部和本场场景一致才用，对不上就换。先把角色的情感冲突和剧情发展对上，再按背景、实际剧情、角色特征逐句改写。符合本集背景和主题后按本集剧情融合，不能硬拼。\n"
                "针对=前提、统一的对立面、社会层、人性层、过渡、危机、证明的对话种子，原句入戏，并写出说者与听者的微动作和表情。自白只写说者。\n"
                "本集落在哪一阶、时间、环境和在场名用分集大纲。场景以简单为先。四壁每壁只有封闭面再加一具贴附，中部只有一个主体。有人坐下时座算在这一具上，不算第二主体。配套和配饰不写进剧本。大纲各集空间行只点地方名。主体在大纲开头【空间主体】。正文这些地方都用上。这一处出现之后先用已有主体。跟 Base Positioning，再跟 Script Mode。地方、到达、越过距离、读写、显形、出手用大纲已经锁的这一模式。没有这一下，不加。做不到或再加就超负载，就换大纲里的另一处，不在旧环境加主体。非封闭远景不计负载。动笔前按本集剧情分析专业。点了领域时，这一下的动作按规程做完，对白按这个身份说出权限、顺序或后果。领域必须是实际学科，或已有的技术技巧。举例是物理、化学、法律、哲学、机械、武器、数学、医学（含中医），以及野外生存、工具制作、企业管理这类已有的技术技巧。同类已有学科和技术技巧同样可以，不限于这几门。工具制作符合本剧时代或剧情背景。设想和科幻仍守所挂那一门的基础框架。领域=无的集不硬塞术语。大纲把同一阶写成另一件事时，改回剧本框架。空字段不另造一套故事。"
                "AI优势应用与劣势回避和大纲本集 AI 行点名了本集的特效时，正文写出那一层形状、规模或季节介质；回避项保持改写。"
                "优势和回避写在 THINKING，不另开一节进剧本页。拍里用动作演出来，不能只抄上游。\n\n"
            )
        else:
            rules = (
            "【剧本框架 — 分集重要依据】\n"
            "注入链是项目信息 → 剧本框架 → 分集大纲 → 剧本生成。这一份是剧本框架，全局只写一次。概念=I1，思想=I2，对抗=I3，人物弧光=I5，节拍事件、对白种子、世界背景、剧情背景、时间节点、专业领域和麦格芬以剧本框架为准，都是本集必须回指的依据。麦格芬有名字就逐字沿用，时限和过期用同一行，不另造一件，不另起一个截止。\n"
            "本集只演落在分集大纲已锁救猫咪拍里的那一层。不把全剧弧光和结局提前演完。专名、对白种子、设定句要进本集相关场面。落到本集拍上、针对主控思想、对抗鸿沟危机、价值弧、压力场、人物前提弧光的对话种子，原句入戏，并写出说者与听者的微动作和表情。自白只写说者。大纲基本点是上一环的标记，不限制本场参考。可以再加借鉴点。每一场主要参考与这一场场景一致的作品，从经典影视、游戏、文学作品、流行短剧取动作逻辑和对白逻辑。大纲那一部和本场场景一致才用，对不上就换。先把角色的情感冲突和剧情发展对上，再按背景、实际剧情、角色特征逐句改写。符合本集背景和主题后按本集剧情融合，不能硬拼。\n"
            "本集落在哪一拍、时间、环境和在场名用分集大纲。场景以简单为先。四壁每壁只有封闭面再加一具贴附，中部只有一个主体。有人坐下时座算在这一具上，不算第二主体。配套和配饰不写进剧本。大纲各集空间行只点地方名。主体在大纲开头【空间主体】。正文这些地方都用上。这一处出现之后先用已有主体。跟 Base Positioning，再跟 Script Mode。地方、到达、越过距离、读写、显形、出手用大纲已经锁的这一模式。没有这一下，不加。做不到或再加就超负载，就换大纲里的另一处，不在旧环境加主体。非封闭远景不计负载。动笔前按本集剧情分析专业。点了领域时，这一下的动作按规程做完，对白按这个身份说出权限、顺序或后果。领域必须是实际学科，或已有的技术技巧。举例是物理、化学、法律、哲学、机械、武器、数学、医学（含中医），以及野外生存、工具制作、企业管理这类已有的技术技巧。同类已有学科和技术技巧同样可以，不限于这几门。工具制作符合本剧时代或剧情背景。设想和科幻仍守所挂那一门的基础框架。领域=无的集不硬塞术语。这一拍的事件、概念、思想、对抗、弧光以剧本框架为准。大纲把同一拍写成另一件事时，改回剧本框架。空字段不另造一套故事。"
            "AI优势应用与劣势回避和大纲本集 AI 行点名了本集的特效时，正文写出那一层形状、规模或季节介质；回避项保持改写。"
            "优势和回避写在 THINKING，不另开一节进剧本页。拍里用动作演出来，不能只抄上游。\n\n"
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
        "这里只使用第 9 节：本集盖住哪一段、入和出、观众行的看因、偿=但是、再看、差=留|补|无、本集时间、在场名、摘要里的因为所以但是、说者和听者的微动作、本集驱动行，以及本集基本点。剧情的因为、所以、但是和本集进或收的推动点一起落在拍上。推动点只演本集这一下，不把整部主旨或总目标演成这一集的任务。只演观众行里本集写了的诉求。进或收的项用对白或自白说出来，用表情或动作放大。说的人按这一拍的人和事来选，可以是当事人，也可以是旁边的人。不按项对号入座，也不把示例原句套进来。悬念可以是还不知道的人用自白点出还缺的那一截，点出悬在哪一件上。错位要让观众感到上帝视角的优越：已经看见的那一件留在画面里，不知者说错、走错还自认为对，知道的人躲开或接话，不把差解释给观众。有炸弹时先给观众看见，不知者再走过去；爆=留不让他碰上，爆=本集才在但是碰上。没写错位不另造一截来凑优越感。博弈让两头的代价都说出来，人停在必须选的那一下，选完点出舍了哪一头、留了哪一头。没写博弈不另造两头。共情让观众站到这个人一边：他自己说出难在哪、扛在哪，或旁边的人说出替他不平、替他疼的那一句。关系由第三者或其中一人点出这一寸现在在哪；距离变了，用一步、一递、一躲或一句把近或裂做出来；没变只留痕迹。没有已锁羁绊不演关系。兑现收成之后，可以由被压住的一方用挫折、表情和对白承住。计划、计策或布局做成了，可以由做成的人、看见的人，或被算进去的人，用对白点出这一步巧在哪、成在哪，把爽感放大。只点这一下，不把过程再讲一遍。兑现还留着不提前演喜悦，也不提前拆怎么巧。场上没有这个人，不另造一个反派、分析者或第三者来套。留的只留痕迹。正文不写观众困惑、观众心疼。留的还握着，不另起一条，也不弄丢。开场只演观众行里写了的项。进=进或收的让它往前。进=留的是还握着、这一集没推的，内容留在账上，等后面的集再推，不演成消失，也不演成新推进。没写的不演。同时的几项在同一段里都看得见。兑现后再入先看见成果，紧接着下一种重新在场。结果带出时，但是后面的那一句进入下一种。正文不写观众想看。偿就是这一句，可以收成一种并带出下一种。集末按再驱动把再看留成未完。配上的前提或主旨、冲突、弧光或本集但是用剧情演出来，不另写一套。差=留时不知者到本集结束仍不知道，留差的那一拍他和已经看见的那一件同在画面里，错话或错动作对着这一件，让观众感到比他多看见的优越。差=补时但是里让他知道。差=无不另造一截差。下一集开场接还留着并且下一集仍然需要的项，以及进过的项，留的内容相同，进的用新状态，不把留改成无来占位，用不上的不写，并可再配合新的推动。大纲本集 AI 行点名的优势和回避，在拍里用动作演出来，不另起一场奇观。动笔前再按本集场面核一次，不照抄来充数。专业不在大纲各集里。专业按框架专业领域和本集剧情、埋点、钩子选定一门实际学科或已有的技术技巧，动作和对白按这一门做完、说完。领域必须是实际学科，或已有的技术技巧。举例是物理、化学、法律、哲学、机械、武器、数学、医学（含中医），以及野外生存、工具制作、企业管理这类已有的技术技巧。同类已有学科和技术技巧同样可以，不限于这几门。工具制作符合本剧时代或剧情背景。设想和科幻仍守所挂那一门的基础框架。这一集用不到就写领域=无，不硬塞术语。空间主体用大纲开头【空间主体】，各集只点地方名。驱动行的最大项是角色弧光和冲突，正文里要演出来，落只写落=但是。每一场先写承=全剧|基本点|另选。对得上就用已锁的那一部，不再另搜。另选要写明已锁的两部为什么对不上这场。\n"
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


# The writer skill alone is about 250k characters. Sent first, it fills a 128k
# context window before the story is read, and the model asks for an outline it
# already had. Trailer calls keep the injected story, then as many rules as fit.
TRAILER_CALL_BUDGET_CHARS = 96000


def trailer_call_system_prompt() -> str:
    """Short system turn. The story lives in the user turn, ahead of the rules."""
    return (
        "你正在按剧本生成的同一套写法写一条预告，不是在检查提示词是否到齐。\n内容是高潮选段。段落可以简洁跳跃。每一节要有能看懂的短情节。禁止写成画面说明。\n"
        "用户消息开头的【已注入的故事与分集输入】就是全局故事大纲、分集规划和本集集号。\n"
        "本集集号=预告片。不要上一集正文，不要 EMERGENCY_RECOVERY_BLOCK。没有它们不是缺口。\n"
        "禁止回复「尚未提供」。禁止要求用户再贴大纲、分集规划、集号或本集生成指导。禁止把停笔说明当成成稿。\n"
        "读完已注入的大纲后直接写这条预告。\n"
        "正式剧本草稿放进 [EPISODE_SCRIPT_OUTPUT_START] 与 [EPISODE_SCRIPT_OUTPUT_END]。\n"
        "OUTPUT 第一个非空行是 # 预告-{不超过8字的剧情短题}。\n"
    )


def build_trailer_story_packet(
    *,
    project_title: str,
    season_line: str = "",
    episode_from: int,
    episode_to: int,
    focus: str = "",
    extra_notes: str = "",
    prefill_source: Any = None,
    framework_md: str = "",
    character_canon_md: str = "",
    relationships: str = "",
) -> str:
    """The three inputs the writer asked for, labeled and placed before any rules."""
    focus_text = str(focus or "").strip()
    notes = str(extra_notes or "").strip()
    lines = [
        "【已注入的故事与分集输入】",
        "以下就是全局故事大纲、分集规划和本集集号。已经附上。不要再向用户索取。",
        "本集集号=预告片。这不是正片续写。写法与剧本生成相同。内容是高潮选段，段落可以简洁跳跃，每一节要有能看懂的短情节，不是画面式描述。",
        f"取材范围=第{int(episode_from)}集到第{int(episode_to)}集。",
        f"侧重点={focus_text or '未指定'}",
        f"补充要求={notes or '无。按已注入的大纲写。'}",
        f"项目名={str(project_title or '').strip() or '未命名'}",
    ]
    season = str(season_line or "").strip()
    if season:
        lines.append(season)
    parts = ["\n".join(lines)]
    if structured_prefill_has_text(prefill_source):
        prefill = "\n\n".join(
            chunk
            for chunk in (
                format_story_creative_input_block(prefill_source).strip(),
                format_outline_registry_block(prefill_source).strip(),
            )
            if chunk
        ).strip()
        if prefill:
            parts.append("【结构化预填】\n" + prefill)
    framework = str(framework_md or "").strip()
    if framework:
        parts.append("【全局故事大纲】【分集规划】\n" + framework)
    canon = str(character_canon_md or "").strip()
    if canon:
        parts.append("【角色】\n" + canon)
    relation = str(relationships or "").strip()
    if relation:
        parts.append("【人物关系】\n" + relation)
    return "\n\n".join(parts).strip() + "\n"


def _split_writer_skill_for_trailer(skill: str) -> tuple[str, str, str]:
    """Opening contract, the long middle, then the output format."""
    text = str(skill or "").strip()
    if not text:
        return "", "", ""
    lines = text.splitlines()
    raw_head = "\n".join(lines[:40])
    head = raw_head.strip()
    offset = len(raw_head)
    if offset < len(text) and text[offset:offset + 1] == "\n":
        offset += 1
    marker = "## 输出格式"
    idx = text.find(marker)
    if idx < 0 or idx < offset:
        return head, text[offset:].strip(), ""
    tail = text[idx:].strip().replace(
        "# {episode_number}-{episode_title}",
        "# 预告-{不超过8字的剧情短题}",
    )
    return head, text[offset:idx].strip(), tail


def _fit_segments(segments: list[str], room: int) -> str:
    """Keep earlier segments whole. The last one that still fits may be shortened."""
    kept: list[str] = []
    used = 0
    for segment in segments:
        text = str(segment or "").strip()
        if not text:
            continue
        gap = 2 if kept else 0
        if used + gap + len(text) <= room:
            kept.append(text)
            used += gap + len(text)
            continue
        remain = room - used - gap - 40
        if remain > 200:
            kept.append(text[:remain].rstrip() + "\n【后部省略。已注入的大纲足够动笔。】")
        elif not kept:
            kept.append(text[: max(0, room - 40)].rstrip() + "\n【后部省略。已注入的大纲足够动笔。】")
        break
    return "\n\n".join(kept).strip()


def assemble_trailer_call_prompts(
    *,
    story_packet: str,
    trailer_rules: str,
    writer_skill: str,
    reference_block: str = "",
    budget_chars: int = TRAILER_CALL_BUDGET_CHARS,
) -> tuple[str, str]:
    """System stays short. User starts with the story. Later rules are dropped first."""
    system = trailer_call_system_prompt()
    story = str(story_packet or "").strip()
    if not story:
        story = (
            "【已注入的故事与分集输入】\n"
            "本集集号=预告片。大纲正文为空。仍直接写这条预告，不要向用户索取。\n"
        )
    head, middle, output_format = _split_writer_skill_for_trailer(writer_skill)
    if head or output_format or middle:
        head = (
            "【执笔规则摘录】故事和分集输入已经在本条开头。不要停下来索取输入。\n\n"
            + head
        ).strip()
    closing = "现在写这条预告。大纲、分集规划和集号已经在本条开头，不要再向用户索取。\n"
    room = max(4000, int(budget_chars) - len(system) - len(closing) - 2)
    body = _fit_segments(
        [
            story,
            str(trailer_rules or ""),
            head,
            output_format,
            str(reference_block or ""),
            middle,
        ],
        room,
    )
    return system, f"{body}\n\n{closing}"


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
            "只从这一段已经写下的情节里选高潮选段。范围外的铺垫不拿来充数。\n"
            "主线之外也可以选全集高光，从全剧任何一集已有的高光里切进来，用那一集已登记的角色、道具和地点。全集高光不替代这一段的主体。\n"
            "范围内按故事顺序先落建置（01–05：Opening、ThemeStated、铺垫、Inciting、Debate）、娱乐时间、反派逼近。这三段在范围内仍要有落点。建置含这五拍，不收成只有铺垫。落在范围外的这三拍不越界去补。其余节拍都可以进入。成片留哪些，由剪辑裁。\n"
        )
    else:
        range_block = (
            "取材范围=全剧，从头到尾。\n"
            "从各集已经写下的情节里选高潮选段。\n"
            "按故事顺序先落建置（01–05：Opening、ThemeStated、铺垫、Inciting、Debate）、娱乐时间、反派逼近。建置含这五拍，不收成只有铺垫。其余节拍都可以进入。成片留哪些，由剪辑裁。\n"
        )
    if focus_text:
        focus_block = (
            f"侧重点={focus_text}\n"
            "选哪些高潮围着这一侧重。侧重点不写进标题。\n"
        )
    else:
        focus_block = "侧重点=未指定。比重按建置、娱乐时间、反派逼近来分，娱乐时间最重。其余高潮都可以进入。成片留哪些，由剪辑裁。\n"
    return (
        "【预告片生成 / Trailer — HIGHEST PRIORITY】\n"
        "【全局故事大纲】【分集规划】【本集】已经在本条提示词里，不要再向用户索取。\n"
        "全局故事大纲 = 下方 Global Story DNA、剧本框架和结构化预填。分集规划 = 其中的第 9 节和本条取材范围。\n"
        "本集集号=预告片。这不是正片续写。不要上一集正文。EMERGENCY_RECOVERY_BLOCK 不适用。没有它们不是缺口。\n"
        "禁止回复「尚未提供」。禁止要求用户再贴大纲、分集规划、集号或交接块。禁止把停笔说明当成成稿。读完已注入的大纲后直接写。\n"
        "每次新写一条，不改已有预告。\n"
        "写法与剧本生成相同。用场、节拍、对白和动作写戏。禁止画面式描述：不写镜头清单，不写只看见什么的旁白，不把一节收成一张奇观，不口播主题。\n"
        "内容是高潮选段。揭秘、胜负、收束和最终 Boss 的真面目可以入选。节拍不设禁入，含中点、一无所有、灵魂黑夜、进入终章、终场、终场画面。成片留哪些，由剪辑裁。每一节仍写成能看懂的短情节，不因此改成画面清单。\n"
        "高光部分优先选择 AI 优势：宏大规模、垂直空域、具象能量与特效、环境奇观、单人五官特写、氛围慢相位、群体质块、不可能尺度。预填或大纲 AI 行已经点给可出镜的场面先选。同一段有好几处能用时，先取命中这些优势的那一处。写进短情节，不收成画面说明。不因此排除节拍，不新造主体，不把回避项写回去。\n"
        "信念对撞与底层进选中的节。读框架的信念对撞：主角信念对对手信念。读底层，闭集是社会、哲学、道德，并读主攻层。这一节用对白或动作让主角不肯放下这一要，对手不肯放下相反的那一要。主攻层让这个选择付出代价。社会是制度、阶层或舆论。哲学是何为真实、自由或注定。道德是何为对、亏欠谁、目的能否开脱伤害。只演框架已经锁的主攻层。框架已经叠上的层可以进同一节。不把这三层各写成一句口号。抽掉对撞这一节仍能当任务完成，不合格。抽掉这一层代价变轻，不合格。不让角色宣布信念或主题。\n"
        f"{range_block}"
        f"{focus_block}"
        "段落可以简洁，也可以从这一节跳到另一节。不把各节铺成连续的一整集，也不为了接上节而补过场。\n"
        "每一节必须有一段基本短情节，让没看过正片的人看懂这一节：谁在场、要什么、这一下发生了什么、结果停在哪。只有画面、没有这件事，不合格。\n"
        "同一节内部这几拍要接得上：问要有着落，动作要有结果。换节是跳跃，不把上节的问硬接成下节的答。不为了把这一节铺长而硬插听者拍。\n"
        "不新造角色、道具、地点。地点用这一节实际发生的已登记地方，逐字沿用。\n"
        "核心建置、人物弧光、世界背景和剧情背景若这一节里已经在演，用这一节的对白和动作读出来，不另开说明节。\n"
        "对话种子落在选中的高潮上、针对主控思想、对抗鸿沟危机、价值弧、压力场或人物弧光的，用原句开口。自白只写说者。\n"
        "跑、追、飞、掠、行驶仍写从哪到哪、跨距和用时。这段路落在宿主，不落在驾驶舱。\n"
        "8000 字内。拍数按每一节看懂所需的短情节来，不按画面条数凑。\n"
        "思考稿在类型执行摘要之前写 ## 预告片框架规划落点。每一节一行：节=k｜来源集=EPxx｜拍型=Opening|ThemeStated|铺垫|Inciting|Debate|FunGames|BadGuysCloseIn|Midpoint|AllIsLost|DarkNight|BreakThree|Finale|FinalImage|其他｜短情节=谁要什么、这一下发生了什么｜落点=Beat n。范围内的建置五拍、娱乐时间、反派逼近必须落点=Beat n。全集高光另写高光=全集。信念对撞和底层写项=信念对撞|底层｜落在节=k。没写落点=Beat n 的节，禁止写进正文。这一节不进 OUTPUT。\n"
        "The first non-empty OUTPUT line MUST be: # 预告-{short title}\n"
        "短题不超过 8 字，从这些高潮的剧情起名。不把侧重点、取材范围、本集生成指导或其他指导原句写进短题。\n"
        "正式剧本仍是场和节拍。卖点只写这一节实际演到的那一下。重要情节写明取材范围、侧重点、哪些节演了核心建置、人物弧光、世界背景、剧情背景、信念对撞和底层。\n\n"
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
