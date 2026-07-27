/**
 * RepoMind — API Client
 *
 * Fetch wrapper for communicating with the FastAPI backend.
 * Automatically injects Firebase JWT token in Authorization header.
 *
 * Reference: Module Design → Section 17 (lib/api.ts)
 */

import { auth } from "./firebase";
import { API_BASE_URL } from "./constants";
import type { ApiResponse, StreamEvent } from "../types";

/**
 * Get a fresh Firebase JWT token for the current user.
 * Returns empty string if not authenticated.
 */
async function getAuthToken(): Promise<string> {
  const user = auth.currentUser;
  if (!user) return "";
  return user.getIdToken();
}

/**
 * Make an authenticated API request to the backend.
 *
 * @param path  - API path (e.g., "/api/repos")
 * @param options - Standard fetch options
 * @returns Parsed JSON response
 * @throws Error with the API error message
 */
export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const token = await getAuthToken();

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({
      error: { code: "UNKNOWN", message: response.statusText },
    }));
    throw new Error(errorData.error?.message || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Stream SSE events from a POST endpoint.
 *
 * Uses fetch + ReadableStream (not EventSource, which doesn't support POST).
 *
 * @param path - API path (e.g., "/api/repos/{id}/query/stream")
 * @param body - Request body object
 * @param onToken - Callback for each token event
 * @param onDone - Callback when stream completes
 * @param onError - Callback on error
 */
export async function apiStream(
  path: string,
  body: object,
  onToken: (token: string) => void,
  onDone: (event: StreamEvent) => void,
  onError: (error: string) => void
): Promise<void> {
  const token = await getAuthToken();

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok || !response.body) {
    const errorData = await response.json().catch(() => ({
      error: { message: "Stream failed" },
    }));
    onError(errorData.error?.message || `HTTP ${response.status}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split("\n");

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;

      try {
        const event: StreamEvent = JSON.parse(line.slice(6));

        if (event.error) {
          onError(event.message || event.error);
          return;
        }

        if (event.done) {
          onDone(event);
          return;
        }

        onToken(event.token);
      } catch {
        // Skip malformed SSE lines
      }
    }
  }
}
