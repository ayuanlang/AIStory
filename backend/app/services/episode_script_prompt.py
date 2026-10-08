# -*- coding: utf-8 -*-
"""Prompt-block helpers for episode-script generation."""
from __future__ import annotations

from typing import Optional


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
        "If a request conflicts with those hard constraints, keep the hard constraint and fulfill the rest of the guidance.\n\n"
        f"{text}\n\n"
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


def format_trailer_episode_title(
    *,
    seq: int,
    episode_title: str = "",
    episode_from: int,
    episode_to: int,
    series_episode_count: int,
    focus: Optional[str] = None,
) -> str:
    """Title that keeps each trailer row distinct in the episode list."""
    parts = [f"预告片{int(seq)}"]
    if int(episode_from) != 1 or int(episode_to) != int(series_episode_count):
        parts.append(f"第{int(episode_from)}-{int(episode_to)}集")
    focus_label = " ".join(str(focus or "").split())
    if focus_label:
        if len(focus_label) > 16:
            focus_label = focus_label[:16].rstrip() + "…"
        parts.append(focus_label)
    title = str(episode_title or "").strip()
    if title:
        parts.append(title)
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
            "范围外的最终揭秘仍然不演。\n"
            "The pieces come from different stages inside this episode range "
            "(cause, escalation, the pressure this stretch is driving toward). "
            "When the range covers more than one episode, locking the trailer to one episode's story circle fails. "
            "When the range is a single episode, play that episode's throughline and leave its ending choice unplayed.\n"
        )
        span_sentence = (
            "Because the selection spans different stages inside the locked episode range, those plot-matched locations "
            "become multiple main environments that carry the trailer. "
            "If the range really happens in only one registered space, use that one space. "
        )
    else:
        range_block = (
            "取材范围=全剧，从头到尾。\n"
            "贯穿全剧: sample the global framework's Save the Cat spine across the series, in story order. "
            "The pieces come from different stages of the whole story (cause, escalation, the pressure it is driving toward). "
            "Locking the trailer to one episode's story circle fails.\n"
        )
        span_sentence = (
            "Because the selection spans different stages of the whole series, those plot-matched locations "
            "become multiple main environments that carry the trailer. "
        )
    if focus_text:
        focus_block = (
            f"侧重点={focus_text}\n"
            "选材、高光比重和收口都围着这一侧重。侧重点不改取材范围，也不许因此揭秘最终 Boss 或终极秘密。\n"
        )
    else:
        focus_block = "侧重点=未指定。按这一段的来龙去脉均衡取样，不单押某一种高光。\n"
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
        "Keep a question open: play up to the crisis, and leave the final choice unplayed. "
        "The throughline must be followable, and the ending must stay unspoiled. "
        "A pile of unrelated cool shots fails. A trailer too cryptic to follow also fails.\n"
        "剧情背景: the trailer must also play the story background. "
        "Take the §8 Lore sentences whose 首投集 is the opening and whose content is the public situation already in force, "
        "the relationship history the audience needs, and why this conflict cannot wait. "
        "When the framework has no per-episode blocks, take those same three from the basic story thread's public situation. "
        "Play them in an early beat with a visible action or a spoken line, "
        "so a viewer who has not seen the series knows what bind these people are already in. "
        "Do not paste the Lore sentence as narration. "
        "Do not use that beat to state later plot, the ending, the final boss, or an unrevealed secret. "
        "When 取材范围 does not start at episode 1, that background is the public situation already in force "
        "at the first episode of the range.\n"
        "Use the global framework's Save the Cat spine as the map of that throughline. "
        "Play the beats that carry the cause. Do not give all 15 beats equal scenes.\n"
        "主环境由选材决定: first lock which Save the Cat pieces this trailer plays. "
        "Then each piece's scene environment is the §8 main environment where that actual plot happens "
        "in the global framework (§9 Episode Scene Environments / Scene-Event Continuity of the episode that owns the turn), "
        "copied character-for-character. "
        "The events in the beat are the events the framework already places in that environment. "
        "Choosing a location first, then fitting plot into it, fails. "
        f"{span_sentence}"
        "Two selected turns that really happen in the same registered space share it. "
        "Adding a place only to raise the environment count, a new location, a near-synonym rename, "
        "or moving a turn into a prettier space fails. "
        "Different §8 environments are different scenes. Each scene header `主环境=` is the environment its beats use.\n"
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
        "娱乐时间 (Fun and Games / 游戏时间 / 节拍08) supplies the richest stretch when that beat falls inside the locked 取材范围: "
        "at least three highlight fragments come from it in that case. "
        "When it falls outside the locked range, do not reach outside the range to collect it.\n"
        "核心看点 (Audience Hook, TOP anchors, iconic lines, 四美, spectacle) "
        "must be seen or heard inside those fragments, not only named in a selling-point list.\n"
        "Shape: open on the cause the audience must know; cut the highlight chain in story order; "
        "end on the crisis the story is driving toward, and leave the final choice unplayed. "
        "Do not reveal the final boss or the ultimate secret.\n"
        "Length: within 2200 字, 6–10 short beats, so each highlight has room for an action or a spoken line plus the plot turn.\n"
        "The first non-empty OUTPUT line MUST be: # 预告-{short title}\n"
        "Keep the formal script blocks. 卖点 are the highlights this trailer actually plays. "
        "重要情节 must state the locked 取材范围, the 侧重点, the throughline the trailer makes clear, the 剧情背景 it plays "
        "(public situation, relationship history, why this conflict cannot wait), the final choice it leaves unplayed, "
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
