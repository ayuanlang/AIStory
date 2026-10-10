# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.environment_consistency import (
    ConsistencyApplyError,
    apply_consistency_writes,
    audit_piece_count_reconciliation,
    audit_street_end_phrases,
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


def test_main_revision_rejects_dropped_grid():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    broken = REVISED_MAIN.replace("[270度格-右下·西]\n台在另一侧。长边从靠近镜头铺到远离镜头。\n", "")
    try:
        plan_consistency_writes(
            entity,
            entity,
            MAIN_PROMPT,
            {"consistent": False, "summary": "缺格", "revised_prompt": broken},
        )
    except ConsistencyApplyError as exc:
        assert "宫格" in str(exc)
    else:
        raise AssertionError("dropped grid should be rejected")


def test_crop_updates_main_prompt_only():
    derived = Dummy(
        id=9,
        name="90度厨房",
        prompt=CROP_PROMPT,
        attrs={"derived_kind": "first_cut", "main_environment": "厨房", "view_angle_from_main": 90},
    )
    main = Dummy(id=3, name="厨房", prompt=MAIN_PROMPT)
    assert classify_checked_prompt(derived, CROP_PROMPT) == "crop"
    plan = plan_consistency_writes(
        derived,
        main,
        CROP_PROMPT,
        {
            "consistent": False,
            "summary": "望东格和开篇竖边不一致",
            "revised_prompt": "这里变成了场景描写，不能写入切割提示词。",
            "revised_main_prompt": REVISED_MAIN,
        },
    )
    assert all(item["entity_id"] == 3 for item in plan["writes"])
    assert not any(item["field"] == "last_submitted_image_prompt" for item in plan["writes"])
    assert not any(item["field"] == "generation_prompt_cn" and item["entity_id"] == 9 for item in plan["writes"])
    assert derived.generation_prompt_cn == CROP_PROMPT
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert written.startswith(MAIN_PROMPT.split("【四向拼图】", 1)[0])
    assert plan["updated_targets"] == ["四向拼图"]


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
    assert "四格中部件数必须相同" in system
    assert "街端" in system
    assert "禁止一头近" in system
    assert "朝向" in system
    assert "位置" in system
    assert "开篇有误：" in system
    assert "左上是0度格望北" in system
    assert "image_edit_instruction" in system
    assert "改图指令" in system
    user = messages[1]["content"][0]["text"]
    assert "主体个数、件数核销、朝向、位置" in user
    assert messages[1]["content"][1]["image_url"]["url"] == "http://example.test/grid.png"


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


def test_center_count_rejects_desk_hidden_behind_camera():
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
    assert any("0度格中部少了M-001" in item for item in issues)
    assert any("四格中部件数不一致" in item for item in issues)


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
    assert plan["image_edit_instruction"] == instruction


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


def test_marked_opening_error_still_rejects_dropped_grid():
    entity = Dummy(id=7, prompt=MAIN_PROMPT)
    rewritten = MAIN_PROMPT.replace("竖边=东西走向。", "竖边=南北走向。").replace(
        "[270度格-右下·西]\n台在另一侧。长边从靠近镜头铺到远离镜头。\n", ""
    )
    try:
        plan_consistency_writes(
            entity,
            entity,
            MAIN_PROMPT,
            {"consistent": False, "summary": "开篇有误：竖边和两端相反", "revised_prompt": rewritten},
        )
    except ConsistencyApplyError as exc:
        assert "宫格" in str(exc)
    else:
        raise AssertionError("dropped grid should be rejected")


def test_crop_marked_opening_error_keeps_opening_fix():
    derived = Dummy(
        id=9,
        name="90度厨房",
        prompt=CROP_PROMPT,
        attrs={"derived_kind": "first_cut", "main_environment": "厨房", "view_angle_from_main": 90},
    )
    main = Dummy(id=3, name="厨房", prompt=MAIN_PROMPT)
    rewritten = MAIN_PROMPT.replace("竖边=东西走向。", "竖边=南北走向。")
    plan = plan_consistency_writes(
        derived,
        main,
        CROP_PROMPT,
        {
            "consistent": False,
            "summary": "开篇有误：竖边和两端相反",
            "revised_prompt": None,
            "revised_main_prompt": rewritten,
        },
    )
    written = next(item["value"] for item in plan["writes"] if item["field"] == "generation_prompt_cn")
    assert written.startswith("【六面一次】")
    assert "竖边=南北走向。" in written
    assert all(item["entity_id"] == 3 for item in plan["writes"])


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
