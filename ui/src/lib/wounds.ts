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
  
  // Create AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
  
  try {
    const res = await fetch(`${BACKEND_URL}/predict`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    
    if (!res.ok) {
      throw new Error(`Predict failed (${res.status}): ${await readErrorBody(res)}`);
    }
    return res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error('Analysis timed out after 60 seconds. Please try again with a smaller image.');
    }
    throw err;
  }
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

  // Create AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
  
  try {
    const predictRes = await fetch(
      `${BACKEND_URL}/predict`,
      {
        method: "POST",
        body: formData,
        signal: controller.signal,
      }
    );
    clearTimeout(timeoutId);

    if (!predictRes.ok) {
      throw new Error(`Predict failed (${predictRes.status}): ${await readErrorBody(predictRes)}`);
    }
    const predictData = await predictRes.json();

    // Analysis succeeded — try to save to S3/DynamoDB but don't block results
    try {
      const uploadUrlRes = await fetch(
        `${BACKEND_URL}/wounds/${woundId}/upload-url?content_type=${encodeURIComponent(
          file.type || "image/jpeg"
        )}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (uploadUrlRes.ok) {
        const { uploadUrl, imageKey } = await uploadUrlRes.json();
        if (imageKey) {
          // Upload image to S3 only when a presigned URL is available
          if (uploadUrl) {
            await fetch(uploadUrl, {
              method: "PUT",
              headers: { "Content-Type": file.type || "image/jpeg" },
              body: file,
            });
          }

          // Ensure there's always a saved image.
          // If the backend didn't produce an annotated image, fall back to the
          // original file encoded as base64 so the thumbnail is never blank.
          let analysisToSave = predictData;
          if (!predictData.annotated_image) {
            try {
              const imgBase64 = await new Promise<string>((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                  const result = reader.result as string;
                  // strip "data:image/jpeg;base64," prefix
                  resolve(result.includes(",") ? result.split(",")[1] : result);
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
              });
              analysisToSave = { ...predictData, annotated_image: imgBase64 };
            } catch {
              // ignore – proceed without image
            }
          }

          // Always save metadata (SQLite locally, DynamoDB when AWS is configured)
          await fetch(`${BACKEND_URL}/wounds/${woundId}/images`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              imageKey,
              timestamp: new Date().toISOString(),
              healingScore: predictData.healing_assessment?.score ?? 0,
              analysis: analysisToSave,
            }),
          });
        }
      }
    } catch {
      // S3/DynamoDB not configured — still return analysis results
      console.warn("Cloud save skipped (S3/DynamoDB not configured)");
    }

    return {
      success: true,
      analysis: predictData,
    };
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error('Analysis timed out after 60 seconds. Please try again with a smaller image.');
    }
    throw err;
  }
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

export async function deleteWound(woundId: string): Promise<void> {
  const token = await getAuthToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetch(`${BACKEND_URL}/wounds/${encodeURIComponent(woundId)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await readErrorBody(res);
    throw new Error(`Delete wound failed (${res.status}): ${body}`);
  }
}