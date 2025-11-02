"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { getProgress, ProgressItem } from "@/lib/progress";
import Link from "next/link";

export default function Progress() {
  const [items, setItems] = useState<ProgressItem[]>([]);
  useEffect(() => {
    setItems(getProgress());
  }, []);

  return (
    <div className="ws-container space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Progress
        </h1>
        <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
          Your recent healing updates
        </p>
      </div>

      {/* Trend Summary */}
      <div className="ws-card p-5">
        <div className="text-lg font-semibold text-slate-800">
          Trend (last {items.length || 1} {items.length === 1 ? "entry" : "entries"})
        </div>
        <div className="mt-3 h-20 w-full rounded-lg bg-blue-50" />
        <p className="mt-2 text-sm text-slate-600">
          {items.length > 0
            ? "A visual summary of your most recent changes."
            : "No data yet — add your first entry to see trends."}
        </p>
      </div>

      {/* No Entries */}
      {items.length === 0 && (
        <p className="text-slate-600 text-base text-center">
          No entries yet — add one from Capture.
        </p>
      )}

      {/* Progress Entries */}
      <div className="space-y-4">
        {items.map((it) => (
          <div key={it.id} className="ws-card p-4">
            <div className="text-slate-900 font-semibold">
              {new Date(it.date).toLocaleString()}
              {typeof it.percentChange === "number" && (
                <span
                  className={`ml-2 ${
                    it.percentChange > 0
                      ? "text-red-500"
                      : "text-blue-600"
                  }`}
                >
                  Size {it.percentChange > 0 ? "↑" : "↓"}{" "}
                  {Math.abs(it.percentChange)}%
                </span>
              )}
            </div>
            {it.note && (
              <div className="mt-1 text-sm text-slate-600">{it.note}</div>
            )}
            {it.imageUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={it.imageUrl}
                alt="wound"
                className="mt-3 max-h-60 w-full rounded-xl object-contain border border-slate-100"
              />
            )}
          </div>
        ))}
      </div>

      {/* Add new entry button */}
      <Button
        asChild
        className="h-12 w-full rounded-xl text-base font-medium mt-2"
      >
        <Link href="/capture">Add new entry</Link>
      </Button>
    </div>
  );
}