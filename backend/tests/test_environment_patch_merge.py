# -*- coding: utf-8 -*-
from app.services.scene_subskill_pipeline_runner import (
    DRAMA_PROMPT,
    _strip_subskill_completion_marker,
)
from app.services.script_analysis_flow_runner import (
    _merge_environment_patches,
    _strip_required_completion_marker,
)


def test_environment_patches_merge_into_matching_scenes_without_rewriting_source():
    split_text = """[SCENES_BLOCK_START]
[COMPREHENSIVE_INFO_START]
project canon
[COMPREHENSIVE_INFO_END]
[SCENE_START:EP01_SC01]
【场景名称】短名=one
[SCENE_CONTENT_START:EP01_SC01]
original one
[SCENE_CONTENT_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[SCENE_START:EP01_SC02]
【场景名称】短名=two
[SCENE_CONTENT_START:EP01_SC02]
original two
[SCENE_CONTENT_END:EP01_SC02]
[SCENE_END:EP01_SC02]
[SCENES_BLOCK_END]
{"project_visual_backfill":{"tone":"cold"}}"""
    patch_text = """[ENV_SCENE_PATCH_START:EP01_SC01]
[ENV_BLOCK_START]
【主环境】room one
[ENV_BLOCK_END]
【Beat→衍生ENV剧情覆盖矩阵】
B1=R:{one}｜ENV:0度room one｜W:{one}｜R−W=∅
【ENV覆盖综合】Beat=全量｜缺项=0
[ENV_SCENE_PATCH_END:EP01_SC01]
[ENV_SCENE_PATCH_START:EP01_SC02]
[ENV_BLOCK_START]
【主环境】room two
[ENV_BLOCK_END]
【Beat→衍生ENV剧情覆盖矩阵】
B1=R:{two}｜ENV:0度room two｜W:{two}｜R−W=∅
【ENV覆盖综合】Beat=全量｜缺项=0
[ENV_SCENE_PATCH_END:EP01_SC02]"""

    merged = _merge_environment_patches(split_text, patch_text)

    assert merged.count("[ENV_BLOCK_START]") == 2
    assert merged.index("【主环境】room one") < merged.index("[SCENE_CONTENT_START:EP01_SC01]")
    assert merged.index("【主环境】room two") < merged.index("[SCENE_CONTENT_START:EP01_SC02]")
    assert "original one" in merged
    assert "original two" in merged
    assert "[COMPREHENSIVE_INFO_START]" in merged
    assert '{"project_visual_backfill":{"tone":"cold"}}' in merged
    assert "ENV_SCENE_PATCH_START" not in merged


def test_completion_markers_must_be_unique_and_terminal():
    environment_marker = "[ENVIRONMENT_PLAN_OUTPUT_END]"
    assert _strip_required_completion_marker(
        f"[ENV_SCENE_PATCH_START:EP01_SC01]\npatch\n{environment_marker}",
        environment_marker,
    ).endswith("patch")
    assert not _strip_required_completion_marker(
        f"{environment_marker}\nextra",
        environment_marker,
    )

    drama_marker = "[DRAMA_STANDARDIZATION_OUTPUT_END]"
    assert _strip_subskill_completion_marker(
        f"[SCENES_BLOCK_START]\nscene\n[SCENES_BLOCK_END]\n{drama_marker}",
        DRAMA_PROMPT,
    ).endswith("[SCENES_BLOCK_END]")
    assert not _strip_subskill_completion_marker(
        f"{drama_marker}\n{drama_marker}",
        DRAMA_PROMPT,
    )
