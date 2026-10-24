import asyncio

from app.services.llm_service import LLMService


OVERLOAD = (
    'grsai供应商调用失败: API Error 400: {"error":{"message":"The model load is too high, '
    'please try again later","type":"rix_api_error"}}'
)


class _FakeAgent:
    def __init__(self, fallbacks):
        self._fallbacks = fallbacks

    def get_fallback_configs(self, *args, **kwargs):
        return list(self._fallbacks)

    def get_fallback_configs_by_ids(self, ids):
        return list(self._fallbacks)


def _patch_agent(monkeypatch, fallbacks):
    import app.services.agent_service as agent_mod

    monkeypatch.setattr(agent_mod, "agent_service", _FakeAgent(fallbacks))


def test_overload_marker_matches_grsai_400_and_ignores_plain_400():
    service = LLMService()
    assert service._is_immediate_provider_fallback_error(OVERLOAD) is True
    assert service._is_immediate_provider_fallback_error("API Error 400: invalid temperature") is False
    assert service._is_immediate_provider_fallback_error("API Error 429: too many requests") is True
    story = "请稍后再试，这场戏先停在门口。"
    assert service._result_requests_immediate_fallback({"content": story}, story) is False
    assert service._result_requests_immediate_fallback(
        {"content": "", "stream_error": OVERLOAD},
        "",
    ) is True


def test_generate_content_skips_active_retries_on_model_overload(monkeypatch):
    service = LLMService()
    calls = []
    fallbacks = [{"provider": "openai", "model": "gpt-backup", "config": {"__resolved_setting_id": 2}}]
    _patch_agent(monkeypatch, fallbacks)

    async def fake_generate(user_prompt, system_prompt, config, image_urls=None, video_urls=None):
        calls.append(config.get("model"))
        if config.get("model") == "gemini-3.8-flash":
            return {
                "content": "",
                "usage": {},
                "finish_reason": "incomplete",
                "stream_error": OVERLOAD,
            }
        return {"content": "fallback ok", "usage": {}, "finish_reason": "stop"}

    monkeypatch.setattr(service, "generate_content", fake_generate)

    async def _run():
        return await service.generate_content_with_fallback(
            "user",
            "system",
            {
                "provider": "grsai",
                "model": "gemini-3.8-flash",
                "config": {"__resolved_setting_id": 1, "__active_retry_attempts": 2},
            },
        )

    result = asyncio.run(_run())
    assert calls == ["gemini-3.8-flash", "gpt-backup"]
    assert result["content"] == "fallback ok"


def test_generate_content_still_retries_ordinary_empty_response(monkeypatch):
    service = LLMService()
    calls = []
    fallbacks = [{"provider": "openai", "model": "gpt-backup", "config": {"__resolved_setting_id": 2}}]
    _patch_agent(monkeypatch, fallbacks)

    async def fake_generate(user_prompt, system_prompt, config, image_urls=None, video_urls=None):
        calls.append(config.get("model"))
        if config.get("model") == "gemini-3.8-flash":
            return {"content": "", "usage": {}, "finish_reason": "stop"}
        return {"content": "fallback ok", "usage": {}, "finish_reason": "stop"}

    monkeypatch.setattr(service, "generate_content", fake_generate)

    async def _run():
        return await service.generate_content_with_fallback(
            "user",
            "system",
            {
                "provider": "grsai",
                "model": "gemini-3.8-flash",
                "config": {"__resolved_setting_id": 1, "__active_retry_attempts": 2},
            },
        )

    result = asyncio.run(_run())
    assert calls == ["gemini-3.8-flash", "gemini-3.8-flash", "gpt-backup"]
    assert result["content"] == "fallback ok"


def test_chat_completion_skips_active_retries_on_model_overload(monkeypatch):
    service = LLMService()
    calls = []
    fallbacks = [{"provider": "openai", "model": "gpt-backup", "config": {"__resolved_setting_id": 2}}]
    _patch_agent(monkeypatch, fallbacks)

    async def fake_chat(messages, config):
        calls.append(config.get("model"))
        if config.get("model") == "gemini-3.8-flash":
            return {
                "content": f"Error: {OVERLOAD}",
                "usage": {},
                "finish_reason": "error",
                "stream_error": OVERLOAD,
                "_immediate_fallback": True,
            }
        return {"content": "fallback ok", "usage": {}, "finish_reason": "stop"}

    monkeypatch.setattr(service, "chat_completion", fake_chat)

    async def _run():
        return await service.chat_completion_with_fallback(
            [{"role": "user", "content": "hi"}],
            {
                "provider": "grsai",
                "model": "gemini-3.8-flash",
                "config": {"__resolved_setting_id": 1, "__active_retry_attempts": 2},
            },
        )

    result = asyncio.run(_run())
    assert calls == ["gemini-3.8-flash", "gpt-backup"]
    assert result["content"] == "fallback ok"
