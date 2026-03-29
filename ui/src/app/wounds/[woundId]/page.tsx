"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getWoundImages,
  getUserWounds,
  deleteWound,
  deleteWoundImage,
} from "@/lib/wounds";
import { Camera, ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const PAGE_TOP_PADDING = "max(calc(env(safe-area-inset-top) + 12px), 56px)";
const PAGE_BOTTOM_PADDING = "max(calc(env(safe-area-inset-bottom) + 12px), 20px)";

type ImageRecord = {
  imageId: string;
  imageKey?: string;
  sk?: string;
  woundId: string;
  timestamp: string;
  healingScore: number;
  viewUrl: string | null;
  analysis: {
    measurements?: {
      area_cm2?: number;
      length_cm?: number;
      width_cm?: number;
      perimeter_cm?: number;
    };
    color_analysis?: { color_description?: string; redness_level?: number };
    healing_assessment?: {
      healing_stage?: string;
      healing_progress?: string;
      severity?: string;
      healing_indicators?: string[];
      concerns?: string[];
      infection_risk?: { level?: string };
      healing_time_prediction?: {
        predicted_days_min?: number;
        predicted_days_max?: number;
      };
      stitches?: { need_stitches?: boolean; recommendation?: string };
      scar_risk?: { risk?: string; tips?: string[] };
    };
    recommendations?: {
      immediate_care?: string[] | string;
      ongoing_care?: string[] | string;
      warning_signs?: string[] | string;
      follow_up?: string;
    };
    overall_assessment?: string;
  };
};

function stripGeneratedSuffix(value: string): string {
  return String(value || "").replace(/-[a-f0-9]{8}$/i, "");
}

function prettifyWoundName(value: string): string {
  const cleaned = stripGeneratedSuffix(value).replace(/[-_]+/g, " ").trim();
  if (!cleaned) return "New wound";

  return cleaned.replace(/\b\w/g, (char) => char.toUpperCase());
}

function AnalysisCard({
  record,
  index,
  onDelete,
  deleting,
}: {
  record: ImageRecord;
  index: number;
  onDelete: (record: ImageRecord) => void;
  deleting: boolean;
}) {
  const [expanded, setExpanded] = useState(index === 0);
  const a = record.analysis ?? {};
  const m = a.measurements ?? {};
  const ha = a.healing_assessment ?? {};
  const rec = a.recommendations ?? {};
  const color = a.color_analysis ?? {};

  const dateStr = record.timestamp
    ? new Date(record.timestamp).toLocaleString()
    : "—";

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
      <div
        style={{
          width: "100%",
          display: "flex",
          alignItems: "flex-start",
          gap: 16,
          padding: 16,
          background: "none",
          border: "none",
          textAlign: "left",
        }}
      >
        {record.viewUrl ? (
          <img
            src={record.viewUrl}
            alt="wound"
            onClick={() => setExpanded((v) => !v)}
            style={{
              width: 96,
              height: 96,
              borderRadius: 10,
              objectFit: "cover",
              flexShrink: 0,
              border: "1px solid #e2e8f0",
              cursor: "pointer",
            }}
          />
        ) : (
          <div
            onClick={() => setExpanded((v) => !v)}
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
              cursor: "pointer",
            }}
          >
            No image
          </div>
        )}

        <div
          style={{ flex: 1, minWidth: 0, cursor: "pointer" }}
          onClick={() => setExpanded((v) => !v)}
        >
          <div
            style={{
              fontWeight: 700,
              color: "#1e293b",
              marginBottom: 4,
            }}
          >
            {dateStr}
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "6px 18px",
              fontSize: 13,
              color: "#475569",
            }}
          >
            {m.area_cm2 != null && (
              <span>
                Area: <strong>{Number(m.area_cm2).toFixed(2)} cm²</strong>
              </span>
            )}
            {m.length_cm != null && (
              <span>
                Length: <strong>{Number(m.length_cm).toFixed(1)} cm</strong>
              </span>
            )}
            {m.width_cm != null && (
              <span>
                Width: <strong>{Number(m.width_cm).toFixed(1)} cm</strong>
              </span>
            )}
            {ha.healing_stage && (
              <span>
                Stage: <strong>{ha.healing_stage}</strong>
              </span>
            )}
            {ha.severity && (
              <span>
                Severity: <strong>{ha.severity}</strong>
              </span>
            )}
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
            <div
              style={{
                marginTop: 4,
                fontSize: 12,
                color: "#64748b",
              }}
            >
              Color: {color.color_description}
            </div>
          )}
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexShrink: 0,
          }}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(record);
            }}
            disabled={deleting}
            title="Delete this photo"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              border: "1px solid #fecaca",
              color: "#dc2626",
              background: deleting ? "#f8fafc" : "#fff",
              borderRadius: 8,
              padding: "6px 10px",
              fontSize: 12,
              fontWeight: 600,
              cursor: deleting ? "not-allowed" : "pointer",
              opacity: deleting ? 0.7 : 1,
            }}
          >
            <Trash2 size={14} />
            {deleting ? "Deleting..." : "Delete"}
          </button>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 4,
              display: "flex",
              alignItems: "center",
              color: "#64748b",
            }}
            aria-label={expanded ? "Collapse details" : "Expand details"}
          >
            {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div
          style={{
            padding: "0 16px 16px",
            borderTop: "1px solid #f1f5f9",
          }}
        >
          {a.overall_assessment && (
            <div
              style={{
                marginTop: 14,
                padding: 12,
                background: "#f8fafc",
                borderRadius: 10,
                fontSize: 14,
                color: "#334155",
              }}
            >
              <strong>Overall assessment:</strong> {a.overall_assessment}
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))",
              gap: 14,
              marginTop: 14,
            }}
          >
            {(ha.healing_indicators?.length ||
              ha.concerns?.length ||
              ha.healing_time_prediction) && (
              <Section title="Healing Assessment">
                {ha.healing_indicators?.length ? (
                  <ul style={listStyle}>
                    {(
                      Array.isArray(ha.healing_indicators)
                        ? ha.healing_indicators
                        : [ha.healing_indicators]
                    ).map((s, i) => (
                      <li key={i} style={{ color: "#16a34a" }}>
                        ✓ {s}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {ha.concerns?.length ? (
                  <ul style={listStyle}>
                    {(Array.isArray(ha.concerns) ? ha.concerns : [ha.concerns]).map(
                      (s, i) => (
                        <li key={i} style={{ color: "#dc2626" }}>
                          ⚠ {s}
                        </li>
                      )
                    )}
                  </ul>
                ) : null}
                {ha.healing_time_prediction?.predicted_days_min != null && (
                  <p style={pStyle}>
                    Estimated healing:{" "}
                    {ha.healing_time_prediction.predicted_days_min}–
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
                    {(Array.isArray(ha.scar_risk.tips)
                      ? ha.scar_risk.tips
                      : [ha.scar_risk.tips]
                    ).map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                ) : null}
              </Section>
            )}

            {rec.immediate_care ? (
              <Section title="Immediate Care">
                {Array.isArray(rec.immediate_care) ? (
                  <ul style={listStyle}>
                    {rec.immediate_care.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                ) : (
                  <p style={pStyle}>{rec.immediate_care}</p>
                )}
              </Section>
            ) : null}

            {rec.ongoing_care ? (
              <Section title="Ongoing Care">
                {Array.isArray(rec.ongoing_care) ? (
                  <ul style={listStyle}>
                    {rec.ongoing_care.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                ) : (
                  <p style={pStyle}>{rec.ongoing_care}</p>
                )}
              </Section>
            ) : null}

            {rec.warning_signs ? (
              <Section title="Warning Signs" accent="#fef2f2" border="#fecaca">
                {Array.isArray(rec.warning_signs) ? (
                  <ul style={listStyle}>
                    {rec.warning_signs.map((s, i) => (
                      <li key={i} style={{ color: "#dc2626" }}>
                        {s}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ ...pStyle, color: "#dc2626" }}>
                    {rec.warning_signs}
                  </p>
                )}
              </Section>
            ) : null}
          </div>

          {rec.follow_up && (
            <div
              style={{
                marginTop: 12,
                fontSize: 13,
                color: "#475569",
              }}
            >
              <strong>Follow-up:</strong> {rec.follow_up}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const listStyle: React.CSSProperties = {
  margin: "4px 0 0 0",
  paddingLeft: 18,
  fontSize: 13,
  color: "#374151",
  lineHeight: 1.6,
};

const pStyle: React.CSSProperties = {
  margin: "4px 0 0 0",
  fontSize: 13,
  color: "#374151",
};

function Section({
  title,
  children,
  accent = "#f0f9ff",
  border = "#bae6fd",
}: {
  title: string;
  children: React.ReactNode;
  accent?: string;
  border?: string;
}) {
  return (
    <div
      style={{
        background: accent,
        border: `1px solid ${border}`,
        borderRadius: 10,
        padding: 12,
      }}
    >
      <div
        style={{
          fontWeight: 600,
          fontSize: 13,
          color: "#1e293b",
          marginBottom: 6,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

export default function WoundHistoryPage() {
  const params = useParams();
  const router = useRouter();
  const woundId = decodeURIComponent(params.woundId as string);

  const [records, setRecords] = useState<ImageRecord[]>([]);
  const [woundName, setWoundName] = useState(prettifyWoundName(woundId));
  const [loading, setLoading] = useState(true);
  const [deleteState, setDeleteState] = useState<"idle" | "confirm" | "deleting">(
    "idle"
  );
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletingImageRef, setDeletingImageRef] = useState<string | null>(null);

  function imageRefOf(record: ImageRecord): string {
    return String(record.imageId || record.imageKey || record.sk || "").trim();
  }

  async function handleDelete() {
    setDeleteState("deleting");
    setDeleteError(null);
    try {
      await deleteWound(woundId);
      router.push("/dashboard");
    } catch (err: any) {
      setDeleteError(err?.message || "Delete failed");
      setDeleteState("confirm");
    }
  }

  async function handleDeleteRecord(record: ImageRecord) {
    const imageRef = imageRefOf(record);
    if (!imageRef) {
      alert("Could not determine image id for deletion.");
      return;
    }

    const ok = window.confirm("Delete this uploaded photo? This cannot be undone.");
    if (!ok) return;

    setDeletingImageRef(imageRef);
    try {
      await deleteWoundImage(woundId, imageRef);
      setRecords((prev) => prev.filter((r) => imageRefOf(r) !== imageRef));
    } catch (err: any) {
      alert(err?.message || "Failed to delete photo.");
    } finally {
      setDeletingImageRef(null);
    }
  }

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const wounds = await getUserWounds();
        const match = wounds.find((w: any) => w.id === woundId);
        if (match?.name) setWoundName(prettifyWoundName(match.name));
        else setWoundName(prettifyWoundName(woundId));

        const images = await getWoundImages(woundId);
        const filtered = (images || []).filter(
          (it: any) => it.imageKey || it.imageId
        );

        filtered.sort(
          (a: any, b: any) =>
            new Date(b.timestamp || 0).getTime() -
            new Date(a.timestamp || 0).getTime()
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
    <div
      className="ws-container space-y-6"
      style={{
        paddingTop: PAGE_TOP_PADDING,
        paddingBottom: PAGE_BOTTOM_PADDING,
        maxWidth: 860,
        margin: "0 auto",
      }}
    >
      <Link
        href="/dashboard"
        style={{
          display: "inline-block",
          color: "#2563eb",
          textDecoration: "none",
          fontWeight: 600,
          marginBottom: 12,
        }}
      >
        ← Back to Dashboard
      </Link>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
            {woundName}
          </h1>
          <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
            {loading
              ? "Loading…"
              : `${records.length} record${records.length !== 1 ? "s" : ""}`}
          </p>
        </div>

        <div className="flex gap-3 flex-wrap items-center">
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
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "#fef2f2",
                border: "1px solid #fca5a5",
                borderRadius: 12,
                padding: "8px 14px",
                flexWrap: "wrap",
              }}
            >
              <span
                style={{
                  fontSize: 13,
                  color: "#dc2626",
                  fontWeight: 600,
                }}
              >
                Delete all records for &ldquo;{woundName}&rdquo;?
              </span>
              <button
                onClick={handleDelete}
                style={{
                  background: "#dc2626",
                  color: "#fff",
                  border: "none",
                  borderRadius: 8,
                  padding: "5px 14px",
                  fontWeight: 700,
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                Yes, delete
              </button>
              <button
                onClick={() => {
                  setDeleteState("idle");
                  setDeleteError(null);
                }}
                style={{
                  background: "transparent",
                  border: "1px solid #94a3b8",
                  borderRadius: 8,
                  padding: "5px 12px",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                Cancel
              </button>
              {deleteError && (
                <span style={{ fontSize: 12, color: "#dc2626" }}>
                  {deleteError}
                </span>
              )}
            </div>
          )}

          {deleteState === "deleting" && (
            <span
              style={{
                fontSize: 13,
                color: "#64748b",
                fontStyle: "italic",
              }}
            >
              Deleting…
            </span>
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
        <div
          style={{
            textAlign: "center",
            padding: 60,
            color: "#94a3b8",
          }}
        >
          Loading records…
        </div>
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
          <p style={{ fontSize: 16, marginBottom: 12 }}>
            No photos yet for this wound.
          </p>
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
            <AnalysisCard
              key={rec.imageId || rec.imageKey || rec.sk || rec.timestamp || i}
              record={rec}
              index={i}
              onDelete={handleDeleteRecord}
              deleting={deletingImageRef === imageRefOf(rec)}
            />
          ))}
        </div>
      )}
    </div>
  );
}