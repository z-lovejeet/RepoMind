"""
RepoMind — Embedder Module

Convert text strings into dense numerical vectors using a pre-trained
Sentence Transformer model.

How it works:
    1. Load model: SentenceTransformer("all-MiniLM-L6-v2")
    2. Encode texts: model.encode(texts, normalize_embeddings=True)
    3. Result: np.ndarray of shape (N, 384), L2-normalized, float32

Why all-MiniLM-L6-v2?
    - 384 dimensions (compact — less memory, fast search)
    - 6 transformer layers (fast inference on CPU)
    - Trained on 1B+ sentence pairs (good semantic understanding)
    - ~80MB download, ~200MB RAM at runtime

Why L2 normalization?
    When all vectors have unit length (||v|| = 1):
        L2² = 2(1 - cosine_similarity)
    This means FAISS's IndexFlatL2 gives us cosine similarity
    ranking FOR FREE — no separate cosine index needed.

Reference:
    - Module Design → Section 4 (core/embedding/embedder.py)
    - RAG Workflow → Stage 6 (Embedding)
    - PRD → FR-5.1, FR-5.3
"""

import logging

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Raised when embedding fails (OOM, model error, etc.)."""
    pass


class Embedder:
    """
    Embed text into dense vectors using Sentence Transformers.

    The model is loaded once at initialization (~2 seconds, ~200MB RAM)
    and reused for all subsequent embed() calls.

    Usage:
        embedder = Embedder()
        vectors = embedder.embed(["How does auth work?", "def login():"])
        print(vectors.shape)  # (2, 384)

        query_vec = embedder.embed_query("How does auth work?")
        print(query_vec.shape)  # (384,)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Load the Sentence Transformer model.

        Args:
            model_name: HuggingFace model name or local path.
                        Default: "all-MiniLM-L6-v2" (384 dims, fast)

        Raises:
            EmbeddingError: If model fails to load
        """
        try:
            logger.info(f"Loading embedding model: {model_name}")
            self.model = SentenceTransformer(model_name)
            self._dimension = self.model.get_sentence_embedding_dimension() if hasattr(self.model, 'get_sentence_embedding_dimension') else self.model.get_embedding_dimension()
            logger.info(
                f"Model loaded: {model_name} "
                f"(dimension={self._dimension})"
            )
        except Exception as e:
            raise EmbeddingError(
                f"Failed to load embedding model '{model_name}': {e}"
            ) from e

    @property
    def dimension(self) -> int:
        """
        Return the embedding dimension.

        Returns:
            384 for all-MiniLM-L6-v2
        """
        return self._dimension

    def embed(
        self, texts: list[str], batch_size: int = 32
    ) -> np.ndarray:
        """
        Embed a list of texts into a NumPy array of vectors.

        Args:
            texts: List of strings to embed
            batch_size: Number of texts to process in one forward pass.
                        Higher = faster but more memory. Default 32.

        Returns:
            np.ndarray of shape (len(texts), self.dimension)
            L2-normalized, dtype=float32

        Raises:
            EmbeddingError: If encoding fails (usually OOM)
        """
        # ─── Handle empty input ───
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        # ─── Filter empty strings ───
        # Empty strings produce meaningless vectors. Filter them out,
        # but keep track of their positions to return correct shape.
        valid_indices: list[int] = []
        valid_texts: list[str] = []

        for i, text in enumerate(texts):
            if text and text.strip():
                valid_indices.append(i)
                valid_texts.append(text)
            else:
                logger.warning(f"Empty text at index {i}, skipping")

        if not valid_texts:
            return np.zeros((len(texts), self.dimension), dtype=np.float32)

        # ─── Encode ───
        try:
            embeddings = self.model.encode(
                valid_texts,
                batch_size=batch_size,
                show_progress_bar=len(valid_texts) > 100,
                normalize_embeddings=True,  # L2 normalization
            )
        except Exception as e:
            raise EmbeddingError(
                f"Encoding failed for {len(valid_texts)} texts: {e}"
            ) from e

        # ─── Ensure float32 ───
        # FAISS requires float32. model.encode() may return float64.
        embeddings = np.asarray(embeddings, dtype=np.float32)

        # ─── Reconstruct full array (with zeros for filtered texts) ───
        if len(valid_texts) < len(texts):
            full = np.zeros((len(texts), self.dimension), dtype=np.float32)
            for new_idx, orig_idx in enumerate(valid_indices):
                full[orig_idx] = embeddings[new_idx]
            return full

        return embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single query string.

        Convenience method for embedding a single search query.
        Returns a 1D vector (not a 2D array).

        Args:
            query: Natural language query string

        Returns:
            np.ndarray of shape (self.dimension,) — 1D vector
        """
        if not query or not query.strip():
            return np.zeros(self.dimension, dtype=np.float32)

        result = self.embed([query])
        return result[0]  # (1, 384) → (384,)
