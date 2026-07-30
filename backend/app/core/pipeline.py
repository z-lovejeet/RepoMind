"""
RepoMind — Pipeline Orchestrator

Wire together all core modules into two main flows:
    1. ingest(repo_dir) → scan → parse → chunk → embed → index → IngestResult
    2. query(query)     → retrieve → context → prompt → generate → parse → PipelineResult

Design: Dependency Injection
    All modules are passed via constructor. This makes the pipeline:
    - Testable: swap real modules for mocks
    - Flexible: change embedder/LLM without touching pipeline code
    - Clear: all dependencies are explicit in __init__

Error Isolation:
    - Individual file failures during ingest are caught and skipped
    - Only embedding/indexing failures are fatal (abort ingest)
    - Query failures propagate to the caller

Reference:
    - Module Design → Section 9 (core/pipeline.py)
    - RAG Workflow → Stages 1-13 (full pipeline)
"""

import logging
import time

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
from app.core.generation.llm_client import LLMClient
from app.core.generation.prompt_builder import PromptBuilder
from app.core.generation.response_parser import ResponseParser
from app.models.schemas import (
    Chunk,
    IngestResult,
    PipelineResult,
    QueryConfig,
    SearchResult,
)

logger = logging.getLogger(__name__)


class Pipeline:
    """
    Orchestrate the full RAG pipeline: ingest + query.

    Usage:
        pipeline = Pipeline(embedder, llm_client, ...)
        ingest_result = pipeline.ingest("/path/to/repo", "rp_abc123")
        query_result = pipeline.query("How does auth work?")
    """

    def __init__(
        self,
        embedder: Embedder,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder | None = None,
        response_parser: ResponseParser | None = None,
    ):
        """
        Accept core dependencies via constructor (dependency injection).

        Modules that are always the same (scanner, reader, parsers, chunkers)
        are created internally. Modules that vary (embedder, LLM) are injected.

        Args:
            embedder: Sentence Transformer embedder
            llm_client: LLM client (Gemini/Groq)
            prompt_builder: Optional custom prompt builder
            response_parser: Optional custom response parser
        """
        # ─── Injected dependencies ───
        self.embedder = embedder
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.response_parser = response_parser or ResponseParser()

        # ─── Internal modules (created fresh each time) ───
        self.scanner = FileScanner()
        self.reader = FileReader()
        self.code_parser = CodeParser()
        self.doc_parser = DocParser()
        self.code_chunker = CodeChunker()
        self.doc_chunker = DocChunker()
        self.text_chunker = TextChunker(chunk_size=512, chunk_overlap=50)
        self.config_chunker = ConfigChunker()

        # ─── Index state (built during ingest, used during query) ───
        self.vector_store: VectorStore | None = None
        self.bm25_index: BM25Index | None = None
        self.retriever: Retriever | None = None
        self.context_builder = ContextBuilder()

        # ─── Repo metadata ───
        self.repo_files: set[str] = set()
        self.repo_name: str = "unknown"
        self.all_chunks: list[Chunk] = []

    def ingest(self, repo_dir: str, repo_id: str = "default") -> IngestResult:
        """
        Full ingestion pipeline: scan → parse → chunk → embed → index.

        Args:
            repo_dir: Path to the cloned/extracted repository
            repo_id: Unique identifier for this repo

        Returns:
            IngestResult with file_count, chunk_count, languages, timings
        """
        timings = {}
        languages: dict[str, int] = {}

        # ─── Extract repo name ───
        self.repo_name = repo_dir.rstrip("/").split("/")[-1]

        # ═══════════════════════════════════════════════════
        # Stage 1: Scan files
        # ═══════════════════════════════════════════════════
        start = time.time()
        files = self.scanner.scan(repo_dir)
        timings["scan_ms"] = (time.time() - start) * 1000

        self.repo_files = {f.path for f in files}
        logger.info(f"Scanned {len(files)} files")

        # Count languages
        for f in files:
            lang = f.language or "unknown"
            languages[lang] = languages.get(lang, 0) + 1

        # ═══════════════════════════════════════════════════
        # Stage 2-5: Read → Parse → Chunk
        # ═══════════════════════════════════════════════════
        start = time.time()
        all_chunks: list[Chunk] = []
        skipped = 0

        for f in files:
            try:
                content = self.reader.read_safe(f.absolute_path)
                if content is None:
                    skipped += 1
                    continue

                chunks = self._parse_and_chunk(content, f)
                all_chunks.extend(chunks)

            except Exception as e:
                logger.warning(f"Skipping {f.path}: {e}")
                skipped += 1
                continue

        timings["parse_chunk_ms"] = (time.time() - start) * 1000
        self.all_chunks = all_chunks
        logger.info(
            f"Parsed and chunked: {len(all_chunks)} chunks "
            f"({skipped} files skipped)"
        )

        if not all_chunks:
            return IngestResult(
                file_count=len(files),
                chunk_count=0,
                languages=languages,
                timings=timings,
            )

        # ═══════════════════════════════════════════════════
        # Stage 6: Embed
        # ═══════════════════════════════════════════════════
        start = time.time()
        texts = [c.text for c in all_chunks]
        embeddings = self.embedder.embed(texts, batch_size=32)
        timings["embed_ms"] = (time.time() - start) * 1000
        logger.info(f"Embedded {len(all_chunks)} chunks")

        # ═══════════════════════════════════════════════════
        # Stage 7: Index
        # ═══════════════════════════════════════════════════
        start = time.time()

        self.vector_store = VectorStore(dimension=self.embedder.dimension)
        self.vector_store.build(embeddings, all_chunks)

        self.bm25_index = BM25Index()
        self.bm25_index.build(all_chunks)

        # Wire up retriever
        self.retriever = Retriever(
            vector_store=self.vector_store,
            bm25_index=self.bm25_index,
            embedder=self.embedder,
        )

        timings["index_ms"] = (time.time() - start) * 1000
        logger.info(
            f"Indexed: FAISS ({self.vector_store.size} vectors) + "
            f"BM25 ({len(all_chunks)} chunks)"
        )

        return IngestResult(
            file_count=len(files),
            chunk_count=len(all_chunks),
            languages=languages,
            timings=timings,
        )

    def query(
        self,
        query: str,
        config: QueryConfig | None = None,
    ) -> PipelineResult:
        """
        Full query pipeline: retrieve → context → prompt → generate → parse.

        Args:
            query: Natural language question about the codebase
            config: Query configuration (strategy, top_k, etc.)

        Returns:
            PipelineResult with answer, citations, timings, config

        Raises:
            RuntimeError: If ingest() hasn't been called yet
        """
        if self.retriever is None:
            raise RuntimeError(
                "Pipeline not ready. Call ingest() first to build indexes."
            )

        config = config or QueryConfig()
        timings = {}

        # ═══════════════════════════════════════════════════
        # Stage 8: Retrieve
        # ═══════════════════════════════════════════════════
        start = time.time()
        results = self.retriever.retrieve(
            query,
            strategy=config.strategy,
            top_k=config.top_k_retrieval,
        )
        timings["retrieval_ms"] = (time.time() - start) * 1000

        # Take top-5 for context (reranker would go here in Phase 7)
        top_results = results[:config.top_k_rerank]

        # ═══════════════════════════════════════════════════
        # Stage 10: Build context
        # ═══════════════════════════════════════════════════
        start = time.time()
        context = self.context_builder.build(top_results, max_context_tokens=4000)
        timings["context_ms"] = (time.time() - start) * 1000

        # ═══════════════════════════════════════════════════
        # Stage 11: Build prompt
        # ═══════════════════════════════════════════════════
        prompt = self.prompt_builder.build(
            context=context,
            query=query,
            repo_name=self.repo_name,
        )

        # ═══════════════════════════════════════════════════
        # Stage 12: Generate
        # ═══════════════════════════════════════════════════
        start = time.time()
        raw_answer = self.llm_client.generate(
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            temperature=config.temperature,
        )
        timings["generation_ms"] = (time.time() - start) * 1000

        # ═══════════════════════════════════════════════════
        # Stage 13: Parse response
        # ═══════════════════════════════════════════════════
        parsed = self.response_parser.parse(
            response=raw_answer,
            context_chunks=top_results,
            repo_files=self.repo_files,
        )

        return PipelineResult(
            answer=parsed.answer,
            citations=parsed.citations,
            timings=timings,
            config={
                "strategy": config.strategy,
                "top_k_retrieval": config.top_k_retrieval,
                "top_k_rerank": config.top_k_rerank,
                "model": config.model,
                "temperature": config.temperature,
            },
        )

    def _parse_and_chunk(self, content: str, file_info) -> list[Chunk]:
        """
        Parse and chunk a single file based on its type.

        Args:
            content: File contents
            file_info: FileInfo with type, language, path

        Returns:
            List of Chunk objects
        """
        if file_info.file_type == "code" and file_info.language == "python":
            try:
                parsed = self.code_parser.parse(content, file_info.path)
                return self.code_chunker.chunk(
                    content, file_info.path, file_info.language,
                    metadata={"parsed_code": parsed},
                )
            except CodeParseError:
                return self.text_chunker.chunk(
                    content, file_info.path, file_info.language
                )

        elif file_info.file_type == "documentation":
            sections = self.doc_parser.parse_markdown(content, file_info.path)
            return self.doc_chunker.chunk(
                content, file_info.path, file_info.language,
                metadata={"sections": sections},
            )

        elif file_info.file_type == "config":
            return self.config_chunker.chunk(
                content, file_info.path, file_info.language
            )

        else:
            return self.text_chunker.chunk(
                content, file_info.path, file_info.language
            )
