// src/lib/auth.ts

import { auth } from "@/firebase/firebase";
export async function getAuthToken(): Promise<string | null> {
  if (!auth) return null; // Auth not configured
  
  const user = auth.currentUser;
  if (!user) return null;

  return await user.getIdToken(true);
}
export type User = {
  email: string;
  username: string;
};

const KEY = "ws_user";

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

// Merge-write so you can set username later without losing email (or vice-versa)
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