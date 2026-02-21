// ui/src/lib/progress.ts
export type ProgressItem = {
  id: string;
  date: string;          // ISO
  note?: string;
  percentChange?: number;
  imageUrl?: string;
};

const KEY = "ws_progress";

export function getProgress(): ProgressItem[] {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
}

export function saveProgress(items: ProgressItem[]) {
  localStorage.setItem(KEY, JSON.stringify(items));
}

export function addProgress(item: ProgressItem) {
  const cur = getProgress();
  cur.unshift(item);
  saveProgress(cur);
}

export function clearProgress() {
  localStorage.removeItem(KEY);
}