"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { getUser } from "@/lib/auth";
import { useAuth } from "@/app/providers/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ProgressChart } from "@/components/ProgressChart";
import {
  getUserWounds,
  getWoundImages,
  createWoundProfile,
  deleteWoundImage,
  isAuthStartupError,
} from "@/lib/wounds";
import {
  Plus,
  Flame,
  Trophy,
  Target,
  ChevronRight,
  Camera,
  Trash2,
} from "lucide-react";

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

type MetricSnapshot = {
  recorded_at: string;
  area_cm2: number | null;
  infection_pct: number | null;
  redness_pct: number | null;
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
  records: WoundRecord[];
  imageItems: any[];
};

const BACKEND_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const PAGE_TOP_PADDING = "max(calc(env(safe-area-inset-top) + 12px), 56px)";
const PAGE_BOTTOM_PADDING = "max(calc(env(safe-area-inset-bottom) + 12px), 20px)";

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

function getRecordedAt(item: any): string {
  return (
    item?.timestamp ||
    item?.created_at ||
    item?.recorded_at ||
    item?.updated_at ||
    item?.captured_at ||
    item?.date ||
    item?.sk ||
    new Date(0).toISOString()
  );
}

function getAreaCm2(item: any): number | null {
  const analysis = item?.analysis || {};
  const measurements = analysis?.measurements || {};

  const raw =
    measurements?.area_cm2 ??
    measurements?.area ??
    item?.area_cm2 ??
    item?.area ??
    null;

  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? value : null;
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

function deriveInfectionPercent(analysis: any): number | null {
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

  return null;
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

function deriveRednessPercent(analysis: any): number | null {
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

  return null;
}

function getDisplayImageUrl(item: any): string | null {
  const direct =
    item?.viewUrl ||
    item?.thumbnailUrl ||
    item?.image_url ||
    item?.url ||
    item?.imageUrl ||
    null;

  if (direct) return String(direct);

  const annotated = item?.analysis?.annotated_image;
  if (typeof annotated === "string" && annotated.trim()) {
    return annotated.startsWith("data:")
      ? annotated
      : `data:image/jpeg;base64,${annotated}`;
  }

  return null;
}

function isRealImageRecord(item: any): boolean {
  if (!item || typeof item !== "object") return false;

  const sk = String(item?.sk ?? "");

  const definitelyNotImage =
    sk.includes("#PROFILE#") ||
    sk.includes("#SUMMARY#") ||
    sk.includes("#META#") ||
    sk.endsWith("#META") ||
    item?.entityType === "profile" ||
    item?.type === "profile";

  if (definitelyNotImage) return false;

  const hasExplicitImageMarker =
    sk.includes("#IMG#") || sk.includes("#IMAGE#");

  const hasImageAsset =
    !!item?.imageKey ||
    !!item?.storageKey ||
    !!item?.s3Key ||
    !!getDisplayImageUrl(item);

  return hasExplicitImageMarker || hasImageAsset;
}

function stripGeneratedSuffix(value: string): string {
  return String(value || "").replace(/-[a-f0-9]{8}$/i, "");
}

function prettifyWoundName(value: string): string {
  const cleaned = stripGeneratedSuffix(value).replace(/[-_]+/g, " ").trim();
  if (!cleaned) return "New wound";

  return cleaned.replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeProfiles(raw: any[]): ProfileSummary[] {
  return (raw || [])
    .map((p: any) => ({
      id: String(p?.id ?? ""),
      name: prettifyWoundName(String(p?.name ?? p?.id ?? "Untitled")),
      createdAt: p?.createdAt ?? p?.last_timestamp,
      location: p?.location ?? "",
      record_count:
        typeof p?.record_count === "number"
          ? p.record_count
          : typeof p?.image_count === "number"
          ? p.image_count
          : 0,
      streak: typeof p?.streak === "number" ? p.streak : 0,
      achievement_count:
        typeof p?.achievement_count === "number" ? p.achievement_count : 0,
    }))
    .filter((p) => p.id);
}

function normalizeImageItems(items: any[]): any[] {
  const seen = new Set<string>();

  const filtered = (items || []).filter((item: any) => isRealImageRecord(item));

  const deduped = filtered.filter((item: any) => {
    const key = String(
      item?.sk ??
        item?.imageKey ??
        item?.storageKey ??
        item?.s3Key ??
        getDisplayImageUrl(item) ??
        `${getRecordedAt(item)}`
    );

    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  deduped.sort(
    (a: any, b: any) =>
      new Date(getRecordedAt(b)).getTime() - new Date(getRecordedAt(a)).getTime()
  );

  return deduped;
}

function buildMeasuredRecords(imageItems: any[]): WoundRecord[] {
  return imageItems
    .map((item: any) => {
      const area = getAreaCm2(item);
      if (area === null) return null;

      return {
        recorded_at: getRecordedAt(item),
        area_cm2: area,
      };
    })
    .filter((record): record is WoundRecord => record !== null)
    .sort(
      (a, b) =>
        new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
    );
}

function buildMetricSnapshots(imageItems: any[]): MetricSnapshot[] {
  return imageItems
    .map((item: any) => {
      const analysis = item?.analysis || {};

      return {
        recorded_at: getRecordedAt(item),
        area_cm2: getAreaCm2(item),
        infection_pct: deriveInfectionPercent(analysis),
        redness_pct: deriveRednessPercent(analysis),
      };
    })
    .filter((snapshot) => !!snapshot.recorded_at)
    .sort(
      (a, b) =>
        new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
    );
}

function buildProfileDetail(base: ProfileSummary, rawItems: any[]): ProfileDetail {
  const imageItems = normalizeImageItems(rawItems);
  const measuredRecords = buildMeasuredRecords(imageItems);

  return {
    id: base.id,
    name: base.name,
    createdAt: imageItems[0] ? getRecordedAt(imageItems[0]) : base.createdAt,
    location: base.location ?? "",
    record_count: imageItems.length,
    streak: base.streak ?? 0,
    achievement_count: base.achievement_count ?? 0,
    wound_type: "",
    start_date: "",
    notes: "",
    achievements: [],
    healing_prediction: undefined,
    records: measuredRecords,
    imageItems,
  };
}

export default function Dashboard() {
  const router = useRouter();

  const [username, setUsername] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [detailsById, setDetailsById] = useState<Record<string, ProfileDetail>>({});
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [creatingWound, setCreatingWound] = useState(false);
  const [deletingImageRef, setDeletingImageRef] = useState<string | null>(null);
  const [showNewWoundForm, setShowNewWoundForm] = useState(false);
  const [newWoundName, setNewWoundName] = useState("");

  const { user: fbUser, loading: authLoading, authEnabled } = useAuth();

  const loadSeqRef = useRef(0);
  const selectedProfileIdRef = useRef<string | null>(null);
  const authUidRef = useRef<string | null>(null);

  useEffect(() => {
    selectedProfileIdRef.current = selectedProfileId;
  }, [selectedProfileId]);

  useEffect(() => {
    authUidRef.current = fbUser?.uid ?? null;
  }, [fbUser]);

  function clearDashboardState() {
    setProfiles([]);
    setDetailsById({});
    setSelectedProfileId(null);
  }

  async function handleNewWound(name?: string) {
    if (!fbUser) {
      alert("Please sign in first.");
      return;
    }

    try {
      setCreatingWound(true);
      const woundId = await createWoundProfile(name?.trim() || undefined);
      setShowNewWoundForm(false);
      setNewWoundName("");
      router.push(`/capture?woundId=${encodeURIComponent(woundId)}`);
    } catch (err: any) {
      console.warn("Create wound failed:", err);
      alert("Could not create wound: " + (err?.message ?? String(err)));
    } finally {
      setCreatingWound(false);
    }
  }

  async function loadDashboardData(
    preferredProfileId?: string | null,
    requestUid?: string | null
  ) {
    const seq = ++loadSeqRef.current;
    const targetUid = requestUid ?? authUidRef.current;

    try {
      setLoading(true);

      let data: any[] | null = null;

      for (let attempt = 1; attempt <= 2; attempt++) {
        try {
          data = await getUserWounds();
          break;
        } catch (error: any) {
          if (seq !== loadSeqRef.current) return;

          const authChanged = authUidRef.current !== targetUid;
          if (authChanged) return;

          if (isAuthStartupError(error)) {
            if (attempt < 2) {
              await sleep(800);
              continue;
            }
            return;
          }

          console.warn("Dashboard load skipped:", error);
          clearDashboardState();
          return;
        }
      }

      if (seq !== loadSeqRef.current) return;
      if (authUidRef.current !== targetUid) return;

      const baseProfiles = normalizeProfiles(
        ((data || []) as any[]).map((d: any) => ({
          id: d.id,
          name: d.name ?? d.id,
          createdAt: d.last_timestamp,
          location: "",
          record_count: d.image_count,
          streak: 0,
          achievement_count: 0,
        }))
      );

      if (!baseProfiles.length) {
        clearDashboardState();
        return;
      }

      const detailResults = await Promise.allSettled(
        baseProfiles.map(async (profile) => {
          try {
            const rawItems = await getWoundImages(profile.id);
            return buildProfileDetail(profile, rawItems);
          } catch (error: any) {
            if (!isAuthStartupError(error)) {
              console.warn(`Skipping wound image load for ${profile.id}:`, error);
            }
            return buildProfileDetail(profile, []);
          }
        })
      );

      if (seq !== loadSeqRef.current) return;
      if (authUidRef.current !== targetUid) return;

      const detailsMap: Record<string, ProfileDetail> = {};
      const hydratedProfiles: ProfileSummary[] = baseProfiles.map((profile, index) => {
        const result = detailResults[index];

        if (result.status === "fulfilled") {
          const detail = result.value;
          detailsMap[profile.id] = detail;

          return {
            ...profile,
            createdAt: detail.createdAt ?? profile.createdAt,
            record_count: detail.imageItems.length,
          };
        }

        return {
          ...profile,
          record_count: 0,
        };
      });

      setDetailsById(detailsMap);
      setProfiles(hydratedProfiles);

      const nextSelectedId =
        preferredProfileId && hydratedProfiles.some((p) => p.id === preferredProfileId)
          ? preferredProfileId
          : selectedProfileIdRef.current &&
            hydratedProfiles.some((p) => p.id === selectedProfileIdRef.current)
          ? selectedProfileIdRef.current
          : hydratedProfiles[0]?.id ?? null;

      setSelectedProfileId(nextSelectedId);
    } catch (error: any) {
      if (seq !== loadSeqRef.current) return;
      if (authUidRef.current !== targetUid) return;

      if (!isAuthStartupError(error)) {
        console.warn("Failed to load dashboard data:", error);
      }

      clearDashboardState();
    } finally {
      if (seq === loadSeqRef.current) {
        setLoading(false);
      }
    }
  }

  async function handleDeleteImage(item: any) {
    if (!selectedProfileId) return;

    const imageRef = String(item?.imageId || item?.sk || item?.imageKey || "").trim();
    if (!imageRef) {
      alert("Could not determine image id for deletion.");
      return;
    }

    const ok = window.confirm(
      "Delete this uploaded photo from this injury? This cannot be undone."
    );
    if (!ok) return;

    try {
      setDeletingImageRef(imageRef);
      await deleteWoundImage(selectedProfileId, imageRef);
      await loadDashboardData(selectedProfileId, authUidRef.current);
    } catch (err: any) {
      alert("Could not delete this photo: " + (err?.message ?? String(err)));
    } finally {
      setDeletingImageRef(null);
    }
  }

  useEffect(() => {
    if (authEnabled && authLoading) {
      loadSeqRef.current += 1;
      setLoading(true);
      return;
    }

    if (!fbUser) {
      loadSeqRef.current += 1;
      setUsername(null);
      clearDashboardState();
      setLoading(false);
      return;
    }

    setUsername(getUser()?.username ?? fbUser.email ?? null);
    void loadDashboardData(selectedProfileIdRef.current, fbUser.uid);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fbUser, authLoading, authEnabled]);

  const selectedProfile = useMemo(() => {
    if (!selectedProfileId) return null;
    return detailsById[selectedProfileId] ?? null;
  }, [detailsById, selectedProfileId]);

  const activeProfileId = selectedProfileId;
  const selectedProfileName = activeProfileId
    ? profiles.find((p) => p.id === activeProfileId)?.name ??
      detailsById[activeProfileId]?.name ??
      activeProfileId
    : null;

  const captureHref = activeProfileId
    ? `/capture?woundId=${encodeURIComponent(activeProfileId)}`
    : "/capture";

  const metricSnapshots = useMemo(() => {
    return buildMetricSnapshots(selectedProfile?.imageItems ?? []);
  }, [selectedProfile]);

  const {
    totalPhotos,
    lastUpdateText,
    healedPct,
    progressBarPct,
    daysTracked,
    avgIntervalDays,
    insightText,
    nextUploadText,
    stableTip,
  } = useMemo(() => {
    const imageItems = selectedProfile?.imageItems ?? [];
    const snapshots = metricSnapshots;
    const totalPhotos = imageItems.length;

    if (!imageItems.length) {
      return {
        totalPhotos: 0,
        lastUpdateText: "No uploads yet",
        healedPct: 0,
        progressBarPct: 0,
        daysTracked: 0,
        avgIntervalDays: 0,
        insightText:
          "No trend yet. Add your first photo to start tracking improvement.",
        nextUploadText: "As soon as you capture your first photo",
        stableTip: "Use consistent lighting and distance for each photo.",
      };
    }

    const imageTimeline = [...imageItems].sort(
      (a, b) =>
        new Date(getRecordedAt(a)).getTime() - new Date(getRecordedAt(b)).getTime()
    );

    const firstImageAt = getRecordedAt(imageTimeline[0]);
    const lastImageAt = getRecordedAt(imageTimeline[imageTimeline.length - 1]);
    const lastUpdateText = new Date(lastImageAt).toLocaleString();

    const msDay = 24 * 60 * 60 * 1000;
    const daysTracked = Math.max(
      1,
      Math.ceil(
        (new Date(lastImageAt).getTime() - new Date(firstImageAt).getTime()) / msDay
      )
    );

    let avgIntervalDays = 0;
    if (imageTimeline.length > 1) {
      let sum = 0;
      for (let i = 1; i < imageTimeline.length; i++) {
        sum +=
          (new Date(getRecordedAt(imageTimeline[i])).getTime() -
            new Date(getRecordedAt(imageTimeline[i - 1])).getTime()) /
          msDay;
      }
      avgIntervalDays = +(sum / (imageTimeline.length - 1)).toFixed(1);
    }

    const tips = [
      "Use the same lighting and distance each time.",
      "Try to upload every 2 to 3 days for a cleaner trend line.",
      "Keep the wound centered in the frame.",
      "Add a size reference whenever possible.",
    ];
    const stableTip =
      tips[(selectedProfile?.id?.length ?? totalPhotos) % tips.length];

    if (snapshots.length < 2) {
      const next = new Date(new Date(lastImageAt).getTime() + 2 * msDay);
      return {
        totalPhotos,
        lastUpdateText,
        healedPct: 0,
        progressBarPct: 0,
        daysTracked,
        avgIntervalDays,
        insightText:
          "Photos are saved, but you need at least 2 records to show a reliable healing trend.",
        nextUploadText: `Suggested next upload: ${next.toLocaleDateString()}`,
        stableTip,
      };
    }

    const first = snapshots[0];
    const last = snapshots[snapshots.length - 1];

    const components: Array<{ weight: number; change: number }> = [];
    const insightParts: string[] = [];

    if (
      first.area_cm2 !== null &&
      last.area_cm2 !== null &&
      first.area_cm2 > 0
    ) {
      const areaDelta = first.area_cm2 - last.area_cm2;
      const areaChange = clamp(areaDelta / first.area_cm2, -1, 1);
      components.push({ weight: 0.5, change: areaChange });

      if (Math.abs(areaDelta) < 0.01) {
        insightParts.push("size unchanged");
      } else if (areaDelta > 0) {
        insightParts.push(`size down ${Math.abs(areaDelta).toFixed(2)} cm²`);
      } else {
        insightParts.push(`size up ${Math.abs(areaDelta).toFixed(2)} cm²`);
      }
    }

    if (first.infection_pct !== null && last.infection_pct !== null) {
      const infectionDelta = first.infection_pct - last.infection_pct;
      const infectionChange = clamp(infectionDelta / 100, -1, 1);
      components.push({ weight: 0.25, change: infectionChange });

      if (Math.abs(infectionDelta) < 1) {
        insightParts.push("infection stable");
      } else if (infectionDelta > 0) {
        insightParts.push(`infection down ${Math.abs(infectionDelta).toFixed(0)}%`);
      } else {
        insightParts.push(`infection up ${Math.abs(infectionDelta).toFixed(0)}%`);
      }
    }

    if (first.redness_pct !== null && last.redness_pct !== null) {
      const rednessDelta = first.redness_pct - last.redness_pct;
      const rednessChange = clamp(rednessDelta / 100, -1, 1);
      components.push({ weight: 0.25, change: rednessChange });

      if (Math.abs(rednessDelta) < 1) {
        insightParts.push("redness stable");
      } else if (rednessDelta > 0) {
        insightParts.push(`redness down ${Math.abs(rednessDelta).toFixed(0)}%`);
      } else {
        insightParts.push(`redness up ${Math.abs(rednessDelta).toFixed(0)}%`);
      }
    }

    const totalWeight = components.reduce((sum, part) => sum + part.weight, 0);
    const weightedImprovement =
      totalWeight > 0
        ? components.reduce((sum, part) => sum + part.change * part.weight, 0) /
          totalWeight
        : 0;

    const healedPct = clamp(weightedImprovement * 100, 0, 100);
    const progressBarPct = healedPct;

    const trend =
      weightedImprovement > 0.05
        ? "Improving"
        : weightedImprovement < -0.05
        ? "Worsening"
        : "Stable";

    const insightText =
      insightParts.length > 0
        ? `${trend}. ${insightParts.join(", ")}.`
        : `${trend}. Not enough comparable metrics to calculate a detailed trend.`;

    const next = new Date(new Date(lastImageAt).getTime() + 2 * msDay);

    return {
      totalPhotos,
      lastUpdateText,
      healedPct,
      progressBarPct,
      daysTracked,
      avgIntervalDays,
      insightText,
      nextUploadText: `Suggested next upload: ${next.toLocaleDateString()}`,
      stableTip,
    };
  }, [selectedProfile, metricSnapshots]);

  return (
    <div
      className="ws-container space-y-6"
      style={{
        paddingTop: PAGE_TOP_PADDING,
        paddingBottom: PAGE_BOTTOM_PADDING,
      }}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
            Dashboard
          </h1>
          <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
            {username ? `Hi ${username}` : "Your wound tracking hub"}
          </p>
        </div>

        {activeProfileId && (
          <Button
            asChild
            size="lg"
            className="w-full sm:w-auto gap-2 rounded-xl font-medium justify-center shrink-0"
          >
            <Link href={captureHref}>
              <Camera className="h-5 w-5" />
              Add photo to {selectedProfileName}
            </Link>
          </Button>
        )}
      </div>

      <div className="ws-card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-lg font-semibold text-slate-800">Your Wounds</div>

          {!showNewWoundForm ? (
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => setShowNewWoundForm(true)}
              disabled={!fbUser}
            >
              <Plus className="h-4 w-4" />
              New Wound
            </Button>
          ) : null}
        </div>

        {showNewWoundForm ? (
          <div className="mb-4 p-4 rounded-lg border-2 border-slate-200 bg-slate-50 space-y-3">
            <Label htmlFor="new-wound-name" className="text-slate-700">
              Profile name
            </Label>

            <Input
              id="new-wound-name"
              placeholder="e.g. Left knee scrape"
              value={newWoundName}
              onChange={(e) => setNewWoundName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleNewWound(newWoundName);
                if (e.key === "Escape") {
                  setShowNewWoundForm(false);
                  setNewWoundName("");
                }
              }}
              className="max-w-sm"
              autoFocus
            />

            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => void handleNewWound(newWoundName)}
                disabled={creatingWound}
              >
                {creatingWound ? "Creating…" : "Create & go to capture"}
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowNewWoundForm(false);
                  setNewWoundName("");
                }}
                disabled={creatingWound}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : null}

        {authEnabled && authLoading ? (
          <div className="text-center py-8 text-slate-500">Checking sign in...</div>
        ) : loading ? (
          <div className="text-center py-8 text-slate-500">Loading your wounds...</div>
        ) : !fbUser ? (
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
              const recordCount = detailsById[profile.id]?.imageItems?.length ?? 0;
              const streak = profile.streak ?? 0;
              const badgeCount = profile.achievement_count ?? 0;
              const isSelected = selectedProfileId === profile.id;

              return (
                <div
                  key={profile.id}
                  className={`text-left p-4 rounded-xl border-2 transition-all hover:shadow-md flex items-center justify-between gap-3 bg-white cursor-pointer ${
                    isSelected
                      ? "border-blue-500 ring-1 ring-blue-300"
                      : "border-slate-200 hover:border-blue-300"
                  }`}
                  onClick={() => setSelectedProfileId(profile.id)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-slate-800 truncate">
                      {profile.name}
                    </div>

                    {profile.location ? (
                      <div className="text-sm text-slate-500 mt-0.5">
                        {profile.location}
                      </div>
                    ) : null}

                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-600">
                      <span>
                        {recordCount} {recordCount === 1 ? "photo" : "photos"}
                      </span>

                      {streak > 0 && (
                        <span className="flex items-center gap-1 text-orange-600 font-medium whitespace-nowrap">
                          <Flame className="h-3 w-3 flex-shrink-0" />
                          {streak} day streak
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

                  <Link
                    href={`/wounds/${encodeURIComponent(profile.id)}`}
                    onClick={(e) => e.stopPropagation()}
                    className="flex-shrink-0 p-1 rounded hover:bg-slate-100"
                    title="View full history"
                  >
                    <ChevronRight className="h-5 w-5 text-slate-400" />
                  </Link>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {selectedProfile && (
        <>
          {selectedProfile.imageItems.length > 0 && (
            <div className="ws-card p-5">
              <div className="text-lg font-semibold text-slate-800 mb-3">
                All records ({selectedProfile.imageItems.length})
              </div>

              <ul className="space-y-3">
                {selectedProfile.imageItems.map((item: any, index: number) => {
                  const recAt = getRecordedAt(item);
                  const area = getAreaCm2(item);
                  const healing = item?.analysis?.healing_assessment || {};
                  const stage = healing?.healing_stage ?? healing?.healing_progress ?? null;
                  const severity = healing?.severity ?? null;
                  const viewUrl = getDisplayImageUrl(item);

                  return (
                    <li
                      key={item?.sk || item?.imageKey || `${recAt}-${index}`}
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

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 justify-between">
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 min-w-0">
                            <span className="font-medium text-slate-800">
                              {recAt ? new Date(recAt).toLocaleString() : "—"}
                            </span>

                            {area !== null && (
                              <span className="text-slate-600">
                                Area: {Number(area).toFixed(2)} cm²
                              </span>
                            )}

                            {stage && (
                              <span className="text-slate-600">Stage: {String(stage)}</span>
                            )}

                            {severity && (
                              <span className="text-slate-600">
                                Severity: {String(severity)}
                              </span>
                            )}
                          </div>

                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                            onClick={() => void handleDeleteImage(item)}
                            disabled={
                              deletingImageRef ===
                              String(item?.imageId || item?.sk || item?.imageKey || "")
                            }
                            title="Delete this photo"
                          >
                            <Trash2 className="h-4 w-4" />
                            {deletingImageRef ===
                            String(item?.imageId || item?.sk || item?.imageKey || "")
                              ? "Deleting..."
                              : "Delete"}
                          </Button>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

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
                        {selectedProfile.streak} Day Streak
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
                    {new Date(
                      selectedProfile.healing_prediction.predicted_date
                    ).toLocaleDateString()}
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
                      {String(
                        selectedProfile.healing_prediction.current_healing_rate
                      ).toUpperCase()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <ProgressChart key={selectedProfile.id} profileId={selectedProfile.id} />

          <div className="text-lg font-semibold text-slate-800">At a glance</div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="ws-card p-5">
              <div className="flex items-end justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-slate-600">
                    Healing progress
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    Last update: {lastUpdateText}
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-3xl font-bold text-blue-600">
                    {healedPct.toFixed(0)}%
                  </div>
                  <div className="text-xs text-slate-500">healed</div>
                </div>
              </div>

              <div className="mt-3 h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                <div
                  className="h-2 rounded-full bg-blue-600 transition-all"
                  style={{ width: `${progressBarPct}%` }}
                />
              </div>
            </div>

            <div className="ws-card p-5">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-xl font-semibold text-slate-900">
                    {totalPhotos}
                  </div>
                  <div className="text-xs text-slate-600">photos</div>
                </div>
                <div>
                  <div className="text-xl font-semibold text-slate-900">
                    {daysTracked}
                  </div>
                  <div className="text-xs text-slate-600">days</div>
                </div>
                <div>
                  <div className="text-xl font-semibold text-slate-900">
                    {avgIntervalDays || "—"}
                  </div>
                  <div className="text-xs text-slate-600">avg gap</div>
                </div>
              </div>
            </div>
          </div>

          <div className="ws-card p-5">
            <div className="text-sm font-semibold text-slate-800">Insight</div>
            <p className="mt-1 text-slate-600 text-sm">{insightText}</p>
            <div className="mt-3 rounded-lg border border-blue-100 bg-blue-50/80 px-3 py-2 text-slate-700 text-sm">
              💡 {stableTip}
            </div>
            <p className="mt-2 text-xs text-slate-500">{nextUploadText}</p>
          </div>
        </>
      )}

      <nav className="flex flex-wrap gap-2 pt-2">
        <Button asChild size="default" className="rounded-xl font-medium">
          <Link href={captureHref} className="gap-2">
            <Camera className="h-4 w-4" />
            {activeProfileId
              ? `Add photo to ${selectedProfileName}`
              : "Capture / Upload"}
          </Link>
        </Button>

        <Button
          asChild
          variant="outline"
          size="default"
          className="rounded-xl font-medium"
        >
          <Link href="/tips">Tips</Link>
        </Button>

        <Button
          asChild
          variant="outline"
          size="default"
          className="rounded-xl font-medium"
        >
          <Link href="/profile">Profile</Link>
        </Button>
      </nav>

      <footer className="text-xs text-slate-400 pt-4 pb-2">
        Backend: {BACKEND_URL}
      </footer>
    </div>
  );
}