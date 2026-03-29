import { getAuthToken } from "@/lib/auth";

const BACKEND_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const DEFAULT_AUTH_ATTEMPTS = 4;

async function readErrorBody(res: Response): Promise<string> {
  try {
    const text = await res.text();
    return text || res.statusText;
  } catch {
    return res.statusText;
  }
}

async function wait(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

function buildHeaders(
  initHeaders?: HeadersInit,
  extraHeaders?: Record<string, string>
): Headers {
  const headers = new Headers(initHeaders);

  if (extraHeaders) {
    for (const [key, value] of Object.entries(extraHeaders)) {
      headers.set(key, value);
    }
  }

  return headers;
}

function isUnauthorizedStatus(status: number) {
  return status === 401 || status === 403;
}

export function isAuthStartupError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /not authenticated|unauthorized|\(401\)|\b401\b/i.test(message);
}

type AuthFetchOptions = {
  maxAttempts?: number;
};

async function authFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
  options: AuthFetchOptions = {}
): Promise<Response> {
  const maxAttempts = options.maxAttempts ?? DEFAULT_AUTH_ATTEMPTS;
  let lastResponse: Response | null = null;
  let lastHadToken = false;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const token = await getAuthToken(attempt > 1);
    lastHadToken = !!token;

    if (!token) {
      if (attempt < maxAttempts) {
        await wait(600 * attempt);
        continue;
      }
      break;
    }

    const res = await fetch(input, {
      ...init,
      headers: buildHeaders(init.headers, {
        Authorization: `Bearer ${token}`,
      }),
    });

    if (!isUnauthorizedStatus(res.status)) {
      return res;
    }

    lastResponse = res;

    if (attempt < maxAttempts) {
      await wait(600 * attempt);
    }
  }

  if (lastResponse) {
    return lastResponse;
  }

  if (!lastHadToken) {
    throw new Error("Not authenticated. Please sign in again.");
  }

  throw new Error("Authentication failed. Please sign in again.");
}

export async function getWoundProfiles(): Promise<any[]> {
  return await getUserWounds();
}

export async function getWoundProfile(id: string): Promise<any | null> {
  const images = await getWoundImages(id);
  if (!images.length) return null;

  const records = images.map((it: any) => ({
    id: it.sk || it.timestamp || "",
    recorded_at: it.timestamp || it.created_at || it.recorded_at || it.sk,
    length_cm: it.analysis?.measurements?.length_cm ?? 0,
    width_cm: it.analysis?.measurements?.width_cm ?? 0,
    area_cm2: it.analysis?.measurements?.area_cm2 ?? 0,
    healing_stage:
      it.analysis?.healing_assessment?.healing_stage ??
      it.analysis?.healing_stage ??
      null,
    severity:
      it.analysis?.healing_assessment?.severity ??
      it.analysis?.severity ??
      null,
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
}

export async function seedPlaceholderData(): Promise<void> {
  try {
    await fetch(`${BACKEND_URL}/api/wounds/seed`, {
      method: "POST",
    });
  } catch {
    // ignore
  }
}

export async function predictOnly(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("image", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);

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

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);

    if (err?.name === "AbortError") {
      throw new Error(
        "Analysis timed out after 60 seconds. Please try again with a smaller image."
      );
    }

    throw err;
  }
}

export async function processAndUploadWound(file: File, woundId: string) {
  const formData = new FormData();
  formData.append("image", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);

  try {
    const predictRes = await fetch(`${BACKEND_URL}/predict`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!predictRes.ok) {
      throw new Error(
        `Predict failed (${predictRes.status}): ${await readErrorBody(predictRes)}`
      );
    }

    const predictData = await predictRes.json();

    const uploadUrlRes = await authFetch(
      `${BACKEND_URL}/wounds/${encodeURIComponent(
        woundId
      )}/upload-url?content_type=${encodeURIComponent(file.type || "image/jpeg")}`,
      {
        method: "POST",
      }
    );

    if (!uploadUrlRes.ok) {
      throw new Error(
        `Upload URL failed (${uploadUrlRes.status}): ${await readErrorBody(uploadUrlRes)}`
      );
    }

    const { uploadUrl, imageKey } = await uploadUrlRes.json();

    if (!imageKey) {
      throw new Error("Upload URL response did not include imageKey");
    }

    if (uploadUrl) {
      const uploadRes = await fetch(uploadUrl, {
        method: "PUT",
        headers: {
          "Content-Type": file.type || "image/jpeg",
        },
        body: file,
      });

      if (!uploadRes.ok) {
        throw new Error(`Image upload failed (${uploadRes.status})`);
      }
    }

    let analysisToSave = predictData;

    if (!predictData.annotated_image) {
      try {
        const imgBase64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();

          reader.onload = () => {
            const result = reader.result as string;
            resolve(result.includes(",") ? result.split(",")[1] : result);
          };

          reader.onerror = reject;
          reader.readAsDataURL(file);
        });

        analysisToSave = {
          ...predictData,
          annotated_image: imgBase64,
        };
      } catch {
        // leave analysis as-is
      }
    }

    const saveRes = await authFetch(
      `${BACKEND_URL}/wounds/${encodeURIComponent(woundId)}/images`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          imageKey,
          timestamp: new Date().toISOString(),
          healingScore: predictData.healing_assessment?.score ?? 0,
          analysis: analysisToSave,
        }),
      }
    );

    if (!saveRes.ok) {
      throw new Error(
        `Saving wound image metadata failed (${saveRes.status}): ${await readErrorBody(saveRes)}`
      );
    }

    const savedJson = await saveRes.json().catch(() => null);
    if (savedJson && savedJson.ok === false) {
      throw new Error(savedJson.error || "Saving wound image metadata failed");
    }

    return {
      success: true,
      analysis: predictData,
    };
  } catch (err: any) {
    clearTimeout(timeoutId);

    if (err?.name === "AbortError") {
      throw new Error(
        "Analysis timed out after 60 seconds. Please try again with a smaller image."
      );
    }

    throw err;
  }
}

export async function getUserWounds(): Promise<any[]> {
  const res = await authFetch(`${BACKEND_URL}/wounds`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Get wounds failed (${res.status}): ${await readErrorBody(res)}`);
  }

  const json = await res.json();
  return json?.ok ? (json.wounds ?? []) : [];
}

export async function createWoundProfile(name?: string): Promise<string> {
  const res = await authFetch(`${BACKEND_URL}/wounds`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(name?.trim() ? { name: name.trim() } : {}),
  });

  if (!res.ok) {
    throw new Error(`Create wound failed (${res.status}): ${await readErrorBody(res)}`);
  }

  const json = await res.json();

  if (!json?.ok || !json?.woundId) {
    throw new Error("Create wound did not return woundId");
  }

  return json.woundId;
}

export async function getWoundImages(woundId: string): Promise<any[]> {
  const res = await authFetch(
    `${BACKEND_URL}/wounds/${encodeURIComponent(woundId)}/images`,
    {
      cache: "no-store",
    }
  );

  if (res.status === 404) {
    return [];
  }

  if (!res.ok) {
    throw new Error(
      `Get wound images failed (${res.status}): ${await readErrorBody(res)}`
    );
  }

  const json = await res.json();
  return json?.ok ? (json.images ?? []) : [];
}

export async function deleteWound(woundId: string): Promise<void> {
  const res = await authFetch(
    `${BACKEND_URL}/wounds/${encodeURIComponent(woundId)}`,
    {
      method: "DELETE",
    }
  );

  if (!res.ok) {
    throw new Error(`Delete wound failed (${res.status}): ${await readErrorBody(res)}`);
  }
}

export async function deleteWoundImage(woundId: string, imageRef: string): Promise<void> {
  const ref = (imageRef || "").trim();
  if (!ref) throw new Error("Image reference is required");

  const res = await authFetch(
    `${BACKEND_URL}/wounds/${encodeURIComponent(woundId)}/images/${encodeURIComponent(ref)}`,
    {
      method: "DELETE",
    }
  );

  if (!res.ok) {
    throw new Error(`Delete image failed (${res.status}): ${await readErrorBody(res)}`);
  }
}