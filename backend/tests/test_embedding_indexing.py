"""
RepoMind — Unit Tests for Embedding & Indexing Modules

Tests for:
    - Embedder: shape, normalization, semantic similarity, empty input
    - VectorStore: build, search, self-search, save/load, empty index
    - BM25Index: exact match, no match, save/load

Reference: Development Roadmap → Phase 4 → Testing
"""

import os
import tempfile
import unittest

import numpy as np

from app.core.embedding.embedder import Embedder, EmbeddingError
from app.core.indexing.vector_store import (
    VectorStore,
    IndexNotReadyError,
)
from app.core.indexing.bm25_index import BM25Index
from app.models.schemas import Chunk


def _make_chunk(text: str, chunk_id: str = "test", file_path: str = "test.py") -> Chunk:
    """Helper to create test Chunk objects."""
    return Chunk(
        id=chunk_id,
        text=text,
        file_path=file_path,
        start_line=1,
        end_line=10,
        chunk_type="code",
        language="python",
        parent_symbol=None,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# EMBEDDER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmbedder(unittest.TestCase):
    """Tests for Embedder Sentence Transformer wrapper."""

    @classmethod
    def setUpClass(cls):
        """Load model once for all tests (expensive operation)."""
        cls.embedder = Embedder()

    def test_embed_shape(self):
        """5 texts → shape (5, 384)."""
        texts = [
            "Hello world",
            "How does authentication work?",
            "def login(username, password):",
            "SELECT * FROM users",
            "The quick brown fox",
        ]
        result = self.embedder.embed(texts)
        self.assertEqual(result.shape, (5, 384))
        self.assertEqual(result.dtype, np.float32)

    def test_embed_normalized(self):
        """All vectors should have L2 norm ≈ 1.0."""
        texts = ["test sentence one", "test sentence two", "test sentence three"]
        result = self.embedder.embed(texts)

        for i in range(len(texts)):
            norm = np.linalg.norm(result[i])
            self.assertAlmostEqual(norm, 1.0, places=4,
                                   msg=f"Vector {i} norm = {norm}, expected 1.0")

    def test_embed_similar_high(self):
        """Semantically similar texts → cosine similarity > 0.5."""
        result = self.embedder.embed(["user login", "authenticate user"])

        # Cosine similarity for L2-normalized vectors: dot product
        similarity = float(np.dot(result[0], result[1]))
        self.assertGreater(similarity, 0.5,
                           f"Expected > 0.5, got {similarity}")

    def test_embed_dissimilar_low(self):
        """Semantically different texts → cosine similarity < 0.5."""
        result = self.embedder.embed(["user login", "database migration schema"])

        similarity = float(np.dot(result[0], result[1]))
        self.assertLess(similarity, 0.5,
                        f"Expected < 0.5, got {similarity}")

    def test_embed_query_shape(self):
        """Single query → shape (384,) — 1D vector."""
        result = self.embedder.embed_query("How does routing work?")
        self.assertEqual(result.shape, (384,))
        self.assertEqual(result.dtype, np.float32)

    def test_embed_empty_list(self):
        """Empty list → shape (0, 384)."""
        result = self.embedder.embed([])
        self.assertEqual(result.shape, (0, 384))


# ═══════════════════════════════════════════════════════════════════════════════
# VECTOR STORE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestVectorStore(unittest.TestCase):
    """Tests for VectorStore FAISS index."""

    @classmethod
    def setUpClass(cls):
        """Create test data once."""
        cls.dimension = 384
        np.random.seed(42)

        # Create 100 random vectors (L2-normalized)
        cls.embeddings = np.random.randn(100, cls.dimension).astype(np.float32)
        # L2 normalize
        norms = np.linalg.norm(cls.embeddings, axis=1, keepdims=True)
        cls.embeddings = cls.embeddings / norms

        # Create 100 matching chunks
        cls.chunks = [
            _make_chunk(f"chunk text {i}", chunk_id=f"chunk_{i}")
            for i in range(100)
        ]

    def test_build_and_search(self):
        """Build with 100 vectors, search returns results."""
        store = VectorStore(dimension=self.dimension)
        store.build(self.embeddings, self.chunks)

        self.assertEqual(store.size, 100)

        # Search with a random query
        query = np.random.randn(self.dimension).astype(np.float32)
        query = query / np.linalg.norm(query)

        results = store.search(query, top_k=5)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r.source == "dense" for r in results))
        # Scores should be in [0, 1]
        self.assertTrue(all(0 <= r.score <= 1 for r in results))

    def test_self_search(self):
        """Search with same vector → top result is itself."""
        store = VectorStore(dimension=self.dimension)
        store.build(self.embeddings, self.chunks)

        # Use vector 42 as query
        query = self.embeddings[42]
        results = store.search(query, top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk.id, "chunk_42")
        # Self-similarity should be very high (≈ 1.0)
        self.assertGreater(results[0].score, 0.99)

    def test_save_and_load(self):
        """Save, load, search → same results."""
        store = VectorStore(dimension=self.dimension)
        store.build(self.embeddings, self.chunks)

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = os.path.join(tmpdir, "test.faiss")
            chunks_path = os.path.join(tmpdir, "chunks.json")

            store.save(index_path, chunks_path)

            # Load into new store
            store2 = VectorStore(dimension=self.dimension)
            store2.load(index_path, chunks_path)

            self.assertEqual(store2.size, 100)
            self.assertEqual(len(store2.chunks), 100)

            # Search should produce same results
            query = self.embeddings[0]
            results1 = store.search(query, top_k=5)
            results2 = store2.search(query, top_k=5)

            self.assertEqual(
                [r.chunk.id for r in results1],
                [r.chunk.id for r in results2],
            )

    def test_search_not_ready(self):
        """Search before build → IndexNotReadyError."""
        store = VectorStore()
        with self.assertRaises(IndexNotReadyError):
            store.search(np.zeros(384, dtype=np.float32))

    def test_search_empty_index(self):
        """Empty index → empty results."""
        store = VectorStore()
        store.build(
            np.zeros((0, 384), dtype=np.float32),
            [],
        )
        results = store.search(np.zeros(384, dtype=np.float32))
        self.assertEqual(len(results), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# BM25 INDEX TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBM25Index(unittest.TestCase):
    """Tests for BM25Index keyword search."""

    def setUp(self):
        self.chunks = [
            _make_chunk("def authenticate(token): verify jwt token", chunk_id="auth"),
            _make_chunk("def process_order(order_id): handle order processing", chunk_id="order"),
            _make_chunk("class DatabaseConnection: manage postgres connections", chunk_id="db"),
            _make_chunk("import os\nimport sys\nfrom pathlib import Path", chunk_id="imports"),
        ]
        self.index = BM25Index()
        self.index.build(self.chunks)

    def test_exact_match(self):
        """Query with exact word → matches chunk containing it."""
        results = self.index.search("process_order", top_k=5)
        self.assertTrue(len(results) > 0)
        # Top result should be the order chunk
        self.assertEqual(results[0].chunk.id, "order")
        self.assertEqual(results[0].source, "bm25")

    def test_no_match(self):
        """Query with unrelated words → no results (or low score)."""
        results = self.index.search("xyzzyspoon quantum teleportation", top_k=5)
        # Should return empty or very low scores
        self.assertEqual(len(results), 0)

    def test_save_and_load(self):
        """Save and load BM25 index → same search results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bm25.pkl")
            self.index.save(path)

            index2 = BM25Index()
            index2.load(path)

            results1 = self.index.search("authenticate token", top_k=3)
            results2 = index2.search("authenticate token", top_k=3)

            self.assertEqual(
                [r.chunk.id for r in results1],
                [r.chunk.id for r in results2],
            )

    def test_empty_query(self):
        """Empty query → no results."""
        results = self.index.search("", top_k=5)
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
