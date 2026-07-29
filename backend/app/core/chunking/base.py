"""
RepoMind — Base Chunker Interface

Abstract base class defining the chunking contract.

This is the Strategy Pattern in action:
    - The pipeline doesn't know or care which chunker it's using
    - It calls chunker.chunk() and gets list[Chunk] back
    - Swapping strategies (code → text → doc) requires zero pipeline changes

All chunkers inherit from BaseChunker and implement the chunk() method.

Reference:
    - Module Design → Section 3 (core/chunking/base.py)
    - RAG Workflow → Stage 5 (Chunking)
"""

from abc import ABC, abstractmethod
from app.models.schemas import Chunk


class BaseChunker(ABC):
    """
    Abstract base class for all chunking strategies.

    Subclasses:
        - CodeChunker: Split by function/class boundaries (AST-aware)
        - DocChunker: Split by heading/section boundaries
        - TextChunker: Recursive text splitting (fallback)
        - ConfigChunker: Keep entire file as one chunk
    """

    @abstractmethod
    def chunk(
        self,
        content: str,
        file_path: str,
        language: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        Split content into chunks.

        Args:
            content: Raw text content to chunk
            file_path: Relative path for chunk metadata
            language: Programming language or format (e.g., "python", "markdown")
            metadata: Optional parsed data (e.g., {"parsed_code": ParsedCode})

        Returns:
            List of Chunk objects with full metadata
        """
        ...
