# -*- coding: utf-8 -*-
import asyncio
from unittest.mock import patch

from app.services.media_service import MediaGenerationService


PNG_1PX = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_ddimatuo_api_root_strips_generations():
    svc = MediaGenerationService()
    assert svc._ddimatuo_api_root("https://api.ddimatuo.top/v1/videos/generations") == "https://api.ddimatuo.top"
    assert svc._ddimatuo_api_root("https://api.aiyrx.xyz/v1/videos") == "https://api.aiyrx.xyz"
    assert svc._ddimatuo_api_root("https://api.aiyrx.xyz", "/v1/videos") == "https://api.aiyrx.xyz"


def test_ddimatuo_extract_asset_id_shapes():
    svc = MediaGenerationService()
    assert svc._ddimatuo_extract_asset_id({"id": "019c9a0a-8888-7000-8000-000000000008"}) == (
        "019c9a0a-8888-7000-8000-000000000008"
    )
    assert svc._ddimatuo_extract_asset_id({"data": {"asset_id": "asset-2"}}) == "asset-2"
    assert svc._ddimatuo_extract_asset_id({"asset": {"id": "asset-3"}}) == "asset-3"
    assert svc._ddimatuo_extract_asset_id({}) == ""


def test_ddimatuo_resolve_output_size():
    svc = MediaGenerationService()
    assert svc._ddimatuo_resolve_output_size(ratio="16:9", resolution="720P") == "1280x720"
    assert svc._ddimatuo_resolve_output_size(ratio="16:9", resolution="1080P") == "1920x1080"
    assert svc._ddimatuo_resolve_output_size(
        ratio="16:9",
        resolution="1080P",
        explicit_size="1280x720",
    ) == "1280x720"


class _FakeResp:
    def __init__(self, payload, status_code=200):
        import json as _json
        self._payload = payload
        self.status_code = status_code
        self.text = _json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self):
        return self._payload


def test_ddimatuo_uploads_asset_then_creates_video_with_references():
    svc = MediaGenerationService()
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, "json": kwargs.get("json"), "data": kwargs.get("data"), "files": kwargs.get("files")})
        if str(url).rstrip("/").endswith("/v1/assets"):
            return _FakeResp({"id": "019c9a0a-8888-7000-8000-000000000008"})
        if str(url).rstrip("/").endswith("/v1/videos"):
            return _FakeResp({"id": "task-1", "status": "queued"})
        if str(url).endswith("/cancel"):
            return _FakeResp({"ok": True})
        return _FakeResp({"error": "unexpected"}, status_code=404)

    def fake_get(url, **kwargs):
        return _FakeResp({
            "id": "task-1",
            "status": "completed",
            "video_url": "https://api.ddimatuo.top/v1/videos/task-1/content",
        })

    async def _no_sleep(*_args, **_kwargs):
        return None

    with patch("app.services.media_service.requests.post", fake_post), \
         patch("app.services.media_service.requests.get", fake_get), \
         patch("app.services.media_service.asyncio.sleep", _no_sleep):
        result = asyncio.run(svc._handle_ddimatuo_generation(
            "video",
            "人物走向镜头",
            {
                "api_key": "sk-test",
                "model": "C4渠道SD2.0-Fast720p-933不卡脸",
                "base_url": "https://api.aiyrx.xyz",
                "config": {
                    "quality": "720P",
                    "ratio": "16:9",
                    "images": [PNG_1PX],
                    "poll_timeout_seconds": 60,
                    "poll_interval_seconds": 3,
                },
            },
            PNG_1PX,
            duration=5,
            aspect_ratio="16:9",
        ))

    assert calls, "expected HTTP calls"
    assert str(calls[0]["url"]).rstrip("/").endswith("/v1/assets"), calls[0]["url"]
    asset_calls = [c for c in calls if str(c["url"]).rstrip("/").endswith("/v1/assets")]
    video_calls = [c for c in calls if str(c["url"]).rstrip("/").endswith("/v1/videos")]
    assert asset_calls, "expected POST /v1/assets before create"
    assert video_calls, "expected POST /v1/videos after asset upload"
    assert "/generations" not in str(video_calls[0]["url"])
    assert asset_calls[0]["data"]["kind"] == "image"
    body = video_calls[0]["json"]
    assert body["model"] == "C4渠道SD2.0-Fast720p-933不卡脸"
    assert body["channel"] == "auto"
    assert body["duration_seconds"] == 5
    assert body["seconds"] == 5
    assert body["size"] == "1280x720"
    assert body["references"][0]["asset_id"] == "019c9a0a-8888-7000-8000-000000000008"
    assert body["references"][0]["role"] == "character"
    assert body["references"][0]["id"] == "image1"
    assert "images" not in body
    assert "videos" not in body
    assert "audios" not in body
    assert result.get("url")
    assert not result.get("submit_failed")
    assert not result.get("error")


if __name__ == "__main__":
    test_ddimatuo_api_root_strips_generations()
    test_ddimatuo_extract_asset_id_shapes()
    test_ddimatuo_resolve_output_size()
    test_ddimatuo_uploads_asset_then_creates_video_with_references()
    print("ok")
