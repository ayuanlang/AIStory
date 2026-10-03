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
    resolve_burn_source,
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
    assert [event["text"] for event in events] == ["天地灵秀·何家乐享"]
    event = events[0]
    assert "家" in event["text"]
    assert event["companion"].count("0599-2323239") == 1
    assert "Hejia" in event["companion"]
    assert event["start"] == 8.0
    assert event["end"] == 12.0
    assert event["place"] == "中"
    assert event["seal"] == "乐章"


def test_close_card_burns_hotline_and_address_verbatim():
    block = (
        "(P1 0s–6s) 字卡专镜，Static Hold。文案=「廿載泓林·常暖人間」｜烧录=libass｜手写=禁｜字级=大。"
        "英文小字「SINCE 1997 HONG LIN」，字级=小。"
        "CTA=「订座热线：13706902999｜地址：福建省松溪县庙下98号」｜烧录=libass｜手写=禁｜字级=小｜落位=句下。"
        "本P无旁白。"
    )
    events = extract_libass_events(block, duration=6)
    assert events[0]["text"] == "廿載泓林·常暖人間"
    assert events[0]["size"] == "大"
    assert "订座热线：13706902999" in events[0]["companion"]
    assert "地址：福建省松溪县庙下98号" in events[0]["companion"]
    assert "垂询热线" not in events[0]["companion"]
    assert "SINCE 1997 HONG LIN" in events[0]["companion"]
    stripped = strip_libass_glyphs_from_prompt(block)
    assert "13706902999" not in stripped
    assert "福建省松溪县庙下98号" not in stripped
    assert "廿載泓林" not in stripped
    assert "禁止生成花字" in stripped


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
    assert len(dialogues) == 6
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
    assert "一盏灯，照见山河" in stripped
    assert "何家乐健康科技" in stripped
    assert "后期烧录" in stripped
    burned = strip_libass_glyphs_from_prompt(
        "画幅叠出片内图形花字「何以安康，家和人乐」｜出字=后期烧录｜听=无"
    )
    assert "何以安康，家和人乐" not in burned
    assert "画幅叠出片内图形花字" not in burned
    assert "禁止生成花字" in burned
    kept = strip_libass_glyphs_from_prompt(
        "画幅叠出片内图形花字「何以安康，家和人乐」｜出字=模型直出｜"
        "其下叠出联系行「服务热线：0599-2323239」，落位=句下，字级=小｜手写=禁"
    )
    assert "0599-2323239" in kept
    assert "何以安康，家和人乐" in kept
    assert extract_libass_events(kept, duration=4) == []
    dropped = strip_libass_glyphs_from_prompt("文案=「何以安康，家和人乐」｜出字=舍")
    assert "何以安康，家和人乐" not in dropped
    assert extract_libass_events(dropped, duration=4) == []


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
    glyphs = [
        line.rsplit("}", 1)[-1]
        for line in ass.splitlines()
        if line.startswith("Dialogue:") and "FlowerSeal" in line and r"\p1" not in line
    ]
    assert "乐章" not in main
    assert "".join(glyphs) == "乐章"
    box = next(line for line in ass.splitlines() if r"\p1" in line and "FlowerSeal" in line)
    side = int(box.split(" l ")[1].split(" ")[0])
    assert side >= 20 * 2
    assert r"\fsp" in main
    assert r"\p1" in ass
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


def test_stage_burn_font_prefers_kaiti_then_the_bundled_font():
    bundled = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "app", "assets", "fonts", "wqy-microhei.ttc"
    ))
    assert os.path.isfile(bundled)
    work = tempfile.mkdtemp(prefix="flower_font_")
    try:
        family = stage_burn_font(work)
        copied = os.listdir(os.path.join(work, "fonts"))
        windir = os.environ.get("WINDIR") or ""
        if os.path.isfile(os.path.join(windir, "Fonts", "simkai.ttf")):
            assert family == "KaiTi"
            assert "simkai.ttf" in copied
        else:
            assert family == "WenQuanYi Micro Hei"
            assert "wqy-microhei.ttc" in copied
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_reburn_uses_the_clean_plate_even_when_the_output_url_is_signed():
    notes = {
        "flower_ass_source_url": "https://cdn.example/clean.mp4",
        "flower_ass_output_url": "https://cdn.example/burned.mp4",
    }
    assert resolve_burn_source("https://cdn.example/burned.mp4?e=1&token=abc", notes) == "https://cdn.example/clean.mp4"
    assert resolve_burn_source("https://cdn.example/fresh.mp4", notes) == "https://cdn.example/fresh.mp4"


def test_reburn_restarts_from_the_original_even_after_two_passes():
    notes = {
        "flower_ass_origin_url": "https://cdn.example/origin.mp4",
        "flower_ass_source_url": "https://cdn.example/burned-once.mp4",
        "flower_ass_output_url": "https://cdn.example/burned-twice.mp4",
        "flower_ass_output_urls": [
            "https://cdn.example/burned-once.mp4",
            "https://cdn.example/burned-twice.mp4",
        ],
    }
    assert resolve_burn_source("https://cdn.example/burned-twice.mp4?token=1", notes) == "https://cdn.example/origin.mp4"
    assert resolve_burn_source("https://cdn.example/fresh.mp4", notes) == "https://cdn.example/fresh.mp4"


def test_playable_shot_video_is_not_replaced_by_an_older_asset_link():
    assert resolve_burn_source(
        "https://cdn.example/saved.mp4?e=new",
        {},
        origin_fallback="https://cdn.example/saved.mp4?e=old",
    ) == "https://cdn.example/saved.mp4?e=new"


def test_reburn_skips_an_unfinished_provider_content_url():
    notes = {}
    assert resolve_burn_source(
        "https://cdn.example/saved.mp4",
        notes,
        origin_fallback="https://dubai3000.xyz/v1/videos/task_x/content.mp4",
    ) == "https://cdn.example/saved.mp4"
    assert resolve_burn_source(
        "https://dubai3000.xyz/v1/videos/task_x/content.mp4",
        {"flower_ass_origin_url": "https://cdn.example/origin.mp4"},
    ) == "https://cdn.example/origin.mp4"


def test_reburn_prefers_the_latest_clean_plate_over_the_first_origin():
    notes = {
        "flower_ass_origin_url": "https://cdn.example/origin-old.mp4",
        "flower_ass_output_url": "https://cdn.example/flower_once.mp4",
        "flower_ass_output_urls": ["https://cdn.example/flower_once.mp4"],
    }
    assert resolve_burn_source(
        "https://cdn.example/flower_once.mp4?token=1",
        notes,
        origin_fallback="https://cdn.example/generated-new.mp4",
    ) == "https://cdn.example/generated-new.mp4"
    assert resolve_burn_source(
        "https://cdn.example/generated-newest.mp4",
        notes,
        origin_fallback="https://cdn.example/generated-new.mp4",
    ) == "https://cdn.example/generated-newest.mp4"


def test_reburn_recovers_past_a_source_that_is_already_burned():
    notes = {
        "flower_ass_source_url": "https://cdn.example/flower_once.mp4",
        "flower_ass_output_url": "https://cdn.example/flower_twice.mp4",
    }
    assert resolve_burn_source(
        "https://cdn.example/flower_twice.mp4?token=1",
        notes,
        origin_fallback="https://cdn.example/origin.mp4",
    ) == "https://cdn.example/origin.mp4"


def test_style_json_sets_colors_and_ignores_rewritten_copy():
    from app.services.flower_text_ass import parse_flower_style

    style = parse_flower_style(
        '{"title_color":"#112233","companion_color":"#AABBCC","seal_color":"#CC1122",'
        '"shadow":0.2,"rule":false,"seal_scale":1.2,"text":"错字"}'
    )
    assert style["title_color"][:3] == (0x11, 0x22, 0x33)
    assert style["companion_color"][:3] == (0xAA, 0xBB, 0xCC)
    assert style["seal_color"][:3] == (0xCC, 0x11, 0x22)
    assert style["shadow"] == 0.2
    assert style["rule"] is False
    assert style["seal_scale"] == 1.2
    assert "text" not in style
    fallback = parse_flower_style("Error: no key")
    assert fallback["title_color"][:3] == (252, 246, 230)
    assert fallback["rule"] is False


def test_title_plate_is_a_transparent_image_with_a_square_seal():
    from PIL import Image

    from app.services.flower_text_ass import render_title_plate, resolve_cjk_font_file

    plate = render_title_plate({
        "text": "何以安康，家和人乐",
        "companion": "公司服务热线:0599-2323239",
        "seal": "朱文",
        "place": "中",
        "size": "大",
    }, width=1920, height=1080, font_path=resolve_cjk_font_file())
    assert isinstance(plate, Image.Image)
    assert plate.mode == "RGBA"
    assert plate.size == (1920, 1080)
    assert plate.getextrema()[3][1] > 200
    pixels = plate.load()
    minx, miny, maxx, maxy = 1920, 1080, 0, 0
    for y in range(1080):
        for x in range(1920):
            red, green, blue, alpha = pixels[x, y]
            if alpha > 180 and red > 120 and green < 80 and blue < 80:
                minx, miny = min(minx, x), min(miny, y)
                maxx, maxy = max(maxx, x), max(maxy, y)
    box_w, box_h = maxx - minx, maxy - miny
    assert box_w > 70 and box_h > 70
    assert abs(box_w - box_h) < 8


def test_burn_uses_art_direction_from_a_sibling_sentence():
    events = extract_libass_events(
        "画幅叠出片内图形花字「何家安泰」，字体=现代宽宋，字色=象牙白(#F3F5F7)，"
        "艺术化=书法+双色套印+印章+浅金渐变。"
        "(P1 0s–4s) 文案=「何以安康，家和人乐」｜烧录=libass｜手写=禁",
        duration=4,
    )
    assert events[0]["text"] == "何以安康，家和人乐"
    assert events[0]["font_kind"] == "brush"
    assert events[0]["look"]["duotone"] is True
    assert events[0]["look"]["gradient"] is True
    assert events[0]["look"]["painted"] is True
    assert events[0]["look"]["wide"] is True
    from app.services.flower_text_ass import render_title_plate, resolve_cjk_font_file

    plate = render_title_plate(
        events[0],
        width=1280,
        height=720,
        font_path=resolve_cjk_font_file(),
    )
    ivory = gold = 0
    pixels = plate.load()
    for y in range(720):
        for x in range(1280):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 180:
                continue
            if red > 220 and green > 210 and blue > 200:
                ivory += 1
            elif red > 190 and 120 < green < 210 and blue < 160:
                gold += 1
    assert ivory > 200
    assert gold > 200


def test_burn_look_follows_the_script_face_and_color():
    from app.services.flower_text_ass import script_flower_look

    gold_brush = script_flower_look("文案=「何以安康」｜字体=楷体｜字色=浅金｜强调体=书法｜艺术=烫金")
    assert gold_brush["font_kind"] == "brush"
    assert gold_brush["title_color"][:3] == (232, 196, 122)
    assert gold_brush["painted"] is True
    assert gold_brush["locked"] is True
    song = script_flower_look("文案=「店号」｜字体=宋体｜字色=#112233")
    assert song["font_kind"] == "song"
    assert song["title_color"][:3] == (0x11, 0x22, 0x33)
    assert song["painted"] is False
    events = extract_libass_events(
        "花字规范=字体=魏碑｜字色=墨\n文案=「何家安泰」｜烧录=libass｜手写=禁",
        duration=4,
    )
    assert events[0]["font_kind"] == "weibei"
    assert events[0]["look"]["title_color"][:3] == (36, 32, 28)


def test_large_title_matches_painted_title_scale():
    from app.services.flower_text_ass import render_title_plate, resolve_cjk_font_file, resolve_title_font_file

    plate = render_title_plate({
        "text": "何家安泰 草木长乐",
        "place": "中",
        "size": "大",
    }, width=1280, height=720, font_path=resolve_cjk_font_file(), title_font_path=resolve_title_font_file())
    pixels = plate.load()
    miny, maxy = 720, 0
    for y in range(720):
        hit = False
        for x in range(1280):
            red, green, blue, alpha = pixels[x, y]
            if alpha > 140 and red > 180 and green > 160:
                hit = True
                break
        if hit:
            miny = min(miny, y)
            maxy = y
    assert maxy > miny
    assert maxy - miny >= int(720 * 0.12)
    assert os.path.basename(resolve_title_font_file()) == "MaShanZheng-Regular.ttf"


def test_burn_style_uses_the_staged_cjk_font():
    ass = build_ass([{
        "text": "何家安泰",
        "start": 0,
        "end": 1,
        "font": "KaiTi",
    }], font_name="SimHei")
    assert "Style: Flower,SimHei," in ass
    assert "KaiTi" not in ass
