from app.services.llm_service import LLMService, _copy_llm_log_trace_fields
from app.services.script_analysis_llm_config import _story_generator_action_label


def test_copy_llm_log_trace_fields_preserves_action_on_fallback():
    source = {
        "provider": "grsai",
        "config": {
            "__resolved_action": "环境规划",
            "__resolved_user_id": 3,
            "__resolved_user_name": "ylsystem",
            "__resolved_project_id": 646,
        },
    }
    dest = {
        "provider": "openai",
        "config": {
            "__resolved_setting_id": 99,
            "__resolved_source": "fallback:openai/gpt",
        },
    }
    copied = _copy_llm_log_trace_fields(source, dest)
    assert copied["config"]["__resolved_action"] == "环境规划"
    assert copied["config"]["__resolved_user_id"] == 3
    assert copied["config"]["__resolved_user_name"] == "ylsystem"
    assert copied["config"]["__resolved_project_id"] == 646
    assert copied["config"]["__resolved_setting_id"] == 99


def test_copy_llm_log_trace_fields_does_not_overwrite_existing_action():
    source = {"config": {"__resolved_action": "全局统筹"}}
    dest = {"config": {"__resolved_action": "文戏增强 · EP01_SC01"}}
    copied = _copy_llm_log_trace_fields(source, dest)
    assert copied["config"]["__resolved_action"] == "文戏增强 · EP01_SC01"


def test_llm_log_trace_keeps_parent_action_when_child_omits_it():
    service = LLMService()
    seen = {}
    with service._llm_log_trace({"__resolved_action": "环境规划"}):
        with service._llm_log_trace({"__resolved_setting_id": 12}):
            from app.services.llm_service import _llm_log_trace_ctx
            seen.update(_llm_log_trace_ctx.get() or {})
    assert seen["__resolved_action"] == "环境规划"
    assert seen["__resolved_setting_id"] == 12


def test_story_generator_action_label_fills_framework_and_outlines():
    assert _story_generator_action_label("structure_creative_input") == "剧本框架"
    assert _story_generator_action_label("structure_creative_input_classic_framework") == "剧本框架"
    assert _story_generator_action_label("generate_project_story_dna_global") == "分集大纲"
    assert _story_generator_action_label("generate_project_story_dna_global", "全剧信息") == "全剧信息"
    assert _story_generator_action_label("industry_analysis_ai_short_dramas") == "行业分析"
    assert _story_generator_action_label("unknown_context") == ""
