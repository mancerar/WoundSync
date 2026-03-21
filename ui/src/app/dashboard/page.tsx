"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getUser } from "@/lib/auth";
import { useAuth } from "@/app/providers/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ProgressChart } from "@/components/ProgressChart";
import {
  getWoundProfiles,
  getWoundProfile,
  seedPlaceholderData,
  getUserWounds,
  getWoundImages,
  createWoundProfile,
} from "@/lib/wounds";
import { Plus, Flame, Trophy, Target, ChevronRight, Camera } from "lucide-react";

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
  /** Full image/record items from the API (for "all items" list) */
  imageItems?: any[];
};

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export default function Dashboard() {
  const router = useRouter();
  const [username, setUsername] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<ProfileDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [creatingWound, setCreatingWound] = useState(false);
  const [showNewWoundForm, setShowNewWoundForm] = useState(false);
  const [newWoundName, setNewWoundName] = useState("");

  const { user: fbUser, loading: authLoading, authEnabled } = useAuth();

  async function handleNewWound(name?: string) {
    if (authEnabled && !fbUser) return;
    try {
      setCreatingWound(true);
      const woundId = await createWoundProfile(name?.trim() || undefined);
      setShowNewWoundForm(false);
      setNewWoundName("");
      router.push(`/capture?woundId=${encodeURIComponent(woundId)}`);
    } catch (err: any) {
      console.error("Create wound failed:", err);
      alert("Could not create wound: " + (err?.message ?? String(err)));
    } finally {
      setCreatingWound(false);
    }
  }

  useEffect(() => {
    
    if (authEnabled && authLoading) {
      setLoading(false);
      setProfiles([]);
      return;
    }

    
    if (authEnabled && !fbUser) {
      setUsername(null);
      setSelectedProfile(null);
    }

    setUsername(getUser()?.username ?? null);
    loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fbUser, authLoading, authEnabled]);

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

      
      let data: any[] = await getUserWounds();
      let normalized = normalizeProfiles(
        data.map((d) => ({ id: d.id, name: d.name ?? d.id, createdAt: d.last_timestamp, location: "", record_count: d.image_count, streak: 0, achievement_count: 0 }))
      );

      
      if (!normalized.length) {
        const fallback: any[] = await getWoundProfiles();
        normalized = normalizeProfiles(fallback);
        if (!normalized.length) {
          await seedPlaceholderData();
          const again: any[] = await getWoundProfiles();
          normalized = normalizeProfiles(again);
        }
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
      const images = await getWoundImages(profileId);
      const imageOnly = (images || []).filter(
        (it: any) => (it.sk && it.sk.includes("#IMG#")) || it.imageKey
      );

      if (!imageOnly.length) {
        setSelectedProfile({
          id: profileId,
          name: profileId,
          createdAt: undefined,
          location: "",
          record_count: 0,
          streak: 0,
          achievement_count: 0,
          wound_type: "",
          start_date: "",
          notes: "",
          achievements: [],
          healing_prediction: undefined,
          records: [],
          imageItems: [],
        });
        return;
      }

      const records: WoundRecord[] = imageOnly.map((it: any) => {
        const recAt = it.timestamp || it.created_at || it.sk || new Date().toISOString();
        const analysis = it.analysis || {};
        const measurements = analysis.measurements || {};
        const area = measurements.area_cm2 ?? measurements.area ?? it.area ?? 0;
        return { recorded_at: recAt, area_cm2: Number(area || 0) };
      });

      const detail: ProfileDetail = {
        id: profileId,
        name: profileId,
        createdAt: imageOnly[0]?.timestamp || imageOnly[0]?.created_at,
        location: "",
        record_count: records.length,
        streak: 0,
        achievement_count: 0,
        wound_type: "",
        start_date: "",
        notes: "",
        achievements: [],
        healing_prediction: undefined,
        records,
        imageItems: imageOnly,
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

    // NOTE: This is the original formula for healedPct.
    // It keeps healed percentage at 0% (not negative) when the wound gets worse.
    // const healedPct =
    //   initialArea > 0
    //     ? Math.max(0, Math.min(100, (areaReduction / initialArea) * 100))
    //     : 0;

    // NOTE: This is the modified formula for healedPct.
    // It allows the healed percentage to go negative when the wound gets worse.
    const healedPct =
    initialArea > 0
      ? Math.min(100, (areaReduction / initialArea) * 100)
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

  const captureHref = selectedProfile
    ? `/capture?woundId=${encodeURIComponent(selectedProfile.id)}`
    : "/capture";

  const selectedProfileName = selectedProfile
    ? (profiles.find((p) => p.id === selectedProfile.id)?.name ?? selectedProfile.name)
    : null;

  return (
    <div className="ws-container space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
            Dashboard
          </h1>
          <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
            {username ? `Hi ${username}` : "Your wound tracking hub"}
          </p>
        </div>
        {selectedProfile && (
          <Button asChild size="lg" className="gap-2 rounded-xl font-medium shrink-0">
            <Link href={captureHref}>
              <Camera className="h-5 w-5" />
              Add photo to {selectedProfileName}
            </Link>
          </Button>
        )}
      </div>

      {/* Wound Profile Selector */}
      <div className="ws-card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-lg font-semibold text-slate-800">Your Wounds</div>
          {!showNewWoundForm ? (
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => setShowNewWoundForm(true)}
              disabled={authEnabled && !fbUser}
            >
              <Plus className="h-4 w-4" />
              New Wound
            </Button>
          ) : null}
        </div>

        {showNewWoundForm ? (
          <div className="mb-4 p-4 rounded-lg border-2 border-slate-200 bg-slate-50 space-y-3">
            <Label htmlFor="new-wound-name" className="text-slate-700">Profile name</Label>
            <Input
              id="new-wound-name"
              placeholder="e.g. Left knee scrape"
              value={newWoundName}
              onChange={(e) => setNewWoundName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleNewWound(newWoundName);
                if (e.key === "Escape") setShowNewWoundForm(false);
              }}
              className="max-w-sm"
              autoFocus
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => handleNewWound(newWoundName)}
                disabled={creatingWound}
              >
                {creatingWound ? "Creating…" : "Create & go to capture"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setShowNewWoundForm(false); setNewWoundName(""); }}
                disabled={creatingWound}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : null}

        {authEnabled && authLoading ? (
          <div className="text-center py-8 text-slate-500">Checking sign-in...</div>
        ) : loading ? (
          <div className="text-center py-8 text-slate-500">Loading your wounds...</div>
        ) : authEnabled && !fbUser ? (
          <div className="text-center py-8 text-slate-500">
            Sign in to see your wound profiles.
          </div>
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
                  className={`text-left p-4 rounded-xl border-2 transition-all hover:shadow-md flex items-center justify-between gap-3 ${
                    selectedProfile?.id === profile.id
                      ? "border-blue-500 bg-blue-50 ring-2 ring-blue-200"
                      : "border-slate-200 bg-white hover:border-blue-300"
                  }`}
                >
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-800 truncate">{profile.name}</div>
                    {profile.location ? (
                      <div className="text-sm text-slate-500 mt-0.5">{profile.location}</div>
                    ) : null}
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-600">
                      <span>
                        {recordCount} {recordCount === 1 ? "photo" : "photos"}
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
                  </div>
                  <ChevronRight
                    className={`h-5 w-5 flex-shrink-0 text-slate-400 ${
                      selectedProfile?.id === profile.id ? "text-blue-600" : ""
                    }`}
                  />
                </button>
              );
            })}
          </div>
        )}
      </div>

      {!selectedProfile && profiles.length > 0 && (
        <div className="ws-card p-5 border-dashed border-2 border-slate-200 bg-slate-50/50">
          <p className="text-slate-600 text-center py-2">
            👆 Select a wound above to see details, photos, and add new ones.
          </p>
        </div>
      )}

      {selectedProfile && (
        <>
          <div className="ws-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <span className="inline-flex items-center justify-center w-2 h-2 rounded-full bg-blue-500" aria-hidden />
              <h2 className="text-lg font-semibold text-slate-800">
                {selectedProfileName}
              </h2>
            </div>
            {(selectedProfile.location || selectedProfile.wound_type || selectedProfile.start_date || selectedProfile.notes) ? (
              <div className="space-y-1 text-sm text-slate-600">
                {selectedProfile.location ? (
                  <div><span className="font-medium">Location:</span> {selectedProfile.location}</div>
                ) : null}
                {selectedProfile.wound_type ? (
                  <div><span className="font-medium">Type:</span> {selectedProfile.wound_type}</div>
                ) : null}
                {selectedProfile.start_date ? (
                  <div><span className="font-medium">Started:</span> {new Date(selectedProfile.start_date).toLocaleDateString()}</div>
                ) : null}
                {selectedProfile.notes ? (
                  <div><span className="font-medium">Notes:</span> {selectedProfile.notes}</div>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No extra details yet. Add photos to track healing.</p>
            )}
          </div>

          {/* All items in this profile */}
          {(selectedProfile.imageItems?.length ?? 0) > 0 && (
            <div className="ws-card p-5">
              <div className="text-lg font-semibold text-slate-800 mb-3">
                All records ({selectedProfile.imageItems!.length})
              </div>
              <ul className="space-y-3">
                {selectedProfile.imageItems!.map((item: any, index: number) => {
                  const recAt = item.timestamp || item.created_at || item.sk || "";
                  const analysis = item.analysis || {};
                  const measurements = analysis.measurements || {};
                  const area = measurements.area_cm2 ?? measurements.area ?? item.area ?? null;
                  const healing = analysis.healing_assessment || {};
                  const stage = healing.healing_stage ?? healing.healing_progress ?? null;
                  const severity = healing.severity ?? null;
                  const viewUrl = item.viewUrl || null;
                  return (
                    <li
                      key={item.sk || item.timestamp || index}
                      className="flex items-start gap-4 py-3 px-3 rounded-lg border border-slate-200 bg-slate-50/50 text-sm"
                    >
                      {viewUrl ? (
                        <img
                          src={viewUrl}
                          alt=""
                          className="w-24 h-24 rounded-lg object-cover flex-shrink-0 border border-slate-200 bg-slate-100"
                        />
                      ) : (
                        <div className="w-24 h-24 rounded-lg flex-shrink-0 border border-slate-200 bg-slate-200 flex items-center justify-center text-slate-500 text-xs">
                          No image
                        </div>
                      )}
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 min-w-0">
                        <span className="font-medium text-slate-800">
                          {recAt ? new Date(recAt).toLocaleString() : "—"}
                        </span>
                        {area != null && (
                          <span className="text-slate-600">Area: {Number(area).toFixed(2)} cm²</span>
                        )}
                        {stage && (
                          <span className="text-slate-600">Stage: {String(stage)}</span>
                        )}
                        {severity && (
                          <span className="text-slate-600">Severity: {String(severity)}</span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

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

      {/* Overview (scoped to selected profile when present) */}
      {selectedProfile && (
        <>
          <div className="text-lg font-semibold text-slate-800">At a glance</div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="ws-card p-5">
              <div className="flex items-end justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-slate-600">Healing progress</div>
                  <div className="text-xs text-slate-500 mt-0.5">Last update: {lastUpdateText}</div>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold text-blue-600">{healedPct.toFixed(0)}%</div>
                  <div className="text-xs text-slate-500">healed</div>
                </div>
              </div>
              <div className="mt-3 h-2 w-full rounded-full bg-slate-200">
                <div
                  className="h-2 rounded-full bg-blue-600 transition-all"
                  // style={{ width: `${Math.min(100, Math.max(0, healedPct))}%` }}
                  style={{ width: `${Math.min(100, healedPct)}%` }}
                />
              </div>
            </div>
            <div className="ws-card p-5">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-xl font-semibold text-slate-900">{totalPhotos}</div>
                  <div className="text-xs text-slate-600">photos</div>
                </div>
                <div>
                  <div className="text-xl font-semibold text-slate-900">{daysTracked}</div>
                  <div className="text-xs text-slate-600">days</div>
                </div>
                <div>
                  <div className="text-xl font-semibold text-slate-900">{avgIntervalDays || "—"}</div>
                  <div className="text-xs text-slate-600">avg gap</div>
                </div>
              </div>
            </div>
          </div>
          <div className="ws-card p-5">
            <div className="text-sm font-semibold text-slate-800">Insight</div>
            <p className="mt-1 text-slate-600 text-sm">{insightText}</p>
            <div className="mt-3 rounded-lg border border-blue-100 bg-blue-50/80 px-3 py-2 text-slate-700 text-sm">
              💡 {randomTip}
            </div>
            <p className="mt-2 text-xs text-slate-500">{nextUploadText}</p>
          </div>
        </>
      )}

      {/* Navigation */}
      <nav className="flex flex-wrap gap-2 pt-2">
        <Button asChild size="default" className="rounded-xl font-medium">
          <Link href={captureHref} className="gap-2">
            <Camera className="h-4 w-4" />
            {selectedProfile ? `Add photo to ${selectedProfileName}` : "Capture / Upload"}
          </Link>
        </Button>
        <Button asChild variant="outline" size="default" className="rounded-xl font-medium">
          <Link href="/progress">Progress</Link>
        </Button>
        <Button asChild variant="outline" size="default" className="rounded-xl font-medium">
          <Link href="/tips">Tips</Link>
        </Button>
        <Button asChild variant="outline" size="default" className="rounded-xl font-medium">
          <Link href="/profile">Profile</Link>
        </Button>
      </nav>

      <footer className="text-xs text-slate-400 pt-4 pb-2">
        Backend: {BACKEND_URL}
      </footer>
    </div>
  );
}