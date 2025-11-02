"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { addProgress } from "@/lib/progress";

export default function Capture() {
  const [preview, setPreview] = useState<string | null>(null);
  const [note, setNote] = useState("");

  async function onUpload() {
    if (!preview) return alert("Please take or select a photo first.");
    addProgress({
      id: crypto.randomUUID(),
      date: new Date().toISOString(),
      note,
      percentChange: undefined,
      imageUrl: preview,
    });
    alert("Saved to Progress Timeline.");
    window.location.href = "/progress";
  }

  return (
    <div className="ws-container space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Capture
        </h1>
        <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
          Good lighting works best for accurate tracking
        </p>
      </div>

      {/* Camera Preview */}
      <div className="overflow-hidden rounded-2xl bg-slate-900 aspect-[3/4] grid place-items-center ws-card p-0">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={preview}
            alt="preview"
            className="h-full w-full object-contain"
          />
        ) : (
          <span className="text-slate-300 text-base">Camera preview</span>
        )}
      </div>

      <p className="text-sm text-slate-600 text-center">
        Center the wound clearly and include a reference marker.
      </p>

      {/* Buttons */}
      <div className="grid grid-cols-2 gap-3">
        <label className="cursor-pointer">
          <input
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setPreview(URL.createObjectURL(f));
            }}
          />
          <Button className="h-12 w-full rounded-xl" asChild>
            <span>Open Camera</span>
          </Button>
        </label>

        <Button
          variant="outline"
          className="h-12 w-full rounded-xl"
          onClick={() => setPreview(null)}
        >
          Retake
        </Button>
      </div>

      {/* Notes */}
      <textarea
        className="w-full rounded-xl border border-slate-200 p-3 text-base focus:ring-2 focus:ring-blue-100 focus:outline-none"
        placeholder="Add a quick note (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={3}
      />

      {/* Upload */}
      <Button
        className="h-12 w-full rounded-xl text-base font-semibold"
        onClick={onUpload}
      >
        Upload
      </Button>
    </div>
  );
}