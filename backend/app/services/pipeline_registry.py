"""
RepoMind — Pipeline Registry

Manages per-repo Pipeline instances in memory.

Each repo has its own FAISS index, BM25 index, and chunked data.
The registry maps repo_id → Pipeline and manages their lifecycle.

The embedding model is loaded ONCE and shared across all pipelines
(it's stateless and thread-safe).

Reference: Module Design → Section 9 (Pipeline Orchestrator)
"""

import logging

from app.core.embedding.embedder import Embedder
from app.core.generation.llm_client import LLMClient, LLMError
from app.core.pipeline import Pipeline

logger = logging.getLogger(__name__)


class PipelineRegistry:
    """
    Manage per-repo Pipeline instances.

    Usage:
        registry = PipelineRegistry()
        registry.initialize()  # Load shared models (call once at startup)

        pipeline = registry.create("rp_abc123")
        pipeline.ingest(repo_dir)

        pipeline = registry.get("rp_abc123")
        result = pipeline.query("How does auth work?")
    """

    def __init__(self):
        self._pipelines: dict[str, Pipeline] = {}
        self._embedder: Embedder | None = None
        self._llm_client: LLMClient | None = None
        self._initialized = False

    def initialize(self) -> None:
        """
        Pre-load shared models. Call once during app startup.

        Loads:
        - Embedding model (sentence-transformers, ~90MB)
        - LLM client (Gemini primary + Groq fallback)
        """
        if self._initialized:
            return

        logger.info("Loading embedding model...")
        self._embedder = Embedder()
        logger.info(
            f"Embedding model loaded: dim={self._embedder.dimension}"
        )

        try:
            self._llm_client = LLMClient()
            logger.info(
                f"LLM client initialized: "
                f"{self._llm_client.provider}/{self._llm_client.model}"
            )
        except LLMError as e:
            logger.warning(f"LLM client init failed: {e}. Queries will fail.")
            self._llm_client = None

        self._initialized = True

    @property
    def models_loaded(self) -> bool:
        """Check if shared models are loaded."""
        return self._initialized and self._embedder is not None

    def create(self, repo_id: str) -> Pipeline:
        """
        Create a new Pipeline for a repo.

        Args:
            repo_id: Unique repo identifier

        Returns:
            Fresh Pipeline instance with shared embedder + LLM

        Raises:
            RuntimeError: If initialize() hasn't been called
        """
        if not self._initialized:
            raise RuntimeError("PipelineRegistry not initialized. Call initialize() first.")

        pipeline = Pipeline(
            embedder=self._embedder,
            llm_client=self._llm_client,
        )
        self._pipelines[repo_id] = pipeline
        logger.info(f"Created pipeline for repo {repo_id}")
        return pipeline

    def get(self, repo_id: str) -> Pipeline | None:
        """Get existing Pipeline for a repo, or None."""
        return self._pipelines.get(repo_id)

    def has(self, repo_id: str) -> bool:
        """Check if a Pipeline exists for a repo."""
        return repo_id in self._pipelines

    def delete(self, repo_id: str) -> None:
        """Remove Pipeline for a repo (frees memory)."""
        if repo_id in self._pipelines:
            del self._pipelines[repo_id]
            logger.info(f"Deleted pipeline for repo {repo_id}")

    @property
    def count(self) -> int:
        """Number of active pipelines."""
        return len(self._pipelines)
