"""
RepoMind — Shared Data Models & API Schemas

This module contains ALL data classes and Pydantic models used across the project.
It is the CONTRACT between modules — every module produces and consumes these exact shapes.

Two categories:
1. Dataclasses — Internal data structures passed between core modules
2. Pydantic Models — API request/response schemas with validation

Reference:
    - Module Design Document: "Shared Data Classes" section
    - API Documentation: "Type Definitions" section
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL DATA CLASSES (used across core modules)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class FileInfo:
    """
    Represents a single file discovered during repository scanning.

    Produced by: core/ingestion/file_scanner.py
    Consumed by: core/parsing/, core/chunking/
    """

    path: str  # Relative to repo root: "auth/middleware.py"
    absolute_path: str  # Full path: "/tmp/repos/rp_abc/auth/middleware.py"
    file_type: str  # "code" | "documentation" | "config" | "other"
    language: str  # "python" | "markdown" | "yaml" | etc.
    size_bytes: int  # File size in bytes


@dataclass
class ParsedFunction:
    """
    A function extracted from Python source code via AST parsing.

    Produced by: core/parsing/code_parser.py
    Consumed by: core/chunking/code_chunker.py, core/analysis/
    """

    name: str  # "authenticate"
    args: list[str]  # ["self", "token: str"]
    return_type: Optional[str]  # "User" or None
    docstring: Optional[str]  # First string literal in function body
    decorators: list[str]  # ["@login_required"]
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed, inclusive
    body: str  # Complete source code of the function


@dataclass
class ParsedClass:
    """
    A class extracted from Python source code via AST parsing.

    Produced by: core/parsing/code_parser.py
    Consumed by: core/chunking/code_chunker.py, core/analysis/
    """

    name: str  # "AuthMiddleware"
    bases: list[str]  # ["BaseMiddleware"]
    docstring: Optional[str]
    methods: list[ParsedFunction]
    start_line: int
    end_line: int
    body: str  # Complete source code of the class


@dataclass
class ParsedImport:
    """
    An import statement extracted from Python source code.

    Produced by: core/parsing/code_parser.py
    Consumed by: core/parsing/dependency_extractor.py
    """

    module: str  # "jwt" or "models.user"
    names: list[str]  # ["decode"] for "from jwt import decode"
    is_from: bool  # True for "from X import Y"
    line: int


@dataclass
class ParsedCode:
    """
    Complete structured representation of a parsed Python file.

    Produced by: core/parsing/code_parser.py
    Consumed by: core/chunking/code_chunker.py, core/analysis/
    """

    file_path: str
    functions: list[ParsedFunction]
    classes: list[ParsedClass]
    imports: list[ParsedImport]


@dataclass
class DocSection:
    """
    A section of a documentation file (Markdown/RST), split by heading.

    Produced by: core/parsing/doc_parser.py
    Consumed by: core/chunking/doc_chunker.py
    """

    heading: str  # "Installation"
    level: int  # 1 for #, 2 for ##, 3 for ###
    content: str  # Text under the heading
    start_line: int
    end_line: int


@dataclass
class Chunk:
    """
    The atomic unit of the RAG pipeline.
    Every chunk is independently embedded, indexed, and retrieved.

    Produced by: core/chunking/*
    Consumed by: core/embedding/, core/indexing/, core/retrieval/
    """

    id: str  # UUID string
    text: str  # The actual text content
    file_path: str  # "auth/middleware.py"
    start_line: int
    end_line: int
    chunk_type: str  # "code" | "documentation" | "config" | "text"
    language: str  # "python" | "markdown" | etc.
    parent_symbol: Optional[str] = None  # "AuthMiddleware.verify" or "## Installation"


@dataclass
class SearchResult:
    """
    A single search result from retrieval (dense, BM25, or hybrid).

    Produced by: core/retrieval/retriever.py
    Consumed by: core/retrieval/reranker.py, core/retrieval/context_builder.py
    """

    chunk: Chunk
    score: float  # 0.0 to 1.0 (higher = more relevant)
    source: str  # "dense" | "bm25" | "hybrid" | "hyde"


@dataclass
class Citation:
    """
    A source citation extracted from the LLM response.

    Produced by: core/generation/response_parser.py
    Consumed by: API response, frontend display
    """

    index: int  # [1], [2], etc.
    file_path: str  # "auth/middleware.py"
    lines: str  # "8-35"
    score: float
    valid: bool  # True if file exists in repo


@dataclass
class PipelineResult:
    """
    The complete result of a RAG query pipeline execution.

    Produced by: core/pipeline.py
    Consumed by: api/query.py
    """

    answer: str
    citations: list[Citation]
    timings: dict  # {"retrieval_ms": 45, "generation_ms": 1200}
    config: dict  # {"strategy": "hybrid", "reranking": True}


@dataclass
class ParsedResponse:
    """
    Parsed LLM response with extracted citations and validation results.

    Produced by: core/generation/response_parser.py
    Consumed by: core/pipeline.py
    """

    answer: str
    citations: list[Citation]
    hallucination_flags: list[str]  # Invalid file paths detected



@dataclass
class IngestResult:
    """
    The result of the ingestion pipeline.

    Produced by: core/pipeline.py
    Consumed by: api/repos.py
    """

    file_count: int
    chunk_count: int
    languages: dict  # {"python": 45, "markdown": 12}
    timings: dict  # {"clone_ms": ..., "parse_ms": ..., "embed_ms": ...}


@dataclass
class QueryConfig:
    """
    Configuration for a single RAG query.

    Produced by: API request parsing
    Consumed by: core/pipeline.py, core/retrieval/
    """

    strategy: str = "hybrid"  # "dense" | "bm25" | "hybrid" | "hyde"
    reranking: bool = True
    top_k_retrieval: int = 20
    top_k_rerank: int = 5
    chunk_size: int = 512
    include_references: bool = True
    model: str = "gpt-4o-mini"
    temperature: float = 0.1


# ─── Analysis Data Classes ───


@dataclass
class DependencyNode:
    """A node in the dependency graph (file or symbol)."""

    id: str  # "auth/middleware.py" or "auth/middleware.py::AuthMiddleware"
    type: str  # "file" | "function" | "class"
    name: str  # "middleware.py" or "AuthMiddleware"
    file_path: str


@dataclass
class DependencyEdge:
    """An edge in the dependency graph (import/call relationship)."""

    source: str  # Node ID of the importer
    target: str  # Node ID of the imported
    edge_type: str  # "imports" | "calls" | "inherits"


@dataclass
class DependencyGraph:
    """Complete dependency graph for a repository."""

    nodes: list[DependencyNode] = field(default_factory=list)
    edges: list[DependencyEdge] = field(default_factory=list)

    def get_importers(self, file_path: str) -> list[str]:
        """Who imports this file?"""
        return [e.source for e in self.edges if e.target == file_path]

    def get_imports(self, file_path: str) -> list[str]:
        """What does this file import?"""
        return [e.target for e in self.edges if e.source == file_path]


@dataclass
class References:
    """All references to a function or class."""

    callers: list[str]  # ["routes/login.py::handle_login"]
    callees: list[str]  # ["jwt.decode", "User.get"]
    tests: list[str]  # ["tests/test_auth.py::test_verify"]


@dataclass
class ProjectStructure:
    """Summary of repository structure and statistics."""

    languages: dict  # {"python": 45, "markdown": 12}
    directories: list[dict]  # [{"path": "auth/", "description": "..."}]
    entry_points: list[str]  # ["app/main.py"]
    stats: dict  # {"total_files": 147, "total_chunks": 523}


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC API SCHEMAS (request/response validation)
# ═══════════════════════════════════════════════════════════════════════════════


# ─── Request Models ───


class CloneRepoRequest(BaseModel):
    """Request body for POST /api/repos/clone."""

    github_url: str = Field(
        ...,
        description="HTTPS GitHub URL to clone",
        json_schema_extra={"example": "https://github.com/tiangolo/fastapi"},
    )

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        if "github.com" not in v:
            raise ValueError("Only GitHub URLs are supported")
        if not v.startswith("https://"):
            raise ValueError("URL must use HTTPS")
        return v


class QueryConfigSchema(BaseModel):
    """Pipeline configuration for a query (Pydantic version of QueryConfig)."""

    strategy: str = Field(default="hybrid", pattern="^(dense|bm25|hybrid|hyde)$")
    reranking: bool = True
    top_k_retrieval: int = Field(default=20, ge=1, le=100)
    top_k_rerank: int = Field(default=5, ge=1, le=20)
    include_references: bool = True
    model: str = Field(default="gpt-4o-mini")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)


class QueryRequest(BaseModel):
    """Request body for POST /api/repos/{repo_id}/query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language question about the repository",
    )
    config: Optional[QueryConfigSchema] = None


class ExperimentRequest(BaseModel):
    """Request body for POST /api/repos/{repo_id}/experiments."""

    query: str = Field(..., min_length=1, max_length=1000)
    config_a: QueryConfigSchema
    config_b: QueryConfigSchema


# ─── Response Models ───


class RepoResponse(BaseModel):
    """Single repository in API responses."""

    id: str
    name: str
    source: str  # "github" | "upload"
    github_url: Optional[str] = None
    status: str  # "indexing" | "ready" | "error"
    file_count: Optional[int] = None
    total_chunks: Optional[int] = None
    languages: list[str] = []
    indexed_at: Optional[str] = None
    created_at: str


class CitationResponse(BaseModel):
    """A source citation in query responses."""

    index: int
    file_path: str
    lines: str
    score: float
    valid: bool
    snippet: Optional[str] = None


class QueryResponse(BaseModel):
    """Response for POST /api/repos/{repo_id}/query."""

    answer: str
    citations: list[CitationResponse]
    timings: dict
    config: dict


class StreamEvent(BaseModel):
    """A single event in the SSE stream."""

    token: str
    done: bool
    sources: Optional[list[CitationResponse]] = None
    timings: Optional[dict] = None
    error: Optional[str] = None
    message: Optional[str] = None


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str  # "REPO_CLONE_FAILED"
    message: str  # "Failed to clone repository"
    detail: Optional[str] = None
    suggestion: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized error response for all endpoints."""

    success: bool = False
    error: ErrorDetail


class SuccessResponse(BaseModel):
    """Generic success wrapper."""

    success: bool = True
    data: dict = {}
