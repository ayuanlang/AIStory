# -*- coding: utf-8 -*-
from app.services.promo_context import (
    apply_promo_fields_to_global_info,
    attach_promo_source_images_to_attrs,
    drop_promo_source_images_from_derived_env_attrs,
    is_derived_environment_name,
    build_promo_injection_section,
    build_promo_source_images,
    collect_promo_brief,
    enrich_rebuild_analysis,
    filter_analysis_to_selected_assets,
    format_promo_injection_body,
    format_visual_rebuild_lines,
    is_promo_project,
    match_promo_source_image_urls,
    promo_scene_split_is_valid,
    strip_visual_watermark_text,
)
from app.services.promo_planner import (
    EXISTING_MATERIAL_ANALYSIS_MARK,
    PROMO_PROJECT_TYPE,
    apply_analysis_status_to_assets,
    assets_needing_analysis,
    catalog_analysis_fields,
    merge_catalog_analysis_extra,
    serialize_promo_catalog_asset,
    slice_asset_analysis,
    backfill_existing_material,
    build_linked_story_global_info,
    build_uploaded_asset_catalog,
    empty_stage_block,
    empty_visual_backfill,
    format_existing_material_from_analysis,
    format_uploaded_asset_catalog_text,
    merge_planner_result,
    merge_single_asset_analysis,
    normalize_image_assets,
    match_enterprise_id_from_records,
    resolve_share_enterprise_id,
    selected_planner_image_assets,
    snapshot_from_catalog,
    result_to_promo_markdown,
    normalize_promo_project_global_info,
    persist_promo_project_extra_info,
    unique_flower_text_slot,
    _build_image_analysis_user_prompt,
    _build_scheme_user_prompt,
    _build_script_user_prompt,
    _promo_skill_system_prompt,
)
from app.services.shot_generation_prompts import _build_project_prompt_context


class _FakePromo:
    id = 17
    title = "品牌形象片"
    extra_info = {
        "global_info": {
            "type": "实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)",
        }
    }
    description = None


def test_is_promo_project_detects_source_and_type():
    assert is_promo_project({"source_promo_project_id": 17})
    assert is_promo_project({"type": "商业宣传片"})
    assert is_promo_project({"promo_goal_type": "即时转化（引流获客）"})
    assert not is_promo_project({"type": "仙侠", "script_title": "X"})
    assert not is_promo_project({})


def test_collect_promo_brief_does_not_mark_regular_projects():
    brief = collect_promo_brief({"script_title": "普通剧", "type": "仙侠"})
    assert brief["promo_single_scene"] is False
    assert brief["type"] == "仙侠"
    assert format_promo_injection_body(brief) == ""
    assert build_promo_injection_section(brief) == ""


def test_linked_story_global_info_persists_promo_fields():
    info = build_linked_story_global_info(
        _FakePromo(),
        planner_input={
            "enterprise_info": {
                "enterprise_name": "星河科技",
                "brand_name": "星河",
                "product_name": "星河手表",
            },
            "campaign_demand": {
                "goal_type": "企业品牌宣传（情绪种草）",
                "expect_duration": "30-60s",
                "cta": "打开官网预约",
            },
        },
        planner_result={
            "overall_scheme": {
                "one_liner": "用手腕上的光记下城市",
                "target_duration": "30-60s",
                "duration_budget": "总时长=45s",
                "main_goal_type": "企业品牌宣传（情绪种草）",
            },
            "stage_plan": {
                "hook": {"name": "吸睛", "duration": "6s", "content": "夜城航拍"},
                "empathy": {"name": "共鸣", "duration": "10s", "content": "通勤人抬头"},
                "value": {"name": "价值", "duration": "20s", "content": "手表记光"},
                "close": {"name": "收口", "duration": "9s", "content": "标与预约", "cta": "打开官网预约"},
            },
            "project_visual_backfill": {
                "Global_Style": "视觉基调=当代｜气质=精致",
                "style_mode": "当代都市",
                "tone": "都市夜色",
                "lighting": "主光质感=霓虹窗光",
                "borrowed_films": ["Apple Shot on iPhone", "Nike You Can't Stop Us"],
            },
            "script_preview": {"logline": "用手腕上的光记下城市"},
        },
    )
    assert "实拍" in str(info.get("type") or "")
    assert info["type"] != PROMO_PROJECT_TYPE
    assert info["source_promo_project_id"] == 17
    assert info["promo_single_scene"] is True
    assert info["promo_rhythm"] == "吸睛-共鸣-价值-收口"
    assert info["promo_goal_type"] == "企业品牌宣传（情绪种草）"
    assert info["promo_expect_duration"] == "30-60s"
    assert info["promo_enterprise"] == "星河科技"
    assert info["promo_cta"] == "打开官网预约"
    assert info["Global_Style"] == "视觉基调=当代｜气质=精致"
    assert info["tone"] == "都市夜色"
    assert "Apple Shot on iPhone" in info["borrowed_films"]


def test_promo_injection_and_project_context():
    brief = collect_promo_brief(
        apply_promo_fields_to_global_info(
            {"source_promo_project_id": 17},
            collect_promo_brief(
                {"source_promo_project_id": 17},
                {"campaign_demand": {"goal_type": "即时转化（引流获客）", "expect_duration": "15-30s"}},
                {
                    "overall_scheme": {"one_liner": "三秒看见效果"},
                    "stage_plan": {
                        "hook": {"name": "吸睛", "duration": "4s", "content": "痛点特写"},
                    },
                },
            ),
        )
    )
    body = format_promo_injection_body(brief)
    assert "片种=商业宣传片" in body
    assert "切场=禁止｜全剧恰好一场" in body
    assert "核心诉求=即时转化（引流获客）" in body
    assert "素材策略=" in body
    assert "新构思" in body


def test_historical_enterprise_match_uses_name_and_sole_catalog():
    enterprises = [{"id": 3, "name": "星河科技"}, {"id": 8, "name": "另一家"}]
    assert match_enterprise_id_from_records(
        enterprise_name="星河 科技",
        enterprises=enterprises,
    ) == 3
    assert match_enterprise_id_from_records(
        enterprises=[{"id": 9, "name": "独此一家"}],
    ) == 9
    assert match_enterprise_id_from_records(
        project_enterprise_id=8,
        enterprises=enterprises,
    ) == 8


def test_resolve_share_enterprise_id_reads_asset_owner():
    class _Proj:
        enterprise_id = None

    assert resolve_share_enterprise_id(_Proj(), {}, [{"owner_kind": "project", "owner_entity_id": 12, "img_url": "https://x"}]) == 12
    assert resolve_share_enterprise_id(_Proj(), {"enterprise_id": 8}, []) == 8


def test_selected_planner_assets_keep_catalog_ref_and_do_not_auto_merge():
    selected = selected_planner_image_assets(
        {
            "image_assets": [
                {
                    "image_id": "kitchen-1",
                    "img_url": "https://example.com/k.jpg",
                    "object_name": "开放式厨房",
                    "owner_kind": "enterprise",
                    "owner_entity_id": 9,
                    "catalog_asset_id": 44,
                    "image_type": "scene",
                }
            ]
        }
    )
    assert len(selected) == 1
    assert selected[0]["catalog_asset_id"] == 44
    assert selected[0]["owner_kind"] == "enterprise"
    assert selected[0]["owner_entity_id"] == 9
    assert selected[0]["image_type"] == "scene"
    assert normalize_image_assets(
        [{"object_name": "仅名字", "owner_kind": "enterprise", "id": 8}]
    ) == []
    snap = snapshot_from_catalog(
        None,
        None,
        image_assets=[],
        overlay={"image_assets": [{"object_name": "全库未选", "img_url": "https://example.com/all.jpg"}]},
    )
    assert snap["image_assets"] == []


def test_project_injection_uses_only_selected_assets():
    selected = [
        {
            "image_id": "keep-1",
            "object_name": "开放式厨房",
            "image_type": "scene",
            "img_url": "https://example.com/kitchen.jpg",
        }
    ]
    analysis = {
        "image_list": [
            {"image_id": "keep-1", "object_name": "开放式厨房", "img_url": "https://example.com/kitchen.jpg"},
            {"image_id": "skip-2", "object_name": "未选用仓库", "img_url": "https://example.com/warehouse.jpg"},
        ],
        "rebuild_subjects": [
            {"kind": "environment", "object_name": "开放式厨房", "name_for_script": "开放式厨房", "source_image_ids": ["keep-1"]},
            {"kind": "environment", "object_name": "未选用仓库", "name_for_script": "未选用仓库", "source_image_ids": ["skip-2"]},
        ],
    }
    filtered = filter_analysis_to_selected_assets(analysis, selected)
    assert [row["image_id"] for row in filtered["image_list"]] == ["keep-1"]
    assert [row["object_name"] for row in filtered["rebuild_subjects"]] == ["开放式厨房"]
    rows = build_promo_source_images(selected, analysis)
    urls = " ".join(url for row in rows for url in (row.get("urls") or []))
    assert "kitchen.jpg" in urls
    assert "warehouse.jpg" not in urls
    brief = collect_promo_brief(
        {"source_promo_project_id": 8},
        {"enterprise_info": {"image_assets": selected}},
        {"image_asset_analysis": analysis},
    )
    body = format_promo_injection_body(brief)
    assert "开放式厨房" in body
    assert "未选用仓库" not in body


def test_promo_asset_strategy_uses_uploaded_names():
    brief = collect_promo_brief(
        {"source_promo_project_id": 8},
        {
            "enterprise_info": {
                "enterprise_name": "星河",
                "image_assets": [{"object_name": "主厨", "img_url": "https://example.com/chef.jpg"}],
            },
            "campaign_demand": {"goal_type": "即时转化（引流获客）"},
        },
        {},
    )
    assert brief["promo_has_uploaded_assets"] is True
    assert "已有素材资源描述" in brief["promo_asset_strategy"]
    assert "已有素材资源描述" in format_promo_injection_body(brief)


def test_visual_rebuild_passes_into_injection():
    analysis = {
        "rebuild_subjects": [
            {
                "kind": "environment",
                "object_name": "开放式厨房",
                "rebuild_brief": "白理石岛台、胡桃木柜、暖黄吊灯",
                "space_layout": "岛台居中，北壁为窗",
                "lighting": "暖黄吊灯",
            },
            {
                "kind": "prop",
                "object_name": "主厨刀",
                "appearance": "8寸日式厨刀，木柄铆钉",
                "clothing_or_material": "碳钢刃+胡桃木柄",
                "scale_and_shape": "长刃窄身",
                "color_and_markings": "柄侧烙印未见文字",
            },
        ]
    }
    text = format_visual_rebuild_lines(analysis)
    assert "ENV:开放式厨房" in text
    assert "白理石岛台" in text
    assert "岛台居中，北壁为窗" in text
    assert "PROP:主厨刀" in text
    assert "碳钢刃+胡桃木柄" in text
    assert "8寸日式厨刀" in text


def test_visual_rebuild_merges_image_list_details():
    analysis = {
        "rebuild_subjects": [
            {
                "kind": "environment",
                "object_name": "开放式厨房",
                "rebuild_brief": "暖黄厨房",
            }
        ],
        "image_list": [
            {
                "image_id": "img-k",
                "object_name": "开放式厨房",
                "image_type": "scene",
                "user_remark": "岛台操作全过程",
                "content_desc": "岛台、吊灯与西壁木柜",
                "environment_detail": "岛台居中，北壁落地窗，西壁胡桃木柜到顶，白理石台面可见水渍",
                "prop_detail": "岛台上有8寸日式厨刀，碳钢刃胡桃木柄",
                "light_info": "暖黄吊灯为主光，窗光作辅",
                "style_desc": "纪实暖厨",
                "composition": "中景平视，岛台占中下",
                "rebuild_brief": "暖黄厨房",
            },
            {
                "image_id": "img-c",
                "object_name": "主厨",
                "image_type": "character",
                "user_remark": "出镜讲解的主厨",
                "character_detail": "中年男性，国字脸，短黑发贴鬓，肤色偏暖，白色双排扣厨服配黑围裙",
                "rebuild_brief": "一位厨师",
            },
        ],
    }
    text = format_visual_rebuild_lines(analysis)
    assert "说明=岛台操作全过程" in text
    assert "北壁落地窗" in text
    assert "白理石台面可见水渍" in text
    assert "暖黄吊灯为主光" in text
    assert "纪实暖厨" in text
    assert "CHAR:主厨" in text
    assert "出镜讲解的主厨" in text
    assert "国字脸" in text
    assert "白色双排扣厨服" in text
    brief = collect_promo_brief(
        {"source_promo_project_id": 9},
        {"enterprise_info": {"image_assets": [{"object_name": "开放式厨房", "img_url": "https://example.com/k.jpg"}]}},
        {"image_asset_analysis": analysis},
    )
    body = format_promo_injection_body(brief)
    assert "已有素材资源描述=" in body
    assert "开放式厨房" in body
    assert "逐字抄已有素材资源描述" in body
    assert "CHAR:主厨" not in body
    section = build_promo_injection_section(brief)
    assert "[商业宣传片开始]" in section
    assert "[商业宣传片结束]" in section

    ctx = _build_project_prompt_context(brief)
    text = str(ctx.get("project_context_section") or "")
    assert "[商业宣传片]" in text
    assert "全剧恰好一场" in text


def test_collect_promo_brief_prefers_fresh_analysis_over_stale_rebuild():
    stale = "- PROP:旧刀｜外形=旧描述"
    analysis = {
        "rebuild_subjects": [
            {
                "kind": "prop",
                "object_name": "主厨刀",
                "appearance": "8寸日式厨刀，木柄铆钉",
                "clothing_or_material": "碳钢刃+胡桃木柄",
                "scale_and_shape": "长刃窄身",
                "color_and_markings": "柄侧烙印未见文字",
            }
        ]
    }
    brief = collect_promo_brief(
        {
            "source_promo_project_id": 11,
            "promo_visual_rebuild": stale,
            "promo_existing_material": "【素材解析】\n综合视觉=旧厨房",
        },
        {
            "enterprise_info": {"image_assets": [{"object_name": "主厨刀", "img_url": "https://example.com/k.jpg"}]},
            "campaign_demand": {"existing_material": "工厂另有航拍未传\n\n【素材解析】\n综合视觉=暖黄厨房"},
        },
        {
            "image_asset_analysis": analysis,
            "existing_material": "工厂另有航拍未传\n\n【素材解析】\n综合视觉=暖黄厨房",
        },
    )
    assert "主厨刀" in brief["promo_visual_rebuild"]
    assert "旧刀" not in brief["promo_visual_rebuild"]
    assert "主厨刀" in brief["promo_existing_material"]
    assert "工厂另有航拍未传" in brief["promo_existing_material"]
    assert "旧厨房" not in brief["promo_existing_material"]
    body = format_promo_injection_body(brief)
    assert "主厨刀" in body
    assert "工厂另有航拍未传" in body
    assert "旧刀" not in body


def test_apply_promo_fields_overwrites_stale_material():
    updated = apply_promo_fields_to_global_info(
        {
            "source_promo_project_id": 12,
            "promo_visual_rebuild": "- PROP:旧刀｜外形=旧描述",
            "promo_existing_material": "【素材解析】\n综合视觉=旧厨房",
            "promo_asset_strategy": "无上传素材：按剧本新构思抽取 CHAR/PROP/ENV，后续补充或由AI生成，禁止因无图停抽或空剧情。",
        },
        {
            "source_promo_project_id": 12,
            "promo_visual_rebuild": "- PROP:主厨刀｜外形=8寸日式厨刀",
            "promo_existing_material": "工厂另有航拍未传\n\n【素材解析】\n综合视觉=暖黄厨房",
            "promo_asset_strategy": "有上传素材：抽取与入镜优先引用已命名素材；外形/材质/空间必须逐字抄视觉还原，供场景与道具重新生成；缺口可后续补充或AI生成。",
            "image_asset_analysis": {"rebuild_subjects": [{"kind": "prop", "object_name": "主厨刀"}]},
        },
    )
    assert "主厨刀" in updated["promo_visual_rebuild"]
    assert "旧刀" not in updated["promo_visual_rebuild"]
    assert "暖黄厨房" in updated["promo_existing_material"]
    assert "旧厨房" not in updated["promo_existing_material"]
    assert "已命名素材" in updated["promo_asset_strategy"]
    assert updated["image_asset_analysis"]["rebuild_subjects"][0]["object_name"] == "主厨刀"


def test_linked_story_global_info_refreshes_material_on_regenerate():
    info = build_linked_story_global_info(
        _FakePromo(),
        planner_input={
            "enterprise_info": {
                "enterprise_name": "星河科技",
                "image_assets": [{"object_name": "主厨刀", "img_url": "https://example.com/k.jpg"}],
            },
            "campaign_demand": {
                "goal_type": "企业品牌宣传（情绪种草）",
                "expect_duration": "30-60s",
                "existing_material": "工厂另有航拍未传\n\n【素材解析】\n综合视觉=暖黄厨房",
            },
        },
        planner_result={
            "image_asset_analysis": {
                "rebuild_subjects": [
                    {
                        "kind": "prop",
                        "object_name": "主厨刀",
                        "appearance": "8寸日式厨刀，木柄铆钉",
                        "clothing_or_material": "碳钢刃+胡桃木柄",
                    }
                ]
            },
            "existing_material": "工厂另有航拍未传\n\n【素材解析】\n综合视觉=暖黄厨房",
            "overall_scheme": {"one_liner": "用刀切开夜色", "target_duration": "30-60s"},
        },
        existing={
            "promo_visual_rebuild": "- PROP:旧刀｜外形=旧描述",
            "promo_existing_material": "【素材解析】\n综合视觉=旧厨房",
            "image_asset_analysis": {"rebuild_subjects": [{"kind": "prop", "object_name": "旧刀"}]},
        },
    )
    assert "主厨刀" in info["promo_visual_rebuild"]
    assert "旧刀" not in info["promo_visual_rebuild"]
    assert "主厨刀" in info["promo_existing_material"]
    assert "工厂另有航拍未传" in info["promo_existing_material"]
    assert info["image_asset_analysis"]["rebuild_subjects"][0]["object_name"] == "主厨刀"


def test_promo_source_images_become_dependency_refs():
    assets = [
        {
            "image_id": "img-k",
            "object_name": "开放式厨房",
            "image_type": "scene",
            "media_kind": "image",
            "img_url": "https://example.com/kitchen.jpg",
        },
        {
            "image_id": "img-k-vid",
            "object_name": "岛台操作",
            "image_type": "scene",
            "media_kind": "video",
            "img_url": "https://example.com/kitchen.mp4",
        },
        {
            "image_id": "img-p",
            "object_name": "主厨刀",
            "image_type": "prop",
            "media_kind": "image",
            "img_url": "https://example.com/knife.jpg",
        },
    ]
    analysis = {
        "rebuild_subjects": [
            {
                "kind": "environment",
                "object_name": "开放式厨房",
                "name_for_script": "开放式厨房",
                "source_image_ids": ["img-k"],
            },
            {
                "kind": "prop",
                "object_name": "主厨刀",
                "source_image_ids": ["img-p"],
            },
        ]
    }
    rows = build_promo_source_images(assets, analysis)
    assert match_promo_source_image_urls("开放式厨房", "environment", rows) == ["https://example.com/kitchen.jpg"]
    assert match_promo_source_image_urls("主厨刀", "prop", rows) == ["https://example.com/knife.jpg"]
    assert "kitchen.mp4" not in " ".join(url for row in rows for url in row.get("urls") or [])
    attrs = attach_promo_source_images_to_attrs(
        {},
        name="开放式厨房",
        entity_type="environment",
        source_images=rows,
    )
    assert attrs["source_image_urls"] == ["https://example.com/kitchen.jpg"]
    brief = collect_promo_brief(
        {"source_promo_project_id": 21},
        {"enterprise_info": {"image_assets": assets}},
        {"image_asset_analysis": analysis},
    )
    body = format_promo_injection_body(brief)
    assert "素材依赖图=" in body
    assert "ENV:开放式厨房" in body
    assert "https://example.com/kitchen.jpg" in body
    assert "PROP:主厨刀" in body
    updated = apply_promo_fields_to_global_info(
        {"source_promo_project_id": 21, "promo_source_images": []},
        brief,
    )
    assert updated["promo_source_images"][0]["urls"] == ["https://example.com/kitchen.jpg"]
    overridden = attach_promo_source_images_to_attrs(
        {
            "source_image_urls": ["https://example.com/replaced-kitchen.jpg"],
            "source_images_overridden": True,
        },
        name="开放式厨房",
        entity_type="environment",
        source_images=rows,
    )
    assert overridden["source_image_urls"] == ["https://example.com/replaced-kitchen.jpg"]
    assert overridden["source_images_overridden"] is True
    assert is_derived_environment_name("0度开放式厨房")
    assert not is_derived_environment_name("开放式厨房")
    derived_attrs = attach_promo_source_images_to_attrs(
        {},
        name="0度开放式厨房",
        entity_type="environment",
        source_images=rows,
        extra_names=["开放式厨房"],
    )
    assert "source_image_urls" not in derived_attrs
    assert not derived_attrs.get("promo_source_attached")
    stripped = drop_promo_source_images_from_derived_env_attrs(
        {
            "source_image_urls": ["https://example.com/kitchen.jpg"],
            "promo_source_attached": True,
            "main_environment": "开放式厨房",
        }
    )
    assert "source_image_urls" not in stripped
    assert not stripped.get("promo_source_attached")
    assert stripped["main_environment"] == "开放式厨房"


def test_promo_scene_split_validity():
    meta = {"source_promo_project_id": 3, "type": "商业宣传片"}
    one = "[SCENES_BLOCK_START]\n[SCENE_START:EP01_SC01]\nbody\n[SCENE_END:EP01_SC01]"
    two = one + "\n[SCENE_START:EP01_SC02]\nmore\n[SCENE_END:EP01_SC02]"
    assert promo_scene_split_is_valid(one, meta) is True
    assert promo_scene_split_is_valid(two, meta) is False
    assert promo_scene_split_is_valid(two, {"type": "仙侠"}) is True


def test_existing_material_backfills_analysis():
    analysis = {
        "global_visual_summary": "暖黄厨房、石材与木色",
        "rebuild_subjects": [
            {
                "kind": "environment",
                "object_name": "开放式厨房",
                "rebuild_brief": "白理石岛台、胡桃木柜",
                "space_layout": "岛台居中",
                "lighting": "暖黄吊灯",
            }
        ],
        "image_list": [
            {
                "object_name": "开放式厨房",
                "media_kind": "image",
                "image_type": "scene",
                "content_desc": "岛台与吊灯",
                "rebuild_brief": "白理石岛台、胡桃木柜",
                "environment_detail": "岛台居中",
            }
        ],
    }
    text = format_existing_material_from_analysis(analysis)
    assert "综合视觉=暖黄厨房、石材与木色" in text
    assert "名称=开放式厨房" in text
    assert text.count("开放式厨房") == 1
    assert "可重生主体" not in text
    assert "逐条素材" not in text
    filled = backfill_existing_material("工厂另有航拍未传", analysis)
    assert filled.startswith("工厂另有航拍未传")
    assert EXISTING_MATERIAL_ANALYSIS_MARK in filled
    assert "白理石岛台" in filled
    again = backfill_existing_material(filled, analysis)
    assert again.count(EXISTING_MATERIAL_ANALYSIS_MARK) == 1
    assert again.startswith("工厂另有航拍未传")
    replaced = backfill_existing_material(
        filled,
        {
            "global_visual_summary": "冷白展厅、金属与玻璃",
            "rebuild_subjects": [
                {
                    "kind": "environment",
                    "object_name": "品牌展厅",
                    "rebuild_brief": "冷白石材、玻璃幕墙",
                    "space_layout": "中庭挑空",
                    "lighting": "天窗冷白",
                }
            ],
        },
    )
    assert replaced.count(EXISTING_MATERIAL_ANALYSIS_MARK) == 1
    assert "冷白展厅、金属与玻璃" in replaced
    assert "品牌展厅" in replaced
    assert "开放式厨房" not in replaced
    assert replaced.startswith("工厂另有航拍未传")
    failed_only = backfill_existing_material(
        "",
        {"image_list": [{"object_name": "展厅", "media_kind": "image", "image_type": "scene", "content_desc": "识别失败或未返回描述"}]},
        [{"object_name": "展厅", "media_kind": "image", "image_type": "scene"}],
    )
    assert EXISTING_MATERIAL_ANALYSIS_MARK in failed_only
    assert "展厅" in failed_only
    assert "名称=展厅" in failed_only
    assert "类型=场景" in failed_only


def test_existing_material_matches_project_library_only():
    analysis = {
        "global_visual_summary": "厨房与未选用仓库混在一起",
        "rebuild_subjects": [
            {"kind": "environment", "object_name": "开放式厨房", "rebuild_brief": "白理石岛台", "source_image_ids": ["keep-1"]},
            {"kind": "environment", "object_name": "未选用仓库", "rebuild_brief": "铁架货垛", "source_image_ids": ["skip-2"]},
        ],
        "image_list": [
            {"image_id": "keep-1", "object_name": "开放式厨房", "image_type": "scene", "content_desc": "岛台与吊灯"},
            {"image_id": "skip-2", "object_name": "未选用仓库", "image_type": "scene", "content_desc": "铁架货垛"},
        ],
    }
    selected = [{"image_id": "keep-1", "object_name": "开放式厨房", "img_url": "https://example.com/kitchen.jpg", "image_type": "scene"}]
    text = format_existing_material_from_analysis(analysis, selected)
    assert "开放式厨房" in text
    assert text.count("开放式厨房") == 1
    assert "未选用仓库" not in text
    assert "厨房与未选用仓库混在一起" not in text
    filled = backfill_existing_material(
        "手写备注\n\n【素材解析】\n综合视觉=厨房与未选用仓库混在一起\n- 未选用仓库",
        analysis,
        selected,
    )
    assert filled.startswith("手写备注")
    assert "开放式厨房" in filled
    assert "未选用仓库" not in filled
    empty = format_existing_material_from_analysis(analysis, [])
    assert empty == ""
    brief = collect_promo_brief(
        {"source_promo_project_id": 22},
        {"enterprise_info": {"image_assets": selected}, "campaign_demand": {"existing_material": filled}},
        {"image_asset_analysis": analysis, "existing_material": filled},
    )
    assert "开放式厨房" in brief["promo_existing_material"]
    assert "未选用仓库" not in brief["promo_existing_material"]


def test_uploaded_asset_catalog_injects_metadata_into_skills():
    assets = [
        {
            "image_id": "img-1",
            "object_name": "主厨",
            "image_type": "character",
            "media_kind": "image",
            "user_remark": "出镜讲解的主厨",
            "img_url": "https://example.com/chef.jpg",
        },
        {
            "image_id": "vid-1",
            "object_name": "开放式厨房",
            "image_type": "scene",
            "media_kind": "video",
            "user_remark": "岛台操作全过程",
            "img_url": "https://example.com/kitchen.mp4",
        },
    ]
    analysis = {
        "image_list": [
            {
                "image_id": "img-1",
                "object_name": "主厨",
                "rebuild_brief": "中年男性，白色双排扣厨服",
                "character_detail": "短发，白色厨服",
            }
        ],
        "rebuild_subjects": [
            {
                "kind": "character",
                "object_name": "主厨",
                "rebuild_brief": "中年男性，白色双排扣厨服",
                "appearance": "中年男性",
                "clothing_or_material": "白色双排扣厨服",
            }
        ],
    }
    catalog = build_uploaded_asset_catalog(assets, analysis)
    assert len(catalog) == 2
    assert catalog[0]["object_name"] == "主厨"
    assert catalog[0]["image_type_label"] == "角色"
    assert catalog[0]["user_remark"] == "出镜讲解的主厨"
    assert catalog[0]["rebuild_brief"] == "中年男性，白色双排扣厨服"
    assert catalog[1]["image_type_label"] == "场景"
    assert catalog[1]["media_kind_label"] == "视频"
    text = format_uploaded_asset_catalog_text(catalog)
    assert "名称=主厨" in text
    assert "类型=角色" in text
    assert "说明=出镜讲解的主厨" in text
    assert "说明=岛台操作全过程" in text

    analysis_prompt = _build_image_analysis_user_prompt(assets, assets=assets)
    assert "名称=主厨" in analysis_prompt
    assert "说明=出镜讲解的主厨" in analysis_prompt
    assert "类型=场景" in analysis_prompt
    assert "岛台操作全过程" in analysis_prompt
    assert "禁止解析水印" in analysis_prompt

    planner_input = {
        "enterprise_info": {"image_assets": assets},
        "campaign_demand": {
            "goal_type": "即时转化（引流获客）",
            "expect_duration": "30-60s",
            "existing_material": "工厂另有航拍未传",
        },
    }
    scheme_prompt = _build_scheme_user_prompt(planner_input, analysis, [])
    assert "已有素材资源描述" in scheme_prompt
    assert "名称=主厨" in scheme_prompt
    assert "出镜讲解的主厨" in scheme_prompt
    assert "岛台操作全过程" in scheme_prompt
    assert "中年男性，白色双排扣厨服" in scheme_prompt
    assert "工厂另有航拍未传" in scheme_prompt
    assert "uploaded_asset_catalog" not in scheme_prompt
    assert "image_asset_analysis" not in scheme_prompt
    assert "visual_rebuild_for_script" not in scheme_prompt

    script_prompt = _build_script_user_prompt(
        title="试片",
        planner_input=planner_input,
        planner_result={"image_asset_analysis": analysis, "existing_material": "工厂另有航拍未传"},
    )
    assert "已有素材资源描述" in script_prompt
    assert "名称=主厨" in script_prompt
    assert "出镜讲解的主厨" in script_prompt
    assert "岛台操作全过程" in script_prompt
    assert "uploaded_asset_catalog" not in script_prompt
    assert "image_asset_analysis" not in script_prompt
    assert "visual_rebuild_for_script" not in script_prompt


def test_promo_flower_text_is_planned_and_injected():
    block = empty_stage_block("吸睛")
    assert "flower_text" in block
    spec = empty_visual_backfill()["flower_text_spec"]
    assert spec["body_size"] == "中"
    assert spec["emphasis_size"] == "大"
    assert spec["body_position"] == "画面中部"
    assert spec["emphasis_position"] == "画面中部"
    assert "script" in spec
    assert "emphasis_font" in spec
    assert spec["en_size"] == "小"
    assert "en_companion" in spec
    assert spec["product_name_layout"] == "画右竖排|画左竖排"
    assert spec["mid_display"] == "中部必须艺术化组合设计，不限于印章/古体/英文小字/颜色"
    assert spec["cut_fusion"] == "优先段末切镜或段首开镜，不与动作抢镜；可黑屏专镜；有旁白则无花字"
    assert spec["cta_hold"] == "CTA可较长停留"
    assert spec["vo_xor"] == "有旁白时不出花字，花字低于旁白，禁同步以免分心"

    merged = merge_planner_result(
        {
            "project_visual_backfill": {
                "flower_text_spec": {
                    "font": "魏碑",
                    "script": "繁",
                    "emphasis_font": "印章体",
                    "en_companion": "重点句可配英文小字",
                    "color": "浅金",
                },
            },
            "stage_plan": {
                "hook": {"name": "吸睛", "copy": "看见改变", "content": "钩子"},
                "close": {"name": "收口", "copy": "一盏灯，照见山河", "cta": "打开预约", "content": "记忆"},
            },
        }
    )
    spec = merged["project_visual_backfill"]["flower_text_spec"]
    assert spec["body_position"] == "画面中部"
    assert spec["script"] == "繁"
    assert spec["emphasis_font"] == "印章体"
    assert "字体=魏碑" in spec["spec_line"]
    assert "字形=繁" in spec["spec_line"]
    assert "强调体=印章体" in spec["spec_line"]
    assert "英级=小" in spec["spec_line"]
    assert "产品名=画右竖排|画左竖排" in spec["spec_line"]
    assert "字色=浅金" in spec["spec_line"]
    assert "位置=中" in merged["stage_plan"]["hook"]["flower_text"]
    assert "字级=中" in merged["stage_plan"]["hook"]["flower_text"]
    assert "上屏=段末切镜" in merged["stage_plan"]["hook"]["flower_text"]
    assert "停留=短" in merged["stage_plan"]["hook"]["flower_text"]
    assert "听=无" in merged["stage_plan"]["hook"]["flower_text"]
    assert "一盏灯，照见山河" in merged["stage_plan"]["close"]["flower_text"]
    assert "位置=中" in merged["stage_plan"]["close"]["flower_text"]
    assert "字级=大" in merged["stage_plan"]["close"]["flower_text"]
    assert "上屏=段末切镜" in merged["stage_plan"]["close"]["flower_text"]
    assert "停留=长" in merged["stage_plan"]["close"]["flower_text"]
    assert "听=无" in merged["stage_plan"]["close"]["flower_text"]
    assert "打开预约" not in merged["stage_plan"]["close"]["flower_text"]

    brief = collect_promo_brief({"source_promo_project_id": 9}, {}, merged)
    body = format_promo_injection_body(brief)
    assert "花字规范=" in body
    assert "花字闸=" in body
    assert "有旁白时不出花字" in body
    assert "字体=魏碑" in body
    assert "字形=繁" in body
    assert "花字=" in body
    applied = apply_promo_fields_to_global_info({"source_promo_project_id": 9}, brief)
    again = collect_promo_brief(applied)
    assert "魏碑" in again["promo_flower_text_spec"]
    assert any(_text_row.get("flower_text") for _text_row in again["promo_stage_plan"])

    scheme_sys = _promo_skill_system_prompt("promo_planner_scheme.md")
    script_sys = _promo_skill_system_prompt("promo_planner_script.md")
    assert "flower_text_spec" in scheme_sys
    assert "花字规范" in script_sys
    assert "印章体" in scheme_sys
    assert "繁体" in scheme_sys
    assert "印章体" in script_sys
    assert "英文小字" in scheme_sys
    assert "英级=小" in script_sys
    assert "画右" in scheme_sys
    assert "画左" in scheme_sys
    assert "排向=竖" in script_sys
    assert "有韵味" in scheme_sys
    assert "有韵味" in script_sys
    assert "禁底部" in scheme_sys
    assert "避字幕" in scheme_sys
    assert "避字幕" in script_sys
    assert "每段最多一条" in scheme_sys
    assert "每段最多一条" in script_sys
    assert "一个动作最多一条" in script_sys
    assert "黑屏专镜" in scheme_sys
    assert "黑屏专镜" in script_sys
    assert "段末切镜" in scheme_sys
    assert "段首开镜" in script_sys
    assert "不与动作抢镜" in scheme_sys
    assert "不与动作抢镜" in script_sys
    assert "旁白优先" in scheme_sys
    assert "旁白优先" in script_sys
    assert "有旁白时不出花字" in scheme_sys or "禁同步" in scheme_sys
    assert "花字: 无" in script_sys
    assert "听=无" in script_sys
    assert "停留=长" in scheme_sys
    assert "书法" in scheme_sys
    assert "书法" in script_sys
    assert "艺术化" in scheme_sys
    assert "艺术化" in script_sys
    assert "并不限于" in scheme_sys
    assert "并不限于" in script_sys
    assert "艺术=" in scheme_sys
    assert "艺术=" in script_sys
    assert "字少味厚" in scheme_sys
    assert unique_flower_text_slot("文案=「山河入盏」｜位置=中|底｜字级=大") == "文案=「山河入盏」｜位置=中｜字级=大"
    assert unique_flower_text_slot("文案=「山河入盏」｜位置=底｜字级=中") == "文案=「山河入盏」｜位置=中｜字级=中"
    assert unique_flower_text_slot("文案=「山河入盏」｜位置=中|底｜字级=大｜艺术=印章+浅金+英文小字") == "文案=「山河入盏」｜位置=中｜字级=大｜艺术=印章+浅金+英文小字"
    assert "位置=中" in merge_planner_result(
        {"stage_plan": {"value": {"flower_text": "文案=「山河入盏」｜位置=中|底｜字级=大"}}}
    )["stage_plan"]["value"]["flower_text"]
    assert "位置=底" not in merge_planner_result(
        {"stage_plan": {"value": {"flower_text": "文案=「山河入盏」｜位置=中|底｜字级=大"}}}
    )["stage_plan"]["value"]["flower_text"]
    lifted = merge_planner_result(
        {
            "project_visual_backfill": {
                "flower_text_spec": {"body_position": "底部居中", "emphasis_position": "底部居中"},
            },
            "stage_plan": {"hook": {"flower_text": "文案=「旧底」｜位置=底｜字级=中"}},
        }
    )
    assert lifted["project_visual_backfill"]["flower_text_spec"]["body_position"] == "画面中部"
    assert lifted["project_visual_backfill"]["flower_text_spec"]["emphasis_position"] == "画面中部"
    assert "位置=中" in lifted["stage_plan"]["hook"]["flower_text"]
    assert "位置=底" not in lifted["stage_plan"]["hook"]["flower_text"]
    assert "上屏=段末切镜" in lifted["stage_plan"]["hook"]["flower_text"]
    assert "字少味厚" in script_sys
    assert "≤15字" in scheme_sys
    assert "≤15字" in script_sys
    assert "中屏展示=中部必须艺术化组合设计，不限于印章/古体/英文小字/颜色" in spec["spec_line"]
    scheme_user = _build_scheme_user_prompt(
        {"enterprise_info": {}, "campaign_demand": {"goal_type": "即时转化（引流获客）", "expect_duration": "15-30s"}},
        {},
        [],
    )
    script_user = _build_script_user_prompt(
        title="试片",
        planner_input={"enterprise_info": {}, "campaign_demand": {}},
        planner_result=merged,
    )
    assert "flower_text_spec" in scheme_user
    assert "艺术=" in scheme_user
    assert "并不限于" in scheme_user
    assert "花字规范" in script_user
    assert "艺术=" in script_user
    assert "并不限于" in script_user
    assert "旁白优先" in scheme_user
    assert "听=无" in scheme_user
    assert "旁白优先" in script_user
    assert "听=无" in script_user
    assert "旁白优先=" in spec["spec_line"] or "有旁白时不出花字" in spec["spec_line"]


def test_promo_music_is_foreground_and_loud():
    merged = merge_planner_result(
        {
            "project_visual_backfill": {
                "music_recommendation": "乐器=弦乐｜风格=现代｜音量=垫底",
            }
        }
    )
    rec = merged["project_visual_backfill"]["music_recommendation"]
    assert "音量=并重" in rec
    assert "音量=垫底" not in rec
    assert "权重=配乐主轴" in rec
    brief = collect_promo_brief({"source_promo_project_id": 11}, {}, merged)
    assert brief["promo_music_volume"] == "并重"
    body = format_promo_injection_body(brief)
    assert "配乐音量=并重" in body
    assert "音量=并重" in body
    scheme_sys = _promo_skill_system_prompt("promo_planner_scheme.md")
    script_sys = _promo_skill_system_prompt("promo_planner_script.md")
    assert "配乐必须更响" in scheme_sys
    assert "配乐必须更响" in script_sys


def test_promo_visual_core_is_locked_and_injected():
    merged = merge_planner_result(
        {
            "overall_scheme": {
                "promo_focus": "要点=主推非遗宴与古镇夜景｜来源=基本介绍｜依据=本次宣传要点",
                "selling_points": "主=美食｜次=美景,文化,历史沉淀｜展现=吸睛宴席特写；价值古镇宏观；收口仪典",
                "visual_core": "核=美食｜加码=充分特写｜依据=已锁主卖点",
            }
        }
    )
    assert merged["overall_scheme"]["promo_focus"].startswith("要点=主推非遗宴")
    assert "美食" in merged["overall_scheme"]["selling_points"]
    assert merged["overall_scheme"]["visual_core"] == "核=美食｜加码=充分特写｜依据=已锁主卖点"
    brief = collect_promo_brief({"source_promo_project_id": 12}, {}, merged)
    assert "美食" in brief["promo_visual_core"]
    assert "非遗宴" in brief["promo_focus"]
    assert "历史沉淀" in brief["promo_selling_points"]
    body = format_promo_injection_body(brief)
    assert "画面核=" in body
    assert "宣传要点=" in body
    assert "主要卖点=" in body
    assert "充分特写" in body
    applied = apply_promo_fields_to_global_info({"source_promo_project_id": 12}, brief)
    again = collect_promo_brief(applied)
    assert "美食" in again["promo_visual_core"]
    assert "非遗宴" in again["promo_focus"]
    assert "文化" in again["promo_selling_points"]
    scheme_sys = _promo_skill_system_prompt("promo_planner_scheme.md")
    script_sys = _promo_skill_system_prompt("promo_planner_script.md")
    assert "充分特写" in scheme_sys
    assert "宏观特效" in scheme_sys
    assert "技术特效" in scheme_sys
    assert "visual_core" in scheme_sys
    assert "特别描述" in scheme_sys
    assert "产品（有产品则必须）" in scheme_sys
    assert "企业元素（有则必须）" in scheme_sys
    assert "Logo" in scheme_sys
    assert "情绪种草禁口播介绍" in scheme_sys
    assert "情绪种草禁口播介绍" in script_sys
    assert "花字可以点" in scheme_sys
    assert "花字可以点" in script_sys
    assert "画面核" in script_sys
    assert "技术特效" in script_sys
    assert "特别描述" in script_sys
    assert "Logo" in script_sys
    assert "slogan" in script_sys.lower() or "Slogan" in script_sys
    scheme_user = _build_scheme_user_prompt(
        {"enterprise_info": {}, "campaign_demand": {"goal_type": "企业品牌宣传（情绪种草）", "expect_duration": "15-30s"}},
        {},
        [],
    )
    script_user = _build_script_user_prompt(
        title="试片",
        planner_input={"enterprise_info": {}, "campaign_demand": {}},
        planner_result=merged,
    )
    assert "花字可以点" in scheme_user or "禁口播" in scheme_user
    assert "花字可以点" in script_user or "种草" in script_user
    assert "visual_core" in scheme_user
    assert "promo_focus" in scheme_user
    assert "selling_points" in scheme_user
    assert "画面核" in script_user or "visual_core" in script_user
    assert "宣传要点" in script_user or "promo_focus" in script_user
    assert "已有素材不作约束" in scheme_sys
    assert "宏观大场面" in scheme_sys
    assert "精密拍摄" in scheme_sys
    assert "已有素材不作约束" in script_sys
    assert "宏观大场面" in scheme_user
    assert "精密拍摄" in script_user
    assert "宣传要点与卖点必须锁满" in scheme_sys
    assert "宣传要点与卖点必须展现" in script_sys
    assert "历史沉淀" in scheme_sys
    markdown = result_to_promo_markdown(
        merged,
        {"enterprise_info": {}, "campaign_demand": {}},
    )
    assert "宣传要点" in markdown
    assert "主要卖点" in markdown


def test_promo_technique_lexicon_injected_into_scheme_and_script():
    block = empty_stage_block("吸睛")
    assert "technique_assoc" in block
    assert "flower_text" in block
    scheme_sys = _promo_skill_system_prompt("promo_planner_scheme.md")
    script_sys = _promo_skill_system_prompt("promo_planner_script.md")
    for text in (scheme_sys, script_sys):
        assert "技巧联想词库" in text
        assert "内容核" in text
        assert "感官核" in text
        assert "点缀装饰" in text
    assert "technique_assoc" in scheme_sys
    assert "按上游规划细化" in script_sys
    assert "四段内容逐字核销" in script_sys
    assert "对标必须全表分析并综合进各拍" in script_sys
    assert "对标综合" in script_sys
    assert "旁白 / 口播 / 动作必须分行" in script_sys
    assert "口播: 「可听短句」" in script_sys or "声型=旁白|口播|对白" in script_sys
    assert "镜头由编剧实现" in script_sys
    assert "镜头不在策划写" in scheme_sys
    assert "美化光" in script_sys
    assert "技术特效" in scheme_sys
    assert "技术特效" in script_sys
    assert "救猫咪" in scheme_sys
    assert "救猫咪" in script_sys
    scheme_user = _build_scheme_user_prompt(
        {"enterprise_info": {}, "campaign_demand": {"goal_type": "即时转化（引流获客）", "expect_duration": "15-30s"}},
        {},
        [],
    )
    script_user = _build_script_user_prompt(
        title="试片",
        planner_input={"enterprise_info": {}, "campaign_demand": {}},
        planner_result=merge_planner_result({}),
    )
    assert "救猫咪" in scheme_user
    assert "救猫咪" in script_user


def test_planner_shots_left_to_script_writer_with_verbatim_checkout():
    merged = merge_planner_result(
        {
            "stage_plan": {
                "hook": {
                    "name": "吸睛",
                    "content": "一句话钩子：看见改变",
                    "sensory": "热气切开汁水",
                    "shots": "MCU 推到锅沿",
                    "copy": "看见改变",
                },
                "empathy": {
                    "name": "共鸣",
                    "content": "客户代入厨房忙乱",
                    "sensory": "手忙脚乱的蒸汽",
                    "shots": "过肩看灶台",
                },
                "value": {
                    "name": "价值",
                    "content": "一刀切开见层次",
                    "sensory": "剖面纹理",
                    "shots": "特写切开",
                },
                "close": {
                    "name": "收口",
                    "content": "记住这口热气",
                    "sensory": "Logo 特写",
                    "shots": "拉到店招",
                    "cta": "预约品鉴",
                },
            }
        }
    )
    for key in ("hook", "empathy", "value", "close"):
        assert "shots" not in merged["stage_plan"][key]
        assert merged["stage_plan"][key]["content"]
    assert "shots" not in empty_stage_block("吸睛")
    assert merged["script_preview"]["beats"][0]["shot"] == "热气切开汁水"
    assert "MCU" not in (merged["script_preview"]["beats"][0].get("shot") or "")

    scheme_user = _build_scheme_user_prompt(
        {
            "enterprise_info": {},
            "campaign_demand": {"goal_type": "即时转化（引流获客）", "expect_duration": "30-60s"},
        },
        {},
        [],
    )
    assert "禁止输出 shots" in scheme_user

    script_user = _build_script_user_prompt(
        title="试片",
        planner_input={
            "enterprise_info": {},
            "campaign_demand": {"goal_type": "即时转化（引流获客）", "expect_duration": "30-60s"},
        },
        planner_result=merged,
    )
    assert "逐字核销" in script_user
    assert "策划核销" in script_user
    assert "对标综合" in script_user
    assert "benchmark_films 全部条目" in script_user
    assert "动作: 【可见主体】" in script_user
    assert "禁止【旁白】后接风景散文" in script_user
    assert "一句话钩子：看见改变" in script_user
    assert "MCU 推到锅沿" not in script_user
    assert '"shots"' not in script_user

    brief = collect_promo_brief({"source_promo_project_id": 9}, {}, merged)
    body = format_promo_injection_body(brief)
    assert "内容=一句话钩子：看见改变" in body
    assert "感官=热气切开汁水" in body
    assert "镜头=" not in body
    assert all("shots" not in row for row in brief["promo_stage_plan"])

    markdown = result_to_promo_markdown(
        merged,
        {"enterprise_info": {}, "campaign_demand": {}},
    )
    assert "内容（编剧逐字核销）" in markdown
    assert "镜头（编剧实现" not in markdown
    assert "   - 镜头" not in markdown
    assert "策划核销" in _promo_skill_system_prompt("promo_planner_script.md")


def test_normalize_promo_project_global_info_locks_type_and_aspect():
    gi = normalize_promo_project_global_info(
        {
            "global_info": {
                "type": "仙侠",
                "language": "中文",
                "country_region": "中国大陆",
                "aspect_ratio": "9:16",
                "base_positioning": "当代都市 / Contemporary Urban",
            }
        },
        title="星河形象片",
        description="品牌气质",
    )
    assert gi["type"] == "仙侠"
    assert gi["type"] != PROMO_PROJECT_TYPE
    assert gi["promo_single_scene"] is True
    assert gi["script_title"] == "星河形象片"
    assert gi["aspect_ratio"] == "9:16"
    assert gi["language"] == "中文"
    extra = persist_promo_project_extra_info(
        {"global_info": gi, "linked_story_project_id": 8},
        title="星河形象片",
        current={"linked_story_episode_id": 3},
        require_aspect_ratio=True,
        require_type=True,
    )
    assert extra["global_info"]["type"] == "仙侠"
    assert extra["linked_story_project_id"] == 8
    assert extra["linked_story_episode_id"] == 3
    from fastapi import HTTPException

    try:
        persist_promo_project_extra_info(
            {"global_info": {"type": "商业宣传片", "aspect_ratio": "16:9"}},
            title="缺类型",
            require_type=True,
            require_aspect_ratio=True,
        )
        raise AssertionError("expected type required")
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "类型" in str(exc.detail)


def test_promo_scheme_and_script_system_prompts_inject_project_info():
    info = {
        "script_title": "星河",
        "type": "实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)",
        "promo_single_scene": True,
        "language": "中文",
        "country_region": "中国大陆",
        "aspect_ratio": "9:16",
        "base_positioning": "当代都市 / Contemporary Urban",
        "era": "当代",
        "season_occurrence": "秋季",
        "lighting": "窗纱柔光",
        "tone": "克制暖金",
    }
    scheme_sys = _promo_skill_system_prompt("promo_planner_scheme.md", info)
    script_sys = _promo_skill_system_prompt("promo_planner_script.md", info)
    for text in (scheme_sys, script_sys):
        assert "[项目信息开始]" in text
        assert "[项目信息结束]" in text
        assert "商业宣传片" in text
        assert "实拍" in text
        assert "9:16" in text
        assert "中文" in text
        assert "技巧联想词库" in text
        assert "项目信息必须继承" in text


def test_scheme_and_script_user_prompts_include_project_info():
    planner_input = {
        "enterprise_info": {"enterprise_name": "星河"},
        "campaign_demand": {"goal_type": "即时转化（引流获客）", "expect_duration": "30-60s"},
    }
    info = {
        "type": "三维动画 / 3D Animation",
        "language": "English",
        "aspect_ratio": "16:9",
        "base_positioning": "近未来科技 / Near-Future Tech",
    }
    scheme = _build_scheme_user_prompt(planner_input, {}, [], project_info=info)
    script = _build_script_user_prompt(
        title="试片",
        planner_input=planner_input,
        planner_result={},
        project_info=info,
    )
    for text in (scheme, script):
        assert "project_info" in text
        assert "16:9" in text
        assert "必须先继承系统提示词与 project_info" in text


def test_linked_story_inherits_stored_promo_global_info():
    class _LockedPromo:
        id = 21
        title = "锁定片"
        description = "建项备注"
        extra_info = {
            "global_info": {
                "type": "仙侠",
                "language": "English",
                "country_region": "USA",
                "aspect_ratio": "2.39:1",
                "base_positioning": "近未来科技 / Near-Future Tech",
                "era": "近未来",
                "season_occurrence": "冬季",
            }
        }

    info = build_linked_story_global_info(_LockedPromo())
    assert info["type"] == "仙侠"
    assert info["type"] != PROMO_PROJECT_TYPE
    assert info["language"] == "English"
    assert info["country_region"] == "USA"
    assert info["aspect_ratio"] == "2.39:1"
    assert "近未来科技" in str(info.get("base_positioning") or "")
    assert info["era"] == "近未来"
    assert info["season_occurrence"] == "冬季"


def test_promo_image_analysis_forbids_watermark_parsing():
    from app.services.prompt_resolve import _resolve_prompt_text

    skill = _resolve_prompt_text("promo_planner_image_analysis.md")
    assert "禁止解析水印" in skill
    assert "Shutterstock" in skill
    prompt = _build_image_analysis_user_prompt(
        [{"object_name": "样品", "image_type": "product", "media_kind": "image", "user_remark": "正面"}],
        assets=[{"object_name": "样品", "image_type": "product", "media_kind": "image", "user_remark": "正面", "img_url": "https://x/a.jpg"}],
    )
    assert "禁止解析水印" in prompt

    cleaned = strip_visual_watermark_text("白理石岛台居中，右下角有 Shutterstock 半透明水印，胡桃木柜贴墙")
    assert "白理石岛台居中" in cleaned
    assert "胡桃木柜贴墙" in cleaned
    assert "Shutterstock" not in cleaned
    assert "水印" not in cleaned
    assert "水印纹釉面" == strip_visual_watermark_text("水印纹釉面")

    analysis = enrich_rebuild_analysis(
        {
            "global_visual_summary": "暖黄厨房，Getty Images 斜向水印",
            "image_list": [
                {
                    "object_name": "开放式厨房",
                    "image_type": "scene",
                    "user_remark": "岛台操作全过程",
                    "content_desc": "岛台与吊灯，四角版权水印",
                    "rebuild_brief": "白理石岛台、胡桃木柜，画面叠 PREVIEW 水印",
                    "environment_detail": "岛台居中",
                    "color_and_markings": "角标 watermark 白字",
                }
            ],
            "rebuild_subjects": [
                {
                    "kind": "environment",
                    "object_name": "开放式厨房",
                    "rebuild_brief": "白理石岛台，Adobe Stock 水印",
                    "appearance": "开放厨房",
                    "user_remark": "岛台操作全过程",
                }
            ],
        }
    )
    text = format_visual_rebuild_lines(analysis)
    assert "开放式厨房" in text
    assert "白理石岛台" in text or "岛台" in text
    assert "水印" not in text
    assert "Getty" not in text
    assert "PREVIEW" not in text
    assert "Adobe Stock" not in text
    assert analysis["image_list"][0]["user_remark"] == "岛台操作全过程"
    assert "水印" not in (analysis.get("global_visual_summary") or "")


def test_scene_image_subjects_are_not_extracted_as_char_or_prop():
    analysis = enrich_rebuild_analysis(
        {
            "rebuild_subjects": [
                {
                    "kind": "environment",
                    "object_name": "开放式厨房",
                    "rebuild_brief": "白理石岛台、暖黄吊灯",
                    "source_image_ids": ["img-k"],
                },
                {
                    "kind": "character",
                    "object_name": "岛台边的人",
                    "rebuild_brief": "场景里站着的厨师",
                    "source_image_ids": ["img-k"],
                },
                {
                    "kind": "prop",
                    "object_name": "岛台",
                    "rebuild_brief": "白理石岛台",
                    "source_image_ids": ["img-k"],
                },
                {
                    "kind": "character",
                    "object_name": "主厨",
                    "rebuild_brief": "中年男性白色厨服",
                    "source_image_ids": ["img-c"],
                },
            ],
            "image_list": [
                {
                    "image_id": "img-k",
                    "object_name": "开放式厨房",
                    "image_type": "scene",
                    "character_detail": "岛台边站着一位厨师",
                    "prop_detail": "岛台上有一把厨刀",
                    "subjects_in_frame": ["开放式厨房", "岛台边的人", "岛台"],
                    "environment_detail": "岛台居中",
                    "rebuild_brief": "暖黄厨房",
                },
                {
                    "image_id": "img-c",
                    "object_name": "主厨",
                    "image_type": "character",
                    "character_detail": "中年男性，白色双排扣厨服",
                    "rebuild_brief": "一位厨师",
                },
            ],
        }
    )
    kinds_names = {(item.get("kind"), item.get("object_name")) for item in analysis["rebuild_subjects"]}
    assert ("environment", "开放式厨房") in kinds_names
    assert ("character", "主厨") in kinds_names
    assert ("character", "岛台边的人") not in kinds_names
    assert ("prop", "岛台") not in kinds_names
    scene_row = next(row for row in analysis["image_list"] if row.get("image_id") == "img-k")
    assert scene_row["character_detail"] == "无"
    assert scene_row["prop_detail"] == "无"
    assert scene_row["subjects_in_frame"] == ["开放式厨房"]
    text = format_visual_rebuild_lines(analysis)
    assert "ENV:开放式厨房" in text
    assert "CHAR:主厨" in text
    assert "CHAR:岛台边的人" not in text
    assert "PROP:岛台" not in text
    prompt = _build_image_analysis_user_prompt(
        [{"object_name": "开放式厨房", "image_type": "scene", "media_kind": "image", "user_remark": "全景"}],
        assets=[{"object_name": "开放式厨房", "image_type": "scene", "media_kind": "image", "user_remark": "全景", "img_url": "https://x/k.jpg"}],
    )
    assert "场景图（类型=场景）只重生环境" in prompt
    assert "本请求通常只有一条素材" in prompt


def test_merge_single_asset_analysis_keeps_other_rows():
    base = {
        "image_list": [
            {
                "image_id": "a",
                "content_desc": "红墙厨房暖黄灯光",
                "rebuild_brief": "红砖墙暖黄灯光不锈钢台面开放式厨房",
                "analysis_status": "success",
            },
        ],
        "rebuild_subjects": [
            {"kind": "environment", "object_name": "厨房", "source_image_ids": ["a"], "appearance": "红砖墙"},
        ],
        "global_visual_summary": "暖黄厨房",
    }
    merged = merge_single_asset_analysis(
        base,
        {"image_id": "b", "image_type": "product", "object_name": "酒瓶", "media_kind": "image"},
        {
            "image_list": [
                {
                    "image_id": "b",
                    "content_desc": "深绿玻璃酒瓶金色标",
                    "rebuild_brief": "深绿玻璃瓶身金色标纸圆柱形暖光",
                }
            ],
            "rebuild_subjects": [
                {"kind": "prop", "object_name": "酒瓶", "source_image_ids": ["b"], "appearance": "深绿玻璃"}
            ],
            "global_visual_summary": "质感酒液",
        },
    )
    ids = {row["image_id"] for row in merged["image_list"]}
    assert ids == {"a", "b"}
    assert all(row["analysis_status"] == "success" for row in merged["image_list"])
    names = {row["object_name"] for row in merged["rebuild_subjects"]}
    assert "厨房" in names and "酒瓶" in names


def test_merge_single_asset_analysis_marks_failure():
    merged = merge_single_asset_analysis(
        {},
        {"image_id": "x", "image_type": "scene", "object_name": "大厅", "media_kind": "image"},
        {},
        error="图片 大厅 无法读取",
    )
    row = merged["image_list"][0]
    assert row["analysis_status"] == "failed"
    assert row["analysis_error"] == "图片 大厅 无法读取"


def test_assets_needing_analysis_skips_success_unless_forced():
    assets = [
        {"image_id": "a", "img_url": "http://a"},
        {"image_id": "b", "img_url": "http://b"},
    ]
    analysis = {
        "image_list": [
            {
                "image_id": "a",
                "content_desc": "可见主体",
                "rebuild_brief": "完整外形段可重生",
                "analysis_status": "success",
            },
            {
                "image_id": "b",
                "content_desc": "识别失败",
                "analysis_status": "failed",
                "analysis_error": "timeout",
            },
        ]
    }
    pending = assets_needing_analysis(assets, analysis)
    assert [item["image_id"] for item in pending] == ["b"]
    forced = assets_needing_analysis(assets, analysis, force_all=True)
    assert [item["image_id"] for item in forced] == ["a", "b"]
    one = assets_needing_analysis(assets, analysis, force_ids=["a"])
    assert [item["image_id"] for item in one] == ["a", "b"]


def test_apply_analysis_status_to_assets():
    assets = [
        {"image_id": "a", "img_url": "http://a"},
        {"image_id": "b", "img_url": "http://b"},
        {"image_id": "c", "img_url": "http://c"},
    ]
    analysis = {
        "image_list": [
            {
                "image_id": "a",
                "content_desc": "可见主体",
                "rebuild_brief": "完整外形段可重生",
                "analysis_status": "success",
            },
            {"image_id": "b", "analysis_status": "failed", "analysis_error": "无法读取"},
        ]
    }
    out = apply_analysis_status_to_assets(assets, analysis)
    by_id = {item["image_id"]: item for item in out}
    assert by_id["a"]["analysis_status"] == "success"
    assert by_id["b"]["analysis_status"] == "failed"
    assert by_id["c"]["analysis_status"] == "pending"


def test_resolve_share_keeps_project_enterprise_when_planner_omits_it():
    class _Proj:
        enterprise_id = 3
        extra_info = {}

    assert resolve_share_enterprise_id(_Proj(), {}, [{"owner_kind": "project", "img_url": "https://x"}]) == 3
    assert resolve_share_enterprise_id(_Proj(), {"enterprise_info": {}}, []) == 3


def test_catalog_analysis_fields_and_share_merge():
    asset = {"image_id": "kitchen-1", "object_name": "开放式厨房", "image_type": "scene", "img_url": "https://x/k.jpg"}
    analysis = {
        "global_visual_summary": "暖光厨房",
        "image_list": [
            {
                "image_id": "kitchen-1",
                "content_desc": "开放式厨房全景",
                "rebuild_brief": "暖光开放厨房，岛台金属拉丝",
                "analysis_status": "success",
            }
        ],
        "rebuild_subjects": [
            {
                "kind": "environment",
                "object_name": "开放式厨房",
                "source_image_ids": ["kitchen-1"],
                "rebuild_brief": "暖光开放厨房",
            }
        ],
    }
    sliced = slice_asset_analysis(analysis, asset)
    assert sliced["image_list"][0]["rebuild_brief"]
    extra = merge_catalog_analysis_extra({}, asset, analysis)
    fields = catalog_analysis_fields(extra, asset)
    assert fields["analysis_status"] == "success"
    assert fields["image_asset_analysis"]["image_list"][0]["content_desc"] == "开放式厨房全景"
    kept = merge_catalog_analysis_extra(extra, asset, {"image_list": [{"image_id": "kitchen-1", "analysis_status": "failed"}]})
    assert catalog_analysis_fields(kept, asset)["analysis_status"] == "success"


def test_serialize_catalog_asset_exposes_analysis():
    class _Row:
        id = 9
        owner_id = 3
        owner_kind = "enterprise"
        owner_entity_id = 2
        media_kind = "image"
        asset_type = "scene"
        image_id = "kitchen-1"
        file_url = "/uploads/3/k.jpg"
        object_name = "开放式厨房"
        user_remark = ""
        extra_info = {
            "analysis_status": "success",
            "analysis_error": "",
            "image_asset_analysis": {
                "image_list": [{"image_id": "kitchen-1", "rebuild_brief": "暖光厨房", "analysis_status": "success"}],
            },
        }
        created_at = "2026-09-19"
        updated_at = "2026-09-19"

    out = serialize_promo_catalog_asset(_Row())
    assert out["analysis_status"] == "success"
    assert out["img_url"] == "/uploads/3/k.jpg"
    assert out["image_asset_analysis"]["image_list"][0]["rebuild_brief"] == "暖光厨房"
