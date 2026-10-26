"""Staging waits on the environment-asset four-cell prompt and injects it."""

from app.services.scene_subskill_pipeline_runner import (
    PIPELINE_CONTRACT_VERSION,
    build_environment_asset_quad_injection,
    collect_staging_main_environment_names,
    compose_staging_scene_text,
    environment_asset_quad_ready,
)
from app.services.script_analysis_flow.registry import get_script_analysis_flow_registry


def _quad(name: str = "客栈大堂") -> str:
    return (
        f"【定位】{name}\n"
        "【四向拼图】\n"
        "2×2 四宫格；四宫度数=左上0度｜右上90度｜左下180度｜右下270度。\n"
        "[0度格-左上·北]\n左侧面：床在画面左。\n"
        "[90度格-右上·东]\n"
        "[180度格-左下·南]\n"
        "[270度格-右下·西]\n"
    )


def test_quad_name_match_ignores_spacing_and_fullwidth_bar():
    from app.services.scene_subskill_pipeline_runner import match_ready_environment_asset_quads

    loaded = {"客栈 大堂｜室内": _quad("客栈大堂")}
    ready = match_ready_environment_asset_quads(loaded, ["客栈大堂"])
    assert list(ready) == ["客栈大堂"]
    assert environment_asset_quad_ready(ready["客栈大堂"]) is True


def test_cancel_running_pipeline_closes_every_open_node():
    from types import SimpleNamespace
    from app.services.scene_subskill_pipeline_runner import cancel_running_pipeline_nodes

    waiting = SimpleNamespace(
        node_name="scene_subskill_scene",
        status="running",
        runtime_meta={"current_step": "wait_env_asset", "business_event": "waiting"},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
        updated_at=None,
    )
    done = SimpleNamespace(
        node_name="scene_subskill_scene",
        status="success",
        runtime_meta={},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
        updated_at=None,
    )
    design = SimpleNamespace(
        node_name="asset_design_environment",
        status="running",
        runtime_meta={},
        last_error_code=None,
        last_error_message=None,
        ended_at=None,
        updated_at=None,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return [waiting, done, design]

    class _Session:
        def query(self, *_args, **_kwargs):
            return _Query()

    assert cancel_running_pipeline_nodes(_Session(), episode_id=1) == 2
    assert waiting.status == "failed"
    assert waiting.last_error_code == "ANALYSIS_CANCELLED"
    assert waiting.runtime_meta["business_event"] == "cancelled"
    assert done.status == "success"
    assert design.status == "failed"
    assert design.last_error_code == "ANALYSIS_CANCELLED"


def test_canceled_task_status_counts_as_stop():
    from types import SimpleNamespace
    from app.services.task_manager import task_record_cancel_is_set

    assert task_record_cancel_is_set(SimpleNamespace(cancel_requested=False, status="canceled")) is True
    assert task_record_cancel_is_set(SimpleNamespace(cancel_requested=True, status="running")) is True
    assert task_record_cancel_is_set(SimpleNamespace(cancel_requested=False, status="running")) is False


def test_quad_ready_requires_all_four_cells():
    assert environment_asset_quad_ready(_quad()) is True
    assert environment_asset_quad_ready("【四向拼图】\n[0度格-左上") is False


def test_collect_main_env_names_skips_degree_derivatives():
    text = """
【主环境】客栈大堂｜室内
[ENV] 名称=客栈大堂｜复用=否｜来源=新建｜匹配主环境=无｜依据=场头
[ENV] 名称=0度客栈大堂｜复用=否｜来源=新建｜匹配主环境=客栈大堂｜依据=衍生
【主环境】飞行器驾驶舱
"""
    assert collect_staging_main_environment_names(text) == ["客栈大堂", "飞行器驾驶舱"]


def test_collect_main_env_names_skips_section_rule():
    text = """
────【主环境】────
【主环境】────
【主环境】────｜玄极科技总裁办｜环境族=普通｜日夜内外=黄昏·内
[SCENE_ENV_IDENT_START:EP00_SC01]
[ENV] 名称=大厦尖顶外空域｜复用=否｜来源=新建｜匹配主环境=无｜依据=场头
[ENV] 名称=────｜复用=否｜来源=新建｜匹配主环境=无｜依据=分隔
[ENV] 名称=上一世浮空艇机舱｜复用=否｜来源=新建｜匹配主环境=无｜依据=闪回
[SCENE_ENV_IDENT_END:EP00_SC01]
"""
    assert collect_staging_main_environment_names(text) == [
        "玄极科技总裁办",
        "大厦尖顶外空域",
        "上一世浮空艇机舱",
    ]


def test_collect_main_env_names_uses_matched_main_not_scene_nickname():
    text = """
【主环境】博弈室｜室内
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=博弈室｜复用=是｜来源=项目库｜匹配主环境=总裁办公室｜依据=闪回
[SCENE_ENV_IDENT_END:EP01_SC01]
"""
    assert collect_staging_main_environment_names(text) == ["总裁办公室"]


def test_settled_quad_node_is_not_still_open():
    from app.services.scene_subskill_pipeline_runner import environment_asset_quad_job_still_open

    assert environment_asset_quad_job_still_open("running") is True
    assert environment_asset_quad_job_still_open("") is True
    assert environment_asset_quad_job_still_open("success") is False
    assert environment_asset_quad_job_still_open("warning") is False


def test_unmatched_quad_is_not_a_wait():
    from fastapi import HTTPException
    from app.services.scene_subskill_pipeline_runner import (
        _scene_subskill_failure_reason,
        is_environment_asset_wait_error,
    )

    exc = HTTPException(
        status_code=422,
        detail="STAGING_ENVIRONMENT_ASSET_UNMATCHED:EP01_SC01:博弈室",
    )
    assert is_environment_asset_wait_error(exc) is False
    reason = _scene_subskill_failure_reason(exc)
    assert "等待" not in reason
    assert "对不上" in reason
    assert "博弈室" in reason


def test_unmatched_quad_reason_names_both_sides():
    from app.services.scene_subskill_pipeline_runner import (
        describe_unmatched_environment_asset_quads,
    )

    body = _quad("客栈大堂")
    loaded = {
        "客栈大堂": body,
        "Inn Hall": body,
        "博弈室": "【定位】博弈室\n只有开篇",
    }
    text = describe_unmatched_environment_asset_quads(
        loaded,
        ["客栈大堂", "博弈室", "总裁办公室"],
    )
    assert "客栈大堂" in text
    assert "已对上：客栈大堂" in text
    assert "博弈室（同名稿在，四宫未齐）" in text
    assert "总裁办公室（名字不在已有四宫格里）" in text
    assert "库中四宫格：客栈大堂" in text
    assert "Inn Hall" not in text
    assert "库中有稿但四宫未齐：博弈室" in text


def test_staging_scene_drops_env_block_and_keeps_ident():
    framing = (
        "[SCENE_START:EP01_SC01]\n"
        "[ENV_BLOCK_START]\n"
        "【主环境】客栈大堂\n"
        "【未落环境实体清单】\n"
        "- 屏风｜待入画\n"
        "[ENV_BLOCK_END]\n"
        "[BEAT_STREAM_START]\n"
        "人站在桌北。\n"
        "[BEAT_STREAM_END]\n"
    )
    env_scene = (
        "[SCENE_ENV_IDENT_START:EP01_SC01]\n"
        "[ENV] 名称=客栈大堂｜复用=否｜来源=新建｜匹配主环境=无｜依据=场头\n"
        "[SCENE_ENV_IDENT_END:EP01_SC01]\n"
        "[ENV_BLOCK_START]\n"
        "【主环境】客栈大堂｜日夜内外=白天·内\n"
        "[ENV_BLOCK_END]\n"
    )
    text = compose_staging_scene_text(framing, env_scene)
    assert "[ENV_BLOCK_START]" not in text
    assert "[ENV_BLOCK_END]" not in text
    assert "【未落环境实体清单】" not in text
    assert "屏风" not in text
    assert "[BEAT_STREAM_START]" in text
    assert "人站在桌北。" in text
    assert "[SCENE_ENV_IDENT_START:EP01_SC01]" in text
    assert "名称=客栈大堂" in text


def test_injection_keeps_grid_cells_readable():
    wrapped = build_environment_asset_quad_injection({"客栈大堂": _quad()})
    assert "环境资产四宫格开始" in wrapped
    assert "环境资产四宫格结束" in wrapped
    assert "【四向拼图】" in wrapped
    assert "【定位】" not in wrapped
    assert "0度望北，正面是北，左侧面是西，右侧面是东" in wrapped
    assert "90度望东，正面是东，左侧面是北，右侧面是南" in wrapped
    assert "180度望南，正面是南，左侧面是东，右侧面是西" in wrapped
    assert "270度望西，正面是西，左侧面是南，右侧面是北" in wrapped
    assert "[0度格-左上·北]" in wrapped
    assert "[90度格-右上·东]" in wrapped
    assert "[180度格-左下·南]" in wrapped
    assert "[270度格-右下·西]" in wrapped
    assert "【主环境四宫格】客栈大堂" in wrapped
    assert build_environment_asset_quad_injection({"客栈大堂": "只有开篇"}) == ""


def test_pipeline_contract_injects_quad_before_staging():
    assert PIPELINE_CONTRACT_VERSION == "asset-quad-before-staging-v5"
    registry = get_script_analysis_flow_registry()
    nodes = {str(node.get("key")): node for node in (registry.get("nodes") or [])}
    chain = nodes["scene_subskill_pipeline"].get("injection_chain") or []
    assert "backend.environment_asset_quad.before_staging" in chain
    assert nodes["asset_design_environment"].get("depends_on") == ["environment_plan"]
    assert nodes["asset_design_environment_quad"].get("depends_on") == ["asset_design_environment"]
    assert nodes["asset_design_environment_quad"].get("prompt_file") == (
        "skills/scene_analysis_feature_stack/environment_quad_prompt.md"
    )
    assert "asset_design_environment_quad" in (nodes["storyboard_generation"].get("depends_on") or [])


def test_art_direction_exposes_rerunnable_derived_environment_node():
    from pathlib import Path

    editor = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "editor" / "components" / "ScriptEditor.jsx"
    src = editor.read_text(encoding="utf-8")
    assert "assets_gen_derived" in src
    assert "handleRerunEnvironmentQuad" in src
    assert "openEnvironmentQuadRerunModal" in src
    assert "key: 'single', labelZh: '单个主环境'" in src
    assert "asset_design_environment_quad" in src
    assert "rerunKind: 'environment_quad'" in src
    assert "quadFailureEnvironmentNames" in src
    assert "四宫格按报错重跑缺失环境" in src
