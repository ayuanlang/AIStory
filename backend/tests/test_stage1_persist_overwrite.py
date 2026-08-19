# -*- coding: utf-8 -*-
import json
from types import SimpleNamespace

from app.services.script_analysis_flow.analyze_scene_stages import (
    extract_stage1_adapted_script_body,
    persist_script_optimization_stage,
)


NEW_VISUAL_BACKFILL = """{
  "project_visual_backfill": {
    "Global_Style": "冷峻写实",
    "borrowed_films": ["电影A"],
    "tone": "克制",
    "color_spectrum": "冷暖对比｜依据：对标电影A",
    "plot_summary": "主线=对质｜冲突=逼账｜结果=出逃",
    "music_recommendation": "风格=弦乐｜情绪=压迫"
  }
}"""

NEW_SCRIPT = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】新茶馆｜日·内
新剧本正文
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]

### 第三部分：Project Visual Backfill
```json
""" + NEW_VISUAL_BACKFILL + """
```"""

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
    assert "project_visual_backfill" not in extracted
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
                            "project_visual_backfill": {
                                "key": "project_visual_backfill",
                                "kind": "json",
                                "title": "全局风格",
                                "content": "{\"project_visual_backfill\":{\"Global_Style\":\"旧风格\"}}",
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
    visual = outputs["stages"]["stage1"]["outputs"]["project_visual_backfill"]["content"]
    assert "新剧本正文" in adapted
    assert "旧剧本正文" not in adapted
    assert "新剧本正文" in raw
    assert "old raw" not in raw
    assert "冷峻写实" in visual
    assert "旧风格" not in visual
    parsed_visual = json.loads(visual)
    assert parsed_visual["project_visual_backfill"]["Global_Style"] == "冷峻写实"


def test_persist_clears_stale_visual_backfill_when_json_missing():
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
                            "adapted_script": {"key": "adapted_script", "content": OLD_SCRIPT},
                            "raw_text": {"key": "raw_text", "content": "old raw"},
                            "project_visual_backfill": {
                                "key": "project_visual_backfill",
                                "kind": "json",
                                "title": "全局风格",
                                "content": "{\"project_visual_backfill\":{\"Global_Style\":\"旧风格\"}}",
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
        result_content="[SCENES_BLOCK_START]\n[SCENE_START:EP01_SC01]\n无JSON\n[SCENE_END:EP01_SC01]\n[SCENES_BLOCK_END]",
    )

    outputs = json.loads(episode.ai_stage_outputs)
    visual = outputs["stages"]["stage1"]["outputs"]["project_visual_backfill"]["content"]
    assert visual == ""
    assert "旧风格" not in visual
