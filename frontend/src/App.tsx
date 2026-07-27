/**
 * RepoMind — Root Application Component
 *
 * Sets up React Router with 4 routes:
 *   /              → Landing page
 *   /dashboard     → User's repos (protected)
 *   /repo/:repoId  → Chat interface (protected)
 *   /experiments   → A/B comparison (protected)
 *
 * Reference: System Architecture → Section 4 (Frontend Architecture)
 */

import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import RepoChat from "./pages/RepoChat";
import Experiments from "./pages/Experiments";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/repo/:repoId" element={<RepoChat />} />
        <Route path="/experiments" element={<Experiments />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
