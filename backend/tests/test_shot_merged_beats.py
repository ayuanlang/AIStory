# -*- coding: utf-8 -*-
from app.services.shot_markdown import (
    extract_merged_beat_ids,
    parse_shots_markdown_table,
    stabilize_shot_logic_merged_beats,
)


def test_extract_canonical_merged_beats_ignores_later_beat_mentions():
    logic = (
        "Beat-Shot映射:合镜Beat=Beat1+Beat3｜Duration=11<br>"
        "场结果:高潮=Beat2@SH01｜空镜=SH01P2"
    )
    assert extract_merged_beat_ids(logic) == [1, 3]


def test_stabilize_old_merge_and_single_spellings():
    merged = stabilize_shot_logic_merged_beats(
        "Beat-Shot映射:合镜=Beat3+Beat4｜Duration=7<br>节奏:中"
    )
    assert merged.startswith("Beat-Shot映射:合镜Beat=Beat3+Beat4｜Duration=7<br>")
    assert extract_merged_beat_ids(merged) == [3, 4]

    single = stabilize_shot_logic_merged_beats(
        "Beat-Shot映射:单Beat=Beat2｜Duration=5<br>节奏:中"
    )
    assert single.startswith("Beat-Shot映射:合镜Beat=Beat2｜Duration=5<br>")
    assert extract_merged_beat_ids(single) == [2]


def test_stabilize_montage_keeps_chain_mark_and_beat_list():
    logic = stabilize_shot_logic_merged_beats(
        "Beat-Shot映射:合镜=蒙太奇链｜Beat1+Beat2+Beat5｜Duration=8<br>ENV:ENV:[A]"
    )
    assert logic.startswith("Beat-Shot映射:合镜Beat=Beat1+Beat2+Beat5｜链=蒙太奇｜Duration=8<br>")
    assert extract_merged_beat_ids(logic) == [1, 2, 5]
    again = stabilize_shot_logic_merged_beats(logic)
    assert again == logic


def test_stabilize_collapses_spaces_and_keeps_regenerate_marker():
    logic = stabilize_shot_logic_merged_beats(
        "Beat-Shot映射:合镜Beat=Beat 1 + Beat 2｜Duration=11<br>衔接:N/A首镜=更新分镜"
    )
    assert "合镜Beat=Beat1+Beat2｜Duration=11<br>" in logic
    assert logic.endswith("=更新分镜")


def test_parse_rewrites_logic_cell_for_later_extraction():
    markdown = (
        "| Shot ID | Shot Name | Scene ID | Shot Logic (CN) | Start Frame | Video Content | "
        "Duration (s) | Keyframes | End Frame | Start Frame (CN) | Video Content (CN) | "
        "Keyframes (CN) | End Frame (CN) | Associated Entities |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| EP01_SC01_SH01 | 对谈 | EP01_SC01 | "
        "Beat-Shot映射:合镜=Beat1+Beat2｜Duration=11<br>节奏:中 |  |  | 11 |  |  |  | "
        "运镜与动作流：(P1 0s–11s) |  |  | CHAR:[@甲] |\n"
    )
    _, rows, _ = parse_shots_markdown_table(markdown)
    logic = rows[0]["Shot Logic (CN)"]
    assert logic.startswith("Beat-Shot映射:合镜Beat=Beat1+Beat2｜")
    assert extract_merged_beat_ids(logic) == [1, 2]
