# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.derived_env_ingest import (
    collect_derived_environment_jsons,
    extract_derived_environment_names_from_scene_text,
    parse_derived_env_extract_items,
    build_derived_environment_item,
    merge_derived_environment_groups,
)


SAMPLE = """【Beat景别构图方案】
B1=景别=WS｜构图=三分｜ENV:0度客栈大堂｜[DERIVED_ENV:0度客栈大堂]
B2=景别=MS｜构图=中心｜ENV:180度客栈大堂｜[DERIVED_ENV:180度客栈大堂]
B3=景别=WS｜构图=三分｜ENV:0度客栈大堂_沙尘｜[DERIVED_ENV:0度客栈大堂_沙尘]
【景别构图综合】Beat=全量
[DERIVED_ENV_EXTRACT_START]
[DERIVED_ENV] 名称=0度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=0｜类型=第一刀｜触发=Master｜lens_profile=Wide｜axis_crossing=None｜spatial_axis=门—柜台｜同角切割父=无｜状态Delta=无
[DERIVED_ENV] 名称=180度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=180｜类型=第一刀｜触发=反打｜lens_profile=Standard｜axis_crossing=PlannedReverse｜spatial_axis=门—柜台｜同角切割父=无｜状态Delta=无
[DERIVED_ENV] 名称=0度客栈大堂_沙尘｜所属主环境=客栈大堂｜view_angle_from_main=0｜类型=衍生的衍生｜触发=状态｜lens_profile=Wide｜axis_crossing=None｜spatial_axis=门—柜台｜同角切割父=0度客栈大堂｜状态Delta=地面沙尘加厚
[DERIVED_ENV_EXTRACT_END]
"""


def test_parse_derived_env_tags_and_extract_block():
    items = parse_derived_env_extract_items(SAMPLE)
    names = {item["name"] for item in items}
    assert names == {"0度客栈大堂", "180度客栈大堂", "0度客栈大堂_沙尘"}
    by_name = {item["name"]: item for item in items}
    assert by_name["180度客栈大堂"]["angle"] == 180
    assert by_name["180度客栈大堂"]["main"] == "客栈大堂"
    assert by_name["0度客栈大堂_沙尘"]["kind"] == "衍生的衍生"


def test_first_cut_json_matches_environment_design_template():
    item = build_derived_environment_item(
        {
            "name": "180度客栈大堂",
            "main": "客栈大堂",
            "angle": 180,
            "kind": "第一刀",
            "lens_profile": "Standard",
            "axis_crossing": "PlannedReverse",
        }
    )
    prompt = item["generation_prompt_cn"]
    assert "所属主环境=客栈大堂" in prompt
    assert "angle_key=客栈大堂|180" in prompt
    assert "右下180度格" in prompt
    assert "只切割，不要改画" in prompt
    assert item["visual_dependencies"] == ["ENV:[客栈大堂]"]
    assert item["description_cn"] == ""
    assert item["dependency_strategy"]["type"] == "Type A"
    assert "截取宫格=右下180度格" in item["dependency_strategy"]["logic"]


def test_state_cut_json_hangs_same_angle_parent():
    item = build_derived_environment_item(
        {
            "name": "0度客栈大堂_沙尘",
            "main": "客栈大堂",
            "angle": 0,
            "kind": "衍生的衍生",
            "parent": "0度客栈大堂",
            "state_delta": "地面沙尘加厚",
        }
    )
    prompt = item["generation_prompt_cn"]
    assert "以已切割的同角衍生「0度客栈大堂」" in prompt
    assert "在此画面基础上叠加：地面沙尘加厚" in prompt
    assert item["visual_dependencies"] == ["ENV:[0度客栈大堂]"]


def test_group_json_by_main_environment():
    groups = collect_derived_environment_jsons(
        SAMPLE
        + "\nB4=ENV:0度马车内舱｜[DERIVED_ENV:0度马车内舱]\n"
        + "[DERIVED_ENV_EXTRACT_START]\n"
        + "[DERIVED_ENV] 名称=0度马车内舱｜所属主环境=马车内舱｜view_angle_from_main=0｜类型=第一刀｜同角切割父=无｜状态Delta=无\n"
        + "[DERIVED_ENV_EXTRACT_END]\n"
    )
    mains = {group["main_environment"]: group for group in groups}
    assert set(mains) == {"客栈大堂", "马车内舱"}
    inn = mains["客栈大堂"]
    assert inn["count"] == 3
    assert '"environments"' in inn["json"]
    assert "0度客栈大堂" in inn["json"]
    assert "180度客栈大堂" in inn["json"]
    assert inn["payload"]["environments"][0]["generation_prompt_cn"]
    assert mains["马车内舱"]["count"] == 1


def test_extract_derived_environment_names_from_extract_block():
    assert extract_derived_environment_names_from_scene_text(SAMPLE) == (
        "0度客栈大堂，180度客栈大堂，0度客栈大堂_沙尘"
    )


def test_extract_derived_environment_names_from_scene_header():
    scene_text = "【本场衍生环境名】0度客栈废墟外，180度客栈废墟外，客栈废墟外"
    assert extract_derived_environment_names_from_scene_text(scene_text) == (
        "0度客栈废墟外，180度客栈废墟外"
    )


def test_extract_derived_environment_names_skips_bare_main_name():
    scene_text = """
[ENV_BLOCK_START]
【主环境】客栈废墟外｜日夜内外=黄昏·外
────【衍生环境】────
- `客栈废墟外`：所属主环境=客栈废墟外
- `0度客栈废墟外`：所属主环境=客栈废墟外
[ENV_BLOCK_END]
[DERIVED_ENV:客栈废墟外]
[DERIVED_ENV:0度客栈废墟外]
"""
    assert extract_derived_environment_names_from_scene_text(scene_text) == "0度客栈废墟外"


def test_extract_derived_environment_names_from_derived_section_bullets():
    scene_text = """
[ENV_BLOCK_START]
────【主环境】────
【主环境】客栈废墟外｜日夜内外=黄昏·外
────【衍生环境】────
- `0度客栈废墟外`：所属主环境=客栈废墟外
- `180度客栈废墟外`：所属主环境=客栈废墟外
[ENV_BLOCK_END]
"""
    assert extract_derived_environment_names_from_scene_text(scene_text) == (
        "0度客栈废墟外，180度客栈废墟外"
    )


def test_main_path_retry_matches_scene_split():
    from app.services.scene_markdown_orchestration import SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS
    from app.services.script_analysis_flow_runner import SCRIPT_ANALYSIS_MAIN_PATH_RETRY_ATTEMPTS

    assert SCRIPT_ANALYSIS_MAIN_PATH_RETRY_ATTEMPTS == 3
    assert SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS == 3


def test_post_env_steps_are_framing_then_staging():
    from app.services.scene_subskill_pipeline_runner import (
        FRAMING_PROMPT,
        SCENE_SUBSKILL_POST_ENV_STEPS,
        STAGING_PROMPT,
        _build_subskill_request,
        _subskill_action_label,
    )

    assert [step for step, _ in SCENE_SUBSKILL_POST_ENV_STEPS] == ["derived_framing", "staging"]
    assert SCENE_SUBSKILL_POST_ENV_STEPS[0][1] == FRAMING_PROMPT
    assert SCENE_SUBSKILL_POST_ENV_STEPS[1][1] == STAGING_PROMPT
    framing_req = _build_subskill_request(
        {"project_id": 258, "episode_id": 1, "prompt_file": STAGING_PROMPT, "action_name": "建置与入戏"},
        prompt_file=FRAMING_PROMPT,
        scene_input="scene",
        scene_id="EP01_SC01",
    )
    assert framing_req.prompt_file == FRAMING_PROMPT
    assert framing_req.action_name == f"{_subskill_action_label(FRAMING_PROMPT)} · EP01_SC01"
    assert framing_req.action_name.startswith("景别构图与衍生环境")
    assert framing_req.system_prompt is None
    assert framing_req.scene_analysis_mode == "classic"


def test_staging_gate_requires_framing_plan_and_tags():
    from fastapi import HTTPException
    from app.services.scene_subskill_pipeline_runner import (
        assert_derived_framing_ready_for_staging,
    )

    ready = assert_derived_framing_ready_for_staging(SAMPLE, "EP01_SC02")
    assert "【Beat景别构图方案】" in ready
    assert "[DERIVED_ENV:" in ready

    try:
        assert_derived_framing_ready_for_staging("文戏+仙攻完成，没有构图方案", "EP01_SC02")
        raise AssertionError("expected staging to be blocked")
    except HTTPException as exc:
        assert "STAGING_BLOCKED_FRAMING_INCOMPLETE" in str(exc.detail)

    try:
        assert_derived_framing_ready_for_staging("【Beat景别构图方案】B1=ENV:0度客栈大堂", "EP01_SC02")
        raise AssertionError("expected missing extract tags to block staging")
    except HTTPException as exc:
        assert "STAGING_BLOCKED_FRAMING_INCOMPLETE" in str(exc.detail)


def test_staging_gate_requires_per_beat_framing_lock():
    from fastapi import HTTPException
    from app.services.scene_subskill_pipeline_runner import (
        assert_derived_framing_ready_for_staging,
    )

    locked = (
        SAMPLE
        + "\n[BEAT_STREAM_START]\n"
        + "[BEAT_START:1]\n- Beat 1：\n"
        + "【取景锁定】当前环境=0度客栈大堂｜[DERIVED_ENV:0度客栈大堂]｜景别=WS｜构图=三分｜主体落点=画左三分｜留白=视线前｜纵深层=前中后同时可读\n"
        + "掌柜拨算盘。\n[BEAT_END:1]\n"
        + "[BEAT_START:2]\n- Beat 2：\n"
        + "【取景锁定】当前环境=180度客栈大堂｜[DERIVED_ENV:180度客栈大堂]｜景别=MS｜构图=中心｜主体落点=中央｜留白=无｜纵深层=浅层单焦\n"
        + "客人抬头。\n[BEAT_END:2]\n"
        + "[BEAT_STREAM_END]\n"
    )
    ready = assert_derived_framing_ready_for_staging(locked, "EP01_SC02")
    assert "【取景锁定】当前环境=0度客栈大堂" in ready

    missing_lock = (
        SAMPLE
        + "\n[BEAT_START:1]\n- Beat 1：\n掌柜拨算盘。\n[BEAT_END:1]\n"
        + "[BEAT_START:2]\n- Beat 2：\n"
        + "【取景锁定】当前环境=180度客栈大堂｜[DERIVED_ENV:180度客栈大堂]｜景别=MS｜构图=中心\n"
        + "客人抬头。\n[BEAT_END:2]\n"
    )
    try:
        assert_derived_framing_ready_for_staging(missing_lock, "EP01_SC02")
        raise AssertionError("expected missing per-beat lock to block staging")
    except HTTPException as exc:
        assert "STAGING_BLOCKED_FRAMING_BEAT_LOCK" in str(exc.detail)
        assert ":1" in str(exc.detail)

    missing_shot = (
        SAMPLE
        + "\n[BEAT_START:1]\n- Beat 1：\n"
        + "【取景锁定】当前环境=0度客栈大堂｜[DERIVED_ENV:0度客栈大堂]｜构图=三分\n"
        + "掌柜拨算盘。\n[BEAT_END:1]\n"
    )
    try:
        assert_derived_framing_ready_for_staging(missing_shot, "EP01_SC02")
        raise AssertionError("expected missing 景别 to block staging")
    except HTTPException as exc:
        assert "STAGING_BLOCKED_FRAMING_BEAT_LOCK" in str(exc.detail)


def test_merge_derived_environment_groups_keeps_prior_mains():
    first = collect_derived_environment_jsons(SAMPLE)
    second = collect_derived_environment_jsons(
        "[DERIVED_ENV_EXTRACT_START]\n"
        "[DERIVED_ENV] 名称=0度马车内舱｜所属主环境=马车内舱｜view_angle_from_main=0｜类型=第一刀｜同角切割父=无｜状态Delta=无\n"
        "[DERIVED_ENV_EXTRACT_END]\n"
    )
    merged = merge_derived_environment_groups(first, second)
    mains = {group["main_environment"]: group for group in merged}
    assert set(mains) == {"客栈大堂", "马车内舱"}
    assert mains["客栈大堂"]["count"] == 3
    assert mains["马车内舱"]["count"] == 1
    overwritten = merge_derived_environment_groups(
        first,
        collect_derived_environment_jsons(
            "[DERIVED_ENV_EXTRACT_START]\n"
            "[DERIVED_ENV] 名称=180度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=180｜类型=第一刀｜触发=覆盖｜同角切割父=无｜状态Delta=无\n"
            "[DERIVED_ENV_EXTRACT_END]\n"
        ),
    )
    inn = {group["main_environment"]: group for group in overwritten}["客栈大堂"]
    assert inn["count"] == 3
    by_name = {row["name"]: row for row in inn["payload"]["environments"]}
    assert set(by_name) == {"0度客栈大堂", "180度客栈大堂", "0度客栈大堂_沙尘"}
    assert "触发=覆盖" in by_name["180度客栈大堂"]["dependency_strategy"]["logic"]


def test_pipeline_ingests_derived_env_immediately_after_framing():
    import inspect
    from app.services.scene_subskill_pipeline_runner import _run_derived_framing_then_staging

    src = inspect.getsource(_run_derived_framing_then_staging)
    framing_idx = src.find('if step_name == "derived_framing"')
    ingest_idx = src.find("_ingest_derived_environments_after_framing")
    staging_continue = src.find("called.append(step_name)")
    assert framing_idx != -1
    assert ingest_idx > framing_idx
    assert ingest_idx < staging_continue


def test_coverage_suffix_stays_first_cut():
    item = build_derived_environment_item(
        {
            "name": "180度客栈大堂_桌后反打",
            "main": "客栈大堂",
            "angle": 180,
            "kind": "第一刀",
        }
    )
    assert item["visual_dependencies"] == ["ENV:[客栈大堂]"]
    assert "右下180度格" in item["generation_prompt_cn"]
    assert "已切割的同角衍生" not in item["generation_prompt_cn"]
