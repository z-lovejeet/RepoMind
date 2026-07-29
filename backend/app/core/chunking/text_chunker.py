"""
RepoMind — Text Chunker Module

Recursive text splitting — the fallback chunking strategy for files
without AST parsing support (unknown file types, non-Python code, etc.)

Algorithm:
    1. Try to split on the most desirable separator (paragraph breaks)
    2. If chunks are still too large, recursively split on next separator
    3. Separator hierarchy: "\\n\\n" → "\\n" → ". " → " " → ""

Why a separator hierarchy?
    We want to split at the most NATURAL boundary:
    1. "\\n\\n" — Paragraph breaks (best — preserves paragraphs)
    2. "\\n"   — Line breaks (good — preserves lines)
    3. ". "   — Sentence ends (okay — preserves sentences)
    4. " "    — Word boundaries (poor — breaks mid-sentence)
    5. ""     — Character boundaries (worst — breaks mid-word)

Chunk Overlap:
    Adjacent chunks share `overlap` characters to prevent information
    loss at boundaries. Without overlap, a query about "JWT tokens"
    might miss a chunk that says "...uses JWT" at the end and
    "tokens expire after 24h..." at the start of the next chunk.

Reference:
    - Module Design → Section 3 (core/chunking/text_chunker.py)
    - RAG Workflow → Stage 5 (Chunking) → Strategy 3: Text Chunker
"""

import uuid

from app.models.schemas import Chunk
from app.core.chunking.base import BaseChunker


class TextChunker(BaseChunker):
    """
    Split text using recursive separator hierarchy with overlap.

    Usage:
        chunker = TextChunker(chunk_size=512, chunk_overlap=50)
        chunks = chunker.chunk(content, "notes.txt", "text")
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Args:
            chunk_size: Maximum characters per chunk (default 512)
            chunk_overlap: Characters shared between adjacent chunks (default 50)

        Raises:
            ValueError: If overlap >= chunk_size
        """
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"Overlap ({chunk_overlap}) must be < chunk_size ({chunk_size}). "
                "Overlap >= chunk_size would cause infinite loops."
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def chunk(
        self,
        content: str,
        file_path: str,
        language: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        Split text using recursive separator hierarchy.

        Args:
            content: Raw text content to chunk
            file_path: Relative file path
            language: Language/format identifier
            metadata: Not used by TextChunker

        Returns:
            List of Chunk objects. Empty list if content is empty.
        """
        if not content or not content.strip():
            return []

        # If content fits in one chunk, return it directly
        if len(content) <= self.chunk_size:
            return [Chunk(
                id=uuid.uuid4().hex,
                text=content.strip(),
                file_path=file_path,
                start_line=1,
                end_line=content.count("\n") + 1,
                chunk_type="text",
                language=language,
                parent_symbol=None,
            )]

        # Recursive split
        text_pieces = self._recursive_split(content, self.separators)

        # Apply overlap
        text_pieces = self._apply_overlap(text_pieces)

        # Convert to Chunk objects
        chunks: list[Chunk] = []
        line_offset = 1

        for piece in text_pieces:
            piece = piece.strip()
            if not piece:
                continue

            line_count = piece.count("\n") + 1

            chunks.append(Chunk(
                id=uuid.uuid4().hex,
                text=piece,
                file_path=file_path,
                start_line=line_offset,
                end_line=line_offset + line_count - 1,
                chunk_type="text",
                language=language,
                parent_symbol=None,
            ))

            # Advance line offset (accounting for overlap)
            line_offset += max(1, line_count - (self.chunk_overlap // 10))

        return chunks

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        """
        Core recursive splitting algorithm.

        Try the first separator. If any resulting pieces are still too
        large, recursively split them with the remaining separators.

        Args:
            text: Text to split
            separators: Remaining separators to try (most desirable first)

        Returns:
            List of text pieces, each <= chunk_size
        """
        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            # Last resort: hard split by character count
            pieces = []
            for i in range(0, len(text), self.chunk_size):
                pieces.append(text[i:i + self.chunk_size])
            return pieces

        separator = separators[0]
        remaining_separators = separators[1:]

        # Split on this separator
        if separator == "":
            # Empty separator = character-level split
            pieces = []
            for i in range(0, len(text), self.chunk_size):
                pieces.append(text[i:i + self.chunk_size])
            return pieces

        parts = text.split(separator)

        # Merge parts into chunks that fit within chunk_size
        merged: list[str] = []
        current = ""

        for part in parts:
            candidate = (current + separator + part) if current else part

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                # Save current chunk
                if current:
                    merged.append(current)

                # If this single part exceeds chunk_size,
                # recursively split it with remaining separators
                if len(part) > self.chunk_size:
                    sub_pieces = self._recursive_split(part, remaining_separators)
                    merged.extend(sub_pieces)
                    current = ""
                else:
                    current = part

        if current:
            merged.append(current)

        return merged

    def _apply_overlap(self, pieces: list[str]) -> list[str]:
        """
        Add overlap between adjacent chunks.

        Each chunk (except the first) gets the last `overlap` characters
        from the previous chunk prepended to it.
        """
        if self.chunk_overlap <= 0 or len(pieces) <= 1:
            return pieces

        result = [pieces[0]]

        for i in range(1, len(pieces)):
            prev = pieces[i - 1]
            overlap_text = prev[-self.chunk_overlap:]

            # Prepend overlap to current piece
            result.append(overlap_text + pieces[i])

        return result
