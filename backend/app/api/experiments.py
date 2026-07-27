"""
RepoMind — Experiments API Endpoints (Stub)

Endpoints for A/B experiment comparison:
    POST /api/repos/{repo_id}/experiments → Run experiment
    GET  /api/repos/{repo_id}/experiments → List experiments

Will be implemented in Phase 13.

Reference: API Documentation → Section 9 (Experiments)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/repos", tags=["Experiments"])
