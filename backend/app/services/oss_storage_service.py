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

    def _is_qiniu_provider(self, pool) -> bool:
        provider = str(getattr(pool, "provider", "") or "").strip().lower()
        provider_alias = str(getattr(pool, "provider_alias", "") or "").strip().lower()
        endpoint = str(getattr(pool, "endpoint", "") or "").strip().lower()
        public_base_url = str(getattr(pool, "public_base_url", "") or "").strip().lower()
        return any(
            marker in provider or marker in provider_alias or marker in endpoint or marker in public_base_url
            for marker in ("qiniu", "qiniucs.com", "clouddn.com", ".bkt.")
        )

    def _normalize_public_base_url(self, pool) -> str:
        public_base_url = str(getattr(pool, "public_base_url", "") or "").strip().rstrip("/")
        if not public_base_url:
            return ""
        
        is_qiniu = self._is_qiniu_provider(pool)

        if "://" in public_base_url:
            if is_qiniu and public_base_url.lower().startswith("http://"):
                return f"https://{public_base_url[len('http://') :]}"
            return public_base_url
            
        endpoint = str(getattr(pool, "endpoint", "") or "").strip()
        endpoint_scheme = urllib.parse.urlparse(endpoint).scheme or ""
        
        if is_qiniu:
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

    def _sanitize_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, str]:
        if not isinstance(metadata, dict) or not metadata:
            return {}

        sanitized: Dict[str, str] = {}
        transformed: List[str] = []
        for raw_key, raw_value in metadata.items():
            if raw_value is None:
                continue
            key = str(raw_key or "").strip()
            if not key:
                continue
            try:
                key.encode("ascii")
            except UnicodeEncodeError:
                continue

            value = str(raw_value)
            try:
                value.encode("ascii")
                sanitized[key] = value
            except UnicodeEncodeError:
                encoded = urllib.parse.quote(value, safe="-_.~")
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
            region_name=str(row.get("region") or "us-east-1").strip() or "us-east-1",
            force_path_style=self._as_bool(row.get("force_path_style"), default=False),
            presign_expires_seconds=max(300, _env_int("OSS_PRESIGN_EXPIRES_SECONDS", "QINIU_PRESIGN_EXPIRES_SECONDS", default=7 * 24 * 3600)),
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
        endpoint = _env_first("OSS_ENDPOINT", "QINIU_ENDPOINT", "S3_ENDPOINT", "AWS_S3_ENDPOINT")
        bucket = _env_first("OSS_BUCKET", "QINIU_BUCKET", "S3_BUCKET", "AWS_STORAGE_BUCKET_NAME")
        if not endpoint or not bucket:
            return None

        provider = _env_first("OSS_PROVIDER", default=("qiniu" if "qiniu" in endpoint.lower() else "s3"))
        public_base_url = _env_first("OSS_PUBLIC_BASE_URL", "QINIU_PUBLIC_BASE_URL", "S3_PUBLIC_BASE_URL")
        root_prefix = _env_first("OSS_ROOT_PREFIX", "QINIU_ROOT_PREFIX", default="aistory/upload").strip().strip("/")
        region_name = _env_first("OSS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION", default="us-east-1")
        force_path_style = _env_bool("OSS_FORCE_PATH_STYLE", "S3_FORCE_PATH_STYLE", default=False)
        presign_expires_seconds = max(
            300,
            _env_int("OSS_PRESIGN_EXPIRES_SECONDS", "QINIU_PRESIGN_EXPIRES_SECONDS", default=7 * 24 * 3600),
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

        access_key = _env_first("OSS_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "QINIU_ACCESS_KEY")
        secret_key = _env_first("OSS_SECRET_KEY", "AWS_SECRET_ACCESS_KEY", "QINIU_SECRET_KEY")
        session_token = _env_first("OSS_SESSION_TOKEN", "AWS_SESSION_TOKEN")
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

        cache_key = f"{getattr(pool, 'endpoint', '')}_{getattr(cred, 'access_key', '')}"
        if cache_key in self._boto3_clients_cache:
            return self._boto3_clients_cache[cache_key]

        # Some S3-compatible providers (including Qiniu gateways) can persist
        # aws-chunked as object Content-Encoding when payload signing is enabled.
        # That can break browser playback (especially over HTTP/2) for video assets.
        s3_config: Dict[str, Any] = {
            "addressing_style": "path" if getattr(pool, "force_path_style", False) else "virtual"
        }
        if self._is_qiniu_provider(pool):
            s3_config["payload_signing_enabled"] = False

        # connect_timeout: abort TCP handshake if endpoint unreachable.
        # read_timeout: max wait for the HTTP response header after sending all
        # data. For large put_object payloads this fires only after the full
        # body has been flushed, so 600s gives a safe ceiling without masking
        # genuine hung connections.
        _connect_timeout = max(5, int(os.getenv("OSS_CONNECT_TIMEOUT", "15")))
        _read_timeout = max(60, int(os.getenv("OSS_READ_TIMEOUT", "600")))
        config = Config(
            signature_version="s3v4",
            s3=s3_config,
            connect_timeout=_connect_timeout,
            read_timeout=_read_timeout,
            retries={"max_attempts": 2, "mode": "standard"},
        )
        client = boto3.client(
            "s3",
            endpoint_url=pool.endpoint,
            region_name=getattr(pool, "region_name", None) or None,
            aws_access_key_id=cred.access_key,
            aws_secret_access_key=cred.secret_key,
            aws_session_token=getattr(cred, "session_token", None),
            config=config,
        )
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
            if self._is_qiniu_provider(pool) and _env_bool("OSS_QINIU_SIGNED_URL", "QINIU_SIGNED_URL", default=True):
                return self._build_qiniu_download_url(pool, key, cred)
            return f"{public_base_url}/{urllib.parse.quote(key, safe='/~._-')}"

        if not _env_bool("OSS_ALLOW_PRESIGNED_URL", "QINIU_ALLOW_PRESIGNED_URL", default=True):
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
        if cache_control:
            extra["CacheControl"] = cache_control
        sanitized_metadata = self._sanitize_metadata(metadata)
        if sanitized_metadata:
            extra["Metadata"] = sanitized_metadata
        if getattr(pool, "default_storage_class", None):
            st_class = str(pool.default_storage_class)
            provider_nm = str(getattr(pool, "provider", "")).lower()
            if self._is_qiniu_provider(pool):
                # Qiniu S3-compatible endpoint may reject StorageClass values from AWS semantics.
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
        use_multipart = content_size >= _OSS_MULTIPART_THRESHOLD_BYTES or bool(file_path)
        upload_extra = dict(extra_args or {})

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

        put_kwargs: Dict[str, Any] = {
            "Bucket": pool.bucket,
            "Key": key,
            "Body": body_bytes or b"",
        }
        put_kwargs.update(upload_extra)
        try:
            client.put_object(**put_kwargs)
        except Exception as first_exc:
            if put_kwargs.get("StorageClass") and self._is_invalid_storage_class_error(first_exc):
                invalid_storage_class = put_kwargs.pop("StorageClass", None)
                _visible_warning(
                    "[OSSUploadRetry] provider=%s alias=%s pool_id=%s key=%s reason=invalid_storage_class storage_class=%s",
                    getattr(pool, "provider", None),
                    getattr(pool, "provider_alias", None),
                    getattr(pool, "id", None),
                    key,
                    invalid_storage_class,
                )
                client.put_object(**put_kwargs)
            else:
                raise

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
                        exc,
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
            if host_part.endswith("clouddn.com") or host_part.endswith("qiniucs.com") or ".bkt." in host_part:
                candidate_raw = f"https://{candidate_raw}"

        try:
            parsed = urllib.parse.urlparse(candidate_raw)
        except Exception:
            return None, None

        path = urllib.parse.unquote(str(parsed.path or "").lstrip("/"))
        if not path:
            return None, None

        for pool in pools:
            public_base_url = self._normalize_public_base_url(pool)
            if public_base_url and candidate_raw.startswith(f"{public_base_url}/"):
                extracted_key = candidate_raw[len(public_base_url) + 1 :].split("?")[0]
                return pool, urllib.parse.unquote(extracted_key)

            if (
                self._is_qiniu_provider(pool)
                and public_base_url
                and public_base_url.lower().startswith("https://")
            ):
                legacy_http_base = f"http://{public_base_url[len('https://') :]}"
                if candidate_raw.startswith(f"{legacy_http_base}/"):
                    extracted_key = candidate_raw[len(legacy_http_base) + 1 :].split("?")[0]
                    return pool, urllib.parse.unquote(extracted_key)

            if self._is_qiniu_provider(pool):
                host = str(parsed.netloc or "").strip().lower()
                root_prefix = str(getattr(pool, "root_prefix", "") or "").strip().strip("/")
                # Include custom CDN domains (e.g. qn.woola.fun) used by provider-direct OSS writes.
                if host and (
                    host.endswith("clouddn.com")
                    or host.endswith("qiniucs.com")
                    or host.endswith("woola.fun")
                    or ".bkt." in host
                ):
                    if not root_prefix or path == root_prefix or path.startswith(f"{root_prefix}/"):
                        return pool, path

            endpoint_host = urllib.parse.urlparse(str(getattr(pool, "endpoint", "") or "")).netloc.lower()
            bucket = str(getattr(pool, "bucket", "") or "").strip()
            if bucket and path.startswith(f"{bucket}/") and parsed.netloc.lower() == endpoint_host:
                return pool, path[len(bucket) + 1 :]
            if parsed.netloc.lower() == endpoint_host:
                return pool, path
            if bucket and parsed.netloc.lower().startswith(f"{bucket}."):
                return pool, path

        return None, None

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
        """Refresh a managed URL if it is a presigned URL or uses Qiniu signed URL, else return it."""
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