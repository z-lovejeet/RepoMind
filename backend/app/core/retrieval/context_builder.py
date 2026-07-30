"""
RepoMind — Context Builder Module

Assemble retrieved chunks into a formatted context string for LLM consumption.

The context string is the bridge between retrieval (Stage 8) and generation
(Stage 11). Each chunk is formatted with metadata headers (file path, line
numbers, type, score) and wrapped in language-specific code fences for
syntax highlighting.

Context Budget:
    Default max_context_tokens=4000 (~16K characters). Even though GPT-4o-mini
    has 128K tokens, research shows LLMs perform worse when context is too long
    ("lost in the middle" problem — Liu et al., 2023). 2000-4000 tokens of
    high-quality context outperforms 50K tokens of mediocre context.

Token Estimation:
    We use len(text) // 4 as a rough approximation (1 token ≈ 4 characters
    for English/code). Exact tokenization requires importing tiktoken which
    is deferred to Phase 6.

Reference:
    - Module Design → Section 6 (core/retrieval/context_builder.py)
    - RAG Workflow → Stage 10 (Context Building)
"""

import logging

from app.models.schemas import SearchResult

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Format retrieved chunks into an LLM-ready context string.

    Each chunk is formatted as:
        [i] File: <path> | Lines: <start>-<end> | Type: <type> | Score: <score>
        ```<language>
        <chunk text>
        ```

    Usage:
        builder = ContextBuilder()
        context = builder.build(search_results, max_context_tokens=4000)
    """

    NO_RESULTS_MESSAGE = (
        "No relevant code chunks were found for this query."
    )

    def build(
        self,
        results: list[SearchResult],
        max_context_tokens: int = 4000,
    ) -> str:
        """
        Assemble chunks into a context string for the LLM.

        Adds chunks in order (highest relevance first) until the token
        budget is exhausted. Does NOT split chunks — either includes
        a chunk fully or skips it entirely.

        Args:
            results: List of SearchResult sorted by relevance
            max_context_tokens: Maximum tokens for the context string.
                                Default 4000 (~16K characters).

        Returns:
            Formatted context string ready for LLM prompt
        """
        if not results:
            return self.NO_RESULTS_MESSAGE

        context_parts: list[str] = []
        total_tokens = 0

        for i, result in enumerate(results):
            # Format this chunk
            formatted = self._format_chunk(i + 1, result)
            chunk_tokens = self._estimate_tokens(formatted)

            # Check budget
            if total_tokens + chunk_tokens > max_context_tokens:
                logger.info(
                    f"Context budget reached: {total_tokens} tokens, "
                    f"stopping at chunk {i}/{len(results)}"
                )
                break

            context_parts.append(formatted)
            total_tokens += chunk_tokens

        if not context_parts:
            # Even the first chunk exceeds budget — include it anyway
            # (better to have one chunk than none)
            context_parts.append(self._format_chunk(1, results[0]))
            total_tokens = self._estimate_tokens(context_parts[0])

        context = "\n\n".join(context_parts)

        logger.info(
            f"Built context: {len(context_parts)} chunks, "
            f"~{total_tokens} tokens"
        )

        return context

    def _format_chunk(self, index: int, result: SearchResult) -> str:
        """
        Format a single chunk with metadata header and code fence.

        Args:
            index: 1-based citation number ([1], [2], etc.)
            result: SearchResult containing the chunk and score

        Returns:
            Formatted string block
        """
        chunk = result.chunk

        # ─── Header line ───
        header = (
            f"[{index}] File: {chunk.file_path} | "
            f"Lines: {chunk.start_line}-{chunk.end_line} | "
            f"Type: {chunk.chunk_type} | "
            f"Score: {result.score:.2f}"
        )

        # ─── Code fence ───
        # Use the chunk's language for syntax highlighting
        language = chunk.language if chunk.language else ""
        text = chunk.text.rstrip()

        body = f"```{language}\n{text}\n```"

        return f"{header}\n{body}"

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count without a tokenizer.

        Approximation: 1 token ≈ 4 characters.
        This is conservative for code (which has more special characters)
        but sufficient for budget enforcement.

        Args:
            text: Text string to estimate

        Returns:
            Estimated token count
        """
        return len(text) // 4
