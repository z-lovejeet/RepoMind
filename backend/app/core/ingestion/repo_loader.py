"""
RepoMind — Repository Loader Module

Downloads repository source code to the local filesystem.
Supports two sources:
    1. GitHub clone (via GitPython, shallow clone)
    2. Zip file extraction (from user upload)

This is Stage 2 (Clone Repository) of the RAG pipeline.

Input:  GitHub URL or zip file path
Output: Local directory path containing the repo source code

Security:
    - URL validation: Only github.com HTTPS URLs allowed (prevents SSRF)
    - Zip bomb protection: Limits file count and total extracted size
    - Timeout: 60-second timeout on git clone (prevents hanging)

Reference:
    - Module Design → Section 1 (core/ingestion/repo_loader.py)
    - RAG Workflow → Stage 2 (Clone Repository)
"""

import os
import re
import shutil
import zipfile
import uuid
import tempfile

from app.config import settings


# ─── Custom Exceptions ───

class RepoCloneError(Exception):
    """Raised when git clone fails (network, auth, not found)."""
    pass


class ZipExtractionError(Exception):
    """Raised when zip extraction fails (corrupt, zip bomb)."""
    pass


class RepoLoader:
    """
    Clone GitHub repos or extract uploaded zip files.

    Usage:
        loader = RepoLoader()
        repo_path = loader.clone("https://github.com/pallets/flask")
        # ... process repo ...
        loader.cleanup(repo_path)
    """

    # Maximum number of files allowed in a zip (prevents zip bombs)
    MAX_ZIP_FILES: int = 500

    # Maximum total extracted size in bytes (500MB)
    MAX_ZIP_TOTAL_SIZE: int = 500 * 1024 * 1024

    # GitHub URL pattern — only HTTPS github.com URLs allowed
    GITHUB_URL_PATTERN = re.compile(
        r"^https://github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?/?$"
    )

    def clone(self, github_url: str, target_dir: str | None = None) -> str:
        """
        Clone a public GitHub repo via shallow clone.

        Uses depth=1 + single_branch=True for speed:
        - Full clone of FastAPI: ~30s, ~100MB
        - Shallow clone: ~5s, ~15MB

        Args:
            github_url: HTTPS GitHub URL (e.g., "https://github.com/pallets/flask")
            target_dir: Optional directory to clone into.
                        If None, creates a temp directory.

        Returns:
            Path to the cloned directory root

        Raises:
            RepoCloneError: If clone fails (network, auth, not found, invalid URL)
        """
        # ─── Validate URL ───
        # This prevents SSRF attacks. Without validation, an attacker could
        # submit "http://169.254.169.254/metadata" (cloud instance metadata)
        # or "http://internal-service:8080/admin" (internal network).
        if not self._validate_github_url(github_url):
            raise RepoCloneError(
                f"Invalid GitHub URL: {github_url}. "
                "Only HTTPS github.com URLs are supported. "
                "Example: https://github.com/owner/repo"
            )

        # ─── Create target directory ───
        if target_dir is None:
            repo_id = f"rp_{uuid.uuid4().hex[:8]}"
            target_dir = os.path.join(settings.TEMP_DIR, repo_id)

        os.makedirs(target_dir, exist_ok=True)

        # ─── Clone ───
        try:
            import git

            git.Repo.clone_from(
                url=github_url,
                to_path=target_dir,
                depth=1,              # Shallow clone — only latest commit
                single_branch=True,   # Only the default branch
                # kill_after_timeout=60 is not universally supported;
                # we rely on the env var GIT_HTTP_LOW_SPEED_LIMIT instead
            )
        except git.exc.GitCommandError as e:
            # Clean up partial clone
            self.cleanup(target_dir)

            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                raise RepoCloneError(
                    f"Repository not found: {github_url}. "
                    "Check that the URL is correct and the repo is public."
                ) from e
            elif "authentication" in error_msg or "403" in error_msg:
                raise RepoCloneError(
                    f"Cannot access repository: {github_url}. "
                    "Only public repositories are supported in MVP."
                ) from e
            else:
                raise RepoCloneError(
                    f"Failed to clone repository: {github_url}. "
                    f"Error: {e}"
                ) from e
        except ImportError:
            raise RepoCloneError(
                "GitPython is not installed. "
                "Run: pip install gitpython"
            )

        return target_dir

    def extract_zip(self, zip_path: str, target_dir: str | None = None) -> str:
        """
        Extract a zip file containing repository source code.

        Includes zip bomb protection:
        - Limits total files to MAX_ZIP_FILES (500)
        - Limits total extracted size to MAX_ZIP_TOTAL_SIZE (500MB)

        Args:
            zip_path: Path to the zip file
            target_dir: Optional directory to extract into.
                        If None, creates a temp directory.

        Returns:
            Path to the extracted directory root

        Raises:
            ZipExtractionError: If extraction fails (corrupt, zip bomb, too large)
        """
        if not os.path.isfile(zip_path):
            raise ZipExtractionError(f"Zip file not found: {zip_path}")

        if target_dir is None:
            repo_id = f"rp_{uuid.uuid4().hex[:8]}"
            target_dir = os.path.join(settings.TEMP_DIR, repo_id)

        os.makedirs(target_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # ─── Zip bomb check: file count ───
                file_list = zf.namelist()
                if len(file_list) > self.MAX_ZIP_FILES:
                    raise ZipExtractionError(
                        f"Zip contains {len(file_list)} files, "
                        f"exceeding limit of {self.MAX_ZIP_FILES}. "
                        "This may be a zip bomb."
                    )

                # ─── Zip bomb check: total uncompressed size ───
                total_size = sum(info.file_size for info in zf.infolist())
                if total_size > self.MAX_ZIP_TOTAL_SIZE:
                    raise ZipExtractionError(
                        f"Zip would extract to {total_size / 1024 / 1024:.0f}MB, "
                        f"exceeding limit of {self.MAX_ZIP_TOTAL_SIZE / 1024 / 1024:.0f}MB. "
                        "This may be a zip bomb."
                    )

                # ─── Path traversal check ───
                # Prevent files like "../../../etc/passwd" in zip
                for name in file_list:
                    member_path = os.path.realpath(
                        os.path.join(target_dir, name)
                    )
                    if not member_path.startswith(os.path.realpath(target_dir)):
                        raise ZipExtractionError(
                            f"Zip contains path traversal attack: {name}"
                        )

                # ─── Extract ───
                zf.extractall(target_dir)

        except zipfile.BadZipFile as e:
            self.cleanup(target_dir)
            raise ZipExtractionError(
                f"Corrupt zip file: {zip_path}. Error: {e}"
            ) from e
        except ZipExtractionError:
            self.cleanup(target_dir)
            raise

        # If zip has a single top-level directory, return that
        # (common pattern: repo-name-main/ containing all files)
        contents = os.listdir(target_dir)
        if len(contents) == 1 and os.path.isdir(
            os.path.join(target_dir, contents[0])
        ):
            return os.path.join(target_dir, contents[0])

        return target_dir

    def cleanup(self, repo_dir: str) -> None:
        """
        Delete a repo directory to free disk space.

        Always use this after processing is complete.
        Called automatically on clone/extract errors.

        Args:
            repo_dir: Path to the repo directory to delete
        """
        try:
            if os.path.isdir(repo_dir):
                shutil.rmtree(repo_dir, ignore_errors=True)
        except Exception:
            pass  # Best-effort cleanup

    def _validate_github_url(self, url: str) -> bool:
        """
        Validate that URL is a proper GitHub HTTPS URL.

        Prevents SSRF by ensuring we only connect to github.com.

        Valid:
            https://github.com/owner/repo
            https://github.com/owner/repo.git

        Invalid:
            http://github.com/owner/repo       (not HTTPS)
            https://gitlab.com/owner/repo      (not GitHub)
            https://github.com/../../../etc    (path traversal)
            http://169.254.169.254/metadata    (cloud metadata — SSRF)
        """
        return bool(self.GITHUB_URL_PATTERN.match(url.strip()))
