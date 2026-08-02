/**
 * RepoMind — Code Viewer Component
 *
 * Syntax-highlighted code display panel.
 * Shows source code when a citation or file tree item is clicked.
 */

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useState } from "react";

interface CodeViewerProps {
  code: string;
  language: string;
  filePath: string;
  highlightLines?: [number, number];
}

export default function CodeViewer({
  code,
  language,
  filePath,
  highlightLines,
}: CodeViewerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may not be available
    }
  };

  if (!code) {
    return (
      <div className="code-viewer">
        <div className="code-viewer-empty">
          <span className="code-viewer-empty-icon">📝</span>
          <p>Click a citation or file to view code</p>
        </div>
      </div>
    );
  }

  return (
    <div className="code-viewer">
      {/* ─── Header ─── */}
      <div className="code-viewer-header">
        <span className="code-viewer-path">{filePath}</span>
        <button
          className="btn btn-sm btn-secondary code-viewer-copy"
          onClick={handleCopy}
        >
          {copied ? "✓ Copied" : "Copy"}
        </button>
      </div>

      {/* ─── Code ─── */}
      <SyntaxHighlighter
        language={language || "text"}
        style={oneDark}
        showLineNumbers
        wrapLines
        lineProps={(lineNumber: number) => {
          const style: React.CSSProperties = {};
          if (
            highlightLines &&
            lineNumber >= highlightLines[0] &&
            lineNumber <= highlightLines[1]
          ) {
            style.backgroundColor = "rgba(108, 92, 231, 0.15)";
            style.borderLeft = "3px solid var(--color-accent)";
            style.paddingLeft = "0.5rem";
          }
          return { style };
        }}
        customStyle={{
          margin: 0,
          borderRadius: "0 0 12px 12px",
          fontSize: "0.85rem",
          maxHeight: "calc(100vh - 180px)",
          overflow: "auto",
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
