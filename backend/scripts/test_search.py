"""
RepoMind — End-to-End Search Test Script

Full pipeline: Clone → Scan → Read → Parse → Chunk → Embed → Index → Search

Usage:
    python -m scripts.test_search <github_url> "<query>"

Example:
    python -m scripts.test_search https://github.com/pallets/markupsafe "How does HTML escaping work?"

Reference: Development Roadmap → Phase 4 → Deliverables
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


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.test_search <github_url> \"<query>\"")
        print('Example: python -m scripts.test_search https://github.com/pallets/markupsafe "How does escaping work?"')
        sys.exit(1)

    github_url = sys.argv[1]
    query = sys.argv[2]

    # ─── Initialize all modules ───
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
        # STAGE 1-5: Ingest → Parse → Chunk
        # ═══════════════════════════════════════════════════
        print(f"🔄 Cloning {github_url}...")
        start = time.time()
        repo_dir = loader.clone(github_url)
        clone_time = time.time() - start
        print(f"✅ Cloned ({clone_time:.1f}s)")

        print(f"🔍 Scanning files...")
        files = scanner.scan(repo_dir)
        print(f"✅ Scanned {len(files)} files")

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
        print(f"✅ {len(all_chunks)} chunks ({parse_time:.1f}s)")

        # ═══════════════════════════════════════════════════
        # STAGE 6: Embedding
        # ═══════════════════════════════════════════════════
        print(f"\n🧮 Loading embedding model...")
        embed_start = time.time()
        embedder = Embedder()
        load_time = time.time() - embed_start

        print(f"✅ Model loaded ({load_time:.1f}s, dim={embedder.dimension})")

        print(f"🧮 Embedding {len(all_chunks)} chunks (batch_size=32)...")
        embed_start = time.time()
        chunk_texts = [c.text for c in all_chunks]
        embeddings = embedder.embed(chunk_texts, batch_size=32)
        embed_time = time.time() - embed_start
        print(f"✅ Embedded → shape {embeddings.shape} ({embed_time:.1f}s)")

        # ═══════════════════════════════════════════════════
        # STAGE 7: Indexing
        # ═══════════════════════════════════════════════════
        print(f"\n📊 Building FAISS index ({len(all_chunks)} vectors, {embedder.dimension} dimensions)...")
        index_start = time.time()
        vector_store = VectorStore(dimension=embedder.dimension)
        vector_store.build(embeddings, all_chunks)
        faiss_time = time.time() - index_start
        print(f"✅ FAISS index built ({faiss_time:.3f}s)")

        print(f"📊 Building BM25 index ({len(all_chunks)} chunks)...")
        bm25_start = time.time()
        bm25_index = BM25Index()
        bm25_index.build(all_chunks)
        bm25_time = time.time() - bm25_start
        print(f"✅ BM25 index built ({bm25_time:.3f}s)")

        # ═══════════════════════════════════════════════════
        # SEARCH
        # ═══════════════════════════════════════════════════
        print(f"\n{'='*60}")
        print(f"🔎 Query: \"{query}\"")
        print(f"{'='*60}")

        # ─── Dense search ───
        print(f"\n🔵 Dense (FAISS) search results:")
        query_vec = embedder.embed_query(query)
        dense_start = time.time()
        dense_results = vector_store.search(query_vec, top_k=5)
        dense_time = time.time() - dense_start

        for i, r in enumerate(dense_results):
            symbol = r.chunk.parent_symbol or "<no symbol>"
            print(f"  [{r.score:.2f}] {r.chunk.file_path}:L{r.chunk.start_line}-L{r.chunk.end_line} — {symbol}")
        print(f"  ⏱️  {dense_time*1000:.1f}ms")

        # ─── BM25 search ───
        print(f"\n🟢 BM25 (keyword) search results:")
        bm25_search_start = time.time()
        bm25_results = bm25_index.search(query, top_k=5)
        bm25_search_time = time.time() - bm25_search_start

        for i, r in enumerate(bm25_results):
            symbol = r.chunk.parent_symbol or "<no symbol>"
            print(f"  [{r.score:.1f}] {r.chunk.file_path}:L{r.chunk.start_line}-L{r.chunk.end_line} — {symbol}")
        print(f"  ⏱️  {bm25_search_time*1000:.1f}ms")

        # ─── Timing summary ───
        print(f"\n{'='*60}")
        print(f"⏱️  TIMING SUMMARY")
        print(f"{'='*60}")
        print(f"  Clone:          {clone_time:.1f}s")
        print(f"  Parse + Chunk:  {parse_time:.1f}s")
        print(f"  Model Load:     {load_time:.1f}s")
        print(f"  Embedding:      {embed_time:.1f}s")
        print(f"  FAISS Build:    {faiss_time:.3f}s")
        print(f"  BM25 Build:     {bm25_time:.3f}s")
        print(f"  Dense Search:   {dense_time*1000:.1f}ms")
        print(f"  BM25 Search:    {bm25_search_time*1000:.1f}ms")
        print(f"{'='*60}")

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
