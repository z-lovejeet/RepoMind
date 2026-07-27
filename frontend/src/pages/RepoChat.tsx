/**
 * RepoMind — Repository Chat Page
 *
 * Main chat interface for querying a repository.
 * Layout: Sidebar (FileTree + Settings) | Chat Area | Code Panel
 *
 * Will be fully implemented in Phase 9.
 */

import { useParams } from "react-router-dom";

export default function RepoChat() {
  const { repoId } = useParams<{ repoId: string }>();

  return (
    <div className="repo-chat">
      <header className="repo-chat-header">
        <h1>Repository: {repoId}</h1>
      </header>

      <main className="repo-chat-main">
        <p className="placeholder">
          Chat interface will be implemented in Phase 9 (Chat & Streaming).
        </p>
      </main>
    </div>
  );
}
