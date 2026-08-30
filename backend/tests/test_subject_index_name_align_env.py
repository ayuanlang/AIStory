# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.subject_index_name_align import (
    apply_scene_table_name_replacements,
    apply_subjects_json_name_replacements,
    apply_text_name_replacements,
    build_scene_name_align_whitelist,
    collect_scene_table_name_mismatches,
    collect_subjects_json_name_mismatches,
    collect_typed_token_name_mismatches,
)


MAIN_ONLY_INDEX = """
| subject_no | subject_type | subject_name_zh | subject_name_en |
|---|---|---|---|
| S001 | character | 林岳 | Lin Yue |
| S004 | environment | 客栈废墟外 | Inn Ruins Exterior |
"""

ASSET_ROWS = [
    {"type": "character", "name": "林岳", "name_en": "Lin Yue"},
    {"type": "character", "name": "苏晚", "name_en": "Su Wan"},
    {"type": "prop", "name": "短刀", "name_en": "Dagger"},
    {"type": "environment", "name": "客栈废墟外", "name_en": "Inn Ruins Exterior"},
    {"type": "environment", "name": "0度客栈废墟外", "name_en": "0 Deg Inn Ruins Exterior"},
    {"type": "environment", "name": "180度客栈废墟外", "name_en": "180 Deg Inn Ruins Exterior"},
]

SCENE_WITH_DERIVED = (
    "| Episode ID | Scene ID | Scene No. | Scene Name | Environment Name | Linked Characters | Key Props |\n"
    "|---|---|---|---|---|---|---|\n"
    "| EP01 | EP01_SC01 | 1 | 客栈废墟外·夜·外 | 0度客栈废墟外，180度客栈废墟外 | CHAR:[@林岳] | None |\n"
    "\n"
    "当前环境=ENV:[0度客栈废墟外]；CHAR:[@林岳] 走进 ENV:[180度客栈废墟外]。\n"
)


def test_scene_whitelist_env_comes_from_asset_library_not_index_main():
    whitelist = build_scene_name_align_whitelist(MAIN_ONLY_INDEX, asset_rows=ASSET_ROWS)
    env_names = set((whitelist.get("by_bucket") or {}).get("environments") or {})
    assert "0度客栈废墟外" in env_names
    assert "180度客栈废墟外" in env_names
    assert "客栈废墟外" not in env_names
    char_names = set((whitelist.get("by_bucket") or {}).get("characters") or {})
    assert "林岳" in char_names
    assert "苏晚" in char_names


def test_derived_env_in_asset_library_is_not_a_mismatch():
    mismatches = collect_scene_table_name_mismatches(
        SCENE_WITH_DERIVED,
        MAIN_ONLY_INDEX,
        asset_rows=ASSET_ROWS,
    )
    env_names = {item["name"] for item in mismatches if item.get("bucket") == "environments"}
    assert env_names == set()


def test_derived_env_without_asset_library_is_not_collapsed_to_index_main():
    mismatches = collect_scene_table_name_mismatches(SCENE_WITH_DERIVED, MAIN_ONLY_INDEX)
    env_names = {item["name"] for item in mismatches if item.get("bucket") == "environments"}
    assert "0度客栈废墟外" not in env_names
    assert "180度客栈废墟外" not in env_names


def test_derived_env_typo_is_mismatch_against_asset_library():
    mismatches = collect_typed_token_name_mismatches(
        "ENV:[0度客栈废虚外]",
        MAIN_ONLY_INDEX,
        asset_rows=ASSET_ROWS,
    )
    assert any(item.get("name") == "0度客栈废虚外" and item.get("bucket") == "environments" for item in mismatches)


def test_char_delta_resolved_from_asset_library():
    mismatches = collect_scene_table_name_mismatches(
        "| Linked Characters |\n|---|\n| CHAR:[@苏晚] |\n",
        MAIN_ONLY_INDEX,
        asset_rows=ASSET_ROWS,
    )
    assert not any(item.get("name") == "苏晚" for item in mismatches)


def test_off_index_character_still_collected_when_absent_from_assets():
    mismatches = collect_scene_table_name_mismatches(
        "| Linked Characters |\n|---|\n| CHAR:[@何亮] |\n",
        MAIN_ONLY_INDEX,
        asset_rows=ASSET_ROWS,
    )
    assert any(item.get("name") == "何亮" and item.get("bucket") == "characters" for item in mismatches)


def test_apply_replacements_refuses_derived_to_main_collapse():
    aligned = apply_scene_table_name_replacements(
        SCENE_WITH_DERIVED,
        [
            {"field": "Environment Name", "from": "0度客栈废墟外", "to": "客栈废墟外"},
            {"field": "ENV:[]", "from": "180度客栈废墟外", "to": "客栈废墟外"},
        ],
    )
    assert "0度客栈废墟外" in aligned
    assert "180度客栈废墟外" in aligned
    assert "ENV:[客栈废墟外]" not in aligned


def test_apply_replacements_still_fixes_character_names():
    text = "CHAR:[@林越] 站在 ENV:[0度客栈废墟外]"
    aligned = apply_scene_table_name_replacements(
        text,
        [
            {"field": "CHAR:[]", "from": "林越", "to": "林岳"},
            {"field": "ENV:[]", "from": "0度客栈废墟外", "to": "客栈废墟外"},
        ],
    )
    assert "CHAR:[@林岳]" in aligned
    assert "ENV:[0度客栈废墟外]" in aligned
    assert "ENV:[客栈废墟外]" not in aligned


def test_text_replacements_refuses_derived_to_main_collapse():
    text = "0度客栈废墟外，180度客栈废墟外"
    aligned = apply_text_name_replacements(
        text,
        [
            {"from": "0度客栈废墟外", "to": "客栈废墟外"},
            {"from_name": "180度客栈废墟外", "to_name": "客栈废墟外"},
        ],
    )
    assert aligned == text


def test_text_replacements_do_not_stack_english_aliases_inside_derived_env():
    text = "ENV:[0度岚京高空交通层]"
    aligned = apply_text_name_replacements(
        text,
        [
            {
                "from": "岚京高空交通层",
                "to": "岚京高空交通层 (Lan-Jing Aerial Transit Layer)",
            }
        ],
    )
    assert aligned == text


def test_subjects_json_derived_env_is_not_remapped_to_main():
    payload = {
        "characters": [],
        "props": [],
        "environments": [
            {"name": "0度客栈废墟外", "name_en": "0 Deg Inn Ruins Exterior"},
            {"name": "客栈废墟外", "name_en": "Inn Ruins Exterior"},
        ],
        "covers": [],
        "posters": [],
    }
    aligned = apply_subjects_json_name_replacements(
        payload,
        [
            {
                "bucket": "environments",
                "from_name": "0度客栈废墟外",
                "from_name_en": "0 Deg Inn Ruins Exterior",
                "to_name": "客栈废墟外",
                "to_name_en": "Inn Ruins Exterior",
            }
        ],
    )
    assert aligned["environments"][0]["name"] == "0度客栈废墟外"
    assert aligned["environments"][1]["name"] == "客栈废墟外"
    mismatches = collect_subjects_json_name_mismatches(payload, MAIN_ONLY_INDEX)
    assert any(item.get("name") == "0度客栈废墟外" for item in mismatches)
