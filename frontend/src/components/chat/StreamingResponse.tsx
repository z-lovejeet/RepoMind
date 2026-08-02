/**
 * RepoMind — Streaming Response Component
 *
 * Displays tokens as they arrive from SSE, with a blinking cursor.
 * Shows "Searching codebase..." during retrieval phase.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useEffect, useRef } from "react";

interface StreamingResponseProps {
  tokens: string;
  loading: boolean;
}

export default function StreamingResponse({ tokens, loading }: StreamingResponseProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // ─── Auto-scroll as tokens arrive ───
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [tokens, loading]);

  // ─── Retrieval loading state ───
  if (loading && !tokens) {
    return (
      <div className="chat-message chat-message-assistant">
        <div className="chat-message-avatar">⚡</div>
        <div className="chat-message-content">
          <div className="streaming-searching">
            <span>Searching codebase</span>
            <span className="streaming-dots">
              <span>.</span><span>.</span><span>.</span>
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (!tokens) return null;

  return (
    <div className="chat-message chat-message-assistant" ref={containerRef}>
      <div className="chat-message-avatar">⚡</div>
      <div className="chat-message-content">
        <div className="streaming-response">
          <div className="markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  const codeString = String(children).replace(/\n$/, "");

                  if (match) {
                    return (
                      <SyntaxHighlighter
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{
                          margin: "0.5rem 0",
                          borderRadius: "8px",
                          fontSize: "0.85rem",
                        }}
                      >
                        {codeString}
                      </SyntaxHighlighter>
                    );
                  }

                  return (
                    <code className="inline-code" {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {tokens}
            </ReactMarkdown>
          </div>
          <span className="streaming-cursor">▌</span>
        </div>
      </div>
    </div>
  );
}
