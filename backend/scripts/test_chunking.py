"""
RepoMind — Integration Test Script for Parsing & Chunking Pipeline

End-to-end test: Clone repo → scan files → read → parse → chunk → stats.

Usage:
    python -m scripts.test_chunking https://github.com/pallets/flask

Expected output:
    Parsed 85 Python files: 312 functions, 67 classes, 890 imports
    Chunks generated: 1834
      Code chunks: 1245 (avg 18 lines)
      Doc chunks: 412 (avg 8 lines)
      Config chunks: 45 (avg 22 lines)
      Text chunks: 132 (avg 12 lines)

Reference: Development Roadmap → Phase 3 → Deliverables
"""

import sys
import time
from collections import Counter

from app.core.ingestion.repo_loader import RepoLoader, RepoCloneError
from app.core.ingestion.file_scanner import FileScanner
from app.core.ingestion.file_reader import FileReader
from app.core.parsing.code_parser import CodeParser, CodeParseError
from app.core.parsing.doc_parser import DocParser
from app.core.parsing.config_parser import ConfigParser, ConfigParseError
from app.core.chunking.code_chunker import CodeChunker
from app.core.chunking.doc_chunker import DocChunker
from app.core.chunking.text_chunker import TextChunker
from app.core.chunking.config_chunker import ConfigChunker


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.test_chunking <github_url>")
        print("Example: python -m scripts.test_chunking https://github.com/pallets/flask")
        sys.exit(1)

    github_url = sys.argv[1]

    # ─── Initialize all modules ───
    loader = RepoLoader()
    scanner = FileScanner()
    reader = FileReader()
    code_parser = CodeParser()
    doc_parser = DocParser()
    config_parser = ConfigParser()
    code_chunker = CodeChunker()
    doc_chunker = DocChunker()
    text_chunker = TextChunker(chunk_size=512, chunk_overlap=50)
    config_chunker = ConfigChunker()

    repo_dir = None

    # Stats counters
    total_functions = 0
    total_classes = 0
    total_imports = 0
    total_parse_errors = 0
    python_files_parsed = 0
    doc_files_parsed = 0
    config_files_parsed = 0

    all_chunks = []

    try:
        # ─── Step 1: Clone ───
        print(f"🔄 Cloning {github_url}...")
        start = time.time()
        repo_dir = loader.clone(github_url)
        clone_time = time.time() - start
        print(f"✅ Cloned → {repo_dir} ({clone_time:.1f}s)")

        # ─── Step 2: Scan ───
        print(f"\n🔍 Scanning files...")
        files = scanner.scan(repo_dir)
        print(f"✅ Scanned {len(files)} files")

        # ─── Step 3: Parse & Chunk each file ───
        print(f"\n📝 Parsing and chunking...")
        start = time.time()

        for f in files:
            content = reader.read_safe(f.absolute_path)
            if content is None:
                continue

            # ─── Route to correct parser + chunker ───
            if f.file_type == "code" and f.language == "python":
                # Parse Python with AST
                try:
                    parsed = code_parser.parse(content, f.path)
                    total_functions += len(parsed.functions)
                    total_classes += len(parsed.classes)
                    total_imports += len(parsed.imports)
                    python_files_parsed += 1

                    # Chunk with code chunker
                    chunks = code_chunker.chunk(
                        content, f.path, f.language,
                        metadata={"parsed_code": parsed}
                    )
                except CodeParseError:
                    total_parse_errors += 1
                    # Fall back to text chunking
                    chunks = text_chunker.chunk(content, f.path, f.language)

            elif f.file_type == "documentation":
                # Parse docs by heading
                if f.language in ("markdown", "text"):
                    sections = doc_parser.parse_markdown(content, f.path)
                else:
                    sections = doc_parser.parse_rst(content, f.path)
                doc_files_parsed += 1

                # Chunk with doc chunker
                chunks = doc_chunker.chunk(
                    content, f.path, f.language,
                    metadata={"sections": sections}
                )

            elif f.file_type == "config":
                config_files_parsed += 1
                # Chunk with config chunker (whole file)
                chunks = config_chunker.chunk(content, f.path, f.language)

            else:
                # Other/unknown → text chunker
                chunks = text_chunker.chunk(content, f.path, f.language)

            all_chunks.extend(chunks)

        parse_time = time.time() - start

        # ─── Step 4: Print statistics ───
        chunk_type_counter = Counter()
        chunk_lines = {"code": [], "documentation": [], "config": [], "text": []}

        for chunk in all_chunks:
            chunk_type_counter[chunk.chunk_type] += 1
            line_count = chunk.end_line - chunk.start_line + 1
            if chunk.chunk_type in chunk_lines:
                chunk_lines[chunk.chunk_type].append(line_count)

        print(f"✅ Parsed & chunked in {parse_time:.1f}s")

        print(f"\n{'='*60}")
        print(f"📋 PARSING & CHUNKING PIPELINE SUMMARY")
        print(f"{'='*60}")

        print(f"\n📊 Parsing Results:")
        print(f"  Python files parsed: {python_files_parsed}")
        print(f"  Functions extracted:  {total_functions}")
        print(f"  Classes extracted:    {total_classes}")
        print(f"  Imports extracted:    {total_imports}")
        print(f"  Doc files parsed:     {doc_files_parsed}")
        print(f"  Config files parsed:  {config_files_parsed}")
        if total_parse_errors:
            print(f"  ⚠️  Parse errors:     {total_parse_errors} (fell back to text chunking)")

        print(f"\n📦 Chunks Generated: {len(all_chunks)}")
        for chunk_type in ["code", "documentation", "config", "text"]:
            count = chunk_type_counter.get(chunk_type, 0)
            if count > 0:
                lines = chunk_lines[chunk_type]
                avg = sum(lines) / len(lines) if lines else 0
                print(f"  {chunk_type.capitalize():15} {count:4} (avg {avg:.0f} lines)")

        print(f"\n⏱️  Timing:")
        print(f"  Clone:          {clone_time:.1f}s")
        print(f"  Parse + Chunk:  {parse_time:.1f}s")
        print(f"{'='*60}")

    except RepoCloneError as e:
        print(f"❌ Clone failed: {e}")
        sys.exit(1)
    finally:
        if repo_dir:
            print(f"\n🧹 Cleaning up {repo_dir}...")
            loader.cleanup(repo_dir)
            print("✅ Done")


if __name__ == "__main__":
    main()
