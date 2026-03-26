"use client";

import React, { useMemo, useRef, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { processAndUploadWound, predictOnly, createWoundProfile } from "@/lib/wounds";

type PredictResponse = {
  ok: boolean;

  // base flags
  detected?: boolean;
  confidence?: number;
  message?: string;
  class?: string;
  error?: string;

  // image overlay returned by backend (base64, no prefix)
  annotated_image?: string;

  // you display this in the UI
  method?: string;

  // measurements section in your UI
  measurements?: {
    length_cm?: number;
    width_cm?: number;
    area_cm2?: number;
    perimeter_cm?: number;
  };

  // color analysis section in your UI
  color_analysis?: {
    color_description?: string;
    redness_level?: number; // looks like 0..1 in your UI
    color_percentages?: Record<string, number>;
    health_indicators?: {
      healthy_pink_present?: boolean;
      excessive_redness?: boolean;
      signs_of_infection?: boolean;
      necrotic_tissue?: boolean;
    };
  };

  // healing assessment section in your UI
  healing_assessment?: {
    healing_stage?: string;
    healing_progress?: string;
    severity?: string;

    healing_indicators?: string[];
    concerns?: string[];

    infection_risk?: {
      level?: string;
      score?: number;
    };

    healing_time_prediction?: {
      predicted_days_min?: number;
      predicted_days_max?: number;
      confidence?: string;
      notes?: string;
    };

    stitches?: {
      need_stitches?: boolean;
      recommendation?: string;
    };

    scar_risk?: {
      risk?: string;
      score?: number;
      tips?: string[];
    };
  };

  // recommendations section in your UI
  recommendations?: {
    immediate_care?: string[] | string;
    ongoing_care?: string[] | string;
    medications?: {
      healing_aids?: string[] | string;
      pain_management?: string[] | string;
      cautions?: string[] | string;
    };
    warning_signs?: string[] | string;
    follow_up?: string;
  };

  // overall assessment section in your UI
  overall_assessment?: string;

  // calibration section in your UI
  calibration?: {
    mode?: string;
    ppcm?: number;
  };
  pixels_per_cm?: number;

  // keep your older assessment block too (doesn't hurt)
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
};

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

function getDisplayWoundName(rawWoundId: string | null): string {
  if (!rawWoundId) return "a new wound";

  const decoded = decodeURIComponent(rawWoundId);
  const cleaned = decoded.replace(/-[a-f0-9]{8}$/i, "");

  return cleaned || decoded;
}

export default function CapturePage() {
  const searchParams = useSearchParams();
  const woundId = searchParams.get("woundId");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [woundName, setWoundName] = useState<string>("");

  // Follow-Up Chat state
  type ChatMsg = { role: "user" | "assistant"; content: string; model?: string; source?: string };
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // ---- TS-safe "narrowed" locals (prevents build errors) ----
  const measurements = result?.measurements;
  const color = result?.color_analysis;
  const healing = result?.healing_assessment;
  const recs = result?.recommendations;

  const healingIndicators = Array.isArray(healing?.healing_indicators) 
    ? healing.healing_indicators 
    : (healing?.healing_indicators ? [healing.healing_indicators] : []);
  const concerns = Array.isArray(healing?.concerns)
    ? healing.concerns
    : (healing?.concerns ? [healing.concerns] : []);
  const scarTips = Array.isArray(healing?.scar_risk?.tips)
    ? healing.scar_risk.tips
    : (healing?.scar_risk?.tips ? [healing.scar_risk.tips] : []);

  const immediateCare = Array.isArray(recs?.immediate_care)
    ? recs.immediate_care
    : (recs?.immediate_care ? [recs.immediate_care] : []);
  const ongoingCare = Array.isArray(recs?.ongoing_care)
    ? recs.ongoing_care
    : (recs?.ongoing_care ? [recs.ongoing_care] : []);
  const warningSigns = Array.isArray(recs?.warning_signs)
    ? recs.warning_signs
    : (recs?.warning_signs ? [recs.warning_signs] : []);

  const rednessLevel = color?.redness_level ?? 0;
  const perimeter = measurements?.perimeter_cm ?? 0;

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
      // If no woundId in the URL, create a new wound profile with the typed name first
      let targetWoundId = woundId;
      if (!targetWoundId) {
        const name = woundName.trim() || "My Wound";
        targetWoundId = await createWoundProfile(name);
      }
      const { analysis } = await processAndUploadWound(file, targetWoundId);
      setResult(analysis as any);
    } catch (e: any) {
      const msg = e?.message || "Request failed";
      const authRequired = /not authenticated|sign in|sign-in|login|401/i.test(msg);
      setResult({ ok: false, error: msg, ...(authRequired && { authRequired: true }) } as any);
    } finally {
      setLoading(false);
    }
  };

  const onAnalyzeOnly = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);
    try {
      const data = await predictOnly(file);
      setResult(data as any);
    } catch (e: any) {
      setResult({ ok: false, error: e?.message || "Request failed" });
    } finally {
      setLoading(false);
    }
  };

  const sendChat = async () => {
    const q = chatInput.trim();
    if (!q || chatLoading) return;
    const userMsg: ChatMsg = { role: "user", content: q };
    const updatedHistory = [...chatMessages, userMsg];
    setChatMessages(updatedHistory);
    setChatInput("");
    setChatLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          wound_context: result ?? undefined,
          history: chatMessages,
        }),
      });
      const data = await res.json();
      const answer = data.answer || "Sorry, I couldn't generate a response.";
      setChatMessages([...updatedHistory, { role: "assistant", content: answer, model: data.model, source: data.source }]);
    } catch {
      setChatMessages([...updatedHistory, { role: "assistant", content: "Connection error — please try again." }]);
    } finally {
      setChatLoading(false);
    }
  };

  const onClear = () => {
    setFile(null);
    setPreviewUrl("");
    setResult(null);
    setChatMessages([]);
  };

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <Link href="/dashboard" style={{ display: "inline-block", color: "#2563eb", textDecoration: "none", fontWeight: 600, marginBottom: 12 }}>← Back to Dashboard</Link>
      <h2 style={{ marginBottom: 6 }}>Add photo</h2>
      <p style={{ color: "#666", marginBottom: 14 }}>
        Adding to <strong>{getDisplayWoundName(woundId)}</strong>. We'll analyze and save to this profile.
      </p>

      {/* Wound name input — only shown when arriving directly (no woundId in URL) */}
      {!woundId && (
        <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 10 }}>
          <label style={{ fontWeight: 600, color: "#333", whiteSpace: "nowrap" }}>
            Wound name:
          </label>
          <input
            suppressHydrationWarning
            type="text"
            placeholder="e.g. Left knee scrape"
            value={woundName}
            onChange={(e) => setWoundName(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border: "1px solid #bbb",
              fontSize: 14,
              width: 260,
            }}
          />
          <span style={{ fontSize: 12, color: "#888" }}>
            (optional — defaults to "My Wound")
          </span>
        </div>
      )}
      {/* old description removed */}
      <div style={{ display: "none" }}>
        Upload a photo. Guidance is based on shape + visual cues (not “size in
        photo”), so zoomed-in papercuts won’t automatically be treated as severe.
      </div>

      {/* Photo Taking Tips */}
      <div
        style={{
          padding: 14,
          background: "#f0f7ff",
          border: "1px solid #2b59ff",
          borderRadius: 12,
          marginBottom: 18,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 8, color: "#1a3d7a" }}>
          📸 Tips for Best Results:
        </div>
        <ul style={{ margin: 0, paddingLeft: 20, color: "#333" }}>
          <li>Hold your device steady (rest your hand on a stable surface)</li>
          <li>Use good lighting - natural daylight works best</li>
          <li>Tap to focus on the wound before taking the photo</li>
          <li>
            Avoid glare - wipe moisture and tilt slightly so light doesn't
            reflect off shiny skin
          </li>
          <li>Keep the wound centered in the frame</li>
          <li>
            Don't zoom in too much - include some surrounding skin for context
          </li>
          <li>Take the photo from directly above the wound (perpendicular)</li>
          <li>Ensure the wound is clean and visible before photographing</li>
        </ul>
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
          {loading ? "Analyzing..." : "Analyze & save"}
        </button>

        <button
          onClick={onAnalyzeOnly}
          disabled={!file || loading}
          title="No sign-in required. Results are not saved."
          style={{
            padding: "10px 14px",
            borderRadius: 10,
            border: "1px solid #16a34a",
            background: "#fff",
            color: "#16a34a",
            cursor: !file || loading ? "not-allowed" : "pointer",
            fontWeight: 600,
          }}
        >
          Analyze only (no sign-in)
        </button>

        <button
          suppressHydrationWarning
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
              src={
                result?.annotated_image
                  ? `data:image/jpeg;base64,${result.annotated_image}`
                  : previewUrl
              }
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
            <div>
              <div style={{ color: "#b00020", marginBottom: 8 }}>
                {result.error || "Something went wrong."}
              </div>
              {(result as any).authRequired && (
                <Link
                  href="/"
                  style={{
                    display: "inline-block",
                    padding: "10px 16px",
                    borderRadius: 10,
                    background: "#2563eb",
                    color: "white",
                    textDecoration: "none",
                    fontWeight: 600,
                  }}
                >
                  Sign in to save results
                </Link>
              )}
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

          {result && result.ok && result.detected === true && (
            <div>
              {/* Wound Detection Status */}
              <div style={{ fontWeight: 900, fontSize: 18, marginBottom: 8 }}>
                Wound Detected: {result.method || "Analysis Complete"} (Roboflow + Gemini AI)
              </div>

              {typeof result.confidence === "number" && (
                <div style={{ marginBottom: 10, color: "#666" }}>
                  Detection confidence: {Math.round(result.confidence * 100)}%
                </div>
              )}

              {/* Measurements */}
              {measurements && (
                <>
                  <div style={{ marginTop: 14, fontWeight: 800, fontSize: 16 }}>
                    📏 Measurements
                  </div>
                  <div style={{ marginTop: 6, paddingLeft: 10 }}>
                    <div>
                      Length: {measurements.length_cm?.toFixed(2) || "N/A"} cm
                    </div>
                    <div>
                      Width: {measurements.width_cm?.toFixed(2) || "N/A"} cm
                    </div>
                    <div>
                      Area: {measurements.area_cm2?.toFixed(2) || "N/A"} cm²
                    </div>
                    {perimeter > 0 && (
                      <div>Perimeter: {perimeter.toFixed(2)} cm</div>
                    )}
                  </div>
                </>
              )}

              {/* Color Analysis */}
              {color && (
                <>
                  <div style={{ marginTop: 14, fontWeight: 800, fontSize: 16 }}>
                    🎨 Color Analysis
                  </div>
                  <div style={{ marginTop: 6, paddingLeft: 10 }}>
                    <div>Description: {color.color_description}</div>
                    <div>Redness Level: {(rednessLevel * 100).toFixed(1)}%</div>

                    {color.color_percentages && (
                      <div style={{ marginTop: 4 }}>
                        {Object.entries(color.color_percentages).map(
                          ([cname, pct]) => (
                            <div key={cname}>
                              - {cname}: {pct.toFixed(1)}%
                            </div>
                          )
                        )}
                      </div>
                    )}

                    {color.health_indicators && (
                      <div style={{ marginTop: 6 }}>
                        <div style={{ fontWeight: 700 }}>Health Indicators:</div>
                        {color.health_indicators.healthy_pink_present && (
                          <div style={{ color: "#1b6e1b" }}>
                            ✅ Healthy Pink Present
                          </div>
                        )}
                        {color.health_indicators.excessive_redness && (
                          <div style={{ color: "#b36b00" }}>
                            ⚠️ Excessive Redness
                          </div>
                        )}
                        {color.health_indicators.signs_of_infection && (
                          <div style={{ color: "#b00020" }}>
                            ⚠️ Signs Of Infection
                          </div>
                        )}
                        {color.health_indicators.necrotic_tissue && (
                          <div style={{ color: "#b00020" }}>
                            ⚠️ Necrotic Tissue
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* Healing Assessment */}
              {healing && (
                <>
                  <div style={{ marginTop: 14, fontWeight: 800, fontSize: 16 }}>
                    🔄 Healing Assessment
                  </div>
                  <div style={{ marginTop: 6, paddingLeft: 10 }}>
                    <div>
                      Stage: {healing.healing_stage?.toUpperCase()}
                    </div>
                    <div>
                      Progress: {healing.healing_progress?.toUpperCase()}
                    </div>
                    <div>
                      Severity: {healing.severity?.toUpperCase()}
                    </div>

                    {healingIndicators.length > 0 && (
                      <div style={{ marginTop: 6 }}>
                        <div style={{ fontWeight: 700 }}>Positive Signs:</div>
                        <ul style={{ marginTop: 2 }}>
                          {healingIndicators.map((sign: string, i: number) => (
                            <li key={`hi-${i}`}>{sign}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {concerns.length > 0 && (
                      <div style={{ marginTop: 6 }}>
                        <div style={{ fontWeight: 700 }}>Concerns:</div>
                        <ul style={{ marginTop: 2 }}>
                          {concerns.map((concern: string, i: number) => (
                            <li key={`c-${i}`}>{concern}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {healing.infection_risk && (
                      <div style={{ marginTop: 6 }}>
                        Infection Likelihood:{" "}
                        {healing.infection_risk.level?.toUpperCase()} (
                        {healing.infection_risk.score}%)
                      </div>
                    )}

                    {healing.healing_time_prediction && (
                      <div style={{ marginTop: 6 }}>
                        <div style={{ fontWeight: 700 }}>
                          Healing Time Prediction:
                        </div>
                        <div>
                          Estimated:{" "}
                          {healing.healing_time_prediction.predicted_days_min}–
                          {healing.healing_time_prediction.predicted_days_max}{" "}
                          days
                        </div>
                        <div style={{ fontSize: 13, color: "#666" }}>
                          Confidence:{" "}
                          {healing.healing_time_prediction.confidence}
                        </div>
                        {healing.healing_time_prediction.notes && (
                          <div
                            style={{
                              fontSize: 13,
                              color: "#666",
                              fontStyle: "italic",
                            }}
                          >
                            {healing.healing_time_prediction.notes}
                          </div>
                        )}
                      </div>
                    )}

                    {healing.stitches && (
                      <div style={{ marginTop: 6 }}>
                        {healing.stitches.need_stitches ? (
                          <div style={{ color: "#b00020", fontWeight: 700 }}>
                            ⚠️ {healing.stitches.recommendation}
                          </div>
                        ) : (
                          <div style={{ color: "#1b6e1b", fontWeight: 700 }}>
                            ✅ Closure:{" "}
                            {healing.stitches.recommendation ||
                              "LIKELY HEALS NATURALLY"}
                          </div>
                        )}
                      </div>
                    )}

                    {healing.scar_risk && (
                      <div style={{ marginTop: 6 }}>
                        <div style={{ fontWeight: 700 }}>
                          Scar Risk: {healing.scar_risk.risk?.toUpperCase()} (
                          {healing.scar_risk.score}%)
                        </div>
                        {scarTips.length > 0 && (
                          <ul style={{ marginTop: 2, fontSize: 13 }}>
                            {scarTips.map((tip: string, i: number) => (
                              <li key={`scar-${i}`}>{tip}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* Recommendations */}
              {recs && (
                <>
                  <div style={{ marginTop: 14, fontWeight: 800, fontSize: 16 }}>
                    💊 Treatment Recommendations
                  </div>

                  {immediateCare.length > 0 && (
                    <>
                      <div style={{ marginTop: 8, fontWeight: 700 }}>
                        Immediate Care:
                      </div>
                      <ul style={{ marginTop: 4 }}>
                        {immediateCare.map((step: string, i: number) => (
                          <li key={`ic-${i}`}>{step}</li>
                        ))}
                      </ul>
                    </>
                  )}

                  {ongoingCare.length > 0 && (
                    <>
                      <div style={{ marginTop: 8, fontWeight: 700 }}>
                        Daily Care Protocol:
                      </div>
                      <ul style={{ marginTop: 4 }}>
                        {ongoingCare.map((step: string, i: number) => (
                          <li key={`oc-${i}`}>{step}</li>
                        ))}
                      </ul>
                    </>
                  )}

                  {recs.medications && (
                    <>
                      <div style={{ marginTop: 8, fontWeight: 700 }}>
                        Medications:
                      </div>
                      <div style={{ paddingLeft: 10, marginTop: 4 }}>
                        {(Array.isArray(recs.medications.healing_aids) 
                          ? recs.medications.healing_aids 
                          : recs.medications.healing_aids ? [recs.medications.healing_aids] : []
                        ).map((med: string, i: number) => (
                          <div key={`ha-${i}`} style={{ marginTop: 2 }}>
                            • {med}
                          </div>
                        ))}
                        {(Array.isArray(recs.medications.pain_management)
                          ? recs.medications.pain_management
                          : recs.medications.pain_management ? [recs.medications.pain_management] : []
                        ).map((med: string, i: number) => (
                          <div key={`pm-${i}`} style={{ marginTop: 2 }}>
                            • {med}
                          </div>
                        ))}
                        {((Array.isArray(recs.medications.cautions)
                          ? recs.medications.cautions
                          : recs.medications.cautions ? [recs.medications.cautions] : []
                        ) ?? []).length > 0 && (
                          <>
                            <div style={{ marginTop: 6, fontWeight: 700 }}>
                              Cautions:
                            </div>
                            {(Array.isArray(recs.medications.cautions)
                              ? recs.medications.cautions
                              : recs.medications.cautions ? [recs.medications.cautions] : []
                            ).map((caution: string, i: number) => (
                              <div
                                key={`caut-${i}`}
                                style={{ marginTop: 2 }}
                              >
                                • {caution}
                              </div>
                            ))}
                          </>
                        )}
                      </div>
                    </>
                  )}

                  {warningSigns.length > 0 && (
                    <>
                      <div style={{ marginTop: 8, fontWeight: 700 }}>
                        ⚠️ Warning Signs:
                      </div>
                      <ul style={{ marginTop: 4 }}>
                        {warningSigns.map((sign: string, i: number) => (
                          <li key={`ws-${i}`}>{sign}</li>
                        ))}
                      </ul>
                    </>
                  )}

                  {recs.follow_up && (
                    <div style={{ marginTop: 8, color: "#666" }}>
                      Follow-up: {recs.follow_up}
                    </div>
                  )}
                </>
              )}


              {/* Overall Assessment */}
              {result.overall_assessment && (
                <div
                  style={{
                    marginTop: 14,
                    padding: 10,
                    background: "#f5f5f5",
                    borderRadius: 8,
                    borderLeft: "4px solid #2b59ff",
                  }}
                >
                  <div style={{ fontWeight: 700 }}>Clinical Summary:</div>
                  <div style={{ marginTop: 4 }}>{result.overall_assessment}</div>
                </div>
              )}

              {/* Gemini AI Clinical Feedback */}
              {result.gemini_feedback && (
                <div
                  style={{
                    marginTop: 14,
                    padding: 10,
                    background: "#fffbe7",
                    borderRadius: 8,
                    borderLeft: "4px solid #fbbf24",
                  }}
                >
                  <div style={{ fontWeight: 700, color: "#b45309" }}>AI Clinical Feedback (Gemini):</div>
                  <div style={{ marginTop: 4, color: "#92400e" }}>{result.gemini_feedback}</div>
                </div>
              )}

              {/* Calibration Info */}
              {result.calibration && (
                <div
                  style={{
                    marginTop: 14,
                    fontSize: 13,
                    color: "#666",
                    padding: 8,
                    background: "#f9f9f9",
                    borderRadius: 6,
                  }}
                >
                  <div style={{ fontWeight: 700 }}>📐 Calibration:</div>
                  <div>Mode: {result.calibration.mode || "Standard"}</div>
                  <div>
                    Pixels per cm:{" "}
                    {result.pixels_per_cm ?? result.calibration.ppcm ?? "N/A"}
                  </div>
                </div>
              )}

              {/* Optional: your older assessment urgency label if backend sends it */}
              {result.assessment?.urgency && (
                <div style={{ marginTop: 14 }}>
                  <div style={{ fontWeight: 700 }}>Urgency:</div>
                  <div style={{ color: urgencyColor }}>{urgencyLabel}</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      {/* ── Follow Up Questions ─────────────────────────────────────────── */}
      {result && result.ok && result.detected === true && (
        <div
          style={{
            marginTop: 24,
            border: "1px solid #c7d2fe",
            borderRadius: 14,
            background: "#f8f9ff",
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "14px 18px",
              background: "#eef2ff",
              borderBottom: "1px solid #c7d2fe",
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <span style={{ fontSize: 20 }}>💬</span>
            <div>
              <div style={{ fontWeight: 800, fontSize: 16, color: "#3730a3" }}>
                Follow Up Questions
              </div>
              <div style={{ fontSize: 12, color: "#6366f1" }}>
                Ask the AI about your wound, care steps, healing time, or any concerns
              </div>
            </div>
          </div>

          {/* Message thread */}
          <div
            style={{
              padding: "14px 18px",
              maxHeight: 380,
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            {chatMessages.length === 0 && (
              <div style={{ color: "#888", fontSize: 13, fontStyle: "italic" }}>
                No messages yet. Ask anything — "How do I clean this wound?", "Should I be worried about infection?", "What pain relief can I take?", or any other question.
              </div>
            )}

            {chatMessages.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: "78%",
                    padding: "10px 14px",
                    borderRadius: msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
                    background: msg.role === "user" ? "#3730a3" : "#fff",
                    color: msg.role === "user" ? "#fff" : "#1e1b4b",
                    border: msg.role === "assistant" ? "1px solid #c7d2fe" : "none",
                    fontSize: 14,
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                  }}
                >
                  {msg.role === "assistant" && (
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: "#6366f1" }}>WoundSync AI</span>
                      {msg.model && (
                        <span style={{ fontSize: 10, background: "#e0e7ff", color: "#4338ca", padding: "1px 6px", borderRadius: 8, fontWeight: 600 }}>
                          {msg.model}
                        </span>
                      )}
                      {!msg.model && msg.source && (
                        <span style={{ fontSize: 10, background: "#f3f4f6", color: "#6b7280", padding: "1px 6px", borderRadius: 8, fontWeight: 600 }}>
                          analysis-based
                        </span>
                      )}
                    </div>
                  )}
                  {msg.content}
                </div>
              </div>
            ))}

            {chatLoading && (
              <div style={{ display: "flex", justifyContent: "flex-start" }}>
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "16px 16px 16px 4px",
                    background: "#fff",
                    border: "1px solid #c7d2fe",
                    color: "#6366f1",
                    fontSize: 14,
                    fontStyle: "italic",
                  }}
                >
                  WoundSync AI is thinking…
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input bar */}
          <div
            style={{
              padding: "12px 18px",
              borderTop: "1px solid #c7d2fe",
              display: "flex",
              gap: 10,
              background: "#fff",
            }}
          >
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); } }}
              placeholder="Ask a follow-up question about your wound…"
              disabled={chatLoading}
              style={{
                flex: 1,
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid #c7d2fe",
                fontSize: 14,
                outline: "none",
                background: chatLoading ? "#f5f5f5" : "#fff",
              }}
            />
            <button
              onClick={sendChat}
              disabled={!chatInput.trim() || chatLoading}
              style={{
                padding: "10px 20px",
                borderRadius: 10,
                border: "none",
                background: !chatInput.trim() || chatLoading ? "#a5b4fc" : "#3730a3",
                color: "#fff",
                fontWeight: 700,
                fontSize: 14,
                cursor: !chatInput.trim() || chatLoading ? "not-allowed" : "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {chatLoading ? "…" : "Send"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}