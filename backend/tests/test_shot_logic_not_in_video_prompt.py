# -*- coding: utf-8 -*-
from app.services.shot_markdown import (
    _clean_shot_video_prompt_cell,
    _looks_like_shot_logic_prefix,
    _looks_like_shot_video_prompt,
    _pick_shot_video_prompt_cell,
    _coerce_shot_row_video_prompt_columns,
    parse_shots_markdown_table,
)


LOGIC = (
    "镜头逻辑总规划:卖点=高武爆发·大漠风情｜高潮=Beat2@SH01｜低谷弧=无<br>"
    "Beat-Shot映射:合镜Beat=Beat1+Beat2｜基准合镜Duration=10.8s｜Duration=11<br>"
    "光影锚定:方向格=90度｜当前衍生ENV=90度龙门风月客栈废墟｜情绪=压迫｜Key=残阳<br>"
    "P段时序链:P1建置CU→特效爆发→P2宏观EWS<br>"
    "本镜出场实体:CHAR:[@李玄],CHAR:[@金镶玉],ENV:[90度龙门风月客栈废墟]"
)

VIDEO = (
    "全局动态风格：项目类型为真人实拍，项目基础定位为古装武侠。<br>"
    "运镜与动作流：(P1) CU, Eye-level 平拍。CHAR:[@金镶玉] 目光一凛。<br>"
    "动态连续光影/焦点：残阳作Key。<br>"
    "光线连动弧光：暖红光芒倾泻而入。<br>"
    "物理文字生成：无。<br>"
    "品质收束：人物面部稳定不变形，无背景音乐，无字幕。"
)


def test_logic_cell_is_not_video_prompt():
    assert _looks_like_shot_logic_prefix(LOGIC)
    assert not _looks_like_shot_video_prompt(LOGIC)
    assert _clean_shot_video_prompt_cell(LOGIC) == ""


def test_lighting_fragment_is_not_video_prompt():
    fragment = (
        "光影锚定:方向格=90度｜当前衍生ENV=90度龙门风月客栈废墟｜情绪=压迫｜"
        "Key=无遮黄昏残阳照亮迎光面｜Fill=烟尘天空冷灰散射｜变=P1浅→P2深 "
        "CHAR:[@金镶玉] ENV:[90度龙门风月客栈废墟]"
    )
    assert _looks_like_shot_logic_prefix(fragment)
    assert not _looks_like_shot_video_prompt(fragment)
    assert _clean_shot_video_prompt_cell(fragment) == ""


def test_merged_logic_and_video_keeps_only_video():
    merged = f"{LOGIC}<br>{VIDEO}"
    assert _looks_like_shot_video_prompt(merged)
    cleaned = _clean_shot_video_prompt_cell(merged)
    assert cleaned.startswith("全局动态风格")
    assert "镜头逻辑总规划" not in cleaned
    assert "Beat-Shot映射" not in cleaned


def test_pick_video_prefers_video_column_over_longer_logic():
    row = {
        "Shot Logic (CN)": LOGIC,
        "Video Content (CN)": VIDEO,
    }
    picked = _pick_shot_video_prompt_cell(row)
    assert picked.startswith("全局动态风格")
    assert "镜头逻辑总规划" not in picked


def test_coerce_strips_logic_from_video_column():
    row = {
        "Shot Logic (CN)": "",
        "Video Content (CN)": f"{LOGIC}<br>{VIDEO}",
    }
    changed, warning = _coerce_shot_row_video_prompt_columns(row)
    assert changed
    assert warning
    assert row["Video Content (CN)"].startswith("全局动态风格")
    assert "镜头逻辑总规划" not in row["Video Content (CN)"]


def test_new_style_result_snapshot_is_logic_not_video():
    snapshot = (
        "Beat-Shot映射:合镜=Beat1+Beat2｜Duration=11<br>"
        "节奏:快｜~｜60fps<br>"
        "运镜:CU Static→EWS Pull Back Reveal<br>"
        "取景:CU→EWS｜平拍→俯拍｜85→35mm｜浅→深<br>"
        "光影:残阳Key｜压迫｜中高｜混合<br>"
        "ENV:ENV:[90度客栈废墟]→ENV:[0度客栈废墟]<br>"
        "实体:CHAR:[@李玄],CHAR:[@金镶玉]<br>"
        "P链:P1建置CU→特效爆发→P2宏观EWS<br>"
        "衔接:N/A首镜"
    )
    assert _looks_like_shot_logic_prefix(snapshot)
    assert not _looks_like_shot_video_prompt(snapshot)
    assert _clean_shot_video_prompt_cell(snapshot) == ""


ENV_OPENING_VIDEO = (
    "ENV:[0度龙门风月客栈内部]。<br>"
    "全局动态风格：项目类型为真人实拍，项目基础定位为古装武侠。<br>"
    "运镜与动作流：(P1) ECU, High Angle 微俯。CHAR:[@金镶玉] 站在柜台内侧操作侧近镜头侧。<br>"
    "动态连续光影/焦点：残阳作Key。<br>"
    "光线连动弧光：暖红光芒倾泻而入。<br>"
    "物理文字生成：无。<br>"
    "品质收束：人物面部稳定不变形，无背景音乐，无字幕。"
)


def test_env_opening_video_is_not_logic():
    assert not _looks_like_shot_logic_prefix(ENV_OPENING_VIDEO)
    assert _looks_like_shot_video_prompt(ENV_OPENING_VIDEO)
    assert _clean_shot_video_prompt_cell(ENV_OPENING_VIDEO).startswith("ENV:[0度龙门风月客栈内部]")


def test_merged_logic_and_env_opening_video_keeps_env_opener():
    merged = f"{LOGIC}<br>{ENV_OPENING_VIDEO}"
    cleaned = _clean_shot_video_prompt_cell(merged)
    assert cleaned.startswith("ENV:[0度龙门风月客栈内部]")
    assert "全局动态风格" in cleaned
    assert "镜头逻辑总规划" not in cleaned
    assert "Beat-Shot映射" not in cleaned


def test_parse_user_style_table_keeps_logic_out_of_video():
    markdown = (
        "| Shot ID | Shot Name | Scene ID | Shot Logic (CN) | Start Frame | Video Content | "
        "Duration (s) | Keyframes | End Frame | Start Frame (CN) | Video Content (CN) | "
        "Keyframes (CN) | End Frame (CN) | Associated Entities |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        f"| EP01_SC04_SH01 | 仙攻与客栈崩塌 | EP01_SC04 | {LOGIC} |  |  | 11 |  |  |  | {VIDEO} |  |  | "
        "CHAR:[@李玄],CHAR:[@金镶玉],ENV:[90度龙门风月客栈废墟] |\n"
    )
    headers, rows, _ = parse_shots_markdown_table(markdown)
    assert "Shot ID" in headers
    assert len(rows) == 1
    video = rows[0]["Video Content (CN)"]
    logic = rows[0]["Shot Logic (CN)"]
    assert video.startswith("全局动态风格")
    assert "镜头逻辑总规划" not in video
    assert "Beat-Shot映射" in logic
    assert "全局动态风格" not in logic


def test_parse_env_opening_video_stays_in_video_column():
    markdown = (
        "| Shot ID | Shot Name | Scene ID | Shot Logic (CN) | Start Frame | Video Content | "
        "Duration (s) | Keyframes | End Frame | Start Frame (CN) | Video Content (CN) | "
        "Keyframes (CN) | End Frame (CN) | Associated Entities |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        f"| EP01_SC01_SH01 | 拨算盘 | EP01_SC01 | {LOGIC} |  |  | 5 |  |  |  | {ENV_OPENING_VIDEO} |  |  | "
        "CHAR:[@金镶玉],ENV:[0度龙门风月客栈内部] |\n"
    )
    headers, rows, _ = parse_shots_markdown_table(markdown)
    assert "Shot ID" in headers
    video = rows[0]["Video Content (CN)"]
    logic = rows[0]["Shot Logic (CN)"]
    assert video.startswith("ENV:[0度龙门风月客栈内部]")
    assert "全局动态风格" in video
    assert "镜头逻辑总规划" not in video
    assert "Beat-Shot映射" in logic
    assert "全局动态风格" not in logic
