"use client";

import { useEffect, useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import { getWoundImages } from "@/lib/wounds";

interface ChartData {
  dates: string[];
  area_cm2: number[];
  infection_risk_pct: number[];
  redness_level_pct: number[];
  record_count: number;
}

type ActiveMetric = "area" | "infection" | "redness";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function toFiniteNumber(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function normalizeToPercent(value: unknown): number | null {
  const n = toFiniteNumber(value);
  if (n === null) return null;

  if (n <= 1) return clamp(n * 100, 0, 100);
  return clamp(n, 0, 100);
}

function extractText(value: unknown): string {
  return String(value || "").toLowerCase().trim();
}

function sameCalendarDay(values: string[]) {
  if (values.length <= 1) return true;

  const first = new Date(values[0]);
  const y = first.getFullYear();
  const m = first.getMonth();
  const d = first.getDate();

  return values.every((value) => {
    const dt = new Date(value);
    return (
      dt.getFullYear() === y &&
      dt.getMonth() === m &&
      dt.getDate() === d
    );
  });
}

function deriveAreaCm2(analysis: any): number {
  const measurements = analysis?.measurements || {};

  const directArea = toFiniteNumber(measurements.area_cm2);
  if (directArea !== null && directArea >= 0) return directArea;

  const length = toFiniteNumber(measurements.length_cm);
  const width = toFiniteNumber(measurements.width_cm);

  if (length !== null && width !== null && length >= 0 && width >= 0) {
    return length * width;
  }

  return 0;
}

function parsePercentFromText(text: string): number | null {
  if (!text) return null;

  const regexes = [
    /infection(?:\s+likelihood|\s+risk)?[^0-9]{0,20}(\d{1,3})\s*%/i,
    /(\d{1,3})\s*%[^.]{0,30}infection/i,
  ];

  for (const regex of regexes) {
    const match = text.match(regex);
    if (match?.[1]) {
      return clamp(Number(match[1]), 0, 100);
    }
  }

  return null;
}

function levelToPercent(levelText: string): number | null {
  const text = extractText(levelText);
  if (!text) return null;

  if (text.includes("high") || text.includes("severe")) return 80;
  if (text.includes("moderate") || text.includes("medium")) return 55;
  if (text.includes("low")) return 25;

  return null;
}

function deriveInfectionPercent(analysis: any): number {
  const healingAssessment = analysis?.healing_assessment || {};
  const healingInfection = healingAssessment?.infection_risk || {};
  const directInfection =
    analysis?.infection_risk ||
    analysis?.infectionRisk ||
    analysis?.infection ||
    {};

  const scoreCandidates = [
    healingInfection?.score,
    directInfection?.score,
    analysis?.infection_score,
    analysis?.infectionScore,
  ];

  for (const candidate of scoreCandidates) {
    const score = normalizeToPercent(candidate);
    if (score !== null) return score;
  }

  const levelCandidates = [
    healingInfection?.level,
    directInfection?.level,
    analysis?.infection_level,
    analysis?.infectionLevel,
  ];

  for (const candidate of levelCandidates) {
    const pct = levelToPercent(String(candidate || ""));
    if (pct !== null) return pct;
  }

  const textCandidates = [
    analysis?.overall_assessment,
    analysis?.assessment?.summary,
    healingAssessment?.notes,
    analysis?.recommendations?.follow_up,
    Array.isArray(healingAssessment?.concerns)
      ? healingAssessment.concerns.join(" ")
      : healingAssessment?.concerns,
  ];

  for (const candidate of textCandidates) {
    const text = String(candidate || "");
    const percent = parsePercentFromText(text);
    if (percent !== null) return percent;

    const pctFromLevel = levelToPercent(text);
    if (pctFromLevel !== null) return pctFromLevel;
  }

  const healthIndicators = analysis?.color_analysis?.health_indicators || {};
  if (healthIndicators.signs_of_infection) return 80;

  const concernsText = extractText(
    Array.isArray(healingAssessment?.concerns)
      ? healingAssessment.concerns.join(" ")
      : healingAssessment?.concerns
  );

  if (
    concernsText.includes("infection") ||
    concernsText.includes("infected") ||
    concernsText.includes("pus") ||
    concernsText.includes("drainage") ||
    concernsText.includes("discharge") ||
    concernsText.includes("odor") ||
    concernsText.includes("odour") ||
    concernsText.includes("warmth") ||
    concernsText.includes("swelling") ||
    concernsText.includes("fever") ||
    concernsText.includes("red streak")
  ) {
    return 70;
  }

  const severity = extractText(healingAssessment?.severity);
  if (severity === "severe" || severity === "critical") return 75;
  if (severity === "moderate") return 50;
  if (severity === "mild") return 20;

  const urgency = extractText(analysis?.assessment?.urgency);
  if (urgency === "urgent") return 80;
  if (urgency === "soon") return 55;
  if (urgency === "home") return 20;

  return 0;
}

function deriveRednessFromPercentages(
  colorPercentages: Record<string, number> | undefined
): number | null {
  if (!colorPercentages) return null;

  let score = 0;
  let foundRelevant = false;

  for (const [rawKey, rawValue] of Object.entries(colorPercentages)) {
    const value = normalizeToPercent(rawValue);
    if (value === null) continue;

    const key = rawKey.toLowerCase().trim();

    if (key.includes("red") || key.includes("erythema")) {
      score += value * 1.0;
      foundRelevant = true;
    } else if (key.includes("inflam") || key.includes("irrit")) {
      score += value * 0.9;
      foundRelevant = true;
    } else if (key.includes("pink")) {
      score += value * 0.55;
      foundRelevant = true;
    }
  }

  if (!foundRelevant) return null;
  return clamp(score, 0, 100);
}

function deriveRednessFromDescription(description: unknown): number | null {
  const text = String(description || "").toLowerCase().trim();
  if (!text) return null;

  if (
    text.includes("severe red") ||
    text.includes("bright red") ||
    text.includes("very red")
  ) {
    return 85;
  }

  if (text.includes("inflamed") || text.includes("erythema")) {
    return 70;
  }

  if (text.includes("red")) {
    return 65;
  }

  if (text.includes("pink")) {
    return 35;
  }

  return null;
}

function deriveRednessPercent(analysis: any): number {
  const colorAnalysis = analysis?.color_analysis || {};

  const direct = normalizeToPercent(colorAnalysis.redness_level);
  if (direct !== null) return direct;

  const fromPercentages = deriveRednessFromPercentages(
    colorAnalysis.color_percentages
  );
  if (fromPercentages !== null) {
    let score = fromPercentages;

    if (colorAnalysis.health_indicators?.excessive_redness) {
      score = Math.max(score, 75);
    } else if (colorAnalysis.health_indicators?.healthy_pink_present) {
      score = Math.max(score, 30);
    }

    return clamp(score, 0, 100);
  }

  const fromDescription = deriveRednessFromDescription(
    colorAnalysis.color_description
  );
  if (fromDescription !== null) {
    let score = fromDescription;

    if (colorAnalysis.health_indicators?.excessive_redness) {
      score = Math.max(score, 75);
    } else if (colorAnalysis.health_indicators?.healthy_pink_present) {
      score = Math.max(score, 30);
    }

    return clamp(score, 0, 100);
  }

  if (colorAnalysis.health_indicators?.excessive_redness) return 75;
  if (colorAnalysis.health_indicators?.healthy_pink_present) return 30;

  return 0;
}

export function ProgressChart({ profileId }: { profileId: string }) {
  const [data, setData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeMetric, setActiveMetric] = useState<ActiveMetric>("area");

  useEffect(() => {
    let cancelled = false;

    async function loadChartData() {
      if (!profileId) {
        setData(null);
        setLoading(false);
        return;
      }

      setLoading(true);

      try {
        let images: any[] = [];

        for (let attempt = 1; attempt <= 3; attempt++) {
          try {
            images = await getWoundImages(profileId);
            break;
          } catch (error) {
            if (attempt < 3) {
              await sleep(600 * attempt);
              if (cancelled) return;
              continue;
            }
            throw error;
          }
        }

        if (cancelled) return;

        const items = (images || []).filter(
          (it: any) => (it.sk && it.sk.includes("#IMG#")) || it.imageKey
        );

        if (!items.length) {
          setData(null);
          return;
        }

        const dates: string[] = [];
        const areas: number[] = [];
        const infectionRiskPct: number[] = [];
        const rednessPct: number[] = [];

        const sorted = [...items].sort((a: any, b: any) => {
          const aTs = a.timestamp || a.created_at || a.sk || "";
          const bTs = b.timestamp || b.created_at || b.sk || "";
          return new Date(aTs).getTime() - new Date(bTs).getTime();
        });

        for (const it of sorted) {
          const recAt =
            it.timestamp || it.created_at || it.sk || new Date().toISOString();
          const analysis = it.analysis || {};

          dates.push(recAt);
          areas.push(deriveAreaCm2(analysis));
          infectionRiskPct.push(deriveInfectionPercent(analysis));
          rednessPct.push(deriveRednessPercent(analysis));
        }

        setData({
          dates,
          area_cm2: areas,
          infection_risk_pct: infectionRiskPct,
          redness_level_pct: rednessPct,
          record_count: dates.length,
        });
      } catch (error) {
        if (!cancelled) {
          console.warn("Progress chart load skipped:", error);
          setData(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadChartData();

    return () => {
      cancelled = true;
    };
  }, [profileId]);

  const showTimeLabels = useMemo(() => {
    if (!data?.dates?.length) return false;
    return sameCalendarDay(data.dates);
  }, [data]);

  const points = useMemo(() => {
    if (!data || !data.dates?.length) return [];
    return data.dates.map((d, i) => ({
      date: d,
      orderLabel: showTimeLabels
        ? new Date(d).toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit",
            second: "2-digit",
          })
        : new Date(d).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          }),
      area: data.area_cm2[i],
      infection: data.infection_risk_pct[i],
      redness: data.redness_level_pct[i],
    }));
  }, [data, showTimeLabels]);

  if (loading) {
    return (
      <div className="ws-card p-5">
        <div className="text-center text-slate-500">Loading chart...</div>
      </div>
    );
  }

  if (!data || data.record_count < 2 || points.length < 2) {
    return (
      <div className="ws-card p-5">
        <div className="text-center text-slate-500">
          Need at least 2 records to show trends
        </div>
      </div>
    );
  }

  const metricConfig: Record<
    ActiveMetric,
    {
      label: string;
      color: string;
      yDomain?: [number, number];
      yTickFormatter?: (value: number) => string;
    }
  > = {
    area: {
      label: "Wound Area (cm²)",
      color: "#2563eb",
    },
    infection: {
      label: "Infection Risk (%)",
      color: "#dc2626",
      yDomain: [0, 100],
      yTickFormatter: (value) => `${Math.round(value)}%`,
    },
    redness: {
      label: "Redness Level (%)",
      color: "#ea580c",
      yDomain: [0, 100],
      yTickFormatter: (value) => `${Math.round(value)}%`,
    },
  };

  const config = metricConfig[activeMetric];

  return (
    <div className="ws-card p-5">
      <div className="mb-4">
        <div className="mb-3 text-lg font-semibold text-slate-800">
          Progress Over Time
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveMetric("area")}
            className={`rounded px-3 py-1 text-sm font-medium ${
              activeMetric === "area"
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Wound Size
          </button>

          <button
            onClick={() => setActiveMetric("infection")}
            className={`rounded px-3 py-1 text-sm font-medium ${
              activeMetric === "infection"
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Infection Risk
          </button>

          <button
            onClick={() => setActiveMetric("redness")}
            className={`rounded px-3 py-1 text-sm font-medium ${
              activeMetric === "redness"
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Redness
          </button>
        </div>
      </div>

      <div className="mb-2 text-sm font-medium text-slate-600">
        {config.label}
      </div>

      <div className="h-64 w-full" style={{ minHeight: 256, minWidth: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={points}
            margin={{ top: 10, right: 20, bottom: 10, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="orderLabel"
              tick={{ fontSize: 11, fill: "#6b7280" }}
            />
            <YAxis
              domain={config.yDomain}
              tick={{ fontSize: 11, fill: "#6b7280" }}
              tickFormatter={config.yTickFormatter}
            />
            <Tooltip
              formatter={(value: any) => {
                if (activeMetric === "area") {
                  return [`${Number(value).toFixed(2)} cm²`, "Area"];
                }

                if (activeMetric === "infection") {
                  return [`${Number(value).toFixed(0)}%`, "Infection Risk"];
                }

                return [`${Number(value).toFixed(0)}%`, "Redness"];
              }}
              labelFormatter={(_label, payload) => {
                const point = payload?.[0]?.payload as any;
                if (!point?.date) return String(_label);
                return new Date(point.date).toLocaleString();
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey={
                activeMetric === "area"
                  ? "area"
                  : activeMetric === "infection"
                  ? "infection"
                  : "redness"
              }
              stroke={config.color}
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}