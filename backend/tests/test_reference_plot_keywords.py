# -*- coding: utf-8 -*-
from app.services.llm_service import LLMService
from app.services.reference_plot_keywords import (
    apply_reference_plot_search_tools,
    attach_reference_plot_search,
    format_reference_plot_block,
    parse_reference_plot_keywords,
    search_tool_was_rejected,
    search_tools_for_submission,
)
from app.services.story_episode_coverage import _fill_user_prompt


def test_parse_fenced_json_and_chinese_aliases_with_limits():
    raw = """```json
{"作品": ["甲", "乙", "丙", "丁", "戊", "己", "庚"], "关键字": "对峙、反转、对峙", "搜索": ["甲 剧情", "乙 plot"]}
```"""
    parsed = parse_reference_plot_keywords(raw)
    assert parsed["works"] == ["甲", "乙", "丙", "丁", "戊", "己"]
    assert parsed["plot_keywords"] == ["对峙", "反转"]
    assert parsed["queries"] == ["甲 剧情", "乙 plot"]


def test_empty_keywords_format_to_no_block():
    assert format_reference_plot_block({"works": [], "plot_keywords": [], "queries": []}, stage="framework") == ""


def test_search_tool_shapes():
    flagged = {"__reference_plot_search": True, "has_google_search": True}
    assert search_tools_for_submission("kie", "gemini-2.5-pro", {"__reference_plot_search": True}, transport="gemini") == [
        {"googleSearch": {}}
    ]
    assert search_tools_for_submission("google", "gemini-2.5-flash", {"__reference_plot_search": True}, transport="chat") == [
        {"google_search": {}}
    ]
    assert search_tools_for_submission("openai", "gpt-4.1", flagged, transport="chat") == [{"type": "web_search"}]
    assert search_tools_for_submission("anthropic", "claude-sonnet-4-5", flagged, transport="claude") == [
        {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
    ]
    assert search_tools_for_submission("openai", "gpt-4.1", {"__reference_plot_search": True}, transport="chat") == []
    assert search_tools_for_submission("google", "gemini-2.5-pro", {"__reference_plot_search": False}, transport="gemini") == []
    assert search_tools_for_submission("google", "gemini-image", {"__reference_plot_search": True}, transport="chat") == []


def test_attach_only_when_terms_exist_and_apply_does_not_duplicate():
    empty = attach_reference_plot_search({"model": "gemini-2.5-pro", "config": {}}, {})
    assert empty["config"]["__reference_plot_search"] is False
    bound = attach_reference_plot_search(
        {"model": "gemini-2.5-pro", "config": {"tools": [{"google_search": {}}]}},
        {"works": ["甲"], "queries": ["甲 剧情"]},
    )
    assert bound["config"]["__reference_plot_search"] is True
    payload = {"tools": [{"google_search": {}}]}
    apply_reference_plot_search_tools(
        payload,
        provider="google",
        model="gemini-2.5-pro",
        extra_config=bound["config"],
        transport="chat",
    )
    assert payload["tools"] == [{"google_search": {}}]


def test_search_tool_was_rejected():
    assert search_tool_was_rejected(Exception("HTTP 400 unknown field tools"))
    assert search_tool_was_rejected(Exception("422 google_search is not supported"))
    assert not search_tool_was_rejected(Exception("HTTP 500 internal error"))
    assert not search_tool_was_rejected(Exception("400 rate limit"))


def test_kie_gemini_normalizes_google_search_and_response_rejection():
    service = LLMService.__new__(LLMService)
    assert service._kie_gemini_tools([{"google_search": {}}]) == [{"googleSearch": {}}]
    assert LLMService._response_rejects_reference_search(
        {"finish_reason": "error", "stream_error": "API Error 400: tools unsupported", "reply": ""}
    )
    assert not LLMService._response_rejects_reference_search(
        {"finish_reason": "stop", "reply": "正文提到 tools 但生成成功"}
    )


def test_search_emphasis_differs_by_stage():
    keywords = {"works": ["甲"], "plot_keywords": ["加压"], "queries": ["甲 结构"]}
    framework = format_reference_plot_block(keywords, stage="framework")
    outline = format_reference_plot_block(keywords, stage="outline")
    episode = format_reference_plot_block(keywords, stage="episode")
    assert "整体架构" in framework
    assert "不要用这次搜索去找对白原句" in framework
    assert "分成连续的集" in outline
    assert "不要用这次搜索去找某一场的对白" in outline
    assert "对白细节" in episode and "动作细节" in episode
    assert "表情驱动" in episode and "具体剧情的驱动细节" in episode
    assert "不把整部架构再搜一遍" in episode


def test_fill_prompt_keeps_reference_block():
    text = _fill_user_prompt("已完成集", [2], 8, registry_block="登记", reference_block="【借鉴剧情检索】\n作品=甲")
    assert text.index("【借鉴剧情检索】") < text.index("计划集数")
    assert "登记" in text
