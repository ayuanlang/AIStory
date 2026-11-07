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
