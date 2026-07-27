"""
RepoMind — Analysis API Endpoints (Stub)

Endpoints for code analysis:
    GET /api/repos/{repo_id}/dependencies       → Dependency graph
    GET /api/repos/{repo_id}/references/{symbol} → Find references

Will be implemented in Phase 12.

Reference: API Documentation → Section 8 (Analysis)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/repos", tags=["Analysis"])
