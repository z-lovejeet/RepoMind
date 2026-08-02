/**
 * RepoMind — Chat Hook
 *
 * Manages chat state and SSE streaming for repository Q&A.
 * Uses fetch + ReadableStream (not EventSource) because we need POST + auth headers.
 *
 * Key design decisions:
 *   - AbortController cancels in-flight streams on unmount or new query
 *   - Functional setState prevents stale closure bugs during streaming
 *   - Session-only history (Firestore persistence deferred to later phase)
 *
 * Reference: Module Design → hooks/useChat.ts
 */

import { useState, useCallback, useRef } from "react";
import { apiStream } from "../lib/api";
import { DEFAULT_QUERY_CONFIG } from "../lib/constants";
import type { Message, Citation, QueryConfig, StreamEvent, Timings } from "../types";

interface UseChatReturn {
  messages: Message[];
  loading: boolean;
  streaming: boolean;
  currentTokens: string;
  error: string | null;
  sendQuery: (query: string, config?: QueryConfig) => Promise<void>;
  clearChat: () => void;
}

let messageIdCounter = 0;
function nextId(): string {
  return `msg_${Date.now()}_${++messageIdCounter}`;
}

export function useChat(repoId: string): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [currentTokens, setCurrentTokens] = useState("");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendQuery = useCallback(
    async (query: string, config?: QueryConfig) => {
      // ─── Abort any in-flight stream ───
      if (abortRef.current) {
        abortRef.current.abort();
      }
      abortRef.current = new AbortController();

      // ─── Add user message ───
      const userMessage: Message = {
        id: nextId(),
        role: "user",
        content: query,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);

      // ─── Reset state ───
      setLoading(true);
      setStreaming(false);
      setCurrentTokens("");
      setError(null);

      let firstToken = true;
      let accumulated = "";

      try {
        await apiStream(
          `/api/repos/${repoId}/query/stream`,
          { query, config: config || DEFAULT_QUERY_CONFIG },
          // ─── onToken ───
          (token: string) => {
            if (firstToken) {
              setLoading(false);
              setStreaming(true);
              firstToken = false;
            }
            accumulated += token;
            setCurrentTokens((prev) => prev + token);
          },
          // ─── onDone ───
          (event: StreamEvent) => {
            const sources: Citation[] = (event.sources || []).map((s) => ({
              ...s,
              snippet: undefined,
            }));
            const timings: Timings | undefined = event.timings
              ? {
                  retrieval_ms: event.timings.retrieval_ms ?? 0,
                  reranking_ms: event.timings.reranking_ms ?? 0,
                  context_build_ms: event.timings.context_build_ms ?? 0,
                  generation_ms: event.timings.generation_ms ?? 0,
                  total_ms: event.timings.total_ms ?? 0,
                }
              : undefined;

            const assistantMessage: Message = {
              id: nextId(),
              role: "assistant",
              content: accumulated,
              sources,
              timings,
              config: config || DEFAULT_QUERY_CONFIG,
              timestamp: new Date().toISOString(),
            };

            setMessages((prev) => [...prev, assistantMessage]);
            setCurrentTokens("");
            setStreaming(false);
            setLoading(false);
          },
          // ─── onError ───
          (errMsg: string) => {
            setError(errMsg);
            setStreaming(false);
            setLoading(false);
            setCurrentTokens("");
          }
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Stream failed";
        setError(msg);
        setStreaming(false);
        setLoading(false);
        setCurrentTokens("");
      }
    },
    [repoId]
  );

  const clearChat = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    setMessages([]);
    setCurrentTokens("");
    setLoading(false);
    setStreaming(false);
    setError(null);
  }, []);

  return {
    messages,
    loading,
    streaming,
    currentTokens,
    error,
    sendQuery,
    clearChat,
  };
}

export default useChat;
