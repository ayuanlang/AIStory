# -*- coding: utf-8 -*-
import asyncio

import pytest
from fastapi import HTTPException

from app.services.environment_plan_runner import (
    _ENVIRONMENT_COMPLETION_MARKER,
    _call_environment_plan_episode,
    _scene_patch_gap,
)


def _closed(body: str) -> str:
    return body.rstrip() + f"\n{_ENVIRONMENT_COMPLETION_MARKER}\n"


def _patch(scene_id: str) -> str:
    return (
        f"[ENV_SCENE_PATCH_START:{scene_id}]\n"
        f"[SCENE_ENV_IDENT_START:{scene_id}]\n"
        "[ENV] 名称=浮空飞行器驾驶舱｜复用=否｜来源=新建｜匹配主环境=无\n"
        f"[SCENE_ENV_IDENT_END:{scene_id}]\n"
        "[ENV_BLOCK_START]\n"
        "【主环境】浮空飞行器驾驶舱\n"
        "[ENV_BLOCK_END]\n"
        f"[ENV_SCENE_PATCH_END:{scene_id}]\n"
    )


def _install(monkeypatch, replies):
    calls = []

    def _attempts(db, function_name, system_api_id, node_key=""):
        return 7, [7, 8]

    async def _analyze(request, current_user=None, db=None, async_mode="0"):
        calls.append(int(request.system_api_id or 0))
        return {"content": replies[len(calls) - 1]}

    monkeypatch.setattr(
        "app.services.script_analysis_flow_runner.build_script_analysis_retry_api_attempts",
        _attempts,
    )
    monkeypatch.setattr(
        "app.api.routers.prompts.analyze_scene.analyze_scene",
        _analyze,
    )
    return calls


def _run(replies, monkeypatch):
    calls = _install(monkeypatch, replies)

    async def _go():
        return await _call_environment_plan_episode(
            db=object(),
            current_user=object(),
            base_payload={"text": "场", "system_api_id": 7},
            episode_input="场",
            node_project_id=0,
            node_episode_id=0,
            scene_ids=["TR01_SC01"],
        )

    return calls, asyncio.run(_go())


def test_missing_scene_patch_retries_then_accepts_the_envelope(monkeypatch):
    bare = _closed("舱" * 160 + "宿主环境=是:双子塔楼缝空域｜舱内环境=是:浮空飞行器驾驶舱")
    covered = _closed("舱" * 160 + "\n" + _patch("TR01_SC01"))
    calls, text = _run([bare, covered], monkeypatch)
    assert calls == [7, 8]
    assert "[ENV_SCENE_PATCH_START:TR01_SC01]" in text
    assert _scene_patch_gap(text, ["TR01_SC01"]) == ""


def test_missing_scene_patch_fails_only_after_the_retries(monkeypatch):
    bare = _closed("舱" * 160 + "依据=陆沉坐在浮空飞行器驾驶座上")
    calls = _install(monkeypatch, [bare, bare])

    async def _go():
        return await _call_environment_plan_episode(
            db=object(),
            current_user=object(),
            base_payload={"text": "场", "system_api_id": 7},
            episode_input="场",
            node_project_id=0,
            node_episode_id=0,
            scene_ids=["TR01_SC01"],
        )

    with pytest.raises(HTTPException) as caught:
        asyncio.run(_go())
    assert calls == [7, 8]
    assert caught.value.detail == "ENVIRONMENT_PLAN_SCENE_PATCH_MISSING:TR01_SC01"


def test_broken_patch_envelope_is_the_same_gap():
    mismatched = _closed(
        "舱" * 160
        + "\n[ENV_SCENE_PATCH_START:TR01_SC01]\n"
        + "[ENV_BLOCK_START]\n【主环境】舱\n[ENV_BLOCK_END]\n"
        + "[ENV_SCENE_PATCH_END:EP01_SC01]"
    )
    assert _scene_patch_gap(mismatched, ["TR01_SC01"]).startswith("ENV_SCENE_PATCH_ID_MISMATCH:")
