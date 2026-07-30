"""
RepoMind — End-to-End RAG Pipeline Test Script

The FIRST complete RAG query: Clone → Ingest → Query → Answer with Citations.

Usage:
    python -m scripts.test_pipeline <github_url> "<query>" [--provider gemini|groq]

Example:
    python -m scripts.test_pipeline https://github.com/pallets/markupsafe \
        "How does HTML escaping work?" --provider gemini

Environment:
    GEMINI_API_KEY or GROQ_API_KEY must be set.

Reference: Development Roadmap → Phase 6 → Deliverables
"""

import sys
import time

from dotenv import load_dotenv

# Load .env file for API keys
load_dotenv()

from app.core.ingestion.repo_loader import RepoLoader, RepoCloneError
from app.core.embedding.embedder import Embedder
from app.core.generation.llm_client import LLMClient, LLMError
from app.core.pipeline import Pipeline


def main():
    # ─── Parse arguments ───
    if len(sys.argv) < 3:
        print(
            "Usage: python -m scripts.test_pipeline <github_url> "
            "\"<query>\" [--provider gemini|groq]"
        )
        sys.exit(1)

    github_url = sys.argv[1]
    query = sys.argv[2]
    provider = "gemini"

    if "--provider" in sys.argv:
        idx = sys.argv.index("--provider")
        if idx + 1 < len(sys.argv):
            provider = sys.argv[idx + 1]

    loader = RepoLoader()
    repo_dir = None

    try:
        # ═══════════════════════════════════════════════════
        # Step 1: Clone
        # ═══════════════════════════════════════════════════
        print(f"🔄 Cloning {github_url}...")
        start = time.time()
        repo_dir = loader.clone(github_url)
        clone_time = time.time() - start
        print(f"✅ Cloned ({clone_time:.1f}s)")

        # ═══════════════════════════════════════════════════
        # Step 2: Initialize Pipeline
        # ═══════════════════════════════════════════════════
        print(f"\n🧮 Loading embedding model...")
        embedder = Embedder()

        print(f"🤖 Initializing LLM ({provider})...")
        try:
            llm_client = LLMClient(provider=provider)
        except LLMError as e:
            print(f"❌ LLM init failed: {e}")
            sys.exit(1)

        pipeline = Pipeline(embedder=embedder, llm_client=llm_client)

        # ═══════════════════════════════════════════════════
        # Step 3: Ingest
        # ═══════════════════════════════════════════════════
        print(f"\n📝 Ingesting repository...")
        start = time.time()
        ingest_result = pipeline.ingest(repo_dir)
        ingest_time = time.time() - start

        print(
            f"✅ Ingested: {ingest_result.file_count} files → "
            f"{ingest_result.chunk_count} chunks ({ingest_time:.1f}s)"
        )
        print(f"   Languages: {ingest_result.languages}")

        # ═══════════════════════════════════════════════════
        # Step 4: Query (THE FIRST COMPLETE RAG QUERY! 🎉)
        # ═══════════════════════════════════════════════════
        print(f"\n{'='*60}")
        print(f"🔎 Query: \"{query}\"")
        print(f"📋 Provider: {provider} | Strategy: hybrid")
        print(f"{'='*60}")

        start = time.time()
        result = pipeline.query(query)
        query_time = time.time() - start

        # ─── Display answer ───
        print(f"\n💬 Answer:")
        print(f"{result.answer}")

        # ─── Display sources ───
        if result.citations:
            print(f"\n📎 Sources:")
            for c in result.citations:
                status = "✓" if c.valid else "⚠️ HALLUCINATED"
                print(
                    f"  [{c.index}] {c.file_path}:{c.lines} "
                    f"(score: {c.score:.2f}) {status}"
                )
        else:
            print(f"\n⚠️ No citations found in response")

        # ─── Display timings ───
        print(f"\n⏱️  Timings:")
        print(f"   Clone: {clone_time:.1f}s")
        print(f"   Ingest: {ingest_time:.1f}s")
        for stage, ms in result.timings.items():
            print(f"   {stage}: {ms:.1f}ms")
        print(f"   Total query: {query_time:.1f}s")

        print(f"\n🎉 First complete RAG query successful!")

    except RepoCloneError as e:
        print(f"❌ Clone failed: {e}")
        sys.exit(1)
    except LLMError as e:
        print(f"❌ LLM generation failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if repo_dir:
            print(f"\n🧹 Cleaning up...")
            loader.cleanup(repo_dir)
            print("✅ Done")


if __name__ == "__main__":
    main()
