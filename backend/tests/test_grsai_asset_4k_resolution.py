# -*- coding: utf-8 -*-
"""Asset generation on selected Grsai image models submits 4K."""
import asyncio


def _service():
    from app.services.media_service import MediaGenerationService

    return MediaGenerationService()


def test_asset_models_require_4k_only_for_subject_assets():
    service = _service()
    subject = {"__asset_type": "subject"}
    assert service._grsai_asset_generation_requires_4k("nano-banana-2", subject) is True
    assert service._grsai_asset_generation_requires_4k("nano-banana-pro", subject) is True
    assert service._grsai_asset_generation_requires_4k("gpt-image-2-vip", subject) is True
    assert service._grsai_asset_generation_requires_4k("nano-banana-pro-vt", subject) is False
    assert service._grsai_asset_generation_requires_4k("nano-banana-fast", subject) is False
    assert service._grsai_asset_generation_requires_4k("gpt-image-2", subject) is False
    assert service._grsai_asset_generation_requires_4k("nano-banana-pro", {"__asset_type": "start_frame"}) is False
    assert service._grsai_asset_generation_requires_4k("nano-banana-pro", {}) is False


def test_gpt_image_2_vip_asset_tier_uses_4k_pixels():
    service = _service()
    size, drop_ratio = service._resolve_grsai_gpt_image_2_size(
        "gpt-image-2-vip",
        "16:9",
        None,
        None,
        None,
        size_tier="4k",
    )
    assert drop_ratio is True
    assert size == "3840x2160"

    default_size, _ = service._resolve_grsai_gpt_image_2_size(
        "gpt-image-2-vip",
        "16:9",
        None,
        None,
        None,
    )
    assert default_size == "1280x720"


def test_grsai_asset_submit_payload_uses_4k(monkeypatch):
    service = _service()
    captured = {}

    async def _fake_submit(endpoint, payload, *args, **kwargs):
        captured["payload"] = dict(payload)
        return {"url": "https://cdn.example.com/asset.png", "metadata": {}}

    monkeypatch.setattr(service, "_submit_and_poll_grsai", _fake_submit)

    async def _run(model, asset_type, image_size="2K"):
        captured.clear()
        await service._handle_grsai_generation(
            "image",
            "a standing character",
            {
                "api_key": "test-key",
                "model": model,
                "base_url": "https://grsai.example",
                "config": {
                    "__asset_type": asset_type,
                    "endpoint": "https://grsai.example/v1/draw/nano-banana",
                },
            },
            aspect_ratio="16:9",
            image_size=image_size,
        )
        return captured["payload"]

    banana = asyncio.run(_run("nano-banana-pro", "subject", "1K"))
    assert banana["imageSize"] == "4K"
    assert "size" not in banana

    banana2 = asyncio.run(_run("nano-banana-2", "character", "2K"))
    assert banana2["imageSize"] == "4K"

    vip = asyncio.run(_run("gpt-image-2-vip", "prop", "1K"))
    assert vip["size"] == "3840x2160"
    assert "aspectRatio" not in vip

    shot = asyncio.run(_run("nano-banana-pro", "start_frame", "2K"))
    assert shot["imageSize"] == "2K"

    other = asyncio.run(_run("nano-banana-fast", "subject", "1K"))
    assert other["imageSize"] == "1K"
