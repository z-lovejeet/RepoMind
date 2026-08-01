"""
RepoMind — Firebase Authentication Middleware

Verifies Firebase JWT on every request.
Extracts token from Authorization: Bearer <token> header.
Sets request.state.user_id = decoded token's uid.

Dev Mode (FIREBASE_PROJECT_ID is empty):
    Allows all requests through with user_id = "dev_user".
    This lets you test the full API without Firebase configured.

Production Mode (FIREBASE_PROJECT_ID is set):
    Verifies JWT via Firebase Admin SDK.
    Returns 401 for missing or invalid tokens.

Skips: GET /api/health, GET /docs, GET /openapi.json, GET /redoc

Reference:
    - API Documentation → Section 2 (Authentication)
    - Module Design → Section 11 (Middleware)
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

# ─── Paths that skip auth ───
SKIP_PATHS = {
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}


def _is_dev_mode() -> bool:
    """Check if we're running without Firebase (dev mode)."""
    return not settings.FIREBASE_PROJECT_ID


async def firebase_auth_middleware(request: Request, call_next):
    """
    Firebase JWT verification middleware.

    Flow:
        1. Check if path is in SKIP_PATHS → pass through
        2. If dev mode → set user_id = "dev_user"
        3. If production → extract Bearer token → verify via Firebase Admin SDK
        4. On failure → return 401 ErrorResponse
    """
    # ─── Skip auth for health/docs ───
    if request.url.path in SKIP_PATHS:
        response = await call_next(request)
        return response

    # ─── Dev mode: allow all requests ───
    if _is_dev_mode():
        request.state.user_id = "dev_user"
        response = await call_next(request)
        return response

    # ─── Production mode: verify Firebase JWT ───
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "AUTH_TOKEN_MISSING",
                    "message": "Authentication required",
                    "detail": "No Authorization header present",
                    "suggestion": "Include 'Authorization: Bearer <token>' in your request",
                },
            },
        )

    token = auth_header.split("Bearer ", 1)[1]

    try:
        import firebase_admin.auth as firebase_auth

        decoded = firebase_auth.verify_id_token(token)
        request.state.user_id = decoded["uid"]
        logger.debug(f"Authenticated user: {decoded['uid']}")

    except Exception as e:
        logger.warning(f"Auth failed: {e}")
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "AUTH_TOKEN_INVALID",
                    "message": "Invalid or expired token",
                    "detail": str(e),
                    "suggestion": "Sign in again to get a fresh token",
                },
            },
        )

    response = await call_next(request)
    return response


def get_current_user_id(request: Request) -> str:
    """
    FastAPI dependency to extract user_id from request state.

    Usage in route handlers:
        user_id: str = Depends(get_current_user_id)
    """
    return getattr(request.state, "user_id", "dev_user")
