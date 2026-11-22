# -*- coding: utf-8 -*-
from app.services.generation_runtime.multi_panel_preview_ref import (
    append_multi_panel_order_note,
    append_preview_ref,
    build_multi_panel_order_note,
    limit_refs_keeping_preview,
    resolve_multi_panel_preview,
)


def test_resolve_prefers_multi_panel_url_and_known_preset():
    url, preset = resolve_multi_panel_preview({
        "multi_panel_image_url": "https://cdn.example/grid.png",
        "storyboard_url": "https://cdn.example/other.png",
        "multi_panel_image_preset": "6panel",
    })
    assert url == "https://cdn.example/grid.png"
    assert preset == "6panel"


def test_resolve_falls_back_to_storyboard_url():
    url, preset = resolve_multi_panel_preview({
        "storyboard_url": "https://cdn.example/board.png",
        "multi_panel_image_preset": "not-a-grid",
    })
    assert url == "https://cdn.example/board.png"
    assert preset == ""


def test_four_panel_note_names_reading_order_and_image_index():
    note = build_multi_panel_order_note(3, "4panel")
    assert "参考@Image3" in note
    assert "左上第1格，右上第2格，左下第3格，右下第4格" in note
    assert "1→2→3→4" in note
    assert "Do not output a split-screen" in note


def test_larger_grids_keep_their_own_order():
    six = build_multi_panel_order_note(1, "6panel")
    nine = build_multi_panel_order_note(2, "9panel")
    two = build_multi_panel_order_note(1, "2panel")
    assert "第4、5、6格" in six
    assert "1→2→3→4→5→6→7→8→9" in nine
    assert "@Image2" in nine
    assert "左边第1格，右边第2格" in two


def test_unknown_preset_follows_the_numerals_on_the_grid():
    note = build_multi_panel_order_note(1, "")
    assert "阿拉伯数字" in note
    assert "数字从小到大" in note


def test_append_note_uses_the_submitted_index_and_does_not_duplicate():
    urls = ["https://cdn.example/a.png", "https://cdn.example/grid.png"]
    once, index = append_multi_panel_order_note(
        "角色走进门。",
        urls,
        "https://cdn.example/grid.png",
        "4panel",
    )
    assert index == 2
    assert once.count("【分镜预览多画格】") == 1
    assert "参考@Image2" in once
    twice, index_again = append_multi_panel_order_note(once, urls, urls[1], "4panel")
    assert index_again == 2
    assert twice.count("【分镜预览多画格】") == 1
    assert twice.startswith("角色走进门。")


def test_missing_grid_leaves_the_prompt_unchanged():
    text, index = append_multi_panel_order_note("保持原样", ["https://cdn.example/a.png"], "", "4panel")
    assert text == "保持原样"
    assert index == 0


def test_limit_keeps_the_grid_and_drops_the_tail_ahead_of_it():
    urls = append_preview_ref(
        ["https://cdn.example/1.png", "https://cdn.example/2.png", "https://cdn.example/3.png"],
        "https://cdn.example/grid.png",
    )
    kept = limit_refs_keeping_preview(urls, 3, "https://cdn.example/grid.png")
    assert kept == [
        "https://cdn.example/1.png",
        "https://cdn.example/2.png",
        "https://cdn.example/grid.png",
    ]


def test_limit_preserves_order_when_the_grid_already_fits():
    urls = [
        "https://cdn.example/1.png",
        "https://cdn.example/grid.png",
        "https://cdn.example/2.png",
    ]
    assert limit_refs_keeping_preview(urls, 9, urls[1]) == urls
