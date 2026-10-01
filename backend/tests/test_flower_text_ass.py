# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile

from app.services.flower_text_ass import (
    build_ass,
    extract_libass_events,
    flower_burn_draft,
    normalize_manual_burn_lines,
    stage_burn_font,
    strip_libass_glyphs_from_prompt,
)


SCRIPT = """
(P1 0s–4s) 画幅叠出片内图形花字「一盏灯，照见山河」，上屏=段末切镜，听=无。
(P3 8s–12s) 字卡专镜，Static Hold。背景参考图为 ENV:[0度何家乐]。文案=「天地灵秀·何家乐享」｜位置=中｜字级=大｜烧录=libass｜手写=禁｜逐字=天/地/灵/秀/·/何/家/乐/享｜禁何乐乐享｜英=「Hejia」｜垂询热线：0599-2323239。本P无旁白。印=句外旁侧｜压字=禁｜印文=「乐章」。
(P4 12s–16s) Voiceover: 何家乐健康科技。花字: 无。
"""


def test_libass_events_keep_shop_name_and_hotline_exact():
    events = extract_libass_events(SCRIPT, duration=16)
    assert [event["text"] for event in events] == ["一盏灯，照见山河", "天地灵秀·何家乐享"]
    event = events[1]
    assert "家" in event["text"]
    assert event["companion"].count("0599-2323239") == 1
    assert "Hejia" in event["companion"]
    assert event["start"] == 8.0
    assert event["end"] == 12.0
    assert event["place"] == "中"
    assert event["seal"] == "乐章"


def test_voiceover_and_footer_jia_are_not_burned():
    events = extract_libass_events(SCRIPT, duration=16)
    blob = " ".join(event["text"] for event in events)
    assert "健康科技" not in blob
    poetic = extract_libass_events("花字「万家灯火」｜上屏=段末切镜｜听=无", duration=4)
    assert poetic == []
    footer = extract_libass_events(
        "花字「家」不是第二个人物。标记烧录=libass的店号与热线禁止描字。",
        duration=4,
    )
    assert footer == []


def test_ass_is_centered_and_copies_glyphs_verbatim():
    events = extract_libass_events(SCRIPT, duration=16)
    ass = build_ass(events, width=1920, height=1080)
    assert "天地灵秀·何家乐享" in ass
    assert "0599-2323239" in ass
    assert r"\an5" in ass
    assert r"\pos(" in ass
    assert r"\an2" not in ass
    dialogues = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogues) == 4
    assert any("FlowerSmall" in line and "0599-2323239" in line for line in dialogues)
    assert any("FlowerSeal" in line for line in dialogues)
    for line in dialogues:
        pos = line.split("\\pos(", 1)[1].split(")", 1)[0]
        y = int(pos.split(",")[1])
        assert y < int(1080 * 0.8)


def test_prompt_sent_to_video_model_drops_shop_glyphs():
    stripped = strip_libass_glyphs_from_prompt(SCRIPT)
    assert "天地灵秀·何家乐享" not in stripped
    assert "0599-2323239" not in stripped
    assert "何/家/乐/享" not in stripped
    assert "禁何乐乐享" not in stripped
    assert "ENV:[0度何家乐]" in stripped
    assert "一盏灯，照见山河" not in stripped
    assert "何家乐健康科技" in stripped
    assert "后期烧录" in stripped


def test_manual_seal_burns_beside_the_line():
    events = normalize_manual_burn_lines([{
        "text": "天地灵秀·何家乐享",
        "companion": "0599-2323239",
        "seal": "乐章",
        "start": 1,
        "end": 3,
        "size": "大",
        "place": "中",
    }])
    assert events[0]["seal"] == "乐章"
    ass = build_ass(events, width=1920, height=1080)
    main = next(line for line in ass.splitlines() if line.startswith("Dialogue:") and "何家乐享" in line)
    seal = next(line for line in ass.splitlines() if line.startswith("Dialogue:") and "FlowerSeal" in line)
    assert "乐章" not in main
    assert seal.replace("\\N", "").endswith("乐章")
    assert r"\an2" not in ass
    assert normalize_manual_burn_lines([{"text": "  ", "seal": ""}]) == []


def test_draft_reads_video_prompt_when_shot_script_is_empty():
    class _Shot:
        video_content = ""
        prompt = ""
        duration = "5"
        technical_notes = json.dumps({
            "video_prompt_cn": (
                "(P1 0s–5s) 文案=「何家安泰 草木长乐」｜烧录=libass｜手写=禁。"
                "文案=「服务热线:0599-2323239」｜烧录=libass。"
                "画幅叠出片内图形花字「何家安泰 草木长乐」。"
                "花字「家」不是第二个人物。标记烧录=libass的店号与热线禁止描字。"
            )
        }, ensure_ascii=False)

    draft = flower_burn_draft(_Shot())
    assert draft["source"] == "script"
    assert draft["lines"][0]["text"] == "何家安泰 草木长乐"
    assert draft["lines"][0]["companion"].count("0599-2323239") == 1
    assert draft["lines"][0]["text"] != "家"


def test_stage_burn_font_copies_simhei_beside_the_ass_file():
    windir = os.environ.get("WINDIR")
    if not windir or not os.path.isfile(os.path.join(windir, "Fonts", "simhei.ttf")):
        return
    work = tempfile.mkdtemp(prefix="flower_font_")
    try:
        family = stage_burn_font(work)
        assert family == "SimHei"
        assert os.path.isfile(os.path.join(work, "fonts", "simhei.ttf"))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_burn_style_uses_the_staged_cjk_font():
    ass = build_ass([{
        "text": "何家安泰",
        "start": 0,
        "end": 1,
        "font": "KaiTi",
    }], font_name="SimHei")
    assert "Style: Flower,SimHei," in ass
    assert "KaiTi" not in ass
