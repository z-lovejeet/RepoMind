"""
RepoMind — BM25 Index Module

Keyword-based search using BM25 (Best Match 25) scoring.

How BM25 works:
    Score(query, document) = Σ IDF(term) × (TF × (k1 + 1)) / (TF + k1 × (1 - b + b × |D|/avgdl))

    Where:
    - TF = term frequency in document
    - IDF = inverse document frequency (rarer terms score higher)
    - k1 = 1.5 (controls term frequency saturation)
    - b = 0.75 (controls document length normalization)
    - |D| = document length, avgdl = average document length

Why BM25 alongside FAISS?
    Dense search (FAISS) captures semantic similarity:
        "authentication" ≈ "login" ≈ "verify credentials"
    But it may MISS exact keyword matches:
        "find process_order function" → BM25 finds "process_order" directly

    Neither alone is perfect. Hybrid retrieval (Phase 5) combines both.

Reference:
    - Module Design → Section 5 (core/indexing/bm25_index.py)
    - RAG Workflow → Stage 7 (Indexing) → BM25 Indexing
"""

import logging
import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.models.schemas import Chunk, SearchResult

logger = logging.getLogger(__name__)


class BM25Index:
    """
    BM25-based keyword search index.

    Usage:
        index = BM25Index()
        index.build(chunks)
        results = index.search("process_order function", top_k=5)

        index.save("bm25.pkl")
        index.load("bm25.pkl")
    """

    def __init__(self):
        self.index: BM25Okapi | None = None
        self.chunks: list[Chunk] = []

    def build(self, chunks: list[Chunk]) -> None:
        """
        Build BM25 index from chunk texts.

        Tokenizes each chunk's text and builds the BM25Okapi index.

        Args:
            chunks: List of Chunk objects to index
        """
        if not chunks:
            logger.warning("Building empty BM25 index (0 chunks)")
            self.chunks = []
            self.index = None
            return

        self.chunks = list(chunks)

        # Tokenize all chunk texts
        tokenized = [self._tokenize(chunk.text) for chunk in self.chunks]

        # Build BM25 index
        self.index = BM25Okapi(tokenized)

        logger.info(f"Built BM25 index: {len(self.chunks)} chunks")

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """
        Score all chunks by BM25 and return top-K.

        Args:
            query: Natural language query string
            top_k: Number of results to return

        Returns:
            List of SearchResult sorted by BM25 score (descending).
            Only results with score > 0 are returned.

        Raises:
            IndexNotReadyError: If build() hasn't been called
        """
        if self.index is None or not self.chunks:
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Get BM25 scores for all chunks
        scores = self.index.get_scores(query_tokens)

        # Get top-K indices (sorted by score, descending)
        top_k = min(top_k, len(self.chunks))
        top_indices = scores.argsort()[-top_k:][::-1]

        # Build results (filter score > 0)
        results: list[SearchResult] = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue  # BM25 can return 0 or negative for no-match

            results.append(SearchResult(
                chunk=self.chunks[idx],
                score=score,
                source="bm25",
            ))

        return results

    def save(self, path: str) -> None:
        """
        Save BM25 index and chunks to disk via pickle.

        Args:
            path: File path for the pickled index

        Note:
            Pickle is used because BM25Okapi objects are not JSON-serializable.
            Only load from trusted paths (our own /tmp/repomind/ directory).
        """
        if self.index is None:
            logger.warning("No BM25 index to save")
            return

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        data = {
            "index": self.index,
            "chunks": self.chunks,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

        logger.info(f"Saved BM25 index ({len(self.chunks)} chunks) to {path}")

    def load(self, path: str) -> None:
        """
        Load BM25 index and chunks from disk.

        Args:
            path: File path to the pickled index

        Raises:
            FileNotFoundError: If path doesn't exist
        """
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.index = data["index"]
        self.chunks = data["chunks"]

        logger.info(
            f"Loaded BM25 index ({len(self.chunks)} chunks) from {path}"
        )

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text for BM25.

        Simple tokenization: split on non-alphanumeric characters,
        convert to lowercase.

        Args:
            text: Raw text string

        Returns:
            List of lowercase tokens
        """
        return re.findall(r"\w+", text.lower())
