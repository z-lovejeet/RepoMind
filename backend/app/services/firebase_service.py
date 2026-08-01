"""
RepoMind — Firebase Service

Wrapper for all Firebase Admin SDK operations.
The ONLY module that imports firebase_admin.
Isolates Firebase from the rest of the codebase.

Two modes:
    1. Dev mode (no FIREBASE_PROJECT_ID): In-memory dict storage
    2. Production mode: Firestore database

Why isolate Firebase?
    If we ever migrate to Supabase, PostgreSQL, or AWS,
    we change ONE file. No core module is affected.
    This is the Dependency Inversion Principle.

Reference: Module Design → Section 13 (Services)
"""

import logging
import uuid
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)


class FirebaseService:
    """
    Firebase Admin SDK wrapper.

    Handles:
    - Firestore: CRUD for repos
    - Auth: Token verification (via middleware)

    Automatically uses in-memory storage when Firebase is not configured.
    """

    def __init__(self):
        """Initialize Firebase Admin SDK or fallback to in-memory."""
        self._firestore_client = None
        self._dev_mode = not settings.FIREBASE_PROJECT_ID

        if self._dev_mode:
            logger.info("FirebaseService: DEV MODE (in-memory storage)")
            self._memory_store: dict[str, dict] = {}
        else:
            self._init_firebase()

    def _init_firebase(self):
        """Initialize Firebase Admin SDK with service account credentials."""
        import json
        import firebase_admin
        from firebase_admin import credentials, firestore

        try:
            if not firebase_admin._apps:
                if settings.FIREBASE_CREDENTIALS_JSON:
                    cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
                    cred = credentials.Certificate(cred_dict)
                else:
                    cred = credentials.ApplicationDefault()

                firebase_admin.initialize_app(cred, {
                    "projectId": settings.FIREBASE_PROJECT_ID,
                    "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
                })

            self._firestore_client = firestore.client()
            logger.info(
                f"FirebaseService: Connected to project "
                f"'{settings.FIREBASE_PROJECT_ID}'"
            )

        except Exception as e:
            logger.error(f"Firebase init failed: {e}. Falling back to dev mode.")
            self._dev_mode = True
            self._memory_store = {}

    # ═══════════════════════════════════════════════════════════════
    # Repo CRUD
    # ═══════════════════════════════════════════════════════════════

    def create_repo(self, user_id: str, repo_data: dict) -> str:
        """
        Create a repo document. Returns repo_id.

        Args:
            user_id: Owner's user ID
            repo_data: Dict with name, github_url, source, etc.

        Returns:
            Generated repo_id (rp_ prefixed)
        """
        repo_id = f"rp_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "id": repo_id,
            "user_id": user_id,
            "name": repo_data.get("name", "unknown"),
            "source": repo_data.get("source", "github"),
            "github_url": repo_data.get("github_url"),
            "status": "indexing",
            "file_count": None,
            "total_chunks": None,
            "languages": [],
            "indexed_at": None,
            "created_at": now,
        }

        if self._dev_mode:
            self._memory_store[repo_id] = doc
        else:
            self._firestore_client.collection("repos").document(repo_id).set(doc)

        logger.info(f"Created repo {repo_id} for user {user_id}")
        return repo_id

    def get_repo(self, repo_id: str, user_id: str) -> dict | None:
        """
        Get repo by ID, enforcing ownership.

        Returns None if repo doesn't exist or belongs to another user.
        """
        if self._dev_mode:
            doc = self._memory_store.get(repo_id)
            if doc and doc.get("user_id") == user_id:
                return doc
            return None
        else:
            ref = self._firestore_client.collection("repos").document(repo_id)
            doc = ref.get()
            if doc.exists:
                data = doc.to_dict()
                if data.get("user_id") == user_id:
                    return data
            return None

    def list_repos(self, user_id: str) -> list[dict]:
        """List all repos for a user, sorted by created_at descending."""
        if self._dev_mode:
            repos = [
                doc for doc in self._memory_store.values()
                if doc.get("user_id") == user_id
            ]
            repos.sort(key=lambda r: r.get("created_at", ""), reverse=True)
            return repos
        else:
            query = (
                self._firestore_client.collection("repos")
                .where("user_id", "==", user_id)
                .order_by("created_at", direction="DESCENDING")
            )
            return [doc.to_dict() for doc in query.stream()]

    def update_repo_status(
        self, repo_id: str, status: str, metadata: dict | None = None
    ) -> None:
        """
        Update repo status and optional metadata fields.

        Args:
            repo_id: Repo to update
            status: New status ("indexing", "ready", "error")
            metadata: Optional dict with file_count, total_chunks, languages, etc.
        """
        update = {"status": status}
        if metadata:
            update.update(metadata)
        if status == "ready":
            update["indexed_at"] = datetime.now(timezone.utc).isoformat()

        if self._dev_mode:
            if repo_id in self._memory_store:
                self._memory_store[repo_id].update(update)
        else:
            self._firestore_client.collection("repos").document(repo_id).update(update)

        logger.info(f"Updated repo {repo_id} status → {status}")

    def delete_repo(self, repo_id: str, user_id: str) -> bool:
        """
        Delete repo document. Returns True if deleted, False if not found.

        Enforces ownership — only the owner can delete.
        """
        if self._dev_mode:
            doc = self._memory_store.get(repo_id)
            if doc and doc.get("user_id") == user_id:
                del self._memory_store[repo_id]
                logger.info(f"Deleted repo {repo_id}")
                return True
            return False
        else:
            ref = self._firestore_client.collection("repos").document(repo_id)
            doc = ref.get()
            if doc.exists and doc.to_dict().get("user_id") == user_id:
                ref.delete()
                logger.info(f"Deleted repo {repo_id}")
                return True
            return False

    def count_repos(self, user_id: str) -> int:
        """Count repos for limit checking."""
        if self._dev_mode:
            return sum(
                1 for doc in self._memory_store.values()
                if doc.get("user_id") == user_id
            )
        else:
            query = (
                self._firestore_client.collection("repos")
                .where("user_id", "==", user_id)
            )
            return len(list(query.stream()))

    def find_repo_by_url(self, user_id: str, github_url: str) -> dict | None:
        """Check if user already has this URL indexed."""
        if self._dev_mode:
            for doc in self._memory_store.values():
                if (
                    doc.get("user_id") == user_id
                    and doc.get("github_url") == github_url
                ):
                    return doc
            return None
        else:
            query = (
                self._firestore_client.collection("repos")
                .where("user_id", "==", user_id)
                .where("github_url", "==", github_url)
                .limit(1)
            )
            docs = list(query.stream())
            return docs[0].to_dict() if docs else None
