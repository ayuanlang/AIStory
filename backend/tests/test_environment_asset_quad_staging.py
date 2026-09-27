"""Staging waits on the environment-asset four-cell prompt and injects it."""

from app.services.scene_subskill_pipeline_runner import (
    PIPELINE_CONTRACT_VERSION,
    build_environment_asset_quad_injection,
    collect_staging_main_environment_names,
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


def test_injection_keeps_grid_cells_readable():
    wrapped = build_environment_asset_quad_injection({"客栈大堂": _quad()})
    assert "环境资产四宫格开始" in wrapped
    assert "环境资产四宫格结束" in wrapped
    assert "[0度格-左上·北]" in wrapped
    assert "[90度格-右上·东]" in wrapped
    assert "[180度格-左下·南]" in wrapped
    assert "[270度格-右下·西]" in wrapped
    assert "【主环境四宫格】客栈大堂" in wrapped
    assert build_environment_asset_quad_injection({"客栈大堂": "只有开篇"}) == ""


def test_pipeline_contract_injects_quad_before_staging():
    assert PIPELINE_CONTRACT_VERSION == "asset-quad-before-staging-v4"
    registry = get_script_analysis_flow_registry()
    nodes = {str(node.get("key")): node for node in (registry.get("nodes") or [])}
    chain = nodes["scene_subskill_pipeline"].get("injection_chain") or []
    assert "backend.environment_asset_quad.before_staging" in chain
    assert nodes["asset_design_environment"].get("depends_on") == ["environment_plan"]
