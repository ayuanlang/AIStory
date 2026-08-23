# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.subject_index_name_align import split_scene_subject_field


def test_split_scene_subject_field_prefers_chinese_comma():
    assert split_scene_subject_field("CHAR:[@林岳]，CHAR:[@苏晚]") == ["林岳", "苏晚"]
    assert split_scene_subject_field("清河城茶摊，客栈废墟外") == ["清河城茶摊", "客栈废墟外"]
    assert split_scene_subject_field("PROP:[短刀]，PROP:[信件]") == ["短刀", "信件"]


def test_split_scene_subject_field_accepts_slash_and_other_marks():
    assert split_scene_subject_field(
        "CHAR:[@大量百姓]／CHAR:[@楚玄_隐匿版]／CHAR:[@血钢丝]／CHAR:[@何亮]"
    ) == ["大量百姓", "楚玄_隐匿版", "血钢丝", "何亮"]
    assert split_scene_subject_field("林岳/苏晚") == ["林岳", "苏晚"]
    assert split_scene_subject_field("林岳|苏晚、何亮;信件") == ["林岳", "苏晚", "何亮", "信件"]
    assert split_scene_subject_field("办公室会客区／会议室") == ["办公室会客区", "会议室"]


def test_split_scene_subject_field_skips_placeholders():
    assert split_scene_subject_field("None") == []
    assert split_scene_subject_field("n/a") == []
    assert split_scene_subject_field("林岳，无") == ["林岳"]
