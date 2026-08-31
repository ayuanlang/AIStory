# -*- coding: utf-8 -*-
import asyncio
from unittest.mock import patch

from app.services.media_service import MediaGenerationService, _extract_provider_money_usage


class _FakeResp:
    def __init__(self, payload, status_code=200):
        import json as _json
        self._payload = payload
        self.status_code = status_code
        self.text = _json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self):
        return self._payload


def test_globalaiopc_api_root_strips_suffixes():
    svc = MediaGenerationService()
    assert svc._globalaiopc_api_root(
        "https://zcbservice.aizfw.cn/kyyReactApiServer/v2/model-center/tasks"
    ) == "https://zcbservice.aizfw.cn/kyyReactApiServer"
    assert svc._globalaiopc_api_root(
        "https://zcbservice.aizfw.cn/kyyReactApiServer/asset/seedance2/assetUpload"
    ) == "https://zcbservice.aizfw.cn/kyyReactApiServer"
    assert svc._globalaiopc_api_root() == svc.GLOBALAIOPC_DEFAULT_API_ROOT


def test_globalaiopc_asset_helpers():
    svc = MediaGenerationService()
    assert svc._globalaiopc_extract_asset_id({
        "assetId": "asset-20260722164336-p4mms",
        "status": "PROCESSING",
    }) == "asset-20260722164336-p4mms"
    assert svc._globalaiopc_extract_asset_id({
        "code": 0,
        "data": {"asset_id": "asset-2", "status": "ACTIVE"},
    }) == "asset-2"
    assert svc._globalaiopc_normalize_asset_status("Active") == "ACTIVE"
    assert svc._globalaiopc_is_asset_ref("assetId://asset-1")
    assert svc._globalaiopc_is_asset_ref("asset://asset-1")
    assert svc._globalaiopc_to_asset_uri("asset-1") == "assetId://asset-1"
    assert svc._globalaiopc_to_asset_uri("asset://asset-1") == "assetId://asset-1"
    assert svc._globalaiopc_guess_asset_type("https://cdn.example.com/a.mp4") == "Video"
    assert svc._globalaiopc_guess_asset_type("https://cdn.example.com/a.mp3") == "Audio"
    assert svc._globalaiopc_guess_asset_type("https://cdn.example.com/a.png") == "Image"
    assert svc._globalaiopc_bare_asset_id("assetId://asset-9") == "asset-9"


def test_globalaiopc_query_asset_posts_json_body():
    svc = MediaGenerationService()
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, "json": kwargs.get("json")})
        return _FakeResp({
            "assetId": "asset-20260722164336-p4mms",
            "status": "ACTIVE",
            "errorMessage": None,
        })

    with patch("app.services.media_service.requests.request", fake_request):
        payload, err = svc._globalaiopc_query_asset(
            detail_url="https://zcbservice.aizfw.cn/kyyReactApiServer/asset/seedance2/assetDetail",
            api_key="sk-test",
            asset_id="assetId://asset-20260722164336-p4mms",
        )
    assert not err
    assert payload["status"] == "ACTIVE"
    assert calls[0]["method"] == "POST"
    assert calls[0]["json"] == {"assetId": "asset-20260722164336-p4mms"}
    assert calls[0]["url"].endswith("/asset/seedance2/assetDetail")


def test_globalaiopc_amount_usage():
    usage = _extract_provider_money_usage({"amount": 0.32, "actualDuration": 5})
    assert usage.get("consumeMoney") == 0.32
    assert usage.get("billing_basis") == "provider_amount"


def test_globalaiopc_reviews_assets_then_submits_seedance_payload():
    svc = MediaGenerationService()
    calls = []
    asset_state = {"status": "PROCESSING"}

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, "json": kwargs.get("json")})
        url_l = str(url).lower()
        if str(method).upper() == "POST" and url_l.endswith("/asset/seedance2/assetupload"):
            body = kwargs.get("json") or {}
            return _FakeResp({
                "assetId": "asset-img-1" if body.get("assetType") == "Image" else "asset-vid-1",
                "assetType": body.get("assetType"),
                "url": body.get("url"),
                "status": "PROCESSING",
                "name": body.get("name"),
                "errorMessage": None,
            })
        if str(method).upper() == "POST" and url_l.endswith("/asset/seedance2/assetdetail"):
            asset_state["status"] = "ACTIVE"
            body = kwargs.get("json") or {}
            return _FakeResp({
                "assetId": body.get("assetId"),
                "status": "ACTIVE",
                "errorMessage": None,
            })
        if str(method).upper() == "POST" and url_l.endswith("/v2/model-center/tasks"):
            return _FakeResp({
                "id": "mcp_example_123456",
                "object": "video",
                "model": "sd_2.0_discount",
                "status": "queued",
                "error": None,
            })
        if str(method).upper() == "GET" and "/v2/model-center/tasks/" in url_l:
            return _FakeResp({
                "id": "mcp_example_123456",
                "status": "completed",
                "progress": 100,
                "result_url": "https://example.com/result.mp4",
                "video_url": "https://example.com/result.mp4",
                "amount": 0.32,
                "actualDuration": 5,
                "error": None,
            })
        return _FakeResp({"error": "unexpected"}, status_code=404)

    async def _no_sleep(*_args, **_kwargs):
        return None

    with patch("app.services.media_service.requests.request", fake_request), \
         patch("app.services.media_service.requests.post", lambda url, **kwargs: fake_request("POST", url, **kwargs)), \
         patch("app.services.media_service.requests.get", lambda url, **kwargs: fake_request("GET", url, **kwargs)), \
         patch("app.services.media_service.asyncio.sleep", _no_sleep):
        result = asyncio.run(svc._handle_globalaiopc_generation(
            "video",
            "A cinematic product shot with natural lighting",
            {
                "api_key": "sk-test",
                "model": "sd_2.0_discount",
                "base_url": "https://zcbservice.aizfw.cn/kyyReactApiServer",
                "config": {
                    "reference_images": ["https://example.com/person.png"],
                    "reference_videos": ["https://example.com/clip.mp4"],
                    "poll_timeout_seconds": 60,
                    "poll_interval_seconds": 5,
                    "asset_poll_timeout_seconds": 30,
                    "asset_poll_interval_seconds": 2,
                },
            },
            duration=5,
            aspect_ratio="16:9",
        ))

    upload_calls = [c for c in calls if str(c["url"]).endswith("/asset/seedance2/assetUpload")]
    detail_calls = [c for c in calls if str(c["url"]).endswith("/asset/seedance2/assetDetail")]
    task_calls = [c for c in calls if str(c["url"]).endswith("/v2/model-center/tasks") and c["method"] == "POST"]
    assert upload_calls, calls
    assert detail_calls, calls
    assert all(c["method"] == "POST" for c in detail_calls)
    assert {c["json"]["assetId"] for c in detail_calls} == {"asset-img-1", "asset-vid-1"}
    assert task_calls, calls
    assert upload_calls[0]["json"]["assetType"] == "Image"
    assert upload_calls[0]["json"]["url"] == "https://example.com/person.png"
    body = task_calls[0]["json"]
    assert body["model"] == "sd_2.0_discount"
    assert body["duration"] == 5
    assert body["aspect_ratio"] == "16:9"
    assert body["reference_images"] == ["assetId://asset-img-1"]
    assert body["reference_videos"] == ["assetId://asset-vid-1"]
    assert "first_image" not in body
    assert "last_image" not in body
    assert result.get("url") == "https://example.com/result.mp4"
    assert not result.get("submit_failed")
    assert not result.get("error")


def test_globalaiopc_first_last_excludes_multimodal_refs():
    svc = MediaGenerationService()
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, "json": kwargs.get("json")})
        url_l = str(url).lower()
        if str(method).upper() == "POST" and url_l.endswith("/asset/seedance2/assetupload"):
            name = str((kwargs.get("json") or {}).get("name") or "")
            asset_id = "asset-first" if "首帧" in name else "asset-last"
            return _FakeResp({
                "assetId": asset_id,
                "status": "ACTIVE",
                "errorMessage": None,
            })
        if str(method).upper() == "POST" and url_l.endswith("/v2/model-center/tasks"):
            return _FakeResp({"id": "task-fl", "status": "queued"})
        if str(method).upper() == "GET" and "/v2/model-center/tasks/" in url_l:
            return _FakeResp({
                "id": "task-fl",
                "status": "completed",
                "video_url": "https://example.com/fl.mp4",
            })
        return _FakeResp({"error": "unexpected"}, status_code=404)

    async def _no_sleep(*_args, **_kwargs):
        return None

    with patch("app.services.media_service.requests.request", fake_request), \
         patch("app.services.media_service.requests.post", lambda url, **kwargs: fake_request("POST", url, **kwargs)), \
         patch("app.services.media_service.requests.get", lambda url, **kwargs: fake_request("GET", url, **kwargs)), \
         patch("app.services.media_service.asyncio.sleep", _no_sleep):
        result = asyncio.run(svc._handle_globalaiopc_generation(
            "video",
            "首尾帧转场",
            {
                "api_key": "sk-test",
                "model": "sd_2.0_discount",
                "config": {
                    "mode": "first_last",
                    "first_image": "https://example.com/first.png",
                    "reference_videos": ["https://example.com/should-drop.mp4"],
                    "poll_timeout_seconds": 60,
                    "poll_interval_seconds": 5,
                },
            },
            last_frame_url="https://example.com/last.png",
            duration=8,
            aspect_ratio="9:16",
        ))

    task_calls = [c for c in calls if str(c["url"]).endswith("/v2/model-center/tasks") and c["method"] == "POST"]
    assert task_calls, calls
    body = task_calls[0]["json"]
    assert body["first_image"] == "assetId://asset-first"
    assert body["last_image"] == "assetId://asset-last"
    assert "reference_images" not in body
    assert "reference_videos" not in body
    assert result.get("url") == "https://example.com/fl.mp4"


if __name__ == "__main__":
    test_globalaiopc_api_root_strips_suffixes()
    test_globalaiopc_asset_helpers()
    test_globalaiopc_query_asset_posts_json_body()
    test_globalaiopc_amount_usage()
    test_globalaiopc_reviews_assets_then_submits_seedance_payload()
    test_globalaiopc_first_last_excludes_multimodal_refs()
    print("ok")
