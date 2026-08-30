# -*- coding: utf-8 -*-
from app.services.emergency_recovery_block import (
    audit_emergency_recovery_block,
    build_previous_episode_handoff_prompt_block,
    extract_previous_episode_tail_context,
)


NEW_BLOCK = """[EMERGENCY_RECOVERY_BLOCK_START]
适用=有下集
#剧情一句话与交接：本集核心=工牌错位；最后一幕=电梯间；角色终态=林一握牌；关键道具位=解雇信在手机；Carry-out=审计倒计时未决
#结尾钩子：保安按响门铃；对齐下集Carry-in=是
#当前场景=EP01_SC01｜场景名=工牌错位｜终态=林一在电梯内握牌
#当前主环境=星澜电梯间 (Xinglan Elevator)｜复用=复用§8｜空间现态=轿厢门将开
#下集开局=开新场景｜依据=钩子切到门外走廊
#项1：紧急待核销=工牌未交；未决态=审计倒计时；下集须兑现=开场前段；依据=结尾钩子；状态=待下集核销
#集级：待核销项数=1｜自检=通过
[EMERGENCY_RECOVERY_BLOCK_END]"""


LEGACY_SCRIPT = """# 1-工牌错位
[SCENES_BLOCK_START]
scene
[SCENES_BLOCK_END]
## 剧情一句话与交接
林一仍握着工牌。
## 结尾钩子
保安上门。
[EMERGENCY_RECOVERY_BLOCK_START]
适用=有下集
#项1：紧急待核销=工牌未交；未决态=审计倒计时；下集须兑现=开场前段；依据=结尾钩子；状态=待下集核销
#集级：待核销项数=1｜自检=通过
[EMERGENCY_RECOVERY_BLOCK_END]
"""


def test_audit_accepts_handoff_container_shape():
    audit = audit_emergency_recovery_block(NEW_BLOCK, episode_number=1)
    assert audit["ok"] is True
    assert audit["applicable"] == "有下集"
    assert audit["item_count"] == 1


def test_audit_requires_logline_hook_scene_env():
    slim = """[EMERGENCY_RECOVERY_BLOCK_START]
适用=有下集
#项1：紧急待核销=工牌未交；未决态=审计倒计时；下集须兑现=开场前段；依据=结尾钩子；状态=待下集核销
#集级：待核销项数=1｜自检=通过
[EMERGENCY_RECOVERY_BLOCK_END]"""
    audit = audit_emergency_recovery_block(slim, episode_number=2)
    assert audit["ok"] is False
    assert "missing_logline_handoff" in audit["issues"]
    assert "missing_ending_hook" in audit["issues"]
    assert "missing_current_scene" in audit["issues"]
    assert "missing_current_env" in audit["issues"]
    assert "missing_next_opening" in audit["issues"]


def test_audit_accepts_combined_scene_env_line():
    combined = """[EMERGENCY_RECOVERY_BLOCK_START]
适用=有下集
#剧情一句话与交接：本集核心=错位；最后一幕=电梯；角色终态=握牌；关键道具位=信在手机；Carry-out=未决
#结尾钩子：门铃；对齐下集Carry-in=是
#当前场景=EP01_SC01｜场景名=工牌错位｜主环境=星澜电梯间 (Xinglan Elevator)｜终态=林一在电梯
#下集开局=开新场景｜依据=切到门外
#项1：紧急待核销=工牌未交；未决态=审计倒计时；下集须兑现=开场前段；依据=结尾钩子；状态=待下集核销
#集级：待核销项数=1｜自检=通过
[EMERGENCY_RECOVERY_BLOCK_END]"""
    audit = audit_emergency_recovery_block(combined, episode_number=1)
    assert audit["ok"] is True
    assert "missing_current_env" not in audit["issues"]


def test_audit_requires_reuse_env_when_continuing_same_scene():
    continued = """[EMERGENCY_RECOVERY_BLOCK_START]
适用=有下集
#剧情一句话与交接：本集核心=错位；最后一幕=电梯；角色终态=握牌；关键道具位=信在手机；Carry-out=未决
#结尾钩子：门铃；对齐下集Carry-in=是
#当前场景=EP01_SC01｜场景名=工牌错位｜终态=林一在电梯
#当前主环境=星澜电梯间 (Xinglan Elevator)｜复用=复用§8｜空间现态=门将开
#下集开局=复场续完｜依据=同场断点必须续完
#项1：紧急待核销=工牌未交；未决态=审计倒计时；下集须兑现=开场前段；依据=结尾钩子；状态=待下集核销
#集级：待核销项数=1｜自检=通过
[EMERGENCY_RECOVERY_BLOCK_END]"""
    audit = audit_emergency_recovery_block(continued, episode_number=1)
    assert audit["ok"] is False
    assert "missing_reuse_env_on_continue" in audit["issues"]

    locked = continued.replace(
        "#下集开局=复场续完｜依据=同场断点必须续完",
        "#下集开局=复场续完｜复用主环境=星澜电梯间 (Xinglan Elevator)｜依据=同场断点必须续完",
    )
    assert audit_emergency_recovery_block(locked, episode_number=1)["ok"] is True


def test_handoff_prompt_includes_scene_env_and_strips_block_from_tail():
    script = (
        "# 1-工牌错位\n[SCENES_BLOCK_START]\nscene\n[SCENES_BLOCK_END]\n"
        + NEW_BLOCK
    )
    handoff = build_previous_episode_handoff_prompt_block(
        script,
        previous_episode_number=1,
        current_episode_number=2,
    )
    assert handoff["has_emergency_recovery_block"] is True
    assert "#当前场景=EP01_SC01" in handoff["prompt_block"]
    assert "#当前主环境=星澜电梯间" in handoff["prompt_block"]
    assert "#剧情一句话与交接" in handoff["prompt_block"]
    assert "#下集开局=开新场景" in handoff["prompt_block"]
    assert "复场续完" in handoff["prompt_block"]
    tail = extract_previous_episode_tail_context(script)
    assert "[EMERGENCY_RECOVERY_BLOCK_START]" not in tail
    assert "#当前场景=" not in tail


def test_legacy_standalone_headings_remain_in_tail():
    tail = extract_previous_episode_tail_context(LEGACY_SCRIPT)
    assert "剧情一句话与交接" in tail
    assert "保安上门" in tail
    assert "#项1" not in tail
