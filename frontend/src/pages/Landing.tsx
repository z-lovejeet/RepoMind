/**
 * RepoMind — Landing Page
 *
 * Public page shown to unauthenticated users.
 * Contains product description and login buttons.
 *
 * Will be fully designed in Phase 8 with Stitch MCP.
 */

import { APP_NAME, APP_DESCRIPTION } from "../lib/constants";

export default function Landing() {
  return (
    <div className="landing">
      <header className="landing-header">
        <h1>{APP_NAME}</h1>
        <p className="landing-tagline">{APP_DESCRIPTION}</p>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <h2>Understand any codebase in minutes</h2>
          <p>
            Upload a GitHub repository and ask questions about its
            architecture, authentication flow, routing system, or any
            implementation detail. Get answers grounded in actual source code.
          </p>
          <div className="landing-actions">
            <button className="btn btn-primary" disabled>
              Sign in with Google (Phase 8)
            </button>
            <button className="btn btn-secondary" disabled>
              Sign in with GitHub (Phase 8)
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
