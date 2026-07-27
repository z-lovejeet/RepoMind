/**
 * RepoMind — Constants
 *
 * Application-wide constants and default configurations.
 *
 * Reference: Module Design → Section 17 (lib/constants.ts)
 */

import type { QueryConfig } from "../types";

/** Backend API base URL */
export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

/** Default pipeline configuration for queries */
export const DEFAULT_QUERY_CONFIG: QueryConfig = {
  strategy: "hybrid",
  reranking: true,
  top_k_retrieval: 20,
  top_k_rerank: 5,
  include_references: true,
  model: "gpt-4o-mini",
  temperature: 0.1,
};

/** Available retrieval strategies */
export const SUPPORTED_STRATEGIES = [
  "dense",
  "bm25",
  "hybrid",
  "hyde",
] as const;

/** Available LLM models */
export const SUPPORTED_MODELS = ["gpt-4o-mini", "ollama"] as const;

/** App metadata */
export const APP_NAME = "RepoMind";
export const APP_VERSION = "1.0.0";
export const APP_DESCRIPTION =
  "AI-Powered Repository Intelligence. Upload a repo, ask anything.";
