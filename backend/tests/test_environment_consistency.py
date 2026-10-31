# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.environment_consistency import (
    ConsistencyApplyError,
    apply_consistency_writes,
    audit_front_double,
    seal_cell_edit_instruction,
    audit_piece_count_reconciliation,
    audit_street_end_phrases,
    audit_wall_corner_span,
    build_consistency_messages,
    classify_checked_prompt,
    parse_consistency_payload,
    plan_consistency_writes,
    remote_vision_image_link,
)


MAIN_PROMPT = """【六面一次】
占地=2.4×0.9米。竖边=东西走向。
【四向拼图】
[0度格-左上·北]
台在画面前方。长边从画面左铺到画面右。
[90度格-右上·东]
台在画面侧面。长边从靠近镜头铺到远离镜头。
[180度格-左下·南]
台在画面后方。长边从画面左铺到画面右。
[270度格-右下·西]
台在另一侧。长边从靠近镜头铺到远离镜头。
"""

REVISED_MAIN = MAIN_PROMPT.replace("台在画面前方。", "台贴在画面前方。")

CROP_PROMPT = (
    "所属主环境=厨房。angle_key=厨房|90。"
    "请严格要求按对应主环境「厨房」四向拼图参考图，截取并放大其中对应的明确宫格位置（右上90度格），"
    "只切割，不要改画。"
)


class Dummy:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.type = kwargs.get("type", "environment")
        self.name = kwargs.get("name", "厨房")
        self.name_en = kwargs.get("name_en", "")
        self.generation_prompt_cn = kwargs.get("prompt", "")
        self.description = kwargs.get("description", "")
        self.custom_attributes = dict(kwargs.get("attrs") or {})
        self.project_id = 1
        self.episode_id = 1


def test_parse_fenced_consistency_json():
    payload = parse_consistency_payload(
        '```json\n{"consistent": false, "summary": "长边反了", "revised_prompt": "全文", "revised_main_prompt": null}\n```'
    )
    assert payload["consistent"] is False
    assert payload["summary"] == "长边反了"
    assert payload["revised_prompt"] == "全文"
    assert payload["revised_main_prompt"] is None
    assert payload["image_edit_instruction"] is None


def test_consistent_result_does_not_write():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {"consistent": True, "summary": "一致", "revised_prompt": "不要写", "revised_main_prompt": "也不要写"},
    )
    assert plan["consistent"] is True
    assert plan["writes"] == []
    assert plan["kind"] == "main"


def test_main_revision_keeps_quad_contract():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {"consistent": False, "summary": "前方位置不对", "revised_prompt": REVISED_MAIN},
    )
    fields = {(item["entity_id"], item["field"]) for item in plan["writes"]}
    assert (7, "generation_prompt_cn") in fields
    assert (7, "last_submitted_image_prompt") in fields
    assert plan["updated_targets"] == ["四向拼图"]
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert written.startswith("【六面一次】")
    assert "竖边=东西走向。" in written
    assert "台贴在画面前方。" in written
    assert plan["consistent"] is False


def test_main_revision_keeps_opening_when_model_rewrites_it():
    entity = Dummy(id=7, prompt=MAIN_PROMPT, description="主环境描述保持不动")
    rewritten = MAIN_PROMPT.replace("竖边=东西走向。", "竖边=南北走向。").replace(
        "台在画面前方。", "台贴在画面前方。"
    )
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {"consistent": False, "summary": "开篇不该被改", "revised_prompt": rewritten},
    )
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert "竖边=东西走向。" in written
    assert "竖边=南北走向。" not in written
    assert "台贴在画面前方。" in written
    apply_consistency_writes(
        {7: entity},
        [item for item in plan["writes"] if item["field"] == "generation_prompt_cn"],
    )
    assert entity.description == "主环境描述保持不动"
    assert entity.generation_prompt_cn == written


def test_main_revision_restores_dropped_grid():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    broken = REVISED_MAIN.replace("[270度格-右下·西]\n台在另一侧。长边从靠近镜头铺到远离镜头。\n", "")
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {"consistent": False, "summary": "缺格", "revised_prompt": broken},
    )
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert "台贴在画面前方。" in written
    assert "[270度格-右下·西]" in written
    assert "台在另一侧。" in written
    assert "竖边=东西走向。" in written


def test_broken_grid_rewrite_keeps_image_edit_instruction():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    instruction = "改0度格的台。现在不在画面前方。改成贴在画面前方。只改这一格里点名的这一处。"
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {
            "consistent": False,
            "summary": "0度格图片里的台不在画面前方。",
            "revised_prompt": "【六面一次】\n占地=2.4×0.9米。竖边=东西走向。\n没有格子。",
            "image_edit_instruction": instruction,
        },
    )
    assert plan["writes"] == []
    assert plan["consistent"] is False
    assert plan["image_edit_instruction"].startswith("改左上格的台")
    picture_only = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {
            "consistent": False,
            "summary": "图片里的台不在画面前方。",
            "revised_prompt": None,
            "image_edit_instruction": instruction,
        },
    )
    assert picture_only["writes"] == []
    assert picture_only["image_edit_instruction"].startswith("改左上格的台")


def test_main_revision_rejects_rewrite_without_grids():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    try:
        plan_consistency_writes(
            entity,
            entity,
            MAIN_PROMPT,
            {
                "consistent": False,
                "summary": "缺格",
                "revised_prompt": "【六面一次】\n占地=2.4×0.9米。竖边=东西走向。\n没有格子。",
            },
        )
    except ConsistencyApplyError as exc:
        assert "宫格" in str(exc)
    else:
        raise AssertionError("rewrite without grids should be rejected")


def test_main_revision_accepts_partial_cells_and_title_variants():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    partial = (
        "【0度格-左上·北】\n"
        "台贴在画面前方。长边从画面左铺到画面右。\n"
        "［90度格·右上·东］\n"
        "台在画面侧面。长边从靠近镜头铺到远离镜头。\n"
    )
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {"consistent": False, "summary": "只改了两格", "revised_prompt": partial},
    )
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert written.startswith("【六面一次】")
    assert "【四向拼图】" in written
    assert "[0度格-左上" in written
    assert "[90度格-右上" in written
    assert "[180度格-左下·南]" in written
    assert "[270度格-右下·西]" in written
    assert "台贴在画面前方。" in written
    assert "竖边=东西走向。" in written


def test_opening_without_six_face_heading_can_still_update_grids():
    prompt = MAIN_PROMPT.replace("【六面一次】", "【定位】", 1)
    entity = Dummy(id=7, prompt=prompt)
    revised = prompt.replace("台在画面前方。", "台贴在画面前方。")
    plan = plan_consistency_writes(
        entity,
        entity,
        prompt,
        {"consistent": False, "summary": "前方位置不对", "revised_prompt": revised},
    )
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert written.startswith("【定位】")
    assert "台贴在画面前方。" in written
    assert "[270度格-右下" in written


def test_cell_check_rewrites_one_grid_and_fills_derived_prompt():
    derived = Dummy(
        id=9,
        name="90度厨房",
        prompt="",
        attrs={"derived_kind": "first_cut", "main_environment": "厨房", "view_angle_from_main": 90},
    )
    main = Dummy(id=3, name="厨房", prompt=MAIN_PROMPT)
    assert classify_checked_prompt(derived, "") == "cell"
    plan = plan_consistency_writes(
        derived,
        main,
        "",
        {
            "consistent": False,
            "summary": "望东格和开篇不一致，参考图长边也反了",
            "revised_cell": "[90度格-右上·东]\n台贴在画面侧面。长边从靠近镜头铺到远离镜头。",
            "revised_prompt": "台贴在画面侧面。长边从靠近镜头铺到远离镜头。",
            "image_edit_instruction": "改这一张图里的台。现在长边横在画面里。改成只见短头，长边从靠近镜头伸向远离镜头。",
        },
    )
    main_write = next(item["value"] for item in plan["writes"] if item["entity_id"] == 3)
    assert "台贴在画面侧面" in main_write
    assert "台在画面前方" in main_write
    assert "[270度格-右下·西]" in main_write
    derived_write = next(
        item["value"] for item in plan["writes"]
        if item["entity_id"] == 9 and item["field"] == "generation_prompt_cn"
    )
    assert derived_write == "台贴在画面侧面。长边从靠近镜头铺到远离镜头。"
    assert "不要重画整张四宫" not in plan["image_edit_instruction"]
    assert plan["updated_targets"] == ["宫格", "衍生环境提示词"]
    assert plan["consistent"] is False


def test_consistency_prompt_checks_count_facing_and_position():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    messages = build_consistency_messages(
        image_url="http://example.test/grid.png",
        entity=entity,
        main_entity=entity,
        checked_prompt=MAIN_PROMPT,
        kind="main",
    )
    system = messages[0]["content"]
    assert "个数" in system
    assert "件数核销" in system
    assert "划出名" in system
    assert "脚后划出" in system
    assert "街端" in system
    assert "禁止一头近" in system
    assert "城墙衔接" in system
    assert "贴在正面墙前" in system
    assert "正面两倍" in system
    assert "朝向" in system
    assert "位置" in system
    assert "开篇有误：" in system
    assert "没改的格子可以不写" in system
    assert "左上是0度格望北" in system
    assert "左上格、左下格、右上格、右下格" in system
    assert "image_edit_instruction" in system
    assert "改图指令" in system
    assert "只改这一格里点名的这一处" in system
    assert "不要重画整张四宫" in system
    assert "用户补充" in system
    user = messages[1]["content"][0]["text"]
    assert "主体个数、件数核销、朝向、位置" in user
    assert "没改的格子可以不写" in user
    assert "按左上格、左下格、右上格、右下格描述要改的宫格" in user
    assert "用户补充，这次要特别处理" not in user
    noted = build_consistency_messages(
        image_url="http://example.test/grid.png",
        entity=entity,
        main_entity=entity,
        checked_prompt=MAIN_PROMPT,
        kind="main",
        note="90度格城墙接到城门楼",
    )
    noted_user = noted[1]["content"][0]["text"]
    assert "用户补充，这次要特别处理" in noted_user
    assert "90度格城墙接到城门楼" in noted_user
    assert messages[1]["content"][1]["image_url"]["url"] == "http://example.test/grid.png"


def test_derived_consistency_message_includes_opening_and_cell():
    opening = (
        "【六面一次】\n上=天花。\n"
        "【北壁】\n别名=窗。\n"
        "【东壁】\n别名=门。\n"
        "【南壁】\n别名=柜。\n"
        "【西壁】\n别名=镜。\n"
        "【中区】\n桌。\n"
    )
    main = Dummy(
        id=3,
        name="厨房",
        prompt=MAIN_PROMPT,
        description=opening,
        attrs={"main_environment_opening": opening},
    )
    derived = Dummy(
        id=9,
        name="90度厨房",
        prompt="",
        attrs={"derived_kind": "first_cut", "view_angle_from_main": 90},
    )
    messages = build_consistency_messages(
        image_url="http://example.test/crop.png",
        entity=derived,
        main_entity=main,
        checked_prompt="",
        kind="cell",
    )
    user = messages[1]["content"][0]["text"]
    assert "开篇可见五壁" in user
    assert "正面（东壁）" in user
    assert "别名=门。" in user
    assert "左侧面（北壁）" in user
    assert "别名=窗。" in user
    assert "右侧面（南壁）" in user
    assert "中部（中区）" in user
    assert "上：上=天花。" in user
    assert "别名=镜。" not in user
    assert "主环境完整提示词" not in user
    assert "对应宫格=90度格：" in user
    assert "台在画面侧面。" in user
    assert "两件核对" in messages[0]["content"]


def test_derived_main_angle_injects_source_walls_cell_and_delta():
    opening = (
        "【六面一次】\n上=天花。\n"
        "【北壁】\n别名=窗。\n"
        "【东壁】\n别名=门。\n"
        "【南壁】\n别名=柜。\n"
        "【西壁】\n别名=镜。\n"
        "【中区】\n桌。\n"
    )
    source = Dummy(
        id=3,
        name="天穹顶层办公室",
        prompt=MAIN_PROMPT,
        description=opening,
        attrs={"main_environment_opening": opening},
    )
    derived_main = Dummy(
        id=8,
        name="天穹顶层办公室_破损",
        prompt=(
            "衍生主环境=天穹顶层办公室_破损。状态Delta=幕墙破口。\n"
            "【四向拼图】\n"
            "[90度格-右上·东]\n正面：破口幕墙。\n"
        ),
        attrs={"derived_kind": "derived_main", "state_delta": "幕墙破口"},
    )
    angle = Dummy(
        id=9,
        name="90度天穹顶层办公室_破损",
        prompt="",
        attrs={"derived_kind": "first_cut", "view_angle_from_main": 90, "derived_from_state": True},
    )
    messages = build_consistency_messages(
        image_url="http://example.test/crop.png",
        entity=angle,
        main_entity=derived_main,
        checked_prompt="",
        kind="cell",
        depended_entity=source,
    )
    user = messages[1]["content"][0]["text"]
    assert "被依赖主环境开篇可见五壁" in user
    assert "正面（东壁）" in user
    assert "别名=门。" in user
    assert "别名=镜。" not in user
    assert "对应宫格=90度格：" in user
    assert "正面：破口幕墙。" in user
    assert "台在画面侧面。" not in user
    assert "衍生Delta：" in user
    assert "幕墙破口" in user
    assert "被依赖主环境提示词" not in user
    assert "主环境完整提示词" not in user
    assert "revised_cell 必须为 null" in messages[0]["content"]


def test_piece_count_ledger_blocks_a_consistent_verdict():
    quad = """【四向拼图】
[0度格-左上·北]
中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。
[90度格-右上·东]
中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。
[180度格-左下·南]
中部：件数=0。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=0开篇=2划出=2改入=0｜上点名=0开篇=0划出=0。
[270度格-右下·西]
中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。
"""
    issues = audit_piece_count_reconciliation(quad)
    assert any("划出名" in item for item in issues)
    assert any("180度格中部少了" in item for item in issues)
    entity = Dummy(id=7, prompt=quad)
    plan = plan_consistency_writes(
        entity,
        entity,
        quad,
        {"consistent": True, "summary": "看起来一致", "revised_prompt": None},
    )
    assert plan["consistent"] is False
    assert plan["writes"] == []
    assert plan["summary"].startswith("件数核销未通过")
    assert any("四格中部件数不一致" in item for item in issues)


def _passing_piece_count_quad() -> str:
    cell = (
        "中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。\n"
        "件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜"
        "右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。\n"
    )
    return (
        "【四向拼图】\n"
        "[0度格-左上·北]\n" + cell
        + "[90度格-右上·东]\n" + cell
        + "[180度格-左下·南]\n" + cell
        + "[270度格-右下·西]\n" + cell
    )


def test_piece_count_uses_the_returned_grid_not_the_stored_failure():
    failing = """【四向拼图】
[0度格-左上·北]
中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。
[90度格-右上·东]
中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。
[180度格-左下·南]
中部：件数=0。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=0开篇=2划出=2改入=0｜上点名=0开篇=0划出=0。
[270度格-右下·西]
中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。
"""
    passing = _passing_piece_count_quad()
    assert audit_piece_count_reconciliation(passing) == []
    entity = Dummy(id=7, prompt=failing)
    plan = plan_consistency_writes(
        entity,
        entity,
        failing,
        {
            "consistent": False,
            "summary": "核销通过",
            "revised_prompt": passing,
            "revised_main_prompt": failing,
        },
    )
    assert not plan["summary"].startswith("件数核销未通过")
    assert plan["summary"] == "核销通过"
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert "中部：件数=0" not in written
    assert written.count("中部点名=2开篇=2划出=0改入=0") == 4


def test_partial_returned_cell_is_merged_before_piece_count_audit():
    failing = """【四向拼图】
[0度格-左上·北]
中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。
[90度格-右上·东]
中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。
[180度格-左下·南]
中部：件数=0。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=0开篇=2划出=2改入=0｜上点名=0开篇=0划出=0。
[270度格-右下·西]
中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。
件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。
"""
    fixed_cell = (
        "[180度格-左下·南]\n"
        "中部：件数=2。[@公案]（M-001）。[@主椅]（M-002）。\n"
        "件数核销：正面点名=0开篇=0划出=0｜左侧面点名=0开篇=0划出=0｜"
        "右侧面点名=0开篇=0划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=0开篇=0划出=0。\n"
    )
    entity = Dummy(id=7, prompt=failing)
    plan = plan_consistency_writes(
        entity,
        entity,
        failing,
        {"consistent": False, "summary": "180度格已补上", "revised_prompt": fixed_cell},
    )
    assert not plan["summary"].startswith("件数核销未通过")
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert "中部：件数=0" not in written
    assert "[0度格-左上" in written
    assert "[270度格-右下" in written


def test_center_count_accepts_foot_depth_strike_when_named():
    quad = """【四向拼图】
[0度格-左上·北]
中部：件数=1。[@地毯]（F-001）。[@书桌]（M-001）在镜头脚后方，镜后整包不入画。
件数核销：正面点名=0开篇=0划出=0划出名=无｜左侧面点名=0开篇=0划出=0划出名=无｜右侧面点名=0开篇=0划出=0划出名=无｜中部点名=1开篇=2划出=1改入=0划出名=[@书桌]（M-001）｜上点名=0开篇=0划出=0划出名=无。
[90度格-右上·东]
中部：件数=2。[@地毯]（F-001）。[@书桌]（M-001）。
件数核销：正面点名=0开篇=0划出=0划出名=无｜左侧面点名=0开篇=0划出=0划出名=无｜右侧面点名=0开篇=0划出=0划出名=无｜中部点名=2开篇=2划出=0改入=0划出名=无｜上点名=0开篇=0划出=0划出名=无。
[180度格-左下·南]
中部：件数=2。[@地毯]（F-001）。[@书桌]（M-001）。
件数核销：正面点名=0开篇=0划出=0划出名=无｜左侧面点名=0开篇=0划出=0划出名=无｜右侧面点名=0开篇=0划出=0划出名=无｜中部点名=2开篇=2划出=0改入=0划出名=无｜上点名=0开篇=0划出=0划出名=无。
[270度格-右下·西]
中部：件数=2。[@地毯]（F-001）。[@书桌]（M-001）。
件数核销：正面点名=0开篇=0划出=0划出名=无｜左侧面点名=0开篇=0划出=0划出名=无｜右侧面点名=0开篇=0划出=0划出名=无｜中部点名=2开篇=2划出=0改入=0划出名=无｜上点名=0开篇=0划出=0划出名=无。
"""
    issues = audit_piece_count_reconciliation(quad)
    assert not any("0度格中部少了M-001" in item for item in issues)
    assert not any("四格中部件数不一致" in item for item in issues)


def test_cross_face_joint_is_not_another_subject():
    quad = """【四向拼图】
[0度格-左上·北]
正面：件数=2。远处那一整面是[@铅墙]（N-001）。[@铅门]（N-002）门洞开在[@铅墙]（N-001）上。顶接到[@穹顶]（C-001）。
左侧面：件数=2。[@钢壁]（E-001）。[@闸门]（E-002）开在[@钢壁]（E-001）上。顶接到[@穹顶]（C-001）。
右侧面：件数=2。[@护墙]（W-001）。[@配电柜]（W-002）贴在[@护墙]（W-001）的墙皮上。顶接到[@穹顶]（C-001）。
中部：件数=2。[@地坪]（F-001）。[@中枢台]（M-001）。
上：件数=1。[@穹顶]（C-001）。梁接到[@铅墙]（N-001）。
件数核销：正面点名=2开篇=2划出=0｜左侧面点名=2开篇=2划出=0｜右侧面点名=2开篇=2划出=0｜中部点名=2开篇=2划出=0改入=0｜上点名=1开篇=1划出=0。
"""
    issues = audit_piece_count_reconciliation(quad)
    assert not any("正文点名" in item or "正文是" in item for item in issues)


def test_extra_subject_on_a_face_is_still_reported_once():
    quad = """【四向拼图】
[0度格-左上·北]
正面：件数=2。远处那一整面是[@铅墙]（N-001）。[@铅门]（N-002）。[@警报灯]（C-002）。顶接到[@穹顶]（C-001）。
上：件数=1。[@穹顶]（C-001）。
中部：件数=1。[@地坪]（F-001）。
件数核销：正面点名=2开篇=2划出=0｜左侧面点名=0开篇=0划出=0｜右侧面点名=0开篇=0划出=0｜中部点名=1开篇=1划出=0改入=0｜上点名=1开篇=1划出=0。
"""
    issues = audit_piece_count_reconciliation(quad)
    assert issues.count("0度格正面件数=2，正文点名3件。") == 1
    assert not any("0度格正面点名=" in item for item in issues)
    assert not any("上件数" in item for item in issues)


def test_center_moved_in_requires_a_wall_strike():
    quad = """【四向拼图】
[0度格-左上·北]
中部：件数=2。[@地毯]（F-001）。[@机组]（M-001）。
件数核销：正面点名=0开篇=0划出=0划出名=无｜左侧面点名=0开篇=0划出=0划出名=无｜右侧面点名=0开篇=0划出=0划出名=无｜中部点名=2开篇=1划出=0改入=1划出名=无｜上点名=0开篇=0划出=0划出名=无。
[90度格-右上·东]
中部：件数=2。[@地毯]（F-001）。[@机组]（M-001）。
件数核销：正面点名=0开篇=0划出=0划出名=无｜左侧面点名=0开篇=0划出=0划出名=无｜右侧面点名=0开篇=0划出=0划出名=无｜中部点名=2开篇=2划出=0改入=0划出名=无｜上点名=0开篇=0划出=0划出名=无。
[180度格-左下·南]
中部：件数=2。[@地毯]（F-001）。[@机组]（M-001）。
件数核销：正面点名=0开篇=0划出=0划出名=无｜左侧面点名=0开篇=0划出=0划出名=无｜右侧面点名=0开篇=0划出=0划出名=无｜中部点名=2开篇=2划出=0改入=0划出名=无｜上点名=0开篇=0划出=0划出名=无。
[270度格-右下·西]
中部：件数=2。[@地毯]（F-001）。[@机组]（M-001）。
件数核销：正面点名=0开篇=0划出=0划出名=无｜左侧面点名=0开篇=0划出=0划出名=无｜右侧面点名=0开篇=0划出=0划出名=无｜中部点名=2开篇=2划出=0改入=0划出名=无｜上点名=0开篇=0划出=0划出名=无。
"""
    issues = audit_piece_count_reconciliation(quad)
    assert any("0度格中部改入=1，壁上没有划出" in item for item in issues)


def test_street_end_rejects_near_depth_and_short_head():
    quad = """【四向拼图】
[0度格-左上·北]
正面：[@北侧商肆]（N-002）。中心在画布原点的画面右15.0米。从画面左铺到画面右。
左侧面：[@出入石坊]（W-001）。从靠近镜头伸向远离镜头，一头近、一头远。
中部：[@青石地面]（F-001）。从画面左铺到画面右。
[90度格-右上·东]
正面：远处没有实墙。[@酒肆露台]（E-001）。
中部：本格沿长侧看[@青石地面]（F-001），近端是短头。
左侧面：[@北侧商肆]（N-002）。从靠近镜头伸向远离镜头，一头近、一头远。
[180度格-左下·南]
中部：[@青石地面]（F-001）。从画面左铺到画面右。
[270度格-右下·西]
正面：[@出入石坊]（W-001）。中心在画布原点的左右对齐。左端和右端离镜头一样远。
中部：本格沿长侧看[@青石地面]（F-001）。
"""
    issues = audit_street_end_phrases(quad)
    assert any("0度格左侧面把街端W-001写成一头近" in item for item in issues)
    assert any("0度格正面N-002盖住长街" in item for item in issues)
    assert any("90度格写了短头" in item for item in issues)
    assert any("90度格写了没有实墙" in item for item in issues)
    entity = Dummy(id=11, prompt=quad)
    plan = plan_consistency_writes(
        entity,
        entity,
        quad,
        {"consistent": True, "summary": "一致", "revised_prompt": quad, "revised_main_prompt": None},
    )
    assert plan["consistent"] is False
    assert plan["writes"] == []
    assert plan["summary"].startswith("长街两端未通过")


def test_invisible_side_stops_a_full_width_wall():
    quad = """[90度格-右上·东]
正面：[@夯土高耸城墙]（E-001）。从画面左铺到画面右。[@送行木牌坊]（E-002）。贴在正面墙前。
左侧面：[@重檐城门楼]（N-001）。一头近、一头远。
右侧面：不可见。
"""
    issues = audit_wall_corner_span(quad)
    assert any("贴在墙前" in item for item in issues)
    assert any("右侧面不可见" in item for item in issues)
    room = """[0度格-左上·北]
正面：[@北墙]（N-001）。从画面左铺到画面右。
左侧面：[@西墙]（W-001）。一头近、一头远。
右侧面：[@东墙]（E-001）。一头近、一头远。
"""
    assert audit_wall_corner_span(room) == []
    entity = Dummy(id=12, prompt=quad)
    plan = plan_consistency_writes(
        entity,
        entity,
        quad,
        {"consistent": True, "summary": "一致", "revised_prompt": quad, "revised_main_prompt": None},
    )
    assert plan["consistent"] is False
    assert plan["writes"] == []
    assert plan["summary"].startswith("城墙衔接未通过")
    street = """[0度格-左上·北]
正面：[@北侧商肆]（N-002）。远离镜头15米。从画面左铺到画面右。
左侧面：不可见。
右侧面：不可见。
[90度格-右上·东]
中部：本格沿长侧看[@青石地面]（F-001）。
正面：[@出入石坊]（W-001）。
"""
    assert audit_wall_corner_span(street) == []


def test_front_double_drops_equal_far_ends():
    quad = """[0度格-左上·北]
正面：[@北侧商肆]（N-002）。中心在画布原点的左右对齐、远离镜头15米。从画面左铺到画面右。
左侧面：[@出入石坊]（W-001）。中心在画布原点的画面左50米、纵深对齐0米。
右侧面：[@酒肆露台]（E-001）。中心在画布原点的画面右50米、纵深对齐0米。
"""
    issues = audit_front_double(quad)
    assert any("左侧面W-001" in item for item in issues)
    assert any("右侧面E-001" in item for item in issues)
    near = quad.replace("画面左50米", "画面左8米").replace("画面右50米", "画面右8米")
    assert audit_front_double(near) == []
    edge = quad.replace("画面左50米", "画面左30米").replace("画面右50米", "画面右30米")
    assert audit_front_double(edge) == []
    entity = Dummy(id=13, prompt=quad)
    plan = plan_consistency_writes(
        entity,
        entity,
        quad,
        {"consistent": True, "summary": "一致", "revised_prompt": quad, "revised_main_prompt": None},
    )
    assert plan["consistent"] is False
    assert plan["writes"] == []
    assert plan["summary"].startswith("正面两倍未通过")
    assert plan["image_edit_instruction"] is None
    blocked = plan_consistency_writes(
        entity,
        entity,
        quad,
        {
            "consistent": True,
            "summary": "四向正文与开篇一致。图片中270度格的驾驶座朝向错误，180度格的客舱座椅朝向错误。",
            "revised_prompt": None,
            "image_edit_instruction": "改270度格的驾驶座。现在只见坐垫朝向镜头。改成椅面朝画面右。",
        },
    )
    assert blocked["image_edit_instruction"].startswith("改右下格的驾驶座")
    assert "只改这一格里点名的这一处" in blocked["image_edit_instruction"]
    assert "四向正文与开篇一致" not in blocked["summary"]
    assert "这次不改图" not in blocked["summary"]
    assert "图片仍按指令修改" in blocked["summary"]
    assert "180度格的客舱座椅" in blocked["summary"]
    assert "左侧面W-001" in blocked["summary"]
    reported = plan_consistency_writes(
        entity,
        entity,
        quad,
        {
            "consistent": True,
            "summary": "四向正文与开篇一致。右上格图片中高背总裁转椅位置与朝向有误。",
            "revised_prompt": None,
            "revised_main_prompt": None,
            "image_edit_instruction": (
                "改右上格的高背总裁转椅。现在位于黑曜石大案右侧且椅面朝画面左。"
                "改成位于黑曜石大案左侧且椅面朝画面右。"
            ),
        },
    )
    assert reported["image_edit_instruction"].startswith("改右上格的高背总裁转椅")
    assert "椅面朝画面右" in reported["image_edit_instruction"]
    assert "这次不改图" not in reported["summary"]


def test_image_edit_instruction_survives_when_prompts_stay():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    instruction = "把左上0度格的台改到画面前方，其余格子保持不动。"
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {
            "consistent": True,
            "summary": "0度格图片里的台不在画面前方。",
            "revised_prompt": None,
            "revised_main_prompt": None,
            "image_edit_instruction": instruction,
        },
    )
    assert plan["consistent"] is True
    assert plan["writes"] == []
    assert plan["image_edit_instruction"].startswith("把左上格的台改到画面前方")
    assert "只改这一格里点名的这一处" in plan["image_edit_instruction"]
    assert "不要重画整张四宫" in plan["image_edit_instruction"]
    sealed = seal_cell_edit_instruction("改90度格的沙发，只见靠背。再改180度格的正面墙。")
    assert "改90度格的沙发" in sealed
    assert "再改180度格的正面墙" in sealed
    assert "不要改180度格" not in sealed
    assert "只改90度格、180度格里点名的这几处" in sealed
    assert seal_cell_edit_instruction("  ") is None


def test_quad_edit_describes_cells_left_column_then_right():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    instruction = (
        "改270度格的椅。现在只见坐垫朝向镜头。改成椅面朝向远离镜头。"
        "再改90度格的台。现在长边横在画面里。改成只见短头。"
        "改0度格的门。现在开在侧面。改成开在正面。"
        "再改180度格的墙。现在是另一面墙。改成这一格该有的那面墙。"
    )
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {
            "consistent": True,
            "summary": "四格图片和开篇不一致。",
            "revised_prompt": None,
            "image_edit_instruction": instruction,
        },
    )
    text = plan["image_edit_instruction"]
    assert text.find("改左上格的门") < text.find("改左下格的墙")
    assert text.find("改左下格的墙") < text.find("改右上格的台")
    assert text.find("改右上格的台") < text.find("改右下格的椅")
    assert text.find("现在开在侧面") < text.find("改左下格的墙")
    assert text.find("现在是另一面墙") < text.find("改右上格的台")
    assert text.find("现在长边横在画面里") < text.find("改右下格的椅")
    assert "只改左上格、左下格、右上格、右下格里点名的这几处" in text
    assert "不要重画整张四宫" in text


def test_consistency_check_passes_public_image_link():
    signed = "https://cdn.example.com/env/grid.png?token=abc"
    assert remote_vision_image_link(signed) == signed
    assert remote_vision_image_link("http://127.0.0.1:8000/uploads/grid.png") == ""
    assert remote_vision_image_link("/uploads/grid.png") == ""
    assert remote_vision_image_link("data:image/png;base64,aaaa") == ""


def test_unmarked_opening_rewrite_is_discarded():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    rewritten = MAIN_PROMPT.replace("竖边=东西走向。", "竖边=南北走向。").replace(
        "台在画面前方。", "台贴在画面前方。"
    )
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {"consistent": False, "summary": "图片里的台转向了", "revised_prompt": rewritten},
    )
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert "竖边=东西走向。" in written
    assert "竖边=南北走向。" not in written
    assert "台贴在画面前方。" in written


def test_marked_opening_error_keeps_opening_fix():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    rewritten = MAIN_PROMPT.replace("竖边=东西走向。", "竖边=南北走向。")
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {"consistent": False, "summary": "开篇有误：竖边和两端相反", "revised_prompt": rewritten},
    )
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert "竖边=南北走向。" in written
    assert "竖边=东西走向。" not in written
    assert "[270度格-右下" in written


def test_marked_opening_error_restores_dropped_grid():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    rewritten = MAIN_PROMPT.replace("竖边=东西走向。", "竖边=南北走向。").replace(
        "[270度格-右下·西]\n台在另一侧。长边从靠近镜头铺到远离镜头。\n", ""
    )
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {"consistent": False, "summary": "开篇有误：竖边和两端相反", "revised_prompt": rewritten},
    )
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert "竖边=南北走向。" in written
    assert "[270度格-右下·西]" in written
    assert "台在另一侧。" in written


def test_opening_error_without_an_opening_keeps_the_stored_one():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    rewritten = (
        "改了前方。\n"
        "[0度格-左上·北]\n"
        "台贴在画面前方。长边从画面左铺到画面右。\n"
    )
    plan = plan_consistency_writes(
        entity,
        entity,
        MAIN_PROMPT,
        {"consistent": False, "summary": "开篇有误：竖边和两端相反", "revised_prompt": rewritten},
    )
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert "竖边=东西走向。" in written
    assert "台贴在画面前方。" in written
    assert "[180度格-左下·南]" in written


def test_opening_fix_still_rejects_dropped_span_key():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    rewritten = MAIN_PROMPT.replace("竖边=东西走向。\n", "")
    try:
        plan_consistency_writes(
            entity,
            entity,
            MAIN_PROMPT,
            {"consistent": False, "summary": "开篇有误：竖边和两端相反", "revised_prompt": rewritten},
        )
    except ConsistencyApplyError as exc:
        assert "竖边" in str(exc)
    else:
        raise AssertionError("dropped 竖边 should be rejected")


def test_cell_check_does_not_rewrite_the_opening():
    derived = Dummy(
        id=9,
        name="90度厨房",
        prompt="",
        attrs={"derived_kind": "first_cut", "main_environment": "厨房", "view_angle_from_main": 90},
    )
    main = Dummy(id=3, name="厨房", prompt=MAIN_PROMPT)
    rewritten = MAIN_PROMPT.replace("竖边=东西走向。", "竖边=南北走向。")
    plan = plan_consistency_writes(
        derived,
        main,
        "",
        {
            "consistent": True,
            "summary": "开篇有误：竖边和两端相反",
            "revised_prompt": None,
            "revised_main_prompt": rewritten,
        },
    )
    assert not any(item["entity_id"] == 3 for item in plan["writes"])
    filled = next(item["value"] for item in plan["writes"] if item["entity_id"] == 9 and item["field"] == "generation_prompt_cn")
    assert "台在画面侧面" in filled
    assert "竖边=南北走向" not in filled
    pending = Dummy(
        id=9,
        name="90度厨房",
        prompt="待生成",
        attrs={"derived_kind": "first_cut", "main_environment": "厨房", "view_angle_from_main": 90},
    )
    pending_plan = plan_consistency_writes(
        pending,
        main,
        "待生成",
        {"consistent": True, "summary": "这一格和参考图都与开篇可见壁一致。", "revised_prompt": None},
    )
    pending_filled = next(item["value"] for item in pending_plan["writes"] if item["field"] == "generation_prompt_cn")
    assert pending_filled != "待生成"
    assert "台在画面侧面" in pending_filled


def test_regen_updates_derived_prompt_only():
    derived = Dummy(
        id=9,
        name="90度厨房",
        prompt=CROP_PROMPT,
        attrs={
            "derived_kind": "first_cut",
            "main_environment": "厨房",
            "grid_regen_prompt": "按90度格修正这张16:9。长边从靠近镜头铺到远离镜头。",
            "last_submitted_image_prompt_kind": "regen",
        },
    )
    main = Dummy(id=3, name="厨房", prompt=MAIN_PROMPT)
    checked = derived.custom_attributes["grid_regen_prompt"]
    revised = "按90度格修正这张16:9。长边从画面左铺到画面右。"
    plan = plan_consistency_writes(
        derived,
        main,
        checked,
        {
            "consistent": False,
            "summary": "长边轴反了",
            "revised_prompt": revised,
            "revised_main_prompt": REVISED_MAIN,
        },
    )
    by_field = {(item["entity_id"], item["field"]): item["value"] for item in plan["writes"]}
    assert by_field[(9, "grid_regen_prompt")] == revised
    assert by_field[(9, "last_submitted_image_prompt")] == revised
    assert (3, "generation_prompt_cn") not in by_field
    assert plan["updated_targets"] == ["重生修正提示词"]
    assert main.generation_prompt_cn == MAIN_PROMPT
    assert derived.generation_prompt_cn == CROP_PROMPT


def test_regen_ignores_opening_fix_even_when_marked():
    derived = Dummy(
        id=9,
        name="90度厨房",
        prompt=CROP_PROMPT,
        attrs={
            "derived_kind": "first_cut",
            "main_environment": "厨房",
            "grid_regen_prompt": "按90度格修正这张16:9。长边从靠近镜头铺到远离镜头。",
            "last_submitted_image_prompt_kind": "regen",
        },
    )
    main = Dummy(id=3, name="厨房", prompt=MAIN_PROMPT)
    revised = "按90度格修正这张16:9。长边从画面左铺到画面右。"
    plan = plan_consistency_writes(
        derived,
        main,
        derived.custom_attributes["grid_regen_prompt"],
        {
            "consistent": False,
            "summary": "开篇有误：竖边和两端相反",
            "revised_prompt": revised,
            "revised_main_prompt": MAIN_PROMPT.replace("竖边=东西走向。", "竖边=南北走向。"),
        },
    )
    assert all(item["entity_id"] == 9 for item in plan["writes"])
    assert main.generation_prompt_cn == MAIN_PROMPT


def test_derived_main_consistency_injects_source_prompt_and_delta():
    source = Dummy(id=3, name="天穹顶层办公室", prompt=MAIN_PROMPT)
    derived_main = Dummy(
        id=8,
        name="天穹顶层办公室_破损",
        prompt="衍生主环境=天穹顶层办公室_破损。被依赖主环境=天穹顶层办公室。状态Delta=幕墙破口。",
        attrs={
            "derived_kind": "derived_main",
            "source_main_environment": "天穹顶层办公室",
            "main_environment": "天穹顶层办公室",
            "state_delta": "幕墙破口",
        },
    )
    assert classify_checked_prompt(derived_main, derived_main.generation_prompt_cn) == "derived_main"
    messages = build_consistency_messages(
        image_url="https://cdn.example/derived-main.jpg",
        entity=derived_main,
        main_entity=source,
        checked_prompt=derived_main.generation_prompt_cn,
        kind="derived_main",
    )
    user_text = messages[1]["content"][0]["text"]
    assert "被依赖主环境提示词" in user_text
    assert "台在画面前方" in user_text
    assert "衍生Delta" in user_text
    assert "幕墙破口" in user_text
    assert "一起改" in messages[0]["content"]
    assert "左上格、左下格、右上格、右下格" in messages[0]["content"]
    plan = plan_consistency_writes(
        derived_main,
        source,
        derived_main.generation_prompt_cn,
        {
            "consistent": False,
            "summary": "只有一格破了",
            "revised_prompt": None,
            "image_edit_instruction": "幕墙破口在四格里都要看见。",
        },
    )
    assert plan["kind"] == "derived_main"
    assert plan["writes"] == []
    assert "一起改" in plan["image_edit_instruction"]
    assert "不要只改一格" in plan["image_edit_instruction"]
    assert source.generation_prompt_cn == MAIN_PROMPT
    ordered = plan_consistency_writes(
        derived_main,
        source,
        derived_main.generation_prompt_cn,
        {
            "consistent": False,
            "summary": "两格都要补破口",
            "revised_prompt": None,
            "image_edit_instruction": "改右下格的幕墙裂开。改左上格的幕墙裂开。",
        },
    )
    edited = ordered["image_edit_instruction"]
    assert edited.find("改左上格的幕墙") < edited.find("改右下格的幕墙")
    assert "一起改" in edited
    assert "不要只改一格" in edited
