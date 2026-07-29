"""
RepoMind — File Scanner Module

Walks a directory tree, classifies files by type and language,
filters out irrelevant files (binaries, ignored directories, large files).

This is Stage 3 (File Discovery) of the RAG pipeline.

Input:  Directory path (cloned repo root)
Output: Sorted list of FileInfo objects

Classification logic:
    .py           → ("code", "python")
    .js/.ts       → ("code", "javascript"/"typescript")
    .md           → ("documentation", "markdown")
    .json/.yaml   → ("config", "json"/"yaml")
    Other text    → ("other", "unknown")

Skips:
    - Ignored directories (.git, node_modules, __pycache__, venv, etc.)
    - Binary files (detected by null-byte scanning)
    - Files larger than MAX_FILE_SIZE (default 1MB)

Reference:
    - Module Design → Section 1 (core/ingestion/file_scanner.py)
    - RAG Workflow → Stage 3 (File Discovery)
"""

import os
from pathlib import Path

from app.models.schemas import FileInfo


class FileScanner:
    """
    Walk a directory tree and return classified file information.

    Why not use glob or pathlib.rglob?
        os.walk() gives us control over which directories to skip
        BEFORE descending into them. With rglob, we'd visit every file
        in node_modules before filtering — wasting time on 50K+ files.

    Usage:
        scanner = FileScanner()
        files = scanner.scan("/tmp/repos/rp_abc123")
    """

    # Directories to skip entirely during scanning.
    # These contain third-party code, build artifacts, or version control data
    # that are irrelevant to understanding the project's own codebase.
    IGNORED_DIRS: set[str] = {
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "venv",
        ".venv",
        "env",
        ".env",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",          # Rust, Java
        ".tox",
        ".eggs",
        "*.egg-info",
        ".idea",
        ".vscode",
        ".DS_Store",
        "coverage",
        ".coverage",
        "htmlcov",
        ".terraform",
        "vendor",          # Go, PHP
        "bower_components",
    }

    # Maximum file size in bytes (1MB). Files larger than this are skipped.
    # Why 1MB? Most source code files are under 100KB. A 1MB file is likely
    # a data file, minified bundle, or generated code — not useful for Q&A.
    MAX_FILE_SIZE: int = 1_048_576  # 1MB

    # ─── File Classification Map ───
    # Maps file extension to (file_type, language) tuple.
    # This is the single source of truth for classification.
    EXTENSION_MAP: dict[str, tuple[str, str]] = {
        # Code files
        ".py": ("code", "python"),
        ".js": ("code", "javascript"),
        ".jsx": ("code", "javascript"),
        ".ts": ("code", "typescript"),
        ".tsx": ("code", "typescript"),
        ".java": ("code", "java"),
        ".go": ("code", "go"),
        ".rs": ("code", "rust"),
        ".cpp": ("code", "cpp"),
        ".c": ("code", "c"),
        ".h": ("code", "c"),
        ".hpp": ("code", "cpp"),
        ".cs": ("code", "csharp"),
        ".rb": ("code", "ruby"),
        ".php": ("code", "php"),
        ".swift": ("code", "swift"),
        ".kt": ("code", "kotlin"),
        ".scala": ("code", "scala"),
        ".r": ("code", "r"),
        ".R": ("code", "r"),
        ".sh": ("code", "shell"),
        ".bash": ("code", "shell"),
        ".zsh": ("code", "shell"),
        ".sql": ("code", "sql"),
        ".dart": ("code", "dart"),
        ".lua": ("code", "lua"),
        ".pl": ("code", "perl"),
        ".ex": ("code", "elixir"),
        ".exs": ("code", "elixir"),
        ".erl": ("code", "erlang"),
        ".hs": ("code", "haskell"),
        ".vue": ("code", "vue"),
        ".svelte": ("code", "svelte"),
        # Documentation files
        ".md": ("documentation", "markdown"),
        ".mdx": ("documentation", "markdown"),
        ".rst": ("documentation", "restructuredtext"),
        ".txt": ("documentation", "text"),
        ".adoc": ("documentation", "asciidoc"),
        # Config files
        ".json": ("config", "json"),
        ".yaml": ("config", "yaml"),
        ".yml": ("config", "yaml"),
        ".toml": ("config", "toml"),
        ".ini": ("config", "ini"),
        ".cfg": ("config", "ini"),
        ".conf": ("config", "conf"),
        ".env": ("config", "env"),
        ".env.example": ("config", "env"),
        ".env.local": ("config", "env"),
        ".xml": ("config", "xml"),
        ".properties": ("config", "properties"),
    }

    # Files without extensions that we can classify by name
    FILENAME_MAP: dict[str, tuple[str, str]] = {
        "Dockerfile": ("config", "dockerfile"),
        "docker-compose.yml": ("config", "yaml"),
        "docker-compose.yaml": ("config", "yaml"),
        "Makefile": ("config", "makefile"),
        "Procfile": ("config", "procfile"),
        "Vagrantfile": ("config", "ruby"),
        ".gitignore": ("config", "gitignore"),
        ".dockerignore": ("config", "dockerignore"),
        ".editorconfig": ("config", "editorconfig"),
        "LICENSE": ("documentation", "text"),
        "CHANGELOG": ("documentation", "markdown"),
        "CHANGELOG.md": ("documentation", "markdown"),
        "CONTRIBUTING.md": ("documentation", "markdown"),
        "README": ("documentation", "text"),
    }

    def scan(self, directory: str) -> list[FileInfo]:
        """
        Walk directory tree and return classified file list.

        Skips:
        - Ignored directories (node_modules, .git, __pycache__, etc.)
        - Binary files (detected by null-byte scanning in first 8KB)
        - Files larger than MAX_FILE_SIZE (1MB)

        Args:
            directory: Absolute path to the root directory to scan

        Returns:
            Sorted list of FileInfo objects (sorted by relative file path)

        Raises:
            FileNotFoundError: If directory does not exist
        """
        if not os.path.isdir(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")

        files: list[FileInfo] = []

        for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
            # ─── Filter ignored directories IN-PLACE ───
            # Modifying dirnames in-place tells os.walk() to skip those
            # subdirectories entirely. This is the idiomatic way to prune
            # the walk — without this, os.walk would descend into every
            # directory first and we'd have to filter after.
            dirnames[:] = [
                d for d in dirnames
                if d not in self.IGNORED_DIRS and not d.startswith(".")
            ]

            for filename in filenames:
                # Skip hidden files (dotfiles like .gitattributes)
                # But keep known dotfiles like .env, .gitignore
                if filename.startswith(".") and filename not in self.FILENAME_MAP:
                    if not any(filename.endswith(ext) for ext in [".env", ".env.example"]):
                        continue

                file_path = os.path.join(dirpath, filename)

                # ─── Size check ───
                try:
                    size = os.path.getsize(file_path)
                except OSError:
                    continue  # Permission denied or broken symlink

                if size > self.MAX_FILE_SIZE:
                    continue  # Skip large files (likely data/generated)

                if size == 0:
                    continue  # Skip empty files

                # ─── Binary check ───
                if self.is_binary(file_path):
                    continue

                # ─── Classify ───
                file_type, language = self.classify_file(file_path)

                # ─── Build relative path ───
                rel_path = os.path.relpath(file_path, directory)

                files.append(
                    FileInfo(
                        path=rel_path,
                        absolute_path=file_path,
                        file_type=file_type,
                        language=language,
                        size_bytes=size,
                    )
                )

        # Sort by relative path for deterministic output
        files.sort(key=lambda f: f.path)

        return files

    def classify_file(self, file_path: str) -> tuple[str, str]:
        """
        Classify a single file by its extension or filename.

        Returns:
            (file_type, language) tuple.
            Examples:
                ("code", "python") for .py files
                ("documentation", "markdown") for .md files
                ("other", "unknown") for unrecognized extensions
        """
        filename = os.path.basename(file_path)

        # Check filename first (handles Dockerfile, Makefile, etc.)
        if filename in self.FILENAME_MAP:
            return self.FILENAME_MAP[filename]

        # Check extension
        ext = Path(file_path).suffix.lower()
        if ext in self.EXTENSION_MAP:
            return self.EXTENSION_MAP[ext]

        # Unknown extension — treat as "other"
        return ("other", "unknown")

    def is_binary(self, file_path: str) -> bool:
        """
        Check if a file is binary by scanning the first 8KB for null bytes.

        Why 8KB? Enough to detect binary headers (PNG starts with \\x89PNG,
        JPEG with \\xff\\xd8, ELF with \\x7fELF). Text files never contain
        null bytes (\\x00), so one null byte = binary file.

        Args:
            file_path: Absolute path to the file

        Returns:
            True if file appears to be binary, False if text
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
            return b"\x00" in chunk
        except (OSError, IOError):
            # If we can't read the file, treat it as binary (skip it)
            return True
