"""
RepoMind — Unit Tests for Generation & Pipeline

Tests for:
    - LLMClient: provider validation, missing key
    - PromptBuilder: system/user message format, grounding constraint
    - ResponseParser: citation extraction, dedup, validation, out-of-range
    - Pipeline: ingest produces chunks, query returns answer (mocked LLM)

All LLM calls are mocked — no API key needed to run these tests.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

from app.core.generation.llm_client import LLMClient, LLMError
from app.core.generation.prompt_builder import PromptBuilder
from app.core.generation.response_parser import ResponseParser
from app.core.pipeline import Pipeline
from app.core.embedding.embedder import Embedder
from app.models.schemas import (
    Chunk,
    Citation,
    ParsedResponse,
    PipelineResult,
    SearchResult,
    QueryConfig,
)


def _make_chunk(
    text: str,
    chunk_id: str = "test",
    file_path: str = "test.py",
    chunk_type: str = "code",
    language: str = "python",
    start_line: int = 1,
    end_line: int = 10,
) -> Chunk:
    """Helper to create test chunks."""
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


def _make_search_result(
    text: str,
    chunk_id: str = "test",
    file_path: str = "test.py",
    score: float = 0.9,
    start_line: int = 1,
    end_line: int = 10,
) -> SearchResult:
    """Helper to create SearchResult objects."""
    return SearchResult(
        chunk=_make_chunk(text, chunk_id=chunk_id, file_path=file_path,
                         start_line=start_line, end_line=end_line),
        score=score,
        source="hybrid",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# LLM CLIENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMClient(unittest.TestCase):
    """Tests for LLMClient initialization and validation."""

    def test_invalid_provider(self):
        """Unknown provider → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            LLMClient(provider="invalid_provider")
        self.assertIn("Unknown provider", str(ctx.exception))

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_gemini_key(self):
        """No GEMINI_API_KEY → clear LLMError."""
        # Clear any existing env vars
        os.environ.pop("GEMINI_API_KEY", None)
        with self.assertRaises(LLMError) as ctx:
            LLMClient(provider="gemini")
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))
        self.assertIn("aistudio.google.com", str(ctx.exception))

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_groq_key(self):
        """No GROQ_API_KEY → clear LLMError."""
        os.environ.pop("GROQ_API_KEY", None)
        with self.assertRaises(LLMError) as ctx:
            LLMClient(provider="groq")
        self.assertIn("GROQ_API_KEY", str(ctx.exception))
        self.assertIn("console.groq.com", str(ctx.exception))


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromptBuilder(unittest.TestCase):
    """Tests for PromptBuilder message construction."""

    def setUp(self):
        self.builder = PromptBuilder()
        self.context = (
            "[1] File: auth/middleware.py | Lines: 8-35 | Type: code\n"
            "```python\ndef authenticate(token): ...\n```"
        )
        self.query = "How does authentication work?"

    def test_prompt_has_system(self):
        """Output has 'system' key."""
        prompt = self.builder.build(self.context, self.query)
        self.assertIn("system", prompt)
        self.assertIsInstance(prompt["system"], str)
        self.assertTrue(len(prompt["system"]) > 0)

    def test_prompt_has_user(self):
        """Output has 'user' key with context + query."""
        prompt = self.builder.build(self.context, self.query)
        self.assertIn("user", prompt)
        self.assertIn("CONTEXT:", prompt["user"])
        self.assertIn("QUESTION:", prompt["user"])

    def test_prompt_contains_context(self):
        """Context string appears in user message."""
        prompt = self.builder.build(self.context, self.query)
        self.assertIn("auth/middleware.py", prompt["user"])
        self.assertIn("authenticate", prompt["user"])

    def test_prompt_grounding_instruction(self):
        """System prompt contains 'ONLY' grounding constraint."""
        prompt = self.builder.build(self.context, self.query)
        self.assertIn("ONLY", prompt["system"])
        self.assertIn("Cite sources", prompt["system"])

    def test_prompt_repo_name(self):
        """System prompt includes repo name."""
        prompt = self.builder.build(self.context, self.query, repo_name="flask")
        self.assertIn("flask", prompt["system"])


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE PARSER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestResponseParser(unittest.TestCase):
    """Tests for ResponseParser citation extraction and validation."""

    def setUp(self):
        self.parser = ResponseParser()
        self.context_chunks = [
            _make_search_result(
                "def authenticate(token): ...",
                chunk_id="auth",
                file_path="auth/middleware.py",
                score=0.92,
                start_line=8,
                end_line=35,
            ),
            _make_search_result(
                "## Authentication\nJWT tokens...",
                chunk_id="doc",
                file_path="README.md",
                score=0.85,
                start_line=45,
                end_line=52,
            ),
        ]

    def test_parse_citations(self):
        """Extract [1] [2] from LLM text."""
        response = "Auth uses JWT [1] as documented in [2]."
        parsed = self.parser.parse(response, self.context_chunks)

        self.assertEqual(len(parsed.citations), 2)
        self.assertEqual(parsed.citations[0].index, 1)
        self.assertEqual(parsed.citations[0].file_path, "auth/middleware.py")
        self.assertEqual(parsed.citations[1].index, 2)
        self.assertEqual(parsed.citations[1].file_path, "README.md")

    def test_parse_citations_dedup(self):
        """Same [1] twice → one Citation object."""
        response = "Auth [1] works via JWT [1] middleware."
        parsed = self.parser.parse(response, self.context_chunks)

        self.assertEqual(len(parsed.citations), 1)
        self.assertEqual(parsed.citations[0].index, 1)

    def test_validate_citations_valid(self):
        """Known file → valid=True."""
        response = "Auth uses middleware [1]."
        repo_files = {"auth/middleware.py", "README.md"}
        parsed = self.parser.parse(response, self.context_chunks, repo_files)

        self.assertTrue(parsed.citations[0].valid)
        self.assertEqual(len(parsed.hallucination_flags), 0)

    def test_validate_citations_invalid(self):
        """Unknown file → valid=False, hallucination_flag."""
        response = "Auth uses middleware [1]."
        # repo_files does NOT contain "auth/middleware.py"
        repo_files = {"other/file.py"}
        parsed = self.parser.parse(response, self.context_chunks, repo_files)

        self.assertFalse(parsed.citations[0].valid)
        self.assertIn("auth/middleware.py", parsed.hallucination_flags)

    def test_parse_out_of_range(self):
        """[99] with 2 chunks → skipped."""
        response = "See [1] and also [99]."
        parsed = self.parser.parse(response, self.context_chunks)

        # Only [1] should be extracted, [99] is out of range
        self.assertEqual(len(parsed.citations), 1)
        self.assertEqual(parsed.citations[0].index, 1)

    def test_parse_no_citations(self):
        """Response with no citations → empty list."""
        response = "I don't have enough information."
        parsed = self.parser.parse(response, self.context_chunks)

        self.assertEqual(len(parsed.citations), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestPipeline(unittest.TestCase):
    """Tests for Pipeline orchestrator (with mocked LLM)."""

    @classmethod
    def setUpClass(cls):
        """Create a real embedder (loaded once)."""
        cls.embedder = Embedder()

    def _create_test_repo(self, tmp_dir: str):
        """Create a minimal test repo."""
        os.makedirs(os.path.join(tmp_dir, "src"), exist_ok=True)

        with open(os.path.join(tmp_dir, "src", "main.py"), "w") as f:
            f.write(
                "def greet(name: str) -> str:\n"
                "    \"\"\"Return a greeting message.\"\"\"\n"
                "    return f'Hello, {name}!'\n\n"
                "def add(a: int, b: int) -> int:\n"
                "    \"\"\"Add two numbers.\"\"\"\n"
                "    return a + b\n"
            )

        with open(os.path.join(tmp_dir, "README.md"), "w") as f:
            f.write(
                "# Test Project\n\n"
                "A simple test project with greeting and math functions.\n\n"
                "## Usage\n"
                "Call `greet('World')` to get a greeting.\n"
            )

    def test_pipeline_ingest(self):
        """Ingest a 2-file fixture → chunk_count > 0."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            self._create_test_repo(tmp_dir)

            # Create pipeline with mocked LLM
            mock_llm = MagicMock(spec=LLMClient)
            pipeline = Pipeline(
                embedder=self.embedder,
                llm_client=mock_llm,
            )

            result = pipeline.ingest(tmp_dir, "test_repo")

            self.assertGreater(result.file_count, 0)
            self.assertGreater(result.chunk_count, 0)
            self.assertIn("scan_ms", result.timings)
            self.assertIn("embed_ms", result.timings)

    def test_pipeline_query(self):
        """Mock LLM → returns PipelineResult with answer."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            self._create_test_repo(tmp_dir)

            # Mock LLM to return a citation-rich answer
            mock_llm = MagicMock(spec=LLMClient)
            mock_llm.generate.return_value = (
                "The greet function [1] returns a formatted greeting string."
            )

            pipeline = Pipeline(
                embedder=self.embedder,
                llm_client=mock_llm,
            )

            # Ingest first
            pipeline.ingest(tmp_dir)

            # Query
            result = pipeline.query("How does greet work?")

            self.assertIsInstance(result, PipelineResult)
            self.assertIn("greet", result.answer)
            self.assertIn("retrieval_ms", result.timings)
            self.assertIn("generation_ms", result.timings)

            # LLM was called
            mock_llm.generate.assert_called_once()

    def test_pipeline_query_before_ingest(self):
        """Query before ingest → RuntimeError."""
        mock_llm = MagicMock(spec=LLMClient)
        pipeline = Pipeline(embedder=self.embedder, llm_client=mock_llm)

        with self.assertRaises(RuntimeError) as ctx:
            pipeline.query("test?")
        self.assertIn("ingest()", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
