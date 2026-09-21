# -*- coding: utf-8 -*-
"""Grsai MiniMax H3 payload and result-parse contract."""


def test_grsai_minimax_h3_t2v_payload_maps_portrait_and_async():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    payload = service._build_grsai_minimax_h3_payload(
        prompt="A cat walking on the beach",
        aspect_ratio="9:16",
        resolution="720p",
        duration="10",
        seed=1000,
    )

    assert payload == {
        "model": "minimax-h3",
        "prompt": "A cat walking on the beach",
        "aspectRatio": "portrait",
        "resolution": "768p",
        "duration": 10,
        "replyType": "async",
        "seed": 1000,
    }


def test_grsai_minimax_h3_i2v_keeps_images_and_audios():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    payload = service._build_grsai_minimax_h3_payload(
        prompt="The character turns and smiles",
        aspect_ratio="16:9",
        resolution="1080p",
        duration=12,
        images=[
            "https://cdn.example.com/first.jpg",
            "https://cdn.example.com/last.jpg",
        ],
        audios=["https://cdn.example.com/voice.mp3"],
    )

    assert payload["aspectRatio"] == "landscape"
    assert payload["resolution"] == "1080p"
    assert payload["duration"] == 10
    assert payload["images"] == [
        "https://cdn.example.com/first.jpg",
        "https://cdn.example.com/last.jpg",
    ]
    assert payload["audios"] == ["https://cdn.example.com/voice.mp3"]


def test_grsai_minimax_h3_duration_and_resolution_clamps():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    assert service._map_grsai_minimax_h3_duration(0) == 5
    assert service._map_grsai_minimax_h3_duration(20) == 15
    assert service._map_grsai_minimax_h3_duration(15, resolution="1080p") == 10
    assert service._map_grsai_minimax_h3_duration("bad") == 5
    assert service._map_grsai_minimax_h3_resolution("480p") == "480p"
    assert service._map_grsai_minimax_h3_resolution("720p") == "768p"
    assert service._map_grsai_minimax_h3_resolution("1080p") == "1080p"
    assert service._map_grsai_minimax_h3_resolution("2k") == "1080p"
    assert service._map_grsai_minimax_h3_resolution("720p", draft=True) == "480p"
    assert service._map_grsai_minimax_h3_resolution("480p", width=1280, height=720) == "768p"


def test_grsai_minimax_h3_aspect_ratio_aliases():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    assert service._map_grsai_minimax_h3_aspect_ratio("portrait") == "portrait"
    assert service._map_grsai_minimax_h3_aspect_ratio("3:4") == "portrait"
    assert service._map_grsai_minimax_h3_aspect_ratio("21:9") == "landscape"
    assert service._map_grsai_minimax_h3_aspect_ratio("720x1280") == "portrait"


def test_grsai_minimax_h3_collects_url_like_audios_only():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    audios = service._collect_grsai_minimax_h3_audios(
        {
            "audios": ["https://cdn.example.com/a.mp3"],
            "audio_ids": ["voice-1", "https://cdn.example.com/b.mp3"],
            "reference_audio_urls": ["data:audio/mpeg;base64,AAA"],
        }
    )
    assert audios == [
        "https://cdn.example.com/a.mp3",
        "data:audio/mpeg;base64,AAA",
        "https://cdn.example.com/b.mp3",
    ]


def test_parse_grsai_flat_generate_result():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    parsed = service._parse_grsai_result_payload(
        {
            "id": "14-5f3cf761-a4bb-486a-8016-77f490998f80",
            "status": "succeeded",
            "progress": 100,
            "results": [
                {"url": "https://file1.aitohumanize.com/file/demo.mp4"},
            ],
        }
    )
    assert parsed["task_id"] == "14-5f3cf761-a4bb-486a-8016-77f490998f80"
    assert parsed["status"] == "succeeded"
    assert parsed["media_url"] == "https://file1.aitohumanize.com/file/demo.mp4"
    assert parsed["progress"] == 100


def test_parse_grsai_legacy_wrapped_task_id():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    parsed = service._parse_grsai_result_payload({"code": 0, "data": "task-abc"})
    assert parsed["task_id"] == "task-abc"


def test_grsai_video_direct_oss_headers_use_video_path():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    headers = service._build_grsai_direct_oss_headers(
        {"_request_user_id": 42, "oss-id": "oss-video-1"},
        asset_kind="video",
    )
    assert headers["oss-id"] == "oss-video-1"
    assert headers["oss-path"].startswith("file/videos/")
    assert headers["oss-path"].endswith("/42")


def test_grsai_image_direct_oss_headers_keep_image_path():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    headers = service._build_grsai_direct_oss_headers(
        {
            "_request_user_id": 7,
            "oss-id": "oss-image-1",
            "oss-path": "file/images/{yyyymm}/{user_id}",
        },
        asset_kind="image",
    )
    assert headers["oss-id"] == "oss-image-1"
    assert headers["oss-path"].startswith("file/images/")
    assert headers["oss-path"].endswith("/7")


def test_is_grsai_minimax_h3_model_does_not_collide_with_kie_slash_models():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    assert service._is_grsai_minimax_h3_model("minimax-h3") is True
    assert service._is_grsai_minimax_h3_model("minimax-h3/text-to-video") is True
    assert service._is_grsai_minimax_h3_model("minimax-video") is False
    assert service._is_kie_minimax_h3_model("minimax-h3") is False
    assert service._is_kie_minimax_h3_model("minimax-h3/text-to-video") is True


def test_resolve_grsai_poll_request_h3_uses_get_query_param():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    spec = service._resolve_grsai_poll_request(
        task_id="12-f546af1b-514c-49b7-9ef5-21d7933803fa",
        query_endpoint="https://grsai.dakka.com.cn/v1/api/result",
        model="minimax-h3",
    )
    assert spec == {
        "url": "https://grsai.dakka.com.cn/v1/api/result",
        "method": "GET",
        "params": {"id": "12-f546af1b-514c-49b7-9ef5-21d7933803fa"},
    }


def test_resolve_grsai_poll_request_h3_rewrites_draw_result_endpoint():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    spec = service._resolve_grsai_poll_request(
        task_id="12-abc",
        query_endpoint="https://grsai.dakka.com.cn/v1/draw/result",
        model="minimax-h3",
    )
    assert spec["method"] == "GET"
    assert spec["url"] == "https://grsai.dakka.com.cn/v1/api/result"
    assert spec["params"] == {"id": "12-abc"}


def test_resolve_grsai_poll_request_sora_keeps_post_draw_result():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    spec = service._resolve_grsai_poll_request(
        task_id="sora-task-1",
        query_endpoint="https://grsai.dakka.com.cn/v1/draw/result",
        model="sora-2",
    )
    assert spec == {
        "url": "https://grsai.dakka.com.cn/v1/draw/result",
        "method": "POST",
        "json": {"id": "sora-task-1"},
    }


def test_fetch_grsai_minimax_h3_result_uses_get_and_parses_results_url(monkeypatch):
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    calls = []

    class _Resp:
        status_code = 200
        content = b'{"id":"12-abc","status":"succeeded","results":[{"url":"https://cdn.example.com/a.mp4"}]}'

        def json(self):
            return {
                "id": "12-abc",
                "status": "succeeded",
                "results": [{"url": "https://cdn.example.com/a.mp4"}],
            }

    def fake_get(url, **kwargs):
        calls.append(("GET", url, kwargs.get("params"), kwargs.get("json")))
        return _Resp()

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs.get("params"), kwargs.get("json")))
        return _Resp()

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("requests.post", fake_post)

    out = service.fetch_provider_task_result(
        task_id="12-abc",
        api_key="k",
        query_endpoint="https://grsai.dakka.com.cn/v1/draw/result",
        provider="grsai",
        kind="video",
        model="minimax-h3",
    )
    assert calls == [
        ("GET", "https://grsai.dakka.com.cn/v1/api/result", {"id": "12-abc"}, None)
    ]
    assert out["url"] == "https://cdn.example.com/a.mp4"
    assert out["status"] == "succeeded"


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []


class _FakeDB:
    def query(self, *args, **kwargs):
        return _FakeQuery()

    def close(self):
        return None


def test_resolve_poll_credentials_grsai_h3_defaults_to_api_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.generation_runtime.timeout_poll_recovery.SessionLocal",
        lambda: _FakeDB(),
    )
    from app.services.generation_runtime.timeout_poll_recovery import _resolve_poll_credentials

    _api_key, query_endpoint, provider, _base_url = _resolve_poll_credentials(
        {"billing_context": {"provider": "grsai", "model": "minimax-h3"}}
    )
    assert provider == "grsai"
    assert query_endpoint == "https://grsai.dakka.com.cn/v1/api/result"


def test_resolve_poll_credentials_grsai_h3_rewrites_draw_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.generation_runtime.timeout_poll_recovery.SessionLocal",
        lambda: _FakeDB(),
    )
    from app.services.generation_runtime.timeout_poll_recovery import _resolve_poll_credentials

    _api_key, query_endpoint, _provider, _base_url = _resolve_poll_credentials(
        {
            "billing_context": {"provider": "grsai", "model": "minimax-h3"},
            "query_endpoint": "https://grsai.dakka.com.cn/v1/draw/result",
        }
    )
    assert query_endpoint == "https://grsai.dakka.com.cn/v1/api/result"


def test_resolve_poll_credentials_grsai_sora_defaults_to_draw_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.generation_runtime.timeout_poll_recovery.SessionLocal",
        lambda: _FakeDB(),
    )
    from app.services.generation_runtime.timeout_poll_recovery import _resolve_poll_credentials

    _api_key, query_endpoint, _provider, _base_url = _resolve_poll_credentials(
        {"billing_context": {"provider": "grsai", "model": "sora-2"}}
    )
    assert query_endpoint == "https://grsai.dakka.com.cn/v1/draw/result"
