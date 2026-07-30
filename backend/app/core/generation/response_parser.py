"""
RepoMind — Response Parser Module

Extract structured information from LLM responses: citations, and validate them.

How Citation Extraction Works:
    1. Regex finds all [N] patterns in the LLM response
    2. Each [N] maps to context_chunks[N-1] (1-indexed)
    3. Build Citation objects with file_path, lines, score from the chunk
    4. Validate: check if cited file_path exists in the repo's file set

Why Validate Citations?
    LLMs hallucinate. They might cite "auth/security.py" when no such file
    exists. Validation catches this and flags it, preventing users from
    trusting fabricated references.

Reference:
    - Module Design → Section 7 (core/generation/response_parser.py)
    - RAG Workflow → Stage 13 (Response Parsing)
"""

import logging
import re

from app.models.schemas import Citation, ParsedResponse, SearchResult

logger = logging.getLogger(__name__)

# Pattern to match [1], [2], etc. in LLM output
CITATION_PATTERN = re.compile(r"\[(\d+)\]")


class ResponseParser:
    """
    Parse LLM responses to extract and validate citations.

    Usage:
        parser = ResponseParser()
        parsed = parser.parse(
            response="The auth uses JWT [1] with middleware [2].",
            context_chunks=search_results[:5],
        )
        # parsed.citations = [Citation(index=1, ...), Citation(index=2, ...)]
        # parsed.hallucination_flags = ["auth/fake.py"]
    """

    def parse(
        self,
        response: str,
        context_chunks: list[SearchResult],
        repo_files: set[str] | None = None,
    ) -> ParsedResponse:
        """
        Parse LLM response, extract citations, and validate them.

        Args:
            response: Raw LLM response text
            context_chunks: The chunks that were used as context (for mapping)
            repo_files: Set of all file paths in the repo (for validation).
                        If None, skips validation (all citations marked valid).

        Returns:
            ParsedResponse with answer, citations, and hallucination flags
        """
        citations = self._extract_citations(response, context_chunks)

        hallucination_flags = []
        if repo_files is not None:
            citations, hallucination_flags = self._validate_citations(
                citations, repo_files
            )

        return ParsedResponse(
            answer=response,
            citations=citations,
            hallucination_flags=hallucination_flags,
        )

    def _extract_citations(
        self,
        text: str,
        context_chunks: list[SearchResult],
    ) -> list[Citation]:
        """
        Find all [N] citation references in the LLM response.

        Maps each [N] to context_chunks[N-1] to build a Citation
        with file path, line numbers, and score.

        Args:
            text: LLM response text
            context_chunks: Context chunks used in the prompt

        Returns:
            Deduplicated list of Citation objects
        """
        # Find all citation indices
        matches = CITATION_PATTERN.findall(text)
        if not matches:
            return []

        # Deduplicate and sort
        unique_indices = sorted(set(int(m) for m in matches))

        citations = []
        for idx in unique_indices:
            # Citations are 1-indexed: [1] → context_chunks[0]
            chunk_idx = idx - 1

            if chunk_idx < 0 or chunk_idx >= len(context_chunks):
                logger.warning(
                    f"Citation [{idx}] out of range "
                    f"(only {len(context_chunks)} context chunks). Skipping."
                )
                continue

            result = context_chunks[chunk_idx]
            chunk = result.chunk

            citations.append(
                Citation(
                    index=idx,
                    file_path=chunk.file_path,
                    lines=f"{chunk.start_line}-{chunk.end_line}",
                    score=result.score,
                    valid=True,  # Default to valid; validation step may change
                )
            )

        return citations

    def _validate_citations(
        self,
        citations: list[Citation],
        repo_files: set[str],
    ) -> tuple[list[Citation], list[str]]:
        """
        Check if cited file paths actually exist in the repository.

        Args:
            citations: Extracted citations
            repo_files: Set of all file paths in the repo

        Returns:
            Tuple of (updated citations, list of hallucinated file paths)
        """
        hallucination_flags = []

        for citation in citations:
            if citation.file_path in repo_files:
                citation.valid = True
            else:
                citation.valid = False
                hallucination_flags.append(citation.file_path)
                logger.warning(
                    f"Hallucination detected: [{citation.index}] cites "
                    f"'{citation.file_path}' which doesn't exist in the repo"
                )

        return citations, hallucination_flags
