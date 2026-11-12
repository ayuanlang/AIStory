# -*- coding: utf-8 -*-
from app.services.space_occupancy_continuity import (
    compare_time,
    judge_against_text,
    judge_occupancy,
    judge_windows,
    latest_per_place,
    normalize_place_name,
    place_keys_in_text,
    records_from_framing,
    render_occupancy_reference,
)


def _framing(last_state: str, place: str = "办公室") -> str:
    return f"""
[BEAT_START:1]
【角色道具世界分布图】
基准=主环境:{place}
CHAR:[@甲]｜在场=开场｜锚=办公桌北椅｜X=轴上｜Y=轴上｜Z=椅面
当前环境=0度{place}
机位锚=办公桌
[BEAT_END:1]
[BEAT_START:4]
【角色道具世界分布图】
基准=主环境:{place}
CHAR:[@甲]｜在场={last_state}｜锚=办公桌北椅｜X=轴上｜Y=南一臂｜Z=椅面｜朝向=面向 CHAR:[@乙]
PROP:[工牌]｜在场=仍在｜锚=CHAR:[@甲]
当前环境=180度{place}
机位锚=办公桌｜景别=MS
[BEAT_END:4]
"""


def _record(last_state: str, *, episode: int = 1, scene: str = "EP01_SC02", place: str = "办公室"):
    rows = records_from_framing(
        framing_text=_framing(last_state, place),
        time_text="【本场时地】季节=秋｜时段=白天｜时辰=巳｜光变档=日南",
        episode_number=episode,
        episode_id=episode,
        scene_id=scene,
    )
    return rows[-1]


def test_normalize_strips_degree_and_parenthetical():
    assert normalize_place_name("180度办公室") == normalize_place_name("办公室")
    assert normalize_place_name("星澜开放工位区 (Starlan Open Cubicles)") == "星澜开放工位区"


def test_last_beat_keeps_people_and_drops_camera():
    record = _record("仍在")
    assert record.beat_id == "4"
    assert record.place == "办公室"
    assert record.still_names == ["甲"]
    assert "X=南一臂" in record.distribution_map or "Y=南一臂" in record.distribution_map
    assert "机位锚" not in record.distribution_map
    assert "景别" not in record.distribution_map
    assert "PROP:[工牌]" in record.distribution_map


def test_everyone_left_is_ended_without_map():
    block = render_occupancy_reference([_record("本拍离场")], current_text="【本场时地】时段=白天｜光变档=日南")
    assert "判定=已结束" in block
    assert "角色已离场" in block
    assert "不附分布图" in block
    assert "Y=南一臂" not in block


def test_same_period_keeps_the_map():
    block = render_occupancy_reference(
        [_record("仍在")],
        current_text="【本场时地】季节=秋｜时段=白天｜光变档=日南",
    )
    assert "判定=未结束" in block
    assert "CHAR:[@甲]" in block
    assert "Y=南一臂" in block


def test_other_period_ends_without_map():
    block = render_occupancy_reference(
        [_record("仍在")],
        current_text="【本场时地】时段=黄昏｜光变档=夕西",
    )
    assert "判定=已结束" in block
    assert "另一时间段" in block
    assert "Y=南一臂" not in block


def test_unknown_time_stays_pending_with_map():
    block = render_occupancy_reference([_record("仍在")], current_text="")
    assert "判定=待判" in block
    assert "Y=南一臂" in block


def test_next_day_words_end_the_occupancy():
    assert compare_time("时段=白天", "次日清晨，地点=办公室") == "另一时间段"


def test_latest_episode_and_scene_win():
    early = _record("仍在", episode=1, scene="EP01_SC01")
    later = _record("仍在", episode=1, scene="EP01_SC03")
    next_ep = _record("本拍离场", episode=2, scene="EP02_SC01")
    picked = latest_per_place([early, next_ep, later], before_episode=3)
    assert len(picked) == 1
    assert picked[0].scene_id == "EP02_SC01"
    assert picked[0].still_names == []
    earlier_only = latest_per_place([early, later, next_ep], before_episode=2)
    assert earlier_only[0].scene_id == "EP01_SC03"


def test_same_episode_only_earlier_scenes():
    first = _record("仍在", episode=2, scene="EP02_SC01")
    current = _record("仍在", episode=2, scene="EP02_SC03")
    picked = latest_per_place(
        [first, current],
        before_episode=2,
        earlier_than=(2, current.scene_rank),
    )
    assert [item.scene_id for item in picked] == ["EP02_SC01"]


def test_outline_space_line_names_match():
    text = (
        "- **空间**：星澜开放工位区 (Starlan Open Cubicles)｜主体=隔断｜占用=沿用；"
        "电梯间｜主体=轿厢"
    )
    assert place_keys_in_text(text) == ["星澜开放工位区", "电梯间"]


def test_mixed_windows_stay_pending_and_keep_the_map():
    record = _record("仍在")
    verdict, reason = judge_windows(
        record,
        ["地点=办公室｜时段=白天", "地点=办公室｜次日清晨"],
    )
    assert verdict == "待判"
    assert "换了时间段" in reason
    block = render_occupancy_reference(
        [record],
        judgments={
            (record.place_key, record.episode_number, record.scene_id, record.beat_id): (verdict, reason)
        },
    )
    assert "判定=待判" in block
    assert "Y=南一臂" in block


def test_judge_same_day_part_from_outline_range():
    record = _record("仍在")
    verdict, _reason = judge_occupancy(
        record,
        "- **时间**：范围=同日白天→同日黄昏｜昼夜=日｜季节=秋｜跳=否",
    )
    assert verdict == "未结束"


def test_dialogue_about_tomorrow_does_not_end_the_room():
    record = _record("仍在")
    text = (
        "【本场时地】季节=秋｜时段=白天｜光变档=日南\n"
        + "甲：第二天再来，把这件事说完。\n" * 5
        + "地点=办公室｜占用=未结束\n"
        + "甲：第二天再来。\n"
    )
    verdict, _reason = judge_against_text(record, text, episode_time=True)
    assert verdict == "未结束"


def test_next_morning_before_the_place_ends_it():
    record = _record("仍在")
    verdict, reason = judge_against_text(record, "次日清晨\n地点=办公室\n", episode_time=True)
    assert verdict == "已结束"
    assert reason == "另一时间段"


def test_scene_title_and_main_env_name_the_place():
    assert place_keys_in_text("【场景名称】办公室·黄昏·内\n【主环境】办公室｜时段=黄昏") == ["办公室"]
    assert "办公室" not in place_keys_in_text("【主环境】总裁办公室｜时段=白天")
