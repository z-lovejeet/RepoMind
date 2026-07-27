/**
 * RepoMind — Application Entry Point
 *
 * Mounts the React app to the DOM.
 * Imports global CSS design system.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
