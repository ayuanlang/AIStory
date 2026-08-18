# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.services.analyze_scene_text_ops import _resolve_scene_beats_adapted_script_text
from app.services.script_analysis_flow import resolve_scene_units_for_markdown_orchestration
from app.services.subject_index_resolve import resolve_usable_episode_subject_index


NEW_SUBJECT_INDEX = """| subject_no | subject_type | subject_name_zh | subject_name_en |
|---|---|---|---|
| S001 | character | 新角色 | NewChar |
"""

OLD_SUBJECT_INDEX = """| subject_no | subject_type | subject_name_zh | subject_name_en |
|---|---|---|---|
| S001 | character | 旧角色 | OldChar |
"""

NEW_SCRIPT = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】新茶馆｜日·内
- Beat 1
[BEAT_START:1]
新剧本正文
[BEAT_END:1]
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]"""

OLD_SCRIPT = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】旧茶馆｜日·内
- Beat 1
[BEAT_START:1]
旧剧本正文
[BEAT_END:1]
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]"""


def test_resolve_subject_index_prefers_explicit_over_usable_episode_field():
    episode = SimpleNamespace(
        id=1,
        ai_scene_analysis_subject_index=OLD_SUBJECT_INDEX,
        ai_stage_outputs="",
    )
    resolved = resolve_usable_episode_subject_index(
        episode,
        explicit_subject_index=NEW_SUBJECT_INDEX,
        heal_episode_field=True,
    )
    assert "新角色" in resolved
    assert "旧角色" not in resolved
    assert "新角色" in str(episode.ai_scene_analysis_subject_index)


def test_scene_beats_adapted_script_keeps_request_markers_instead_of_episode_fallback():
    request_text = f"[优化后剧本 - Stage 2.2权威输入]\n{NEW_SCRIPT}"
    resolved = _resolve_scene_beats_adapted_script_text(request_text, OLD_SCRIPT)
    assert "新剧本正文" in resolved
    assert "旧剧本正文" not in resolved


def test_scene_units_do_not_fall_back_to_stale_episode_adaptation():
    units, source = resolve_scene_units_for_markdown_orchestration(
        db=None,
        user_text="",
        adapted_script_text="[SCENES_BLOCK_START]\n[SCENES_BLOCK_END]",
        project_id=0,
        episode_id=0,
        episode_adaptation_text=OLD_SCRIPT,
    )
    assert units == []
    assert "adapted_script" in source


def test_scene_units_parse_request_adapted_script():
    units, source = resolve_scene_units_for_markdown_orchestration(
        db=None,
        user_text="",
        adapted_script_text=NEW_SCRIPT,
        project_id=0,
        episode_id=0,
        episode_adaptation_text=OLD_SCRIPT,
    )
    assert source == "adapted_script"
    assert len(units) == 1
    assert "新剧本正文" in str(units[0].scene_text)
    assert "旧剧本正文" not in str(units[0].scene_text)
