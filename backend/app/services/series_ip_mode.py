# -*- coding: utf-8 -*-
"""系列剧（IP模式）：全剧只锁圣经，分集按本集指定写，并回灌此前各集摘要。"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.emergency_recovery_block import extract_emergency_recovery_block

SERIES_EPISODE_SUMMARY_START = "[SERIES_EPISODE_SUMMARY_START]"
SERIES_EPISODE_SUMMARY_END = "[SERIES_EPISODE_SUMMARY_END]"

_SUMMARY_START_RE = re.compile(r"\[\s*SERIES_EPISODE_SUMMARY_START\s*\]", re.IGNORECASE)
_SUMMARY_END_RE = re.compile(r"\[\s*SERIES_EPISODE_SUMMARY_END\s*\]", re.IGNORECASE)
_LOGLINE_RE = re.compile(r"^#剧情一句话(?:与交接)?\s*[：:]\s*(.+)$", re.MULTILINE)
_HOOK_RE = re.compile(r"^#结尾钩子\s*[：:]\s*(.+)$", re.MULTILINE)

_PER_SUMMARY_CAP = 900
_OLDER_SUMMARY_CAP = 180
_TOTAL_SUMMARY_CAP = 12000


def is_series_ip_script_mode(script_mode: Any) -> bool:
    raw = str(script_mode or "").strip().lower()
    if not raw:
        return False
    return ("ip模式" in raw) or ("series ip" in raw) or ("ip mode" in raw)


def build_series_ip_global_prompt_block() -> str:
    return (
        "【系列剧 IP 模式 / Series IP — HIGHEST PRIORITY】\n"
        "Script Mode 是系列剧（IP模式）。本段覆盖系统提示词里的「分集完整」和 §9 逐集情节模板。\n"
        "- 不预写 EP01–EPN 分集剧情框架。禁止输出 [EPISODE_BLOCK_START]、Scene-Event Continuity、每集故事环、每集场表。\n"
        "- 只写全剧信息：世界观、主要角色 IP、基本故事线索、全剧冲突发动机、经典对标（整体剧本的机制参考）。\n"
        "- 时间节点仍登记在 §8：至少开篇；有重生、穿越、回归等断点则分名登记，如重生前、重生后，并写该节点的季节、昼夜、气候。不因此预写各集情节。\n"
        "- §9 契约写明：之后每一集必须交时间范围（绝对，或相对已登记节点），用来确认季节、昼夜、气候。此前各集摘要里的本集时间，后续集与全局统筹继承。\n"
        "- 预填里的救猫咪 15 拍若存在，只当作全剧走向，写进 §5，不得拆成各集情节。\n"
        "- Episodes Count 只记录计划体量，不因此展开 N 集。\n"
        "- 后续每一集另给「基本剧情 / 要体现的冲突 / 重要亮点」，并读取此前各集摘要。本阶段不要替那些集编情节。\n"
        "- §9 改成「分集生成契约」一段，说明上述分工。Episode Coverage Audit 不得要求 Rendered=N。\n"
        "- 人物信念、隐藏反派守密、取名、末日视觉、原文专名仍然有效，但不得借此补写分集情节。\n\n"
    )


def compose_series_ip_episode_brief(
    *,
    plot: Any = None,
    conflict: Any = None,
    highlights: Any = None,
    reference: Any = None,
    guidance: Any = None,
) -> str:
    parts: List[str] = []
    plot_text = str(plot or "").strip()
    conflict_text = str(conflict or "").strip()
    highlights_text = str(highlights or "").strip()
    reference_text = str(reference or "").strip()
    if plot_text:
        parts.append(f"基本剧情：{plot_text}")
    if conflict_text:
        parts.append(f"要体现的冲突：{conflict_text}")
    if highlights_text:
        parts.append(f"重要亮点：{highlights_text}")
    if reference_text:
        parts.append(f"对标参考（学机制，不搬剧情；可对标整体剧本）：{reference_text}")
    structured = "\n".join(parts).strip()
    loose = str(guidance or "").strip()
    if structured and loose:
        if loose == structured or structured in loose:
            return loose
        if loose in structured:
            return structured
        return f"{structured}\n\n补充：\n{loose}"
    return structured or loose


def series_ip_brief_is_usable(brief: Any) -> bool:
    text = str(brief or "").strip()
    if len(text) < 8:
        return False
    if ("基本剧情" in text) and ("冲突" in text):
        return True
    return len(text) >= 20


def build_series_ip_episode_prompt_block(*, brief: str, prior_summaries_block: str) -> str:
    brief_text = str(brief or "").strip() or "（缺失：不得自行把全剧走向拆成一套完整分集大纲来填）"
    prior = str(prior_summaries_block or "").strip()
    return (
        "【系列剧 IP 模式 / Series IP — HIGHEST PRIORITY】\n"
        "本集没有预先写好的分集剧情框架。Global Story DNA 若没有本集的 EP 情节块，禁止到 §9 里找场表，"
        "也禁止把全剧节拍拆成其他集或替未写的集编情节。\n"
        "本集要演的内容只来自下面的「本集指定」。全剧只继承世界观、主要角色 IP、基本故事线索、人物信念与身份，不得改人设、不得改世界规则。\n"
        "对标经典只学机制与可拍逻辑，服务本集指定和全剧线索；禁止把参考作品的剧情搬进来当本集大纲。\n"
        "此前各集摘要是已发生事实。必须承接，不得改写，不得让已退场的人无声明回来。摘要里没有的集，视为还没发生。\n"
        "故事环由本集指定现推：用本集冲突走一步或相邻两步，并让人物做出一次被迫的选择。不要为了走完八步把后面几集的事提前演完。\n"
        "卖点以本集「重要亮点」为准；未写的轴可以无，但写了的亮点必须在对白或动作里被看见。\n"
        "正片写完后，在正式剧本标记之外另起一块摘要，供下一集读取。摘要不进正片正文，不写机位：\n"
        f"{SERIES_EPISODE_SUMMARY_START}\n"
        "本集发生：…\n"
        "冲突落地：…\n"
        "人物状态：…\n"
        "未决钩子：…\n"
        "后续约束：…\n"
        "本集时间：式=绝对|相对｜节点=…｜范围=起点→终点｜季节=…｜昼夜=日|夜|日转入夜|夜转入日｜气候=…\n"
        f"{SERIES_EPISODE_SUMMARY_END}\n\n"
        "本集指定：\n"
        f"{brief_text}\n\n"
        f"{prior}\n\n"
    )


def build_series_ip_trailer_note(
    *,
    episode_from: Optional[int] = None,
    episode_to: Optional[int] = None,
) -> str:
    if episode_from and episode_to:
        range_line = (
            f"取材范围是第{int(episode_from)}集到第{int(episode_to)}集："
            "只从这一段已经写好的分集摘要取样。范围外的摘要只作已发生的公开背景。\n"
        )
    else:
        range_line = "未写取材范围时，用全部已写摘要，相当于从头到尾。\n"
    return (
        "【系列剧 IP 模式 · 预告】全剧框架没有逐集剧情。"
        "预告只从世界观、主要角色 IP、基本故事线索，以及已经写好的分集摘要里取样。\n"
        f"{range_line}"
        "须带上剧情背景：公开处境、关系前史、这场冲突此刻为何非做不可，用短拍里的动作或对白演出来。"
        "不要假装存在 EP01–EPN 分集规划，也不要为了预告补写未生成的集。\n\n"
    )


def extract_series_episode_summary(text: str) -> str:
    raw = str(text or "")
    start = _SUMMARY_START_RE.search(raw)
    if not start:
        return ""
    end = _SUMMARY_END_RE.search(raw, start.end())
    body = raw[start.end() : end.start()] if end else raw[start.end() :]
    return body.strip()


def strip_series_episode_summary(text: str) -> str:
    raw = str(text or "")
    if not raw or not _SUMMARY_START_RE.search(raw):
        return raw
    cleaned = re.sub(
        r"\[\s*SERIES_EPISODE_SUMMARY_START\s*\][\s\S]*?\[\s*SERIES_EPISODE_SUMMARY_END\s*\]",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\[\s*SERIES_EPISODE_SUMMARY_START\s*\][\s\S]*\Z",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def fallback_series_episode_summary(script: str) -> str:
    """When the writer omits the summary block, keep the handoff logline for the next episode."""
    block = extract_emergency_recovery_block(script) or ""
    source = block or str(script or "")
    parts: List[str] = []
    logline = _LOGLINE_RE.search(source)
    if logline:
        parts.append(logline.group(1).strip())
    hook = _HOOK_RE.search(source)
    if hook:
        parts.append(f"结尾钩子：{hook.group(1).strip()}")
    return "\n".join(part for part in parts if part).strip()


def _clip(text: str, limit: int) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip() + "…"


def build_prior_episode_summaries_prompt_block(
    rows: List[Dict[str, Any]],
    *,
    current_episode_number: int,
) -> str:
    """rows: {number, title, summary} for episodes already written before this one."""
    current = int(current_episode_number)
    header = (
        "此前各集摘要（硬约束，已发生事实）：\n"
        f"- 正在写第 {current} 集。下面只列已经写成的集。\n"
        "- 必须承接这些事实，不得改写，不得让已退场的人无声明回来。\n"
        "- 没有出现在这里的集视为尚未写成，禁止替它们编造已发生情节。\n"
    )
    usable = []
    for row in rows or []:
        number = int(row.get("number") or 0)
        summary = str(row.get("summary") or "").strip()
        if number <= 0 or number >= current or not summary:
            continue
        usable.append(
            {
                "number": number,
                "title": str(row.get("title") or "").strip(),
                "summary": summary,
            }
        )
    usable.sort(key=lambda item: item["number"])
    if not usable:
        return (
            header
            + "- 此前没有已生成分集。本集按全剧信息与本集指定开写。\n"
        )

    clipped = [
        {
            **item,
            "summary": _clip(item["summary"], _PER_SUMMARY_CAP),
        }
        for item in usable
    ]
    total = sum(len(item["summary"]) for item in clipped)
    if total > _TOTAL_SUMMARY_CAP:
        keep_full_from = max(clipped[-1]["number"] - 7, clipped[0]["number"])
        for item in clipped:
            if item["number"] < keep_full_from:
                first_line = item["summary"].splitlines()[0]
                item["summary"] = _clip(first_line, _OLDER_SUMMARY_CAP)

    lines = [header]
    for item in clipped:
        title = f" · {item['title']}" if item["title"] else ""
        lines.append(f"### 第{item['number']}集{title}")
        lines.append(item["summary"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"
