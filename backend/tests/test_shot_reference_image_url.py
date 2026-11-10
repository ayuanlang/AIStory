# -*- coding: utf-8 -*-
"""Shot refs use the current four-grid cell, not a derivative portrait from the previous sheet."""

from app.services.generation_runtime.video_ref_pipeline import (
    _collect_prompt_entity_ref_images,
    _entity_lookup_alias_keys,
)


def _lookup(*rows):
    lookup = {}
    for row in rows:
        for key in _entity_lookup_alias_keys(row.get("name"), row.get("name_en")):
            lookup.setdefault(key, row)
    return lookup


def _main(image_url, cells, source_url):
    return {
        "entity_id": 1,
        "name": "城门大街",
        "entity_type": "environment",
        "image_url": image_url,
        "generation_prompt_cn": "四宫度数=左上0度｜右上90度｜左下180度｜右下270度",
        "custom_attributes": {
            "quad_cell_images": {
                "source_url": source_url,
                "cells": cells,
            },
        },
    }


def _derived(image_url, *, kind="first_cut", name="90度城门大街"):
    return {
        "entity_id": 2,
        "name": name,
        "entity_type": "environment",
        "image_url": image_url,
        "generation_prompt_cn": "只切割。所属主环境=城门大街。angle_key=城门大街|90。",
        "custom_attributes": {
            "derived_kind": kind,
            "main_environment": "城门大街",
            "view_angle_from_main": 90,
        },
        "visual_dependencies": ["ENV:[城门大街]"],
    }


def test_current_cell_replaces_old_derivative_portrait():
    main = _main(
        "https://cdn.example/main.jpg",
        {"右上": "https://cdn.example/tr.jpg"},
        "https://cdn.example/main.jpg",
    )
    derived = _derived("https://cdn.example/derived-old.jpg")
    refs = _collect_prompt_entity_ref_images(
        "ENV:[90度城门大街] ENV:[城门大街]",
        _lookup(main, derived),
    )
    assert refs == ["https://cdn.example/tr.jpg"]


def test_stale_cell_is_omitted_after_the_sheet_changes():
    main = _main(
        "https://cdn.example/main-new.jpg",
        {"右上": "https://cdn.example/tr-old.jpg"},
        "https://cdn.example/main.jpg",
    )
    derived = _derived("https://cdn.example/tr-old.jpg")
    refs = _collect_prompt_entity_ref_images("ENV:[90度城门大街]", _lookup(main, derived))
    assert refs == []


def test_character_and_special_cut_keep_their_own_image():
    main = _main(
        "https://cdn.example/main.jpg",
        {"右上": "https://cdn.example/tr.jpg"},
        "https://cdn.example/main.jpg",
    )
    character = {
        "entity_id": 9,
        "name": "陆青",
        "entity_type": "character",
        "image_url": "https://cdn.example/face.jpg",
    }
    special = _derived(
        "https://cdn.example/up.jpg",
        kind="special",
        name="90度城门大街_仰天",
    )
    special["generation_prompt_cn"] = "所属主环境=城门大街。angle_key=城门大街|90。禁止只做平视宫格原样切割。特别表述=仰天。"
    assert _collect_prompt_entity_ref_images("CHAR:[陆青]", _lookup(character)) == ["https://cdn.example/face.jpg"]
    assert _collect_prompt_entity_ref_images("ENV:[90度城门大街_仰天]", _lookup(main, special)) == [
        "https://cdn.example/up.jpg"
    ]
