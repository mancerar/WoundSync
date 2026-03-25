// src/lib/auth.ts

import { auth } from "@/firebase/firebase";
import { onAuthStateChanged, type User as FirebaseAuthUser } from "firebase/auth";

export type User = {
  email: string;
  username: string;
};

const KEY = "ws_user";

async function waitForCurrentUser(timeoutMs = 1500): Promise<FirebaseAuthUser | null> {
  const authInstance = auth;
  if (!authInstance) return null;
  if (authInstance.currentUser) return authInstance.currentUser;

  return await new Promise((resolve) => {
    let settled = false;

    const finish = (user: FirebaseAuthUser | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      unsubscribe();
      resolve(user);
    };

    const unsubscribe = onAuthStateChanged(authInstance, (user) => {
      finish(user);
    });

    const timer = setTimeout(() => {
      finish(authInstance.currentUser);
    }, timeoutMs);
  });
}

export async function getAuthToken(): Promise<string | null> {
  const user = await waitForCurrentUser();
  if (!user) return null;
  return await user.getIdToken(true);
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function setUser(partial: Partial<User>) {
  if (typeof window === "undefined") return;

  const prev = getUser() ?? { email: "", username: "" };
  const next = { ...prev, ...partial } as User;
  localStorage.setItem(KEY, JSON.stringify(next));
}

export function clearUser() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(KEY);
}