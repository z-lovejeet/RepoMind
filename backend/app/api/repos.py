"""
RepoMind — Repository API Endpoints

Endpoints for repository management:
    POST   /api/repos/clone      → Clone a GitHub repo
    GET    /api/repos            → List user's repos
    GET    /api/repos/{repo_id}  → Get repo details
    DELETE /api/repos/{repo_id}  → Delete repo

The API layer is THIN — no business logic here.
All work is delegated to FirebaseService and Pipeline.

Reference: API Documentation → Section 6 (Repos)
"""

import logging
import os

from fastapi import APIRouter, Depends, Request, Query

from app.config import settings
from app.exceptions import (
    RepoAlreadyExistsError,
    RepoCloneFailedError,
    RepoLimitReachedError,
    RepoNotFoundError,
    RepoTooLargeError,
    IndexFailedError,
)
from app.middleware.firebase_auth import get_current_user_id
from app.models.schemas import CloneRepoRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repos", tags=["Repositories"])


def _get_firebase_service():
    """Get the shared FirebaseService instance from app state."""
    from app.main import firebase_service
    return firebase_service


def _get_pipeline_registry():
    """Get the shared PipelineRegistry instance from app state."""
    from app.main import pipeline_registry
    return pipeline_registry


# ═══════════════════════════════════════════════════════════════
# POST /api/repos/clone
# ═══════════════════════════════════════════════════════════════


@router.post("/clone", status_code=202)
async def clone_repo(
    body: CloneRepoRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Clone a public GitHub repository, ingest it, and build the search index.

    Returns 202 Accepted with repo metadata.
    Currently runs synchronously (async background tasks in Phase 14).
    """
    fb = _get_firebase_service()
    registry = _get_pipeline_registry()

    github_url = str(body.github_url).rstrip("/")

    # ─── Check repo limit ───
    count = fb.count_repos(user_id)
    if count >= settings.MAX_REPO_COUNT:
        raise RepoLimitReachedError(settings.MAX_REPO_COUNT)

    # ─── Check duplicate ───
    existing = fb.find_repo_by_url(user_id, github_url)
    if existing:
        raise RepoAlreadyExistsError(github_url)

    # ─── Extract repo name from URL ───
    repo_name = github_url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    # ─── Create repo document (status = indexing) ───
    repo_id = fb.create_repo(user_id, {
        "name": repo_name,
        "source": "github",
        "github_url": github_url,
    })

    # ─── Clone ───
    from app.core.ingestion.repo_loader import RepoLoader, RepoCloneError

    loader = RepoLoader()
    target_dir = os.path.join(settings.TEMP_DIR, repo_id)
    repo_dir = None

    try:
        repo_dir = loader.clone(github_url, target_dir=target_dir)
    except RepoCloneError as e:
        fb.update_repo_status(repo_id, "error", {"error_detail": str(e)})
        raise RepoCloneFailedError(str(e))

    # ─── Ingest ───
    try:
        pipeline = registry.create(repo_id)
        ingest_result = pipeline.ingest(repo_dir, repo_id)

        # ─── Check file count limit ───
        if ingest_result.file_count > settings.MAX_FILES_PER_REPO:
            loader.cleanup(repo_dir)
            registry.delete(repo_id)
            fb.update_repo_status(repo_id, "error")
            raise RepoTooLargeError(
                ingest_result.file_count, settings.MAX_FILES_PER_REPO
            )

        # ─── Update repo status to ready ───
        fb.update_repo_status(repo_id, "ready", {
            "file_count": ingest_result.file_count,
            "total_chunks": ingest_result.chunk_count,
            "languages": list(ingest_result.languages.keys()),
        })

        logger.info(
            f"Repo {repo_id} indexed: {ingest_result.file_count} files, "
            f"{ingest_result.chunk_count} chunks"
        )

    except (RepoTooLargeError, IndexFailedError):
        if repo_dir:
            loader.cleanup(repo_dir)
        raise
    except Exception as e:
        if repo_dir:
            loader.cleanup(repo_dir)
        fb.update_repo_status(repo_id, "error", {"error_detail": str(e)})
        registry.delete(repo_id)
        raise IndexFailedError(str(e))

    # ─── Return repo data ───
    repo = fb.get_repo(repo_id, user_id)
    return {"success": True, "data": repo}


# ═══════════════════════════════════════════════════════════════
# GET /api/repos
# ═══════════════════════════════════════════════════════════════


@router.get("")
async def list_repos(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """List all repositories for the authenticated user."""
    fb = _get_firebase_service()
    repos = fb.list_repos(user_id)
    return {"success": True, "data": repos, "count": len(repos)}


# ═══════════════════════════════════════════════════════════════
# GET /api/repos/{repo_id}
# ═══════════════════════════════════════════════════════════════


@router.get("/{repo_id}")
async def get_repo(
    repo_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Get detailed information about a single repository."""
    fb = _get_firebase_service()
    repo = fb.get_repo(repo_id, user_id)

    if repo is None:
        raise RepoNotFoundError(repo_id)

    return {"success": True, "data": repo}

# ═══════════════════════════════════════════════════════════════
# GET /api/repos/{repo_id}/files
# ═══════════════════════════════════════════════════════════════

@router.get("/{repo_id}/files")
async def get_repo_files(
    repo_id: str,
    request: Request,
    path: str = Query(default="/", description="Directory path relative to repo root"),
    user_id: str = Depends(get_current_user_id),
):
    """Get file tree for a repository path."""
    fb = _get_firebase_service()
    
    # ─── Verify repo exists and belongs to user ───
    repo = fb.get_repo(repo_id, user_id)
    if repo is None:
        raise RepoNotFoundError(repo_id)

    # ─── Check repo is ready ───
    if repo.get("status") != "ready":
        raise IndexNotReadyError(repo_id, repo.get("status", "unknown"))
        
    # ─── Security: sanitize path ───
    if ".." in path:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid path")
    
    repo_dir = os.path.join(settings.TEMP_DIR, repo_id)
    target_path = os.path.normpath(os.path.join(repo_dir, path.lstrip("/")))
    
    if not target_path.startswith(os.path.realpath(repo_dir)) and not target_path.startswith(repo_dir):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid path traversal")
        
    children = []
    
    lang_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
        '.jsx': 'javascript', '.md': 'markdown', '.json': 'json', '.yaml': 'yaml',
        '.yml': 'yaml', '.html': 'html', '.css': 'css', '.txt': 'text'
    }
    
    if os.path.exists(target_path) and os.path.isdir(target_path):
        for name in os.listdir(target_path):
            if name == ".git" or name == "__pycache__" or name == ".DS_Store":
                continue
            full_path = os.path.join(target_path, name)
            if os.path.isdir(full_path):
                try:
                    count = len([f for f in os.listdir(full_path) if f != ".git" and f != "__pycache__"])
                except Exception:
                    count = 0
                children.append({
                    "name": name,
                    "type": "directory",
                    "children_count": count
                })
            else:
                ext = os.path.splitext(name)[1].lower()
                lang = lang_map.get(ext, "unknown")
                size = 0
                try:
                    size = os.path.getsize(full_path)
                except Exception:
                    pass
                children.append({
                    "name": name,
                    "type": "file",
                    "size_bytes": size,
                    "language": lang
                })
                
    # Sort: directories first, then files, both alphabetically
    directories = sorted([c for c in children if c["type"] == "directory"], key=lambda x: x["name"].lower())
    files = sorted([c for c in children if c["type"] == "file"], key=lambda x: x["name"].lower())
    
    return {"success": True, "data": {"path": path, "children": directories + files}}


# ═══════════════════════════════════════════════════════════════
# DELETE /api/repos/{repo_id}
# ═══════════════════════════════════════════════════════════════


@router.delete("/{repo_id}")
async def delete_repo(
    repo_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a repository and all associated data."""
    fb = _get_firebase_service()
    registry = _get_pipeline_registry()

    deleted = fb.delete_repo(repo_id, user_id)
    if not deleted:
        raise RepoNotFoundError(repo_id)

    # ─── Clean up in-memory pipeline ───
    registry.delete(repo_id)

    return {"success": True, "data": {"id": repo_id, "deleted": True}}
