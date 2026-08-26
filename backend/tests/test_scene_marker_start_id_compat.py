# -*- coding: utf-8 -*-
from app.services.script_analysis_flow import (
    build_scene_subskill_task_payloads,
    parse_scene_units_from_markers,
)
from app.services.scene_subskill_pipeline_runner import _extract_single_scene_block


def test_start_end_id_mismatch_uses_start_scene_id():
    script = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC05]
scene five body
[SCENE_END:EP01_SC03]
[SCENE_START:EP01_SC06]
scene six body
[SCENE_END:EP01_SC06]
[SCENES_BLOCK_END]
"""
    units = parse_scene_units_from_markers(script)
    assert [u.scene_id for u in units] == ["EP01_SC05", "EP01_SC06"]
    assert units[0].scene_text == "scene five body"
    assert units[1].scene_text == "scene six body"


def test_nested_content_wrappers_and_duplicate_end_still_parse():
    script = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】客栈对峙
[SCENE_CONTENT_START:EP01_SC01]
[SCENE_START:EP01_SC01]
[ENV_BLOCK_START]
客栈内部。
[ENV_BLOCK_END]
[SCENE_END:EP01_SC01]
[SCENE_CONTENT_END:EP01_SC01]
[SCENE_END:EP01_SC01]

[SCENE_START:EP01_SC04]
【场景名称】客栈毁灭
[SCENE_CONTENT_START:EP01_SC04]
[SCENE_START:EP01_SC04]
[ENV_BLOCK_START]
客栈废墟。
[ENV_BLOCK_END]
[SCENE_END:EP01_SC04]
[SCENE_START:EP01_SC05]
[ENV_BLOCK_START]
荒漠古道。
[ENV_BLOCK_END]
[SCENE_END:EP01_SC05]
[SCENE_CONTENT_END:EP01_SC04]
[SCENE_END:EP01_SC04]
[SCENES_BLOCK_END]
"""
    units = parse_scene_units_from_markers(script)
    assert [u.scene_id for u in units] == ["EP01_SC01", "EP01_SC04", "EP01_SC05"]
    assert "客栈内部" in units[0].scene_text
    assert "客栈废墟" in units[1].scene_text
    assert "荒漠古道" in units[2].scene_text


def test_extra_trailing_scene_end_is_ignored():
    script = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
one
[SCENE_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
"""
    units = parse_scene_units_from_markers(script)
    assert [u.scene_id for u in units] == ["EP01_SC01"]
    assert units[0].scene_text == "one"


def test_visual_backfill_inside_block_does_not_fail_parse():
    script = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
one
[SCENE_END:EP01_SC01]
{
  "project_visual_backfill": {
    "note": "example [SCENE_END:EPxx_SC01]"
  }
}
[SCENES_BLOCK_END]
"""
    units = parse_scene_units_from_markers(script)
    assert [u.scene_id for u in units] == ["EP01_SC01"]
    assert units[0].scene_text == "one"


def test_matching_start_end_ids_still_parse():
    script = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
one
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
"""
    units = parse_scene_units_from_markers(script)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC01"


def test_missing_outer_end_is_recovered_when_start_and_scene_pairs_exist():
    script = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
one
[SCENE_END:EP01_SC01]
"""
    units = parse_scene_units_from_markers(script)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC01"
    assert units[0].scene_text == "one"


def test_missing_outer_wrappers_are_recovered_when_scene_pairs_exist():
    script = """
[SCENE_START:EP01_SC02]
two
[SCENE_END:EP01_SC02]
"""
    units = parse_scene_units_from_markers(script)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC02"
    assert units[0].scene_text == "two"


def test_missing_outer_start_is_recovered_when_scene_pairs_and_end_exist():
    script = """
[COMPREHENSIVE_INFO_START]
overall plot
[COMPREHENSIVE_INFO_END]
[SCENE_START:EP01_SC01]
one
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
"""
    units = parse_scene_units_from_markers(script)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC01"
    assert units[0].scene_text == "one"


def test_special_routing_and_comprehensive_info_are_attached_to_scene_tasks():
    script = """
[SCENES_BLOCK_START]
[COMPREHENSIVE_INFO_START]
[INFO_ITEM_START:PLOT:1]
overall plot
[INFO_ITEM_END:PLOT:1]
[COMPREHENSIVE_INFO_END]
[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]
[VFX] 命中=是｜类型=近身打斗｜证据=原文：“挥拳”
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC01]
[SCENE_START:EP01_SC01]
scene body
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
{"project_visual_backfill": {"tone": "tense"}}
"""
    units = parse_scene_units_from_markers(script)
    assert units[0].special_routing["VFX"]["hit"] is True
    assert units[0].special_routing["XIAN"]["hit"] is False
    assert "[COMPREHENSIVE_INFO_START]" in units[0].comprehensive_info

    tasks = build_scene_subskill_task_payloads(script)
    assert len(tasks) == 1
    assert tasks[0]["call_vfx"] is True
    assert tasks[0]["call_xian"] is False
    assert tasks[0]["special_analysis"].startswith("[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]")


def test_drama_output_special_is_kept_when_fallback_empty():
    drama_output = """
[SCENES_BLOCK_START]
[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]
[VFX] 命中=是｜类型=近身打斗｜证据=原文：“挥拳”
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC01]
[SCENE_START:EP01_SC01]
【场景综合】本场卖点=对峙
optimized drama body
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
"""
    extracted = _extract_single_scene_block(drama_output, "EP01_SC01", "")
    assert extracted.startswith("[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]")
    assert extracted.count("[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]") == 1
    assert "[VFX] 命中=是" in extracted
    assert "optimized drama body" in extracted


def test_scene_split_without_special_builds_tasks():
    script = """
[SCENES_BLOCK_START]
[COMPREHENSIVE_INFO_START]
overall plot
[COMPREHENSIVE_INFO_END]
[SCENE_START:EP01_SC01]
【场景衔接】上场=开场｜下场=EP01_SC02｜手法=硬切
scene body
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
"""
    tasks = build_scene_subskill_task_payloads(script)
    assert len(tasks) == 1
    assert tasks[0]["special_analysis"] == ""
    assert tasks[0]["call_vfx"] is False
    assert tasks[0]["call_xian"] is False


def test_subskill_duplicate_readonly_metadata_is_replaced_by_authoritative_block():
    authoritative_special = """[SPECIAL_SCENE_ANALYSIS_START:EP01_SC03]
[VFX] 命中=否｜类型=无｜证据=无
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC03]"""
    duplicated_output = f"""
[SCENES_BLOCK_START]
[COMPREHENSIVE_INFO_START]
first copy
[COMPREHENSIVE_INFO_END]
{authoritative_special}
{authoritative_special}
[SCENE_START:EP01_SC03]
optimized scene body
[SCENE_END:EP01_SC03]
[SCENES_BLOCK_END]
"""

    extracted = _extract_single_scene_block(
        duplicated_output,
        "EP01_SC03",
        authoritative_special,
    )

    assert extracted.count("[SPECIAL_SCENE_ANALYSIS_START:EP01_SC03]") == 1
    assert "[COMPREHENSIVE_INFO_START]" not in extracted
    assert "optimized scene body" in extracted


def test_subskill_env_matrix_only_output_is_parse_failed():
    from fastapi import HTTPException

    from app.services.scene_subskill_pipeline_runner import (
        _scene_subskill_failure_reason,
        _subskill_parse_failure_code,
    )

    matrix_only = """【Beat→衍生ENV剧情覆盖矩阵】
B1=R:{朝堂铁骑:全貌|地平线:可见面}｜ENV:0度荒漠残阳古道｜W:{沙丘:正面}｜R−W=∅｜选角=覆盖｜跨对向=否
【ENV覆盖综合】Beat=全量｜缺项=0｜同ENV最长=2｜新建主环境=无
"""
    try:
        _extract_single_scene_block(matrix_only, "EP01_SC02", "")
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "SCENE_SUBSKILL_OUTPUT_PARSE_FAILED:EP01_SC02:SCENE_MARKER_BLOCK_MISSING" == exc.detail
        assert _subskill_parse_failure_code(exc) == "SCENE_SUBSKILL_OUTPUT_PARSE_FAILED"
        assert "环境矩阵" in _scene_subskill_failure_reason(exc)
    else:
        raise AssertionError("expected parse failure for matrix-only output")


def test_subskill_staging_fragment_recovers_scene_wrappers():
    previous = """[SPECIAL_SCENE_ANALYSIS_START:EP01_SC02]
[VFX] 命中=否｜类型=无｜证据=无
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC02]
[SCENE_START:EP01_SC02]
【场景名称】清河城接头｜日·外
[ENV_BLOCK_START]
────【主环境】────
【主环境】荒漠残阳古道｜日夜内外=黄昏·外
[ENV_BLOCK_END]
[BEAT_STREAM_START]
[BEAT_START:1]
- Beat 1：
旧建置
[BEAT_END:1]
[BEAT_STREAM_END]
[SCENE_END:EP01_SC02]"""
    fragment = """【Beat→衍生ENV剧情覆盖矩阵】
B1=R:{朝堂铁骑:全貌|地平线:可见面}｜ENV:0度荒漠残阳古道｜W:{沙丘:正面}｜R−W=∅｜选角=覆盖｜跨对向=否
【ENV覆盖综合】Beat=全量｜缺项=0｜同ENV最长=3≤3｜例外:无｜新建主环境=无

【位置规划综合】主锚=无｜C位=朝堂铁骑簇｜依据=大军压境为本场唯一焦点
【角色位置】无
【未落实体位置】朝堂铁骑簇=初:后景中央｜变:B1-B3:向前景逼近｜终:前景中央

[BEAT_STREAM_START]
[BEAT_START:1]
- Beat 1：
镜头从残阳如血、狂风卷起漫天黄沙的空镜头缓慢向下摇。
[BEAT_END:1]
[BEAT_START:2]
~ Beat 2：
镜头极速推近至沙地特写。
[BEAT_END:2]
[BEAT_START:3]
- Beat 3：
铁骑阵列保持着冰冷的秩序。
[BEAT_END:3]
[BEAT_STREAM_END]"""
    special = """[SPECIAL_SCENE_ANALYSIS_START:EP01_SC02]
[VFX] 命中=否｜类型=无｜证据=无
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC02]"""

    extracted = _extract_single_scene_block(
        fragment,
        "EP01_SC02",
        special,
        previous_block=previous,
    )

    assert extracted.count("[SCENE_START:EP01_SC02]") == 1
    assert extracted.count("[SCENE_END:EP01_SC02]") == 1
    assert "【场景名称】清河城接头｜日·外" in extracted
    assert "【主环境】荒漠残阳古道" in extracted
    assert "【Beat→衍生ENV剧情覆盖矩阵】" in extracted
    assert "镜头从残阳如血" in extracted
    assert "铁骑阵列保持着冰冷的秩序" in extracted
    assert "旧建置" not in extracted
    assert extracted.count("[SPECIAL_SCENE_ANALYSIS_START:EP01_SC02]") == 1


def test_subskill_staging_fragment_wraps_when_previous_missing():
    fragment = """[BEAT_STREAM_START]
[BEAT_START:1]
- Beat 1：
空镜。
[BEAT_END:1]
[BEAT_STREAM_END]"""

    extracted = _extract_single_scene_block(fragment, "EP01_SC02", "")

    assert "[SCENE_START:EP01_SC02]" in extracted
    assert "[SCENE_END:EP01_SC02]" in extracted
    assert "空镜。" in extracted


def test_subskill_accepts_complete_beats_without_end_marker():
    from app.services.scene_subskill_pipeline_runner import (
        STAGING_PROMPT,
        _strip_subskill_completion_marker,
        _try_extract_subskill_scene_block,
    )

    body = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC04]
【场景名称】客栈夜话｜夜·内
[BEAT_STREAM_START]
[BEAT_START:1]
- Beat 1：
入夜。
[BEAT_END:1]
[BEAT_STREAM_END]
[SCENE_END:EP01_SC04]
[SCENES_BLOCK_END]"""

    assert _strip_subskill_completion_marker(body, STAGING_PROMPT) == ""
    extracted = _try_extract_subskill_scene_block(body, "EP01_SC04", "")
    assert "[SCENE_START:EP01_SC04]" in extracted
    assert "入夜。" in extracted
