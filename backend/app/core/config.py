
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# This points to the 'backend' directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

def _env_or_default(key: str, default: str) -> str:
    value = os.getenv(key)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _path_env_or_default(key: str, default_relative: str) -> str:
    value = os.getenv(key)
    raw = value.strip() if value and value.strip() else default_relative
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path.resolve())

class Settings(BaseSettings):
    BASE_DIR: Path = BASE_DIR
    PROJECT_NAME: str = "AI Story"
    API_V1_STR: str = "/api/v1"
    
    # Database config with Postgres support for Render
    # Render provides DATABASE_URL starting with postgres:// but SQLAlchemy needs postgresql://
    _db_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/aistory.db")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)

    # Render external DB URL as fallback when internal DNS fails
    _db_url_ext: str = os.getenv("DATABASE_URL_EXTERNAL", "")
    if _db_url_ext.startswith("postgres://"):
        _db_url_ext = _db_url_ext.replace("postgres://", "postgresql://", 1)
    DATABASE_URL_EXTERNAL: str = _db_url_ext

    DATABASE_URL: str = _db_url
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "270"))
    DB_POOL_PRE_PING: bool = os.getenv("DB_POOL_PRE_PING", "1") not in {"0", "false", "False"}
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200"))
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    UPLOAD_DIR: str = _path_env_or_default("UPLOAD_DIR", "uploads")
    SECURITY_HEADERS_ENABLED: bool = os.getenv("SECURITY_HEADERS_ENABLED", "1") not in {"0", "false", "False"}
    SECURITY_HSTS_SECONDS: int = int(os.getenv("SECURITY_HSTS_SECONDS", "31536000"))
    GZIP_MINIMUM_SIZE: int = int(os.getenv("GZIP_MINIMUM_SIZE", "1024"))
    RATE_LIMIT_LOGIN: str = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
    RATE_LIMIT_RESET: str = os.getenv("RATE_LIMIT_RESET", "3/minute")
    CORS_ORIGINS: str = _env_or_default(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,https://aistory.pro,https://www.aistory.pro,https://aistory-frontend.onrender.com",
    )
    CORS_ALLOW_ORIGIN_REGEX: str = _env_or_default("CORS_ALLOW_ORIGIN_REGEX", r"^https://.*\.onrender\.com$")
    MAX_ASSET_UPLOAD_MB: int = int(os.getenv("MAX_ASSET_UPLOAD_MB", "100"))
    MAX_AVATAR_UPLOAD_MB: int = int(os.getenv("MAX_AVATAR_UPLOAD_MB", "5"))
    WEBHOOK_HMAC_KEY: str = os.getenv("WEBHOOK_HMAC_KEY", "").strip()
    # KIE can use a dedicated webhook secret; falls back to WEBHOOK_HMAC_KEY when unset.
    KIE_WEBHOOK_HMAC_KEY: str = os.getenv("KIE_WEBHOOK_HMAC_KEY", "").strip()
    # Secure-by-default: reject unsigned callbacks unless explicitly allowed.
    WEBHOOK_HMAC_ALLOW_UNSIGNED: bool = os.getenv("WEBHOOK_HMAC_ALLOW_UNSIGNED", "0") in {"1", "true", "True"}
    WEBHOOK_TIMESTAMP_MAX_SKEW_SECONDS: int = int(os.getenv("WEBHOOK_TIMESTAMP_MAX_SKEW_SECONDS", "300"))
    UPLOAD_CACHE_CONTROL: str = os.getenv("UPLOAD_CACHE_CONTROL", "public, max-age=604800").strip()

    # Email (Password Reset)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "1") not in {"0", "false", "False"}
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "")
    
    # Render Specific
    RENDER_EXTERNAL_URL: str = os.getenv("RENDER_EXTERNAL_URL", "")

    # WeChat Pay
    WECHAT_APPID: str = os.getenv("WECHAT_APPID", "")
    WECHAT_MCHID: str = os.getenv("WECHAT_MCHID", "")
    WECHAT_API_V3_KEY: str = os.getenv("WECHAT_API_V3_KEY", "")
    WECHAT_PRIVATE_KEY_PATH: str = os.getenv("WECHAT_PRIVATE_KEY_PATH", "") # Path to .pem
    WECHAT_CERT_SERIAL_NO: str = os.getenv("WECHAT_CERT_SERIAL_NO", "")
    WECHAT_NOTIFY_URL: str = os.getenv("WECHAT_NOTIFY_URL", "")

    # Optional search API keys when not configured in Admin > 系统 API (Tools providers).
    SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "").strip()
    BRAVE_SEARCH_API_KEY: str = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "").strip()
    # Cloud deploys (Render etc.) cannot reach html.duckduckgo.com reliably.
    # Set to 1/true to skip DuckDuckGo HTML scraping; auto-enabled when RENDER is set.
    DISABLE_DDG_HTML_SEARCH: str = os.getenv("DISABLE_DDG_HTML_SEARCH", "").strip()
    # Optional override, comma-separated: serper,brave,tavily,ddg_html,ddgs,bing_html,searxng
    SEARCH_BACKENDS: str = os.getenv("SEARCH_BACKENDS", "").strip()
    # After SERP rank: fetch body for top-K URLs (always, not only weak snippets).
    SEARCH_ENRICH_TOP_K: int = max(0, int(os.getenv("SEARCH_ENRICH_TOP_K", "5") or 5))
    SEARCH_SNIPPET_MAX_LEN: int = max(200, int(os.getenv("SEARCH_SNIPPET_MAX_LEN", "800") or 800))
    SEARCH_EXCERPT_MAX_LEN: int = max(400, int(os.getenv("SEARCH_EXCERPT_MAX_LEN", "2000") or 2000))
    SEARCH_ALWAYS_ENRICH_TOP_K: bool = os.getenv("SEARCH_ALWAYS_ENRICH_TOP_K", "1") not in {
        "0",
        "false",
        "False",
    }
    TAVILY_SEARCH_DEPTH: str = (os.getenv("TAVILY_SEARCH_DEPTH", "advanced") or "advanced").strip().lower()
    TAVILY_INCLUDE_RAW_CONTENT: bool = os.getenv("TAVILY_INCLUDE_RAW_CONTENT", "1") not in {
        "0",
        "false",
        "False",
    }

    # Daily DB backup + stale project retention (Asia/Shanghai 03:00 scheduler).
    # Default on for Render; off for local/dev unless explicitly enabled.
    RUN_MAINTENANCE_SCHEDULER: bool = os.getenv(
        "RUN_MAINTENANCE_SCHEDULER",
        "1" if os.getenv("RENDER") else "0",
    ) not in {"0", "false", "False"}
    DB_BACKUP_DIR: str = _path_env_or_default("DB_BACKUP_DIR", "backups/db")
    DB_BACKUP_KEEP_COUNT: int = max(1, int(os.getenv("DB_BACKUP_KEEP_COUNT", "7") or 7))
    PROJECT_BACKUP_DIR: str = _path_env_or_default("PROJECT_BACKUP_DIR", "backups/projects")
    PROJECT_RETENTION_DAYS: int = max(1, int(os.getenv("PROJECT_RETENTION_DAYS", "60") or 60))
    PROJECT_BACKUP_KEEP_DAYS: int = max(1, int(os.getenv("PROJECT_BACKUP_KEEP_DAYS", "60") or 60))
    # Manual admin purge default filter: 0 = all projects idle for PROJECT_RETENTION_DAYS.
    # Set to 1 to only list/purge soft-deleted projects.
    PROJECT_RETENTION_REQUIRE_SOFT_DELETED: bool = os.getenv(
        "PROJECT_RETENTION_REQUIRE_SOFT_DELETED", "0"
    ) not in {"0", "false", "False"}

    # Nightly billing reconcile (query provider actual usage for recent API txs)
    BILLING_RECONCILE_ENABLED: bool = os.getenv("BILLING_RECONCILE_ENABLED", "1") not in {"0", "false", "False"}
    BILLING_RECONCILE_LOOKBACK_DAYS: int = max(1, int(os.getenv("BILLING_RECONCILE_LOOKBACK_DAYS", "3") or 3))
    BILLING_RECONCILE_MAX_ROWS: int = max(1, int(os.getenv("BILLING_RECONCILE_MAX_ROWS", "500") or 500))
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
