# -*- coding: utf-8 -*-
from app.services.shot_ai_generation_ops import (
    _SCENE_SHOT_GEN_IN_FLIGHT,
    _acquire_scene_shot_generation,
    _release_scene_shot_generation,
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
