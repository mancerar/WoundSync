// Progress comparison chart component
"use client";

import { useEffect, useState } from "react";

interface ChartData {
  dates: string[];
  area_cm2: number[];
  length_cm: number[];
  width_cm: number[];
  infection_risk: number[];
  redness_level: number[];
  record_count: number;
}

export function ProgressChart({ profileId }: { profileId: number }) {
  const [data, setData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeMetric, setActiveMetric] = useState<"area" | "infection" | "redness">("area");

  useEffect(() => {
    loadChartData();
  }, [profileId]);

  async function loadChartData() {
    try {
      setLoading(true);
      const response = await fetch(`http://127.0.0.1:8000/api/charts/metrics/${profileId}`);
      const result = await response.json();
      if (result.ok) {
        setData(result.data);
      }
    } catch (error) {
      console.error("Failed to load chart data:", error);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="ws-card p-5">
        <div className="text-center text-slate-500">Loading chart...</div>
      </div>
    );
  }

  if (!data || data.record_count < 2) {
    return (
      <div className="ws-card p-5">
        <div className="text-center text-slate-500">Need at least 2 records to show trends</div>
      </div>
    );
  }

  const getMetricData = () => {
    switch (activeMetric) {
      case "area":
        return data.area_cm2;
      case "infection":
        return data.infection_risk;
      case "redness":
        return data.redness_level;
      default:
        return data.area_cm2;
    }
  };

  const getMetricLabel = () => {
    switch (activeMetric) {
      case "area":
        return "Wound Area (cm²)";
      case "infection":
        return "Infection Risk Level";
      case "redness":
        return "Redness Level";
      default:
        return "Metric";
    }
  };

  const metricData = getMetricData();
  const maxValue = Math.max(...metricData);
  const minValue = Math.min(...metricData);

  return (
    <div className="ws-card p-5">
      <div className="mb-4">
        <div className="text-lg font-semibold text-slate-800 mb-3">Progress Over Time</div>
        <div className="flex gap-2">
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

      <div className="mb-2 text-sm font-medium text-slate-600">{getMetricLabel()}</div>
      
      {/* Simple bar chart */}
      <div className="space-y-2">
        {data.dates.map((date, index) => {
          const value = metricData[index];
          const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;
          const isImproving = index > 0 && value < metricData[index - 1];
          
          return (
            <div key={index} className="flex items-center gap-2">
              <div className="text-xs text-slate-500 w-24 flex-shrink-0">
                {new Date(date).toLocaleDateString()}
              </div>
              <div className="flex-1 bg-slate-100 rounded-full h-8 relative overflow-hidden">
                <div
                  className={`h-full transition-all ${
                    activeMetric === "area"
                      ? isImproving
                        ? "bg-green-500"
                        : "bg-blue-500"
                      : activeMetric === "infection"
                      ? value === 1
                        ? "bg-green-500"
                        : value === 2
                        ? "bg-yellow-500"
                        : "bg-red-500"
                      : value === 1
                      ? "bg-green-500"
                      : value === 2
                      ? "bg-yellow-500"
                      : "bg-red-500"
                  }`}
                  style={{ width: `${percentage}%` }}
                />
                <div className="absolute inset-0 flex items-center px-3 text-xs font-medium">
                  {activeMetric === "area" ? `${value.toFixed(2)} cm²` : 
                   value === 1 ? "Low" : value === 2 ? "Moderate" : "High"}
                </div>
              </div>
              {index > 0 && (
                <div className="text-xs w-16 flex-shrink-0 text-right">
                  {activeMetric === "area" ? (
                    <span className={isImproving ? "text-green-600" : "text-red-600"}>
                      {isImproving ? "↓" : "↑"} {Math.abs(value - metricData[index - 1]).toFixed(2)}
                    </span>
                  ) : null}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary */}
      <div className="mt-4 pt-4 border-t border-slate-200 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-xs text-slate-500">Start</div>
          <div className="font-semibold text-slate-800">
            {activeMetric === "area" 
              ? `${metricData[0].toFixed(2)} cm²`
              : metricData[0] === 1 ? "Low" : metricData[0] === 2 ? "Moderate" : "High"}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Current</div>
          <div className="font-semibold text-slate-800">
            {activeMetric === "area"
              ? `${metricData[metricData.length - 1].toFixed(2)} cm²`
              : metricData[metricData.length - 1] === 1 ? "Low" : metricData[metricData.length - 1] === 2 ? "Moderate" : "High"}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Change</div>
          <div className={`font-semibold ${
            activeMetric === "area" && metricData[0] > metricData[metricData.length - 1]
              ? "text-green-600"
              : "text-slate-800"
          }`}>
            {activeMetric === "area"
              ? `${(metricData[0] - metricData[metricData.length - 1]).toFixed(2)} cm²`
              : metricData[0] - metricData[metricData.length - 1] >= 0 ? "Improved" : "Worsened"}
          </div>
        </div>
      </div>
    </div>
  );
}
