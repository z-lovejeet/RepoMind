/**
 * RepoMind — Chat Message Component
 *
 * Renders a single user or assistant message.
 * Assistant messages use react-markdown for rich formatting.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { Message, Citation } from "../../types";
import SourceCitation from "./SourceCitation";

interface ChatMessageProps {
  message: Message;
  onCitationClick?: (citation: Citation) => void;
}

export default function ChatMessage({ message, onCitationClick }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`chat-message ${isUser ? "chat-message-user" : "chat-message-assistant"}`}>
      {/* ─── Avatar ─── */}
      <div className="chat-message-avatar">
        {isUser ? "👤" : "⚡"}
      </div>

      {/* ─── Content ─── */}
      <div className="chat-message-content">
        {isUser ? (
          <p>{message.content}</p>
        ) : (
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
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* ─── Sources ─── */}
        {message.sources && message.sources.length > 0 && (
          <div className="source-citations-list">
            <span className="source-citations-label">Sources:</span>
            {message.sources.map((citation) => (
              <SourceCitation
                key={citation.index}
                citation={citation}
                onClick={() => onCitationClick?.(citation)}
              />
            ))}
          </div>
        )}

        {/* ─── Timings ─── */}
        {message.timings && (
          <div className="timing-footer">
            <span className="timing-stat">
              🔍 {Math.round(message.timings.retrieval_ms)}ms retrieval
            </span>
            <span className="timing-stat">
              ✨ {Math.round(message.timings.generation_ms)}ms generation
            </span>
            <span className="timing-stat">
              ⏱ {Math.round(message.timings.total_ms)}ms total
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
