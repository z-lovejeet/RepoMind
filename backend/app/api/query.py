"""
RepoMind — Query API Endpoints

Endpoints for querying repositories:
    POST /api/repos/{repo_id}/query        → Full response with citations

Streaming (POST /api/repos/{repo_id}/query/stream) will be added in Phase 9.

Reference: API Documentation → Section 7 (Query)
"""

import logging

from fastapi import APIRouter, Depends, Request

from app.exceptions import (
    IndexNotReadyError,
    LLMApiError,
    RepoNotFoundError,
)
from app.middleware.firebase_auth import get_current_user_id
from app.models.schemas import QueryRequest, QueryConfig
from app.core.generation.llm_client import LLMError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repos", tags=["Query"])


def _get_firebase_service():
    """Get the shared FirebaseService instance from app state."""
    from app.main import firebase_service
    return firebase_service


def _get_pipeline_registry():
    """Get the shared PipelineRegistry instance from app state."""
    from app.main import pipeline_registry
    return pipeline_registry


# ═══════════════════════════════════════════════════════════════
# POST /api/repos/{repo_id}/query
# ═══════════════════════════════════════════════════════════════


@router.post("/{repo_id}/query")
async def query_repo(
    repo_id: str,
    body: QueryRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Ask a question about a repository and receive a complete response
    with source citations, timings, and config.

    Requires repo status to be "ready".
    """
    fb = _get_firebase_service()
    registry = _get_pipeline_registry()

    # ─── Verify repo exists and belongs to user ───
    repo = fb.get_repo(repo_id, user_id)
    if repo is None:
        raise RepoNotFoundError(repo_id)

    # ─── Check repo is ready ───
    if repo.get("status") != "ready":
        raise IndexNotReadyError(repo_id, repo.get("status", "unknown"))

    # ─── Get pipeline ───
    pipeline = registry.get(repo_id)
    if pipeline is None:
        raise IndexNotReadyError(repo_id, "pipeline_missing")

    # ─── Convert Pydantic config → dataclass ───
    config = QueryConfig()
    if body.config:
        config = QueryConfig(
            strategy=body.config.strategy,
            reranking=body.config.reranking,
            top_k_retrieval=body.config.top_k_retrieval,
            top_k_rerank=body.config.top_k_rerank,
            include_references=body.config.include_references,
            model=body.config.model,
            temperature=body.config.temperature,
        )

    # ─── Run query ───
    try:
        result = pipeline.query(body.query, config)
    except LLMError as e:
        raise LLMApiError(str(e))
    except RuntimeError as e:
        raise IndexNotReadyError(repo_id, str(e))

    # ─── Format citations ───
    citations = [
        {
            "index": c.index,
            "file_path": c.file_path,
            "lines": c.lines,
            "score": round(c.score, 3),
            "valid": c.valid,
        }
        for c in result.citations
    ]

    return {
        "success": True,
        "data": {
            "answer": result.answer,
            "citations": citations,
            "timings": {
                k: round(v, 1) for k, v in result.timings.items()
            },
            "config": result.config,
        },
    }
