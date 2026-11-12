# -*- coding: utf-8 -*-
"""Cloudflare R2 pools and Grsai direct-write repository selection."""

import urllib.parse
from types import SimpleNamespace


def _clear_oss_env(monkeypatch):
    for key in (
        "OSS_ENDPOINT",
        "OSS_BUCKET",
        "OSS_PROVIDER",
        "OSS_REGION",
        "OSS_PUBLIC_BASE_URL",
        "OSS_FORCE_PATH_STYLE",
        "S3_FORCE_PATH_STYLE",
        "QINIU_ENDPOINT",
        "QINIU_BUCKET",
        "TOS_ENDPOINT",
        "TOS_BUCKET",
        "VOLC_TOS_ENDPOINT",
        "S3_ENDPOINT",
        "AWS_S3_ENDPOINT",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "R2_ENDPOINT",
        "R2_BUCKET",
        "R2_ACCOUNT_ID",
        "R2_REGION",
        "CLOUDFLARE_R2_ENDPOINT",
        "CLOUDFLARE_R2_BUCKET",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_R2_ACCOUNT_ID",
        "CLOUDFLARE_R2_REGION",
        "GRSAI_OSS_ID",
        "GRSAI_CLOUDFLARE_OSS_ID",
    ):
        monkeypatch.delenv(key, raising=False)


def test_cloudflare_pool_defaults_region_auto_and_keeps_grsai_id():
    from app.services.oss_storage_service import OSSStorageService

    service = OSSStorageService()
    pool = service._normalize_pool_row({
        "id": 3,
        "provider": "r2",
        "endpoint": "https://acct.r2.cloudflarestorage.com",
        "bucket": "media",
        "public_base_url": "https://pub-demo.r2.dev",
        "credentials": [{"access_key": "ak", "secret_key": "sk", "is_active": True}],
        "is_active": True,
        "grsai_oss_id": "cf-repo-1",
    })
    assert pool.provider == "r2"
    assert pool.region_name == "auto"
    assert pool.grsai_oss_id == "cf-repo-1"
    assert service._is_cloudflare_provider(pool) is True
    assert service._is_s3_compat_unsigned_payload(pool) is True
    assert service._is_qiniu_provider(pool) is False


def test_qiniu_pool_is_not_cloudflare():
    from app.services.oss_storage_service import OSSStorageService

    service = OSSStorageService()
    pool = SimpleNamespace(
        provider="qiniu",
        provider_alias="Qiniu CN",
        endpoint="https://s3.cn-south-1.qiniucs.com",
        public_base_url="https://qn.woola.fun",
    )
    assert service._is_cloudflare_provider(pool) is False
    assert service._is_qiniu_provider(pool) is True


def test_env_account_id_builds_cloudflare_pool(monkeypatch):
    from app.services.oss_storage_service import OSSStorageService

    _clear_oss_env(monkeypatch)
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("R2_BUCKET", "media")
    service = OSSStorageService()
    pool = service._pick_env_pool()
    assert pool is not None
    assert pool.provider == "cloudflare"
    assert pool.endpoint == "https://acct123.r2.cloudflarestorage.com"
    assert pool.region_name == "auto"
    assert pool.force_path_style is True
    assert pool.bucket == "media"


def test_r2_path_style_key_strips_bucket():
    from app.services.oss_storage_service import OSSStorageService

    service = OSSStorageService()
    pool = SimpleNamespace(
        provider="cloudflare",
        provider_alias=None,
        endpoint="https://acct.r2.cloudflarestorage.com",
        bucket="media",
        public_base_url="https://cdn.example.com",
        root_prefix="aistory/upload",
    )
    key = service._extract_key_for_pool(
        pool,
        candidate_raw="https://acct.r2.cloudflarestorage.com/media/aistory/upload/202611/1/a.jpg",
        parsed=urllib.parse.urlparse(
            "https://acct.r2.cloudflarestorage.com/media/aistory/upload/202611/1/a.jpg"
        ),
        path="media/aistory/upload/202611/1/a.jpg",
    )
    assert key == "aistory/upload/202611/1/a.jpg"


def test_default_grsai_oss_id_is_cloudflare_repository(monkeypatch):
    from app.services.oss_storage_service import (
        DEFAULT_GRSAI_DIRECT_OSS_ID,
        LEGACY_GRSAI_DIRECT_OSS_ID,
        oss_storage_service,
    )

    _clear_oss_env(monkeypatch)
    monkeypatch.setattr(oss_storage_service, "active_cloudflare_grsai_oss_id", lambda db=None: "")
    assert DEFAULT_GRSAI_DIRECT_OSS_ID == "6aef48974bf26bda0f7fbde5"
    assert oss_storage_service.resolve_grsai_direct_oss_id("") == DEFAULT_GRSAI_DIRECT_OSS_ID
    assert oss_storage_service.resolve_grsai_direct_oss_id(LEGACY_GRSAI_DIRECT_OSS_ID) == DEFAULT_GRSAI_DIRECT_OSS_ID


def test_resolve_grsai_oss_id_replaces_legacy_with_cloudflare(monkeypatch):
    from app.services.oss_storage_service import LEGACY_GRSAI_DIRECT_OSS_ID, oss_storage_service

    monkeypatch.setattr(
        oss_storage_service,
        "active_cloudflare_grsai_oss_id",
        lambda db=None: "cf-repo-9",
    )
    assert oss_storage_service.resolve_grsai_direct_oss_id(LEGACY_GRSAI_DIRECT_OSS_ID) == "cf-repo-9"
    assert oss_storage_service.resolve_grsai_direct_oss_id("") == "cf-repo-9"
    assert oss_storage_service.resolve_grsai_direct_oss_id("custom-oss") == "custom-oss"


def test_auto_host_grsai_object_maps_to_cloudflare_and_presigns(monkeypatch):
    from app.services.oss_storage_service import OSSStorageService

    service = OSSStorageService()
    cloudflare = SimpleNamespace(
        provider="cloudflare",
        endpoint="https://acct.r2.cloudflarestorage.com",
        bucket="media",
        public_base_url="https://cdn.example.com",
        root_prefix="",
        is_active=True,
        grsai_oss_id="6aef48974bf26bda0f7fbde5",
        presign_expires_seconds=3600,
    )
    qiniu = SimpleNamespace(
        provider="qiniu",
        endpoint="https://s3.cn-south-1.qiniucs.com",
        bucket="qiniu-bucket",
        public_base_url="https://qn.woola.fun",
        root_prefix="",
        is_active=True,
    )
    image_url = "https://auto/file/images/202611/3/ac3ba61bf2944d67ad458c92d471df17.png"
    pool, key = service._extract_managed_target_from_pools(image_url, [qiniu, cloudflare])
    assert pool is cloudflare
    assert key == "file/images/202611/3/ac3ba61bf2944d67ad458c92d471df17.png"
    assert service.grsai_direct_cloudflare_object_key(image_url) == key

    video_url = "https://auto/file/videos/202611/3/clip.mp4"
    video_pool, video_key = service._extract_managed_target_from_pools(video_url, [cloudflare])
    assert video_pool is cloudflare
    assert video_key == "file/videos/202611/3/clip.mp4"

    qiniu_url = "https://qn.woola.fun/aistory/upload/a.jpg"
    kept_pool, kept_key = service._extract_managed_target_from_pools(qiniu_url, [qiniu, cloudflare])
    assert kept_pool is qiniu
    assert kept_key == "aistory/upload/a.jpg"

    monkeypatch.setattr(service, "_extract_managed_target", lambda url: (cloudflare, key))
    monkeypatch.setattr(service, "_pick_credential", lambda pool: (SimpleNamespace(access_key="ak", secret_key="sk"), None))

    class FakeClient:
        def generate_presigned_url(self, op, Params, ExpiresIn):
            assert op == "get_object"
            assert Params["Bucket"] == "media"
            assert Params["Key"] == key
            assert ExpiresIn == 3600
            return "https://acct.r2.cloudflarestorage.com/media/" + key + "?X-Amz-Signature=abc"

    monkeypatch.setattr(service, "_build_client", lambda pool, cred: FakeClient())
    signed = service.refresh_url(image_url)
    assert signed.startswith("https://acct.r2.cloudflarestorage.com/")
    assert "X-Amz-Signature=abc" in signed


def test_path_style_r2_grsai_url_is_durable_oss_not_temp():
    from app.services.oss_storage_service import OSSStorageService
    from app.services.generation_runtime.media_persist import (
        _is_durable_persisted_media_url,
        _is_ephemeral_provider_media_url,
        _is_provider_direct_oss_url,
    )

    service = OSSStorageService()
    cloudflare = SimpleNamespace(
        provider="cloudflare",
        endpoint="https://bd9e93e4d77bddd376c40ad2f75d1f26.r2.cloudflarestorage.com",
        bucket="woolastory",
        public_base_url="https://cdn.example.com",
        root_prefix="aistory/upload",
        is_active=True,
        grsai_oss_id="6aef48974bf26bda0f7fbde5",
    )
    qiniu = SimpleNamespace(
        provider="qiniu",
        endpoint="https://s3.cn-south-1.qiniucs.com",
        bucket="qiniu-bucket",
        public_base_url="https://qn.woola.fun",
        root_prefix="aistory/upload",
        is_active=True,
    )
    image_url = (
        "https://bd9e93e4d77bddd376c40ad2f75d1f26.r2.cloudflarestorage.com/"
        "woolastory/file/images/202611/3/7fccd92013ac4a56b71499dd78eba94f.png"
        "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ak%2F20261112%2Fauto%2Fs3%2Faws4_request"
        "&X-Amz-Date=20261112T103507Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host"
        "&X-Amz-Signature=140d4c07f4770724f285f6c4c9bf7c76682d3f25dc87c5ea503246c0d89e0431"
    )
    key = "file/images/202611/3/7fccd92013ac4a56b71499dd78eba94f.png"
    assert service.grsai_direct_cloudflare_object_key(image_url) == key
    pool, extracted = service._extract_managed_target_from_pools(image_url, [qiniu, cloudflare])
    assert pool is cloudflare
    assert extracted == key
    assert _is_ephemeral_provider_media_url(image_url) is False
    assert _is_provider_direct_oss_url(image_url, {}) is True
    assert _is_durable_persisted_media_url(image_url, {"provider_direct_oss_url": True}) is True


def test_grsai_cloudflare_object_skips_redownload(monkeypatch):
    from types import SimpleNamespace as NS
    from app.services.generation_runtime import media_persist as mp

    image_url = "https://auto/file/images/202611/3/ac3ba61bf2944d67ad458c92d471df17.png"

    def boom(*args, **kwargs):
        raise AssertionError("should not download")

    monkeypatch.setattr(mp.requests, "get", boom)
    out, meta = mp._persist_remote_image_result(
        NS(id=3),
        image_url,
        {},
        force_configured_oss=True,
    )
    assert out == image_url
    assert meta["provider_direct_oss_url"] is True
    assert mp._is_provider_direct_oss_url(image_url, {}) is True
    assert mp._is_durable_persisted_media_url(image_url, meta) is True


def test_grsai_direct_headers_use_cloudflare_repository(monkeypatch):
    from app.services.media_service import MediaGenerationService
    from app.services.oss_storage_service import LEGACY_GRSAI_DIRECT_OSS_ID, oss_storage_service

    monkeypatch.setattr(
        oss_storage_service,
        "active_cloudflare_grsai_oss_id",
        lambda db=None: "cf-repo-9",
    )
    service = MediaGenerationService()
    headers = service._build_grsai_direct_oss_headers(
        {"_request_user_id": 3, "oss-id": LEGACY_GRSAI_DIRECT_OSS_ID},
        asset_kind="video",
    )
    assert headers["oss-id"] == "cf-repo-9"
    assert headers["oss-path"].startswith("file/videos/")
    assert headers["oss-path"].endswith("/3")
