"""
RepoMind — Unit Tests for Parsing & Chunking Modules

Tests for:
    - CodeParser: parse functions, classes, imports, syntax errors
    - DocParser: parse markdown headings, code blocks, empty content
    - ConfigParser: parse JSON, YAML, TOML, .env
    - CodeChunker: chunk by function/class boundaries
    - DocChunker: chunk by heading
    - TextChunker: recursive splitting, overlap, size limits
    - ConfigChunker: whole-file chunking

Reference: Development Roadmap → Phase 3 → Testing
"""

import unittest

from app.core.parsing.code_parser import CodeParser, CodeParseError
from app.core.parsing.doc_parser import DocParser
from app.core.parsing.config_parser import ConfigParser, ConfigParseError
from app.core.chunking.code_chunker import CodeChunker
from app.core.chunking.doc_chunker import DocChunker
from app.core.chunking.text_chunker import TextChunker
from app.core.chunking.config_chunker import ConfigChunker


# ═══════════════════════════════════════════════════════════════════════════════
# CODE PARSER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCodeParser(unittest.TestCase):
    """Tests for CodeParser AST-based extraction."""

    def setUp(self):
        self.parser = CodeParser()

    def test_parse_function(self):
        """Single function → correct name, args, docstring."""
        source = '''
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}"
'''
        result = self.parser.parse(source.strip(), "greet.py")
        self.assertEqual(len(result.functions), 1)
        fn = result.functions[0]
        self.assertEqual(fn.name, "greet")
        self.assertIn("name: str", fn.args)
        self.assertEqual(fn.return_type, "str")
        self.assertEqual(fn.docstring, "Say hello.")

    def test_parse_class_with_methods(self):
        """Class with methods → correct structure."""
        source = '''
class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        return a + b

    def subtract(self, a: int, b: int) -> int:
        return a - b
'''
        result = self.parser.parse(source.strip(), "calc.py")
        self.assertEqual(len(result.classes), 1)
        cls = result.classes[0]
        self.assertEqual(cls.name, "Calculator")
        self.assertEqual(cls.docstring, "A simple calculator.")
        self.assertEqual(len(cls.methods), 2)
        self.assertEqual(cls.methods[0].name, "add")
        self.assertEqual(cls.methods[1].name, "subtract")
        # Methods should NOT appear as top-level functions
        self.assertEqual(len(result.functions), 0)

    def test_parse_imports(self):
        """Import and from-import statements extracted."""
        source = '''
import os
from sys import path
from typing import Optional, List
'''
        result = self.parser.parse(source.strip(), "imports.py")
        self.assertEqual(len(result.imports), 3)
        # import os
        self.assertEqual(result.imports[0].module, "os")
        self.assertFalse(result.imports[0].is_from)
        # from sys import path
        self.assertEqual(result.imports[1].module, "sys")
        self.assertTrue(result.imports[1].is_from)
        self.assertIn("path", result.imports[1].names)
        # from typing import Optional, List
        self.assertEqual(result.imports[2].module, "typing")
        self.assertIn("Optional", result.imports[2].names)
        self.assertIn("List", result.imports[2].names)

    def test_parse_syntax_error(self):
        """Syntax error → CodeParseError raised, not a crash."""
        source = "def foo(:\n    pass"
        with self.assertRaises(CodeParseError):
            self.parser.parse(source, "broken.py")

    def test_parse_empty_file(self):
        """Empty string → empty functions/classes/imports."""
        result = self.parser.parse("", "empty.py")
        self.assertEqual(len(result.functions), 0)
        self.assertEqual(len(result.classes), 0)
        self.assertEqual(len(result.imports), 0)

    def test_parse_decorators(self):
        """Decorated function → decorators extracted."""
        source = '''
@app.get("/")
@login_required
def index():
    return "home"
'''
        result = self.parser.parse(source.strip(), "views.py")
        fn = result.functions[0]
        self.assertEqual(len(fn.decorators), 2)
        self.assertIn("@app.get", fn.decorators[0])
        self.assertEqual(fn.decorators[1], "@login_required")

    def test_parse_class_with_bases(self):
        """Class with base classes → bases extracted."""
        source = '''
class Dog(Animal):
    def bark(self):
        return "woof"
'''
        result = self.parser.parse(source.strip(), "dog.py")
        cls = result.classes[0]
        self.assertEqual(cls.name, "Dog")
        self.assertIn("Animal", cls.bases)

    def test_parse_async_function(self):
        """Async function → extracted as function."""
        source = '''
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    pass
'''
        result = self.parser.parse(source.strip(), "async.py")
        self.assertEqual(len(result.functions), 1)
        self.assertEqual(result.functions[0].name, "fetch_data")


# ═══════════════════════════════════════════════════════════════════════════════
# DOC PARSER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocParser(unittest.TestCase):
    """Tests for DocParser Markdown/RST parsing."""

    def setUp(self):
        self.parser = DocParser()

    def test_parse_single_heading(self):
        """One heading with content below."""
        source = "# Title\n\nSome content here."
        sections = self.parser.parse_markdown(source, "README.md")
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].heading, "Title")
        self.assertEqual(sections[0].level, 1)
        self.assertIn("Some content", sections[0].content)

    def test_parse_nested_headings(self):
        """Multiple heading levels."""
        source = "# Title\n\nIntro\n\n## Section 1\n\nContent 1\n\n### Subsection\n\nContent 2"
        sections = self.parser.parse_markdown(source, "README.md")
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0].level, 1)
        self.assertEqual(sections[1].level, 2)
        self.assertEqual(sections[2].level, 3)

    def test_parse_no_headings(self):
        """Plain text with no headings → single section."""
        source = "Just some plain text\nwith no headings."
        sections = self.parser.parse_markdown(source, "notes.txt")
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].heading, "")
        self.assertEqual(sections[0].level, 0)
        self.assertIn("plain text", sections[0].content)

    def test_parse_empty(self):
        """Empty string → empty list."""
        sections = self.parser.parse_markdown("", "empty.md")
        self.assertEqual(len(sections), 0)

    def test_parse_code_blocks(self):
        """Headings inside fenced code blocks should be ignored."""
        source = "# Real Heading\n\nSome text\n\n```python\n# This is a comment, not a heading\ndef foo():\n    pass\n```\n\n## Another Heading\n\nMore text"
        sections = self.parser.parse_markdown(source, "README.md")
        # Should be 2 sections (Real Heading and Another Heading), not 3
        headings = [s.heading for s in sections]
        self.assertIn("Real Heading", headings)
        self.assertIn("Another Heading", headings)
        self.assertNotIn("This is a comment, not a heading", headings)

    def test_parse_heading_line_numbers(self):
        """Line numbers should be tracked correctly."""
        source = "# First\n\nLine 2\nLine 3\n\n## Second\n\nLine 7"
        sections = self.parser.parse_markdown(source, "doc.md")
        self.assertEqual(sections[0].start_line, 1)
        self.assertEqual(sections[1].heading, "Second")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG PARSER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigParser(unittest.TestCase):
    """Tests for ConfigParser JSON/YAML/TOML/.env parsing."""

    def setUp(self):
        self.parser = ConfigParser()

    def test_parse_json(self):
        """Valid JSON → dict."""
        source = '{"name": "repomind", "version": "1.0"}'
        result = self.parser.parse(source, "config.json", "json")
        self.assertEqual(result["name"], "repomind")
        self.assertEqual(result["version"], "1.0")

    def test_parse_json_invalid(self):
        """Invalid JSON → ConfigParseError."""
        with self.assertRaises(ConfigParseError):
            self.parser.parse("{invalid json}", "bad.json", "json")

    def test_parse_yaml(self):
        """Valid YAML → dict."""
        source = "name: repomind\nversion: '1.0'"
        result = self.parser.parse(source, "config.yaml", "yaml")
        self.assertEqual(result["name"], "repomind")

    def test_parse_toml(self):
        """Valid TOML → dict."""
        source = '[project]\nname = "repomind"\nversion = "1.0"'
        result = self.parser.parse(source, "pyproject.toml", "toml")
        self.assertIn("project", result)
        self.assertEqual(result["project"]["name"], "repomind")

    def test_parse_env(self):
        """.env KEY=VALUE → dict."""
        source = 'DATABASE_URL=postgres://localhost\nSECRET_KEY="my-secret"\n# comment\nexport API_KEY=abc123'
        result = self.parser.parse(source, ".env", "env")
        self.assertEqual(result["DATABASE_URL"], "postgres://localhost")
        self.assertEqual(result["SECRET_KEY"], "my-secret")
        self.assertEqual(result["API_KEY"], "abc123")
        self.assertNotIn("#", result)

    def test_parse_empty(self):
        """Empty config → empty dict."""
        result = self.parser.parse("", "empty.json", "json")
        self.assertEqual(result, {})

    def test_parse_unsupported_format(self):
        """Unsupported format → ConfigParseError."""
        with self.assertRaises(ConfigParseError):
            self.parser.parse("data", "file.xyz", "xyz")


# ═══════════════════════════════════════════════════════════════════════════════
# CODE CHUNKER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCodeChunker(unittest.TestCase):
    """Tests for CodeChunker AST-aware chunking."""

    def setUp(self):
        self.parser = CodeParser()
        self.chunker = CodeChunker()

    def _parse_and_chunk(self, source: str, file_path: str = "test.py"):
        parsed = self.parser.parse(source, file_path)
        return self.chunker.chunk(
            source, file_path, "python",
            metadata={"parsed_code": parsed}
        )

    def test_chunk_single_function(self):
        """One function → function chunk + module-level chunk."""
        source = "import os\n\ndef greet():\n    return 'hello'"
        chunks = self._parse_and_chunk(source)
        # Should have at least a function chunk
        code_chunks = [c for c in chunks if c.parent_symbol == "greet"]
        self.assertEqual(len(code_chunks), 1)

    def test_chunk_preserves_body(self):
        """Chunk text should contain the complete function source."""
        source = 'def add(a, b):\n    """Add two numbers."""\n    return a + b'
        chunks = self._parse_and_chunk(source)
        fn_chunks = [c for c in chunks if c.parent_symbol == "add"]
        self.assertEqual(len(fn_chunks), 1)
        self.assertIn("def add", fn_chunks[0].text)
        self.assertIn("return a + b", fn_chunks[0].text)

    def test_chunk_class_with_methods(self):
        """Class with methods → one class chunk."""
        source = 'class Calc:\n    def add(self):\n        pass\n    def sub(self):\n        pass'
        chunks = self._parse_and_chunk(source)
        class_chunks = [c for c in chunks if c.parent_symbol == "Calc"]
        self.assertEqual(len(class_chunks), 1)
        self.assertIn("class Calc", class_chunks[0].text)

    def test_chunk_preserves_metadata(self):
        """Chunk metadata should have parent_symbol = function name."""
        source = "def foo():\n    pass"
        chunks = self._parse_and_chunk(source)
        fn_chunks = [c for c in chunks if c.parent_symbol == "foo"]
        self.assertEqual(len(fn_chunks), 1)
        self.assertEqual(fn_chunks[0].chunk_type, "code")
        self.assertEqual(fn_chunks[0].language, "python")

    def test_chunk_empty_file(self):
        """Empty file → 0 chunks."""
        chunks = self._parse_and_chunk("")
        self.assertEqual(len(chunks), 0)

    def test_chunk_only_imports(self):
        """File with only imports → module-level chunk."""
        source = "import os\nimport sys\nfrom pathlib import Path"
        chunks = self._parse_and_chunk(source)
        self.assertTrue(len(chunks) >= 1)
        module_chunks = [c for c in chunks if c.parent_symbol == "<module>"]
        self.assertEqual(len(module_chunks), 1)


# ═══════════════════════════════════════════════════════════════════════════════
# DOC CHUNKER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocChunker(unittest.TestCase):
    """Tests for DocChunker heading-based chunking."""

    def setUp(self):
        self.doc_parser = DocParser()
        self.chunker = DocChunker()

    def _parse_and_chunk(self, source: str, file_path: str = "README.md"):
        sections = self.doc_parser.parse_markdown(source, file_path)
        return self.chunker.chunk(
            source, file_path, "markdown",
            metadata={"sections": sections}
        )

    def test_doc_chunk_by_heading(self):
        """3 headings → 3 chunks."""
        source = "# Title\n\nIntro\n\n## Install\n\nRun pip...\n\n## Usage\n\nImport and..."
        chunks = self._parse_and_chunk(source)
        self.assertEqual(len(chunks), 3)

    def test_doc_chunk_includes_heading(self):
        """Chunk text should include the heading for context."""
        source = "## Installation\n\nRun pip install repomind"
        chunks = self._parse_and_chunk(source)
        self.assertEqual(len(chunks), 1)
        self.assertIn("Installation", chunks[0].text)
        self.assertIn("pip install", chunks[0].text)

    def test_doc_chunk_empty(self):
        """Empty doc → 0 chunks."""
        chunks = self._parse_and_chunk("")
        self.assertEqual(len(chunks), 0)

    def test_doc_chunk_metadata(self):
        """Chunk should have chunk_type='documentation'."""
        source = "# Title\n\nContent"
        chunks = self._parse_and_chunk(source)
        self.assertEqual(chunks[0].chunk_type, "documentation")
        self.assertEqual(chunks[0].language, "markdown")


# ═══════════════════════════════════════════════════════════════════════════════
# TEXT CHUNKER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTextChunker(unittest.TestCase):
    """Tests for TextChunker recursive splitting."""

    def setUp(self):
        self.chunker = TextChunker(chunk_size=100, chunk_overlap=20)

    def test_text_chunk_short_content(self):
        """Content shorter than chunk_size → 1 chunk."""
        chunks = self.chunker.chunk("Short text.", "notes.txt", "text")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "Short text.")

    def test_text_chunk_respects_size(self):
        """No chunk should exceed chunk_size (plus overlap)."""
        long_text = "This is a sentence. " * 50  # ~1000 chars
        chunks = self.chunker.chunk(long_text, "notes.txt", "text")
        self.assertTrue(len(chunks) > 1)
        # Each chunk (minus potential overlap) should be reasonable
        for chunk in chunks:
            # Allow some tolerance for overlap
            self.assertLessEqual(
                len(chunk.text),
                self.chunker.chunk_size + self.chunker.chunk_overlap + 50
            )

    def test_text_chunk_overlap(self):
        """Adjacent chunks should share overlap characters."""
        long_text = "Word " * 100  # ~500 chars
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk(long_text, "notes.txt", "text")
        if len(chunks) >= 2:
            # The end of chunk 0 should appear at the start of chunk 1
            end_of_first = chunks[0].text[-20:]
            self.assertIn(end_of_first, chunks[1].text)

    def test_text_chunk_overlap_validation(self):
        """Overlap >= chunk_size → ValueError."""
        with self.assertRaises(ValueError):
            TextChunker(chunk_size=100, chunk_overlap=100)
        with self.assertRaises(ValueError):
            TextChunker(chunk_size=100, chunk_overlap=200)

    def test_text_chunk_empty(self):
        """Empty content → 0 chunks."""
        chunks = self.chunker.chunk("", "notes.txt", "text")
        self.assertEqual(len(chunks), 0)

    def test_text_chunk_metadata(self):
        """Chunk type should be 'text'."""
        chunks = self.chunker.chunk("Some text.", "notes.txt", "text")
        self.assertEqual(chunks[0].chunk_type, "text")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG CHUNKER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigChunker(unittest.TestCase):
    """Tests for ConfigChunker whole-file chunking."""

    def setUp(self):
        self.chunker = ConfigChunker()

    def test_config_chunk_whole_file(self):
        """Entire config file → 1 chunk."""
        source = '{"name": "repomind", "version": "1.0"}'
        chunks = self.chunker.chunk(source, "config.json", "json")
        self.assertEqual(len(chunks), 1)
        self.assertIn("repomind", chunks[0].text)

    def test_config_chunk_empty(self):
        """Empty config → 0 chunks."""
        chunks = self.chunker.chunk("", "config.json", "json")
        self.assertEqual(len(chunks), 0)

    def test_config_chunk_metadata(self):
        """Chunk should have chunk_type='config'."""
        source = "key: value"
        chunks = self.chunker.chunk(source, "config.yaml", "yaml")
        self.assertEqual(chunks[0].chunk_type, "config")
        self.assertEqual(chunks[0].language, "yaml")

    def test_config_chunk_preserves_content(self):
        """Chunk text should be the entire file content."""
        source = "[project]\nname = 'repomind'\nversion = '1.0'"
        chunks = self.chunker.chunk(source, "pyproject.toml", "toml")
        self.assertEqual(len(chunks), 1)
        self.assertIn("[project]", chunks[0].text)
        self.assertIn("repomind", chunks[0].text)


if __name__ == "__main__":
    unittest.main()
