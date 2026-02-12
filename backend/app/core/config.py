
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
    UPLOAD_DIR: str = "uploads"
    
    class Config:
        env_file = ".env"

settings = Settings()
