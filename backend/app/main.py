import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import init_db, SessionLocal
from app.api.notes import router as notes_router
from app.schemas.note import HealthResponse
from app.services.job_service import check_redis_health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Audio Notes Platform backend...")
    init_db()
    logger.info("Database initialized.")
    yield
    # Shutdown
    logger.info("Shutting down backend services.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Full-stack Audio Notes platform using Gnani ASR and AI summarization.",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    logger.info(f"{request.method} {request.url.path} returned {response.status_code} ({duration_ms:.1f}ms)")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


@app.get(f"{settings.API_V1_PREFIX}/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """
    Checks database, redis, storage, and service configurations.
    """
    # 1. Check Database
    db_status = "healthy"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = f"unhealthy: {str(e)}"

    # 2. Check Redis
    redis_status = check_redis_health()

    # 3. Check Storage
    storage_status = f"{settings.STORAGE_PROVIDER} configured"

    # 4. Check API Keys configured
    gnani_ok = bool(settings.GNANI_API_KEY and len(settings.GNANI_API_KEY) > 5)
    gemini_ok = bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 5)
    llm_ok = gemini_ok or bool(settings.LLM_API_KEY and len(settings.LLM_API_KEY) > 5)

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        redis=redis_status,
        storage=storage_status,
        gnani_configured=gnani_ok,
        llm_configured=llm_ok,
        gemini_configured=gemini_ok,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/", tags=["Root"])
def root():
    return {
        "name": settings.PROJECT_NAME,
        "status": "online",
        "docs_url": "/docs",
        "api_prefix": settings.API_V1_PREFIX,
    }


# Include Notes Router
app.include_router(notes_router, prefix=settings.API_V1_PREFIX)
