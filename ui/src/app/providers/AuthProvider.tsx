"use client";

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

// If your firebase.ts exports `auth` even when not configured, keep this import.
// If it exports `auth` as null when missing env vars, this code handles that too.
import { auth } from "@/firebase/firebase";

import {
  onAuthStateChanged,
  setPersistence,
  browserSessionPersistence,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  type ActionCodeSettings,
  signOut as fbSignOut,
} from "firebase/auth";

type AppUser = {
  uid: string;
  email: string | null;
};

type AuthContextType = {
  user: AppUser | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => Promise<string | null>;
  authEnabled: boolean;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider />");
  return ctx;
}

export default function AuthProvider({ children }: { children: ReactNode }) {
  const authEnabled = !!auth;

  const [user, setUser] = useState<AppUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // If Firebase isn’t configured, don’t crash the whole app.
    if (!authEnabled) {
      console.warn("Firebase env vars missing; auth will be disabled for local dev.");
      setLoading(false);
      return;
    }

    let unsub: (() => void) | undefined;

    const init = async () => {
      try {
        await setPersistence(auth!, browserSessionPersistence);
      } catch (error) {
        console.warn("Could not enable Firebase session persistence:", error);
      }

      unsub = onAuthStateChanged(auth!, (u) => {
        if (!u) setUser(null);
        else setUser({ uid: u.uid, email: u.email });
        setLoading(false);
      });
    };

    void init();

    return () => {
      if (unsub) unsub();
    };
  }, [authEnabled]);

  const value = useMemo<AuthContextType>(() => {
    const signIn = async (email: string, password: string) => {
      if (!authEnabled) {
        // Local-dev fallback so UI doesn’t explode
        setUser({ uid: "local-dev", email });
        return;
      }
      await signInWithEmailAndPassword(auth!, email, password);
    };

    const signUp = async (email: string, password: string) => {
      if (!authEnabled) {
        setUser({ uid: "local-dev", email });
        return;
      }
      await createUserWithEmailAndPassword(auth!, email, password);
    };

    const resetPassword = async (email: string) => {
      if (!authEnabled) {
        throw new Error("Password reset email is unavailable while Firebase auth is disabled.");
      }

      const configuredBase = process.env.NEXT_PUBLIC_PASSWORD_RESET_URL?.trim();
      const runtimeBase = typeof window !== "undefined" ? window.location.origin : "";
      const baseUrl = (configuredBase || runtimeBase || "http://localhost:3000").replace(/\/$/, "");
      const actionCodeSettings: ActionCodeSettings = {
        url: `${baseUrl}/reset-password`,
        handleCodeInApp: false,
      };

      await sendPasswordResetEmail(auth!, email, actionCodeSettings);
    };

    const getToken = async () => {
    if (!authEnabled || !auth?.currentUser) return null;
      return await auth.currentUser.getIdToken();
    };

    const signOut = async () => {
      if (!authEnabled) {
        setUser(null);
        return;
      }
      await fbSignOut(auth!);
    };

    return { user, loading, signIn, signUp, resetPassword, signOut, getToken, authEnabled };
  }, [authEnabled, user, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}