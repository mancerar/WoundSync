"use client";

import React, { useMemo, useState } from "react";

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
    immediate_care?: string[];
    ongoing_care?: string[];
    medications?: {
      healing_aids?: string[];
      pain_management?: string[];
      cautions?: string[];
    };
    warning_signs?: string[];
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

export default function CapturePage() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);

  // ---- TS-safe "narrowed" locals (prevents build errors) ----
  const measurements = result?.measurements;
  const color = result?.color_analysis;
  const healing = result?.healing_assessment;
  const recs = result?.recommendations;

  const healingIndicators = healing?.healing_indicators ?? [];
  const concerns = healing?.concerns ?? [];
  const scarTips = healing?.scar_risk?.tips ?? [];

  const immediateCare = recs?.immediate_care ?? [];
  const ongoingCare = recs?.ongoing_care ?? [];
  const warningSigns = recs?.warning_signs ?? [];

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

          {result && result.ok && result.detected === true && (
            <div>
              {/* Wound Detection Status */}
              <div style={{ fontWeight: 900, fontSize: 18, marginBottom: 8 }}>
                Wound Detected: {result.method || "Analysis Complete"}
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
                        {recs.medications.healing_aids?.map(
                          (med: string, i: number) => (
                            <div key={`ha-${i}`} style={{ marginTop: 2 }}>
                              • {med}
                            </div>
                          )
                        )}
                        {recs.medications.pain_management?.map(
                          (med: string, i: number) => (
                            <div key={`pm-${i}`} style={{ marginTop: 2 }}>
                              • {med}
                            </div>
                          )
                        )}
                        {(recs.medications.cautions ?? []).length > 0 && (
                          <>
                            <div style={{ marginTop: 6, fontWeight: 700 }}>
                              Cautions:
                            </div>
                            {(recs.medications.cautions ?? []).map(
                              (caution: string, i: number) => (
                                <div
                                  key={`caut-${i}`}
                                  style={{ marginTop: 2 }}
                                >
                                  • {caution}
                                </div>
                              )
                            )}
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
    </div>
  );
}