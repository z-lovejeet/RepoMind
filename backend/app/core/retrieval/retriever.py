"""
RepoMind — Retriever Module

Find the most relevant chunks for a given query using selectable strategies.

Strategies:
    - "dense":  Embed query → FAISS nearest-neighbor search (semantic)
    - "bm25":   Tokenize query → BM25 keyword scoring (exact match)
    - "hybrid": Dense + BM25 combined via Reciprocal Rank Fusion (best of both)

How Hybrid Retrieval works:
    1. Run dense retrieval → get top-K ranked results
    2. Run BM25 retrieval  → get top-K ranked results
    3. Merge via RRF: score(chunk) = Σ 1/(k + rank_i + 1) for each list
    4. Chunks in BOTH lists get boosted (their scores sum)
    5. Sort by combined RRF score → return top-K

Why k=60?
    The original RRF paper (Cormack et al., 2009) tested values from 1-1000
    and found k=60 gives the best results across diverse datasets.

Reference:
    - Module Design → Section 6 (core/retrieval/retriever.py)
    - RAG Workflow → Stage 8 (Retrieval)
    - Development Roadmap → Phase 5
"""

import logging
import time

from app.core.embedding.embedder import Embedder
from app.core.indexing.vector_store import VectorStore
from app.core.indexing.bm25_index import BM25Index
from app.models.schemas import SearchResult

logger = logging.getLogger(__name__)


class RetrievalError(Exception):
    """Raised when retrieval fails."""
    pass


class Retriever:
    """
    Retrieve relevant code chunks using configurable strategies.

    Usage:
        retriever = Retriever(vector_store, bm25_index, embedder)
        results = retriever.retrieve("How does auth work?", strategy="hybrid")
    """

    # Supported strategies
    STRATEGIES = {"dense", "bm25", "hybrid"}

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        embedder: Embedder,
    ):
        """
        Args:
            vector_store: FAISS-backed vector store (must be built/loaded)
            bm25_index: BM25 keyword index (must be built/loaded)
            embedder: Sentence Transformer embedder for query encoding
        """
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.embedder = embedder

    def retrieve(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 20,
    ) -> list[SearchResult]:
        """
        Retrieve relevant chunks using the specified strategy.

        Args:
            query: Natural language question
            strategy: "dense" | "bm25" | "hybrid"
            top_k: Number of results to return

        Returns:
            List of SearchResult sorted by relevance (descending)

        Raises:
            ValueError: If strategy is not supported
            RetrievalError: If retrieval fails
        """
        if not query or not query.strip():
            return []

        if strategy not in self.STRATEGIES:
            if strategy == "hyde":
                raise ValueError(
                    "HyDE requires LLM client — available in Phase 6"
                )
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Supported: {sorted(self.STRATEGIES)}"
            )

        start = time.time()

        try:
            if strategy == "dense":
                results = self._dense_retrieve(query, top_k)
            elif strategy == "bm25":
                results = self._bm25_retrieve(query, top_k)
            elif strategy == "hybrid":
                results = self._hybrid_retrieve(query, top_k)
            else:
                results = []
        except Exception as e:
            raise RetrievalError(
                f"Retrieval failed (strategy={strategy}): {e}"
            ) from e

        elapsed_ms = (time.time() - start) * 1000
        logger.info(
            f"Retrieved {len(results)} chunks "
            f"(strategy={strategy}, top_k={top_k}, {elapsed_ms:.1f}ms)"
        )

        return results

    def _dense_retrieve(
        self, query: str, top_k: int
    ) -> list[SearchResult]:
        """
        Embed query → FAISS nearest-neighbor search.

        How it works:
            1. Embed the query text into a 384-dim vector
            2. Search FAISS index for top-K nearest vectors
            3. Return SearchResult objects with source="dense"
        """
        query_vector = self.embedder.embed_query(query)
        results = self.vector_store.search(query_vector, top_k=top_k)
        return results

    def _bm25_retrieve(
        self, query: str, top_k: int
    ) -> list[SearchResult]:
        """
        Tokenize query → BM25 keyword scoring.

        How it works:
            1. Tokenize query (split on non-alphanumeric, lowercase)
            2. Score all chunks by term frequency (BM25Okapi)
            3. Return top-K results with score > 0
        """
        results = self.bm25_index.search(query, top_k=top_k)
        return results

    def _hybrid_retrieve(
        self, query: str, top_k: int
    ) -> list[SearchResult]:
        """
        Dense + BM25 combined via Reciprocal Rank Fusion.

        How it works:
            1. Run both dense and BM25 with top_k each
            2. Merge via RRF: chunks in BOTH lists get boosted
            3. Return top_k results sorted by combined RRF score
        """
        dense_results = self._dense_retrieve(query, top_k)
        bm25_results = self._bm25_retrieve(query, top_k)
        merged = self._rrf_merge(dense_results, bm25_results, k=60)
        return merged[:top_k]

    def _rrf_merge(
        self,
        results_a: list[SearchResult],
        results_b: list[SearchResult],
        k: int = 60,
    ) -> list[SearchResult]:
        """
        Reciprocal Rank Fusion: combine two ranked lists.

        For each chunk, the RRF score is:
            score = Σ 1/(k + rank_i + 1)

        where rank_i is the chunk's position in each list (0-indexed).
        Chunks appearing in both lists get scores from both, boosting
        them above chunks appearing in only one list.

        Args:
            results_a: First ranked list (e.g., dense results)
            results_b: Second ranked list (e.g., BM25 results)
            k: RRF constant (default 60 from the original paper)

        Returns:
            Merged list sorted by combined RRF score (descending)
        """
        # ─── Score accumulation ───
        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, SearchResult] = {}

        for rank, result in enumerate(results_a):
            chunk_id = result.chunk.id
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (k + rank + 1)
            chunk_map[chunk_id] = result

        for rank, result in enumerate(results_b):
            chunk_id = result.chunk.id
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (k + rank + 1)
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = result

        # ─── Sort by combined score ───
        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda cid: rrf_scores[cid],
            reverse=True,
        )

        # ─── Build results with hybrid source ───
        return [
            SearchResult(
                chunk=chunk_map[cid].chunk,
                score=rrf_scores[cid],
                source="hybrid",
            )
            for cid in sorted_ids
        ]
