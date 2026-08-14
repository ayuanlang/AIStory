import base64
import hashlib
import hmac
import io
import json
import logging
import mimetypes
import os
import random
import threading
import time
import urllib.parse
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

# boto3 1.36+ defaults to flexible CRC checksums. Qiniu/TOS S3 gateways
# reject those headers (CreateMultipartUpload 400) or hang on UploadPart.
# Env must be set before boto3/botocore clients are constructed.
os.environ.setdefault("AWS_REQUEST_CHECKSUM_CALCULATION", "WHEN_REQUIRED")
os.environ.setdefault("AWS_RESPONSE_CHECKSUM_VALIDATION", "WHEN_REQUIRED")

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.oss_upload_dedup import (
    complete_oss_upload_claim,
    is_oss_cross_process_dedup_enabled,
    release_oss_upload_claim,
    try_claim_oss_upload,
    wait_for_oss_upload_peer,
)


logger = logging.getLogger(__name__)
activity_logger = logging.getLogger("functional_activity")


def _visible_info(message: str, *args: Any) -> None:
    logger.info(message, *args)
    if activity_logger is not logger:
        activity_logger.info(message, *args)


def _visible_warning(message: str, *args: Any) -> None:
    logger.warning(message, *args)
    if activity_logger is not logger:
        activity_logger.warning(message, *args)


def _env_first(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value is None:
            continue
        stripped = value.strip()
        if stripped:
            return stripped
    return default


def _env_bool(*keys: str, default: bool = False) -> bool:
    value = _env_first(*keys)
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(*keys: str, default: int) -> int:
    raw = _env_first(*keys)
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Process-level upload in-flight dedup: prevents concurrent uploads of the
# same content (same MD5-based key) from wasting bandwidth and OSS writes.
# ---------------------------------------------------------------------------
_OSS_UPLOAD_INFLIGHT_LOCK = threading.Lock()
_OSS_UPLOAD_INFLIGHT: Dict[str, threading.Event] = {}   # key -> event signalled when done
_OSS_UPLOAD_INFLIGHT_RESULTS: Dict[str, Optional[Dict[str, Any]]] = {}  # key -> result
_OSS_UPLOAD_INFLIGHT_RESULTS_MAX = max(
    32,
    int(os.getenv("OSS_UPLOAD_INFLIGHT_RESULTS_MAX", "256") or 256),
)

# Threshold above which put_object is replaced by managed multipart upload.
_OSS_MULTIPART_THRESHOLD_BYTES = max(
    4 * 1024 * 1024,
    int(os.getenv("OSS_MULTIPART_THRESHOLD_MB", "6")) * 1024 * 1024,
)
_OSS_MULTIPART_CHUNK_BYTES = max(
    4 * 1024 * 1024,
    int(os.getenv("OSS_MULTIPART_CHUNK_MB", "6")) * 1024 * 1024,
)
_OSS_HASH_CHUNK_BYTES = max(
    256 * 1024,
    int(os.getenv("OSS_HASH_CHUNK_KB", "1024") or 1024) * 1024,
)


class OSSStorageService:
    def __init__(self) -> None:
        self._credential_cursors: Dict[str, int] = {}
        self._boto3_clients_cache: Dict[str, Any] = {}

    def _urlsafe_b64encode(self, raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode("utf-8")

    def _pool_identity_text(self, pool) -> str:
        return " ".join(
            str(getattr(pool, field, "") or "").strip().lower()
            for field in ("provider", "provider_alias", "endpoint", "public_base_url")
        )

    @staticmethod
    def _is_qiniu_cdn_host(host: str) -> bool:
        hostname = str(host or "").strip().lower().split(":", 1)[0]
        if not hostname:
            return False
        return (
            hostname.endswith("clouddn.com")
            or hostname.endswith("qiniucs.com")
            or hostname.endswith("qiniu.com")
            or hostname.endswith("woola.fun")
            or ".bkt." in hostname
        )

    def _pool_public_host(self, pool) -> str:
        raw = str(getattr(pool, "public_base_url", "") or "").strip()
        if not raw:
            return ""
        if "://" not in raw:
            raw = f"https://{raw}"
        try:
            return str(urllib.parse.urlparse(raw).hostname or "").strip().lower()
        except Exception:
            return ""

    def _is_qiniu_endpoint(self, pool) -> bool:
        endpoint = str(getattr(pool, "endpoint", "") or "").strip().lower()
        return "qiniu" in endpoint or "qiniucs.com" in endpoint or "clouddn.com" in endpoint

    def _is_tos_endpoint(self, pool) -> bool:
        endpoint = str(getattr(pool, "endpoint", "") or "").strip().lower()
        return "volces.com" in endpoint or "ivolces.com" in endpoint or "tos-s3-" in endpoint

    def _is_qiniu_provider(self, pool) -> bool:
        haystack = self._pool_identity_text(pool)
        if any(
            marker in haystack
            for marker in ("qiniu", "qiniucs.com", "clouddn.com", "woola.fun", ".bkt.")
        ):
            return True
        return self._is_qiniu_cdn_host(self._pool_public_host(pool))

    def _is_tos_provider(self, pool) -> bool:
        # Qiniu CDN hosts (qn.woola.fun / clouddn / qiniucs) must never be treated as TOS.
        # A TOS pool that reuses the Qiniu public domain would otherwise emit TOS4
        # signatures that Qiniu rejects with 401.
        if self._is_qiniu_cdn_host(self._pool_public_host(pool)):
            return False
        if self._is_qiniu_endpoint(pool) and not self._is_tos_endpoint(pool):
            return False
        provider = str(getattr(pool, "provider", "") or "").strip().lower()
        if provider in {"tos", "volcengine", "volcengine-tos", "volces", "volc-tos"}:
            return True
        haystack = self._pool_identity_text(pool)
        return any(
            marker in haystack
            for marker in ("volces.com", "ivolces.com", "volcengine-tos", "tos-cn-", "tos-s3-")
        )

    def _is_s3_compat_unsigned_payload(self, pool) -> bool:
        return self._is_qiniu_provider(pool) or self._is_tos_provider(pool)

    @staticmethod
    def _is_tos_object_host(host: str) -> bool:
        hostname = str(host or "").strip().lower().split(":", 1)[0]
        if not hostname or "tos-" not in hostname:
            return False
        return hostname.endswith(".volces.com") or hostname.endswith(".ivolces.com")

    @staticmethod
    def _infer_tos_region(endpoint: str, fallback: str = "cn-beijing") -> str:
        host = str(urllib.parse.urlparse(str(endpoint or "").strip()).hostname or "").strip().lower()
        if not host:
            return fallback
        for prefix in ("tos-s3-", "tos-"):
            if host.startswith(prefix) and (host.endswith(".volces.com") or host.endswith(".ivolces.com")):
                region = host.split(".", 1)[0][len(prefix) :]
                if region:
                    return region
        marker = ".tos-s3-" if ".tos-s3-" in host else ".tos-" if ".tos-" in host else ""
        if marker:
            region = host.split(marker, 1)[-1].split(".", 1)[0]
            if region:
                return region
        return fallback

    @staticmethod
    def _tos_uri_encode(value: str, *, encode_slash: bool = True) -> str:
        encoded: List[str] = []
        for char in str(value or ""):
            if char.isalnum() or char in "-._~" or (char == "/" and not encode_slash):
                encoded.append(char)
            else:
                encoded.append("%{:02X}".format(ord(char)))
        return "".join(encoded)

    def _normalize_public_base_url(self, pool) -> str:
        public_base_url = str(getattr(pool, "public_base_url", "") or "").strip().rstrip("/")
        if not public_base_url:
            return ""

        force_https = self._is_qiniu_provider(pool) or self._is_tos_provider(pool)

        if "://" in public_base_url:
            if force_https and public_base_url.lower().startswith("http://"):
                return f"https://{public_base_url[len('http://') :]}"
            return public_base_url

        endpoint = str(getattr(pool, "endpoint", "") or "").strip()
        endpoint_scheme = urllib.parse.urlparse(endpoint).scheme or ""

        if force_https:
            return f"https://{public_base_url}"

        if endpoint_scheme:
            return f"{endpoint_scheme}://{public_base_url}"

        return f"https://{public_base_url}"

    def _build_qiniu_download_url(self, pool, key: str, cred) -> str:
        public_base_url = self._normalize_public_base_url(pool)
        if not public_base_url:
            return ""

        object_url = f"{public_base_url}/{urllib.parse.quote(key, safe='/~._-')}"
        expires_at = int(time.time()) + int(getattr(pool, "presign_expires_seconds", 7 * 24 * 3600) or 7 * 24 * 3600)
        separator = "&" if "?" in object_url else "?"
        signed_base = f"{object_url}{separator}e={expires_at}"

        access_key = str(getattr(cred, "access_key", "") or "").strip()
        secret_key = str(getattr(cred, "secret_key", "") or "").strip()
        if not access_key or not secret_key:
            return signed_base

        digest = hmac.new(secret_key.encode("utf-8"), signed_base.encode("utf-8"), hashlib.sha1).digest()
        token = f"{access_key}:{self._urlsafe_b64encode(digest)}"
        return f"{signed_base}&token={token}"

    def _build_tos_download_url(self, pool, key: str, cred) -> str:
        public_base_url = self._normalize_public_base_url(pool)
        if not public_base_url:
            return ""

        object_path = urllib.parse.quote(str(key or "").lstrip("/"), safe="/~._-")
        object_url = f"{public_base_url}/{object_path}"
        access_key = str(getattr(cred, "access_key", "") or "").strip()
        secret_key = str(getattr(cred, "secret_key", "") or "").strip()
        if not access_key or not secret_key:
            return object_url

        parsed = urllib.parse.urlparse(public_base_url)
        host = str(parsed.netloc or "").strip().lower()
        if not host:
            return object_url

        now = datetime.utcnow()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        datestamp = now.strftime("%Y%m%d")
        region = str(getattr(pool, "region_name", "") or "").strip() or self._infer_tos_region(
            str(getattr(pool, "endpoint", "") or ""),
            "cn-beijing",
        )
        expires = max(300, int(getattr(pool, "presign_expires_seconds", 7 * 24 * 3600) or 7 * 24 * 3600))
        credential = f"{access_key}/{datestamp}/{region}/tos/request"
        query_params = {
            "X-Tos-Algorithm": "TOS4-HMAC-SHA256",
            "X-Tos-Credential": credential,
            "X-Tos-Date": amz_date,
            "X-Tos-Expires": str(expires),
            "X-Tos-SignedHeaders": "host",
        }
        session_token = str(getattr(cred, "session_token", "") or "").strip()
        if session_token:
            query_params["X-Tos-Security-Token"] = session_token

        canonical_query = "&".join(
            f"{self._tos_uri_encode(name)}={self._tos_uri_encode(value)}"
            for name, value in sorted(query_params.items(), key=lambda item: item[0])
        )
        canonical_uri = "/" + self._tos_uri_encode(str(key or "").lstrip("/"), encode_slash=False)
        canonical_request = "\n".join(
            [
                "GET",
                canonical_uri,
                canonical_query,
                f"host:{host}",
                "",
                "host",
                "UNSIGNED-PAYLOAD",
            ]
        )
        credential_scope = f"{datestamp}/{region}/tos/request"
        string_to_sign = "\n".join(
            [
                "TOS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        def _hmac(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        signing_key = _hmac(
            _hmac(_hmac(_hmac(("TOS4" + secret_key).encode("utf-8"), datestamp), region), "tos"),
            "request",
        )
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{object_url}?{canonical_query}&X-Tos-Signature={signature}"

    def _sanitize_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, str]:
        if not isinstance(metadata, dict) or not metadata:
            return {}

        sanitized: Dict[str, str] = {}
        transformed: List[str] = []
        skip_keys = {
            "prompt",
            "raw",
            "negative_prompt",
            "download_api_key",
            "api_key",
        }
        max_value_bytes = 256
        for raw_key, raw_value in metadata.items():
            if raw_value is None or isinstance(raw_value, (dict, list)):
                continue
            key = str(raw_key or "").strip()
            if not key or key.lower() in skip_keys:
                continue
            try:
                key.encode("ascii")
            except UnicodeEncodeError:
                continue

            value = str(raw_value)
            if len(value.encode("utf-8")) > max_value_bytes:
                continue
            try:
                value.encode("ascii")
                sanitized[key] = value
            except UnicodeEncodeError:
                encoded = urllib.parse.quote(value, safe="-_.~")
                if len(encoded.encode("ascii")) > max_value_bytes:
                    continue
                sanitized[key] = encoded
                transformed.append(key)

        if transformed:
            _visible_info(
                "[OSSMetadataSanitized] transformed_keys=%s",
                ",".join(transformed),
            )
        return sanitized

    def _is_invalid_storage_class_error(self, exc: Exception) -> bool:
        if isinstance(exc, ClientError):
            try:
                code = str((((exc.response or {}).get("Error") or {}).get("Code") or "")).strip()
                if code in ("InvalidStorageClass", "NotImplemented"):
                    return True
            except Exception:
                pass
        return "InvalidStorageClass" in str(exc) or "Backblaze only supports the" in str(exc)

    @staticmethod
    def _format_oss_error(exc: Exception) -> str:
        if isinstance(exc, ClientError):
            response = exc.response or {}
            error = response.get("Error") or {}
            status = ((response.get("ResponseMetadata") or {}).get("HTTPStatusCode"))
            code = str(error.get("Code") or "").strip()
            message = str(error.get("Message") or "").strip()
            parts = [str(exc)]
            if status:
                parts.append(f"status={status}")
            if code:
                parts.append(f"code={code}")
            if message:
                parts.append(f"message={message}")
            return " | ".join(parts)
        return str(exc)

    @staticmethod
    def _is_flexible_checksum_header(name: str, value: str = "") -> bool:
        lower = str(name or "").lower()
        return (
            lower.startswith("x-amz-checksum-")
            or lower in {
                "x-amz-sdk-checksum-algorithm",
                "x-amz-checksum-algorithm",
                "x-amz-checksum-type",
                "x-amz-checksum-mode",
                "x-amz-mp-object-size",
                "x-amz-trailer",
                "x-amz-decoded-content-length",
            }
            or (lower == "content-encoding" and "aws-chunked" in str(value or "").lower())
        )

    @staticmethod
    def _strip_checksum_headers_from_mapping(headers) -> List[str]:
        if headers is None:
            return []
        drop_keys = []
        for key in list(headers.keys()):
            value = str(headers.get(key) or "")
            if OSSStorageService._is_flexible_checksum_header(str(key), value):
                drop_keys.append(key)
        for key in drop_keys:
            try:
                del headers[key]
            except Exception:
                try:
                    headers.pop(key, None)
                except Exception:
                    pass
        return [str(key) for key in drop_keys]

    @staticmethod
    def _drop_checksum_params(params, **kwargs) -> None:
        if not isinstance(params, dict):
            return
        for field in (
            "ChecksumAlgorithm",
            "ChecksumType",
            "ChecksumMode",
            "ChecksumCRC32",
            "ChecksumCRC32C",
            "ChecksumSHA1",
            "ChecksumSHA256",
            "ChecksumCRC64NVME",
            "MpuObjectSize",
        ):
            params.pop(field, None)
        headers = params.get("headers")
        if isinstance(headers, dict):
            OSSStorageService._strip_checksum_headers_from_mapping(headers)

    @staticmethod
    def _strip_flexible_checksum_headers(request=None, params=None, **kwargs) -> None:
        if isinstance(request, dict) and params is None:
            params = request
            request = None
        if request is not None:
            OSSStorageService._strip_checksum_headers_from_mapping(
                getattr(request, "headers", None)
            )
        OSSStorageService._drop_checksum_params(params)

    @staticmethod
    def _log_s3_signed_request(request=None, **kwargs) -> None:
        if request is None:
            return
        headers = getattr(request, "headers", None) or {}
        names = sorted(str(key) for key in headers.keys())
        total = 0
        try:
            for key in headers.keys():
                total += len(str(key).encode("utf-8")) + len(str(headers.get(key) or "").encode("utf-8"))
        except Exception:
            total = -1
        _visible_info(
            "[OSSUploadS3Request] url=%s header_bytes=%s headers=%s",
            str(getattr(request, "url", "") or ""),
            total,
            ",".join(names),
        )

    @staticmethod
    def _log_s3_http_error(http_response=None, parsed=None, **kwargs) -> None:
        status = None
        if http_response is not None:
            status = getattr(http_response, "status_code", None) or getattr(http_response, "status", None)
        if parsed is not None and not status:
            try:
                status = ((parsed.get("ResponseMetadata") or {}).get("HTTPStatusCode"))
            except Exception:
                status = None
        try:
            status_i = int(status or 0)
        except Exception:
            status_i = 0
        if status_i < 400:
            return
        body = ""
        if http_response is not None:
            for attr in ("text", "content", "data"):
                raw = getattr(http_response, attr, None)
                if not raw:
                    continue
                body = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
                break
        _visible_warning(
            "[OSSUploadS3HttpError] status=%s body=%s",
            status_i,
            str(body or "").replace("\n", " ")[:800] or "-",
        )

    def _attach_s3_compat_request_filters(self, client) -> None:
        events = client.meta.events
        # Parent event names match all S3 operations via botocore's hierarchical emitter.
        for event_name in (
            "before-parameter-build.s3",
            "before-call.s3",
            "before-sign.s3",
        ):
            try:
                events.register(event_name, self._strip_flexible_checksum_headers)
            except Exception:
                continue
        try:
            events.register("before-sign.s3", self._log_s3_signed_request)
        except Exception:
            pass
        try:
            events.register("after-call.s3", self._log_s3_http_error)
        except Exception:
            pass

    def _load_json_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
            except Exception:
                return []
            if isinstance(parsed, list):
                return parsed
            return []
        return []

    def _load_json_dict(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except Exception:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    def _as_bool(self, value: Any, *, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _normalize_weights(self, values: Any, target_len: int) -> List[float]:
        if target_len <= 0:
            return []
        raw_values = self._load_json_list(values)
        if not raw_values and isinstance(values, list):
            raw_values = list(values)
        weights: List[float] = []
        for item in raw_values:
            try:
                weight = float(item)
            except Exception:
                weight = 1.0
            weights.append(weight if weight > 0 else 1.0)
        if not weights:
            weights = [1.0] * target_len
        if len(weights) < target_len:
            weights.extend([1.0] * (target_len - len(weights)))
        return weights[:target_len]

    def _normalize_strategy(self, value: Any) -> str:
        raw = str(value or "").strip().lower()
        if raw in {"random", "round_robin", "weighted"}:
            return raw
        return "random"

    def _normalize_credential_entry(self, value: Any) -> Optional[Dict[str, Any]]:
        item = self._load_json_dict(value)
        if not item:
            return None
        access_key = str(item.get("access_key") or item.get("accessKey") or item.get("ak") or "").strip()
        secret_key = str(item.get("secret_key") or item.get("secretKey") or item.get("sk") or "").strip()
        session_token = str(item.get("session_token") or item.get("sessionToken") or item.get("token") or "").strip() or None
        if not access_key or not secret_key:
            return None
        return {
            "access_key": access_key,
            "secret_key": secret_key,
            "session_token": session_token,
            "label": str(item.get("label") or "").strip() or None,
            "weight": item.get("weight"),
            "is_active": self._as_bool(item.get("is_active"), default=True),
        }

    def _normalize_pool_row(self, row: Dict[str, Any]) -> Optional[SimpleNamespace]:
        endpoint = str(row.get("endpoint") or "").strip().rstrip("/")
        bucket = str(row.get("bucket") or "").strip()
        if not endpoint or not bucket:
            return None

        raw_credentials = self._load_json_list(row.get("credentials"))
        credentials: List[Dict[str, Any]] = []
        for entry in raw_credentials:
            normalized = self._normalize_credential_entry(entry)
            if normalized and normalized.get("is_active", True):
                credentials.append(normalized)

        return SimpleNamespace(
            id=int(row.get("id") or 0),
            provider=str(row.get("provider") or "").strip() or "s3",
            provider_alias=str(row.get("provider_alias") or "").strip() or None,
            endpoint=endpoint,
            bucket=bucket,
            public_base_url=str(row.get("public_base_url") or "").strip().rstrip("/"),
            root_prefix=str(row.get("root_prefix") or "").strip().strip("/"),
            region_name=(
                str(row.get("region") or "").strip()
                or (
                    self._infer_tos_region(endpoint, "cn-beijing")
                    if any(marker in endpoint.lower() for marker in ("volces.com", "ivolces.com", "tos-"))
                    else "us-east-1"
                )
            ),
            force_path_style=self._as_bool(row.get("force_path_style"), default=False),
            presign_expires_seconds=max(
                300,
                _env_int(
                    "OSS_PRESIGN_EXPIRES_SECONDS",
                    "TOS_PRESIGN_EXPIRES_SECONDS",
                    "QINIU_PRESIGN_EXPIRES_SECONDS",
                    default=7 * 24 * 3600,
                ),
            ),
            strategy=self._normalize_strategy(row.get("strategy")),
            weights=self._normalize_weights(row.get("weights"), len(credentials)),
            credentials=credentials,
            default_storage_class=str(row.get("default_storage_class") or "").strip() or None,
            is_active=self._as_bool(row.get("is_active"), default=False),
            source="db",
        )

    def _load_db_pools(self, db=None, *, active_only: bool = True) -> List[SimpleNamespace]:
        owned_session = None
        try:
            session = db
            if session is None:
                owned_session = SessionLocal()
                session = owned_session

            result = session.execute(text(
                """
                SELECT id, provider, provider_alias, endpoint, region, bucket,
                       public_base_url, root_prefix, credentials, strategy, weights,
                       default_storage_class, retention_days, force_path_style, is_active,
                       created_at, updated_at
                FROM oss_provider_pools
                """
            ))
            pools: List[SimpleNamespace] = []
            for row in result.mappings().all():
                normalized = self._normalize_pool_row(dict(row))
                if not normalized:
                    continue
                if active_only and not getattr(normalized, "is_active", False):
                    continue
                if active_only and not getattr(normalized, "credentials", None):
                    continue
                pools.append(normalized)
            return pools
        except Exception as exc:
            logger.info("OSS db pool load skipped | err=%s", exc)
            return []
        finally:
            if owned_session is not None:
                owned_session.close()

    def _pick_env_pool(self):
        endpoint = _env_first(
            "OSS_ENDPOINT",
            "QINIU_ENDPOINT",
            "TOS_ENDPOINT",
            "VOLC_TOS_ENDPOINT",
            "S3_ENDPOINT",
            "AWS_S3_ENDPOINT",
        )
        bucket = _env_first(
            "OSS_BUCKET",
            "QINIU_BUCKET",
            "TOS_BUCKET",
            "VOLC_TOS_BUCKET",
            "S3_BUCKET",
            "AWS_STORAGE_BUCKET_NAME",
        )
        if not endpoint or not bucket:
            return None

        explicit_provider = _env_first("OSS_PROVIDER").strip().lower()
        endpoint_lower = endpoint.lower()
        if any(marker in endpoint_lower for marker in ("volces.com", "ivolces.com", "tos-cn-", "tos-s3-")):
            inferred_provider = "tos"
        elif "qiniu" in endpoint_lower:
            inferred_provider = "qiniu"
        else:
            inferred_provider = "s3"
        # A Qiniu endpoint always stays Qiniu so TOS_PROVIDER / TOS_* cannot hijack it.
        if inferred_provider == "qiniu":
            provider = "qiniu"
        elif explicit_provider in {"tos", "qiniu", "s3", "minio", "backblaze"}:
            provider = explicit_provider
        else:
            provider = inferred_provider
        public_base_url = _env_first(
            "OSS_PUBLIC_BASE_URL",
            "QINIU_PUBLIC_BASE_URL",
            "TOS_PUBLIC_BASE_URL",
            "VOLC_TOS_PUBLIC_BASE_URL",
            "S3_PUBLIC_BASE_URL",
        )
        root_prefix = _env_first(
            "OSS_ROOT_PREFIX",
            "QINIU_ROOT_PREFIX",
            "TOS_ROOT_PREFIX",
            default="aistory/upload",
        ).strip().strip("/")
        default_region = (
            self._infer_tos_region(endpoint, "cn-beijing")
            if inferred_provider == "tos"
            else "us-east-1"
        )
        region_name = _env_first(
            "OSS_REGION",
            "TOS_REGION",
            "VOLC_TOS_REGION",
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
            default=default_region,
        )
        force_path_style = _env_bool("OSS_FORCE_PATH_STYLE", "S3_FORCE_PATH_STYLE", default=False)
        presign_expires_seconds = max(
            300,
            _env_int(
                "OSS_PRESIGN_EXPIRES_SECONDS",
                "TOS_PRESIGN_EXPIRES_SECONDS",
                "QINIU_PRESIGN_EXPIRES_SECONDS",
                default=7 * 24 * 3600,
            ),
        )

        return SimpleNamespace(
            id=0,
            provider=provider,
            provider_alias=None,
            endpoint=endpoint.rstrip("/"),
            bucket=bucket,
            public_base_url=public_base_url.rstrip("/"),
            root_prefix=root_prefix,
            region_name=region_name,
            force_path_style=force_path_style,
            presign_expires_seconds=presign_expires_seconds,
            strategy="random",
            weights=[],
            credentials=[],
            default_storage_class=None,
            is_active=True,
            source="env",
        )

    def _get_active_pools(self, db=None) -> List[SimpleNamespace]:
        pools = self._load_db_pools(db, active_only=True)
        if pools:
            return pools
        env_pool = self._pick_env_pool()
        return [env_pool] if env_pool else []

    def _get_all_pools(self, db=None) -> List[SimpleNamespace]:
        pools = self._load_db_pools(db, active_only=False)
        env_pool = self._pick_env_pool()
        if env_pool:
            pools.append(env_pool)
        return pools

    def _pick_pool(self, db=None):
        pools = self._get_active_pools(db)
        if not pools:
            return None
        return random.choice(pools)

    def _pick_credential(self, pool) -> Tuple[Optional[SimpleNamespace], Optional[str]]:
        if not pool:
            return None, "pool_not_configured"

        if getattr(pool, "source", "") == "db":
            entries = list(getattr(pool, "credentials", None) or [])
            if not entries:
                return None, "credential_not_configured"

            strategy = self._normalize_strategy(getattr(pool, "strategy", None))
            provider_key = str(getattr(pool, "provider", "") or getattr(pool, "id", "pool"))
            picked: Optional[Dict[str, Any]] = None
            if strategy == "round_robin":
                cursor = int(self._credential_cursors.get(provider_key, 0))
                picked = entries[cursor % len(entries)]
                self._credential_cursors[provider_key] = cursor + 1
            elif strategy == "weighted":
                raw_weights = []
                for index, item in enumerate(entries):
                    raw_weight = item.get("weight")
                    if raw_weight is None:
                        row_weights = list(getattr(pool, "weights", []) or [])
                        raw_weight = row_weights[index] if index < len(row_weights) else 1.0
                    try:
                        weight = float(raw_weight)
                    except Exception:
                        weight = 1.0
                    raw_weights.append(weight if weight > 0 else 1.0)
                picked = random.choices(entries, weights=raw_weights, k=1)[0]
            else:
                picked = random.choice(entries)

            if not picked:
                return None, "credential_not_configured"
            return SimpleNamespace(
                access_key=str(picked.get("access_key") or "").strip(),
                secret_key=str(picked.get("secret_key") or "").strip(),
                session_token=str(picked.get("session_token") or "").strip() or None,
                label=str(picked.get("label") or "").strip() or None,
            ), None

        if self._is_tos_provider(pool):
            access_key = _env_first(
                "TOS_ACCESS_KEY",
                "VOLC_TOS_ACCESS_KEY",
                "OSS_ACCESS_KEY",
                "AWS_ACCESS_KEY_ID",
            )
            secret_key = _env_first(
                "TOS_SECRET_KEY",
                "VOLC_TOS_SECRET_KEY",
                "OSS_SECRET_KEY",
                "AWS_SECRET_ACCESS_KEY",
            )
        else:
            access_key = _env_first("OSS_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "QINIU_ACCESS_KEY")
            secret_key = _env_first("OSS_SECRET_KEY", "AWS_SECRET_ACCESS_KEY", "QINIU_SECRET_KEY")
        session_token = _env_first("OSS_SESSION_TOKEN", "TOS_SESSION_TOKEN", "AWS_SESSION_TOKEN")
        if not access_key or not secret_key:
            return None, "credential_not_configured"

        return SimpleNamespace(
            access_key=access_key,
            secret_key=secret_key,
            session_token=session_token or None,
        ), None

    def _build_client(self, pool, cred):
        if not pool or not cred:
            raise ValueError("OSS pool or credential missing")

        is_s3_compat = self._is_s3_compat_unsigned_payload(pool)
        cache_key = (
            f"{getattr(pool, 'endpoint', '')}_{getattr(cred, 'access_key', '')}"
            f"_{int(self._is_qiniu_provider(pool))}_{int(self._is_tos_provider(pool))}"
        )
        if cache_key in self._boto3_clients_cache:
            return self._boto3_clients_cache[cache_key]

        # Some S3-compatible providers (including Qiniu gateways) can persist
        # aws-chunked as object Content-Encoding when payload signing is enabled.
        # That can break browser playback (especially over HTTP/2) for video assets.
        s3_config: Dict[str, Any] = {
            "addressing_style": (
                "path"
                if self._is_qiniu_provider(pool) or getattr(pool, "force_path_style", False)
                else "virtual"
            )
        }
        if is_s3_compat:
            s3_config["payload_signing_enabled"] = False

        # connect_timeout: abort TCP handshake if endpoint unreachable.
        # read_timeout: max wait for the HTTP response header after sending all
        # data. For large put_object payloads this fires only after the full
        # body has been flushed, so 600s gives a safe ceiling without masking
        # genuine hung connections.
        _connect_timeout = max(5, int(os.getenv("OSS_CONNECT_TIMEOUT", "15")))
        _read_timeout = max(60, int(os.getenv("OSS_READ_TIMEOUT", "600")))
        config_kwargs: Dict[str, Any] = {
            "signature_version": "s3v4",
            "s3": s3_config,
            "connect_timeout": _connect_timeout,
            "read_timeout": _read_timeout,
            "retries": {"max_attempts": 2, "mode": "standard"},
        }
        # Keep the historical upload_fileobj path, but disable boto3 1.36+
        # flexible CRC headers that Qiniu rejects on CreateMultipartUpload.
        if is_s3_compat:
            config_kwargs["request_checksum_calculation"] = "when_required"
            config_kwargs["response_checksum_validation"] = "when_required"
        try:
            config = Config(**config_kwargs)
        except TypeError:
            config_kwargs.pop("request_checksum_calculation", None)
            config_kwargs.pop("response_checksum_validation", None)
            config = Config(**config_kwargs)
        client = boto3.client(
            "s3",
            endpoint_url=pool.endpoint,
            region_name=getattr(pool, "region_name", None) or None,
            aws_access_key_id=cred.access_key,
            aws_secret_access_key=cred.secret_key,
            aws_session_token=getattr(cred, "session_token", None),
            config=config,
        )
        if is_s3_compat:
            self._attach_s3_compat_request_filters(client)
        self._boto3_clients_cache[cache_key] = client
        return client

    def is_enabled(self, db=None) -> bool:
        for pool in self._get_active_pools(db):
            cred, _ = self._pick_credential(pool)
            if pool and cred:
                return True
        return False

    def _normalize_filename(self, filename: Optional[str], content_type: Optional[str] = None) -> str:
        raw = str(filename or "").strip()
        raw = os.path.basename(raw).replace("\\", "/")
        raw = raw.replace("..", "")
        if not raw:
            ext = mimetypes.guess_extension(content_type or "") or ".bin"
            if ext == ".jpe":
                ext = ".jpg"
            raw = f"generated_{os.urandom(8).hex()}{ext}"
        return raw

    def _content_addressed_filename(
        self,
        filename: str,
        *,
        content_hash: str,
        content_type: Optional[str],
        category: str,
    ) -> str:
        """Rewrite generated filenames to a stable content-hash name."""
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = mimetypes.guess_extension(content_type or "") or ".bin"
            if ext == ".jpe":
                ext = ".jpg"

        prefix_match = ""
        if filename.startswith("gen_"):
            prefix_match = "gen_"
        elif filename.startswith("rh-upload-"):
            prefix_match = "rh-upload-"

        if prefix_match or category == "generated":
            filename = f"{prefix_match}{content_hash[:16]}{ext}"
        return self._normalize_filename(filename, content_type)

    @staticmethod
    def _md5_file(path: str) -> Tuple[str, int]:
        hasher = hashlib.md5()
        size = 0
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(_OSS_HASH_CHUNK_BYTES)
                if not chunk:
                    break
                hasher.update(chunk)
                size += len(chunk)
        return hasher.hexdigest(), size

    @staticmethod
    def _prune_inflight_results_locked() -> None:
        overflow = len(_OSS_UPLOAD_INFLIGHT_RESULTS) - _OSS_UPLOAD_INFLIGHT_RESULTS_MAX
        if overflow <= 0:
            return
        for stale_key in list(_OSS_UPLOAD_INFLIGHT_RESULTS.keys())[:overflow]:
            _OSS_UPLOAD_INFLIGHT_RESULTS.pop(stale_key, None)

    def _finish_inflight_upload(self, key: str, result: Optional[Dict[str, Any]] = None) -> None:
        if result is not None:
            with _OSS_UPLOAD_INFLIGHT_LOCK:
                _OSS_UPLOAD_INFLIGHT_RESULTS[key] = result
                self._prune_inflight_results_locked()
                evt = _OSS_UPLOAD_INFLIGHT.pop(key, None)
        else:
            with _OSS_UPLOAD_INFLIGHT_LOCK:
                evt = _OSS_UPLOAD_INFLIGHT.pop(key, None)
        if evt:
            evt.set()

    def _acquire_inflight_upload(self, key: str) -> Tuple[Optional[threading.Event], Optional[Dict[str, Any]]]:
        """Return (waiter_event, cached_result). waiter_event is None when this caller owns the slot."""
        with _OSS_UPLOAD_INFLIGHT_LOCK:
            cached = _OSS_UPLOAD_INFLIGHT_RESULTS.get(key)
            if cached is not None:
                return None, cached
            if key in _OSS_UPLOAD_INFLIGHT:
                return _OSS_UPLOAD_INFLIGHT[key], None
            _OSS_UPLOAD_INFLIGHT[key] = threading.Event()
            return None, None

    def _build_object_key(
        self,
        pool,
        *,
        user_id: int,
        filename: str,
        category: str = "generated",
        object_prefix: Optional[str] = None,
    ) -> str:
        segments = []
        root_prefix = str(getattr(pool, "root_prefix", "") or "").strip().strip("/")
        if root_prefix:
            segments.append(root_prefix)
        # Year-month top-level bucket keeps any single directory from growing
        # unbounded over time (easier lifecycle/archival management on OSS).
        segments.append(datetime.utcnow().strftime("%Y%m"))
        segments.append(str(user_id or 0))
        if object_prefix:
            cleaned_prefix = str(object_prefix).strip().strip("/")
            if cleaned_prefix:
                segments.append(cleaned_prefix)
        elif category:
            segments.append(str(category).strip().strip("/"))
        segments.append(self._normalize_filename(filename))
        return "/".join(part for part in segments if part)

    def _build_public_url(self, client, pool, key: str, cred=None) -> str:
        public_base_url = self._normalize_public_base_url(pool)
        if public_base_url:
            public_host = self._pool_public_host(pool)
            use_qiniu_sign = (
                self._is_qiniu_cdn_host(public_host) or self._is_qiniu_provider(pool)
            ) and not self._is_tos_object_host(public_host)
            if use_qiniu_sign and _env_bool("OSS_QINIU_SIGNED_URL", "QINIU_SIGNED_URL", default=True):
                return self._build_qiniu_download_url(pool, key, cred)
            if self._is_tos_provider(pool) and _env_bool("OSS_TOS_SIGNED_URL", "TOS_SIGNED_URL", default=True):
                return self._build_tos_download_url(pool, key, cred)
            return f"{public_base_url}/{urllib.parse.quote(key, safe='/~._-')}"

        if not _env_bool("OSS_ALLOW_PRESIGNED_URL", "TOS_ALLOW_PRESIGNED_URL", "QINIU_ALLOW_PRESIGNED_URL", default=True):
            return ""

        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": pool.bucket, "Key": key},
                ExpiresIn=int(getattr(pool, "presign_expires_seconds", 7 * 24 * 3600)),
            )
            return url
        except Exception as exc:
            logger.warning("OSS presign failed | key=%s err=%s", key, exc)
            return ""

    def _build_upload_extra_args(
        self,
        pool,
        *,
        content_type: Optional[str],
        cache_control: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        # Qiniu rejects oversized/unknown x-amz-meta-* and extra S3 headers with a
        # generic 400 before the body is read. Keep PutObject headers minimal.
        if self._is_qiniu_provider(pool):
            return extra
        if cache_control:
            extra["CacheControl"] = cache_control
        sanitized_metadata = self._sanitize_metadata(metadata)
        if sanitized_metadata:
            extra["Metadata"] = sanitized_metadata
        if getattr(pool, "default_storage_class", None):
            st_class = str(pool.default_storage_class)
            provider_nm = str(getattr(pool, "provider", "")).lower()
            if self._is_qiniu_provider(pool) or self._is_tos_provider(pool):
                # Qiniu / TOS S3-compatible endpoints may reject AWS StorageClass values.
                pass
            elif provider_nm == "backblaze" and st_class == "STANDARD_IA":
                pass
            else:
                extra["StorageClass"] = st_class
        return extra

    def _put_or_upload_fileobj(
        self,
        client,
        pool,
        key: str,
        *,
        body_bytes: Optional[bytes] = None,
        file_path: Optional[str] = None,
        content_size: int,
        extra_args: Dict[str, Any],
    ) -> None:
        """Upload from in-memory bytes or a path. Path path never loads the whole file."""
        upload_extra = dict(extra_args or {})
        # Qiniu's S3 gateway returns a generic 400 on CreateMultipartUpload when
        # boto3/s3transfer injects CRC / checksum-type / mp-object-size headers.
        # Keep TOS on managed multipart; Qiniu uses a single PutObject.
        use_multipart = (not self._is_qiniu_provider(pool)) and (
            content_size >= _OSS_MULTIPART_THRESHOLD_BYTES or bool(file_path)
        )

        if use_multipart:
            transfer_cfg = TransferConfig(
                multipart_threshold=_OSS_MULTIPART_THRESHOLD_BYTES,
                multipart_chunksize=_OSS_MULTIPART_CHUNK_BYTES,
                max_concurrency=max(1, int(os.getenv("OSS_MULTIPART_CONCURRENCY", "2"))),
                use_threads=True,
            )
            _visible_info(
                "[OSSUploadMultipart] starting | key=%s bytes=%s threshold=%s chunk=%s source=%s",
                key,
                content_size,
                _OSS_MULTIPART_THRESHOLD_BYTES,
                _OSS_MULTIPART_CHUNK_BYTES,
                "file" if file_path else "bytes",
            )

            def _do_upload(extra: Dict[str, Any]) -> None:
                if file_path:
                    with open(file_path, "rb") as handle:
                        client.upload_fileobj(
                            handle,
                            pool.bucket,
                            key,
                            ExtraArgs=extra if extra else None,
                            Config=transfer_cfg,
                        )
                else:
                    client.upload_fileobj(
                        io.BytesIO(body_bytes or b""),
                        pool.bucket,
                        key,
                        ExtraArgs=extra if extra else None,
                        Config=transfer_cfg,
                    )

            try:
                _do_upload(upload_extra)
            except Exception as mp_exc:
                if upload_extra.get("StorageClass") and self._is_invalid_storage_class_error(mp_exc):
                    upload_extra.pop("StorageClass", None)
                    _do_upload(upload_extra)
                else:
                    raise
            return

        if self._is_qiniu_provider(pool):
            if file_path:
                with open(file_path, "rb") as handle:
                    body = handle.read()
            else:
                body = body_bytes or b""
            put_kwargs: Dict[str, Any] = {
                "Bucket": pool.bucket,
                "Key": key,
                "Body": body,
            }
            content_type = str(upload_extra.get("ContentType") or "").strip()
            if content_type:
                put_kwargs["ContentType"] = content_type
            _visible_info(
                "[OSSUploadPutObject] starting | key=%s bytes=%s source=%s mode=qiniu_bytes",
                key,
                len(body),
                "file" if file_path else "bytes",
            )
            client.put_object(**put_kwargs)
            return

        _visible_info(
            "[OSSUploadPutObject] starting | key=%s bytes=%s source=%s",
            key,
            content_size,
            "file" if file_path else "bytes",
        )

        def _do_put(kwargs: Dict[str, Any]) -> None:
            client.put_object(**kwargs)

        def _put_with_storage_retry(kwargs: Dict[str, Any]) -> None:
            try:
                _do_put(kwargs)
            except Exception as first_exc:
                if kwargs.get("StorageClass") and self._is_invalid_storage_class_error(first_exc):
                    invalid_storage_class = kwargs.pop("StorageClass", None)
                    _visible_warning(
                        "[OSSUploadRetry] provider=%s alias=%s pool_id=%s key=%s reason=invalid_storage_class storage_class=%s",
                        getattr(pool, "provider", None),
                        getattr(pool, "provider_alias", None),
                        getattr(pool, "id", None),
                        key,
                        invalid_storage_class,
                    )
                    _do_put(kwargs)
                else:
                    raise

        if file_path:
            size = int(content_size or os.path.getsize(file_path))
            with open(file_path, "rb") as handle:
                put_kwargs: Dict[str, Any] = {
                    "Bucket": pool.bucket,
                    "Key": key,
                    "Body": handle,
                    "ContentLength": size,
                }
                put_kwargs.update(upload_extra)
                _put_with_storage_retry(put_kwargs)
            return

        body = body_bytes or b""
        put_kwargs = {
            "Bucket": pool.bucket,
            "Key": key,
            "Body": body,
            "ContentLength": len(body),
        }
        put_kwargs.update(upload_extra)
        _put_with_storage_retry(put_kwargs)

    def _upload_with_pools(
        self,
        *,
        user_id: int,
        filename: str,
        content_type: Optional[str],
        category: str,
        object_prefix: Optional[str],
        metadata: Optional[Dict[str, Any]],
        cache_control: Optional[str],
        content_size: int,
        body_bytes: Optional[bytes] = None,
        file_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        candidate_pools = self._get_active_pools(None)
        if not candidate_pools:
            _visible_warning("OSS upload skipped | reason=pool_not_configured")
            return None

        # TOS buckets that still publish via qn.woola.fun / clouddn would mix TOS4
        # signatures onto Qiniu CDN URLs. Prefer a real Qiniu pool when both exist.
        qiniu_safe_pools = [
            pool
            for pool in candidate_pools
            if not (self._is_tos_endpoint(pool) and self._is_qiniu_cdn_host(self._pool_public_host(pool)))
        ]
        if qiniu_safe_pools and len(qiniu_safe_pools) < len(candidate_pools):
            _visible_warning(
                "OSS skipped TOS pool bound to Qiniu CDN public_base_url | kept=%s dropped=%s",
                len(qiniu_safe_pools),
                len(candidate_pools) - len(qiniu_safe_pools),
            )
            candidate_pools = qiniu_safe_pools

        random.shuffle(candidate_pools)
        owned_key: Optional[str] = None
        owned_cross_key: Optional[str] = None
        try:
            for pool in candidate_pools:
                cred, reason = self._pick_credential(pool)
                if not cred:
                    if reason:
                        _visible_warning(
                            "OSS credential skipped | provider=%s reason=%s",
                            getattr(pool, "provider", None),
                            reason,
                        )
                    continue

                key = self._build_object_key(
                    pool,
                    user_id=user_id,
                    filename=filename,
                    category=category,
                    object_prefix=object_prefix,
                )
                client = self._build_client(pool, cred)
                extra_args = self._build_upload_extra_args(
                    pool,
                    content_type=content_type,
                    cache_control=cache_control,
                    metadata=metadata,
                )

                try:
                    _visible_info(
                        "[OSSUploadRequest] provider=%s alias=%s pool_id=%s bucket=%s key=%s endpoint=%s user_id=%s bytes=%s content_type=%s category=%s object_prefix=%s credential_label=%s storage_class=%s",
                        getattr(pool, "provider", None),
                        getattr(pool, "provider_alias", None),
                        getattr(pool, "id", None),
                        getattr(pool, "bucket", None),
                        key,
                        getattr(pool, "endpoint", None),
                        user_id,
                        content_size,
                        content_type,
                        category,
                        object_prefix,
                        getattr(cred, "label", None),
                        extra_args.get("StorageClass"),
                    )

                    # Process-local in-flight dedup for identical content-hash keys.
                    while True:
                        waiter, cached = self._acquire_inflight_upload(key)
                        if cached is not None:
                            _visible_info(
                                "[OSSUploadDedup] reused cached result | key=%s url=%s",
                                key,
                                cached.get("url"),
                            )
                            return cached
                        if waiter is None:
                            owned_key = key
                            break
                        _visible_info("[OSSUploadDedup] waiting for in-flight upload | key=%s", key)
                        waiter.wait(timeout=700)
                        cached = _OSS_UPLOAD_INFLIGHT_RESULTS.get(key)
                        if cached is not None:
                            _visible_info(
                                "[OSSUploadDedup] reused in-flight result | key=%s url=%s",
                                key,
                                cached.get("url"),
                            )
                            return cached
                        # Original upload failed or timed out; retry as owner.

                    # Cross-process claim (web workers + generation worker share DB).
                    if is_oss_cross_process_dedup_enabled():
                        claimed = try_claim_oss_upload(key)
                        if not claimed:
                            _visible_info("[OSSUploadCrossDedup] waiting for peer | key=%s", key)
                            peer_result = wait_for_oss_upload_peer(key)
                            if peer_result:
                                self._finish_inflight_upload(key, peer_result)
                                owned_key = None
                                return peer_result
                            # Peer released without a reusable result; prefer durable OSS head.
                            try:
                                client.head_object(Bucket=pool.bucket, Key=key)
                                url = self._build_public_url(client, pool, key, cred)
                                if url:
                                    upload_result = {
                                        "key": key,
                                        "url": url,
                                        "provider": getattr(pool, "provider", None),
                                        "bucket": getattr(pool, "bucket", None),
                                        "provider_alias": getattr(pool, "provider_alias", None),
                                        "endpoint": getattr(pool, "endpoint", None),
                                        "public_base_url": self._normalize_public_base_url(pool) or None,
                                    }
                                    self._finish_inflight_upload(key, upload_result)
                                    owned_key = None
                                    return upload_result
                            except ClientError as ce:
                                if ce.response["Error"]["Code"] != "404":
                                    logger.warning("OSS head_object warning | key=%s err=%s", key, ce)
                            claimed = try_claim_oss_upload(key)
                            if not claimed:
                                peer_result = wait_for_oss_upload_peer(key)
                                if peer_result:
                                    self._finish_inflight_upload(key, peer_result)
                                    owned_key = None
                                    return peer_result
                                _visible_warning(
                                    "[OSSUploadCrossDedup] proceeding without claim after wait | key=%s",
                                    key,
                                )
                            else:
                                owned_cross_key = key
                        else:
                            owned_cross_key = key

                    # Skip re-upload when object already exists.
                    try:
                        client.head_object(Bucket=pool.bucket, Key=key)
                        _visible_info(
                            "[OSSUploadSkipped] provider=%s alias=%s pool_id=%s bucket=%s key=%s status=already_exists",
                            getattr(pool, "provider", None),
                            getattr(pool, "provider_alias", None),
                            getattr(pool, "id", None),
                            getattr(pool, "bucket", None),
                            key,
                        )
                        url = self._build_public_url(client, pool, key, cred)
                        if url:
                            upload_result = {
                                "key": key,
                                "url": url,
                                "provider": getattr(pool, "provider", None),
                                "bucket": getattr(pool, "bucket", None),
                                "provider_alias": getattr(pool, "provider_alias", None),
                                "endpoint": getattr(pool, "endpoint", None),
                                "public_base_url": self._normalize_public_base_url(pool) or None,
                            }
                            if owned_cross_key == key:
                                complete_oss_upload_claim(key, upload_result)
                                owned_cross_key = None
                            self._finish_inflight_upload(key, upload_result)
                            owned_key = None
                            return upload_result
                    except ClientError as ce:
                        if ce.response["Error"]["Code"] != "404":
                            logger.warning("OSS head_object warning | key=%s err=%s", key, ce)

                    self._put_or_upload_fileobj(
                        client,
                        pool,
                        key,
                        body_bytes=body_bytes,
                        file_path=file_path,
                        content_size=content_size,
                        extra_args=extra_args,
                    )
                    url = self._build_public_url(client, pool, key, cred)
                    if not url:
                        _visible_warning(
                            "[OSSUploadResponse] provider=%s alias=%s pool_id=%s key=%s status=no_public_url",
                            getattr(pool, "provider", None),
                            getattr(pool, "provider_alias", None),
                            getattr(pool, "id", None),
                            key,
                        )
                        if owned_cross_key == key:
                            release_oss_upload_claim(key)
                            owned_cross_key = None
                        self._finish_inflight_upload(key, None)
                        owned_key = None
                        continue

                    _visible_info(
                        "[OSSUploadResponse] provider=%s alias=%s pool_id=%s bucket=%s key=%s status=success url=%s",
                        getattr(pool, "provider", None),
                        getattr(pool, "provider_alias", None),
                        getattr(pool, "id", None),
                        getattr(pool, "bucket", None),
                        key,
                        url,
                    )
                    upload_result = {
                        "url": url,
                        "key": key,
                        "bucket": pool.bucket,
                        "provider": pool.provider,
                        "provider_alias": getattr(pool, "provider_alias", None),
                        "endpoint": pool.endpoint,
                        "public_base_url": self._normalize_public_base_url(pool) or None,
                    }
                    if owned_cross_key == key:
                        complete_oss_upload_claim(key, upload_result)
                        owned_cross_key = None
                    self._finish_inflight_upload(key, upload_result)
                    owned_key = None
                    return upload_result
                except Exception as exc:
                    if owned_cross_key == key:
                        release_oss_upload_claim(key)
                        owned_cross_key = None
                    self._finish_inflight_upload(key, None)
                    owned_key = None
                    _visible_warning(
                        "[OSSUploadResponse] provider=%s alias=%s pool_id=%s bucket=%s key=%s status=error err=%s",
                        getattr(pool, "provider", None),
                        getattr(pool, "provider_alias", None),
                        getattr(pool, "id", None),
                        getattr(pool, "bucket", None),
                        key,
                        self._format_oss_error(exc),
                    )

            return None
        finally:
            if owned_cross_key:
                release_oss_upload_claim(owned_cross_key)
            if owned_key:
                self._finish_inflight_upload(owned_key, None)

    def upload_bytes(
        self,
        content: bytes,
        *,
        user_id: int,
        filename: str,
        content_type: Optional[str] = None,
        category: str = "generated",
        object_prefix: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        cache_control: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not content:
            return None

        content_hash = hashlib.md5(content).hexdigest()
        resolved_name = self._content_addressed_filename(
            filename,
            content_hash=content_hash,
            content_type=content_type,
            category=category,
        )
        return self._upload_with_pools(
            user_id=user_id,
            filename=resolved_name,
            content_type=content_type,
            category=category,
            object_prefix=object_prefix,
            metadata=metadata,
            cache_control=cache_control,
            content_size=len(content),
            body_bytes=content,
        )

    def upload_file(
        self,
        file_path: str,
        *,
        user_id: int,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        category: str = "generated",
        object_prefix: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        cache_control: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Stream a local file to OSS without loading the whole file into RAM."""
        target_path = str(file_path or "").strip()
        if not target_path or not os.path.exists(target_path):
            return None

        resolved_name = self._normalize_filename(filename or os.path.basename(target_path), content_type)
        guessed_type = content_type or mimetypes.guess_type(resolved_name)[0] or "application/octet-stream"
        try:
            content_hash, content_size = self._md5_file(target_path)
            if content_size <= 0:
                return None
            addressed_name = self._content_addressed_filename(
                resolved_name,
                content_hash=content_hash,
                content_type=guessed_type,
                category=category,
            )
            return self._upload_with_pools(
                user_id=user_id,
                filename=addressed_name,
                content_type=guessed_type,
                category=category,
                object_prefix=object_prefix,
                metadata=metadata,
                cache_control=cache_control,
                content_size=content_size,
                file_path=target_path,
            )
        except Exception as exc:
            logger.warning("OSS upload_file failed | path=%s err=%s", target_path, exc)
            return None

    def _extract_key_for_pool(
        self,
        pool,
        *,
        candidate_raw: str,
        parsed: urllib.parse.ParseResult,
        path: str,
    ) -> Optional[str]:
        public_base_url = self._normalize_public_base_url(pool)
        if public_base_url and candidate_raw.startswith(f"{public_base_url}/"):
            extracted_key = candidate_raw[len(public_base_url) + 1 :].split("?")[0]
            return urllib.parse.unquote(extracted_key)

        if public_base_url and public_base_url.lower().startswith("https://"):
            legacy_http_base = f"http://{public_base_url[len('https://') :]}"
            if candidate_raw.startswith(f"{legacy_http_base}/"):
                extracted_key = candidate_raw[len(legacy_http_base) + 1 :].split("?")[0]
                return urllib.parse.unquote(extracted_key)

        host = str(parsed.hostname or parsed.netloc or "").strip().lower().split(":", 1)[0]
        root_prefix = str(getattr(pool, "root_prefix", "") or "").strip().strip("/")
        public_host = self._pool_public_host(pool)

        if host and public_host and host == public_host:
            if not root_prefix or path == root_prefix or path.startswith(f"{root_prefix}/"):
                return path

        if self._is_qiniu_provider(pool) and self._is_qiniu_cdn_host(host):
            if not root_prefix or path == root_prefix or path.startswith(f"{root_prefix}/"):
                return path

        if self._is_tos_provider(pool) and self._is_tos_object_host(host):
            bucket = str(getattr(pool, "bucket", "") or "").strip().lower()
            endpoint_host = urllib.parse.urlparse(str(getattr(pool, "endpoint", "") or "")).netloc.lower()
            host_matches_pool = (
                (bucket and (host == f"{bucket}.{endpoint_host}" or host.startswith(f"{bucket}.")))
                or (endpoint_host and host == endpoint_host)
            )
            if host_matches_pool and (not root_prefix or path == root_prefix or path.startswith(f"{root_prefix}/")):
                return path

        endpoint_host = urllib.parse.urlparse(str(getattr(pool, "endpoint", "") or "")).netloc.lower()
        bucket = str(getattr(pool, "bucket", "") or "").strip()
        if bucket and path.startswith(f"{bucket}/") and host == endpoint_host:
            return path[len(bucket) + 1 :]
        if host == endpoint_host:
            return path
        if bucket and host.startswith(f"{bucket}."):
            return path
        return None

    def _score_pool_for_url(self, pool, parsed: urllib.parse.ParseResult) -> int:
        host = str(parsed.hostname or "").strip().lower()
        score = 0
        public_host = self._pool_public_host(pool)
        if host and public_host and host == public_host:
            score += 100
        if self._is_qiniu_cdn_host(host):
            if self._is_qiniu_endpoint(pool):
                score += 80
            elif self._is_qiniu_provider(pool):
                score += 60
            if self._is_tos_endpoint(pool):
                score -= 120
        if self._is_tos_object_host(host) and self._is_tos_provider(pool):
            score += 80
        return score

    def _extract_managed_target_from_pools(
        self,
        url: str,
        pools: Optional[List[SimpleNamespace]],
    ) -> Tuple[Optional[SimpleNamespace], Optional[str]]:
        raw = str(url or "").strip()
        if not raw or not pools:
            return None, None

        candidate_raw = raw
        if "://" not in candidate_raw and "/" in candidate_raw:
            host_part = candidate_raw.split("/", 1)[0].strip().lower()
            if self._is_qiniu_cdn_host(host_part) or self._is_tos_object_host(host_part):
                candidate_raw = f"https://{candidate_raw}"

        try:
            parsed = urllib.parse.urlparse(candidate_raw)
        except Exception:
            return None, None

        path = urllib.parse.unquote(str(parsed.path or "").lstrip("/"))
        if not path:
            return None, None

        best: Optional[Tuple[int, SimpleNamespace, str]] = None
        for pool in pools:
            extracted_key = self._extract_key_for_pool(
                pool,
                candidate_raw=candidate_raw,
                parsed=parsed,
                path=path,
            )
            if not extracted_key:
                continue
            score = self._score_pool_for_url(pool, parsed)
            if best is None or score > best[0]:
                best = (score, pool, extracted_key)
        if best is None:
            return None, None
        return best[1], best[2]

    def _extract_managed_target(self, url: str) -> Tuple[Optional[SimpleNamespace], Optional[str]]:
        return self._extract_managed_target_from_pools(url, self._get_all_pools(None))

    def match_active_pool(self, url: str, db=None) -> Tuple[Optional[SimpleNamespace], Optional[str]]:
        return self._extract_managed_target_from_pools(url, self._get_active_pools(db))

    def is_active_managed_url(self, url: str, db=None) -> bool:
        pool, key = self.match_active_pool(url, db)
        return bool(pool and key)

    def _pool_url_hosts(self, pool: SimpleNamespace) -> List[str]:
        hosts: List[str] = []
        public_base_url = self._normalize_public_base_url(pool)
        if public_base_url:
            try:
                host = str(urllib.parse.urlparse(public_base_url).hostname or "").strip().lower()
                if host:
                    hosts.append(host)
            except Exception:
                pass
        endpoint = str(getattr(pool, "endpoint", "") or "").strip()
        if endpoint:
            try:
                host = str(urllib.parse.urlparse(endpoint).hostname or "").strip().lower()
                if host:
                    hosts.append(host)
            except Exception:
                pass
        bucket = str(getattr(pool, "bucket", "") or "").strip().lower()
        if bucket:
            hosts.append(f"{bucket}.{hosts[-1]}" if hosts else bucket)
        return sorted(set(host for host in hosts if host))

    def get_active_url_signatures(self, db=None) -> Dict[str, Any]:
        pools = self._get_active_pools(db)
        public_base_urls: List[str] = []
        hostnames: List[str] = []
        providers: List[str] = []
        for pool in pools:
            provider = str(getattr(pool, "provider", "") or "").strip()
            if provider:
                providers.append(provider)
            public_base_url = self._normalize_public_base_url(pool)
            if public_base_url:
                public_base_urls.append(public_base_url.rstrip("/"))
            hostnames.extend(self._pool_url_hosts(pool))
        return {
            "oss_enabled": bool(pools),
            "pool_count": len(pools),
            "providers": sorted(set(providers)),
            "public_base_urls": sorted(set(public_base_urls)),
            "hostnames": sorted(set(hostnames)),
        }

    def inspect_media_url(self, url: str, db=None) -> Dict[str, Any]:
        raw = str(url or "").strip()
        signatures = self.get_active_url_signatures(db)
        oss_enabled = bool(signatures.get("oss_enabled"))
        active_pool, active_key = self.match_active_pool(raw, db)
        any_pool, any_key = self._extract_managed_target(raw)
        parsed_host = ""
        try:
            parsed_host = str(urllib.parse.urlparse(raw).hostname or "").strip().lower()
        except Exception:
            parsed_host = ""

        local_upload = raw.startswith("/uploads/") or (
            raw.startswith("/") and not raw.startswith("//") and not raw.startswith("/uploads/")
        )
        host_matches_signature = bool(parsed_host and parsed_host in set(signatures.get("hostnames") or []))
        public_prefix_match = any(
            raw.startswith(f"{base}/") or raw == base
            for base in (signatures.get("public_base_urls") or [])
            if base
        )

        return {
            "url": raw,
            "oss_enabled": oss_enabled,
            "local_upload": bool(local_upload),
            "matches_active_oss_pool": bool(active_pool and active_key),
            "matches_any_configured_pool": bool(any_pool and any_key),
            "host_matches_signature": host_matches_signature,
            "public_base_prefix_match": public_prefix_match,
            "oss": {
                "provider": getattr(active_pool, "provider", None) if active_pool else getattr(any_pool, "provider", None),
                "bucket": getattr(active_pool, "bucket", None) if active_pool else getattr(any_pool, "bucket", None),
                "key": active_key or any_key,
                "endpoint": getattr(active_pool, "endpoint", None) if active_pool else getattr(any_pool, "endpoint", None),
            } if (active_key or any_key) else None,
        }

    def is_managed_url(self, url: str) -> bool:
        _, key = self._extract_managed_target(url)
        return bool(key)

    def refresh_url(self, url: str) -> str:
        """Refresh a managed URL if it is a presigned URL or uses Qiniu/TOS signed URL, else return it."""
        raw = str(url or "").strip()
        if not raw:
            return raw

        pool, key = self._extract_managed_target(raw)
        if not pool or not key:
            return raw

        cred, _ = self._pick_credential(pool)
        if not cred:
            return raw

        try:
            client = self._build_client(pool, cred)
            refreshed = self._build_public_url(client, pool, key, cred)
            return str(refreshed or raw)
        except Exception as exc:
            logger.warning("OSS refresh_url failed | key=%s err=%s", key, exc)
            return raw

    def delete_url(self, url: str) -> bool:
        pool, key = self._extract_managed_target(url)
        if not pool or not key:
            return False

        cred, _ = self._pick_credential(pool)
        if not pool or not cred:
            return False

        try:
            client = self._build_client(pool, cred)
            client.delete_object(Bucket=pool.bucket, Key=key)
            return True
        except Exception as exc:
            logger.warning("OSS delete failed | key=%s err=%s", key, exc)
            return False


oss_storage_service = OSSStorageService()