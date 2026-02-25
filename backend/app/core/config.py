
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# This points to the 'backend' directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    BASE_DIR: Path = BASE_DIR
    PROJECT_NAME: str = "AI Story"
    API_V1_STR: str = "/api/v1"
    
    # Database config with Postgres support for Render
    # Render provides DATABASE_URL starting with postgres:// but SQLAlchemy needs postgresql://
    _db_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/aistory.db")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    
    DATABASE_URL: str = _db_url
    
    # Security (simplistic for demo)
    SECRET_KEY: str = "supersecretkey"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 525600  # 1 year
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    UPLOAD_DIR: str = "uploads"
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    CORS_ALLOW_ORIGIN_REGEX: str = os.getenv("CORS_ALLOW_ORIGIN_REGEX", r"^https://.*\.onrender\.com$")
    MAX_ASSET_UPLOAD_MB: int = int(os.getenv("MAX_ASSET_UPLOAD_MB", "100"))
    MAX_AVATAR_UPLOAD_MB: int = int(os.getenv("MAX_AVATAR_UPLOAD_MB", "5"))

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

settings = Settings()
