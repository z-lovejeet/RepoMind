"""
RepoMind — Vector Store Module

Store embedded vectors in a FAISS index for fast nearest-neighbor search.

How it works:
    1. build(): Create faiss.IndexFlatL2(384) and add embeddings
    2. search(): query → index.search(query, k) → distances + indices
    3. save(): faiss.write_index() + JSON chunks file
    4. load(): faiss.read_index() + JSON chunks file

Why IndexFlatL2?
    - Exact search (no approximation error)
    - For < 50K vectors, it's fast enough (~1ms per query)
    - Simple — no training step, no hyperparameters
    - Combined with L2-normalized vectors, it gives cosine similarity

Memory formula:
    chunks × dimensions × 4 bytes (float32)
    5,000 × 384 × 4 = 7.5 MB

Reference:
    - Module Design → Section 5 (core/indexing/vector_store.py)
    - RAG Workflow → Stage 7 (Indexing)
    - PRD → FR-5.4
"""

import json
import logging
from dataclasses import asdict
from pathlib import Path

import faiss
import numpy as np

from app.models.schemas import Chunk, SearchResult

logger = logging.getLogger(__name__)


class IndexNotReadyError(Exception):
    """Raised when search() is called before build() or load()."""
    pass


class IndexCorruptedError(Exception):
    """Raised when a loaded index is corrupted."""
    pass


class VectorStore:
    """
    FAISS-backed vector store for semantic search.

    Usage:
        store = VectorStore(dimension=384)
        store.build(embeddings, chunks)
        results = store.search(query_vector, top_k=5)

        store.save("index.faiss", "chunks.json")
        store.load("index.faiss", "chunks.json")
    """

    def __init__(self, dimension: int = 384):
        """
        Args:
            dimension: Vector dimension. Must match the embedding model.
                       384 for all-MiniLM-L6-v2.
        """
        self.dimension = dimension
        self.index: faiss.Index | None = None
        self.chunks: list[Chunk] = []

    def build(
        self,
        embeddings: np.ndarray,
        chunks: list[Chunk],
        index_type: str = "flat",
    ) -> None:
        """
        Build FAISS index from embeddings.

        Args:
            embeddings: NumPy array of shape (N, dimension), float32
            chunks: Parallel list of Chunk objects (index i → chunk i)
            index_type: "flat" (exact search). IVF/HNSW reserved for future.

        Raises:
            ValueError: If embeddings shape doesn't match dimension or chunks length
        """
        if len(embeddings) != len(chunks):
            raise ValueError(
                f"Embeddings count ({len(embeddings)}) != "
                f"chunks count ({len(chunks)})"
            )

        if len(embeddings) == 0:
            logger.warning("Building empty index (0 vectors)")
            self.index = faiss.IndexFlatL2(self.dimension)
            self.chunks = []
            return

        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension ({embeddings.shape[1]}) != "
                f"expected dimension ({self.dimension})"
            )

        # ─── Ensure float32 ───
        embeddings = embeddings.astype(np.float32)

        # ─── Build index ───
        if index_type == "flat":
            self.index = faiss.IndexFlatL2(self.dimension)
        else:
            # Future: IVF, HNSW
            logger.warning(
                f"Index type '{index_type}' not supported, using 'flat'"
            )
            self.index = faiss.IndexFlatL2(self.dimension)

        self.index.add(embeddings)
        self.chunks = list(chunks)

        logger.info(
            f"Built FAISS index: {self.index.ntotal} vectors, "
            f"{self.dimension} dimensions"
        )

    def search(
        self, query_vector: np.ndarray, top_k: int = 10
    ) -> list[SearchResult]:
        """
        Find top-K nearest chunks by L2 distance.

        Args:
            query_vector: Query embedding, shape (dimension,) or (1, dimension)
            top_k: Number of results to return

        Returns:
            List of SearchResult sorted by score (descending).
            Score is cosine similarity: 1 - L2²/2 (valid for normalized vectors).

        Raises:
            IndexNotReadyError: If index hasn't been built or loaded
        """
        if self.index is None:
            raise IndexNotReadyError(
                "Index not ready. Call build() or load() first."
            )

        if self.index.ntotal == 0:
            return []

        # ─── Reshape query ───
        # FAISS expects (1, dim), but callers may pass (dim,)
        query = np.asarray(query_vector, dtype=np.float32)
        if query.ndim == 1:
            query = query.reshape(1, -1)

        # ─── Clamp top_k ───
        top_k = min(top_k, self.index.ntotal)

        # ─── Search ───
        distances, indices = self.index.search(query, top_k)

        # ─── Build results ───
        results: list[SearchResult] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue  # No result at this position
            if idx >= len(self.chunks):
                continue  # Safety check

            # Convert L2 distance to cosine similarity
            # For L2-normalized vectors: cos_sim = 1 - L2²/2
            score = float(1.0 - dist / 2.0)
            score = max(0.0, min(1.0, score))  # Clamp to [0, 1]

            results.append(SearchResult(
                chunk=self.chunks[idx],
                score=score,
                source="dense",
            ))

        return results

    def save(self, index_path: str, chunks_path: str) -> None:
        """
        Save index and chunks to disk.

        Args:
            index_path: Path for FAISS binary index file
            chunks_path: Path for JSON chunks metadata
        """
        if self.index is None:
            raise IndexNotReadyError("No index to save.")

        # ─── Save FAISS index ───
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, index_path)

        # ─── Save chunks as JSON ───
        Path(chunks_path).parent.mkdir(parents=True, exist_ok=True)
        chunks_data = [asdict(chunk) for chunk in self.chunks]
        with open(chunks_path, "w") as f:
            json.dump(chunks_data, f)

        logger.info(
            f"Saved index ({self.index.ntotal} vectors) to {index_path}"
        )

    def load(self, index_path: str, chunks_path: str) -> None:
        """
        Load index and chunks from disk.

        Args:
            index_path: Path to FAISS binary index file
            chunks_path: Path to JSON chunks metadata

        Raises:
            IndexCorruptedError: If files are missing or corrupted
        """
        try:
            self.index = faiss.read_index(index_path)
        except Exception as e:
            raise IndexCorruptedError(
                f"Failed to load FAISS index from {index_path}: {e}"
            ) from e

        try:
            with open(chunks_path, "r") as f:
                chunks_data = json.load(f)
            self.chunks = [Chunk(**data) for data in chunks_data]
        except Exception as e:
            raise IndexCorruptedError(
                f"Failed to load chunks from {chunks_path}: {e}"
            ) from e

        logger.info(
            f"Loaded index ({self.index.ntotal} vectors) from {index_path}"
        )

    @property
    def size(self) -> int:
        """Number of vectors in the index."""
        if self.index is None:
            return 0
        return self.index.ntotal
