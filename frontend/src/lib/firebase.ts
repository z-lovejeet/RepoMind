/**
 * RepoMind — Firebase SDK Initialization
 *
 * Initializes Firebase with environment variables from Vite.
 * Exports auth, firestore, and storage instances for use across the app.
 *
 * Why environment variables?
 *   Firebase config is NOT secret (it's in client-side code),
 *   but keeping it in env vars makes deployment configuration clean.
 *
 * Reference: System Architecture → Section 6 (Firebase Architecture)
 */

import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, GithubAuthProvider } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
import { getStorage } from "firebase/storage";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// ─── Export Firebase services ───
export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);

// ─── Auth Providers ───
export const googleProvider = new GoogleAuthProvider();
export const githubProvider = new GithubAuthProvider();

export default app;
