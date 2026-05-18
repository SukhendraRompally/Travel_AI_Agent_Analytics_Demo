// VITE_BACKEND_URL must be set in Vercel env vars to your Render backend URL.
// For local dev, create frontend/.env.local with VITE_BACKEND_URL=http://localhost:8002
const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "";

export interface StateObject {
  state_name: string;
  start_time: string;
  end_time: string;
  duration_ms: number;
  status: "SUCCESS" | "LATENCY_WARN" | "FAILURE" | string;
  metadata: Record<string, unknown>;
}

export interface TraceSummary {
  total_duration_ms: number;
  state_count: number;
  latency_warnings: number;
  failures: number;
  llm_reasoning_ms: number;
  tool_call_ms: number;
  total_latency_s?: number;
  success_rate_pct?: number;
  experience_score?: number;
  revenue_at_risk_usd?: number;
  reasoning_ratio_pct?: number;
}

export interface TraceResponse {
  session_id: string;
  states: StateObject[];
  summary: TraceSummary;
}

export interface ChatResponse {
  response: string;
  session_id: string;
}

export interface ChaosResponse {
  chaos_mode: boolean;
  message: string;
}

export interface HealthResponse {
  status: string;
  timestamp?: string;
  chaos_mode?: boolean;
  azure_configured?: boolean;
}

export async function postChat(message: string, session_id: string): Promise<ChatResponse> {
  const res = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}

export async function getTrace(session_id: string): Promise<TraceResponse> {
  const res = await fetch(`${BACKEND_URL}/trace/${session_id}`);
  if (!res.ok) throw new Error(`Trace failed: ${res.status}`);
  return res.json();
}

export async function postChaosToggle(): Promise<ChaosResponse> {
  const res = await fetch(`${BACKEND_URL}/chaos/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`Chaos toggle failed: ${res.status}`);
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BACKEND_URL}/health`);
  if (!res.ok) throw new Error(`Health failed: ${res.status}`);
  return res.json();
}
