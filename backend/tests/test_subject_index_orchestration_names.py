# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.subject_index_name_align import (
    format_entity_rows_for_orchestration,
    format_subject_index_names_for_orchestration,
)


ASSET_ROWS = [
    {"type": "character", "name": "林岳", "name_en": "Lin Yue"},
    {"type": "character", "name": "林岳_礼服版", "name_en": "Lin Yue Formal"},
    {"type": "prop", "name": "短刀", "name_en": "Dagger"},
    {"type": "environment", "name": "客栈废墟外", "name_en": "Inn Ruins Exterior"},
    {"type": "environment", "name": "0度客栈废墟外", "name_en": "0 Deg Inn Ruins Exterior"},
    {"type": "environment", "name": "180度客栈废墟外", "name_en": "180 Deg Inn Ruins Exterior"},
    {"type": "cover", "name": "封面", "name_en": "Cover"},
]


def test_orchestration_names_from_asset_table_keep_zh_en_drop_main_env():
    compact = format_entity_rows_for_orchestration(ASSET_ROWS)
    assert compact == (
        "CHAR: 林岳 / Lin Yue，林岳_礼服版 / Lin Yue Formal\n"
        "PROP: 短刀 / Dagger\n"
        "ENV: 0度客栈废墟外 / 0 Deg Inn Ruins Exterior，180度客栈废墟外 / 180 Deg Inn Ruins Exterior"
    )
    assert "客栈废墟外 / Inn Ruins Exterior" not in compact
    assert "封面" not in compact


def test_orchestration_names_drop_bare_main_environment():
    assert format_entity_rows_for_orchestration(
        [{"type": "environment", "name": "客栈废墟外", "name_en": "Inn"}]
    ) == ""


def test_orchestration_names_merge_scene_local_derived_env():
    compact = format_entity_rows_for_orchestration(
        ASSET_ROWS,
        extra_derived_environment_names="90度客栈废墟外，客栈废墟外",
    )
    assert compact == (
        "CHAR: 林岳 / Lin Yue，林岳_礼服版 / Lin Yue Formal\n"
        "PROP: 短刀 / Dagger\n"
        "ENV: 0度客栈废墟外 / 0 Deg Inn Ruins Exterior，180度客栈废墟外 / 180 Deg Inn Ruins Exterior，90度客栈废墟外"
    )


def test_legacy_index_formatter_also_emits_zh_en_pairs():
    index_text = """
| subject_no | subject_type | subject_name_zh | subject_name_en | base_entity | dependency_reference | entity_attributes | script_entity_coverage |
|---|---|---|---|---|---|---|---|
| S001 | character | 林岳 | Lin Yue | None | None | basic_positioning:男主 | 林岳 |
| S004 | environment | 客栈废墟外 | Inn Ruins Exterior | None | None | activity_space:废墟庭院 | 客栈废墟外 |
| S005 | environment | 0度客栈废墟外 | 0 Deg Inn Ruins Exterior | 客栈废墟外 | S004 | env_role:视角衍生 | 0度客栈废墟外 |
"""
    compact = format_subject_index_names_for_orchestration(index_text)
    assert compact == (
        "CHAR: 林岳 / Lin Yue\n"
        "ENV: 0度客栈废墟外 / 0 Deg Inn Ruins Exterior"
    )
