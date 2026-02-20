import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "./components/Card";
import { Badge } from "./components/Badge";
import { Stat } from "./components/Stat";
import { usePolling } from "./hooks/usePolling";
import {
  type LatestReading,
  type MlPerfResponse,
  type Readiness,
  type ReadingsResponse,
  type ReadingsItem,
  type ShapExplainResponse,
  API_BASE,
  fetchLatest,
  fetchMlPerfLatest,
  fetchReadiness,
  fetchReadings,
  fetchShapLatest,
} from "./api";

const COLORS = {
  distance: "#3b82f6",
  rain: "#0ea5e9",
  risk: "#f43f5e",
  shapUp: "#f43f5e",
  shapDown: "#10b981",
} as const;

const tipStyle = {
  contentStyle: {
    background: "rgba(255,255,255,0.97)",
    border: "1px solid rgba(203,213,225,0.6)",
    borderRadius: "10px",
    boxShadow: "0 8px 32px rgba(0,0,0,0.09)",
    fontSize: "12px",
    padding: "8px 12px",
  },
  itemStyle: { color: "#334155" },
  labelStyle: { color: "#94a3b8", fontSize: "11px", marginBottom: "4px" },
} as const;

function formatTime(ts: string | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function riskLabel(risk: number | null | undefined): string {
  if (risk === 0) return "Safe";
  if (risk === 1) return "Warning";
  if (risk === 2) return "Critical";
  return "Unknown";
}

function riskBadgeVariant(
  risk: number | null | undefined,
): "neutral" | "warn" | "danger" {
  if (risk === 1) return "warn";
  if (risk === 2) return "danger";
  return "neutral";
}

function asPct(prob: number | null | undefined): string {
  if (prob === null || prob === undefined || Number.isNaN(prob)) return "—";
  return `${Math.round(prob * 100)}%`;
}

function safeJsonParse(value: string): unknown {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asFiniteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

function humanizeFeatureName(key: string): string {
  const map: Record<string, string> = {
    distance_cm: "Distance to water (cm)",
    rain_analog: "Rain sensor (0–1023)",
    float_status: "Float switch (0/1)",
    rise_rate_cm_per_min: "Rise rate (cm/min)",
    rain_trend_5min: "Rain trend (5 min mean)",
    distance_rolling_mean_3min: "Distance mean (3 min)",
    distance_rolling_std_3min: "Distance variability (3 min std)",
    cumulative_rain_30min: "Cumulative rain (30 min approx)",
    time_since_rain_start: "Minutes since rain began",
    emergency_flag: "Emergency flag",
    season_flag: "Rainy season flag",
    hour_of_day: "Hour of day",
    day_of_week: "Day of week",
    month: "Month",
  };
  return map[key] ?? key;
}

function formatFeatureValue(featureKey: string, value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (featureKey === "distance_cm") return `${value.toFixed(1)} cm`;
  if (featureKey === "rise_rate_cm_per_min")
    return `${value.toFixed(2)} cm/min`;
  if (featureKey === "time_since_rain_start") return `${value.toFixed(1)} min`;
  if (
    featureKey === "float_status" ||
    featureKey === "emergency_flag" ||
    featureKey === "season_flag"
  ) {
    return value >= 0.5 ? "1" : "0";
  }
  if (
    featureKey === "hour_of_day" ||
    featureKey === "day_of_week" ||
    featureKey === "month"
  ) {
    return String(Math.round(value));
  }
  // Default: keep compact.
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(3);
}

function formatSigned(value: number, digits: number): string {
  if (!Number.isFinite(value)) return "—";
  const fixed = value.toFixed(digits);
  return value > 0 ? `+${fixed}` : fixed;
}

function ShapTooltip({
  active,
  payload,
  targetLabel,
}: {
  active?: boolean;
  payload?: Array<{ payload?: Record<string, unknown> }>;
  targetLabel: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload ?? {};
  const featureKey = asString(row["featureKey"]) ?? "";
  const feature = asString(row["feature"]) ?? featureKey;
  const value = asFiniteNumber(row["value"]) ?? NaN;
  const shapVal = asFiniteNumber(row["shap"]) ?? NaN;
  const dir = asString(row["direction"]) ?? "";
  const directionText =
    dir === "decreases_risk"
      ? `Decreases ${targetLabel}`
      : `Increases ${targetLabel}`;

  return (
    <div style={tipStyle.contentStyle as CSSProperties}>
      <div style={{ ...tipStyle.labelStyle, marginBottom: 6 }}>{feature}</div>
      {featureKey && featureKey !== feature ? (
        <div style={{ color: "#94a3b8", fontSize: 11, marginBottom: 6 }}>
          {featureKey}
        </div>
      ) : null}
      <div style={{ display: "grid", gap: 4 }}>
        <div
          style={{ display: "flex", justifyContent: "space-between", gap: 12 }}
        >
          <span style={{ color: "#64748b", fontSize: 11 }}>Value</span>
          <span style={{ color: "#0f172a", fontSize: 11 }}>
            {formatFeatureValue(featureKey, value)}
          </span>
        </div>
        <div
          style={{ display: "flex", justifyContent: "space-between", gap: 12 }}
        >
          <span style={{ color: "#64748b", fontSize: 11 }}>SHAP</span>
          <span style={{ color: "#0f172a", fontSize: 11 }}>
            {formatSigned(shapVal, 3)}
          </span>
        </div>
        <div
          style={{ display: "flex", justifyContent: "space-between", gap: 12 }}
        >
          <span style={{ color: "#64748b", fontSize: 11 }}>Effect</span>
          <span style={{ color: "#0f172a", fontSize: 11 }}>
            {directionText}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const readiness = usePolling<Readiness>({
    key: "readiness",
    intervalMs: 10_000,
    load: fetchReadiness,
  });

  const latest = usePolling<LatestReading>({
    key: "latest",
    intervalMs: 3_000,
    load: fetchLatest,
  });

  const readings = usePolling<ReadingsResponse>({
    key: "readings",
    intervalMs: 3_000,
    load: () => fetchReadings(200),
  });

  const shap = usePolling<ShapExplainResponse>({
    key: "shap",
    intervalMs: 10_000,
    load: () => fetchShapLatest(6),
  });

  const chartData = useMemo(() => {
    const items: ReadingsItem[] = readings.data?.items ?? [];
    return items
      .map((r) => ({
        t: new Date(r.created_at).getTime(),
        distance_cm: r.distance_cm,
        rain_analog: r.rain_analog,
        risk_probability: r.risk_probability ?? null,
        predicted_risk: r.predicted_risk ?? null,
        float_status: r.float_status,
      }))
      .filter((r) => Number.isFinite(r.t));
  }, [readings.data]);

  const shapSorted = useMemo(() => {
    if (!shap.data || !("top_features" in shap.data)) return [];
    return [...shap.data.top_features]
      .sort((a, b) => Math.abs(b.shap) - Math.abs(a.shap))
      .map((f) => ({
        featureKey: f.feature,
        feature: humanizeFeatureName(f.feature),
        value: f.value,
        shap: f.shap,
        direction: f.direction,
      }));
  }, [shap.data]);

  const latestReading =
    latest.data && "distance_cm" in latest.data ? latest.data : null;

  const latestTime = latestReading ? formatTime(latestReading.created_at) : "—";
  const latestRisk = latestReading ? latestReading.predicted_risk : null;
  const latestProb = latestReading ? latestReading.risk_probability : null;

  const [mlPerf, setMlPerf] = useState<MlPerfResponse | null>(null);
  const [llmText, setLlmText] = useState<string>("");
  const [llmMeta, setLlmMeta] = useState<{
    id?: number;
    model?: string;
    created_at?: string;
  } | null>(null);
  const [llmDone, setLlmDone] = useState<{
    ok?: boolean;
    error?: string;
    total_ms?: number;
    first_token_ms?: number | null;
    eval_count?: number;
    prompt_eval_count?: number;
    eval_duration_ns?: number;
    token_events?: number;
    model?: string;
  } | null>(null);
  const [llmStreaming, setLlmStreaming] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const streamFlagsRef = useRef({
    expectedClose: false,
    receivedAnyEvent: false,
    receivedDone: false,
  });

  useEffect(() => {
    return () => {
      if (esRef.current) {
        streamFlagsRef.current.expectedClose = true;
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, []);

  const stopStream = () => {
    if (esRef.current) {
      streamFlagsRef.current.expectedClose = true;
      esRef.current.close();
      esRef.current = null;
    }
    setLlmStreaming(false);
  };

  const startStream = async () => {
    stopStream();
    setLlmError(null);
    setLlmText("");
    setLlmMeta(null);
    setLlmDone(null);
    setLlmStreaming(true);
    streamFlagsRef.current = {
      expectedClose: false,
      receivedAnyEvent: false,
      receivedDone: false,
    };

    try {
      const perf = await fetchMlPerfLatest();
      setMlPerf(perf);
    } catch {
      setMlPerf(null);
    }

    const es = new EventSource(`${API_BASE}/llm/explain/stream/latest`);
    esRef.current = es;

    es.addEventListener("meta", (evt) => {
      streamFlagsRef.current.receivedAnyEvent = true;
      try {
        const parsed = safeJsonParse((evt as MessageEvent).data);
        if (!isRecord(parsed)) return;
        setLlmMeta({
          id: asFiniteNumber(parsed["id"]),
          model: asString(parsed["model"]),
          created_at: asString(parsed["created_at"]),
        });
      } catch {
        // ignore
      }
    });

    es.addEventListener("ml_perf", (evt) => {
      streamFlagsRef.current.receivedAnyEvent = true;
      try {
        const data = JSON.parse((evt as MessageEvent).data) as MlPerfResponse;
        setMlPerf(data);
      } catch {
        // ignore
      }
    });

    es.addEventListener("token", (evt) => {
      streamFlagsRef.current.receivedAnyEvent = true;
      try {
        const data = JSON.parse((evt as MessageEvent).data) as {
          text?: string;
        };
        if (data?.text) setLlmText((t) => t + data.text);
      } catch {
        // ignore
      }
    });

    es.addEventListener("done", (evt) => {
      streamFlagsRef.current.receivedAnyEvent = true;
      streamFlagsRef.current.receivedDone = true;
      try {
        const parsed = safeJsonParse((evt as MessageEvent).data);
        if (!isRecord(parsed)) {
          setLlmDone({ ok: false, error: "invalid_done_payload" });
          stopStream();
          return;
        }
        const okRaw = parsed["ok"];
        const ok = typeof okRaw === "boolean" ? okRaw : undefined;
        const doneObj = {
          ok,
          error: asString(parsed["error"]),
          total_ms: asFiniteNumber(parsed["total_ms"]),
          first_token_ms: asFiniteNumber(parsed["first_token_ms"]),
          eval_count: asFiniteNumber(parsed["eval_count"]),
          prompt_eval_count: asFiniteNumber(parsed["prompt_eval_count"]),
          eval_duration_ns: asFiniteNumber(parsed["eval_duration_ns"]),
          token_events: asFiniteNumber(parsed["token_events"]),
          model: asString(parsed["model"]),
        };
        setLlmDone(doneObj);
        // Surface server-side errors (e.g. Ollama unavailable) as the UI error.
        if (ok === false && doneObj.error) {
          setLlmError(`LLM error: ${doneObj.error}`);
        }
      } catch {
        setLlmDone({ ok: false, error: "invalid_done_payload" });
      }
      stopStream();
    });

    es.onerror = (evt) => {
      // Some browsers fire an error event when we intentionally close.
      if (
        streamFlagsRef.current.expectedClose ||
        streamFlagsRef.current.receivedDone
      ) {
        return;
      }
      const target = evt.target as EventSource | null;
      const state = target ? target.readyState : -1;
      // readyState 0 = CONNECTING, 1 = OPEN, 2 = CLOSED
      // If we never received any events and get an error the backend is likely
      // unreachable or returned a non-2xx status.
      const gotAny = streamFlagsRef.current.receivedAnyEvent;
      const msg =
        !gotAny && (state === 0 || state === 2)
          ? "Cannot connect to backend. Make sure uvicorn is running on localhost:8000."
          : "Stream closed unexpectedly. Check that Ollama is running and the model is pulled (see System status).";
      setLlmError(msg);
      stopStream();
    };
  };

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-slate-200/60 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-500 shadow-sm shadow-blue-500/40">
              <svg
                className="h-4 w-4 text-white"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5S10.62 6.5 12 6.5s2.5 1.12 2.5 2.5S13.38 11.5 12 11.5z" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-slate-900">
                Flood Detection
              </h1>
              <p className="text-[11px] text-slate-400">
                Realtime sensor dashboard
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span
              className={`h-2 w-2 rounded-full ${
                latest.isLoading
                  ? "bg-amber-400"
                  : "animate-pulse bg-emerald-400"
              }`}
            />
            {latest.isLoading ? "Connecting…" : `Updated ${latestTime}`}
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-4 px-5 py-5 md:grid-cols-12">
        <section className="md:col-span-5" aria-label="System status">
          <Card
            title="System status"
            subtitle="Backend readiness checks for database, serial input, and optional LLM."
            right={
              readiness.isLoading ? (
                <Badge variant="neutral">Checking…</Badge>
              ) : readiness.error ? (
                <Badge variant="danger">Not ready</Badge>
              ) : (
                <Badge variant="ok">Ready</Badge>
              )
            }
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Stat
                label="Database"
                value={readiness.data?.db?.ok ? "OK" : "Not OK"}
                tone={readiness.data?.db?.ok ? "good" : "bad"}
                detail={readiness.data?.db?.error || "Connectivity check"}
              />
              <Stat
                label="Serial"
                value={
                  readiness.data?.serial?.ok ? "Connected" : "Disconnected"
                }
                tone={readiness.data?.serial?.ok ? "good" : "warn"}
                detail={
                  readiness.data?.serial?.port
                    ? `Port: ${readiness.data.serial.port}`
                    : readiness.data?.serial?.error || "USB/COM input"
                }
              />
              <Stat
                label="LLM"
                value={
                  readiness.data?.llm
                    ? readiness.data.llm.ok
                      ? "Available"
                      : "Unavailable"
                    : "Not checked"
                }
                tone={
                  readiness.data?.llm
                    ? readiness.data.llm.ok
                      ? "good"
                      : "warn"
                    : "neutral"
                }
                detail={
                  readiness.data?.llm?.model
                    ? `Model: ${readiness.data.llm.model}`
                    : readiness.data?.llm?.error || "Explainer optional"
                }
              />
              <Stat
                label="Polling"
                value={latest.isLoading ? "Starting…" : "Live"}
                tone={latest.isLoading ? "neutral" : "good"}
                detail="Updates every ~3 seconds"
              />
            </div>

            {readiness.error ? (
              <p className="mt-4 text-sm text-slate-600">
                Backend returned not-ready. You can still view UI, but charts
                may be empty.
              </p>
            ) : null}
          </Card>
        </section>

        <section className="md:col-span-7" aria-label="Current risk">
          <Card
            title="Current reading"
            subtitle="Most recent sensor reading stored in the database."
            right={
              <Badge variant={riskBadgeVariant(latestRisk)}>
                {riskLabel(latestRisk)}
              </Badge>
            }
          >
            {latestReading ? (
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <div className="text-xs font-medium text-slate-500">
                    Water distance
                  </div>
                  <div className="mt-1 text-2xl font-semibold text-slate-900">
                    {latestReading.distance_cm.toFixed(1)}
                    <span className="ml-1 text-sm font-medium text-slate-600">
                      cm
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Lower distance can imply higher water level.
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500">
                    Rain sensor
                  </div>
                  <div className="mt-1 text-2xl font-semibold text-slate-900">
                    {latestReading.rain_analog}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Raw ADC value (0–1023).
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500">
                    Float switch
                  </div>
                  <div className="mt-1 text-2xl font-semibold text-slate-900">
                    {latestReading.float_status === 1 ? "Triggered" : "Normal"}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Emergency override when triggered.
                  </div>
                </div>
              </div>
            ) : latest.isLoading ? (
              <p className="text-sm text-slate-600">Loading latest reading…</p>
            ) : (
              <p className="text-sm text-slate-600">
                No readings yet. Start the backend serial listener to populate
                data.
              </p>
            )}

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <Stat
                label="Predicted risk"
                value={riskLabel(latestRisk)}
                tone={
                  latestRisk === 2 ? "bad" : latestRisk === 1 ? "warn" : "good"
                }
                detail="Model output class"
              />
              <Stat
                label="Risk probability"
                value={asPct(latestProb)}
                tone={
                  latestProb !== null &&
                  latestProb !== undefined &&
                  latestProb >= 0.8
                    ? "warn"
                    : "neutral"
                }
                detail="Probability of predicted class"
              />
            </div>

            {latestReading?.explanation ? (
              <div className="mt-5 rounded-xl bg-slate-50/90 p-4 ring-1 ring-slate-200/80">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                  Stored Explanation
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                  {latestReading.explanation}
                </p>
              </div>
            ) : (
              <p className="mt-5 text-sm text-slate-600">
                No explanation stored for the latest reading.
              </p>
            )}
          </Card>
        </section>

        <section className="md:col-span-12" aria-label="Live LLM explanation">
          <Card
            title="Live explanation (LLM)"
            subtitle="Generate a real-time explanation for the latest reading. Shows token streaming and engine performance."
            right={
              <div className="flex items-center gap-2">
                {llmStreaming ? (
                  <Badge variant="warn">Streaming</Badge>
                ) : llmDone?.ok ? (
                  <Badge variant="ok">Done</Badge>
                ) : llmError ? (
                  <Badge variant="danger">Error</Badge>
                ) : (
                  <Badge variant="neutral">Idle</Badge>
                )}
              </div>
            }
          >
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void startStream()}
                disabled={llmStreaming}
                className="inline-flex items-center justify-center rounded-xl bg-blue-500 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-blue-500/30 transition hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Generate live explanation
              </button>
              <button
                type="button"
                onClick={stopStream}
                disabled={!llmStreaming}
                className="inline-flex items-center justify-center rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Stop
              </button>
              <div className="ml-auto text-sm text-slate-600">
                {llmMeta?.model ? `Model: ${llmMeta.model}` : ""}
              </div>
            </div>

            {llmError ? (
              <div className="mt-4 rounded-xl bg-rose-50 px-4 py-3 ring-1 ring-rose-200">
                <p className="text-sm font-medium text-rose-700">{llmError}</p>
                <ul className="mt-2 space-y-0.5 text-xs text-rose-600">
                  <li>
                    · Backend:{" "}
                    <code className="font-mono">
                      uvicorn backend.main:app --reload
                    </code>
                  </li>
                  <li>
                    · Ollama: <code className="font-mono">ollama serve</code>{" "}
                    and{" "}
                    <code className="font-mono">
                      ollama pull {llmMeta?.model ?? "phi3:mini"}
                    </code>
                  </li>
                  <li>
                    · Check the <strong>System status</strong> card — LLM row
                    shows if Ollama is reachable.
                  </li>
                </ul>
              </div>
            ) : null}

            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <Stat
                label="ML inference"
                value={
                  mlPerf &&
                  "inference_ms" in mlPerf &&
                  mlPerf.inference_ms !== undefined
                    ? `${mlPerf.inference_ms} ms`
                    : "—"
                }
                tone={
                  mlPerf && "ok" in mlPerf && mlPerf.ok ? "good" : "neutral"
                }
                detail={
                  mlPerf && "predicted_risk" in mlPerf
                    ? `risk=${mlPerf.predicted_risk ?? "—"}, prob=${
                        mlPerf.risk_probability ?? "—"
                      }`
                    : "Timed on latest sample"
                }
              />
              <Stat
                label="LLM total"
                value={
                  llmDone?.total_ms !== undefined
                    ? `${llmDone.total_ms} ms`
                    : "—"
                }
                tone={llmDone?.ok ? "good" : llmError ? "bad" : "neutral"}
                detail={
                  llmDone?.first_token_ms !== undefined &&
                  llmDone?.first_token_ms !== null
                    ? `first token: ${llmDone.first_token_ms} ms`
                    : "first token: —"
                }
              />
              <Stat
                label="LLM throughput"
                value={
                  llmDone?.eval_count && llmDone?.eval_duration_ns
                    ? `${Math.max(
                        0,
                        Math.round(
                          llmDone.eval_count /
                            (Number(llmDone.eval_duration_ns) / 1_000_000_000),
                        ),
                      )} tok/s`
                    : "—"
                }
                tone="neutral"
                detail={
                  llmDone?.token_events !== undefined
                    ? `events: ${llmDone.token_events}`
                    : "events: —"
                }
              />
            </div>

            <div className="mt-5 rounded-xl bg-slate-50/90 p-4 ring-1 ring-slate-200/80">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                Live output
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                {llmText ||
                  (llmStreaming ? "Generating…" : "Press generate to start.")}
              </p>
            </div>
          </Card>
        </section>

        <section className="md:col-span-12" aria-label="Trends">
          <Card
            title="Recent trends"
            subtitle="Last 200 readings (time series). Use these charts to spot rapid changes and sustained conditions."
          >
            {readings.isLoading ? (
              <p className="text-sm text-slate-600">Loading readings…</p>
            ) : readings.error ? (
              <p className="text-sm text-slate-600">
                Could not load readings. Is the backend running on
                localhost:8000?
              </p>
            ) : chartData.length < 2 ? (
              <p className="text-sm text-slate-600">
                Not enough data yet to plot trends.
              </p>
            ) : (
              <div className="grid gap-5 lg:grid-cols-3">
                <div className="h-72 rounded-2xl bg-white/90 p-4 ring-1 ring-slate-200/60 shadow-sm">
                  <div className="mb-3 flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-blue-500 shadow-sm shadow-blue-500/50" />
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                      Water distance (cm)
                    </span>
                  </div>
                  <div className="h-[calc(100%-2.25rem)]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={chartData}
                        margin={{ left: 4, right: 12, top: 4, bottom: 4 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          strokeOpacity={0.1}
                          vertical={false}
                        />
                        <XAxis
                          dataKey="t"
                          type="number"
                          domain={["dataMin", "dataMax"]}
                          tickFormatter={(v) =>
                            new Date(v).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          }
                          tick={{ fontSize: 10, fill: "#94a3b8" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          width={34}
                          tick={{ fontSize: 10, fill: "#94a3b8" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          {...tipStyle}
                          labelFormatter={(v) =>
                            new Date(Number(v)).toLocaleString()
                          }
                          formatter={(val) => [
                            `${Number(val).toFixed(1)} cm`,
                            "Distance",
                          ]}
                        />
                        <Line
                          type="monotone"
                          dataKey="distance_cm"
                          strokeWidth={2}
                          stroke={COLORS.distance}
                          dot={false}
                          activeDot={{
                            r: 4,
                            fill: COLORS.distance,
                            strokeWidth: 0,
                          }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="h-72 rounded-2xl bg-white/90 p-4 ring-1 ring-slate-200/60 shadow-sm">
                  <div className="mb-3 flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-sky-400 shadow-sm shadow-sky-400/50" />
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                      Rain sensor (0–1023)
                    </span>
                  </div>
                  <div className="h-[calc(100%-2.25rem)]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={chartData}
                        margin={{ left: 4, right: 12, top: 4, bottom: 4 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          strokeOpacity={0.1}
                          vertical={false}
                        />
                        <XAxis
                          dataKey="t"
                          type="number"
                          domain={["dataMin", "dataMax"]}
                          tickFormatter={(v) =>
                            new Date(v).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          }
                          tick={{ fontSize: 10, fill: "#94a3b8" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          width={34}
                          tick={{ fontSize: 10, fill: "#94a3b8" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          {...tipStyle}
                          labelFormatter={(v) =>
                            new Date(Number(v)).toLocaleString()
                          }
                          formatter={(val) => [`${val}`, "Rain analog"]}
                        />
                        <Area
                          type="monotone"
                          dataKey="rain_analog"
                          stroke={COLORS.rain}
                          fill={COLORS.rain}
                          fillOpacity={0.12}
                          strokeWidth={2}
                          activeDot={{
                            r: 4,
                            fill: COLORS.rain,
                            strokeWidth: 0,
                          }}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="h-72 rounded-2xl bg-white/90 p-4 ring-1 ring-slate-200/60 shadow-sm">
                  <div className="mb-3 flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-500 shadow-sm shadow-rose-500/50" />
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                      Risk probability
                    </span>
                  </div>
                  <div className="h-[calc(100%-2.25rem)]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={chartData}
                        margin={{ left: 4, right: 12, top: 4, bottom: 4 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          strokeOpacity={0.1}
                          vertical={false}
                        />
                        <XAxis
                          dataKey="t"
                          type="number"
                          domain={["dataMin", "dataMax"]}
                          tickFormatter={(v) =>
                            new Date(v).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          }
                          tick={{ fontSize: 10, fill: "#94a3b8" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          width={34}
                          domain={[0, 1]}
                          tickFormatter={(v) =>
                            `${Math.round(Number(v) * 100)}%`
                          }
                          tick={{ fontSize: 10, fill: "#94a3b8" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          {...tipStyle}
                          labelFormatter={(v) =>
                            new Date(Number(v)).toLocaleString()
                          }
                          formatter={(val) => [
                            `${Math.round(Number(val) * 100)}%`,
                            "Probability",
                          ]}
                        />
                        <Line
                          type="monotone"
                          dataKey="risk_probability"
                          strokeWidth={2}
                          stroke={COLORS.risk}
                          dot={false}
                          connectNulls
                          activeDot={{
                            r: 4,
                            fill: COLORS.risk,
                            strokeWidth: 0,
                          }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </section>

        <section className="md:col-span-12" aria-label="Explainability">
          <Card
            title="Model explainability (SHAP)"
            subtitle="Top engineered features that most increase/decrease the risk-class probability."
          >
            {shap.isLoading ? (
              <p className="text-sm text-slate-600">
                Loading SHAP explanation…
              </p>
            ) : shap.error ? (
              <p className="text-sm text-slate-600">
                SHAP explanation not available yet.
              </p>
            ) : shap.data && "top_features" in shap.data ? (
              <div className="grid gap-4 md:grid-cols-12">
                <div className="md:col-span-4">
                  <p className="text-xs text-slate-500">
                    SHAP values here explain the probability of{" "}
                    <span className="font-medium text-slate-700">
                      {shap.data.target_label ?? "Risk"}
                    </span>
                    .
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-1">
                    <Stat
                      label="Predicted class"
                      value={shap.data.predicted_label}
                      tone={
                        shap.data.predicted_class === 2
                          ? "bad"
                          : shap.data.predicted_class === 1
                            ? "warn"
                            : "good"
                      }
                      detail="Model output"
                    />
                    <Stat
                      label="Predicted prob"
                      value={asPct(shap.data.probability)}
                      tone="neutral"
                      detail="Of predicted class"
                    />
                    <Stat
                      label="Explained prob"
                      value={asPct(
                        shap.data.target_probability ?? shap.data.probability,
                      )}
                      tone="neutral"
                      detail={shap.data.target_label ?? "Risk"}
                    />
                  </div>
                  <div className="mt-4 space-y-1.5">
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <span className="h-2.5 w-2.5 rounded-sm bg-rose-500/80" />
                      <span>Increases {shap.data.target_label ?? "risk"}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500/80" />
                      <span>Decreases {shap.data.target_label ?? "risk"}</span>
                    </div>
                  </div>
                </div>

                <div className="h-80 md:col-span-8">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={shapSorted}
                      layout="vertical"
                      margin={{ left: 8, right: 24, top: 8, bottom: 8 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        strokeOpacity={0.1}
                        horizontal={false}
                      />
                      <ReferenceLine x={0} stroke="#cbd5e1" strokeWidth={1.5} />
                      <XAxis
                        type="number"
                        tickFormatter={(v) => Number(v).toFixed(2)}
                        tick={{ fontSize: 10, fill: "#94a3b8" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="feature"
                        width={200}
                        tick={{ fontSize: 11, fill: "#475569" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        content={
                          <ShapTooltip
                            targetLabel={shap.data.target_label ?? "risk"}
                          />
                        }
                      />
                      <Bar dataKey="shap" radius={[0, 4, 4, 0]}>
                        {shapSorted.map((entry, i) => (
                          <Cell
                            key={i}
                            fill={
                              entry.direction === "decreases_risk"
                                ? COLORS.shapDown
                                : COLORS.shapUp
                            }
                            fillOpacity={0.85}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-600">No SHAP data yet.</p>
            )}
          </Card>
        </section>
      </main>

      <footer className="mx-auto max-w-7xl px-5 pb-8">
        <p className="text-xs text-slate-400">
          Read-only dashboard · values reflect the latest records stored by the
          backend.
        </p>
      </footer>
    </div>
  );
}
