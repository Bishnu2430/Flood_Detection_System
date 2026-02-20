export type LatestReading =
  | {
      status: string;
    }
  | {
      id: number;
      distance_cm: number;
      rain_analog: number;
      float_status: number;
      predicted_risk: number | null;
      risk_probability: number | null;
      explanation: string | null;
      created_at: string;
    };

export type Readiness = {
  ready: boolean;
  db: { ok: boolean; error: string | null };
  serial: { ok: boolean; port: string | null; error: string | null };
  llm?: { ok: boolean; error: string | null; model: string | null };
};

export type ReadingsItem = {
  id: number;
  distance_cm: number;
  rain_analog: number;
  float_status: number;
  predicted_risk: number | null;
  risk_probability: number | null;
  created_at: string;
};

export type ReadingsResponse = {
  count: number;
  items: ReadingsItem[];
};

export type ShapTopFeature = {
  feature: string;
  value: number;
  shap: number;
  direction: "increases_risk" | "decreases_risk";
};

export type ShapExplainResponse =
  | { status: string }
  | {
      id: number;
      predicted_class: number;
      predicted_label: string;
      probability: number;
      target_class?: number;
      target_label?: string;
      target_probability?: number;
      top_features: ShapTopFeature[];
    };

export type MlPerfResponse =
  | { status: string }
  | {
      id: number;
      ok: boolean;
      predicted_risk: number | null;
      risk_probability: number | null;
      inference_ms?: number;
      error?: string | null;
      errors?: string[];
    };

const defaultBase = import.meta.env.DEV ? "http://127.0.0.1:8000" : "/api";

export const API_BASE = (import.meta.env.VITE_API_BASE ?? defaultBase).replace(
  /\/$/,
  "",
);

function buildUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith("/")) return `${API_BASE}${path}`;
  return `${API_BASE}/${path}`;
}

class HttpError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(`Request failed: ${status}`);
    this.name = "HttpError";
    this.status = status;
    this.body = body;
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(buildUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  const contentType = res.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");

  if (!res.ok) {
    const body = isJson
      ? await res.json().catch(() => null)
      : await res.text().catch(() => null);
    throw new HttpError(res.status, body);
  }

  if (!isJson) {
    throw new Error("Expected JSON response");
  }
  return (await res.json()) as T;
}

export async function fetchReadiness(): Promise<Readiness> {
  try {
    return await fetchJson<Readiness>(
      "/ready?require_serial=false&include_llm=true",
    );
  } catch (e) {
    // FastAPI returns 503 with { detail: { ...payload } } when not ready.
    if (e instanceof HttpError) {
      const body = e.body;
      if (typeof body === "object" && body !== null && "detail" in body) {
        const detail = (body as { detail?: unknown }).detail;
        if (typeof detail === "object" && detail !== null) {
          return detail as Readiness;
        }
      }
    }
    throw e;
  }
}

export async function fetchLatest(): Promise<LatestReading> {
  return await fetchJson<LatestReading>("/latest");
}

export async function fetchReadings(limit: number): Promise<ReadingsResponse> {
  const safeLimit = Math.max(1, Math.min(5000, Math.trunc(limit)));
  return await fetchJson<ReadingsResponse>(`/readings?limit=${safeLimit}`);
}

export async function fetchShapLatest(
  topK: number,
): Promise<ShapExplainResponse> {
  const safeTopK = Math.max(1, Math.min(25, Math.trunc(topK)));
  try {
    return await fetchJson<ShapExplainResponse>(
      `/shap/explain/latest?top_k=${safeTopK}`,
    );
  } catch (e) {
    if (e instanceof HttpError && (e.status === 422 || e.status === 503)) {
      return { status: "Not available yet" };
    }
    throw e;
  }
}

export async function fetchMlPerfLatest(): Promise<MlPerfResponse> {
  return await fetchJson<MlPerfResponse>("/ml/predict/latest");
}
