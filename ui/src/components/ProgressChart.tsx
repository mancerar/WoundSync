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
import { getWoundImages, isAuthStartupError } from "@/lib/wounds";

interface ChartData {
  dates: string[];
  area_cm2: number[];
  infection_risk: number[];
  redness_level: number[];
  record_count: number;
}

type ActiveMetric = "area" | "infection" | "redness";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
            if (isAuthStartupError(error) && attempt < 3) {
              await sleep(900 * attempt);
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
        const infectionRisk: number[] = [];
        const rednessLevel: number[] = [];

        const sorted = [...items].sort((a: any, b: any) => {
          const aTs = a.timestamp || a.sk || "";
          const bTs = b.timestamp || b.sk || "";
          return new Date(aTs).getTime() - new Date(bTs).getTime();
        });

        for (const it of sorted) {
          const recAt = it.timestamp || it.created_at || it.sk || new Date().toISOString();
          const analysis = it.analysis || {};
          const measurements = analysis.measurements || {};

          const area = Number(measurements.area_cm2 ?? 0);

          const assessment = analysis.assessment || {};
          const urgency: string | undefined = assessment.urgency;
          let infectionNum = 1;
          if (typeof urgency === "string") {
            const v = urgency.toLowerCase();
            if (v === "soon") infectionNum = 2;
            else if (v === "urgent") infectionNum = 3;
          }

          const colorAnalysis = analysis.color_analysis || {};
          const rednessVal = Number(colorAnalysis.redness_level ?? 0);
          const rednessNum = Math.max(0, Math.min(1, rednessVal));

          dates.push(recAt);
          areas.push(area);
          infectionRisk.push(infectionNum);
          rednessLevel.push(rednessNum);
        }

        setData({
          dates,
          area_cm2: areas,
          infection_risk: infectionRisk,
          redness_level: rednessLevel,
          record_count: dates.length,
        });
      } catch (error) {
        if (cancelled) return;

        if (!isAuthStartupError(error)) {
          console.warn("Progress chart load skipped:", error);
        }

        setData(null);
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

  const points = useMemo(() => {
    if (!data || !data.dates?.length) return [];
    return data.dates.map((d, i) => ({
      date: d,
      area: data.area_cm2[i],
      infection: data.infection_risk[i],
      redness: data.redness_level[i],
    }));
  }, [data]);

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
    { label: string; color: string; yDomain?: [number, number] }
  > = {
    area: {
      label: "Wound Area (cm²)",
      color: "#2563eb",
    },
    infection: {
      label: "Infection Risk (1=Low, 3=High)",
      color: "#dc2626",
      yDomain: [1, 3],
    },
    redness: {
      label: "Redness Level (0-1)",
      color: "#ea580c",
      yDomain: [0, 1],
    },
  };

  const config = metricConfig[activeMetric];

  return (
    <div className="ws-card p-5">
      <div className="mb-4">
        <div className="text-lg font-semibold text-slate-800 mb-3">
          Progress Over Time
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveMetric("area")}
            className={`px-3 py-1 rounded text-sm font-medium ${
              activeMetric === "area"
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Wound Size
          </button>
          <button
            onClick={() => setActiveMetric("infection")}
            className={`px-3 py-1 rounded text-sm font-medium ${
              activeMetric === "infection"
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Infection Risk
          </button>
          <button
            onClick={() => setActiveMetric("redness")}
            className={`px-3 py-1 rounded text-sm font-medium ${
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

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="date"
              tickFormatter={(value) =>
                new Date(value).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                })
              }
              tick={{ fontSize: 11, fill: "#6b7280" }}
            />
            <YAxis
              domain={config.yDomain}
              tick={{ fontSize: 11, fill: "#6b7280" }}
            />
            <Tooltip
              formatter={(value: any) =>
                activeMetric === "area"
                  ? [`${Number(value).toFixed(2)} cm²`, "Area"]
                  : [value, activeMetric === "infection" ? "Infection" : "Redness"]
              }
              labelFormatter={(value) =>
                new Date(value as string).toLocaleString()
              }
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