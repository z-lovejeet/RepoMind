/**
 * RepoMind — Dashboard Page
 *
 * Protected page showing user's repositories.
 * Users can clone new repos and manage existing ones.
 *
 * Reference: PRD → Section 10 (Core Features)
 */

import Navbar from "../components/ui/Navbar";
import RepoUploader from "../components/repo/RepoUploader";
import RepoCard from "../components/repo/RepoCard";
import Loader from "../components/ui/Loader";
import { useRepos } from "../hooks/useRepos";
import { MAX_REPOS } from "../lib/constants";

export default function Dashboard() {
  const { repos, loading, error, cloning, cloneRepo, deleteRepo } = useRepos();

  return (
    <div className="dashboard-page">
      <Navbar />

      <div className="dashboard">
        <header className="dashboard-header">
          <div>
            <h1>My Repositories</h1>
            <p>Clone a GitHub repository to start asking questions about its codebase.</p>
          </div>
        </header>

        {/* ─── Repo Uploader ─── */}
        <RepoUploader
          onClone={cloneRepo}
          cloning={cloning}
          repoCount={repos.length}
          maxRepos={MAX_REPOS}
        />

        {/* ─── Error Display ─── */}
        {error && (
          <div className="dashboard-error">
            <span>⚠️</span> {error}
          </div>
        )}

        {/* ─── Repo Grid ─── */}
        {loading ? (
          <div className="dashboard-loading">
            <Loader size="lg" />
            <p>Loading repositories...</p>
          </div>
        ) : repos.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📂</div>
            <h3>No repositories yet</h3>
            <p>
              Paste a GitHub URL above to clone and index your first repository.
              Try a small repo like{" "}
              <code>https://github.com/pallets/markupsafe</code>
            </p>
          </div>
        ) : (
          <div className="repo-grid">
            {repos.map((repo) => (
              <RepoCard key={repo.id} repo={repo} onDelete={deleteRepo} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
