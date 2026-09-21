# -*- coding: utf-8 -*-
"""Grsai video persist-media copies the OSS URL instead of re-downloading."""


def test_grsai_direct_oss_url_is_detected_from_provider():
    from app.services.generation_runtime.media_persist import _is_grsai_direct_oss_video_url

    assert _is_grsai_direct_oss_video_url(
        "https://file1.aitohumanize.com/file/demo.mp4",
        {"provider": "grsai"},
    ) is True
    assert _is_grsai_direct_oss_video_url(
        "https://file1.aitohumanize.com/file/demo.mp4",
        explicit_provider="grsai-video",
    ) is True
    assert _is_grsai_direct_oss_video_url(
        "https://file1.aitohumanize.com/file/demo.mp4",
        {"provider": "kie"},
    ) is False
    assert _is_grsai_direct_oss_video_url("/uploads/1/demo.mp4", {"provider": "grsai"}) is False


def test_persist_remote_video_skips_download_for_grsai_when_forced():
    from unittest.mock import MagicMock, patch

    from app.services.generation_runtime.media_persist import _persist_remote_video_result

    user = MagicMock()
    user.id = 1
    source = "https://file1.aitohumanize.com/file/demo.mp4"
    with patch("app.services.generation_runtime.media_persist.media_service._download_and_save") as download:
        url, meta, uploaded = _persist_remote_video_result(
            user,
            source,
            {"provider": "grsai"},
            force_configured_oss=True,
        )

    download.assert_not_called()
    assert url == source
    assert uploaded is True
    assert meta["provider"] == "grsai"
    assert meta["provider_direct_oss_url"] is True
