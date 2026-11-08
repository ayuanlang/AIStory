"""KIE Grok chat models use POST /grok/v1/responses, not /{model}/v1/chat/completions."""

from app.services.llm_service import LLMService


def test_grok_4_7_uses_responses_endpoint():
    svc = LLMService()
    root, model, url, kind = svc._resolve_kie_llm_url("https://api.kie.ai", "grok-4-7")
    assert root == "https://api.kie.ai"
    assert model == "grok-4-7"
    assert url == "https://api.kie.ai/grok/v1/responses"
    assert kind == "responses"


def test_grok_dot_alias_and_saved_chat_completions_url():
    svc = LLMService()
    _, model, url, kind = svc._resolve_kie_llm_url(
        "https://api.kie.ai/grok-4.7/v1/chat/completions",
        "grok-4.7",
    )
    assert model == "grok-4-7"
    assert url == "https://api.kie.ai/grok/v1/responses"
    assert kind == "responses"


def test_gpt_still_uses_codex_responses():
    svc = LLMService()
    _, model, url, kind = svc._resolve_kie_llm_url("https://api.kie.ai", "gpt-5-2")
    assert model == "gpt-5-2"
    assert url == "https://api.kie.ai/codex/v1/responses"
    assert kind == "responses"


def test_gemini_3_pro_stays_on_chat_completions():
    svc = LLMService()
    _, model, url, kind = svc._resolve_kie_llm_url("https://api.kie.ai", "gemini-3-pro")
    assert model == "gemini-3-pro"
    assert url == "https://api.kie.ai/gemini-3-pro/v1/chat/completions"
    assert kind == "chat_completions"


def test_gemini_3_8_flash_uses_stream_generate_content():
    svc = LLMService()
    _, model, url, kind = svc._resolve_kie_llm_url("https://api.kie.ai", "gemini-3.8-flash")
    assert model == "gemini-3-8-flash"
    assert url == "https://api.kie.ai/gemini/v1/models/gemini-3-8-flash:streamGenerateContent"
    assert kind == "gemini"


def test_gemini_openai_alias_stays_on_chat_completions():
    svc = LLMService()
    _, model, url, kind = svc._resolve_kie_llm_url("https://api.kie.ai", "gemini-3.8-flash-openai")
    assert model == "gemini-3-8-flash-openai"
    assert url == "https://api.kie.ai/gemini-3-8-flash-openai/v1/chat/completions"
    assert kind == "chat_completions"


def test_gemini_contents_fold_system_and_skip_sample_tool():
    svc = LLMService()
    contents = svc._build_kie_gemini_contents([
        {"role": "system", "content": "You are a script editor."},
        {"role": "user", "content": "What is the weather in Beijing today?"},
        {"role": "assistant", "content": "Checking."},
    ])
    assert contents == [
        {
            "role": "user",
            "parts": [
                {"text": "You are a script editor."},
                {"text": "What is the weather in Beijing today?"},
            ],
        },
        {"role": "model", "parts": [{"text": "Checking."}]},
    ]
    assert svc._extract_kie_gemini_options({}) == {}
    options = svc._extract_kie_gemini_options({
        "include_thoughts": True,
        "reasoning_effort": "high",
        "tools": [{
            "type": "function",
            "function": {
                "name": "get_weather_forecast",
                "description": "Get the weather forecast for a given location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string", "description": "The city name, e.g. Beijing"}},
                    "required": ["location"],
                },
            },
        }],
    })
    assert options["generationConfig"]["thinkingConfig"] == {"includeThoughts": True, "thinkingLevel": "high"}
    declaration = options["tools"][0]["functionDeclarations"][0]
    assert declaration["name"] == "get_weather_forecast"
    assert declaration["parameters"]["type"] == "OBJECT"
    assert declaration["parameters"]["properties"]["location"]["type"] == "STRING"


def test_gemini_candidate_text_ignores_thought_signature():
    svc = LLMService()
    text, finish = svc._gemini_candidate_text_and_finish({
        "candidates": [{
            "content": {
                "role": "model",
                "parts": [
                    {"text": "Beijing is clear.", "thought": True},
                    {"text": "Beijing is sunny."},
                    {"thoughtSignature": "Es8CCswCAb4example"},
                ],
            },
            "finishReason": "STOP",
        }],
        "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4, "totalTokenCount": 16},
    })
    assert text == "Beijing is sunny."
    assert finish == "stop"
    assert svc._kie_usage_from_gemini_metadata({
        "promptTokenCount": 12,
        "candidatesTokenCount": 4,
        "totalTokenCount": 16,
    }) == {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}


def test_kie_error_envelope_is_not_a_successful_reply():
    svc = LLMService()
    message = svc._kie_error_envelope_message({
        "code": 422,
        "msg": "The model is not supported",
        "data": None,
    })
    assert "422" in message
    assert "not supported" in message
    assert svc._is_immediate_provider_fallback_error(message) is True
    assert svc._kie_error_envelope_message({
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
        "code": 200,
    }) == ""


def test_grok_responses_input_matches_official_shape_without_demo_schema():
    svc = LLMService()
    instructions, response_input = svc._build_kie_responses_input([
        {"role": "user", "content": "Hello, please reply in Chinese"},
    ])
    assert instructions == ""
    assert response_input == [{
        "role": "user",
        "content": [{"type": "input_text", "text": "Hello, please reply in Chinese"}],
    }]
    options = svc._extract_kie_responses_options({})
    assert "text" not in options
