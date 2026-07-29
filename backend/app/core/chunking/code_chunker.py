"""
RepoMind — Code Chunker Module

Split Python source code into chunks at function/class boundaries.

Uses ParsedCode from the code parser to create semantically meaningful chunks:
    - Each function → one chunk
    - Each class (with all methods) → one chunk
    - Module-level code (imports + globals) → one chunk

Key Rule: NEVER split within a function.
    A 200-line function becomes one 200-line chunk. Semantic completeness
    is more important than size uniformity. If a function is too long,
    the embedding will capture its overall meaning, and the LLM gets
    the complete context it needs to answer questions about it.

Reference:
    - Module Design → Section 3 (core/chunking/code_chunker.py)
    - RAG Workflow → Stage 5 (Chunking) → Strategy 1: Code Chunker
"""

import uuid

from app.models.schemas import Chunk, ParsedCode, ParsedFunction, ParsedClass
from app.core.chunking.base import BaseChunker


class CodeChunker(BaseChunker):
    """
    Split code into chunks at function/class boundaries.

    Requires metadata["parsed_code"] (ParsedCode) from the code parser.
    Falls back to returning the entire file as one chunk if no parsed
    data is provided.

    Usage:
        from app.core.parsing.code_parser import CodeParser
        parser = CodeParser()
        parsed = parser.parse(source, "auth/middleware.py")

        chunker = CodeChunker()
        chunks = chunker.chunk(source, "auth/middleware.py", "python",
                               metadata={"parsed_code": parsed})
    """

    def chunk(
        self,
        content: str,
        file_path: str,
        language: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        Split code into chunks at function/class boundaries.

        Args:
            content: Raw source code string
            file_path: Relative file path
            language: Programming language (e.g., "python")
            metadata: Must contain {"parsed_code": ParsedCode}

        Returns:
            List of Chunk objects. Empty list if content is empty.
        """
        if not content or not content.strip():
            return []

        # If no parsed data, return the whole file as one chunk
        if not metadata or "parsed_code" not in metadata:
            return [Chunk(
                id=uuid.uuid4().hex,
                text=content,
                file_path=file_path,
                start_line=1,
                end_line=content.count("\n") + 1,
                chunk_type="code",
                language=language,
                parent_symbol=None,
            )]

        parsed: ParsedCode = metadata["parsed_code"]
        chunks: list[Chunk] = []

        # ─── Chunk each function ───
        for fn in parsed.functions:
            chunk = self._chunk_function(fn, file_path, language)
            if chunk:
                chunks.append(chunk)

        # ─── Chunk each class (entire class = one chunk) ───
        for cls in parsed.classes:
            chunk = self._chunk_class(cls, file_path, language)
            if chunk:
                chunks.append(chunk)

        # ─── Module-level code (imports + globals) ───
        module_chunk = self._chunk_module_level(
            content, parsed, file_path, language
        )
        if module_chunk:
            chunks.append(module_chunk)

        return chunks

    def _chunk_function(
        self, fn: ParsedFunction, file_path: str, language: str
    ) -> Chunk | None:
        """Create a chunk from a single parsed function."""
        if not fn.body or not fn.body.strip():
            return None

        return Chunk(
            id=uuid.uuid4().hex,
            text=fn.body,
            file_path=file_path,
            start_line=fn.start_line,
            end_line=fn.end_line,
            chunk_type="code",
            language=language,
            parent_symbol=fn.name,
        )

    def _chunk_class(
        self, cls: ParsedClass, file_path: str, language: str
    ) -> Chunk | None:
        """
        Create a chunk from a single parsed class.

        The entire class (including all methods) is one chunk.
        This preserves the relationship between methods and their class.
        """
        if not cls.body or not cls.body.strip():
            return None

        return Chunk(
            id=uuid.uuid4().hex,
            text=cls.body,
            file_path=file_path,
            start_line=cls.start_line,
            end_line=cls.end_line,
            chunk_type="code",
            language=language,
            parent_symbol=cls.name,
        )

    def _chunk_module_level(
        self,
        source: str,
        parsed: ParsedCode,
        file_path: str,
        language: str,
    ) -> Chunk | None:
        """
        Create a chunk from module-level code (imports + global statements).

        Extracts lines that are NOT part of any function or class body.
        This typically includes import statements and global variable assignments.
        """
        source_lines = source.splitlines()

        # Collect line ranges that belong to functions and classes
        occupied: set[int] = set()
        for fn in parsed.functions:
            for line_no in range(fn.start_line, fn.end_line + 1):
                occupied.add(line_no)
        for cls in parsed.classes:
            for line_no in range(cls.start_line, cls.end_line + 1):
                occupied.add(line_no)

        # Collect module-level lines (not in any function/class)
        module_lines: list[str] = []
        for i, line in enumerate(source_lines, start=1):
            if i not in occupied:
                module_lines.append(line)

        module_text = "\n".join(module_lines).strip()

        if not module_text:
            return None

        return Chunk(
            id=uuid.uuid4().hex,
            text=module_text,
            file_path=file_path,
            start_line=1,
            end_line=len(source_lines),
            chunk_type="code",
            language=language,
            parent_symbol="<module>",
        )
