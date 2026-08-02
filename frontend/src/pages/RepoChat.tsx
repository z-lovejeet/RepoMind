/**
 * RepoMind — Repository Chat Page
 *
 * Full 3-panel chat interface:
 *   Left:   FileTree sidebar (repo structure)
 *   Center: Chat area (messages + streaming + input)
 *   Right:  CodeViewer panel (source code from citations/file clicks)
 *
 * Reference: Module Design → pages/RepoChat.tsx layout spec
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { useChat } from "../hooks/useChat";
import Navbar from "../components/ui/Navbar";
import FileTree from "../components/repo/FileTree";
import CodeViewer from "../components/repo/CodeViewer";
import ChatInput from "../components/chat/ChatInput";
import ChatMessage from "../components/chat/ChatMessage";
import StreamingResponse from "../components/chat/StreamingResponse";
import Loader from "../components/ui/Loader";
import type { Repo, Citation } from "../types";

interface CodeViewerState {
  code: string;
  language: string;
  filePath: string;
  highlightLines?: [number, number];
}

export default function RepoChat() {
  const { repoId } = useParams<{ repoId: string }>();
  const navigate = useNavigate();

  // ─── Repo details ───
  const [repo, setRepo] = useState<Repo | null>(null);
  const [repoLoading, setRepoLoading] = useState(true);

  // ─── Chat state ───
  const {
    messages,
    loading,
    streaming,
    currentTokens,
    error,
    sendQuery,
    clearChat,
  } = useChat(repoId || "");

  // ─── Code viewer state ───
  const [codeState, setCodeState] = useState<CodeViewerState>({
    code: "",
    language: "",
    filePath: "",
  });

  // ─── Sidebar toggle ───
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // ─── Auto-scroll chat ───
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentTokens]);

  // ─── Load repo details ───
  useEffect(() => {
    if (!repoId) return;
    async function loadRepo() {
      try {
        const res = await apiRequest<Repo>(`/api/repos/${repoId}`);
        setRepo(res.data);
      } catch {
        // Repo not found — redirect
        navigate("/dashboard", { replace: true });
      } finally {
        setRepoLoading(false);
      }
    }
    loadRepo();
  }, [repoId, navigate]);

  // ─── Handle citation click → show in code viewer ───
  const handleCitationClick = useCallback(
    async (citation: Citation) => {
      if (!repoId || !citation.valid) return;

      const lines = citation.lines.split("-");
      const startLine = parseInt(lines[0], 10) || 1;
      const endLine = parseInt(lines[1], 10) || startLine;

      try {
        const res = await apiRequest<{ path: string; content: string }>(
          `/api/repos/${repoId}/file/content?path=${encodeURIComponent(citation.file_path)}`
        );
        setCodeState({
          code: res.data.content,
          language: citation.file_path.endsWith(".py")
            ? "python"
            : citation.file_path.endsWith(".ts") || citation.file_path.endsWith(".tsx")
              ? "typescript"
              : citation.file_path.endsWith(".js") || citation.file_path.endsWith(".jsx")
                ? "javascript"
                : "text",
          filePath: citation.file_path,
          highlightLines: [startLine, endLine],
        });
      } catch {
        setCodeState({
          code: `// Source: ${citation.file_path}\n// Lines: ${citation.lines}\n// Score: ${Math.round(citation.score * 100)}%\n\n// Could not load file content`,
          language: "text",
          filePath: citation.file_path,
          highlightLines: [startLine, endLine],
        });
      }
    },
    [repoId]
  );

  // ─── Handle file tree click ───
  const handleFileSelect = useCallback(
    async (filePath: string) => {
      if (!repoId) return;

      const ext = filePath.split(".").pop() || "";
      const langMap: Record<string, string> = {
        py: "python",
        ts: "typescript",
        tsx: "typescript",
        js: "javascript",
        jsx: "javascript",
        md: "markdown",
        json: "json",
        yaml: "yaml",
        yml: "yaml",
        html: "html",
        css: "css",
      };

      try {
        const res = await apiRequest<{ path: string; content: string }>(
          `/api/repos/${repoId}/file/content?path=${encodeURIComponent(filePath)}`
        );
        setCodeState({
          code: res.data.content,
          language: langMap[ext] || "text",
          filePath,
        });
      } catch {
        setCodeState({
          code: `// File: ${filePath}\n// Failed to load file content`,
          language: langMap[ext] || "text",
          filePath,
        });
      }
    },
    [repoId]
  );

  // ─── Loading state ───
  if (repoLoading) {
    return (
      <div className="repo-chat-page">
        <Navbar />
        <div className="auth-guard-loading">
          <Loader size="lg" />
          <p>Loading repository...</p>
        </div>
      </div>
    );
  }

  if (!repo || !repoId) {
    return (
      <div className="repo-chat-page">
        <Navbar />
        <div className="auth-guard-loading">
          <p>Repository not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="repo-chat-page">
      {/* ─── Header ─── */}
      <div className="repo-chat-header">
        <div className="repo-chat-header-left">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => navigate("/dashboard")}
          >
            ← Back
          </button>
          <h2 className="repo-chat-title">{repo.name}</h2>
          <span className={`badge badge-${repo.status}`}>{repo.status}</span>
        </div>
        <div className="repo-chat-header-right">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? "Hide Files" : "Show Files"}
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={clearChat}
            disabled={messages.length === 0}
          >
            Clear Chat
          </button>
        </div>
      </div>

      {/* ─── 3-Panel Body ─── */}
      <div className={`repo-chat-body ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
        {/* ─── Sidebar ─── */}
        {sidebarOpen && (
          <aside className="repo-chat-sidebar">
            <div className="repo-chat-sidebar-header">
              <h3>Files</h3>
            </div>
            <FileTree repoId={repoId} onFileSelect={handleFileSelect} />
          </aside>
        )}

        {/* ─── Chat Area ─── */}
        <main className="repo-chat-main">
          <div className="chat-messages">
            {messages.length === 0 && !loading && !streaming && (
              <div className="chat-empty">
                <div className="chat-empty-icon">💬</div>
                <h3>Ask anything about this codebase</h3>
                <p>
                  Try questions like "How does authentication work?" or
                  "What does the main entry point do?"
                </p>
              </div>
            )}

            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                onCitationClick={handleCitationClick}
              />
            ))}

            {/* Streaming in progress */}
            {(loading || streaming) && (
              <StreamingResponse tokens={currentTokens} loading={loading} />
            )}

            {/* Error display */}
            {error && (
              <div className="chat-error">
                <span>⚠️</span> {error}
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* ─── Input ─── */}
          <ChatInput
            onSend={(query) => sendQuery(query)}
            disabled={loading || streaming}
          />
        </main>

        {/* ─── Code Panel ─── */}
        <aside className="repo-chat-code">
          <CodeViewer
            code={codeState.code}
            language={codeState.language}
            filePath={codeState.filePath}
            highlightLines={codeState.highlightLines}
          />
        </aside>
      </div>
    </div>
  );
}
