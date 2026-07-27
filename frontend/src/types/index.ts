/**
 * RepoMind — TypeScript Type Definitions
 *
 * Mirrors backend Pydantic models exactly.
 * This is the frontend's contract with the backend API.
 *
 * Reference: API Documentation → Section 10 (Type Definitions)
 */

// ═══════════════════════════════════════════════════════════════
// Core Types
// ═══════════════════════════════════════════════════════════════

export interface Repo {
  id: string;
  name: string;
  source: "github" | "upload";
  github_url: string | null;
  status: "indexing" | "ready" | "error";
  file_count: number | null;
  total_chunks: number | null;
  languages: string[];
  indexed_at: string | null;
  created_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Citation[];
  timings?: Timings;
  config?: QueryConfig;
  timestamp: string;
}

export interface Citation {
  index: number;
  file_path: string;
  lines: string;
  score: number;
  valid: boolean;
  snippet?: string;
}

export interface QueryConfig {
  strategy: "dense" | "bm25" | "hybrid" | "hyde";
  reranking: boolean;
  top_k_retrieval: number;
  top_k_rerank: number;
  include_references: boolean;
  model: string;
  temperature: number;
}

export interface Timings {
  retrieval_ms: number;
  reranking_ms: number;
  context_build_ms: number;
  generation_ms: number;
  total_ms: number;
}

export interface StreamEvent {
  token: string;
  done: boolean;
  sources?: Citation[];
  timings?: Timings;
  error?: string;
  message?: string;
}

export interface Experiment {
  id: string;
  query: string;
  config_a: QueryConfig;
  config_b: QueryConfig;
  result_a?: QueryResult;
  result_b?: QueryResult;
  created_at: string;
}

export interface QueryResult {
  answer: string;
  citations: Citation[];
  timings: Timings;
  config: QueryConfig;
}

// ─── Dependency Graph Types ───

export interface DependencyNode {
  id: string;
  type: "file" | "function" | "class";
  name: string;
  language: string;
  functions?: number;
  classes?: number;
}

export interface DependencyEdge {
  source: string;
  target: string;
  type: "imports" | "calls" | "inherits";
  label: string;
}

export interface DependencyGraph {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
}

export interface ProjectStructure {
  languages: Record<string, number>;
  directories: { path: string; file_count: number; description: string }[];
  entry_points: string[];
  stats: Record<string, number>;
}

// ─── File Tree Types ───

export interface FileNode {
  name: string;
  type: "file" | "directory";
  language?: string;
  size_bytes?: number;
  children_count?: number;
  children?: FileNode[];
}

// ─── API Response Wrappers ───

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  count?: number;
  total?: number;
}

export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string;
    detail?: string;
    suggestion?: string;
  };
}

// ─── Auth Types ───

export interface AuthUser {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
}
