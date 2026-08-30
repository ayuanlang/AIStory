# -*- coding: utf-8 -*-
from app.services.episode_script_prompt import (
    build_episode_generation_guidance_prompt_block,
    resolve_episode_generation_guidance_for_prompt,
)


def test_empty_guidance_yields_empty_block():
    assert build_episode_generation_guidance_prompt_block("") == ""
    assert build_episode_generation_guidance_prompt_block("   \n") == ""
    assert build_episode_generation_guidance_prompt_block(None) == ""


def test_guidance_block_is_high_priority_and_keeps_user_text():
    block = build_episode_generation_guidance_prompt_block("本集强化反派压迫感；开场回收门铃声。")
    assert block.startswith("【本集生成指导 / Episode Generation Guidance — HIGHEST PRIORITY】")
    assert "HIGHEST PRIORITY" in block
    assert "outranks Extra Notes" in block
    assert "本集强化反派压迫感；开场回收门铃声。" in block
    assert block.endswith("\n\n")


def test_resolve_injects_only_in_single_episode_mode():
    request_text = "高潮改在雨中对峙"
    persisted_text = "备用指导"
    assert resolve_episode_generation_guidance_for_prompt(
        single_episode_mode=False,
        request_guidance=request_text,
        persisted_guidance=persisted_text,
    ) == ""
    block = resolve_episode_generation_guidance_for_prompt(
        single_episode_mode=True,
        request_guidance=request_text,
        persisted_guidance=persisted_text,
    )
    assert "高潮改在雨中对峙" in block
    assert "备用指导" not in block


def test_resolve_falls_back_to_persisted_when_request_empty():
    block = resolve_episode_generation_guidance_for_prompt(
        single_episode_mode=True,
        request_guidance="  ",
        persisted_guidance="开场必须回收上集门铃。",
    )
    assert "开场必须回收上集门铃。" in block
