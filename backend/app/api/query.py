"""
RepoMind — Query API Endpoints (Stub)

Endpoints for querying repositories:
    POST /api/repos/{repo_id}/query        → Full response
    POST /api/repos/{repo_id}/query/stream  → SSE streaming

Will be implemented in Phase 6-7.

Reference: API Documentation → Section 7 (Query)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/repos", tags=["Query"])
