// src/lib/wounds.ts
// Frontend API wrapper (kept loose to avoid TS build failures)

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export async function getWoundProfiles(): Promise<any[]> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/wounds`, { cache: "no-store" });
    const json = await res.json();
    return json?.ok ? (json.data ?? []) : [];
  } catch {
    return [];
  }
}

export async function getWoundProfile(id: string): Promise<any | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/wounds/${encodeURIComponent(id)}`, {
      cache: "no-store",
    });
    const json = await res.json();
    return json?.ok ? (json.data ?? null) : null;
  } catch {
    return null;
  }
}

export async function seedPlaceholderData(): Promise<void> {
  try {
    await fetch(`${BACKEND_URL}/api/wounds/seed`, { method: "POST" });
  } catch {
    // ignore
  }
}