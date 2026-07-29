"""
RepoMind — Documentation Chunker Module

Split documentation files into chunks by heading/section boundaries.

Each DocSection from the doc parser becomes one chunk. The heading
is included in the chunk text as context so the embedding captures
what the section is about.

Example:
    Section: DocSection(heading="Installation", level=2, content="Run pip install...")
    Chunk text: "## Installation\n\nRun pip install..."

Why include the heading in chunk text?
    Without it, the embedding of "Run pip install..." has no context.
    With it, the embedding of "## Installation\nRun pip install..."
    captures that this text is ABOUT installation.

Reference:
    - Module Design → Section 3 (core/chunking/doc_chunker.py)
    - RAG Workflow → Stage 5 (Chunking) → Strategy 2: Doc Chunker
"""

import uuid

from app.models.schemas import Chunk, DocSection
from app.core.chunking.base import BaseChunker


class DocChunker(BaseChunker):
    """
    Split documentation into chunks at heading boundaries.

    Each section (heading + content) becomes one chunk.
    If metadata contains parsed sections, those are used.
    Otherwise, treats the entire content as a single chunk.

    Usage:
        from app.core.parsing.doc_parser import DocParser
        parser = DocParser()
        sections = parser.parse_markdown(source, "README.md")

        chunker = DocChunker()
        chunks = chunker.chunk(source, "README.md", "markdown",
                               metadata={"sections": sections})
    """

    def chunk(
        self,
        content: str,
        file_path: str,
        language: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        Split documentation into chunks by heading.

        Args:
            content: Raw documentation text
            file_path: Relative file path
            language: Document format (e.g., "markdown", "restructuredtext")
            metadata: Should contain {"sections": list[DocSection]}

        Returns:
            List of Chunk objects. Empty list if content is empty.
        """
        if not content or not content.strip():
            return []

        # If no parsed sections, return whole file as one chunk
        if not metadata or "sections" not in metadata:
            return [Chunk(
                id=uuid.uuid4().hex,
                text=content,
                file_path=file_path,
                start_line=1,
                end_line=content.count("\n") + 1,
                chunk_type="documentation",
                language=language,
                parent_symbol=None,
            )]

        sections: list[DocSection] = metadata["sections"]
        chunks: list[Chunk] = []

        for section in sections:
            chunk = self._section_to_chunk(section, file_path, language)
            if chunk:
                chunks.append(chunk)

        return chunks

    def _section_to_chunk(
        self, section: DocSection, file_path: str, language: str
    ) -> Chunk | None:
        """
        Convert a DocSection into a Chunk.

        Includes the heading in the chunk text for embedding context.
        """
        # Build chunk text: heading + content
        if section.heading and section.level > 0:
            heading_prefix = "#" * section.level + " " + section.heading
            text = heading_prefix + "\n\n" + section.content if section.content else heading_prefix
        elif section.content:
            text = section.content
        else:
            return None  # Empty section

        text = text.strip()
        if not text:
            return None

        return Chunk(
            id=uuid.uuid4().hex,
            text=text,
            file_path=file_path,
            start_line=section.start_line,
            end_line=section.end_line,
            chunk_type="documentation",
            language=language,
            parent_symbol=section.heading if section.heading else None,
        )
