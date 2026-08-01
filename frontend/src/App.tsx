/**
 * RepoMind — Root Application Component
 *
 * Sets up React Router with 4 routes:
 *   /              → Landing page (public)
 *   /dashboard     → User's repos (protected)
 *   /repo/:repoId  → Chat interface (protected)
 *   /experiments   → A/B comparison (protected)
 *
 * Authentication is provided via AuthProvider context.
 * Protected routes are wrapped in AuthGuard.
 *
 * Reference: System Architecture → Section 4 (Frontend Architecture)
 */

import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth";
import AuthGuard from "./components/auth/AuthGuard";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import RepoChat from "./pages/RepoChat";
import Experiments from "./pages/Experiments";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route
            path="/dashboard"
            element={
              <AuthGuard>
                <Dashboard />
              </AuthGuard>
            }
          />
          <Route
            path="/repo/:repoId"
            element={
              <AuthGuard>
                <RepoChat />
              </AuthGuard>
            }
          />
          <Route
            path="/experiments"
            element={
              <AuthGuard>
                <Experiments />
              </AuthGuard>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
