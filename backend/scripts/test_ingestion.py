"""
RepoMind — Integration Test Script for Ingestion Pipeline

End-to-end test: Clone a real GitHub repo, scan files, read contents,
and print a classified summary.

Usage:
    python -m scripts.test_ingestion https://github.com/pallets/flask

Expected output:
    ✅ Cloned https://github.com/pallets/flask → /tmp/repomind/rp_abc12345
    Scanned 142 files:
      Code: 85 (python: 85)
      Docs: 32 (markdown: 30, rst: 2)
      Config: 15 (yaml: 5, toml: 3, json: 7)
      Other: 10
    Read 142/142 files successfully

Reference: Development Roadmap → Phase 2 → Deliverables
"""

import sys
import time
from collections import Counter

from app.core.ingestion.repo_loader import RepoLoader, RepoCloneError
from app.core.ingestion.file_scanner import FileScanner
from app.core.ingestion.file_reader import FileReader


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.test_ingestion <github_url>")
        print("Example: python -m scripts.test_ingestion https://github.com/pallets/flask")
        sys.exit(1)

    github_url = sys.argv[1]

    loader = RepoLoader()
    scanner = FileScanner()
    reader = FileReader()

    repo_dir = None

    try:
        # ─── Step 1: Clone ───
        print(f"🔄 Cloning {github_url}...")
        start = time.time()
        repo_dir = loader.clone(github_url)
        clone_time = time.time() - start
        print(f"✅ Cloned → {repo_dir} ({clone_time:.1f}s)")

        # ─── Step 2: Scan ───
        print(f"\n🔍 Scanning files...")
        start = time.time()
        files = scanner.scan(repo_dir)
        scan_time = time.time() - start
        print(f"✅ Scanned {len(files)} files ({scan_time:.1f}s)")

        # ─── Step 3: Classify and summarize ───
        type_counter = Counter()
        lang_counter = Counter()
        for f in files:
            type_counter[f.file_type] += 1
            lang_counter[f.language] += 1

        print(f"\n📊 File Classification:")
        for file_type in ["code", "documentation", "config", "other"]:
            count = type_counter.get(file_type, 0)
            if count > 0:
                # Find languages in this type
                type_langs = Counter()
                for f in files:
                    if f.file_type == file_type:
                        type_langs[f.language] += 1
                lang_str = ", ".join(
                    f"{lang}: {c}" for lang, c in type_langs.most_common()
                )
                print(f"  {file_type.capitalize():15} {count:4} ({lang_str})")

        # ─── Step 4: Read files ───
        print(f"\n📖 Reading file contents...")
        start = time.time()
        success = 0
        fail = 0
        total_bytes = 0
        for f in files:
            content = reader.read_safe(f.absolute_path)
            if content is not None:
                success += 1
                total_bytes += len(content.encode("utf-8"))
            else:
                fail += 1
                print(f"  ⚠️  Failed to read: {f.path}")
        read_time = time.time() - start
        print(
            f"✅ Read {success}/{len(files)} files "
            f"({total_bytes / 1024:.0f} KB, {read_time:.1f}s)"
        )
        if fail > 0:
            print(f"  ⚠️  {fail} files could not be read")

        # ─── Summary ───
        print(f"\n{'='*50}")
        print(f"📋 INGESTION PIPELINE SUMMARY")
        print(f"{'='*50}")
        print(f"  Repository:  {github_url}")
        print(f"  Files found: {len(files)}")
        print(f"  Files read:  {success}")
        print(f"  Total size:  {total_bytes / 1024:.0f} KB")
        print(f"  Clone time:  {clone_time:.1f}s")
        print(f"  Scan time:   {scan_time:.1f}s")
        print(f"  Read time:   {read_time:.1f}s")
        print(f"  Languages:   {', '.join(lang_counter.keys())}")
        print(f"{'='*50}")

    except RepoCloneError as e:
        print(f"❌ Clone failed: {e}")
        sys.exit(1)
    finally:
        # ─── Cleanup ───
        if repo_dir:
            print(f"\n🧹 Cleaning up {repo_dir}...")
            loader.cleanup(repo_dir)
            print("✅ Done")


if __name__ == "__main__":
    main()
