import { useState } from "react";
import Loader from "../ui/Loader";

interface RepoUploaderProps {
  onClone: (githubUrl: string) => Promise<void>;
  cloning: boolean;
  repoCount: number;
  maxRepos: number;
}

export default function RepoUploader({ onClone, cloning, repoCount, maxRepos }: RepoUploaderProps) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const atLimit = repoCount >= maxRepos;

  const validateUrl = (value: string): boolean => {
    if (!value.startsWith("https://github.com/")) {
      setError("Only public GitHub URLs are supported (https://github.com/...)");
      return false;
    }
    const parts = value.replace("https://github.com/", "").split("/");
    if (parts.length < 2 || !parts[0] || !parts[1]) {
      setError("URL must be in format: https://github.com/owner/repo");
      return false;
    }
    setError(null);
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateUrl(url)) return;

    try {
      await onClone(url.trim());
      setUrl("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Clone failed");
    }
  };

  return (
    <div className="card repo-uploader">
      <div className="repo-uploader-header">
        <h3>Add Repository</h3>
        <span className="repo-count">
          {repoCount} / {maxRepos} repos
        </span>
      </div>

      <form onSubmit={handleSubmit} className="repo-uploader-form">
        <div className="repo-uploader-input-group">
          <input
            type="url"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (error) setError(null);
            }}
            placeholder="https://github.com/owner/repo"
            className="repo-uploader-input"
            disabled={cloning || atLimit}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={cloning || !url.trim() || atLimit}
          >
            {cloning ? (
              <>
                <Loader size="sm" />
                Cloning & Indexing...
              </>
            ) : (
              "Clone & Index"
            )}
          </button>
        </div>

        {error && <p className="repo-uploader-error">{error}</p>}
        {atLimit && (
          <p className="repo-uploader-error">
            Repository limit reached. Delete a repo to add a new one.
          </p>
        )}
      </form>
    </div>
  );
}
