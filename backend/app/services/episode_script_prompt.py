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
        "This call writes ONE trailer. It is not series episode 1 and not a compressed episode.\n"
        "Story-circle completeness, previous-episode handoff, and next-episode setup do not apply.\n"
        "A viewer who has not seen the series must still grasp the story's 来龙去脉: "
        "who wants what, what starts the trouble, how the conflict escalates, and where the pressure is heading. "
        "Join the pieces with cause and result (因为 / 于是). A pile of unrelated cool shots fails.\n"
        "Use the global framework's Save the Cat spine as the map of that throughline. "
        "Play the beats that carry the cause. Do not give all 15 beats equal scenes.\n"
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
        "重要情节 must state the throughline the trailer makes clear, and the final choice it leaves unplayed.\n\n"
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
