"""FastAPI Application entrypoint for Agent Trace Observatory."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.evaluation import router as eval_router
from app.api.routes.export import router as export_router
from app.api.routes.traces import router as traces_router
from app.core.config import settings
from app.core.database import init_db
from app.core.seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    # Verify environment constraints (refuses demo mode in production)
    settings.validate_environment()

    # Initialize SQLite tables and seed data
    init_db()
    seed_database()

    yield


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    description="Deterministic AI Agent Trace Observatory, DAG visualization, token cost attribution, and redaction pipeline.",
    lifespan=lifespan
)

# CORS middleware configuration
origins = [
    settings.frontend_origin,
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://localhost:8080"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Healthcheck endpoint for container orchestration and reverse proxies."""
    return {
        "status": "healthy",
        "service": settings.project_slug,
        "version": settings.version,
        "environment": settings.environment,
        "demo_mode": settings.demo_mode
    }


# Mount API routers
app.include_router(auth_router, prefix="/api")
app.include_router(traces_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(eval_router, prefix="/api")
app.include_router(export_router, prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Redacted fallback error handler preventing stack traces in production."""
    err_str = str(exc)
    # Never expose sensitive tokens in exception payloads
    if "key" in err_str.lower() or "secret" in err_str.lower():
        err_str = "Internal server error occurred."

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": err_str}
    )
