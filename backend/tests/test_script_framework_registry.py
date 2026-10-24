# -*- coding: utf-8 -*-
from app.services.prompt_resolve import _resolve_prompt_text
from app.services.story_generator_llm import (
    apply_registry_fields_from_llm,
    registry_fields_needing_fill,
)


def test_chinese_keys_fill_the_five_framework_fields():
    normalized = apply_registry_fields_from_llm(
        {key: "" for key in (
            "plot_background",
            "story_lines",
            "time_nodes",
            "professional_domains",
            "places_and_props",
        )},
        {
            "剧情背景": {
                "公开处境": "林一还想保住留任",
                "关系前史": "周薇经手过她的工牌",
                "此刻为何非做不可": "审计只留二十四小时",
            },
            "故事线": {"线A": "林一留证", "线B": "周薇收牌"},
            "时间节点": {"季节": "秋", "昼夜": "日", "气候": "阴"},
            "专业领域": {"领域": "无"},
            "场景与道具": [
                {"名": "星澜开放工位区", "EN": "Starlan Open Cubicles", "功能": "晨会看见工牌", "准入": "开放"},
                {"名": "星澜总裁电梯间", "功能": "误刷看见解雇信", "准入": "受限"},
                {"道具": "林一的工牌", "功能": "开门并留下审计"},
            ],
        },
    )
    assert normalized["plot_background"].startswith("剧情背景:")
    assert "林一还想保住留任" in normalized["plot_background"]
    assert "周薇经手过她的工牌" in normalized["plot_background"]
    assert normalized["story_lines"] == "线A=林一留证｜线B=周薇收牌"
    assert "季节=秋" in normalized["time_nodes"]
    assert "昼夜=日" in normalized["time_nodes"]
    assert "气候=阴" in normalized["time_nodes"]
    assert normalized["professional_domains"] == "领域=无｜依据=本剧选择不依赖行业规程"
    assert "星澜开放工位区 (Starlan Open Cubicles)｜功能=晨会看见工牌｜准入=开放" in normalized["places_and_props"]
    assert "星澜总裁电梯间｜功能=误刷看见解雇信｜准入=受限" in normalized["places_and_props"]
    assert "道具｜林一的工牌｜功能=开门并留下审计" in normalized["places_and_props"]
    assert registry_fields_needing_fill(normalized) == []


def test_headed_blob_and_nested_registry_are_split_back():
    blob = (
        "世界背景: WB01｜职级决定能进哪扇门。\n"
        "剧情背景: PB01｜留任已经写在公告上｜手段=动作｜禁提前=信上的名字\n"
        "故事线: 线A=留下照片｜线B=勒令交牌\n"
        "时间节点: 开篇｜式=相对｜季节=秋｜昼夜=日｜气候=阴｜说明=故事当日\n"
        "专业领域: 领域=法律｜触因=要留证｜规程=不删审计｜错法=当场删掉\n"
        "场景与道具: 星澜开放工位区｜功能=晨会｜准入=开放"
    )
    normalized = apply_registry_fields_from_llm({key: "" for key in (
        "plot_background", "story_lines", "time_nodes", "professional_domains", "places_and_props",
    )}, {"background": blob})
    assert normalized["plot_background"].startswith("PB01")
    assert "线A=留下照片" in normalized["story_lines"]
    assert "季节=秋" in normalized["time_nodes"]
    assert "领域=法律" in normalized["professional_domains"]
    assert "星澜开放工位区" in normalized["places_and_props"]

    nested = apply_registry_fields_from_llm(
        {"story_lines": ""},
        {"全局登记": {"故事线": "线数=1｜豁免依据=单一封闭空间"}},
    )
    assert nested["story_lines"] == "线数=1｜豁免依据=单一封闭空间"


def test_fill_context_uses_the_neighbors_not_the_last_episode():
    from app.services.story_episode_coverage import framework_context_for_fill

    def block(number: int, title: str, body: str) -> str:
        tag = f"EP{number:02d}"
        return f"[EPISODE_BLOCK_START:{tag}]\n{title}\n{body}\n[EPISODE_BLOCK_END:{tag}]"

    markdown = "\n\n".join([
        block(2, "第二集标题", "上一集全文MARKER"),
        block(4, "第四集标题", "夹在中间MARKER"),
        block(6, "第六集标题", "下一集全文MARKER"),
        block(10, "第十集标题", "最后一集全文MARKER"),
    ])
    context = framework_context_for_fill(markdown, [3, 5])
    assert "上一集全文MARKER" in context
    assert "下一集全文MARKER" in context
    assert "夹在中间MARKER" in context
    assert "最后一集全文MARKER" not in context
    assert "第十集标题" in context


def test_outline_user_prompt_injects_the_five_fields():
    from app.services.story_episode_coverage import _fill_user_prompt
    from app.services.story_generator_llm import (
        format_outline_registry_block,
        prefill_source_for_outline,
    )

    req = type("Req", (), {"story_lines": "线A=新的一线｜线B=新的二线"})()
    source = prefill_source_for_outline(
        req,
        {
            "story_generator_global_input": {
                "plot_background": "剧情背景: PB01｜公开处境已经锁好｜手段=对话｜禁提前=结局",
                "story_lines": "线A=旧｜线B=旧",
                "time_nodes": "开篇｜式=相对｜季节=夏｜昼夜=夜｜气候=暴雨雷电｜说明=首日",
                "professional_domains": "领域=战术穿梭机低空机动驾驶｜触因=围堵｜规程=侧倾｜错法=直飞",
                "places_and_props": "总裁办公室 (Executive Office)｜功能=部署｜准入=受限",
            }
        },
    )
    block = format_outline_registry_block(source)
    assert "剧情背景: PB01｜公开处境已经锁好" in block
    assert "线A=新的一线" in block
    assert "线A=旧" not in block
    assert "季节=夏" in block
    assert "领域=战术穿梭机低空机动驾驶" in block
    assert "总裁办公室 (Executive Office)" in block
    fill = _fill_user_prompt("已完成集", [2], 8, registry_block=block)
    assert "剧本框架五栏" in fill
    assert "总裁办公室 (Executive Office)" in fill
    assert "这次只补：EP02" in fill


def test_existing_english_text_is_kept_and_prompts_require_the_fields():
    kept = apply_registry_fields_from_llm(
        {"plot_background": "剧情背景: PB01｜已经写好｜手段=对话｜禁提前=结局"},
        {"剧情背景": "另一套"},
    )
    assert "已经写好" in kept["plot_background"]
    assert "另一套" not in kept["plot_background"]
    stringified = apply_registry_fields_from_llm(
        {"story_lines": "{'线A': '留证', '线B': '收牌'}"},
        {"story_lines": {"线A": "留证", "线B": "收牌"}},
    )
    assert stringified["story_lines"] == "线A=留证｜线B=收牌"
    assert registry_fields_needing_fill({"professional_domains": "无", "plot_background": ""}) == [
        "plot_background",
        "story_lines",
        "time_nodes",
        "professional_domains",
        "places_and_props",
    ]

    structure = _resolve_prompt_text("story_generator_structure_creative_input.txt")
    emotion = _resolve_prompt_text("emotion_driven_structure_prefill.txt")
    assert "These five keys are mandatory" in structure
    assert "leave the room for a later node" not in structure
    assert "The object you return must contain these keys" in structure
    assert "少一个键，这次回答无效" in emotion
    assert "地点拿不准就不写" not in emotion
    assert "永远不许空" in emotion
