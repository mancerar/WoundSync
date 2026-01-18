"use client";

import React, { useMemo, useState } from "react";

type PredictResponse = {
  ok: boolean;
  detected?: boolean;
  confidence?: number;
  message?: string;
  class?: string;
  assessment?: {
    summary: string;
    urgency: "home" | "soon" | "urgent";
    wound_type: "cut" | "scrape" | "uncertain";
    disclaimer: string;
    next_steps: string[];
    tips: string[];
    watch_for: string[];
    retake_tips?: string[];
    quality?: any;
    context?: any;
  };
  error?: string;
};

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export default function CapturePage() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);

  const urgencyLabel = useMemo(() => {
    const u = result?.assessment?.urgency;
    if (!u) return "";
    if (u === "urgent") return "Urgent (get checked today if worried)";
    if (u === "soon") return "Get checked soon (same/next day if worsening)";
    return "Home care (monitor)";
  }, [result]);

  const urgencyColor = useMemo(() => {
    const u = result?.assessment?.urgency;
    if (u === "urgent") return "#b00020";
    if (u === "soon") return "#b36b00";
    return "#1b6e1b";
  }, [result]);

  const onPickFile = (f: File | null) => {
    setResult(null);
    setFile(f);
    if (!f) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(f);
    setPreviewUrl(url);
  };

  const onAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);

    try {
      const form = new FormData();
      form.append("image", file);

      const res = await fetch(`${BACKEND_URL}/predict?debug=false`, {
        method: "POST",
        body: form,
      });

      const data = (await res.json()) as PredictResponse;
      setResult(data);
    } catch (e: any) {
      setResult({ ok: false, error: e?.message || "Request failed" });
    } finally {
      setLoading(false);
    }
  };

  const onClear = () => {
    setFile(null);
    setPreviewUrl("");
    setResult(null);
  };

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 6 }}>Wound Check (Image Only)</h2>
      <div style={{ color: "#666", marginBottom: 14 }}>
        Upload a photo. Guidance is based on shape + visual cues (not “size in photo”),
        so zoomed-in papercuts won’t automatically be treated as severe.
      </div>

      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          padding: 16,
          border: "1px solid #ddd",
          borderRadius: 12,
          marginBottom: 18,
          background: "#fff",
        }}
      >
        <label
          style={{
            display: "inline-block",
            padding: "10px 14px",
            border: "1px solid #bbb",
            borderRadius: 10,
            cursor: "pointer",
            background: "#f7f7f7",
          }}
        >
          Select / Take Photo
          <input
            type="file"
            accept="image/*"
            capture="environment"
            style={{ display: "none" }}
            onChange={(e) => onPickFile(e.target.files?.[0] || null)}
          />
        </label>

        <button
          onClick={onAnalyze}
          disabled={!file || loading}
          style={{
            padding: "10px 14px",
            borderRadius: 10,
            border: "1px solid #2b59ff",
            background: loading ? "#9bb0ff" : "#2b59ff",
            color: "white",
            cursor: !file || loading ? "not-allowed" : "pointer",
            minWidth: 110,
            fontWeight: 700,
          }}
        >
          {loading ? "Analyzing..." : "Analyze"}
        </button>

        <button
          onClick={onClear}
          disabled={loading}
          style={{
            padding: "10px 14px",
            borderRadius: 10,
            border: "1px solid #bbb",
            background: "#fff",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          Clear
        </button>

        <div style={{ marginLeft: "auto", fontSize: 13, color: "#666" }}>
          Backend: {BACKEND_URL}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <div
          style={{
            border: "1px solid #ddd",
            borderRadius: 12,
            padding: 14,
            background: "#fff",
            minHeight: 420,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 10 }}>Preview</div>
          {previewUrl ? (
            <img
              src={previewUrl}
              alt="preview"
              style={{
                width: "100%",
                borderRadius: 12,
                border: "1px solid #eee",
              }}
            />
          ) : (
            <div style={{ color: "#777", paddingTop: 30 }}>
              Pick a photo to preview it here.
            </div>
          )}
        </div>

        <div
          style={{
            border: "1px solid #ddd",
            borderRadius: 12,
            padding: 14,
            background: "#fff",
            minHeight: 420,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 10 }}>Result</div>

          {!result && (
            <div style={{ color: "#777", paddingTop: 10 }}>
              Analyze to get guidance.
            </div>
          )}

          {result && !result.ok && (
            <div style={{ color: "#b00020" }}>
              {result.error || "Something went wrong."}
            </div>
          )}

          {result && result.ok && result.detected === false && (
            <div>
              <div style={{ fontWeight: 800, marginBottom: 6 }}>
                Not confident enough
              </div>
              <div style={{ color: "#333" }}>
                {result.message || "Try retaking with better light and focus."}
              </div>
              {typeof result.confidence === "number" && (
                <div style={{ marginTop: 10, color: "#666" }}>
                  Confidence: {Math.round(result.confidence * 100)}%
                </div>
              )}
            </div>
          )}

          {result && result.ok && result.detected === true && result.assessment && (
            <div>
              <div style={{ fontWeight: 900, fontSize: 18, marginBottom: 8 }}>
                {result.assessment.summary}
              </div>

              <div
                style={{
                  display: "inline-block",
                  padding: "6px 10px",
                  borderRadius: 999,
                  background: urgencyColor,
                  color: "white",
                  fontWeight: 800,
                  fontSize: 12,
                  marginBottom: 12,
                }}
              >
                {urgencyLabel}
              </div>

              {typeof result.confidence === "number" && (
                <div style={{ marginBottom: 10, color: "#666" }}>
                  Detection confidence: {Math.round(result.confidence * 100)}%
                </div>
              )}

              {result.assessment.retake_tips?.length ? (
                <>
                  <div style={{ marginTop: 10, fontWeight: 800 }}>Retake tips</div>
                  <ul style={{ marginTop: 6 }}>
                    {result.assessment.retake_tips.map((t, i) => (
                      <li key={`rt-${i}`}>{t}</li>
                    ))}
                  </ul>
                </>
              ) : null}

              <div style={{ marginTop: 10, fontWeight: 800 }}>Next steps</div>
              <ul style={{ marginTop: 6 }}>
                {result.assessment.next_steps.map((t, i) => (
                  <li key={`ns-${i}`}>{t}</li>
                ))}
              </ul>

              <div style={{ marginTop: 10, fontWeight: 800 }}>Tips</div>
              <ul style={{ marginTop: 6 }}>
                {result.assessment.tips.map((t, i) => (
                  <li key={`tip-${i}`}>{t}</li>
                ))}
              </ul>

              <div style={{ marginTop: 10, fontWeight: 800 }}>Watch for</div>
              <ul style={{ marginTop: 6 }}>
                {result.assessment.watch_for.map((t, i) => (
                  <li key={`wf-${i}`}>{t}</li>
                ))}
              </ul>

              <div style={{ marginTop: 12, color: "#666", fontSize: 12 }}>
                {result.assessment.disclaimer}
              </div>

              <details style={{ marginTop: 12 }}>
                <summary style={{ cursor: "pointer", fontWeight: 700 }}>
                  Why the app decided this (for demo / transparency)
                </summary>
                <pre style={{ whiteSpace: "pre-wrap", marginTop: 10, fontSize: 12 }}>
                  {JSON.stringify(
                    {
                      wound_type: result.assessment.wound_type,
                      quality: result.assessment.quality,
                      context: result.assessment.context,
                    },
                    null,
                    2
                  )}
                </pre>
              </details>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}