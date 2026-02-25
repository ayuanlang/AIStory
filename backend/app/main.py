
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# Create DB tables
Base.metadata.create_all(bind=engine)
# Run migrations for existing tables and data seeding
check_and_migrate_tables()
create_default_superuser()
init_initial_data()

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_uvicorn_logging_noise_reduction()
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(LoggingMiddleware)

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

allow_credentials = True
if "*" in origins:
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router, prefix=settings.API_V1_STR)
app.include_router(settings_api.router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to AI Story API"}

if __name__ == "__main__":
    import uvicorn
    # Use import string to enable reload
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
