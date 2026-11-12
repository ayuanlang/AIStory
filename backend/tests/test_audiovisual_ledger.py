# -*- coding: utf-8 -*-
from app.services.audiovisual_ledger import (
    extract_audiovisual_ledger,
    restore_audiovisual_by_beat,
    strip_audiovisual_passthrough,
    strip_nameplate_instructions,
)
from app.services.flower_text_ass import _scene_placed_nameplates


DRAMA = """
【声画综合】乐器=主奏=低弦｜配乐出声=后期
【名牌前后标签】
种类=角色｜对象=CHAR:[@甲]｜主标=甲｜副标=掌柜｜落位=人物下方｜字体=魏碑｜样式=暗底横牌｜字色=鎏金｜字级=中｜出字=后期烧录｜上屏=待落｜进视频=否｜挂拍=B1
种类=角色｜对象=CHAR:[@乙]｜主标=乙｜副标=无｜落位=人物下方｜字体=魏碑｜样式=无｜字色=鎏金｜字级=中｜出字=模型直出｜上屏=首见｜进视频=是｜挂拍=B2
[BEAT_START:1]
甲推门。开口 | CHAR:[@甲] | {进来。} | 闭嘴 | 其他人均闭嘴
【配乐】 | （低弦） | 态=起 | 音量=弱 | 出声=后期
【音效】 | <门轴一声> | 配合=门 | 方位=近 | 音量=弱
[BEAT_END:1]
[BEAT_START:2]
乙回头。
【配乐】 | （低弦） | 态=续 | 音量=中 | 出声=后期
[BEAT_END:2]
"""

STAGING = """
[BEAT_START:1]
甲推门。开口 | CHAR:[@甲] | {进来。} | 闭嘴 | 其他人均闭嘴
[BEAT_END:1]
[BEAT_START:2]
乙回头。
[BEAT_END:2]
"""


def test_strip_keeps_dialogue_and_drops_score_sfx_and_plates():
    cleaned = strip_audiovisual_passthrough(DRAMA)
    assert "【配乐】" not in cleaned
    assert "【音效】" not in cleaned
    assert "【声画综合】" not in cleaned
    assert "【名牌前后标签】" not in cleaned
    assert "主标=甲" not in cleaned
    assert "{进来。}" in cleaned
    assert "甲推门" in cleaned


def test_restore_by_beat_is_idempotent():
    restored = restore_audiovisual_by_beat(STAGING, DRAMA)
    assert "【声画综合】" in restored
    assert "挂拍=B1" in restored
    beat1, beat2 = restored.split("[BEAT_START:2]", 1)
    assert "【配乐】" in beat1 and "<门轴一声>" in beat1
    assert "【名牌挂位】" in beat1 and "主标=甲" in beat1
    assert "画面打出物理文字标签：【乙】" in beat2
    assert "态=续" in beat2
    again = restore_audiovisual_by_beat(restored, DRAMA)
    assert again.count("【配乐】") == restored.count("【配乐】")
    assert again.count("画面打出物理文字标签") == restored.count("画面打出物理文字标签")


def test_brief_nameplate_sections_drop_and_voice_stays():
    brief = "【名牌展现】字体=魏碑｜样式=暗底横牌\n字色=鎏金\n【本场对白声线】甲=低\n"
    cleaned = strip_nameplate_instructions(brief)
    assert "【名牌展现】" not in cleaned
    assert "魏碑" not in cleaned
    assert "【本场对白声线】" in cleaned


def test_hang_beat_places_burn_row():
    placed = _scene_placed_nameplates(DRAMA)
    by_main = {}
    for beat, row in placed:
        if "主标=甲" in row and "【名牌挂位】" not in row:
            by_main["甲"] = beat
        if "主标=乙" in row:
            by_main["乙"] = beat
    assert by_main["甲"] == 1
    assert by_main["乙"] == 2
    ledger = extract_audiovisual_ledger(DRAMA)
    assert ledger["plates"][0]["beat"] == "1"
    assert ledger["beats"]["1"]["sfx"]
