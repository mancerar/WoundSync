"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getUser } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { ProgressChart } from "@/components/ProgressChart";
import { getWoundProfiles, getWoundProfile, seedPlaceholderData } from "@/lib/wounds";
import { Plus, Flame, Trophy, Target } from "lucide-react";

/**
 * Local UI-friendly types (loose on purpose)
 * so Next build doesn't fail if the backend / lib types are incomplete.
 */
type AchievementItem = {
  id: string;
  icon?: string;
  name: string;
  description?: string;
};

type HealingPrediction = {
  days_remaining: number;
  predicted_date: string;
  daily_reduction_cm2: number;
  current_healing_rate: "good" | "fair" | "slow" | string;
};

type WoundRecord = {
  recorded_at: string;
  area_cm2: number;
};

type ProfileSummary = {
  id: string;
  name: string;
  createdAt?: string;
  location?: string;
  record_count?: number;
  streak?: number;
  achievement_count?: number;
};

type ProfileDetail = ProfileSummary & {
  wound_type?: string;
  start_date?: string;
  notes?: string;
  achievements?: AchievementItem[];
  healing_prediction?: HealingPrediction;
  records?: WoundRecord[];
};

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export default function Dashboard() {
  const [username, setUsername] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<ProfileDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setUsername(getUser()?.username ?? null);
    loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function normalizeProfiles(raw: any[]): ProfileSummary[] {
    return (raw || []).map((p: any) => ({
      id: String(p?.id ?? ""),
      name: String(p?.name ?? "Untitled"),
      createdAt: p?.createdAt,
      location: p?.location ?? "",
      record_count: typeof p?.record_count === "number" ? p.record_count : 0,
      streak: typeof p?.streak === "number" ? p.streak : 0,
      achievement_count:
        typeof p?.achievement_count === "number" ? p.achievement_count : 0,
    })).filter((p) => p.id);
  }

  async function loadProfiles() {
    try {
      setLoading(true);

      let data: any[] = await getWoundProfiles();
      let normalized = normalizeProfiles(data);

      // If no profiles, seed placeholder data
      if (!normalized.length) {
        await seedPlaceholderData();
        data = await getWoundProfiles();
        normalized = normalizeProfiles(data);
      }

      setProfiles(normalized);

      if (normalized.length > 0) {
        await loadProfileDetails(normalized[0].id);
      } else {
        setSelectedProfile(null);
      }
    } catch (error: any) {
      console.error("Failed to load profiles:", error);
      alert("Error loading wound profiles: " + (error?.message ?? String(error)));
      setSelectedProfile(null);
    } finally {
      setLoading(false);
    }
  }

  async function loadProfileDetails(profileId: string) {
    try {
      const profile: any = await getWoundProfile(profileId);

      if (!profile) {
        setSelectedProfile(null);
        return;
      }

      // Normalize detail fields so UI doesn’t crash
      const detail: ProfileDetail = {
        id: String(profile?.id ?? profileId),
        name: String(profile?.name ?? "Untitled"),
        createdAt: profile?.createdAt,
        location: profile?.location ?? "",
        record_count: typeof profile?.record_count === "number" ? profile.record_count : 0,
        streak: typeof profile?.streak === "number" ? profile.streak : 0,
        achievement_count:
          typeof profile?.achievement_count === "number" ? profile.achievement_count : 0,

        wound_type: profile?.wound_type ?? "",
        start_date: profile?.start_date ?? "",
        notes: profile?.notes ?? "",

        achievements: Array.isArray(profile?.achievements) ? profile.achievements : [],
        healing_prediction: profile?.healing_prediction,
        records: Array.isArray(profile?.records) ? profile.records : [],
      };

      setSelectedProfile(detail);
    } catch (error) {
      console.error("Failed to load profile details:", error);
      setSelectedProfile(null);
    }
  }

  const {
    totalPhotos,
    lastUpdateText,
    healedPct,
    daysTracked,
    avgIntervalDays,
    insightText,
    nextUploadText,
    randomTip,
  } = useMemo(() => {
    const records: WoundRecord[] = selectedProfile?.records ?? [];

    if (!records.length) {
      return {
        totalPhotos: 0,
        lastUpdateText: "No uploads yet",
        healedPct: 0,
        daysTracked: 0,
        avgIntervalDays: 0,
        insightText:
          "No trend yet — add your first photo to start tracking improvement.",
        nextUploadText: "As soon as you capture your first photo",
        randomTip: "Use consistent lighting and distance for each photo.",
      };
    }

    const sorted = [...records].sort(
      (a, b) =>
        new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
    );

    const first = sorted[0];
    const last = sorted[sorted.length - 1];
    const totalPhotos = sorted.length;
    const lastUpdateText = new Date(last.recorded_at).toLocaleString();

    const initialArea = Number(first.area_cm2 || 0);
    const currentArea = Number(last.area_cm2 || 0);
    const areaReduction = initialArea - currentArea;

    const healedPct =
      initialArea > 0
        ? Math.max(0, Math.min(100, (areaReduction / initialArea) * 100))
        : 0;

    const msDay = 24 * 60 * 60 * 1000;
    const daysTracked = Math.max(
      1,
      Math.ceil(
        (new Date(last.recorded_at).getTime() - new Date(first.recorded_at).getTime()) /
          msDay
      )
    );

    let avgIntervalDays = 0;
    if (sorted.length > 1) {
      let sum = 0;
      for (let i = 1; i < sorted.length; i++) {
        sum +=
          (new Date(sorted[i].recorded_at).getTime() -
            new Date(sorted[i - 1].recorded_at).getTime()) /
          msDay;
      }
      avgIntervalDays = +(sum / (sorted.length - 1)).toFixed(1);
    }

    const trend =
      areaReduction > 0 ? "Improving" : areaReduction < 0 ? "Worsening" : "Stable";
    const insightText = `${trend} — wound area changed by ${Math.abs(areaReduction).toFixed(
      1
    )} cm²`;

    const next = new Date(new Date(last.recorded_at).getTime() + 2 * msDay);
    const nextUploadText = `Suggested next upload: ${next.toLocaleDateString()}`;

    const tips = [
      "Clean gently. Keep area dry.",
      "Upload a photo every 2–3 days.",
      "Use consistent lighting and distance.",
      "Include a reference marker for size.",
    ];
    const randomTip = tips[Math.floor(Math.random() * tips.length)];

    return {
      totalPhotos,
      lastUpdateText,
      healedPct,
      daysTracked,
      avgIntervalDays,
      insightText,
      nextUploadText,
      randomTip,
    };
  }, [selectedProfile]);

  return (
    <div className="ws-container space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Dashboard
        </h1>
        <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
          {username ? `Your latest healing status: ${username}` : "Your latest healing status"}
        </p>
      </div>

      {/* Wound Profile Selector */}
      <div className="ws-card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-lg font-semibold text-slate-800">Your Wounds</div>
          <Button variant="outline" size="sm" className="gap-2">
            <Plus className="h-4 w-4" />
            New Wound
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-8 text-slate-500">Loading your wounds...</div>
        ) : profiles.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            No wounds tracked yet. Click &quot;New Wound&quot; to get started.
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {profiles.map((profile) => {
              const recordCount = profile.record_count ?? 0;
              const streak = profile.streak ?? 0;
              const badgeCount = profile.achievement_count ?? 0;

              return (
                <button
                  key={profile.id}
                  onClick={() => loadProfileDetails(profile.id)}
                  className={`text-left p-4 rounded-lg border-2 transition-all hover:shadow-md ${
                    selectedProfile?.id === profile.id
                      ? "border-blue-500 bg-blue-50"
                      : "border-slate-200 bg-white hover:border-blue-300"
                  }`}
                >
                  <div className="font-semibold text-slate-800">{profile.name}</div>
                  <div className="text-sm text-slate-500 mt-1">{profile.location ?? ""}</div>

                  <div className="flex items-center gap-3 mt-3 text-xs">
                    <span className="text-slate-600">
                      {recordCount} {recordCount === 1 ? "record" : "records"}
                    </span>

                    {streak > 0 && (
                      <span className="flex items-center gap-1 text-orange-600 font-medium whitespace-nowrap">
                        <Flame className="h-3 w-3 flex-shrink-0" />
                        {streak}-day streak
                      </span>
                    )}

                    {badgeCount > 0 && (
                      <span className="flex items-center gap-1 text-yellow-600 font-medium whitespace-nowrap">
                        <Trophy className="h-3 w-3 flex-shrink-0" />
                        {badgeCount} {badgeCount === 1 ? "badge" : "badges"}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {selectedProfile && (
        <>
          <div className="ws-card p-5">
            <div className="text-lg font-semibold text-slate-800 mb-2">
              {selectedProfile.name}
            </div>

            <div className="space-y-1 text-sm text-slate-600">
              <div>
                <span className="font-medium">Location:</span>{" "}
                {selectedProfile.location || "—"}
              </div>
              <div>
                <span className="font-medium">Type:</span>{" "}
                {selectedProfile.wound_type || "—"}
              </div>
              <div>
                <span className="font-medium">Started:</span>{" "}
                {selectedProfile.start_date
                  ? new Date(selectedProfile.start_date).toLocaleDateString()
                  : "—"}
              </div>
              {selectedProfile.notes ? (
                <div>
                  <span className="font-medium">Notes:</span> {selectedProfile.notes}
                </div>
              ) : null}
            </div>
          </div>

          {/* Achievements & Progress */}
          {(selectedProfile.streak ?? 0) > 0 ||
          (selectedProfile.achievements?.length ?? 0) > 0 ? (
            <div className="ws-card p-5">
              <div className="text-lg font-semibold text-slate-800 mb-3 flex items-center gap-2">
                <Trophy className="h-5 w-5 text-yellow-600" />
                Achievements & Progress
              </div>

              {(selectedProfile.streak ?? 0) > 0 && (
                <div className="mb-4 p-4 bg-gradient-to-r from-orange-50 to-red-50 rounded-lg border-2 border-orange-200">
                  <div className="flex items-center gap-3">
                    <Flame className="h-7 w-7 text-orange-600 flex-shrink-0" />
                    <div>
                      <div className="font-bold text-lg text-slate-800">
                        {selectedProfile.streak}-Day Streak!
                      </div>
                      <div className="text-sm text-slate-600">
                        Keep uploading photos regularly to maintain your streak
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {(selectedProfile.achievements?.length ?? 0) > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  {selectedProfile.achievements!.map((achievement) => (
                    <div
                      key={achievement.id}
                      className="p-3 bg-white rounded-lg border-2 border-slate-200 hover:border-yellow-300 transition-colors text-center"
                    >
                      <div className="text-3xl mb-2">{achievement.icon ?? "🏅"}</div>
                      <div className="font-semibold text-sm text-slate-800">
                        {achievement.name}
                      </div>
                      <div className="text-xs text-slate-500 mt-1 leading-tight">
                        {achievement.description ?? ""}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : null}

          {/* Healing Prediction */}
          {selectedProfile.healing_prediction && (
            <div className="ws-card p-5 bg-gradient-to-br from-blue-50 to-purple-50 border-blue-200">
              <div className="text-lg font-semibold text-slate-800 mb-2 flex items-center gap-2">
                <Target className="h-5 w-5 text-blue-600" />
                Healing Prediction
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-slate-600">Estimated days remaining:</span>
                  <span className="font-semibold text-lg text-blue-600">
                    {selectedProfile.healing_prediction.days_remaining}
                  </span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-slate-600">Predicted heal date:</span>
                  <span className="font-medium text-slate-800">
                    {new Date(selectedProfile.healing_prediction.predicted_date).toLocaleDateString()}
                  </span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-slate-600">Daily reduction rate:</span>
                  <span className="font-medium text-green-600">
                    {selectedProfile.healing_prediction.daily_reduction_cm2} cm²/day
                  </span>
                </div>

                <div className="mt-3 p-2 bg-white rounded border border-blue-200">
                  <div className="text-xs text-slate-500">
                    Healing rate:{" "}
                    <span
                      className={`font-medium ${
                        selectedProfile.healing_prediction.current_healing_rate === "good"
                          ? "text-green-600"
                          : "text-yellow-600"
                      }`}
                    >
                      {String(selectedProfile.healing_prediction.current_healing_rate).toUpperCase()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Progress Chart */}
          <ProgressChart profileId={selectedProfile.id} />
        </>
      )}

      {/* Healing Progress */}
      <div className="ws-card p-5">
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-lg font-semibold text-slate-800">Healing progress</div>
            <div className="text-sm text-slate-500">Last update: {lastUpdateText}</div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-blue-600">{healedPct.toFixed(0)}%</div>
            <div className="text-sm text-slate-500">Healed</div>
          </div>
        </div>

        <div className="mt-4 h-2 w-full rounded-full bg-slate-200">
          <div
            className="h-2 rounded-full bg-blue-600 transition-all"
            style={{ width: `${Math.min(100, Math.max(0, healedPct))}%` }}
          />
        </div>
      </div>

      {/* Quick Stats */}
      <div className="ws-card p-5">
        <div className="grid grid-cols-3 gap-3 text-center sm:text-left sm:grid-cols-3">
          <div>
            <div className="text-2xl font-semibold text-slate-900">{totalPhotos}</div>
            <div className="text-sm text-slate-600">Photos tracked</div>
          </div>
          <div>
            <div className="text-2xl font-semibold text-slate-900">{daysTracked}</div>
            <div className="text-sm text-slate-600">Days tracked</div>
          </div>
          <div>
            <div className="text-2xl font-semibold text-slate-900">{avgIntervalDays || "—"}</div>
            <div className="text-sm text-slate-600">Avg interval (days)</div>
          </div>
        </div>
      </div>

      {/* Insights */}
      <div className="ws-card p-5">
        <div className="text-lg font-semibold text-slate-800">Your Healing Insights</div>
        <p className="mt-1 text-slate-600">{insightText}</p>
      </div>

      {/* Next Step and Tips */}
      <div className="ws-card p-5">
        <div className="text-lg font-semibold text-slate-800">Next step</div>
        <p className="mt-1 text-slate-600">{nextUploadText}</p>
        <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50 px-4 py-2 text-slate-700">
          💡 Tip: {randomTip}
        </div>
      </div>

      {/* Navigation */}
      <div className="grid gap-3">
        <Button asChild size="lg" className="h-12 rounded-xl text-base font-medium">
          <Link href="/capture">Capture / Upload</Link>
        </Button>
        <Button asChild variant="outline" className="h-12 rounded-xl text-base font-medium">
          <Link href="/progress">Progress Timeline</Link>
        </Button>
        <Button asChild variant="outline" className="h-12 rounded-xl text-base font-medium">
          <Link href="/tips">Tips & Guidance</Link>
        </Button>
        <Button asChild variant="outline" className="h-12 rounded-xl text-base font-medium">
          <Link href="/profile">Profile</Link>
        </Button>
      </div>

      {/* just keeping this visible since you had it in other pages */}
      <div className="text-xs text-slate-400">
        Backend: {BACKEND_URL}
      </div>
    </div>
  );
}