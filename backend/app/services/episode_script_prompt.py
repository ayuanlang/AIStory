# -*- coding: utf-8 -*-
"""Prompt-block helpers for episode-script generation."""
from __future__ import annotations

from typing import Any, Optional

from app.services.story_generator_llm import (
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
        "If a request conflicts with those hard constraints, keep the hard constraint and fulfill the rest of the guidance.\n\n"
        f"{text}\n\n"
    )


def build_structured_prefill_prompt_block(source: Any, *, trailer: bool) -> str:
    """Inject the structured prefill as a required source for episode and trailer writing.

    A blank prefill yields an empty string. Trailer length stays 6–10 beats. 核心建置,
    人物弧光, and the foundational worldview ride inside 建置, 娱乐时间, and 反派逼近.
    """
    if not structured_prefill_has_text(source):
        return ""
    body = format_story_creative_input_block(source).strip()
    if trailer:
        rules = (
            "【结构化预填 — 预告片重要依据】\n"
            "注入链是项目信息 → 结构化预填 → 剧本框架 → 剧本生成。预告必须严格落实这份预填；框架已经写了不同内容时以框架为准，框架没写的预填内容仍然要演。预告必须把核心建置、人物弧光和基础世界观演进已有短拍，让没看过正片的观众读得出来。\n"
            "核心建置＝概念=I1 高概念、思想=I2 主控思想、对抗=I3、I3b 三幕价值弧、I4 故事世界。人物弧光＝I5。基础世界观＝世界背景＋剧情背景，并含 I4。\n"
            "节奏与篇幅不变：仍是 2200 字内、6–10 个短拍。不另开说明拍，不口播，不把预告拉长。\n"
            "概念=I1：一个动作或一句对白点出谁要什么、谁在挡、失败失去什么。"
            "思想=I2：一个动作或一句对白点出价值加原因，不宣布成主题。"
            "对抗=I3：落在娱乐时间，并在反派逼近顶一下，两句相反的原则当场相撞。"
            "I3b 只演取材范围内各幕的价值方向，不演谁胜谁负。"
            "I4 与世界背景落在建置：时代、制度、礼法、能力边界里，缺了就看不懂这一拍选择的那一句，用动作或对白演出来。\n"
            "人物弧光要能读出极性：旧的自己、被这套世界逼着要改的那一下、弧光往哪边走。用动作或对白演。终场的胜负和秘密答案不说破。\n"
            "预填里的 11–15 拍和谁胜谁负不入选材。空字段不另造一套故事。"
            "AI优势应用与劣势回避若点了本段要演的拍，短拍里写出那一层特效画面；回避项保持改写，不把风险动作写回。\n\n"
        )
    else:
        rules = (
            "【结构化预填 — 分集重要依据】\n"
            "注入链是项目信息 → 结构化预填 → 剧本框架 → 剧本生成。必须严格落实这份预填；框架已经写了不同内容时以框架为准，框架没写的预填内容仍然要演。概念=I1，思想=I2，对抗=I3，人物弧光=I5，救猫咪事件种子都是本集必须回指的依据。\n"
            "本集只演落在已锁救猫咪拍里的那一层。不把全剧弧光和结局提前演完。专名、对白种子、设定句要进本集相关场面。\n"
            "本集事件和拍以大纲为准。概念、思想、对抗、弧光的方向以预填为准。空字段不另造一套故事。"
            "AI优势应用与劣势回避点名了本集这一拍的特效时，正文写出那一层形状、规模或季节介质；回避项保持改写。\n\n"
        )
    return f"{rules}{body}\n\n"


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
            "选材、高光比重和收口都围着这一侧重，但只在建置、娱乐时间、反派逼近里加重。侧重点不改取材范围，不改去结局，也不许因此揭秘最终 Boss 或终极秘密。\n"
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
        "Keep a question open: play through 反派逼近, and leave the ending unplayed. "
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
        "反派逼近 is the last beat: the opponent closes in, the situation tightens, and the choice is still unfinished. "
        "When any of beats 01–05, Fun and Games, or Bad Guys Close In falls inside the locked 取材范围, the trailer must include that beat. "
        "When it falls outside the range, do not reach outside the range, and do not replace it with an ending beat.\n"
        "不涉及结局: do not play AllIsLost, DarkNight, BreakThree, Finale, or FinalImage. "
        "Do not play ChoicePrice or ThemeProof. Do not show who wins. "
        "一无所有、灵魂黑夜、进入终章、终场、终场画面都不入选材。\n"
        "主环境由选材决定: first lock the 建置, 娱乐时间, and 反派逼近 pieces this trailer plays. "
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
        "娱乐时间 (Fun and Games / FunGames) is the highlight body when that beat falls inside the locked 取材范围: "
        "at least three highlight fragments come from it in that case. "
        "建置 contributes the 01–05 beats that fall inside the range, in that order, not a single Set-up shot. "
        "反派逼近 contributes at least one fragment when it falls inside the range. "
        "When any of beats 01–05, Fun and Games, or Bad Guys Close In falls outside the locked range, do not reach outside the range to collect it.\n"
        "核心看点 (Audience Hook, TOP anchors, iconic lines, 四美, spectacle) "
        "must be seen or heard inside those fragments, not only named in a selling-point list.\n"
        "Shape: open on 建置; cut the 娱乐时间 highlights in story order; "
        "end on 反派逼近, and leave the ending unplayed. "
        "Do not reveal the final boss or the ultimate secret.\n"
        "核心建置、人物弧光与基础世界观进已有短拍: when 【结构化预填】 is in the user message, "
        "embody 核心建置 and 人物弧光 inside the existing beats, together with the foundational worldview. "
        "核心建置 is 概念 (I1), 思想 (I2), 对抗 (I3), the three-act value direction (I3b), and the story world (I4). "
        "人物弧光 (I5) must be readable: the old self, the pressure that forces a change, and which way the arc turns. "
        "基础世界观 is 世界背景 plus 剧情背景, and includes I4. "
        "概念 (I1) and 思想 (I2) each land as one action or one spoken line. "
        "对抗 (I3) runs through 娱乐时间 and crests at 反派逼近. "
        "I3b plays only the value direction of the acts inside the locked range, and does not show who wins. "
        "I4 and 世界背景 land in 建置 as the rule without which this choice cannot be understood. "
        "Do not announce the theme. Do not add a lecture beat. Do not lengthen the trailer. Do not play prefill beats 11–15.\n"
        "Length: within 2200 字, 6–10 short beats, so each highlight has room for an action or a spoken line plus the plot turn.\n"
        "The first non-empty OUTPUT line MUST be: # 预告-{short title}\n"
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
