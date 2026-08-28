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
    assert svc._ddimatuo_api_root("https://api.aiyrx.xyz/v1/media-assets") == "https://api.aiyrx.xyz"
    assert svc._ddimatuo_api_root() == "https://api.aiyrx.xyz"


def test_ddimatuo_media_asset_download_url():
    svc = MediaGenerationService()
    assert svc._ddimatuo_extract_media_asset_id({
        "status": "completed",
        "media_asset_id": "ma-1",
    }) == "ma-1"
    assert svc._ddimatuo_extract_media_asset_id({
        "output": {"id": "ma-2"},
    }) == "ma-2"
    assert svc._ddimatuo_extract_media_asset_id({
        "video_url": "https://api.aiyrx.xyz/v1/media-assets/ma-3/download",
    }) == "ma-3"
    assert svc._ddimatuo_media_download_url("ma-1", "https://api.aiyrx.xyz") == (
        "https://api.aiyrx.xyz/v1/media-assets/ma-1/download"
    )
    assert svc._ddimatuo_resolve_result_url(
        {"status": "completed", "media_asset_id": "ma-9"},
        root_url="https://api.aiyrx.xyz",
        task_id="task-1",
    ) == "https://api.aiyrx.xyz/v1/media-assets/ma-9/download"


def test_ddimatuo_status_and_webhook_helpers():
    svc = MediaGenerationService()
    assert svc._ddimatuo_normalize_status("provider_queued") == "provider_queued"
    assert svc._ddimatuo_normalize_status("video.completed") == "completed"
    assert svc._ddimatuo_normalize_status("video.cancelled") == "cancelled"
    assert svc._ddimatuo_is_terminal_status("manual_review")
    assert svc._ddimatuo_is_terminal_status("expired")
    assert not svc._ddimatuo_is_terminal_status("cancelling")
    assert svc._ddimatuo_public_webhook_url("https://app.example.com/api/v1/generate/callback/t1")
    assert not svc._ddimatuo_public_webhook_url("http://app.example.com/cb")
    assert not svc._ddimatuo_public_webhook_url("https://localhost/cb")
    sigs = svc._ddimatuo_webhook_signature_candidates("sk-test", "1710000000", b'{"id":"task-1"}')
    assert sigs
    import hmac
    import hashlib
    key = hashlib.sha256(b"sk-test").digest()
    expected = hmac.new(key, b'1710000000.{"id":"task-1"}', hashlib.sha256).hexdigest()
    assert expected in sigs


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
            "media_asset_id": "ma-clip-1",
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
    assert result.get("url") == "https://api.aiyrx.xyz/v1/media-assets/ma-clip-1/download"
    assert result.get("metadata", {}).get("media_asset_id") == "ma-clip-1"
    assert not result.get("submit_failed")
    assert not result.get("error")


def test_ddimatuo_submit_includes_webhook_and_can_pending_callback():
    svc = MediaGenerationService()
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, "json": kwargs.get("json"), "data": kwargs.get("data")})
        if str(url).rstrip("/").endswith("/v1/assets"):
            return _FakeResp({"id": "asset-1"})
        if str(url).rstrip("/").endswith("/v1/videos"):
            return _FakeResp({"id": "task-wh", "status": "created"})
        return _FakeResp({"error": "unexpected"}, status_code=404)

    with patch("app.services.media_service.requests.post", fake_post):
        result = asyncio.run(svc._handle_ddimatuo_generation(
            "video",
            "人物走向镜头",
            {
                "api_key": "sk-test",
                "model": "SD_2.0",
                "base_url": "https://api.aiyrx.xyz",
                "config": {
                    "quality": "720P",
                    "ratio": "16:9",
                    "images": [PNG_1PX],
                    "_provider_callback_url": "https://app.example.com/api/v1/generate/callback/video-job-abc",
                    "_provider_callback_ticket": "video-job-abc",
                    "_pure_callback_mode": True,
                },
            },
            PNG_1PX,
            duration=5,
            aspect_ratio="16:9",
        ))

    video_calls = [c for c in calls if str(c["url"]).rstrip("/").endswith("/v1/videos")]
    assert video_calls
    assert video_calls[0]["json"]["webhook"] == (
        "https://app.example.com/api/v1/generate/callback/video-job-abc"
    )
    assert result.get("pending_callback") is True
    assert result.get("provider_task_id") == "task-wh"
    assert result.get("metadata", {}).get("webhook")


def test_ddimatuo_cancel_202_keeps_polling_until_cancelled():
    svc = MediaGenerationService()
    gets = {"n": 0}

    def fake_post(url, **kwargs):
        if str(url).rstrip("/").endswith("/v1/assets"):
            return _FakeResp({"id": "asset-1"})
        if str(url).rstrip("/").endswith("/v1/videos"):
            return _FakeResp({"id": "task-c", "status": "queued"})
        if str(url).endswith("/cancel"):
            return _FakeResp({"status": "cancelling"}, status_code=202)
        return _FakeResp({"error": "unexpected"}, status_code=404)

    def fake_get(url, **kwargs):
        gets["n"] += 1
        if gets["n"] <= 2:
            return _FakeResp({"id": "task-c", "status": "generating"})
        return _FakeResp({"id": "task-c", "status": "cancelled", "error": {"message": "user cancelled"}})

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
                "model": "SD_2.0",
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

    assert result.get("error")
    assert "cancelled" in str(result.get("error") or "").lower() or "user cancelled" in str(result.get("error") or "").lower()
    assert gets["n"] >= 3


if __name__ == "__main__":
    test_ddimatuo_api_root_strips_generations()
    test_ddimatuo_extract_asset_id_shapes()
    test_ddimatuo_resolve_output_size()
    test_ddimatuo_media_asset_download_url()
    test_ddimatuo_status_and_webhook_helpers()
    test_ddimatuo_uploads_asset_then_creates_video_with_references()
    test_ddimatuo_submit_includes_webhook_and_can_pending_callback()
    test_ddimatuo_cancel_202_keeps_polling_until_cancelled()
    print("ok")
