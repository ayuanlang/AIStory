# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.derived_env_ingest import (
    build_derived_env_frame_anchor_injection,
    collect_derived_environment_jsons,
    extract_derived_environment_names_from_scene_text,
    parse_derived_env_extract_items,
    build_derived_environment_item,
    merge_derived_environment_groups,
)


SAMPLE = """【主体定位方案】掌柜=方式=相对｜锚=柜台｜组=无
【Beat主体定位】
B1=掌柜=方式=相对｜可见性=V｜组=无｜锚=柜台｜ENV:0度客栈大堂｜[DERIVED_ENV:0度客栈大堂]
B2=客人=方式=相对｜可见性=V｜组=无｜锚=客位｜ENV:180度客栈大堂｜[DERIVED_ENV:180度客栈大堂]
B3=掌柜=方式=相对｜可见性=V｜组=无｜锚=柜台｜ENV:0度客栈大堂_沙尘｜[DERIVED_ENV:0度客栈大堂_沙尘]
[DERIVED_ENV_EXTRACT_START]
[DERIVED_ENV] 名称=0度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=0｜类型=第一刀｜触发=Master｜lens_profile=Wide｜axis_crossing=None｜spatial_axis=门—柜台｜同角切割父=无｜状态Delta=无｜背景=柜台｜画左=楼梯口｜画右=账房窗
[DERIVED_ENV] 名称=180度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=180｜类型=第一刀｜触发=反打｜lens_profile=Standard｜axis_crossing=PlannedReverse｜spatial_axis=门—柜台｜同角切割父=无｜状态Delta=无｜背景=正门｜画左=账房窗｜画右=楼梯口
[DERIVED_ENV] 名称=0度客栈大堂_沙尘｜所属主环境=客栈大堂｜view_angle_from_main=0｜类型=衍生的衍生｜触发=状态｜lens_profile=Wide｜axis_crossing=None｜spatial_axis=门—柜台｜同角切割父=0度客栈大堂｜状态Delta=地面沙尘加厚｜背景=柜台｜画左=楼梯口｜画右=账房窗
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
    assert by_name["0度客栈大堂"]["background"] == "柜台"
    assert by_name["0度客栈大堂"]["frame_left"] == "楼梯口"
    assert by_name["0度客栈大堂"]["frame_right"] == "账房窗"
    assert not by_name["0度客栈大堂"].get("references")
    assert by_name["180度客栈大堂"]["background"] == "正门"
    assert by_name["180度客栈大堂"]["frame_left"] == "账房窗"
    assert by_name["180度客栈大堂"]["frame_right"] == "楼梯口"


def test_frame_anchor_injection_lists_named_sides():
    block = build_derived_env_frame_anchor_injection(SAMPLE)
    assert block.startswith("【衍生环境画幅锚】")
    assert "画外=镜头后对向主体，明确不可见" in block
    assert "选角与建置/入戏禁止点名画外主体" in block
    assert "宫格参照=画外时，落位改写为离镜头近处中间主体" in block
    assert (
        "ENV:[0度客栈大堂]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=0｜"
        "背景=柜台｜画左=楼梯口｜画右=账房窗"
    ) in block
    assert (
        "ENV:[180度客栈大堂]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=180｜"
        "背景=正门｜画左=账房窗｜画右=楼梯口"
    ) in block
    assert (
        "ENV:[0度客栈大堂_沙尘]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=0｜"
        "背景=柜台｜画左=楼梯口｜画右=账房窗"
    ) in block
    assert "画外=柜台" not in block
    assert "画外=正门" not in block


def test_frame_anchor_injection_keeps_main_when_sides_missing():
    text = (
        "[DERIVED_ENV_EXTRACT_START]\n"
        "[DERIVED_ENV] 名称=0度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=0｜类型=第一刀\n"
        "[DERIVED_ENV_EXTRACT_END]\n"
    )
    block = build_derived_env_frame_anchor_injection(text)
    assert "ENV:[0度客栈大堂]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=0" in block
    assert "背景=" not in block.split("ENV:[0度客栈大堂]", 1)[1].split("\n", 1)[0]


def test_frame_anchor_injection_empty_when_no_derived():
    assert build_derived_env_frame_anchor_injection("无衍生") == ""


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


def test_build_item_persists_frame_anchors():
    item = build_derived_environment_item(
        {
            "name": "0度客栈大堂",
            "main": "客栈大堂",
            "angle": 0,
            "kind": "第一刀",
            "background": "柜台",
            "frame_left": "楼梯口",
            "frame_right": "账房窗",
            "offscreen": "大门",
        }
    )
    attrs = item["custom_attributes"]
    assert attrs["background"] == "柜台"
    assert attrs["frame_left"] == "楼梯口"
    assert attrs["frame_right"] == "账房窗"
    assert attrs["offscreen"] == "大门"
    assert item["anchor_description"] == "背景=柜台｜画左=楼梯口｜画右=账房窗｜画外=大门（不可见）"
    assert "只切割，不要改画" in item["generation_prompt_cn"]
    assert "背景=柜台" not in item["generation_prompt_cn"]


def test_first_cut_anchor_description_empty_slots():
    item = build_derived_environment_item(
        {
            "name": "180度客栈大堂",
            "main": "客栈大堂",
            "angle": 180,
            "kind": "第一刀",
        }
    )
    assert item["anchor_description"] == ""


def test_derived_anchors_copy_matching_main_env_angle_subjects():
    from app.services.script_analysis_flow.derived_env_ingest import (
        format_derived_anchor_description,
        parse_derived_env_extract_items,
        parse_main_environment_angle_subjects,
    )

    text = (
        "────【主环境】────\n"
        "【主环境】客栈大堂｜日夜内外=日/内\n"
        "0度轴=大门｜四向+中心：0度=客栈大门｜扇型=单扇｜开闭=半开｜"
        "90度=雕花窗格｜180度=红木柜台与酒架｜270度=贴墙木楼梯｜中心=八仙桌\n"
        "空中=通高梁架\n"
        "[DERIVED_ENV_EXTRACT_START]\n"
        "[DERIVED_ENV] 名称=0度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=0｜"
        "类型=第一刀｜背景=柜台｜画左=无｜画右=正门｜参照物=八仙桌、算盘\n"
        "[DERIVED_ENV] 名称=180度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=180｜"
        "类型=第一刀｜背景=正门｜画左=无｜画右=无\n"
        "[DERIVED_ENV] 名称=0度客栈大堂_仰天｜所属主环境=客栈大堂｜view_angle_from_main=0｜"
        "类型=特别｜特别表述=仰天:梁架｜背景=无｜画左=无｜画右=无\n"
        "[DERIVED_ENV_EXTRACT_END]\n"
    )
    mains = parse_main_environment_angle_subjects(text)
    assert mains["客栈大堂"]["0"] == "客栈大门"
    assert mains["客栈大堂"]["90"] == "雕花窗格"
    assert mains["客栈大堂"]["180"] == "红木柜台与酒架"
    assert mains["客栈大堂"]["270"] == "贴墙木楼梯"
    assert mains["客栈大堂"]["空中"] == "通高梁架"

    by_name = {item["name"]: item for item in parse_derived_env_extract_items(text)}
    zero = by_name["0度客栈大堂"]
    assert zero["background"] == "客栈大门"
    assert zero["frame_left"] == "贴墙木楼梯"
    assert zero["frame_right"] == "雕花窗格"
    assert zero["offscreen"] == "红木柜台与酒架"
    assert not zero.get("references")
    reverse = by_name["180度客栈大堂"]
    assert reverse["background"] == "红木柜台与酒架"
    assert reverse["frame_left"] == "雕花窗格"
    assert reverse["frame_right"] == "贴墙木楼梯"
    assert reverse["offscreen"] == "客栈大门"
    look_up = by_name["0度客栈大堂_仰天"]
    assert look_up["background"] == "通高梁架"
    assert look_up["frame_left"] == "贴墙木楼梯"
    assert look_up["frame_right"] == "雕花窗格"
    assert look_up["offscreen"] == "红木柜台与酒架"

    built = build_derived_environment_item(zero)
    assert (
        built["anchor_description"]
        == "背景=客栈大门｜画左=贴墙木楼梯｜画右=雕花窗格｜画外=红木柜台与酒架（不可见）"
    )
    assert built["custom_attributes"]["offscreen"] == "红木柜台与酒架"
    assert "无" not in built["anchor_description"]
    assert "背景=柜台" not in built["anchor_description"]
    assert "背景=红木柜台" not in built["anchor_description"]
    assert "八仙桌" not in built["anchor_description"]
    reverse_built = build_derived_environment_item(reverse)
    assert reverse_built["anchor_description"] == (
        "背景=红木柜台与酒架｜画左=雕花窗格｜画右=贴墙木楼梯｜画外=客栈大门（不可见）"
    )
    look_up_built = build_derived_environment_item(look_up)
    assert look_up_built["anchor_description"].startswith("背景=通高梁架")
    assert "画外=红木柜台与酒架（不可见）" in look_up_built["anchor_description"]
    assert format_derived_anchor_description(
        background="无", frame_left="无", frame_right="无", offscreen="无"
    ) == ""
    assert format_derived_anchor_description(offscreen="红木柜台") == "画外=红木柜台（不可见）"
    assert (
        format_derived_anchor_description(offscreen="红木柜台（不可见）")
        == "画外=红木柜台（不可见）"
    )

    injection = build_derived_env_frame_anchor_injection(text)
    assert "画外=红木柜台与酒架（不可见）" in injection
    assert "画外=客栈大门（不可见）" in injection
    assert "选角与建置/入戏禁止点名画外主体" in injection


def test_sample_ingest_writes_frame_and_reference_anchors():
    groups = collect_derived_environment_jsons(SAMPLE)
    by_name = {
        row["name"]: row
        for group in groups
        for row in group["payload"]["environments"]
    }
    zero = by_name["0度客栈大堂"]["anchor_description"]
    assert "背景=柜台" in zero
    assert "画左=楼梯口" in zero
    assert "画右=账房窗" in zero
    assert "参照物=" not in zero
    assert "柜台" in zero
    assert by_name["0度客栈大堂"]["generation_prompt_cn"].startswith("所属主环境=客栈大堂")


def test_derived_env_anchors_drop_character_and_prop_content():
    from app.services.script_analysis_flow.derived_env_ingest import (
        format_derived_anchor_description,
        parse_derived_env_extract_items,
    )

    dirty = (
        "【主体定位方案】CHAR:[@金镶玉]=方式=相对｜锚=二楼客房木门\n"
        "CHAR:[@金镶玉]右手挥出气刃。PROP:[皇家暗纹玉佩]脱落。"
        "CHAR:[@金镶玉]冷冷逼视。CHAR:[@李玄]死死抿住唇线。"
        "CHAR:[@金镶玉]双手猛然合拢结印。CHAR:[@李玄]后背撞上木门。"
        "CHAR:[@金镶玉]双掌齐出。\n"
        "[DERIVED_ENV_EXTRACT_START]\n"
        "[DERIVED_ENV] 名称=0度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=0｜"
        "类型=第一刀｜背景=二楼雕花栏杆｜画左=客栈大门｜画右=柜台｜"
        "参照物=二楼客房木门、二楼雕花栏杆、CHAR:[@金镶玉]右手挥出气刃、"
        "PROP:[皇家暗纹玉佩]脱落、CHAR:[@金镶玉]冷冷逼视、CHAR:[@李玄]死死抿住唇线、"
        "CHAR:[@金镶玉]双手猛然合拢结印、CHAR:[@李玄]后背撞上木门、"
        "CHAR:[@金镶玉]双掌齐出、客栈大门、柜台\n"
        "[DERIVED_ENV_EXTRACT_END]\n"
    )
    item = parse_derived_env_extract_items(dirty)[0]
    built = build_derived_environment_item(item)
    anchor = built["anchor_description"]
    assert "背景=二楼雕花栏杆" in anchor
    assert "画左=客栈大门" in anchor
    assert "画右=柜台" in anchor
    assert "二楼客房木门" not in anchor
    assert "参照物=" not in anchor
    assert "CHAR:" not in anchor
    assert "PROP:" not in anchor
    assert "金镶玉" not in anchor
    assert "李玄" not in anchor
    assert "玉佩" not in anchor
    assert "挥出气刃" not in anchor
    assert format_derived_anchor_description(
        background="CHAR:[@金镶玉]冷冷逼视",
        frame_left="客栈大门",
        frame_right="柜台",
        references=["PROP:[皇家暗纹玉佩]脱落", "二楼雕花栏杆"],
    ) == "画左=客栈大门｜画右=柜台"


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
    assert framing_req.action_name.startswith("场景现场编排")
    assert framing_req.system_prompt is None
    assert framing_req.scene_analysis_mode == "classic"


def test_staging_gate_requires_framing_plan_and_tags():
    from fastapi import HTTPException
    from app.services.scene_subskill_pipeline_runner import (
        assert_derived_framing_ready_for_staging,
    )

    ready = assert_derived_framing_ready_for_staging(SAMPLE, "EP01_SC02")
    assert "【Beat主体定位】" in ready
    assert "[DERIVED_ENV:" in ready

    try:
        assert_derived_framing_ready_for_staging("文戏+仙攻完成，没有构图方案", "EP01_SC02")
        raise AssertionError("expected staging to be blocked")
    except HTTPException as exc:
        assert "STAGING_BLOCKED_FRAMING_INCOMPLETE" in str(exc.detail)

    try:
        assert_derived_framing_ready_for_staging("【Beat主体定位】B1=掌柜=可见性=V", "EP01_SC02")
        raise AssertionError("expected missing extract tags to block staging")
    except HTTPException as exc:
        assert "STAGING_BLOCKED_FRAMING_INCOMPLETE" in str(exc.detail)

    legacy = (
        "【Beat景别构图方案】B1=景别=WS｜ENV:0度客栈大堂｜[DERIVED_ENV:0度客栈大堂]\n"
        "[DERIVED_ENV_EXTRACT_START]\n"
        "[DERIVED_ENV] 名称=0度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=0\n"
        "[DERIVED_ENV_EXTRACT_END]\n"
    )
    legacy_ready = assert_derived_framing_ready_for_staging(legacy, "EP01_SC02")
    assert "【Beat景别构图方案】" in legacy_ready


def test_staging_gate_requires_per_beat_framing_lock():
    from fastapi import HTTPException
    from app.services.scene_subskill_pipeline_runner import (
        assert_derived_framing_ready_for_staging,
    )

    locked = (
        SAMPLE
        + "\n[BEAT_STREAM_START]\n"
        + "[BEAT_START:1]\n- Beat 1：\n"
        + "【取景锁定】当前环境=0度客栈大堂｜景别=WS｜构图=三分｜镜头角度=平拍｜关系角=干净｜主体落点=画左三分｜留白=视线前｜纵深层=前中后同时可读\n"
        + "掌柜拨算盘。\n"
        + "────【场记分析】────\n"
        + "选择证据=ENV:Beat:拨算盘｜机位:Beat:柜台后｜景别:文戏:开场画面｜构图:场级三分｜[DERIVED_ENV:0度客栈大堂]\n"
        + "────【场记分析结束】────\n"
        + "[BEAT_END:1]\n"
        + "[BEAT_START:2]\n- Beat 2：\n"
        + "【取景锁定】当前环境=180度客栈大堂｜景别=MS｜构图=中心｜镜头角度=平拍｜关系角=过肩｜主体落点=中央｜留白=无｜纵深层=浅层单焦\n"
        + "客人抬头。\n"
        + "────【场记分析】────\n"
        + "选择证据=ENV:Beat:客人抬头｜机位:Beat:对掌柜｜景别:Beat:对白｜构图:文戏:对峙｜[DERIVED_ENV:180度客栈大堂]\n"
        + "────【场记分析结束】────\n"
        + "[BEAT_END:2]\n"
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

    missing_angle = (
        SAMPLE
        + "\n[BEAT_START:1]\n- Beat 1：\n"
        + "【取景锁定】当前环境=0度客栈大堂｜[DERIVED_ENV:0度客栈大堂]｜景别=WS｜构图=三分\n"
        + "掌柜拨算盘。\n[BEAT_END:1]\n"
    )
    try:
        assert_derived_framing_ready_for_staging(missing_angle, "EP01_SC02")
        raise AssertionError("expected missing 镜头角度 to block staging")
    except HTTPException as exc:
        assert "STAGING_BLOCKED_FRAMING_BEAT_LOCK" in str(exc.detail)

    missing_evidence = (
        SAMPLE
        + "\n[BEAT_START:1]\n- Beat 1：\n"
        + "【取景锁定】当前环境=0度客栈大堂｜[DERIVED_ENV:0度客栈大堂]｜景别=WS｜构图=三分｜镜头角度=平拍\n"
        + "掌柜拨算盘。\n[BEAT_END:1]\n"
    )
    try:
        assert_derived_framing_ready_for_staging(missing_evidence, "EP01_SC02")
        raise AssertionError("expected missing 选择证据 to block staging")
    except HTTPException as exc:
        assert "STAGING_BLOCKED_FRAMING_BEAT_LOCK" in str(exc.detail)


def test_staging_gate_uses_rewritten_beat_lock():
    from app.services.scene_subskill_pipeline_runner import (
        assert_derived_framing_ready_for_staging,
    )

    echoed = (
        SAMPLE
        + "\n[BEAT_START:1]\n掌柜拨算盘。\n[BEAT_END:1]\n"
        + "[BEAT_STREAM_START]\n"
        + "[BEAT_START:1]\n"
        + "【取景锁定】当前环境=0度客栈大堂｜景别=WS｜构图=三分｜镜头角度=平拍｜选择证据＝ENV:文戏:开场｜[DERIVED_ENV:0度客栈大堂]\n"
        + "掌柜拨算盘。\n[BEAT_END:1]\n"
        + "[BEAT_STREAM_END]\n"
    )
    ready = assert_derived_framing_ready_for_staging(echoed, "EP01_SC01")
    assert "【取景锁定】当前环境=0度客栈大堂" in ready


def test_extract_keeps_framing_payload_after_scene_end():
    from app.services.scene_subskill_pipeline_runner import (
        _extract_single_scene_block,
        assert_derived_framing_ready_for_staging,
    )

    raw = (
        "[SCENES_BLOCK_START]\n"
        "[SCENE_START:EP01_SC01]\n"
        "【场景名称】客栈\n"
        "[SCENE_END:EP01_SC01]\n"
        "[SCENES_BLOCK_END]\n"
        f"{SAMPLE}"
        "[BEAT_STREAM_START]\n"
        "[BEAT_START:1]\n"
        "【取景锁定】当前环境=ENV:[0度客栈大堂]｜景别=WS｜构图=三分｜镜头角度=平拍｜"
        "选择证据=ENV:文戏:开场｜机位:Beat:柜台｜景别:文戏:开场｜构图:场级三分｜"
        "[DERIVED_ENV:0度客栈大堂]\n"
        "掌柜拨算盘。\n"
        "[BEAT_END:1]\n"
        "[BEAT_STREAM_END]\n"
        "[DERIVED_FRAMING_OUTPUT_END]\n"
    )
    extracted = _extract_single_scene_block(raw, "EP01_SC01", "")
    assert "[DERIVED_ENV_EXTRACT_START]" in extracted
    assert "【Beat主体定位】" in extracted
    assert "【取景锁定】" in extracted
    ready = assert_derived_framing_ready_for_staging(extracted, "EP01_SC01")
    assert "【取景锁定】" in ready


def test_extract_keeps_framing_payload_before_scenes_block_end():
    from app.services.scene_subskill_pipeline_runner import (
        _extract_single_scene_block,
        _scene_subskill_failure_reason,
        assert_derived_framing_ready_for_staging,
    )
    from fastapi import HTTPException

    raw = (
        "[SCENES_BLOCK_START]\n"
        "[SCENE_START:EP01_SC01]\n"
        "【场景名称】客栈\n"
        "[SCENE_END:EP01_SC01]\n"
        f"{SAMPLE}"
        "[BEAT_STREAM_START]\n"
        "[BEAT_START:1]\n"
        "【取景锁定】当前环境=ENV:[0度客栈大堂]｜景别=WS｜构图=三分｜镜头角度=平拍｜"
        "选择证据=ENV:文戏:开场｜[DERIVED_ENV:0度客栈大堂]\n"
        "掌柜拨算盘。\n"
        "[BEAT_END:1]\n"
        "[BEAT_STREAM_END]\n"
        "[SCENES_BLOCK_END]\n"
        "[DERIVED_FRAMING_OUTPUT_END]\n"
    )
    extracted = _extract_single_scene_block(raw, "EP01_SC01", "")
    assert "[DERIVED_ENV_EXTRACT_START]" in extracted
    assert "【取景锁定】" in extracted
    assert_derived_framing_ready_for_staging(extracted, "EP01_SC01")

    reason = _scene_subskill_failure_reason(
        HTTPException(status_code=422, detail="STAGING_BLOCKED_FRAMING_BEAT_LOCK:EP01_SC01:1,3")
    )
    assert "拍 1,3" in reason
    assert "已返回" in reason


def test_framing_gate_accepts_markdown_fence_and_scene_content_markers():
    from app.services.scene_subskill_pipeline_runner import (
        _coerce_ready_framing_block,
        _scene_subskill_failure_reason,
        _strip_subskill_completion_marker,
        _try_extract_subskill_scene_block,
        FRAMING_PROMPT,
        assert_derived_framing_ready_for_staging,
    )
    from fastapi import HTTPException

    raw = """```markdown
[SCENE_START:EP01_SC03]
【场景名称】水墨苍岭山道
[SCENE_CONTENT_START:EP01_SC03]
林昭被围。
[SCENE_CONTENT_END:EP01_SC03]
【主体定位方案】CHAR:[@林昭]=方式=绝对｜宫格=中
【宫格草稿】
B1=中:{林昭}
【Beat主体定位】
B1=ENV:0度水墨苍岭山道｜CHAR:[@林昭]=可见性=V
[DERIVED_ENV_EXTRACT_START]
[DERIVED_ENV] 名称=0度水墨苍岭山道｜所属主环境=水墨苍岭山道｜view_angle_from_main=0
[DERIVED_ENV_EXTRACT_END]
[BEAT_STREAM_START]
[BEAT_START:1]
【取景锁定】当前环境=ENV:[0度水墨苍岭山道]｜景别=WS｜构图=中心｜镜头角度=平拍｜选择证据=ENV:Beat:包抄｜[DERIVED_ENV:0度水墨苍岭山道]
林昭被围。
[BEAT_END:1]
[BEAT_STREAM_END]
[SCENE_END:EP01_SC03]
[SCENES_BLOCK_END]
[DERIVED_FRAMING_OUTPUT_END]
```
"""
    stripped = _strip_subskill_completion_marker(raw, FRAMING_PROMPT)
    extracted = _try_extract_subskill_scene_block(stripped or raw, "EP01_SC03", "")
    ready = _coerce_ready_framing_block(extracted, stripped or raw, "EP01_SC03")
    assert ready
    assert "【取景锁定】" in ready
    assert_derived_framing_ready_for_staging(ready, "EP01_SC03")

    reason = _scene_subskill_failure_reason(
        HTTPException(status_code=422, detail="STAGING_BLOCKED_FRAMING_INCOMPLETE:EP01_SC03")
    )
    assert "主体定位或衍生环境提取" in reason


def test_framing_coerce_uses_raw_candidate_when_extract_is_header_only():
    from app.services.scene_subskill_pipeline_runner import _coerce_ready_framing_block

    extracted = "[SCENE_START:EP01_SC03]\n【场景名称】山道\n[SCENE_END:EP01_SC03]"
    candidate = (
        extracted
        + "\n【主体定位方案】林昭=中\n【宫格草稿】B1=中:{林昭}\n"
        + SAMPLE
        + "[BEAT_STREAM_START]\n[BEAT_START:1]\n"
        + "【取景锁定】当前环境=ENV:[0度客栈大堂]｜景别=WS｜构图=三分｜镜头角度=平拍｜"
        + "选择证据=ENV:文戏:开场｜[DERIVED_ENV:0度客栈大堂]\n"
        + "掌柜拨算盘。\n[BEAT_END:1]\n[BEAT_STREAM_END]\n"
    )
    ready = _coerce_ready_framing_block(extracted, candidate, "EP01_SC03")
    assert "【取景锁定】" in ready
    assert "[DERIVED_ENV_EXTRACT_START]" in ready


def test_strip_beat_notes_removes_analysis_and_legacy_transition():
    from app.services.script_analysis_flow import strip_beat_transition_notes_from_script

    source = (
        "[BEAT_START:8]\n- Beat 8：节拍=铺垫\n"
        "────【建置】────\n当前环境=0度无极宗山顶广场｜景别=MS\n"
        "────【入戏】────\n大长老递令牌。\n"
        "────【场记分析】────\n"
        "选择证据=ENV:Beat:授受双方同场｜跨度=越级:交付拉开\n"
        "速查更新=楚玄|扇区=0|F≈0\n"
        "────【场记分析结束】────\n"
        "[BEAT_END:8]\n"
        "[BEAT_START:9]\n- Beat 9：\n"
        "────【建置】────\n当前环境=0度无极宗山顶广场｜景别=MCU\n"
        "────【Beat切换说明】────\n变化过程=走位=无\n"
        "────【Beat切换说明结束】────\n"
        "[BEAT_END:9]\n"
    )
    cleaned = strip_beat_transition_notes_from_script(source)
    assert "【建置】" in cleaned
    assert "大长老递令牌" in cleaned
    assert "场记分析" not in cleaned
    assert "选择证据=" not in cleaned
    assert "Beat切换说明" not in cleaned
    assert "变化过程=走位=无" not in cleaned


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


def test_special_note_injected_into_generation_prompt():
    items = parse_derived_env_extract_items(
        "[DERIVED_ENV_EXTRACT_START]\n"
        "[DERIVED_ENV] 名称=0度客栈大堂｜所属主环境=客栈大堂｜view_angle_from_main=0｜类型=第一刀｜同角切割父=无｜状态Delta=无\n"
        "[DERIVED_ENV] 名称=0度客栈大堂_仰天｜所属主环境=客栈大堂｜view_angle_from_main=0｜类型=特别｜特别表述=仰天:满幅夜空与檐口剪影，地面仅近端截断｜同角切割父=无｜状态Delta=无\n"
        "[DERIVED_ENV] 名称=180度客栈大堂_变形｜所属主环境=客栈大堂｜view_angle_from_main=180｜类型=特别｜特别表述=变形:荷兰角地平线左低右高，立柱倾斜压迫｜同角切割父=无｜状态Delta=无\n"
        "[DERIVED_ENV_EXTRACT_END]\n"
    )
    by_name = {item["name"]: item for item in items}
    assert by_name["0度客栈大堂_仰天"]["special_note"].startswith("仰天")
    regular = build_derived_environment_item(by_name["0度客栈大堂"])
    assert "特别表述=" not in regular["generation_prompt_cn"]
    assert regular["custom_attributes"]["derived_kind"] == "first_cut"
    look_up = build_derived_environment_item(by_name["0度客栈大堂_仰天"])
    assert "特别表述=仰天:满幅夜空与檐口剪影，地面仅近端截断" in look_up["generation_prompt_cn"]
    assert "按该特别表述改机位俯仰或透视" in look_up["generation_prompt_cn"]
    assert "只切割，不要改画" not in look_up["generation_prompt_cn"]
    assert look_up["custom_attributes"]["derived_kind"] == "special"
    assert look_up["visual_dependencies"] == ["ENV:[客栈大堂]"]
    warped = build_derived_environment_item(by_name["180度客栈大堂_变形"])
    assert "特别表述=变形:荷兰角地平线左低右高，立柱倾斜压迫" in warped["generation_prompt_cn"]
    assert "dutch angle" not in warped["negative_prompt_en"]


def test_coverage_suffix_merges_into_degree_main_name():
    item = build_derived_environment_item(
        {
            "name": "180度客栈大堂_桌后反打",
            "main": "客栈大堂",
            "angle": 180,
            "kind": "第一刀",
        }
    )
    assert item["name"] == "180度客栈大堂"
    assert item["visual_dependencies"] == ["ENV:[客栈大堂]"]
    assert "右下180度格" in item["generation_prompt_cn"]
    assert "已切割的同角衍生" not in item["generation_prompt_cn"]


def test_same_direction_shot_size_aliases_merge():
    from app.services.script_analysis_flow.derived_env_ingest import (
        canonicalize_derived_environment_name,
        rewrite_merged_derived_environment_names,
    )

    assert canonicalize_derived_environment_name("0度客栈大堂_近景", {"main": "客栈大堂"}) == "0度客栈大堂"
    assert canonicalize_derived_environment_name("0度客栈大堂_仰视", {"main": "客栈大堂"}) == "0度客栈大堂_仰天"
    assert canonicalize_derived_environment_name(
        "0度客栈大堂_沙尘",
        {"main": "客栈大堂", "kind": "衍生的衍生", "state_delta": "地面沙尘加厚"},
    ) == "0度客栈大堂_沙尘"
    rewritten = rewrite_merged_derived_environment_names(
        "当前环境=0度客栈大堂_近景｜[DERIVED_ENV:0度客栈大堂_桌后反打]｜ENV:0度客栈大堂_沙尘"
    )
    assert "0度客栈大堂_近景" not in rewritten
    assert "0度客栈大堂_桌后反打" not in rewritten
    assert "[DERIVED_ENV:0度客栈大堂]" in rewritten
    assert "ENV:0度客栈大堂_沙尘" in rewritten


def test_beat_evidence_titles_are_not_derived_env_names():
    from app.services.script_analysis_flow.derived_env_ingest import (
        canonicalize_derived_environment_name,
        parse_derived_env_extract_items,
        rewrite_merged_derived_environment_names,
    )

    extra = {"main": "当铺柜房"}
    assert canonicalize_derived_environment_name("Beat:金镶玉拨算盘", extra) == "0度当铺柜房"
    assert canonicalize_derived_environment_name(
        "0deg Beat:金镶玉拨算盘，再收紧些",
        extra,
    ) == "0度当铺柜房"
    assert canonicalize_derived_environment_name("Beat:金镶玉拨算盘") == ""
    assert canonicalize_derived_environment_name("0deg当铺柜房", extra) == "0度当铺柜房"

    source = (
        "【主环境】当铺柜房｜日夜内外=日/内\n"
        "当前环境=Beat:金镶玉拨算盘｜[DERIVED_ENV:0deg Beat:金镶玉拨算盘，再收紧些]\n"
        "选择证据=ENV:Beat:金镶玉拨算盘｜机位:Beat:柜台后\n"
        "[DERIVED_ENV_EXTRACT_START]\n"
        "[DERIVED_ENV] 名称=Beat:金镶玉拨算盘｜所属主环境=当铺柜房｜view_angle_from_main=0｜类型=第一刀｜同角切割父=无｜状态Delta=无\n"
        "[DERIVED_ENV] 名称=0deg Beat:金镶玉拨算盘，再收紧些｜所属主环境=当铺柜房｜view_angle_from_main=0｜类型=第一刀｜同角切割父=无｜状态Delta=无\n"
        "[DERIVED_ENV_EXTRACT_END]\n"
    )
    rewritten = rewrite_merged_derived_environment_names(source)
    assert "当前环境=0度当铺柜房" in rewritten
    assert "[DERIVED_ENV:0度当铺柜房]" in rewritten
    assert "选择证据=ENV:Beat:金镶玉拨算盘" in rewritten
    assert "Beat:金镶玉拨算盘，再收紧些" not in rewritten
    names = {item["name"] for item in parse_derived_env_extract_items(rewritten)}
    assert names == {"0度当铺柜房"}


def test_canonicalize_unwraps_typed_env_token():
    from app.services.script_analysis_flow.derived_env_ingest import (
        canonicalize_derived_environment_name,
        extract_derived_environment_names_from_scene_text,
        rewrite_merged_derived_environment_names,
    )

    assert canonicalize_derived_environment_name("ENV:[0度客栈大堂]") == "0度客栈大堂"
    source = (
        "【主环境】客栈大堂\n"
        "【本场衍生环境名】ENV:[0度客栈大堂]，ENV:[180度客栈大堂]\n"
        "【取景锁定】当前环境=ENV:[0度客栈大堂]｜景别=WS\n"
    )
    rewritten = rewrite_merged_derived_environment_names(source)
    assert "当前环境=ENV:[0度客栈大堂]" in rewritten
    names = extract_derived_environment_names_from_scene_text(source)
    assert "0度客栈大堂" in names
    assert "180度客栈大堂" in names


def test_canonicalize_strips_stacked_english_aliases():
    from app.services.script_analysis_flow.derived_env_ingest import (
        canonicalize_derived_environment_name,
        extract_derived_environment_names_from_scene_text,
    )

    stacked = (
        "0度岚京高空交通层 (Lan-Jing Aerial Transit Layer) "
        "(Lan-Jing Aerial Transit Layer) (Lan-Jing Aerial Transit Layer)"
    )
    assert canonicalize_derived_environment_name(stacked) == "0度岚京高空交通层"
    assert (
        canonicalize_derived_environment_name(
            stacked,
            {"main": "岚京高空交通层 (Lan-Jing Aerial Transit Layer)"},
        )
        == "0度岚京高空交通层"
    )
    scene_text = (
        "【本场衍生环境名】"
        "ENV:[0度岚京高空交通层 (Lan-Jing Aerial Transit Layer) (Lan-Jing Aerial Transit Layer)]，"
        "ENV:[90度岚京高空交通层 (Lan-Jing Aerial Transit Layer)]，"
        "ENV:[0度岚京高空交通层 (Lan-Jing Aerial Transit Layer)]\n"
    )
    assert extract_derived_environment_names_from_scene_text(scene_text) == (
        "0度岚京高空交通层，90度岚京高空交通层"
    )


def test_collect_framing_texts_prefers_scene_framing_output():
    from app.services.script_analysis_flow.derived_env_ingest import (
        collect_framing_texts_from_results_map,
        has_derived_env_signals,
    )

    assert has_derived_env_signals(SAMPLE)
    rows = collect_framing_texts_from_results_map(
        {
            "EP01_SC01": {"framing": SAMPLE, "staging": "建置稿，不含衍生标签"},
            "EP01_SC02": {"framing": "", "staging": SAMPLE},
            "EP01_SC03": {"framing": "", "staging": "只有建置"},
        }
    )
    by_id = {row["scene_id"]: row for row in rows}
    assert by_id["EP01_SC01"]["source"] == "framing"
    assert by_id["EP01_SC02"]["source"] == "staging"
    assert "EP01_SC03" not in by_id
    scoped = collect_framing_texts_from_results_map(
        {"EP01_SC01": {"framing": SAMPLE}, "EP01_SC02": {"staging": SAMPLE}},
        scene_ids=["EP01_SC02"],
    )
    assert [row["scene_id"] for row in scoped] == ["EP01_SC02"]


def test_regen_derived_env_button_does_not_call_llm():
    from pathlib import Path

    editor = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "editor" / "components" / "ScriptEditor.jsx"
    src = editor.read_text(encoding="utf-8")
    assert "handleRegenDerivedEnvironments" in src
    assert "ingestDerivedEnvironmentsFromFraming" in src
    assert "envScope: 'derived'" not in src


def test_ingest_endpoint_is_programmatic():
    from pathlib import Path

    router = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "prompts" / "progress_flow.py"
    src = router.read_text(encoding="utf-8")
    assert "ingest-derived-environments" in src
    assert "regen_derived_environments_from_framing" in src
    assert "No LLM" in src or "no LLM" in src.lower()
