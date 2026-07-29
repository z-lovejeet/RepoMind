"""
RepoMind — Config Chunker Module

Keep configuration files as single, whole-file chunks.

Why not split config files?
    Config files are small and internally cross-referenced.
    Splitting a pyproject.toml mid-way would separate [project]
    from [build-system], losing the context that they're both
    parts of the same project configuration.

    A typical config file is 20-100 lines — well within embedding
    limits and LLM context windows.

Reference:
    - Module Design → Section 3 (core/chunking/config_chunker.py)
    - RAG Workflow → Stage 5 (Chunking) → Strategy 4: Config Chunker
"""

import uuid

from app.models.schemas import Chunk
from app.core.chunking.base import BaseChunker


class ConfigChunker(BaseChunker):
    """
    Keep entire config files as single chunks.

    Usage:
        chunker = ConfigChunker()
        chunks = chunker.chunk(content, "pyproject.toml", "toml")
        assert len(chunks) == 1
    """

    def chunk(
        self,
        content: str,
        file_path: str,
        language: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        Return the entire config file as a single chunk.

        Args:
            content: Raw config file content
            file_path: Relative file path
            language: Config format (e.g., "json", "yaml", "toml")
            metadata: Not used by ConfigChunker

        Returns:
            List with exactly one Chunk, or empty list if content is empty.
        """
        if not content or not content.strip():
            return []

        return [Chunk(
            id=uuid.uuid4().hex,
            text=content.strip(),
            file_path=file_path,
            start_line=1,
            end_line=content.count("\n") + 1,
            chunk_type="config",
            language=language,
            parent_symbol=None,
        )]
