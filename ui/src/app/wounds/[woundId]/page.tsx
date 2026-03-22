"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getWoundImages, getUserWounds, deleteWound } from "@/lib/wounds";
import { Camera, ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

type ImageRecord = {  imageId: string;
  woundId: string;
  timestamp: string;
  healingScore: number;
  viewUrl: string | null;
  analysis: {
    measurements?: { area_cm2?: number; length_cm?: number; width_cm?: number; perimeter_cm?: number };
    color_analysis?: { color_description?: string; redness_level?: number };
    healing_assessment?: {
      healing_stage?: string;
      healing_progress?: string;
      severity?: string;
      healing_indicators?: string[];
      concerns?: string[];
      infection_risk?: { level?: string };
      healing_time_prediction?: { predicted_days_min?: number; predicted_days_max?: number };
      stitches?: { need_stitches?: boolean; recommendation?: string };
      scar_risk?: { risk?: string; tips?: string[] };
    };
    recommendations?: {
      immediate_care?: string[];
      ongoing_care?: string[];
      warning_signs?: string[];
      follow_up?: string;
    };
    overall_assessment?: string;
  };
};

function AnalysisCard({ record, index }: { record: ImageRecord; index: number }) {
  const [expanded, setExpanded] = useState(index === 0);
  const a = record.analysis ?? {};
  const m = a.measurements ?? {};
  const ha = a.healing_assessment ?? {};
  const rec = a.recommendations ?? {};
  const color = a.color_analysis ?? {};

  const dateStr = record.timestamp ? new Date(record.timestamp).toLocaleString() : "—";

  return (
    <div
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: 14,
        background: "#fff",
        overflow: "hidden",
        boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
      }}
    >
      {/* Summary row — always visible */}
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "flex-start",
          gap: 16,
          padding: 16,
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        {/* Thumbnail */}
        {record.viewUrl ? (
          <img
            src={record.viewUrl}
            alt="wound"
            style={{
              width: 96,
              height: 96,
              borderRadius: 10,
              objectFit: "cover",
              flexShrink: 0,
              border: "1px solid #e2e8f0",
            }}
          />
        ) : (
          <div
            style={{
              width: 96,
              height: 96,
              borderRadius: 10,
              flexShrink: 0,
              background: "#f1f5f9",
              border: "1px solid #e2e8f0",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#94a3b8",
              fontSize: 12,
            }}
          >
            No image
          </div>
        )}

        {/* Key stats */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, color: "#1e293b", marginBottom: 4 }}>{dateStr}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 18px", fontSize: 13, color: "#475569" }}>
            {m.area_cm2 != null && <span>Area: <strong>{Number(m.area_cm2).toFixed(2)} cm²</strong></span>}
            {m.length_cm != null && <span>Length: <strong>{Number(m.length_cm).toFixed(1)} cm</strong></span>}
            {m.width_cm != null && <span>Width: <strong>{Number(m.width_cm).toFixed(1)} cm</strong></span>}
            {ha.healing_stage && <span>Stage: <strong>{ha.healing_stage}</strong></span>}
            {ha.severity && <span>Severity: <strong>{ha.severity}</strong></span>}
            {ha.infection_risk?.level && (
              <span
                style={{
                  color:
                    ha.infection_risk.level === "high"
                      ? "#dc2626"
                      : ha.infection_risk.level === "medium"
                      ? "#d97706"
                      : "#16a34a",
                  fontWeight: 600,
                }}
              >
                Infection risk: {ha.infection_risk.level}
              </span>
            )}
          </div>
          {color.color_description && (
            <div style={{ marginTop: 4, fontSize: 12, color: "#64748b" }}>
              Color: {color.color_description}
            </div>
          )}
        </div>

        <div style={{ color: "#94a3b8", flexShrink: 0 }}>
          {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </div>
      </button>

      {/* Expanded full feedback */}
      {expanded && (
        <div style={{ padding: "0 16px 16px", borderTop: "1px solid #f1f5f9" }}>
          {a.overall_assessment && (
            <div style={{ marginTop: 14, padding: 12, background: "#f8fafc", borderRadius: 10, fontSize: 14, color: "#334155" }}>
              <strong>Overall assessment:</strong> {a.overall_assessment}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 14, marginTop: 14 }}>

            {/* Healing assessment */}
            {(ha.healing_indicators?.length || ha.concerns?.length || ha.healing_time_prediction) && (
              <Section title="Healing Assessment">
                {ha.healing_indicators?.length ? (
                  <ul style={listStyle}>
                    {ha.healing_indicators.map((s, i) => <li key={i} style={{ color: "#16a34a" }}>✓ {s}</li>)}
                  </ul>
                ) : null}
                {ha.concerns?.length ? (
                  <ul style={listStyle}>
                    {ha.concerns.map((s, i) => <li key={i} style={{ color: "#dc2626" }}>⚠ {s}</li>)}
                  </ul>
                ) : null}
                {ha.healing_time_prediction?.predicted_days_min != null && (
                  <p style={pStyle}>
                    Estimated healing: {ha.healing_time_prediction.predicted_days_min}–
                    {ha.healing_time_prediction.predicted_days_max} days
                  </p>
                )}
                {ha.stitches?.recommendation && (
                  <p style={pStyle}>Stitches: {ha.stitches.recommendation}</p>
                )}
                {ha.scar_risk?.risk && (
                  <p style={pStyle}>Scar risk: {ha.scar_risk.risk}</p>
                )}
                {ha.scar_risk?.tips?.length ? (
                  <ul style={listStyle}>
                    {ha.scar_risk.tips.map((t, i) => <li key={i}>{t}</li>)}
                  </ul>
                ) : null}
              </Section>
            )}

            {/* Immediate care */}
            {rec.immediate_care?.length ? (
              <Section title="Immediate Care">
                <ul style={listStyle}>
                  {rec.immediate_care.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </Section>
            ) : null}

            {/* Ongoing care */}
            {rec.ongoing_care?.length ? (
              <Section title="Ongoing Care">
                <ul style={listStyle}>
                  {rec.ongoing_care.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </Section>
            ) : null}

            {/* Warning signs */}
            {rec.warning_signs?.length ? (
              <Section title="Warning Signs" accent="#fef2f2" border="#fecaca">
                <ul style={listStyle}>
                  {rec.warning_signs.map((s, i) => <li key={i} style={{ color: "#dc2626" }}>{s}</li>)}
                </ul>
              </Section>
            ) : null}
          </div>

          {rec.follow_up && (
            <div style={{ marginTop: 12, fontSize: 13, color: "#475569" }}>
              <strong>Follow-up:</strong> {rec.follow_up}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const listStyle: React.CSSProperties = { margin: "4px 0 0 0", paddingLeft: 18, fontSize: 13, color: "#374151", lineHeight: 1.6 };
const pStyle: React.CSSProperties = { margin: "4px 0 0 0", fontSize: 13, color: "#374151" };

function Section({ title, children, accent = "#f0f9ff", border = "#bae6fd" }: {
  title: string; children: React.ReactNode; accent?: string; border?: string;
}) {
  return (
    <div style={{ background: accent, border: `1px solid ${border}`, borderRadius: 10, padding: 12 }}>
      <div style={{ fontWeight: 600, fontSize: 13, color: "#1e293b", marginBottom: 6 }}>{title}</div>
      {children}
    </div>
  );
}

export default function WoundHistoryPage() {
  const params = useParams();
  const router = useRouter();
  const woundId = decodeURIComponent(params.woundId as string);

  const [records, setRecords] = useState<ImageRecord[]>([]);
  const [woundName, setWoundName] = useState(woundId);
  const [loading, setLoading] = useState(true);
  const [deleteState, setDeleteState] = useState<"idle" | "confirm" | "deleting">("idle");
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete() {
    setDeleteState("deleting");
    setDeleteError(null);
    try {
      await deleteWound(woundId);
      router.push("/dashboard");
    } catch (err: any) {
      setDeleteError(err?.message || "Delete failed");
      setDeleteState("confirm"); // stay on confirm so user can retry
    }
  }

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        // Try to get the human-readable name from the wounds list
        const wounds = await getUserWounds();
        const match = wounds.find((w: any) => w.id === woundId);
        if (match?.name) setWoundName(match.name);

        const images = await getWoundImages(woundId);
        const filtered = (images || []).filter((it: any) => it.imageKey || it.imageId);
        // Sort newest first
        filtered.sort((a: any, b: any) =>
          new Date(b.timestamp || 0).getTime() - new Date(a.timestamp || 0).getTime()
        );
        setRecords(filtered as ImageRecord[]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [woundId]);

  const captureHref = `/capture?woundId=${encodeURIComponent(woundId)}`;

  return (
    <div style={{ padding: "20px 24px", maxWidth: 860, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, marginBottom: 20 }}>
        <div>
          <Link href="/dashboard" style={{ color: "#2563eb", fontWeight: 600, textDecoration: "none", fontSize: 14 }}>
            ← Dashboard
          </Link>
          <h1 style={{ margin: "6px 0 2px", fontSize: 26, fontWeight: 800, color: "#0f172a" }}>
            {woundName}
          </h1>
          <p style={{ margin: 0, color: "#64748b", fontSize: 14 }}>
            {loading ? "Loading…" : `${records.length} record${records.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          {deleteState === "idle" && (
            <Button
              variant="outline"
              size="lg"
              className="gap-2 rounded-xl font-medium shrink-0 border-red-300 text-red-600 hover:bg-red-50"
              onClick={() => setDeleteState("confirm")}
            >
              <Trash2 className="h-4 w-4" />
              Delete wound
            </Button>
          )}
          {deleteState === "confirm" && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 12, padding: "8px 14px" }}>
              <span style={{ fontSize: 13, color: "#dc2626", fontWeight: 600 }}>Delete all records for &ldquo;{woundName}&rdquo;?</span>
              <button
                onClick={handleDelete}
                style={{ background: "#dc2626", color: "#fff", border: "none", borderRadius: 8, padding: "5px 14px", fontWeight: 700, cursor: "pointer", fontSize: 13 }}
              >
                Yes, delete
              </button>
              <button
                onClick={() => { setDeleteState("idle"); setDeleteError(null); }}
                style={{ background: "transparent", border: "1px solid #94a3b8", borderRadius: 8, padding: "5px 12px", cursor: "pointer", fontSize: 13 }}
              >
                Cancel
              </button>
              {deleteError && <span style={{ fontSize: 12, color: "#dc2626" }}>{deleteError}</span>}
            </div>
          )}
          {deleteState === "deleting" && (
            <span style={{ fontSize: 13, color: "#64748b", fontStyle: "italic" }}>Deleting…</span>
          )}
          <Button asChild size="lg" className="gap-2 rounded-xl font-medium shrink-0">
            <Link href={captureHref}>
              <Camera className="h-5 w-5" />
              Add photo
            </Link>
          </Button>
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#94a3b8" }}>Loading records…</div>
      )}

      {!loading && records.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: 60,
            border: "2px dashed #e2e8f0",
            borderRadius: 16,
            color: "#64748b",
          }}
        >
          <p style={{ fontSize: 16, marginBottom: 12 }}>No photos yet for this wound.</p>
          <Button asChild>
            <Link href={captureHref}>
              <Camera className="h-4 w-4 mr-2" />
              Add first photo
            </Link>
          </Button>
        </div>
      )}

      {!loading && records.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {records.map((rec, i) => (
            <AnalysisCard key={rec.imageId || rec.timestamp || i} record={rec} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
