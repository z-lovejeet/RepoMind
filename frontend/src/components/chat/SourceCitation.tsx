/**
 * RepoMind — Source Citation Component
 *
 * Compact citation card showing file path, line range, and relevance score.
 * Clickable to open the file in the CodeViewer panel.
 */

import type { Citation } from "../../types";

interface SourceCitationProps {
  citation: Citation;
  onClick: () => void;
}

function scoreColor(score: number): string {
  if (score >= 0.8) return "var(--color-success)";
  if (score >= 0.5) return "var(--color-warning)";
  return "var(--color-error)";
}

export default function SourceCitation({ citation, onClick }: SourceCitationProps) {
  return (
    <button
      className={`source-citation ${!citation.valid ? "source-citation-invalid" : ""}`}
      onClick={onClick}
      title={
        citation.valid
          ? `Open ${citation.file_path}:${citation.lines}`
          : "File not found in repository"
      }
    >
      <span className="source-citation-index">[{citation.index}]</span>
      <span className={`source-citation-path ${!citation.valid ? "strikethrough" : ""}`}>
        {citation.file_path}
      </span>
      <span className="source-citation-lines">:{citation.lines}</span>
      <span
        className="source-citation-score"
        style={{ color: scoreColor(citation.score) }}
      >
        {Math.round(citation.score * 100)}%
      </span>
    </button>
  );
}
