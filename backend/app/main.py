"""
RepoMind — FastAPI Application Entry Point

This is the main application file. It:
1. Creates the FastAPI app with metadata
2. Configures CORS middleware for frontend communication
3. Sets up Firebase Auth middleware
4. Registers global error handlers
5. Pre-loads ML models on startup (lifespan)
6. Registers the health endpoint
7. Includes all API routers

Architecture Reference:
    - System Architecture: Section 5 (Backend Architecture)
    - API Documentation: Section 5 (Health Endpoint)
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import RepoMindError
from app.api import repos, query, analysis, experiments
from app.middleware.firebase_auth import firebase_auth_middleware
from app.services.firebase_service import FirebaseService
from app.services.pipeline_registry import PipelineRegistry

logger = logging.getLogger(__name__)

# ─── Shared service instances ───
firebase_service = FirebaseService()
pipeline_registry = PipelineRegistry()

# ─── Track server uptime ───
_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler for startup and shutdown events.

    Startup:
        - Record server start time
        - Pre-load embedding model and LLM client

    Shutdown:
        - (Future: cleanup temp dirs, save indexes to storage)

    Why lifespan instead of @app.on_event?
        @app.on_event is deprecated in FastAPI >= 0.109.
        The lifespan context manager is the modern replacement.
    """
    global _start_time
    _start_time = time.time()

    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    print(f"   Debug mode: {settings.DEBUG}")
    print(f"   CORS origins: {settings.CORS_ORIGINS}")
    print(f"   Firebase: {'DEV MODE (in-memory)' if not settings.FIREBASE_PROJECT_ID else settings.FIREBASE_PROJECT_ID}")

    # ─── Pre-load ML models ───
    print(f"🧮 Loading embedding model...")
    pipeline_registry.initialize()
    print(f"✅ Models loaded ({time.time() - _start_time:.1f}s)")

    yield  # ← App runs here

    print(f"👋 {settings.APP_NAME} shutting down...")


# ─── Create FastAPI Application ───
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-Powered Repository Intelligence System. "
        "Upload a GitHub repo and ask questions about its codebase."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════
# Middleware (order matters: last added = first executed)
# ═══════════════════════════════════════════════════════════════


# ─── CORS Middleware ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─── Firebase Auth Middleware ───
app.middleware("http")(firebase_auth_middleware)


# ═══════════════════════════════════════════════════════════════
# Global Error Handlers
# ═══════════════════════════════════════════════════════════════


@app.exception_handler(RepoMindError)
async def repomind_error_handler(request: Request, exc: RepoMindError):
    """
    Handle all typed RepoMind exceptions.

    Each exception carries its own code, message, status_code, detail,
    and suggestion — we just convert it to the standard ErrorResponse.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
                "suggestion": exc.suggestion,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors (422).

    FastAPI raises these automatically when request body/params
    don't match the Pydantic model.
    """
    errors = exc.errors()
    detail = "; ".join(
        f"{e.get('loc', ['?'])[-1]}: {e.get('msg', 'invalid')}"
        for e in errors
    )

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "detail": detail,
                "suggestion": "Check the request body matches the expected schema",
            },
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """
    Catch-all for unhandled exceptions (500).

    Logs the full traceback for debugging, but returns a safe
    message to the client (no internal details leaked).
    """
    logger.exception(f"Unhandled error: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "detail": str(exc) if settings.DEBUG else None,
                "suggestion": "Try again. If the issue persists, contact support.",
            },
        },
    )


# ═══════════════════════════════════════════════════════════════
# Health Endpoint
# ═══════════════════════════════════════════════════════════════


@app.get(
    "/api/health",
    tags=["Health"],
    summary="Health Check",
    response_description="Server health status",
)
async def health_check():
    """
    Health check endpoint for uptime monitoring.

    No authentication required.
    Returns server status, version, model load state, and uptime.

    Reference: API Documentation → Section 5 (Health)
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app_name": settings.APP_NAME,
        "models_loaded": pipeline_registry.models_loaded,
        "active_repos": pipeline_registry.count,
        "uptime_seconds": round(time.time() - _start_time, 2),
    }


# ═══════════════════════════════════════════════════════════════
# Register API Routers
# ═══════════════════════════════════════════════════════════════

app.include_router(repos.router)
app.include_router(query.router)
app.include_router(analysis.router)
app.include_router(experiments.router)
