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

const apiKey = import.meta.env.VITE_FIREBASE_API_KEY;
const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;

const isDev = !apiKey || !projectId || projectId === "your-project-id" || apiKey === "your-api-key";

const dummyConfig = {
  apiKey: "AIzaSyDummyKeyForDevModeOnly12345",
  authDomain: "dev.firebaseapp.com",
  projectId: "dev-project",
  storageBucket: "dev.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:123456789",
};

const firebaseConfig = isDev
  ? dummyConfig
  : {
      apiKey,
      authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
      projectId,
      storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
      messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
      appId: import.meta.env.VITE_FIREBASE_APP_ID,
    };

// Initialize Firebase safely
let app: any;
let auth: any;
let db: any;
let storage: any;

try {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  db = getFirestore(app);
  storage = getStorage(app);
} catch (e) {
  console.warn("[Firebase] Dev mode stub initialized:", e);
  app = null;
  auth = { currentUser: null };
  db = null;
  storage = null;
}

export { auth, db, storage };

// ─── Auth Providers ───
export const googleProvider = new GoogleAuthProvider();
export const githubProvider = new GithubAuthProvider();

export default app;

