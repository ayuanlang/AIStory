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


def build_trailer_generation_prompt_block() -> str:
    """Highest-priority brief when this call writes a trailer, not a series episode."""
    return (
        "【预告片生成 / Trailer — HIGHEST PRIORITY】\n"
        "This call writes ONE trailer for the WHOLE series. It is not series episode 1, "
        "not a compressed episode, and not a highlight reel of a single episode.\n"
        "Story-circle completeness, previous-episode handoff, and next-episode setup do not apply.\n"
        "贯穿全剧: sample the global framework's Save the Cat spine across the series, in story order. "
        "The pieces come from different stages of the whole story (cause, escalation, the pressure it is driving toward). "
        "Locking the trailer to one episode's story circle fails.\n"
        "交代剧情又留悬疑: a viewer who has not seen the series must still grasp the story's 来龙去脉: "
        "who wants what, what starts the trouble, how the conflict escalates, and where the pressure is heading. "
        "Join the pieces with cause and result (因为 / 于是). "
        "Keep a question open: play up to the crisis, leave the final choice unplayed, "
        "do not stage the finale proof, and do not name a hidden villain. "
        "The throughline must be followable, and the ending must stay unspoiled. "
        "A pile of unrelated cool shots fails. A trailer too cryptic to follow also fails.\n"
        "Use the global framework's Save the Cat spine as the map of that throughline. "
        "Play the beats that carry the cause. Do not give all 15 beats equal scenes.\n"
        "主环境由选材决定: first lock which Save the Cat pieces this trailer plays. "
        "Then each piece's scene environment is the §8 main environment where that actual plot happens "
        "in the global framework (§9 Episode Scene Environments / Scene-Event Continuity of the episode that owns the turn), "
        "copied character-for-character. "
        "The events in the beat are the events the framework already places in that environment. "
        "Choosing a location first, then fitting plot into it, fails. "
        "Because the selection spans different stages of the whole series, those plot-matched locations "
        "become multiple main environments that carry the trailer. "
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
        "The body is 高光剧情. The trailer must play all three kinds, each as a scene fragment:\n"
        "1) 动作: a visible action with a clear result.\n"
        "2) 对白: lines spoken in the scene, including the framework's iconic and conflict lines.\n"
        "3) 情节: a plot turn the audience can follow — what changes, and why the next piece follows.\n"
        "娱乐时间 (Fun and Games / 游戏时间 / 节拍08) supplies the richest stretch: "
        "at least three highlight fragments come from it.\n"
        "核心看点 (Audience Hook, TOP anchors, iconic lines, 四美, spectacle) "
        "must be seen or heard inside those fragments, not only named in a selling-point list.\n"
        "Shape: open on the cause the audience must know; cut the highlight chain in story order; "
        "end on the crisis the story is driving toward, and leave the final choice unplayed. "
        "Do not stage the finale proof, and do not name a hidden villain.\n"
        "Length: within 2200 字, 6–10 short beats, so each highlight has room for an action or a spoken line plus the plot turn.\n"
        "The first non-empty OUTPUT line MUST be: # 预告-{short title}\n"
        "Keep the formal script blocks. 卖点 are the highlights this trailer actually plays. "
        "重要情节 must state the throughline the trailer makes clear, the final choice it leaves unplayed, "
        "and which beats play `#信念对撞` plus the locked `#底层`.\n\n"
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
