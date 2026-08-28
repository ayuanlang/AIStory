# -*- coding: utf-8 -*-
import json
from types import SimpleNamespace

from app.services.deletion_ops import (
    clear_episode_analysis_artifacts,
    reset_episode_analysis_progress,
)
from app.services.script_analysis_flow.analyze_scene_stages import (
    persist_assets_extraction_stage,
    persist_scene_subskill_step_result,
    persist_script_optimization_stage,
)


class _Query:
    def __init__(self, db, model):
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def populate_existing(self):
        return self

    def first(self):
        return self.db.episode

    def delete(self, synchronize_session=False):
        counts = getattr(self.db, "delete_counts", {})
        return int(counts.get(self.model, 2))


class _DummyDb:
    def __init__(self, episode=None, delete_counts=None):
        self.episode = episode
        self.episode_model = type(episode) if episode is not None else None
        self.delete_counts = delete_counts or {}
        self.committed = False

    def query(self, model):
        if self.episode is not None:
            self.episode_model = type(self.episode)
        return _Query(self, model)

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        return None


def test_persist_keeps_node_output_key():
    episode = SimpleNamespace(id=1, ai_scene_analysis_adaptation="", ai_stage_outputs="")
    persist_script_optimization_stage(
        db=_DummyDb(),
        episode=episode,
        result_content="[SCENES_BLOCK_START]\n[SCENE_START:EP01_SC01]\nbody\n[SCENE_END:EP01_SC01]\n[SCENES_BLOCK_END]",
        node_output_key="scene_split",
    )
    outputs = json.loads(episode.ai_stage_outputs)["stages"]["stage1"]["outputs"]
    assert "body" in outputs["scene_split"]["content"]
    assert "body" in outputs["adapted_script"]["content"]


def test_persist_subskill_step_merges_by_scene_and_step():
    episode = SimpleNamespace(id=7, ai_stage_outputs="")
    db = _DummyDb(episode=episode)
    persist_scene_subskill_step_result(
        db=db,
        episode_id=7,
        scene_id="EP01_SC01",
        step_key="drama",
        result_text="[SCENE_START:EP01_SC01]\ndrama\n[SCENE_END:EP01_SC01]",
    )
    persist_scene_subskill_step_result(
        db=db,
        episode_id=7,
        scene_id="EP01_SC01",
        step_key="framing",
        result_text="[SCENE_START:EP01_SC01]\nframing\n[SCENE_END:EP01_SC01]",
    )
    persist_scene_subskill_step_result(
        db=db,
        episode_id=7,
        scene_id="EP01_SC02",
        step_key="drama",
        result_text="[SCENE_START:EP01_SC02]\ndrama2\n[SCENE_END:EP01_SC02]",
    )
    result_map = json.loads(
        json.loads(episode.ai_stage_outputs)["stages"]["stage1"]["outputs"]["scene_subskill_results"]["content"]
    )
    assert "drama" in result_map["EP01_SC01"]["drama"]
    assert "framing" in result_map["EP01_SC01"]["framing"]
    assert "drama2" in result_map["EP01_SC02"]["drama"]
    assert db.committed


def test_load_subskill_results_accepts_object_content():
    from app.services.script_analysis_flow.analyze_scene_stages import (
        load_scene_subskill_results_map,
        merge_ai_stage_outputs_preserving_subskills,
    )

    episode = SimpleNamespace(
        id=9,
        ai_stage_outputs=json.dumps(
            {
                "version": 1,
                "stages": {
                    "stage1": {
                        "outputs": {
                            "scene_subskill_results": {
                                "key": "scene_subskill_results",
                                "content": {
                                    "EP01_SC01": {
                                        "drama": "[SCENE_START:EP01_SC01]\n文戏增强已完成的正文足够长\n[SCENE_END:EP01_SC01]"
                                    }
                                },
                            }
                        }
                    }
                },
            },
            ensure_ascii=False,
        ),
    )
    result_map = load_scene_subskill_results_map(_DummyDb(episode=episode), 9)
    assert "文戏增强已完成的正文足够长" in result_map["EP01_SC01"]["drama"]

    incoming = json.dumps(
        {
            "version": 1,
            "stages": {
                "stage1": {
                    "outputs": {
                        "scene_split": {"key": "scene_split", "content": "new split"}
                    }
                }
            },
        },
        ensure_ascii=False,
    )
    merged = json.loads(merge_ai_stage_outputs_preserving_subskills(episode.ai_stage_outputs, incoming))
    kept = json.loads(merged["stages"]["stage1"]["outputs"]["scene_subskill_results"]["content"])
    assert "文戏增强已完成的正文足够长" in kept["EP01_SC01"]["drama"]
    assert merge_ai_stage_outputs_preserving_subskills(episode.ai_stage_outputs, "") == ""
    assert merge_ai_stage_outputs_preserving_subskills(episode.ai_stage_outputs, "   ") == ""


def test_persist_assets_extraction_writes_stage2_slots():
    episode = SimpleNamespace(
        id=3,
        ai_scene_analysis_subject_index="",
        ai_stage_outputs="",
    )
    persist_assets_extraction_stage(
        db=_DummyDb(),
        episode=episode,
        result_content="| subject_no | name |\n| 1 | 主角 |",
    )
    outputs = json.loads(episode.ai_stage_outputs)["stages"]["stage2"]["outputs"]
    assert "主角" in episode.ai_scene_analysis_subject_index
    assert "主角" in outputs["subject_index"]["content"]
    assert "主角" in outputs["assets_extraction"]["content"]


def test_reset_episode_analysis_progress_deletes_all_progress_rows():
    from app.models.all_models import (
        ScriptProgressIssue,
        ScriptProgressPipelineNode,
        ScriptProgressSceneUnit,
    )

    db = _DummyDb(delete_counts={
        ScriptProgressSceneUnit: 4,
        ScriptProgressPipelineNode: 9,
        ScriptProgressIssue: 1,
    })
    summary = reset_episode_analysis_progress(db, project_id=1, episode_id=2)
    assert summary["removed_scene_units"] == 4
    assert summary["removed_pipeline_nodes"] == 9
    assert summary["removed_issues"] == 1


def test_clear_episode_analysis_artifacts_blanks_stage_fields():
    episode = SimpleNamespace(
        ai_scene_analysis_result="old split",
        ai_scene_analysis_adaptation="old adapt",
        ai_scene_analysis_subject_index="old si",
        ai_scene_analysis_scene_markdown="old md",
        ai_entity_design_result="old assets",
        ai_stage_outputs='{"stages":{"stage1":{}}}',
    )
    assert clear_episode_analysis_artifacts(episode) == 6
    assert episode.ai_stage_outputs == ""
    assert episode.ai_scene_analysis_adaptation == ""
    assert clear_episode_analysis_artifacts(episode) == 0
