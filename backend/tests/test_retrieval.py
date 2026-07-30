"""
RepoMind — Unit Tests for Retrieval & Context Builder

Tests for:
    - Retriever: dense, bm25, hybrid, RRF merge, edge cases
    - ContextBuilder: formatting, token limits, empty results

Reference: Development Roadmap → Phase 5 → Testing
"""

import unittest

import numpy as np

from app.core.embedding.embedder import Embedder
from app.core.indexing.vector_store import VectorStore
from app.core.indexing.bm25_index import BM25Index
from app.core.retrieval.retriever import Retriever
from app.core.retrieval.context_builder import ContextBuilder
from app.models.schemas import Chunk, SearchResult


def _make_chunk(
    text: str,
    chunk_id: str = "test",
    file_path: str = "test.py",
    chunk_type: str = "code",
    language: str = "python",
    start_line: int = 1,
    end_line: int = 10,
) -> Chunk:
    """Helper to create test Chunk objects."""
    return Chunk(
        id=chunk_id,
        text=text,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        chunk_type=chunk_type,
        language=language,
        parent_symbol=None,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES — Shared across retriever tests
# ═══════════════════════════════════════════════════════════════════════════════


# Sample chunks simulating a real codebase
SAMPLE_CHUNKS = [
    _make_chunk(
        "def authenticate(token: str) -> User:\n"
        "    decoded = jwt.decode(token, SECRET_KEY)\n"
        "    return User.get(decoded['user_id'])",
        chunk_id="auth_func",
        file_path="auth/middleware.py",
        start_line=8,
        end_line=11,
    ),
    _make_chunk(
        "class AuthMiddleware:\n"
        "    def verify(self, request):\n"
        "        token = request.headers.get('Authorization')\n"
        "        return self.authenticate(token)",
        chunk_id="auth_class",
        file_path="auth/middleware.py",
        start_line=15,
        end_line=19,
    ),
    _make_chunk(
        "def process_order(order_id: int) -> OrderResult:\n"
        "    order = Order.get(order_id)\n"
        "    payment = charge_payment(order.total)\n"
        "    return OrderResult(order=order, payment=payment)",
        chunk_id="order_func",
        file_path="orders/service.py",
        start_line=1,
        end_line=4,
    ),
    _make_chunk(
        "## Authentication\n"
        "The API uses JWT tokens for authentication.\n"
        "Include the token in the Authorization header.",
        chunk_id="auth_doc",
        file_path="README.md",
        chunk_type="documentation",
        language="markdown",
        start_line=45,
        end_line=48,
    ),
    _make_chunk(
        "DATABASE_URL=postgresql://localhost:5432/app\n"
        "SECRET_KEY=super-secret-key-here\n"
        "DEBUG=true",
        chunk_id="env_config",
        file_path=".env",
        chunk_type="config",
        language="env",
        start_line=1,
        end_line=3,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# RETRIEVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRetriever(unittest.TestCase):
    """Tests for Retriever with real embeddings."""

    @classmethod
    def setUpClass(cls):
        """Build real indexes from sample chunks (expensive, done once)."""
        cls.embedder = Embedder()
        cls.chunks = SAMPLE_CHUNKS

        # Embed all chunks
        texts = [c.text for c in cls.chunks]
        embeddings = cls.embedder.embed(texts)

        # Build vector store
        cls.vector_store = VectorStore(dimension=cls.embedder.dimension)
        cls.vector_store.build(embeddings, cls.chunks)

        # Build BM25 index
        cls.bm25_index = BM25Index()
        cls.bm25_index.build(cls.chunks)

        # Create retriever
        cls.retriever = Retriever(
            vector_store=cls.vector_store,
            bm25_index=cls.bm25_index,
            embedder=cls.embedder,
        )

    def test_dense_returns_results(self):
        """Dense search returns non-empty list with source='dense'."""
        results = self.retriever.retrieve(
            "How does authentication work?",
            strategy="dense",
            top_k=3,
        )
        self.assertTrue(len(results) > 0)
        self.assertTrue(all(r.source == "dense" for r in results))

    def test_bm25_exact_match(self):
        """BM25 finds exact keyword in chunk."""
        results = self.retriever.retrieve(
            "process_order",
            strategy="bm25",
            top_k=3,
        )
        self.assertTrue(len(results) > 0)
        # Top result should contain "process_order"
        self.assertIn("process_order", results[0].chunk.text)
        self.assertEqual(results[0].source, "bm25")

    def test_hybrid_combines_both(self):
        """Hybrid returns results (combines dense and BM25)."""
        results = self.retriever.retrieve(
            "How does authentication work?",
            strategy="hybrid",
            top_k=5,
        )
        self.assertTrue(len(results) > 0)
        self.assertTrue(all(r.source == "hybrid" for r in results))

    def test_invalid_strategy(self):
        """Unknown strategy → ValueError."""
        with self.assertRaises(ValueError):
            self.retriever.retrieve("test", strategy="invalid")

    def test_hyde_not_available(self):
        """HyDE strategy → clear error message."""
        with self.assertRaises(ValueError) as ctx:
            self.retriever.retrieve("test", strategy="hyde")
        self.assertIn("Phase 6", str(ctx.exception))

    def test_empty_query(self):
        """Empty string → empty results."""
        results = self.retriever.retrieve("", strategy="dense")
        self.assertEqual(len(results), 0)

        results = self.retriever.retrieve("   ", strategy="bm25")
        self.assertEqual(len(results), 0)


class TestRRFMerge(unittest.TestCase):
    """Tests specifically for Reciprocal Rank Fusion logic."""

    def setUp(self):
        """Create a retriever with mock dependencies (RRF doesn't use them)."""
        # RRF merge is a pure function on lists — we can test it in isolation
        # by calling _rrf_merge directly
        self.retriever = Retriever.__new__(Retriever)

    def test_rrf_merge_scores(self):
        """Verify RRF score computation: 1/(60+rank+1)."""
        chunk_a = _make_chunk("chunk A", chunk_id="a")
        chunk_b = _make_chunk("chunk B", chunk_id="b")

        results_a = [
            SearchResult(chunk=chunk_a, score=0.9, source="dense"),
            SearchResult(chunk=chunk_b, score=0.8, source="dense"),
        ]
        results_b = []  # Only one list

        merged = self.retriever._rrf_merge(results_a, results_b, k=60)

        # chunk_a at rank 0: 1/(60+0+1) = 1/61 ≈ 0.01639
        # chunk_b at rank 1: 1/(60+1+1) = 1/62 ≈ 0.01613
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].chunk.id, "a")
        self.assertAlmostEqual(merged[0].score, 1 / 61, places=5)
        self.assertAlmostEqual(merged[1].score, 1 / 62, places=5)

    def test_rrf_ranks_dual_presence(self):
        """Chunk in both lists ranks higher than single-list chunks."""
        chunk_both = _make_chunk("in both", chunk_id="both")
        chunk_only_a = _make_chunk("only in A", chunk_id="only_a")
        chunk_only_b = _make_chunk("only in B", chunk_id="only_b")

        results_a = [
            SearchResult(chunk=chunk_only_a, score=0.95, source="dense"),
            SearchResult(chunk=chunk_both, score=0.90, source="dense"),
        ]
        results_b = [
            SearchResult(chunk=chunk_both, score=8.5, source="bm25"),
            SearchResult(chunk=chunk_only_b, score=5.0, source="bm25"),
        ]

        merged = self.retriever._rrf_merge(results_a, results_b, k=60)

        # "both" should be #1 because it gets scores from both lists:
        #   From list A (rank 1): 1/(60+1+1) = 1/62
        #   From list B (rank 0): 1/(60+0+1) = 1/61
        #   Total: 1/61 + 1/62 ≈ 0.03252
        #
        # "only_a" gets only: 1/(60+0+1) = 1/61 ≈ 0.01639
        # "only_b" gets only: 1/(60+1+1) = 1/62 ≈ 0.01613
        self.assertEqual(merged[0].chunk.id, "both")
        self.assertGreater(merged[0].score, merged[1].score)
        self.assertEqual(merged[0].source, "hybrid")

    def test_rrf_empty_lists(self):
        """Both empty lists → empty result."""
        merged = self.retriever._rrf_merge([], [])
        self.assertEqual(len(merged), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestContextBuilder(unittest.TestCase):
    """Tests for ContextBuilder formatting and token limits."""

    def setUp(self):
        self.builder = ContextBuilder()

        # Sample results
        self.results = [
            SearchResult(
                chunk=_make_chunk(
                    "def authenticate(token):\n    return jwt.decode(token)",
                    chunk_id="auth",
                    file_path="auth/middleware.py",
                    start_line=8,
                    end_line=10,
                ),
                score=0.92,
                source="dense",
            ),
            SearchResult(
                chunk=_make_chunk(
                    "## Authentication\nThe API uses JWT tokens.",
                    chunk_id="doc",
                    file_path="README.md",
                    chunk_type="documentation",
                    language="markdown",
                    start_line=45,
                    end_line=47,
                ),
                score=0.85,
                source="bm25",
            ),
        ]

    def test_context_format_has_header(self):
        """Output contains [1] File: ... header."""
        context = self.builder.build(self.results)
        self.assertIn("[1] File: auth/middleware.py", context)
        self.assertIn("Lines: 8-10", context)
        self.assertIn("Type: code", context)
        self.assertIn("Score: 0.92", context)

    def test_context_format_has_code_fence(self):
        """Output contains language-tagged code fences."""
        context = self.builder.build(self.results)
        self.assertIn("```python", context)
        self.assertIn("```markdown", context)

    def test_context_numbering(self):
        """Multiple chunks numbered [1], [2]."""
        context = self.builder.build(self.results)
        self.assertIn("[1] File:", context)
        self.assertIn("[2] File:", context)

    def test_context_respects_token_limit(self):
        """With very small budget, only partial chunks included."""
        # Each result is roughly 150+ chars → 37+ tokens
        # Set budget so only one fits
        context = self.builder.build(self.results, max_context_tokens=50)

        # Should have [1] but not [2]
        self.assertIn("[1]", context)
        self.assertNotIn("[2]", context)

    def test_context_empty_results(self):
        """Empty list → 'no results' message."""
        context = self.builder.build([])
        self.assertEqual(context, ContextBuilder.NO_RESULTS_MESSAGE)

    def test_context_first_chunk_always_included(self):
        """Even if first chunk exceeds budget, it's still included."""
        context = self.builder.build(self.results, max_context_tokens=1)
        self.assertIn("[1] File:", context)


if __name__ == "__main__":
    unittest.main()
