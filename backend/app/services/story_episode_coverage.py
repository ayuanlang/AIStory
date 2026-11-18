# -*- coding: utf-8 -*-
"""Force global story frameworks to contain one block per requested episode."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.episode_script_reference_service import extract_story_dna_delimited_block
from app.services.llm_service import llm_service

logger = logging.getLogger("api_logger")

_START_RE = re.compile(r"\[\s*EPISODE_BLOCK_START\s*:\s*EP(\d+)\s*\]", re.IGNORECASE)
_AUDIT_RE = re.compile(r"(?im)^#{1,3}\s*Episode\s+Coverage\s+Audit\b")
_OUTPUT_END_RE = re.compile(r"\[\s*STORY_DNA_OUTPUT_END\s*\]", re.IGNORECASE)

_FILL_SYSTEM = (
    "你在补全已经写好的分集大纲里缺掉的集。已闭合的集不要重写。只输出本次点名的集。\n"
    "每一集一对独占行 [EPISODE_BLOCK_START:EPxx] 与 [EPISODE_BLOCK_END:EPxx]，集号用两位。\n"
    "每集只有十二行：标题、摘要（一个因为、一个所以、一个但是）、交接（入，以及出=未完谁、未完事、未完停）、观众（看因、偿=但是、再看、差=留|补|无、不知者、情绪、时限态、消耗、过期可见）、时间（绝对或相对节点的范围，含季节、昼夜、气候）、救猫咪拍（拍名、收完、但是落在）、空间（本集涉及的每一处，至少一处，可以多处）、在场名、AI（落到本集拍上的优势和回避，没有则优势=无｜回避=无）、专业（领域、动作、对白；没碰到写领域=无｜动作=无｜对白=无）、驱动（弧光和冲突是最大项；被逼的那一下写进因为或所以；落只写落=但是）、基本点（只写一处经典、一个落点，写这句如何让本集更难收场；类=文学|影视|游戏；不写流行，不写第二处；不抄原句）。\n"
    "看因从观影心理写。每一集都写悬念、错位、博弈、共情、兑现、关系。只写本集这一下，能指回本集的因为、所以或但是，不写整部主旨、弧光或总目标。观众还握着、这一集没推的写留，内容留下，等后面的集再推。观众这里还没有的才写无。关系没有已锁羁绊才写无；羁绊在而没推，写留。至少一项为进。下集接留着和进过的项，留的内容相同，不把留改成无。末集把还留着的项收掉。全剧逐步释放、逐步推进：EP01 只放开场握得住的，其后每一集推进已握住的或新释放一项，末集收完。本集但是就是这一步。可以有几种配合。因驱动写它们怎么配合：同时再抛出、兑现后再入、结果带出。悬念、博弈、共情、兑现是常见几种，还有别的推动就写那种。每种都配上框架已锁的前提或主旨、冲突、弧光，或本集但是，由本集剧情演出来。没有上一集时，从开场里写这几种怎么一起被看见。有上一集时，接那一集的再看和再驱动，并可再配合新的推动。再看用再驱动，不把但是再写一遍，点名未完谁和未完事。给出了下一集时，再看和再驱动必须能交给那一集。末集再看=无、再驱动=无。偿只写偿=但是，不另写一句。差=留时不知者到本集结束仍不知道，情绪只许爽、喜剧、心疼、紧张。差=补时但是里让他知道。差=无时不知者=无、情绪=无。集数多出来的加压集，但是必须改掉已锁事实：谁站到哪边、东西到了谁手里、或时限更短。只把上一集再看再演一遍，不交。还在追麦格芬而消耗=无，不交。不另起一个截止。\n"
    "不写故事环、卖点、金句、场表、选场逻辑、多线表、戏份。不写 §0–§8。救猫咪拍行只写拍名和收完。AI 行不写成场表或长文。专业行不写成百科。按本集剧情评估所需专业，含埋点和钩子。把可能用到、能让这一下站得住的专业知识带进来。登记里有的用登记名。剧情必须靠一门登记里没有的，写来源=本集。剧情、埋点和钩子都不靠专业知识，才写领域=无。不把这一集用不到的门贴上。\n"
    "不写思考过程，不写用户原文保留区，不写逐字落实映射，不回抄用户原文，不重写剧本框架，不写 Episode Coverage Audit。\n"
    "人物和道具只用已有名字和已有功能，写在名行。空间行必写，至少一处，可以多处，不并成一个名字。环境名逐字对应剧本框架场景与道具里的空间名。没登记的才标补。不用打斗地这类事件名。场景以简单为先：四壁每壁只有封闭面再加一具贴附，中部只有一个主体。有人坐下才把座写进主体，座不算第二主体。配套和配饰不在这一阶段写。一处首现只锁这个上限，之后复用；新功能落在已有主体上。跟 Base Positioning，再跟 Script Mode。短剧、电影、通用连续剧不改世界。地方、到达、越过距离、读写、显形、出手用这一模式这一时代会有的：高科技用全息屏和已有通道；修仙用法宝、粒子和已设定术法；时代剧不用电脑、全息、手机，除非明文穿越或该时代已有；普通时代不套同一套办公室，也不升级成全息或法宝；末日不写成全息，除非模式明文是赛博朋克。没有这一下，不加。不写颜色、材质、纹样。不够或超负载就换地方并标补，不在旧处加主体。非封闭远景不计负载。\n"
    "补上的集，入必须接上给出的上一集未完谁和未完事：同一个人、同一处、同一件还在做的事。上一集未完停，本集摘要先做到可见结果，再写新的所以和但是。看因接上一集再看。上集有角色刚入场，本集先完成谁见他、他来做什么、他落到哪一步；安排写完之前不换地方、不另起无关的事、不把他写成已经就位，也不让他从名行消失。给出了下一集时，出必须交给那一集的入，并把本集没做完的事留在出里。没有给出的邻集，不要用全文最后一集来接。摘要从这态接着写。没有上一集，入写开场看见的那一态。EP01 的 Opening 保住框架开场画面的吸睛档：宏观看得见规模，两难两角已经在场。双线或蒙太奇切场必须在交接写明切=双线或切=蒙太奇，以及切到哪一条、哪些地方。上集仍保持刚入场或未做完的那一下，切回来再完成。\n"
    "项目季节是开篇。本次要补的集如果剧情时间已经走到下一季，季节按春夏秋冬顺着变，并写跨季=是。换季只改时间行的季节。不写景致、衣着、道具外形、环境实体细节。每一处再写占用=首现|未结束|已结束。角色已离场，或再开始已经是另一个时间段，占用=已结束，重新初始化或重新入场。同一时间段里人还在，占用=未结束，入接着上一场。有空间占用参考时，只用来源集小于本集的最近一条，不把坐标写进大纲。\n"
)


def _end_re(episode_number: int) -> re.Pattern[str]:
    return re.compile(rf"\[\s*EPISODE_BLOCK_END\s*:\s*EP0*{int(episode_number)}\s*\]", re.IGNORECASE)


def complete_episode_blocks(text: str) -> Dict[int, str]:
    """Map episode number to a closed START…END block. Later duplicates do not replace the first."""
    source = str(text or "")
    found: Dict[int, str] = {}
    for match in _START_RE.finditer(source):
        number = int(match.group(1))
        if number in found:
            continue
        end = _end_re(number).search(source, match.end())
        if not end:
            continue
        found[number] = source[match.start() : end.end()].strip()
    return found


def missing_episode_numbers(text: str, planned: int) -> List[int]:
    try:
        total = int(planned)
    except (TypeError, ValueError):
        return []
    if total <= 0:
        return []
    have = set(complete_episode_blocks(text))
    return [number for number in range(1, total + 1) if number not in have]


def drop_incomplete_episode_tail(text: str) -> str:
    """Remove a trailing episode that has START but no END, and keep a later audit or output end."""
    source = str(text or "")
    starts = list(_START_RE.finditer(source))
    if not starts:
        return source
    last = starts[-1]
    number = int(last.group(1))
    if _end_re(number).search(source, last.end()):
        return source
    end_at = len(source)
    for marker in (_AUDIT_RE, _OUTPUT_END_RE):
        found = marker.search(source, last.start())
        if found:
            end_at = min(end_at, found.start())
    return source[: last.start()].rstrip() + "\n\n" + source[end_at:].lstrip()


def splice_episode_blocks(base: str, addition: str) -> str:
    """Insert closed blocks from addition into base, in episode order, without duplicating."""
    cleaned = drop_incomplete_episode_tail(base)
    merged = complete_episode_blocks(cleaned)
    for number, block in complete_episode_blocks(addition).items():
        merged.setdefault(number, block)
    if not merged:
        return cleaned
    stripped = cleaned
    for block in complete_episode_blocks(cleaned).values():
        stripped = stripped.replace(block, "", 1)
    chunk = "\n\n".join(merged[number] for number in sorted(merged))
    audit = _AUDIT_RE.search(stripped)
    if audit:
        return stripped[: audit.start()].rstrip() + "\n\n" + chunk + "\n\n" + stripped[audit.start() :]
    output_end = _OUTPUT_END_RE.search(stripped)
    if output_end:
        return stripped[: output_end.start()].rstrip() + "\n\n" + chunk + "\n\n" + stripped[output_end.start() :]
    return stripped.rstrip() + "\n\n" + chunk + "\n"


def _neighbor_numbers(blocks: Dict[int, str], batch: List[int]) -> Tuple[Optional[int], Optional[int], List[int]]:
    """The episode before the batch, the episode after it, and completed episodes sitting inside the span."""
    wanted = sorted({int(number) for number in batch if int(number) > 0})
    if not wanted:
        return None, None, []
    first, last = wanted[0], wanted[-1]
    have = set(blocks)
    prev = first - 1 if first > 1 and (first - 1) in have else None
    nxt = last + 1 if (last + 1) in have else None
    inside = [number for number in range(first + 1, last) if number in have and number not in set(wanted)]
    return prev, nxt, inside


def framework_context_for_fill(
    markdown: str,
    batch: Optional[List[int]] = None,
    *,
    limit: int = 12000,
) -> str:
    """Context for a fill call. Full text is only the episodes beside the ones being written."""
    output = extract_story_dna_delimited_block(markdown, "OUTPUT") or str(markdown or "")
    section9 = re.search(r"(?im)^##\s*9\)", output)
    if section9:
        head = output[: section9.start()]
    else:
        first_block = _START_RE.search(output)
        head = output[: first_block.start()] if first_block else output
    blocks = complete_episode_blocks(output)
    titles: List[str] = []
    for number in sorted(blocks):
        for line in blocks[number].splitlines():
            stripped = line.strip()
            if stripped and "EPISODE_BLOCK_" not in stripped:
                titles.append(stripped[:180])
                break
    parts: List[str] = []
    if head.strip():
        parts.append(head.strip()[:2000])
    if titles:
        parts.append("已完成集（只留标题）:\n" + "\n".join(titles))
    wanted = [int(number) for number in (batch or []) if int(number) > 0]
    if not wanted:
        return "\n\n".join(parts)[:limit]
    first, last = min(wanted), max(wanted)
    prev, nxt, inside = _neighbor_numbers(blocks, wanted)
    if first <= 1:
        parts.append("上一集：没有。这次从开篇补起。")
    elif prev is not None:
        parts.append(f"上一集 EP{prev:02d}（紧挨本次要补的集，入接这一集的出）:\n{blocks[prev]}")
    else:
        parts.append(f"上一集 EP{first - 1:02d} 还没有写成。不要用更后面已经写完的集冒充上一集。")
    for number in inside:
        parts.append(f"夹在本次要补的集中间、已经写完的 EP{number:02d}:\n{blocks[number]}")
    if nxt is not None:
        parts.append(f"下一集 EP{nxt:02d}（紧挨本次要补的集，出交给这一集的入）:\n{blocks[nxt]}")
    else:
        parts.append(f"下一集 EP{last + 1:02d} 还没有写成。不要用已经写完的最后一集冒充下一集。")
    return "\n\n".join(parts)[:limit]


def _usage_pair(usage: Any) -> Tuple[int, int]:
    if not isinstance(usage, dict):
        return 0, 0
    prompt = usage.get("prompt_tokens")
    if prompt is None:
        prompt = usage.get("input_tokens") or 0
    completion = usage.get("completion_tokens")
    if completion is None:
        completion = usage.get("output_tokens") or 0
    return int(prompt or 0), int(completion or 0)


def merge_usage(base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    prompt, completion = _usage_pair(base)
    extra_prompt, extra_completion = _usage_pair(extra)
    prompt += extra_prompt
    completion += extra_completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "input_tokens": prompt,
        "output_tokens": completion,
        "total_tokens": prompt + completion,
    }


def _fill_user_prompt(
    context: str,
    batch: List[int],
    planned: int,
    registry_block: str = "",
    reference_block: str = "",
) -> str:
    labels = ", ".join(f"EP{number:02d}" for number in batch)
    head = str(registry_block or "").strip()
    prefix = f"{head}\n\n" if head else ""
    reference = str(reference_block or "").strip()
    reference_prefix = f"{reference}\n\n" if reference else ""
    return (
        f"{prefix}"
        f"{reference_prefix}"
        f"计划集数 = {planned}。这次只补：{labels}。\n"
        "每集单独成块，含本集冲突、转折、Continuity 和集末钩子。不要用总述代替。\n"
        "时间、在场名、专业、故事线切场沿用上面的剧本框架五栏，不另起一套。\n\n"
        f"{context}"
    )


async def ensure_story_episode_blocks(
    markdown: str,
    *,
    episodes_count: int,
    llm_config: Optional[Dict[str, Any]],
    user_id: Optional[int] = None,
    batch_size: int = 4,
    max_rounds: int = 8,
    fill_system: Optional[str] = None,
    registry_block: str = "",
    reference_block: str = "",
) -> Tuple[str, Dict[str, Any]]:
    """Append any missing EP01–EPN blocks. Raises if they are still missing after the fill rounds."""
    current = str(markdown or "")
    added_usage: Dict[str, Any] = {}
    try:
        planned = int(episodes_count)
    except (TypeError, ValueError):
        return current, added_usage
    if planned <= 0:
        return current, added_usage

    missing = missing_episode_numbers(current, planned)
    if not missing:
        return current, added_usage

    stalls = 0
    from app.services.task_manager import abort_if_current_task_canceled

    for _round in range(max_rounds):
        abort_if_current_task_canceled()
        if not missing:
            break
        batch = missing[: max(1, int(batch_size))]
        context = framework_context_for_fill(current, batch)
        response = await llm_service.generate_content_with_fallback(
            _fill_user_prompt(context, batch, planned, registry_block, reference_block),
            fill_system or _FILL_SYSTEM,
            llm_config or {},
            image_urls=None,
            video_urls=None,
            user_id=user_id,
            category="LLM",
        )
        added_usage = merge_usage(added_usage, (response or {}).get("usage"))
        addition = str((response or {}).get("content") or "")
        updated = splice_episode_blocks(current, addition)
        still_missing = missing_episode_numbers(updated, planned)
        logger.info(
            "[ensure_story_episode_blocks] planned=%s batch=%s before=%s after=%s",
            planned,
            batch,
            missing,
            still_missing,
        )
        if len(still_missing) >= len(missing):
            stalls += 1
            if stalls >= 2:
                break
        else:
            stalls = 0
            current = updated
            missing = still_missing

    if missing:
        raise RuntimeError(
            "分集大纲未写齐全部分集，缺："
            + ", ".join(f"EP{number:02d}" for number in missing)
        )
    return current, added_usage
