
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api import endpoints, settings as settings_api
from app.db.session import engine
from app.models.all_models import Base
from app.core.logging import LoggingMiddleware, logger
from app.db.init_db import check_and_migrate_tables
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Create DB tables
Base.metadata.create_all(bind=engine)
# Run migrations for existing tables
check_and_migrate_tables()

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(LoggingMiddleware)

# Ensure upload dir exists
import os
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation Error: {exc.errors()}")
    logger.error(f"Body: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)},
    )

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://localhost:5173", # Vite default
]

# Add production domains from env if present
if os.getenv("RENDER_EXTERNAL_URL"):
    origins.append(os.getenv("RENDER_EXTERNAL_URL"))

# Allow all origins for simplicity in this demo/blueprint setup
# In a strict production environment, you should list specific domains
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
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
