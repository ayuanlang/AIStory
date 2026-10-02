# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.environment_consistency import (
    ConsistencyApplyError,
    apply_consistency_writes,
    classify_checked_prompt,
    parse_consistency_payload,
    plan_consistency_writes,
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
