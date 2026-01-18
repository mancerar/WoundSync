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
    photo_note?: string;
    why_flagged?: string[];
    disclaimer: string;
    next_steps: string[];
    tips: string[];
    watch_for: string[];
    signals?: any;
  };
  error?: string;
};

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export default function CapturePage() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);

  // Optional context (for realism)
  const [bleedingNotStop, setBleedingNotStop] = useState(false);
  const [biteDirty, setBiteDirty] = useState(false);
  const [highRisk, setHighRisk] = useState(false);
  const [numbWeak, setNumbWeak] = useState(false);
  const [onHandFaceJoint, setOnHandFaceJoint] = useState(false);

  const urgencyLabel = useMemo(() => {
    const u = result?.assessment?.urgency;
    if (!u) return "";
    if (u === "urgent") return "Urgent care recommended";
    if (u === "soon") return "Get checked soon";
    return "Home care";
  }, [result]);

  const urgencyStyle = useMemo(() => {
    const u = result?.assessment?.urgency;
    if (u === "urgent") return { bg: "#fde8ea", border: "#f3b0b8", text: "#b4232c" };
    if (u === "soon") return { bg: "#fff4e5", border: "#ffd59a", text: "#8a4b00" };
    return { bg: "#e9f7ef", border: "#a7e1c1", text: "#116b3b" };
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

      const params = new URLSearchParams();
      params.set("debug", "false");
      params.set("bleeding_not_stop", bleedingNotStop ? "true" : "false");
      params.set("bite_dirty", biteDirty ? "true" : "false");
      params.set("high_risk", highRisk ? "true" : "false");
      params.set("numbness_weakness", numbWeak ? "true" : "false");
      params.set("on_hand_face_joint", onHandFaceJoint ? "true" : "false");

      const res = await fetch(`${BACKEND_URL}/predict?${params.toString()}`, {
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

    setBleedingNotStop(false);
    setBiteDirty(false);
    setHighRisk(false);
    setNumbWeak(false);
    setOnHandFaceJoint(false);
  };

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 12 }}>Wound Check (Image Only)</h2>

      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          padding: 16,
          border: "1px solid #ddd",
          borderRadius: 12,
          marginBottom: 14,
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

      <div
        style={{
          border: "1px solid #ddd",
          borderRadius: 12,
          padding: 14,
          background: "#fff",
          marginBottom: 18,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 10 }}>Optional context (improves realism)</div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <input type="checkbox" checked={bleedingNotStop} onChange={(e) => setBleedingNotStop(e.target.checked)} />
            Bleeding won’t stop after 10 minutes of pressure
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <input type="checkbox" checked={numbWeak} onChange={(e) => setNumbWeak(e.target.checked)} />
            Numbness or weakness near the injury
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <input type="checkbox" checked={biteDirty} onChange={(e) => setBiteDirty(e.target.checked)} />
            Bite / dirty object / contaminated wound
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <input type="checkbox" checked={onHandFaceJoint} onChange={(e) => setOnHandFaceJoint(e.target.checked)} />
            On face / hand / across a joint
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <input type="checkbox" checked={highRisk} onChange={(e) => setHighRisk(e.target.checked)} />
            Higher infection risk (optional)
          </label>
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
          <div style={{ fontWeight: 600, marginBottom: 10 }}>Preview</div>
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
          <div style={{ fontWeight: 600, marginBottom: 10 }}>Result</div>

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
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Not confident enough</div>
              <div style={{ color: "#333" }}>
                {result.message || "Try retaking the photo (brighter, closer, no blur)."}
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
              <div
                style={{
                  background: urgencyStyle.bg,
                  border: `1px solid ${urgencyStyle.border}`,
                  color: urgencyStyle.text,
                  borderRadius: 10,
                  padding: "10px 12px",
                  fontWeight: 800,
                  marginBottom: 14,
                }}
              >
                {urgencyLabel}
              </div>

              <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 6 }}>
                {result.assessment.summary}
              </div>

              {typeof result.confidence === "number" && (
                <div style={{ marginBottom: 12, color: "#666" }}>
                  Detection confidence: {Math.round(result.confidence * 100)}%
                </div>
              )}

              {result.assessment.why_flagged?.length ? (
                <>
                  <div style={{ marginTop: 10, fontWeight: 700 }}>Why it flagged this</div>
                  <ul style={{ marginTop: 6 }}>
                    {result.assessment.why_flagged.map((t, i) => (
                      <li key={`why-${i}`}>{t}</li>
                    ))}
                  </ul>
                </>
              ) : null}

              {result.assessment.photo_note ? (
                <>
                  <div style={{ marginTop: 10, fontWeight: 700 }}>Photo note</div>
                  <div style={{ marginTop: 6, color: "#333" }}>{result.assessment.photo_note}</div>
                </>
              ) : null}

              <div style={{ marginTop: 12, fontWeight: 700 }}>Next steps</div>
              <ul style={{ marginTop: 6 }}>
                {result.assessment.next_steps.map((t, i) => (
                  <li key={`ns-${i}`}>{t}</li>
                ))}
              </ul>

              <div style={{ marginTop: 10, fontWeight: 700 }}>Tips</div>
              <ul style={{ marginTop: 6 }}>
                {result.assessment.tips.map((t, i) => (
                  <li key={`tip-${i}`}>{t}</li>
                ))}
              </ul>

              <div style={{ marginTop: 10, fontWeight: 700 }}>Watch for</div>
              <ul style={{ marginTop: 6 }}>
                {result.assessment.watch_for.map((t, i) => (
                  <li key={`wf-${i}`}>{t}</li>
                ))}
              </ul>

              <div style={{ marginTop: 12, color: "#666", fontSize: 12 }}>
                {result.assessment.disclaimer}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
