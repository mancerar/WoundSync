// ui/src/firebase/firebase.ts
import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

const envTrue = (v?: string) => (v || "").trim().toLowerCase() === "true";
const isPlaceholder = (v?: string) => !v || v.startsWith("your_") || v === "";
const forceDisableAuth = envTrue(process.env.NEXT_PUBLIC_DISABLE_FIREBASE_AUTH);
const hasFirebaseConfig =
  !isPlaceholder(firebaseConfig.apiKey) &&
  !isPlaceholder(firebaseConfig.projectId) &&
  !isPlaceholder(firebaseConfig.authDomain) &&
  !isPlaceholder(firebaseConfig.appId);

let auth: Auth | null = null;

if (forceDisableAuth) {
  console.warn("Firebase auth disabled via NEXT_PUBLIC_DISABLE_FIREBASE_AUTH=true");
} else if (hasFirebaseConfig) {
  const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  auth = getAuth(app);
} else {
  // No Firebase creds -> allow app to run locally without auth
  console.warn("Firebase env vars missing; auth will be disabled for local dev.");
}

export { auth };