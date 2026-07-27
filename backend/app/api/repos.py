"""
RepoMind — Repository API Endpoints (Stub)

Endpoints for repository management:
    POST /api/repos/clone      → Clone a GitHub repo
    POST /api/repos/upload     → Upload a zip file
    GET  /api/repos            → List user's repos
    GET  /api/repos/{repo_id}  → Get repo details
    DELETE /api/repos/{repo_id} → Delete repo

Will be implemented in Phase 7 (API Layer & Auth).

Reference: API Documentation → Section 6 (Repos)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/repos", tags=["Repositories"])


@router.get("")
async def list_repos():
    """List all repositories for the authenticated user. (Stub)"""
    return {"success": True, "data": [], "count": 0}
