# -*- coding: utf-8 -*-
import json
from types import SimpleNamespace

from app.services.script_analysis_flow.analyze_scene_stages import (
    extract_stage1_adapted_script_body,
    persist_script_optimization_stage,
)


NEW_SCRIPT = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】新茶馆｜日·内
新剧本正文
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]"""

OLD_SCRIPT = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】旧茶馆｜日·内
旧剧本正文
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]"""


class _DummyDb:
    def commit(self):
        return None

    def refresh(self, _obj):
        return None


def test_extract_without_part2_heading_uses_scenes_block():
    raw = "前言说明\n" + NEW_SCRIPT + "\n### Subject Index\n| subject_no |"
    extracted = extract_stage1_adapted_script_body(raw)
    assert "[SCENES_BLOCK_START]" in extracted
    assert "新剧本正文" in extracted
    assert "Subject Index" not in extracted
    assert "前言说明" not in extracted


def test_extract_with_part2_heading_still_keeps_scenes_block():
    raw = "### 第二部分：修改后的剧本\n" + NEW_SCRIPT
    extracted = extract_stage1_adapted_script_body(raw)
    assert "新剧本正文" in extracted
    assert "[SCENE_START:EP01_SC01]" in extracted


def test_persist_overwrites_old_adaptation_and_stage_outputs():
    episode = SimpleNamespace(
        id=1,
        ai_scene_analysis_adaptation=OLD_SCRIPT,
        ai_stage_outputs=json.dumps(
            {
                "version": 1,
                "stages": {
                    "stage1": {
                        "key": "stage1",
                        "outputs": {
                            "adapted_script": {
                                "key": "adapted_script",
                                "content": OLD_SCRIPT,
                            },
                            "raw_text": {
                                "key": "raw_text",
                                "content": "old raw",
                            },
                        },
                    }
                },
            },
            ensure_ascii=False,
        ),
    )

    persist_script_optimization_stage(
        db=_DummyDb(),
        episode=episode,
        result_content=NEW_SCRIPT,
    )

    assert "新剧本正文" in episode.ai_scene_analysis_adaptation
    assert "旧剧本正文" not in episode.ai_scene_analysis_adaptation

    outputs = json.loads(episode.ai_stage_outputs)
    adapted = outputs["stages"]["stage1"]["outputs"]["adapted_script"]["content"]
    raw = outputs["stages"]["stage1"]["outputs"]["raw_text"]["content"]
    assert "新剧本正文" in adapted
    assert "旧剧本正文" not in adapted
    assert "新剧本正文" in raw
    assert "old raw" not in raw
