# -*- coding: utf-8 -*-
from app.services.shot_ai_generation_ops import (
    _SCENE_SHOT_GEN_IN_FLIGHT,
    _acquire_scene_shot_generation,
    _release_scene_shot_generation,
    should_skip_scene_shot_llm,
)


def test_scene_shot_generation_rejects_second_acquire_until_release():
    scene_id = 909001
    _release_scene_shot_generation(scene_id)
    try:
        assert _acquire_scene_shot_generation(scene_id) is True
        assert _acquire_scene_shot_generation(scene_id) is False
        assert scene_id in _SCENE_SHOT_GEN_IN_FLIGHT
    finally:
        _release_scene_shot_generation(scene_id)
    assert scene_id not in _SCENE_SHOT_GEN_IN_FLIGHT
    assert _acquire_scene_shot_generation(scene_id) is True
    _release_scene_shot_generation(scene_id)


def test_skip_shot_llm_when_shots_already_stored():
    assert should_skip_scene_shot_llm(existing_shot_count=3, replace_existing=False, attempt_index=1) is True
    assert should_skip_scene_shot_llm(existing_shot_count=3, replace_existing=True, attempt_index=1) is False
    assert should_skip_scene_shot_llm(existing_shot_count=3, replace_existing=True, attempt_index=2) is True
    assert should_skip_scene_shot_llm(existing_shot_count=0, replace_existing=False, attempt_index=2) is False
