/**
 * RepoMind — Landing Page
 *
 * Public page shown to unauthenticated users.
 * Contains product hero, feature highlights, and sign-in button.
 * Auto-redirects to /dashboard if already signed in.
 *
 * Reference: PRD → Section 2 (Product Vision)
 */

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import LoginButton from "../components/auth/LoginButton";
import { APP_NAME } from "../lib/constants";

export default function Landing() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && user) {
      navigate("/dashboard", { replace: true });
    }
  }, [user, loading, navigate]);

  return (
    <div className="landing">
      {/* ─── Hero Section ─── */}
      <header className="landing-header">
        <div className="landing-logo">⚡</div>
        <h1>{APP_NAME}</h1>
        <p className="landing-tagline">
          AI-Powered Repository Intelligence
        </p>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <h2>Understand any codebase in minutes</h2>
          <p>
            Upload a GitHub repository and ask questions about its
            architecture, authentication flow, routing system, or any
            implementation detail. Get answers grounded in actual source code
            with file-level citations.
          </p>
          <div className="landing-actions">
            <LoginButton />
          </div>
        </section>

        {/* ─── Feature Cards ─── */}
        <section className="landing-features">
          <div className="feature-card">
            <div className="feature-icon">🧬</div>
            <h3>Code-Aware RAG</h3>
            <p>
              AST-based parsing understands functions, classes, and imports.
              Unlike generic tools, RepoMind never breaks code mid-function.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🔍</div>
            <h3>Multi-Strategy Retrieval</h3>
            <p>
              Hybrid search combines dense vectors, BM25 keywords, and
              cross-encoder reranking for production-grade answer quality.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🏗️</div>
            <h3>Dependency Intelligence</h3>
            <p>
              Understands who calls what. Answers like "How does auth work?"
              trace the full call chain across files.
            </p>
          </div>
        </section>

        {/* ─── How It Works ─── */}
        <section className="landing-steps">
          <h2>How it works</h2>
          <div className="steps-grid">
            <div className="step">
              <div className="step-number">1</div>
              <h4>Paste a GitHub URL</h4>
              <p>Public repos only. We clone and index the entire codebase.</p>
            </div>
            <div className="step">
              <div className="step-number">2</div>
              <h4>Wait for indexing</h4>
              <p>Files are parsed, chunked, embedded, and indexed in ~30 seconds.</p>
            </div>
            <div className="step">
              <div className="step-number">3</div>
              <h4>Ask anything</h4>
              <p>Get grounded answers with source citations and code snippets.</p>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <p>Built for developers who read more code than they write.</p>
      </footer>
    </div>
  );
}
