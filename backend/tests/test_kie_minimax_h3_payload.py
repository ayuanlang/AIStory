# -*- coding: utf-8 -*-
"""KIE MiniMax H3 payload contract."""


def test_minimax_h3_i2v_maps_image_url_to_first_frame():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    payload = {
        "prompt": "The character turns and smiles",
        "image_url": "https://cdn.example.com/first.jpg",
        "image_urls": ["https://cdn.example.com/first.jpg"],
        "duration": "8",
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "sound": True,
    }

    error = service._normalize_kie_minimax_h3_input(
        payload,
        model="minimax-h3/image-to-video",
    )

    assert error is None
    assert payload == {
        "prompt": "The character turns and smiles",
        "first_frame_url": "https://cdn.example.com/first.jpg",
        "duration": 8,
        "resolution": "768P",
    }
    assert "image_url" not in payload
    assert "image_urls" not in payload
    assert "aspect_ratio" not in payload
    assert "sound" not in payload


def test_minimax_h3_i2v_uses_second_ref_as_last_frame():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    payload = {
        "prompt": "Walk from start to end",
        "duration": 6,
    }

    error = service._normalize_kie_minimax_h3_input(
        payload,
        model="minimax-h3/image-to-video",
        resolved_refs=[
            "https://cdn.example.com/first.jpg",
            "https://cdn.example.com/last.jpg",
        ],
    )

    assert error is None
    assert payload["first_frame_url"] == "https://cdn.example.com/first.jpg"
    assert payload["last_frame_url"] == "https://cdn.example.com/last.jpg"
    assert payload["duration"] == 6
    assert payload["resolution"] == "2K"


def test_minimax_h3_i2v_requires_public_frame_url():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    payload = {
        "prompt": "Animate this still",
        "image_url": "http://localhost/private-first.jpg",
        "duration": 6,
    }

    error = service._normalize_kie_minimax_h3_input(
        payload,
        model="minimax-h3/image-to-video",
    )

    assert error is not None
    assert error.get("submit_failed") is True
    assert "first_frame_url" in str(error.get("details") or "")


def test_minimax_h3_t2v_keeps_aspect_ratio_and_integer_duration():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    payload = {
        "prompt": "A cat walking on the beach",
        "aspect_ratio": "portrait",
        "duration": "10",
        "resolution": "768",
        "image_urls": ["https://cdn.example.com/unused.jpg"],
        "sound": False,
    }

    error = service._normalize_kie_minimax_h3_input(
        payload,
        model="minimax-h3/text-to-video",
    )

    assert error is None
    assert payload == {
        "prompt": "A cat walking on the beach",
        "aspect_ratio": "9:16",
        "duration": 10,
        "resolution": "768P",
    }


def test_minimax_h3_duration_and_resolution_clamps():
    from app.services.media_service import MediaGenerationService

    service = MediaGenerationService()
    assert service._map_kie_minimax_h3_duration(3) == 4
    assert service._map_kie_minimax_h3_duration(20) == 15
    assert service._map_kie_minimax_h3_duration("bad") == 6
    assert service._map_kie_minimax_h3_resolution("480p") == "768P"
    assert service._map_kie_minimax_h3_resolution("1080p") == "2K"
