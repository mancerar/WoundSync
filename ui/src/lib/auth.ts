import { auth } from "@/firebase/firebase";
import { onAuthStateChanged, type User as FirebaseAuthUser } from "firebase/auth";

export type User = {
  email: string;
  username: string;
};

const KEY = "ws_user";

async function waitForCurrentUser(timeoutMs = 5000): Promise<FirebaseAuthUser | null> {
  const authInstance = auth;
  if (!authInstance) return null;
  if (authInstance.currentUser) return authInstance.currentUser;

  return await new Promise((resolve) => {
    let settled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let unsubscribe = () => {};

    const finish = (user: FirebaseAuthUser | null) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      unsubscribe();
      resolve(user);
    };

    unsubscribe = onAuthStateChanged(authInstance, (user) => {
      finish(user);
    });

    timer = setTimeout(() => {
      finish(authInstance.currentUser);
    }, timeoutMs);
  });
}

export async function getAuthToken(forceRefresh = false): Promise<string | null> {
  const user = await waitForCurrentUser(forceRefresh ? 7000 : 5000);
  if (!user) return null;

  try {
    return await user.getIdToken(forceRefresh);
  } catch {
    return null;
  }
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