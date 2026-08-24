# -*- coding: utf-8 -*-
from app.services.scene_subskill_pipeline_runner import (
    filter_subskill_tasks_by_target_ids,
    merge_scene_blocks_into_script,
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


def test_resolve_subskill_start_group_aliases():
    assert resolve_subskill_start_group({}) == "drama"
    assert resolve_subskill_start_group({"start_from_step": "combat_opt"}) == "combat"
    assert resolve_subskill_start_group({"target_subskill": "derived_framing"}) == "framing"
    assert resolve_subskill_start_group({"subskill_group": "staging_env"}) == "staging"


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
