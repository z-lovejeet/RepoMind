"""
RepoMind — FastAPI Application Entry Point

This is the main application file. It:
1. Creates the FastAPI app with metadata
2. Configures CORS middleware for frontend communication
3. Sets up lifespan events (startup/shutdown)
4. Registers the health endpoint
5. Includes all API routers

Architecture Reference:
    - System Architecture: Section 5 (Backend Architecture)
    - API Documentation: Section 5 (Health Endpoint)
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import repos, query, analysis, experiments


# ─── Track server uptime ───
_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler for startup and shutdown events.

    Startup:
        - Record server start time
        - (Future phases: pre-load ML models, restore FAISS indexes)

    Shutdown:
        - (Future phases: cleanup temp directories, save indexes)

    Why lifespan instead of @app.on_event?
        @app.on_event is deprecated in FastAPI >= 0.109.
        The lifespan context manager is the modern replacement.
    """
    global _start_time
    _start_time = time.time()
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    print(f"   Debug mode: {settings.DEBUG}")
    print(f"   CORS origins: {settings.CORS_ORIGINS}")

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


# ─── CORS Middleware ───
# Required because frontend (localhost:5173) and backend (localhost:8000)
# are on different origins. Without CORS, the browser blocks all requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ─── Health Endpoint ───
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
    Returns server status, version, and uptime.

    Reference: API Documentation → Section 5 (Health)
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app_name": settings.APP_NAME,
        "uptime_seconds": round(time.time() - _start_time, 2),
    }


# ─── Register API Routers ───
app.include_router(repos.router)
app.include_router(query.router)
app.include_router(analysis.router)
app.include_router(experiments.router)

