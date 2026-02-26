
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api import endpoints, settings as settings_api
from app.db.session import engine
from app.models.all_models import Base
from app.core.logging import LoggingMiddleware, logger, configure_uvicorn_logging_noise_reduction
from app.db.init_db import check_and_migrate_tables, create_default_superuser, init_initial_data
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Create DB tables
Base.metadata.create_all(bind=engine)
# Run migrations for existing tables and data seeding
check_and_migrate_tables()
create_default_superuser()
init_initial_data()

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_uvicorn_logging_noise_reduction()
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(LoggingMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=settings.GZIP_MINIMUM_SIZE)

# Ensure upload dir exists
import os
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation Error: {exc.errors()}")
    try:
        raw_body = await request.body()
        logger.error(f"Body (truncated): {raw_body[:2048]}")
    except Exception:
        logger.error("Body: <unavailable>")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

# CORS configuration
origins = [item.strip() for item in (settings.CORS_ORIGINS or "").split(",") if item.strip()]
if os.getenv("RENDER_EXTERNAL_URL"):
    render_origin = os.getenv("RENDER_EXTERNAL_URL").strip()
    if render_origin and render_origin not in origins:
        origins.append(render_origin)
if not origins:
    origins = ["http://localhost:3000", "http://localhost:5173"]

origin_regex = (settings.CORS_ALLOW_ORIGIN_REGEX or "").strip() or None

allow_credentials = True
if "*" in origins:
    allow_credentials = False

logger.info(
    "CORS initialized | allow_origins=%s allow_origin_regex=%s allow_credentials=%s",
    origins,
    origin_regex,
    allow_credentials,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=origin_regex,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    if settings.SECURITY_HEADERS_ENABLED:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = f"max-age={settings.SECURITY_HSTS_SECONDS}; includeSubDomains"
    return response

app.include_router(endpoints.router, prefix=settings.API_V1_STR)
app.include_router(settings_api.router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to AI Story API"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # Use import string to enable reload
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
