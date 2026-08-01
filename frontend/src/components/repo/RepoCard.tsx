import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Repo } from "../../types";

interface RepoCardProps {
  repo: Repo;
  onDelete: (repoId: string) => Promise<void>;
}

export default function RepoCard({ repo, onDelete }: RepoCardProps) {
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleDelete = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setDeleting(true);
    try {
      await onDelete(repo.id);
    } catch {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  const statusClass = `badge badge-${repo.status}`;

  return (
    <div className="card repo-card">
      <div className="repo-card-header">
        <div>
          <h3 className="repo-card-name">{repo.name}</h3>
          {repo.github_url && (
            <a
              href={repo.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="repo-card-url"
            >
              {repo.github_url.replace("https://github.com/", "")}
            </a>
          )}
        </div>
        <span className={statusClass}>{repo.status}</span>
      </div>

      {repo.status === "ready" && (
        <div className="repo-card-stats">
          {repo.file_count != null && (
            <span className="repo-card-stat">
              📄 {repo.file_count} files
            </span>
          )}
          {repo.total_chunks != null && (
            <span className="repo-card-stat">
              🧩 {repo.total_chunks} chunks
            </span>
          )}
        </div>
      )}

      {repo.languages.length > 0 && (
        <div className="repo-card-languages">
          {repo.languages.map((lang) => (
            <span key={lang} className="repo-card-lang-tag">
              {lang}
            </span>
          ))}
        </div>
      )}

      <div className="repo-card-actions">
        <button
          className="btn btn-primary btn-sm"
          onClick={() => navigate(`/repo/${repo.id}`)}
          disabled={repo.status !== "ready"}
        >
          Ask Questions
        </button>
        <button
          className={`btn btn-sm ${confirmDelete ? "btn-danger" : "btn-secondary"}`}
          onClick={handleDelete}
          disabled={deleting}
          onBlur={() => setConfirmDelete(false)}
        >
          {deleting ? "Deleting..." : confirmDelete ? "Confirm Delete" : "Delete"}
        </button>
      </div>
    </div>
  );
}
