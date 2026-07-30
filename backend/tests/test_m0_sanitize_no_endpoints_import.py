# -*- coding: utf-8 -*-
"""M0 guard: script analysis must not import app.api.endpoints for sanitize."""
from __future__ import annotations

import sys


def _drop_modules(prefixes: tuple[str, ...]) -> None:
    for name in list(sys.modules):
        if name.startswith(prefixes):
            sys.modules.pop(name, None)


def test_sanitize_module_standalone():
    _drop_modules(("app.services.llm_markdown_sanitize", "app.api.endpoints"))
    from app.services.llm_markdown_sanitize import (
        sanitize_llm_markdown_output,
        sanitize_subject_index_text,
    )

    assert "app.api.endpoints" not in sys.modules
    cleaned = sanitize_llm_markdown_output("<think>x</think>\n# Title\nbody")
    assert cleaned.startswith("# Title")
    idx = sanitize_subject_index_text(
        "I will analyze first.\n## Subject Index\n| subject_no | subject_type |\n| S001 | character |"
    )
    assert "Subject Index" in idx
    assert "S001" in idx


def test_sanitize_subject_index_keeps_rows_without_title():
    _drop_modules(("app.services.llm_markdown_sanitize", "app.api.endpoints"))
    from app.services.llm_markdown_sanitize import sanitize_subject_index_text
    from app.services.subject_index_resolve import _subject_index_has_usable_content

    # Fullwidth pipes + no ### Subject Index title should still be recoverable.
    raw = (
        "----------------*****--------------\n"
        "｜ S001 ｜ character ｜ 林月 ｜ Lin Yue ｜ None ｜ None ｜ age_tier:青年 ｜ 林月 ｜"
    )
    idx = sanitize_subject_index_text(raw)
    assert "S001" in idx
    assert _subject_index_has_usable_content(idx)


def test_sanitize_subject_index_table_before_delimiter():
    _drop_modules(("app.services.llm_markdown_sanitize", "app.api.endpoints"))
    from app.services.llm_markdown_sanitize import sanitize_subject_index_text
    from app.services.subject_index_resolve import _subject_index_has_usable_content

    raw = (
        "### Subject Index\n"
        "| subject_no | subject_type | subject_name_zh |\n"
        "| S001 | character | 林月 |\n"
        "----------------*****--------------\n"
    )
    idx = sanitize_subject_index_text(raw)
    assert _subject_index_has_usable_content(idx)
    assert "S001" in idx


def test_analyze_scene_stages_import_does_not_load_endpoints():
    _drop_modules(
        (
            "app.api.endpoints",
            "app.services.script_analysis_flow",
            "app.services.llm_markdown_sanitize",
        )
    )
    from app.services.script_analysis_flow import analyze_scene_stages  # noqa: F401

    assert "app.api.endpoints" not in sys.modules
    assert hasattr(analyze_scene_stages, "persist_assets_extraction_stage")
