
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
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
