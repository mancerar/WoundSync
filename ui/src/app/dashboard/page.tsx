"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getUser } from "@/lib/auth";
import { getProgress, ProgressItem } from "@/lib/progress";
import { Button } from "@/components/ui/button";

export default function Dashboard() {
  const [username, setUsername] = useState<string | null>(null);
  const [items, setItems] = useState<ProgressItem[]>([]);

  useEffect(() => {
    setUsername(getUser()?.username ?? null);
    setItems(getProgress());
  }, []);

  const {
    totalPhotos,
    lastUpdateText,
    healedPct,
    daysTracked,
    avgIntervalDays,
    insightText,
    nextUploadText,
    randomTip,
  } = useMemo(() => {
   
    if (!items.length) {
      return {
        totalPhotos: 0,
        lastUpdateText: "No uploads yet",
        healedPct: 0,
        daysTracked: 0,
        avgIntervalDays: 0,
        insightText:
          "No trend yet — add your first photo to start tracking improvement.",
        nextUploadText: "As soon as you capture your first photo",
        randomTip: "Use consistent lighting and distance for each photo.",
      };
    }
    const sorted = [...items].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );
    const first = sorted[0];
    const last = sorted[sorted.length - 1];
    const totalPhotos = sorted.length;
    const lastUpdateText = new Date(last.date).toLocaleString();
    const healedPct =
      typeof last.percentChange === "number"
        ? Math.max(0, Math.min(100, 100 - Math.max(0, -last.percentChange)))
        : 72;

    const msDay = 24 * 60 * 60 * 1000;
    const daysTracked = Math.max(
      1,
      Math.ceil(
        (new Date(last.date).getTime() - new Date(first.date).getTime()) / msDay
      )
    );

    let avgIntervalDays = 0;
    if (sorted.length > 1) {
      let sum = 0;
      for (let i = 1; i < sorted.length; i++) {
        sum +=
          (new Date(sorted[i].date).getTime() -
            new Date(sorted[i - 1].date).getTime()) /
          msDay;
      }
      avgIntervalDays = +(sum / (sorted.length - 1)).toFixed(1);
    }

    const sevenDaysAgo = new Date(Date.now() - 7 * msDay);
    const last7 = sorted.filter((it) => new Date(it.date) >= sevenDaysAgo);
    const deltas = last7
      .map((it) => it.percentChange)
      .filter((n): n is number => typeof n === "number");
    const avgDelta =
      deltas.length ? deltas.reduce((a, b) => a + b, 0) / deltas.length : 0;

    const trend =
      deltas.length === 0
        ? "Insufficient data this week"
        : avgDelta < 0
        ? "Improving"
        : avgDelta > 0
        ? "Worsening"
        : "Stable";
    const insightText =
      deltas.length === 0
        ? "No new analysis in the last 7 days."
        : `${trend} over the last 7 days (avg change ${avgDelta.toFixed(1)}%).`;

    const next = new Date(new Date(last.date).getTime() + 2 * msDay);
    const nextUploadText = `Suggested next upload: ${next.toLocaleDateString()}`;

    const tips = [
      "Clean gently. Keep area dry.",
      "Upload a photo every 2–3 days.",
      "Use consistent lighting and distance.",
      "Include a reference marker for size.",
    ];
    const randomTip = tips[Math.floor(Math.random() * tips.length)];

    return {
      totalPhotos,
      lastUpdateText,
      healedPct,
      daysTracked,
      avgIntervalDays,
      insightText,
      nextUploadText,
      randomTip,
    };
  }, [items]);

  return (
    <div className="ws-container space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Dashboard
        </h1>
        <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
          {username ? `Your latest healing status: ${username}` : "Your latest healing status"}
        </p>
      </div>

      {/* Healing Progress */}
      <div className="ws-card p-5">
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-lg font-semibold text-slate-800">
              Healing progress
            </div>
            <div className="text-sm text-slate-500">
              Last update: {lastUpdateText}
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-blue-600">
              {healedPct}%
            </div>
            <div className="text-sm text-slate-500">Healed</div>
          </div>
        </div>
        <div className="mt-4 h-2 w-full rounded-full bg-slate-200">
          <div
            className="h-2 rounded-full bg-blue-600 transition-all"
            style={{ width: `${Math.min(100, Math.max(0, healedPct))}%` }}
          />
        </div>
      </div>

      {/* Quick Stats */}
      <div className="ws-card p-5">
        <div className="grid grid-cols-3 gap-3 text-center sm:text-left sm:grid-cols-3">
          <div>
            <div className="text-2xl font-semibold text-slate-900">
              {totalPhotos}
            </div>
            <div className="text-sm text-slate-600">Photos tracked</div>
          </div>
          <div>
            <div className="text-2xl font-semibold text-slate-900">
              {daysTracked}
            </div>
            <div className="text-sm text-slate-600">Days tracked</div>
          </div>
          <div>
            <div className="text-2xl font-semibold text-slate-900">
              {avgIntervalDays || "—"}
            </div>
            <div className="text-sm text-slate-600">Avg interval (days)</div>
          </div>
        </div>
      </div>

      {/* Insights */}
      <div className="ws-card p-5">
        <div className="text-lg font-semibold text-slate-800">
          Your Healing Insights
        </div>
        <p className="mt-1 text-slate-600">{insightText}</p>
      </div>

      {/* Next Step and Tips */}
      <div className="ws-card p-5">
        <div className="text-lg font-semibold text-slate-800">Next step</div>
        <p className="mt-1 text-slate-600">{nextUploadText}</p>
        <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50 px-4 py-2 text-slate-700">
          💡 Tip: {randomTip}
        </div>
      </div>

      {/* Navigation */}
      <div className="grid gap-3">
        <Button
          asChild
          size="lg"
          className="h-12 rounded-xl text-base font-medium"
        >
          <Link href="/capture">Capture / Upload</Link>
        </Button>
        <Button
          asChild
          variant="outline"
          className="h-12 rounded-xl text-base font-medium"
        >
          <Link href="/progress">Progress Timeline</Link>
        </Button>
        <Button
          asChild
          variant="outline"
          className="h-12 rounded-xl text-base font-medium"
        >
          <Link href="/tips">Tips & Guidance</Link>
        </Button>
        <Button
          asChild
          variant="outline"
          className="h-12 rounded-xl text-base font-medium"
        >
          <Link href="/profile">Profile</Link>
        </Button>
      </div>
    </div>
  );
}