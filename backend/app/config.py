"""
RepoMind Configuration Module

Loads all settings from environment variables using Pydantic Settings.
This is the single source of truth for configuration across the entire backend.

Usage:
    from app.config import settings
    print(settings.OPENAI_API_KEY)
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic Settings automatically reads from:
    1. Environment variables (highest priority)
    2. .env file (if present)

    Why Pydantic Settings instead of os.getenv()?
    - Type validation (catches wrong types at startup, not at runtime)
    - Default values with documentation
    - Immutable after loading (prevents accidental mutation)
    - Automatic .env file support
    """

    # ─── Application ───
    APP_NAME: str = "RepoMind"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ─── Server ───
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ─── CORS ───
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins. Add production frontend URL here.",
    )

    # ─── Firebase (Server-Side Admin SDK) ───
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CREDENTIALS_JSON: str = Field(
        default="",
        description="Firebase service account JSON string (for server-side Admin SDK)",
    )
    FIREBASE_STORAGE_BUCKET: str = ""

    # ─── OpenAI ───
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ─── Ollama (Local LLM Fallback) ───
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # ─── Embedding Model ───
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # ─── Reranker Model ───
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # ─── Pipeline Defaults ───
    DEFAULT_CHUNK_SIZE: int = 512
    DEFAULT_CHUNK_OVERLAP: int = 50
    DEFAULT_TOP_K_RETRIEVAL: int = 20
    DEFAULT_TOP_K_RERANK: int = 5
    DEFAULT_STRATEGY: str = "hybrid"
    DEFAULT_TEMPERATURE: float = 0.1

    # ─── LLM Providers ───
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # ─── Limits ───
    MAX_REPO_COUNT: int = 10
    MAX_FILE_SIZE_BYTES: int = 1_048_576  # 1MB
    MAX_FILES_PER_REPO: int = 500
    MAX_ZIP_SIZE_BYTES: int = 104_857_600  # 100MB
    MAX_QUERY_LENGTH: int = 1000

    # ─── Paths ───
    TEMP_DIR: str = "/tmp/repomind"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# Singleton instance — import this everywhere
settings = Settings()
