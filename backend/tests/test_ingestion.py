"""
RepoMind — Unit Tests for Ingestion Module

Tests for:
    - FileScanner: classify_file, is_binary, scan
    - FileReader: read (UTF-8, Latin-1 fallback)
    - RepoLoader: URL validation, clone error handling

Reference: Development Roadmap → Phase 2 → Testing
"""

import os
import tempfile
import shutil
import unittest

from app.core.ingestion.file_scanner import FileScanner
from app.core.ingestion.file_reader import FileReader, FileReadError
from app.core.ingestion.repo_loader import RepoLoader, RepoCloneError


class TestFileScanner(unittest.TestCase):
    """Tests for FileScanner classification, binary detection, and directory scanning."""

    def setUp(self):
        self.scanner = FileScanner()
        # Create a temp directory with test files
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ─── classify_file tests ───

    def test_classify_python(self):
        """Python files should be classified as code/python."""
        file_type, language = self.scanner.classify_file("app/main.py")
        self.assertEqual(file_type, "code")
        self.assertEqual(language, "python")

    def test_classify_javascript(self):
        """JavaScript files should be classified as code/javascript."""
        file_type, language = self.scanner.classify_file("src/index.js")
        self.assertEqual(file_type, "code")
        self.assertEqual(language, "javascript")

    def test_classify_typescript(self):
        """TypeScript files should be classified as code/typescript."""
        file_type, language = self.scanner.classify_file("src/App.tsx")
        self.assertEqual(file_type, "code")
        self.assertEqual(language, "typescript")

    def test_classify_markdown(self):
        """Markdown files should be classified as documentation/markdown."""
        file_type, language = self.scanner.classify_file("README.md")
        self.assertEqual(file_type, "documentation")
        self.assertEqual(language, "markdown")

    def test_classify_yaml(self):
        """YAML files should be classified as config/yaml."""
        file_type, language = self.scanner.classify_file("docker-compose.yml")
        self.assertEqual(file_type, "config")
        self.assertEqual(language, "yaml")

    def test_classify_json(self):
        """JSON files should be classified as config/json."""
        file_type, language = self.scanner.classify_file("package.json")
        self.assertEqual(file_type, "config")
        self.assertEqual(language, "json")

    def test_classify_toml(self):
        """TOML files should be classified as config/toml."""
        file_type, language = self.scanner.classify_file("pyproject.toml")
        self.assertEqual(file_type, "config")
        self.assertEqual(language, "toml")

    def test_classify_dockerfile(self):
        """Dockerfile should be classified as config/dockerfile."""
        file_type, language = self.scanner.classify_file("Dockerfile")
        self.assertEqual(file_type, "config")
        self.assertEqual(language, "dockerfile")

    def test_classify_unknown(self):
        """Unknown extensions should be classified as other/unknown."""
        file_type, language = self.scanner.classify_file("data.xyz")
        self.assertEqual(file_type, "other")
        self.assertEqual(language, "unknown")

    # ─── is_binary tests ───

    def test_is_binary_text_file(self):
        """Text files should NOT be detected as binary."""
        text_file = os.path.join(self.test_dir, "test.py")
        with open(text_file, "w") as f:
            f.write("import os\nprint('hello')\n")
        self.assertFalse(self.scanner.is_binary(text_file))

    def test_is_binary_png(self):
        """Files with null bytes (like PNG) should be detected as binary."""
        binary_file = os.path.join(self.test_dir, "image.png")
        with open(binary_file, "wb") as f:
            # PNG magic bytes: \x89PNG\r\n\x1a\n
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        self.assertTrue(self.scanner.is_binary(binary_file))

    def test_is_binary_empty_file(self):
        """Empty files should NOT be binary (no null bytes)."""
        empty_file = os.path.join(self.test_dir, "empty.txt")
        with open(empty_file, "w") as f:
            pass
        self.assertFalse(self.scanner.is_binary(empty_file))

    # ─── scan tests ───

    def test_scan_basic_directory(self):
        """Scan should find and classify files correctly."""
        # Create test files
        with open(os.path.join(self.test_dir, "main.py"), "w") as f:
            f.write("print('hello')")
        with open(os.path.join(self.test_dir, "README.md"), "w") as f:
            f.write("# Hello")
        with open(os.path.join(self.test_dir, "config.yaml"), "w") as f:
            f.write("key: value")

        files = self.scanner.scan(self.test_dir)
        self.assertEqual(len(files), 3)

        # Check that files are sorted by path
        paths = [f.path for f in files]
        self.assertEqual(paths, sorted(paths))

    def test_scan_skips_git_dir(self):
        """Scan should skip .git/ directory."""
        os.makedirs(os.path.join(self.test_dir, ".git", "objects"))
        with open(os.path.join(self.test_dir, ".git", "HEAD"), "w") as f:
            f.write("ref: refs/heads/main")
        with open(os.path.join(self.test_dir, "main.py"), "w") as f:
            f.write("print('hello')")

        files = self.scanner.scan(self.test_dir)
        paths = [f.path for f in files]
        self.assertNotIn(".git/HEAD", paths)
        self.assertIn("main.py", paths)

    def test_scan_skips_node_modules(self):
        """Scan should skip node_modules/ directory."""
        os.makedirs(os.path.join(self.test_dir, "node_modules", "express"))
        with open(
            os.path.join(self.test_dir, "node_modules", "express", "index.js"), "w"
        ) as f:
            f.write("module.exports = {}")
        with open(os.path.join(self.test_dir, "app.js"), "w") as f:
            f.write("const express = require('express')")

        files = self.scanner.scan(self.test_dir)
        paths = [f.path for f in files]
        self.assertEqual(len(files), 1)
        self.assertIn("app.js", paths)

    def test_scan_skips_binary_files(self):
        """Scan should skip binary files (files containing null bytes)."""
        with open(os.path.join(self.test_dir, "code.py"), "w") as f:
            f.write("import os")
        with open(os.path.join(self.test_dir, "image.png"), "wb") as f:
            f.write(b"\x89PNG\x00\x00" + b"\x00" * 50)

        files = self.scanner.scan(self.test_dir)
        paths = [f.path for f in files]
        self.assertIn("code.py", paths)
        self.assertNotIn("image.png", paths)

    def test_scan_skips_large_files(self):
        """Scan should skip files larger than MAX_FILE_SIZE (1MB)."""
        # Create a small file (should be included)
        with open(os.path.join(self.test_dir, "small.py"), "w") as f:
            f.write("x = 1")

        # Create a large file (should be skipped)
        with open(os.path.join(self.test_dir, "large.py"), "w") as f:
            f.write("x = 1\n" * 200_000)  # ~1.2MB

        files = self.scanner.scan(self.test_dir)
        paths = [f.path for f in files]
        self.assertIn("small.py", paths)
        self.assertNotIn("large.py", paths)

    def test_scan_skips_empty_files(self):
        """Scan should skip empty files (0 bytes)."""
        with open(os.path.join(self.test_dir, "empty.py"), "w") as f:
            pass  # 0 bytes
        with open(os.path.join(self.test_dir, "real.py"), "w") as f:
            f.write("x = 1")

        files = self.scanner.scan(self.test_dir)
        paths = [f.path for f in files]
        self.assertNotIn("empty.py", paths)
        self.assertIn("real.py", paths)

    def test_scan_nonexistent_directory(self):
        """Scan should raise FileNotFoundError for nonexistent dirs."""
        with self.assertRaises(FileNotFoundError):
            self.scanner.scan("/nonexistent/directory")


class TestFileReader(unittest.TestCase):
    """Tests for FileReader encoding detection and fallback."""

    def setUp(self):
        self.reader = FileReader()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_read_utf8(self):
        """Should read UTF-8 files correctly."""
        file_path = os.path.join(self.test_dir, "utf8.py")
        content = "# This is UTF-8: Hello, World! 🚀\nprint('hello')\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        result = self.reader.read(file_path)
        self.assertEqual(result, content)

    def test_read_latin1_fallback(self):
        """Should fall back to Latin-1 when UTF-8 fails."""
        file_path = os.path.join(self.test_dir, "latin1.txt")
        # Write bytes that are valid Latin-1 but invalid UTF-8
        with open(file_path, "wb") as f:
            f.write(b"R\xe9sum\xe9 of the project\n")

        result = self.reader.read(file_path)
        self.assertIn("sum", result)  # At least the ASCII parts should be there

    def test_read_nonexistent_file(self):
        """Should raise FileReadError for nonexistent files."""
        with self.assertRaises((FileReadError, FileNotFoundError)):
            self.reader.read("/nonexistent/file.py")

    def test_read_safe_returns_none_on_error(self):
        """read_safe should return None instead of raising."""
        result = self.reader.read_safe("/nonexistent/file.py")
        self.assertIsNone(result)

    def test_read_safe_returns_content(self):
        """read_safe should return content for valid files."""
        file_path = os.path.join(self.test_dir, "good.py")
        with open(file_path, "w") as f:
            f.write("x = 1")

        result = self.reader.read_safe(file_path)
        self.assertEqual(result, "x = 1")


class TestRepoLoader(unittest.TestCase):
    """Tests for RepoLoader URL validation and error handling."""

    def setUp(self):
        self.loader = RepoLoader()

    def test_validate_valid_github_url(self):
        """Valid GitHub URLs should pass validation."""
        self.assertTrue(
            self.loader._validate_github_url("https://github.com/pallets/flask")
        )

    def test_validate_github_url_with_git_suffix(self):
        """GitHub URLs with .git suffix should pass."""
        self.assertTrue(
            self.loader._validate_github_url("https://github.com/pallets/flask.git")
        )

    def test_validate_invalid_url_http(self):
        """HTTP (not HTTPS) should be rejected."""
        self.assertFalse(
            self.loader._validate_github_url("http://github.com/pallets/flask")
        )

    def test_validate_invalid_url_gitlab(self):
        """Non-GitHub URLs should be rejected."""
        self.assertFalse(
            self.loader._validate_github_url("https://gitlab.com/owner/repo")
        )

    def test_validate_invalid_url_ssrf(self):
        """Cloud metadata URLs (SSRF) should be rejected."""
        self.assertFalse(
            self.loader._validate_github_url("http://169.254.169.254/metadata")
        )

    def test_validate_invalid_url_internal(self):
        """Internal network URLs should be rejected."""
        self.assertFalse(
            self.loader._validate_github_url("http://internal-service:8080/admin")
        )

    def test_clone_invalid_url_raises(self):
        """Cloning with an invalid URL should raise RepoCloneError."""
        with self.assertRaises(RepoCloneError):
            self.loader.clone("https://gitlab.com/owner/repo")


if __name__ == "__main__":
    unittest.main()
