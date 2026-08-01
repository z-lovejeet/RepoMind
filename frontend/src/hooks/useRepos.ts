import { useState, useEffect, useCallback } from "react";
import { apiRequest } from "../lib/api";
import type { Repo } from "../types";

interface UseReposReturn {
  repos: Repo[];
  loading: boolean;
  error: string | null;
  cloning: boolean;
  cloneRepo: (githubUrl: string) => Promise<void>;
  deleteRepo: (repoId: string) => Promise<void>;
  refreshRepos: () => Promise<void>;
}

export function useRepos(): UseReposReturn {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [cloning, setCloning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshRepos = useCallback(async () => {
    try {
      setError(null);
      const res = await apiRequest<Repo[]>("/api/repos");
      setRepos(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load repos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshRepos();
  }, [refreshRepos]);

  const cloneRepo = useCallback(async (githubUrl: string) => {
    try {
      setCloning(true);
      setError(null);
      await apiRequest("/api/repos/clone", {
        method: "POST",
        body: JSON.stringify({ github_url: githubUrl }),
      });
      await refreshRepos();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Clone failed";
      setError(message);
      throw err;
    } finally {
      setCloning(false);
    }
  }, [refreshRepos]);

  const deleteRepo = useCallback(async (repoId: string) => {
    try {
      setError(null);
      await apiRequest(`/api/repos/${repoId}`, { method: "DELETE" });
      setRepos((prev) => prev.filter((r) => r.id !== repoId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
      throw err;
    }
  }, []);

  return { repos, loading, error, cloning, cloneRepo, deleteRepo, refreshRepos };
}

export default useRepos;
