# -*- coding: utf-8 -*-
from app.services.scene_subskill_pipeline_runner import (
    filter_subskill_tasks_by_target_ids,
    is_timeout_like_error,
    merge_scene_blocks_into_script,
    payload_has_explicit_subskill_start,
    persisted_subskill_step_usable,
    resolve_scene_subskill_resume,
    resolve_subskill_start_group,
)


BASE_SCRIPT = """[SCENES_BLOCK_START]
[COMPREHENSIVE_INFO_START]
全局上下文
[COMPREHENSIVE_INFO_END]
[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]
[VFX] 命中=否｜类型=无｜证据=无
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC01]
[SCENE_START:EP01_SC01]
【场景名称】旧茶馆｜日·内
SC01旧正文
[SCENE_END:EP01_SC01]
[SPECIAL_SCENE_ANALYSIS_START:EP01_SC02]
[VFX] 命中=是｜类型=爆炸｜证据=炸
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC02]
[SCENE_START:EP01_SC02]
【场景名称】街口｜夜·外
SC02旧正文
[SCENE_END:EP01_SC02]
[SCENES_BLOCK_END]

### 第三部分：Project Visual Backfill
{"keep": true}
"""

NEW_SC02 = """[SPECIAL_SCENE_ANALYSIS_START:EP01_SC02]
[VFX] 命中=是｜类型=爆炸｜证据=炸
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC02]
[SCENE_START:EP01_SC02]
【场景名称】街口｜夜·外
SC02新正文
[SCENE_END:EP01_SC02]"""


DRAMA_OK = (
    "[SCENE_START:EP01_SC01]\n"
    "文戏增强已完成的正文，足够长以便续跑时识别为可用落库。\n"
    "[DRAMA_STANDARDIZATION_OUTPUT_END]\n"
    "[SCENE_END:EP01_SC01]"
)
DRAMA_STRIPPED = (
    "[SCENE_START:EP01_SC01]\n"
    "文戏增强已完成并已去掉结束标签的正文，续跑仍应识别。\n"
    "[SCENE_END:EP01_SC01]"
)
FRAMING_STRIPPED = (
    "[SCENE_START:EP01_SC01]\n"
    "【Beat主体定位】B1=甲=可见性=V｜组=无\n"
    "【取景锁定】当前环境=主环境 景别=MS 构图=中景 镜头角度=平视 选择证据=原文\n"
    "[DERIVED_ENV:0度沙漠]\n"
    "[SCENE_END:EP01_SC01]"
)
STAGING_OK = (
    "[SCENE_START:EP01_SC01]\n"
    "建置与入戏已完成的正文，足够长以便跳过整场。\n"
    "[STAGING_ENV_OUTPUT_END]\n"
    "[SCENE_END:EP01_SC01]"
)
STAGING_STRIPPED = (
    "[SCENE_START:EP01_SC01]\n"
    "【建置】【入戏】入戏状态=站立 出场状态=离开 ENV氛围微=风沙\n"
    "[SCENE_END:EP01_SC01]"
)


def test_resolve_subskill_start_group_aliases():
    assert resolve_subskill_start_group({}) == "drama"
    assert resolve_subskill_start_group({"start_from_step": "combat_opt"}) == "combat"
    assert resolve_subskill_start_group({"target_subskill": "derived_framing"}) == "framing"
    assert resolve_subskill_start_group({"subskill_group": "staging_env"}) == "staging"
    assert payload_has_explicit_subskill_start({}) is False
    assert payload_has_explicit_subskill_start({"start_from_step": "drama"}) is True


def test_resume_skips_completed_drama_and_starts_at_framing():
    plan = resolve_scene_subskill_resume(
        scene_id="EP01_SC01",
        steps={"drama": DRAMA_OK},
        call_vfx=False,
        call_xian=False,
    )
    assert plan.start_group == "framing"
    assert plan.skipped_reason == "resume_framing"
    assert "drama" in plan.called
    assert persisted_subskill_step_usable("drama", DRAMA_OK)


def test_resume_starts_combat_when_drama_done_and_vfx_needed():
    plan = resolve_scene_subskill_resume(
        scene_id="EP01_SC02",
        steps={"drama": DRAMA_OK},
        call_vfx=True,
    )
    assert plan.start_group == "combat"
    assert plan.skipped_reason == "resume_combat"


def test_resume_skips_scene_when_pipeline_already_success():
    plan = resolve_scene_subskill_resume(
        scene_id="EP01_SC01",
        steps={"staging": STAGING_OK},
        pipeline_status="success",
        pipeline_scene_block=STAGING_OK,
    )
    assert plan.start_group == "done"
    assert plan.skipped_reason in {"pipeline_success", "staging_persisted"}


def test_resume_starts_from_drama_when_nothing_persisted():
    plan = resolve_scene_subskill_resume(scene_id="EP01_SC03", steps={})
    assert plan.start_group == "drama"
    assert plan.skipped_reason == "start_drama"


def test_resume_uses_stripped_persisted_blocks_without_end_markers():
    assert persisted_subskill_step_usable("drama", DRAMA_STRIPPED)
    assert persisted_subskill_step_usable("framing", FRAMING_STRIPPED)
    assert persisted_subskill_step_usable("staging", STAGING_STRIPPED)
    plan = resolve_scene_subskill_resume(
        scene_id="EP01_SC01",
        steps={"drama": DRAMA_STRIPPED},
        call_vfx=False,
    )
    assert plan.start_group == "framing"
    assert plan.skipped_reason == "resume_framing"


def test_timeout_like_error_detects_hard_cancel_and_read_timeout():
    assert is_timeout_like_error(TimeoutError("LLM call timed out after 900s"))
    assert is_timeout_like_error(Exception("vendor failed: Read timeout: wall-clock"))
    assert not is_timeout_like_error(Exception("SCENE_SUBSKILL_OUTPUT_INVALID"))


def test_filter_subskill_tasks_matches_canonical_and_tail():
    tasks = [
        {"scene_id": "EP01_SC01", "scene_order": 1},
        {"scene_id": "EP01_SC02", "scene_order": 2},
    ]
    assert [row["scene_id"] for row in filter_subskill_tasks_by_target_ids(tasks, ["EP01_SC02"])] == ["EP01_SC02"]
    assert [row["scene_id"] for row in filter_subskill_tasks_by_target_ids(tasks, ["SC01"])] == ["EP01_SC01"]
    assert filter_subskill_tasks_by_target_ids(tasks, ["EP01_SC09"]) == []


def test_merge_scene_blocks_keeps_other_scenes_and_tail():
    merged = merge_scene_blocks_into_script(
        BASE_SCRIPT,
        [{"scene_id": "EP01_SC02", "scene_block": NEW_SC02}],
    )
    assert "SC01旧正文" in merged
    assert "SC02新正文" in merged
    assert "SC02旧正文" not in merged
    assert "[COMPREHENSIVE_INFO_START]" in merged
    assert "Project Visual Backfill" in merged
    assert merged.count("[SCENE_START:EP01_SC01]") == 1
    assert merged.count("[SCENE_START:EP01_SC02]") == 1
