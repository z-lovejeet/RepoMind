"""
RepoMind — File Reader Module

Reads file contents with encoding detection and fallback strategy.

Encoding Strategy:
    1. Try UTF-8 (most common encoding for source code)
    2. Fall back to Latin-1 (ISO-8859-1) — maps every byte to a character,
       so it NEVER throws a decoding error (may produce garbled text for
       non-Latin scripts, but at least produces *something*)

Why not use chardet/charset-normalizer for auto-detection?
    - Adds a dependency for a problem that rarely occurs
    - UTF-8 handles 99%+ of source code files
    - Latin-1 handles the remaining 1% (old Windows files, legacy code)
    - chardet can be SLOW (it reads the entire file to guess encoding)
    - For the rare Shift-JIS or UTF-16 file, skipping is acceptable

Reference:
    - Module Design → Section 1 (core/ingestion/file_reader.py)
    - RAG Workflow → Stage 3 (File Discovery)
"""


class FileReadError(Exception):
    """Raised when a file cannot be read after all encoding attempts."""
    pass


class FileReader:
    """
    Read file contents with smart encoding fallback.

    Usage:
        reader = FileReader()
        content = reader.read("/path/to/file.py")
    """

    # Encodings to try, in order of preference
    ENCODINGS: list[str] = ["utf-8", "latin-1"]

    def read(self, file_path: str) -> str:
        """
        Read file contents with encoding detection.

        Strategy:
            1. Try UTF-8 (most common encoding for source code)
            2. Fall back to Latin-1 (never fails — maps every byte to a char)

        Args:
            file_path: Absolute path to the file to read

        Returns:
            File contents as a string

        Raises:
            FileReadError: If file cannot be read after all encoding attempts
                (should never happen with Latin-1 fallback, but just in case)
            FileNotFoundError: If file does not exist
        """
        for encoding in self.ENCODINGS:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                # This encoding failed — try the next one
                continue
            except (OSError, IOError) as e:
                # File system error — no point trying other encodings
                raise FileReadError(
                    f"Cannot read file {file_path}: {e}"
                ) from e

        # If we get here, all encodings failed (shouldn't happen with latin-1)
        raise FileReadError(
            f"Cannot decode file {file_path} with any supported encoding: "
            f"{self.ENCODINGS}"
        )

    def read_safe(self, file_path: str) -> str | None:
        """
        Read file contents, returning None on any error.

        Useful in pipelines where we want to skip bad files
        rather than crash the entire ingestion.

        Args:
            file_path: Absolute path to the file

        Returns:
            File contents as a string, or None if reading failed
        """
        try:
            return self.read(file_path)
        except (FileReadError, FileNotFoundError):
            return None
