# -*- coding: utf-8 -*-
from app.services.shot_generation_prompts import _build_project_prompt_context
from app.services.space_occupancy_continuity import render_occupancy_reference


def test_script_nodes_drop_shot_runtime_from_project_context():
    info = {
        "script_title": "夜堂",
        "language": "中文",
        "shot_preference": "短镜头 / Short Take",
        "max_shot_seconds": 12,
        "expected_model_family": "seedance",
        "tech_params": {"visual_standard": {"aspect_ratio": "16:9", "image_size": "1024"}},
    }
    full = _build_project_prompt_context(info)
    slim = _build_project_prompt_context(info, shot_controls=False, image_runtime=False)
    full_text = str(full["project_context_section"])
    slim_text = str(slim["project_context_section"])
    assert "分镜最长秒数" in full_text
    assert "镜头偏好" in full_text
    assert "Expected Model Family" in full_text
    assert "first-class constraints" not in full_text
    assert "夜堂" in slim_text
    assert "16:9" in slim_text
    assert "分镜最长秒数" not in slim_text
    assert "镜头偏好" not in slim_text
    assert "Expected Model Family" not in slim_text
    assert "Image Size" not in slim_text
    assert slim["metadata"]["max_shot_seconds"] == 12


def test_occupancy_injection_keeps_the_map_without_the_judgment_essay():
    from app.services.space_occupancy_continuity import records_from_framing

    framing = """
[BEAT_START:1]
【角色道具世界分布图】
基准=主环境:办公室
CHAR:[@甲]｜在场=仍在｜锚=办公桌北椅｜X=轴上｜Y=南一臂｜Z=椅面
[BEAT_END:1]
"""
    rows = records_from_framing(
        framing_text=framing,
        time_text="【本场时地】季节=秋｜时段=白天｜时辰=巳｜光变档=日南",
        episode_number=1,
        episode_id=1,
        scene_id="EP01_SC02",
    )
    block = render_occupancy_reference(
        rows,
        current_text="【本场时地】季节=秋｜时段=白天｜光变档=日南",
    )
    assert "先判这一处环境是否已经结束" not in block
    assert "判定=未结束" in block
    assert "CHAR:[@甲]" in block
