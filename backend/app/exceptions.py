"""
RepoMind — Custom Exception Hierarchy

Every exception maps to a specific HTTP status code and error code.
The global exception handler in main.py catches these and returns
the standardized ErrorResponse format.

Reference: API Documentation → Section 3 (Error Handling)
"""


class RepoMindError(Exception):
    """Base exception for all RepoMind errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        detail: str | None = None,
        suggestion: str | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        self.suggestion = suggestion
        super().__init__(message)


class RepoNotFoundError(RepoMindError):
    """Repo ID doesn't exist or belongs to another user."""

    def __init__(self, repo_id: str):
        super().__init__(
            code="REPO_NOT_FOUND",
            message="Repository not found",
            status_code=404,
            detail=f"No repository with ID '{repo_id}' found for this user",
            suggestion="Check the repo ID and try again",
        )


class RepoCloneFailedError(RepoMindError):
    """git clone failed (invalid URL, private repo, network error)."""

    def __init__(self, detail: str):
        super().__init__(
            code="REPO_CLONE_FAILED",
            message="Failed to clone repository",
            status_code=400,
            detail=detail,
            suggestion="Check that the URL is correct and the repository is public",
        )


class RepoAlreadyExistsError(RepoMindError):
    """User already has this URL indexed."""

    def __init__(self, github_url: str):
        super().__init__(
            code="REPO_ALREADY_EXISTS",
            message="Repository already indexed",
            status_code=409,
            detail=f"You already have '{github_url}' indexed",
            suggestion="Delete the existing repo first if you want to re-index",
        )


class RepoLimitReachedError(RepoMindError):
    """User has reached the maximum number of repos (10)."""

    def __init__(self, limit: int = 10):
        super().__init__(
            code="REPO_LIMIT_REACHED",
            message="Maximum repository limit reached",
            status_code=429,
            detail=f"You already have {limit} repositories indexed",
            suggestion="Delete an existing repo before adding a new one",
        )


class RepoTooLargeError(RepoMindError):
    """Repo exceeds file count limit."""

    def __init__(self, file_count: int, limit: int = 500):
        super().__init__(
            code="REPO_TOO_LARGE",
            message="Repository too large for processing",
            status_code=413,
            detail=f"Repository has {file_count} files (limit: {limit})",
            suggestion="Try a smaller repository or a specific subdirectory",
        )


class IndexNotReadyError(RepoMindError):
    """Query attempted before indexing completes."""

    def __init__(self, repo_id: str, status: str):
        super().__init__(
            code="INDEX_NOT_READY",
            message="Repository is still indexing",
            status_code=400,
            detail=f"Repo '{repo_id}' status is '{status}', not 'ready'",
            suggestion="Wait for indexing to complete before querying",
        )


class IndexFailedError(RepoMindError):
    """Embedding or FAISS build failed."""

    def __init__(self, detail: str):
        super().__init__(
            code="INDEX_FAILED",
            message="Indexing failed",
            status_code=500,
            detail=detail,
            suggestion="Try re-cloning the repository",
        )


class QueryTooLongError(RepoMindError):
    """Query exceeds max length."""

    def __init__(self, length: int, limit: int = 1000):
        super().__init__(
            code="QUERY_TOO_LONG",
            message="Query is too long",
            status_code=422,
            detail=f"Query has {length} characters (limit: {limit})",
            suggestion=f"Shorten your query to under {limit} characters",
        )


class LLMApiError(RepoMindError):
    """LLM provider returned an error."""

    def __init__(self, detail: str):
        super().__init__(
            code="LLM_API_ERROR",
            message="AI service temporarily unavailable",
            status_code=502,
            detail=detail,
            suggestion="Try again in a few seconds. If the issue persists, "
            "the AI provider may be experiencing downtime.",
        )


class AuthTokenMissingError(RepoMindError):
    """No Authorization header present."""

    def __init__(self):
        super().__init__(
            code="AUTH_TOKEN_MISSING",
            message="Authentication required",
            status_code=401,
            detail="No Authorization header present in the request",
            suggestion="Include 'Authorization: Bearer <token>' in your request",
        )


class AuthTokenInvalidError(RepoMindError):
    """JWT verification failed."""

    def __init__(self, detail: str = "Token is malformed, expired, or revoked"):
        super().__init__(
            code="AUTH_TOKEN_INVALID",
            message="Invalid or expired token",
            status_code=401,
            detail=detail,
            suggestion="Sign in again to get a fresh token",
        )
