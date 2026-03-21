// src/lib/wounds.ts
// Frontend API wrapper (kept loose to avoid TS build failures)


import { getAuthToken } from "@/lib/auth"; 

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

async function readErrorBody(res: Response): Promise<string> {
  try {
    const text = await res.text();
    return text || res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function getWoundProfiles(): Promise<any[]> {
  return await getUserWounds();
}

export async function getWoundProfile(id: string): Promise<any | null> {
  try {
    const images = await getWoundImages(id);
    if (!images || !images.length) return null;

    
    const records = images.map((it: any) => ({
      id: it.sk || it.timestamp || "",
      recorded_at: it.timestamp || it.created_at || it.sk,
      length_cm: it.analysis?.measurements?.length_cm ?? 0,
      width_cm: it.analysis?.measurements?.width_cm ?? 0,
      area_cm2: it.analysis?.measurements?.area_cm2 ?? 0,
      healing_stage: it.analysis?.healing_stage ?? null,
      severity: it.analysis?.severity ?? null,
      infection_risk: it.analysis?.infection_risk ?? null,
      confidence: it.analysis?.confidence ?? null,
    }));

    return {
      ok: true,
      profile: {
        id,
        name: id,
        records,
        record_count: records.length,
      },
    };
  } catch {
    return null;
  }
}

export async function seedPlaceholderData(): Promise<void> {
  try {
    await fetch(`${BACKEND_URL}/api/wounds/seed`, { method: "POST" });
  } catch {
    // ignore
  }
}
export async function predictOnly(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("image", file);
  const res = await fetch(`${BACKEND_URL}/predict`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    throw new Error(`Predict failed (${res.status}): ${await readErrorBody(res)}`);
  }
  return res.json();
}

export async function processAndUploadWound(
  file: File,
  woundId: string
) {
  const token = await getAuthToken();

  if (!token) throw new Error("Not authenticated");

  //Run Prediction First

  const formData = new FormData();
  formData.append("image", file);

  const predictRes = await fetch(
    `${BACKEND_URL}/predict`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!predictRes.ok) {
    throw new Error(`Predict failed (${predictRes.status}): ${await readErrorBody(predictRes)}`);
  }
  const predictData = await predictRes.json();

  if (!predictData.detected) {
    throw new Error("No wound detected");
  }

  // THen Get S3 Upload URL

  const uploadUrlRes = await fetch(
    `${BACKEND_URL}/wounds/${woundId}/upload-url?content_type=${encodeURIComponent(
      file.type || "image/jpeg"
    )}`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!uploadUrlRes.ok) {
    throw new Error(`upload-url failed (${uploadUrlRes.status}): ${await readErrorBody(uploadUrlRes)}`);
  }
  const { uploadUrl, imageKey } = await uploadUrlRes.json();
  if (!uploadUrl || !imageKey) {
    throw new Error("upload-url did not return uploadUrl/imageKey");
  }

  // then Upload Image to S3

  const s3PutRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      "Content-Type": file.type || "image/jpeg",
    },
    body: file,
  });
  if (!s3PutRes.ok) {
    throw new Error(`S3 PUT failed (${s3PutRes.status})`);
  }

  //Save Metadata to DynamoDB
  
  const metaRes = await fetch(`${BACKEND_URL}/wounds/${woundId}/images`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      imageKey,
      timestamp: new Date().toISOString(),
      healingScore: predictData.healing_assessment?.score ?? 0,
      analysis: predictData,
    }),
  });
  if (!metaRes.ok) {
    throw new Error(`Dynamo save failed (${metaRes.status}): ${await readErrorBody(metaRes)}`);
  }

  return {
    success: true,
    analysis: predictData,
  };
}

export async function getUserWounds(): Promise<any[]> {
  try {
    const token = await getAuthToken();
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const res = await fetch(`${BACKEND_URL}/wounds`, { cache: "no-store", headers });
    if (!res.ok) {
      console.warn("getUserWounds non-OK:", res.status, await readErrorBody(res));
      return [];
    }
    const json = await res.json();
    return json?.ok ? (json.wounds ?? []) : [];
  } catch (err) {
    console.error("getUserWounds error", err);
    return [];
  }
}

export async function createWoundProfile(name?: string): Promise<string> {
  const token = await getAuthToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetch(`${BACKEND_URL}/wounds`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(name != null ? { name } : {}),
  });
  if (!res.ok) {
    throw new Error(`Create wound failed (${res.status}): ${await readErrorBody(res)}`);
  }
  const json = await res.json();
  if (!json?.ok || !json.woundId) throw new Error("Create wound did not return woundId");
  return json.woundId;
}

export async function getWoundImages(woundId: string): Promise<any[]> {
  try {
    const token = await getAuthToken();
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const res = await fetch(`${BACKEND_URL}/wounds/${encodeURIComponent(woundId)}/images`, { cache: "no-store", headers });
    if (!res.ok) return [];
    const json = await res.json();
    return json?.ok ? (json.images ?? []) : [];
  } catch (err) {
    console.error("getWoundImages error", err);
    return [];
  }
}