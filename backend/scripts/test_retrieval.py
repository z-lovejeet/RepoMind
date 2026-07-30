"""
RepoMind — End-to-End Retrieval Test Script

Full pipeline: Clone → Scan → Read → Parse → Chunk → Embed → Index → Retrieve → Context

Usage:
    python -m scripts.test_retrieval <github_url> "<query>" [--strategy dense|bm25|hybrid]

Example:
    python -m scripts.test_retrieval https://github.com/pallets/markupsafe "How does escaping work?" --strategy hybrid

Reference: Development Roadmap → Phase 5 → Deliverables
"""

import sys
import time

from app.core.ingestion.repo_loader import RepoLoader, RepoCloneError
from app.core.ingestion.file_scanner import FileScanner
from app.core.ingestion.file_reader import FileReader
from app.core.parsing.code_parser import CodeParser, CodeParseError
from app.core.parsing.doc_parser import DocParser
from app.core.chunking.code_chunker import CodeChunker
from app.core.chunking.doc_chunker import DocChunker
from app.core.chunking.text_chunker import TextChunker
from app.core.chunking.config_chunker import ConfigChunker
from app.core.embedding.embedder import Embedder
from app.core.indexing.vector_store import VectorStore
from app.core.indexing.bm25_index import BM25Index
from app.core.retrieval.retriever import Retriever
from app.core.retrieval.context_builder import ContextBuilder


def main():
    # ─── Parse arguments ───
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.test_retrieval <github_url> \"<query>\" [--strategy dense|bm25|hybrid]")
        sys.exit(1)

    github_url = sys.argv[1]
    query = sys.argv[2]
    strategy = "hybrid"

    if "--strategy" in sys.argv:
        idx = sys.argv.index("--strategy")
        if idx + 1 < len(sys.argv):
            strategy = sys.argv[idx + 1]

    # ─── Initialize modules ───
    loader = RepoLoader()
    scanner = FileScanner()
    reader = FileReader()
    code_parser = CodeParser()
    doc_parser = DocParser()
    code_chunker = CodeChunker()
    doc_chunker = DocChunker()
    text_chunker = TextChunker(chunk_size=512, chunk_overlap=50)
    config_chunker = ConfigChunker()

    repo_dir = None

    try:
        # ═══════════════════════════════════════════════════
        # STAGES 1-5: Ingest → Parse → Chunk
        # ═══════════════════════════════════════════════════
        print(f"🔄 Cloning {github_url}...")
        start = time.time()
        repo_dir = loader.clone(github_url)
        clone_time = time.time() - start
        print(f"✅ Cloned ({clone_time:.1f}s)")

        print(f"🔍 Scanning...")
        files = scanner.scan(repo_dir)

        print(f"📝 Parsing and chunking...")
        start = time.time()
        all_chunks = []

        for f in files:
            content = reader.read_safe(f.absolute_path)
            if content is None:
                continue

            if f.file_type == "code" and f.language == "python":
                try:
                    parsed = code_parser.parse(content, f.path)
                    chunks = code_chunker.chunk(
                        content, f.path, f.language,
                        metadata={"parsed_code": parsed}
                    )
                except CodeParseError:
                    chunks = text_chunker.chunk(content, f.path, f.language)
            elif f.file_type == "documentation":
                sections = doc_parser.parse_markdown(content, f.path)
                chunks = doc_chunker.chunk(
                    content, f.path, f.language,
                    metadata={"sections": sections}
                )
            elif f.file_type == "config":
                chunks = config_chunker.chunk(content, f.path, f.language)
            else:
                chunks = text_chunker.chunk(content, f.path, f.language)

            all_chunks.extend(chunks)

        parse_time = time.time() - start
        print(f"✅ {len(files)} files → {len(all_chunks)} chunks ({parse_time:.1f}s)")

        # ═══════════════════════════════════════════════════
        # STAGE 6-7: Embed → Index
        # ═══════════════════════════════════════════════════
        print(f"\n🧮 Loading embedding model...")
        embedder = Embedder()

        print(f"🧮 Embedding {len(all_chunks)} chunks...")
        start = time.time()
        embeddings = embedder.embed([c.text for c in all_chunks], batch_size=32)
        embed_time = time.time() - start
        print(f"✅ Embedded ({embed_time:.1f}s)")

        print(f"📊 Building indexes...")
        vector_store = VectorStore(dimension=embedder.dimension)
        vector_store.build(embeddings, all_chunks)

        bm25_index = BM25Index()
        bm25_index.build(all_chunks)
        print(f"✅ FAISS ({vector_store.size} vectors) + BM25 ({len(all_chunks)} chunks)")

        # ═══════════════════════════════════════════════════
        # STAGE 8: Retrieval
        # ═══════════════════════════════════════════════════
        retriever = Retriever(vector_store, bm25_index, embedder)
        context_builder = ContextBuilder()

        print(f"\n{'='*60}")
        print(f"🔎 Query: \"{query}\"")
        print(f"📋 Strategy: {strategy}")
        print(f"{'='*60}")

        start = time.time()
        results = retriever.retrieve(query, strategy=strategy, top_k=10)
        retrieval_time = (time.time() - start) * 1000

        print(f"\n🔍 Retrieved {len(results)} chunks ({retrieval_time:.1f}ms):\n")
        for i, r in enumerate(results[:10]):
            symbol = r.chunk.parent_symbol or "<module>"
            print(
                f"  [{i+1}] [{r.score:.4f}] "
                f"{r.chunk.file_path}:L{r.chunk.start_line}-L{r.chunk.end_line} "
                f"— {symbol} ({r.source})"
            )

        # ═══════════════════════════════════════════════════
        # STAGE 10: Context Building
        # ═══════════════════════════════════════════════════
        context = context_builder.build(results[:5], max_context_tokens=4000)
        estimated_tokens = len(context) // 4

        print(f"\n{'='*60}")
        print(f"📄 CONTEXT (estimated {estimated_tokens} tokens):")
        print(f"{'='*60}")
        print(context)
        print(f"{'='*60}")

        # ─── Timing summary ───
        print(f"\n⏱️  Clone: {clone_time:.1f}s | "
              f"Parse: {parse_time:.1f}s | "
              f"Embed: {embed_time:.1f}s | "
              f"Retrieve: {retrieval_time:.1f}ms")

    except RepoCloneError as e:
        print(f"❌ Clone failed: {e}")
        sys.exit(1)
    finally:
        if repo_dir:
            print(f"\n🧹 Cleaning up...")
            loader.cleanup(repo_dir)
            print("✅ Done")


if __name__ == "__main__":
    main()
