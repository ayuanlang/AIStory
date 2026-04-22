import base64
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import random
import time
import urllib.parse
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy import text

from app.db.session import SessionLocal


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


class OSSStorageService:
    def __init__(self) -> None:
        self._credential_cursors: Dict[str, int] = {}

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

        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if getattr(pool, "force_path_style", False) else "virtual"},
        )
        return boto3.client(
            "s3",
            endpoint_url=pool.endpoint,
            region_name=getattr(pool, "region_name", None) or None,
            aws_access_key_id=cred.access_key,
            aws_secret_access_key=cred.secret_key,
            aws_session_token=getattr(cred, "session_token", None),
            config=config,
        )

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

        # Replace random generated filename with a content hash based filename
        # to prevent uploading the same file multiple times with different UUIDs
        content_hash = hashlib.md5(content).hexdigest()
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

        filename = self._normalize_filename(filename, content_type)
        candidate_pools = self._get_active_pools(None)
        if not candidate_pools:
            _visible_warning("OSS upload skipped | reason=pool_not_configured")
            return None

        random.shuffle(candidate_pools)
        for pool in candidate_pools:
            cred, reason = self._pick_credential(pool)
            if not cred:
                if reason:
                    _visible_warning("OSS credential skipped | provider=%s reason=%s", getattr(pool, "provider", None), reason)
                continue

            key = self._build_object_key(pool, user_id=user_id, filename=filename, category=category, object_prefix=object_prefix)
            client = self._build_client(pool, cred)
            extra: Dict[str, Any] = {
                "Bucket": pool.bucket,
                "Key": key,
                "Body": content,
            }
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
                if provider_nm == "backblaze" and st_class == "STANDARD_IA":
                    pass
                else:
                    extra["StorageClass"] = st_class

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
                    len(content),
                    content_type,
                    category,
                    object_prefix,
                    getattr(cred, "label", None),
                    extra.get("StorageClass"),
                )

                # Check if object already exists
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
                        return {
                            "key": key,
                            "url": url,
                            "provider": getattr(pool, "provider", None),
                        }
                except ClientError as ce:
                    # 404 Not Found means we need to upload
                    if ce.response['Error']['Code'] != '404':
                        logger.warning("OSS head_object warning | key=%s err=%s", key, ce)

                try:
                    client.put_object(**extra)
                except Exception as first_exc:
                    if extra.get("StorageClass") and self._is_invalid_storage_class_error(first_exc):
                        invalid_storage_class = extra.pop("StorageClass", None)
                        _visible_warning(
                            "[OSSUploadRetry] provider=%s alias=%s pool_id=%s key=%s reason=invalid_storage_class storage_class=%s",
                            getattr(pool, "provider", None),
                            getattr(pool, "provider_alias", None),
                            getattr(pool, "id", None),
                            key,
                            invalid_storage_class,
                        )
                        client.put_object(**extra)
                    else:
                        raise
                url = self._build_public_url(client, pool, key, cred)
                if not url:
                    _visible_warning(
                        "[OSSUploadResponse] provider=%s alias=%s pool_id=%s key=%s status=no_public_url",
                        getattr(pool, "provider", None),
                        getattr(pool, "provider_alias", None),
                        getattr(pool, "id", None),
                        key,
                    )
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
                return {
                    "url": url,
                    "key": key,
                    "bucket": pool.bucket,
                    "provider": pool.provider,
                    "provider_alias": getattr(pool, "provider_alias", None),
                    "endpoint": pool.endpoint,
                    "public_base_url": self._normalize_public_base_url(pool) or None,
                }
            except Exception as exc:
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
        target_path = str(file_path or "").strip()
        if not target_path or not os.path.exists(target_path):
            return None

        resolved_name = self._normalize_filename(filename or os.path.basename(target_path), content_type)
        guessed_type = content_type or mimetypes.guess_type(resolved_name)[0] or "application/octet-stream"
        try:
            with open(target_path, "rb") as handle:
                return self.upload_bytes(
                    handle.read(),
                    user_id=user_id,
                    filename=resolved_name,
                    content_type=guessed_type,
                    category=category,
                    object_prefix=object_prefix,
                    metadata=metadata,
                    cache_control=cache_control,
                )
        except Exception as exc:
            logger.warning("OSS upload_file failed | path=%s err=%s", target_path, exc)
            return None

    def _extract_managed_target(self, url: str) -> Tuple[Optional[SimpleNamespace], Optional[str]]:
        raw = str(url or "").strip()
        if not raw:
            return None, None

        try:
            parsed = urllib.parse.urlparse(raw)
        except Exception:
            return None, None

        path = urllib.parse.unquote(str(parsed.path or "").lstrip("/"))
        if not path:
            return None, None

        for pool in self._get_all_pools(None):
            public_base_url = self._normalize_public_base_url(pool)
            if public_base_url and raw.startswith(f"{public_base_url}/"):
                extracted_key = raw[len(public_base_url) + 1 :].split("?")[0]
                return pool, urllib.parse.unquote(extracted_key)

            endpoint_host = urllib.parse.urlparse(str(getattr(pool, "endpoint", "") or "")).netloc.lower()
            bucket = str(getattr(pool, "bucket", "") or "").strip()
            if bucket and path.startswith(f"{bucket}/") and parsed.netloc.lower() == endpoint_host:
                return pool, path[len(bucket) + 1 :]
            if parsed.netloc.lower() == endpoint_host:
                return pool, path
            if bucket and parsed.netloc.lower().startswith(f"{bucket}."):
                return pool, path

        return None, None

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