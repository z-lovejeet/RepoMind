"""
RepoMind — Firebase Service (Stub)

Wrapper for all Firebase Admin SDK operations.
The ONLY module that imports firebase_admin.
Isolates Firebase from the rest of the codebase.

Why isolate?
    If we ever migrate to Supabase, PostgreSQL, or AWS,
    we change ONE file. No core module is affected.
    This is the Dependency Inversion Principle.

Will be fully implemented in Phase 7.

Reference: Module Design → Section 13 (Services)
"""


class FirebaseService:
    """
    Firebase Admin SDK wrapper.

    Handles:
    - Firestore: CRUD for repos, chats, experiments
    - Storage: Upload/download files (zips, indexes)
    - Auth: Token verification

    Currently a stub with placeholder methods.
    """

    def __init__(self):
        """Initialize Firebase Admin SDK. (Stub)"""
        self._initialized = False

    async def create_repo(self, user_id: str, repo_data: dict) -> str:
        """Create a repo document. Returns repo_id. (Stub)"""
        raise NotImplementedError("Firebase not configured yet — Phase 7")

    async def get_repo(self, repo_id: str) -> dict | None:
        """Get repo by ID. (Stub)"""
        raise NotImplementedError("Firebase not configured yet — Phase 7")

    async def list_repos(self, user_id: str) -> list[dict]:
        """List all repos for a user. (Stub)"""
        raise NotImplementedError("Firebase not configured yet — Phase 7")

    async def update_repo_status(
        self, repo_id: str, status: str, metadata: dict | None = None
    ) -> None:
        """Update repo status. (Stub)"""
        raise NotImplementedError("Firebase not configured yet — Phase 7")

    async def delete_repo(self, repo_id: str) -> None:
        """Delete repo document and associated data. (Stub)"""
        raise NotImplementedError("Firebase not configured yet — Phase 7")

    def verify_token(self, id_token: str) -> dict:
        """Verify a Firebase JWT token. (Stub)"""
        raise NotImplementedError("Firebase not configured yet — Phase 7")
