"""
RepoMind — Firebase Authentication Middleware (Stub)

Verifies Firebase JWT on every request.
Extracts token from Authorization: Bearer <token> header.
Sets request.state.user_id = decoded token's uid.

Skips: GET /api/health, GET /docs, GET /openapi.json

Will be fully implemented in Phase 7.

Reference:
    - API Documentation → Section 2 (Authentication)
    - Module Design → Section 11 (Middleware)
"""

from fastapi import Request


async def firebase_auth_middleware(request: Request, call_next):
    """
    Firebase JWT verification middleware.

    Currently a pass-through stub.
    Phase 7 will add actual Firebase Admin SDK token verification.
    """
    # Stub: allow all requests through without auth
    request.state.user_id = "dev_user"
    response = await call_next(request)
    return response


def get_current_user_id(request: Request) -> str:
    """
    FastAPI dependency to extract user_id from request state.

    Usage in route handlers:
        user_id: str = Depends(get_current_user_id)
    """
    return getattr(request.state, "user_id", "dev_user")
