import { useState } from "react";
import {
  Activity, Clock, DollarSign, Brain,
  AlertCircle, CheckCircle, Zap, Loader2, Gauge, TrendingUp,
} from "lucide-react";
import type { StateObject, TraceSummary } from "@/lib/api";
import StateDrawer from "@/components/StateDrawer";

interface TracePanelProps {
  states: StateObject[];
  summary: TraceSummary | null;
  isProcessing: boolean;
  chaosMode: boolean;
}

function isFail(status: string): boolean {
  return status === "FAIL" || status === "FAILURE" || status === "ERROR";
}

function getBarColor(status: string, duration_ms: number): string {
  if (isFail(status)) return "bg-red-500";
  if (status === "LATENCY_WARN" || duration_ms > 3000) return "bg-amber-400";
  return "bg-emerald-500";
}

function getBarBorder(status: string, duration_ms: number): string {
  if (isFail(status)) return "border-red-400";
  if (status === "LATENCY_WARN" || duration_ms > 3000) return "border-amber-300";
  return "border-emerald-400";
}

function getStatusIcon(status: string) {
  if (isFail(status))
    return <AlertCircle className="w-3 h-3 text-red-400 flex-shrink-0" />;
  if (status === "LATENCY_WARN")
    return <Zap className="w-3 h-3 text-amber-400 flex-shrink-0" />;
  return <CheckCircle className="w-3 h-3 text-emerald-400 flex-shrink-0" />;
}

function formatStateName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function TracePanel({ states, summary, isProcessing, chaosMode }: TracePanelProps) {
  const [selectedState, setSelectedState] = useState<StateObject | null>(null);

  const handleBarClick = (state: StateObject, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedState(state);
  };

  const maxDuration = states.length > 0 ? Math.max(...states.map((s) => s.duration_ms)) : 1;

  const totalLatency = summary?.total_latency_s != null
    ? `${summary.total_latency_s.toFixed(1)}s`
    : null;

  const successRate = summary?.success_rate_pct != null
    ? `${Math.round(summary.success_rate_pct)}%`
    : null;

  const experienceScore = summary?.experience_score != null
    ? summary.experience_score
    : null;

  const revenueAtRisk = summary?.revenue_at_risk_usd != null
    ? `$${summary.revenue_at_risk_usd.toLocaleString()}`
    : null;

  const reasoningRatio = summary?.reasoning_ratio_pct != null
    ? `${summary.reasoning_ratio_pct.toFixed(1)}%`
    : null;

  const expScoreColor =
    experienceScore === null ? "text-foreground"
    : experienceScore >= 80 ? "text-emerald-400"
    : experienceScore >= 50 ? "text-amber-400"
    : "text-red-400";

  const expScoreBg =
    experienceScore === null ? "bg-card border-border"
    : experienceScore >= 80 ? "bg-card border-border"
    : experienceScore >= 50 ? "border-amber-400/30 bg-amber-400/5"
    : "border-red-500/30 bg-red-500/5";

  return (
    <div className="flex flex-col h-full bg-background">
      <div className="px-5 py-3.5 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">Agent Experience Trace</h2>
          {chaosMode && (
            <span className="ml-auto flex items-center gap-1 text-[10px] font-medium bg-red-500/15 text-red-400 border border-red-500/20 px-2 py-0.5 rounded-full">
              <AlertCircle className="w-2.5 h-2.5" />
              CHAOS MODE
            </span>
          )}
        </div>
      </div>

      <div className="px-4 py-3 border-b border-border flex-shrink-0 space-y-2.5">
        <div className="grid grid-cols-2 gap-2.5">
          {/* Card 1 — Total Latency */}
          <div className="bg-card border border-border rounded-lg p-2.5">
            <div className="flex items-center gap-1.5 mb-1">
              <Clock className="w-3 h-3 text-muted-foreground" />
              <span className="text-[9px] font-medium text-muted-foreground uppercase tracking-wide">Total Latency</span>
            </div>
            <div className="text-base font-bold text-foreground font-mono">
              {totalLatency ?? "—"}
            </div>
            <div className="text-[9px] text-muted-foreground mt-0.5">end-to-end response time</div>
          </div>

          {/* Card 2 — Success Rate */}
          <div className="bg-card border border-border rounded-lg p-2.5">
            <div className="flex items-center gap-1.5 mb-1">
              <TrendingUp className="w-3 h-3 text-muted-foreground" />
              <span className="text-[9px] font-medium text-muted-foreground uppercase tracking-wide">Success Rate</span>
            </div>
            <div className={`text-base font-bold font-mono ${
              successRate === null ? "text-foreground"
              : summary!.success_rate_pct! >= 90 ? "text-emerald-400"
              : summary!.success_rate_pct! >= 70 ? "text-amber-400"
              : "text-red-400"
            }`}>
              {successRate ?? "—"}
            </div>
            <div className="text-[9px] text-muted-foreground mt-0.5">
              {summary ? `${summary.latency_warnings} warn · ${summary.failures} fail` : "awaiting trace"}
            </div>
          </div>

          {/* Card 3 — Reasoning Ratio */}
          <div className="bg-card border border-border rounded-lg p-2.5">
            <div className="flex items-center gap-1.5 mb-1">
              <Brain className="w-3 h-3 text-muted-foreground" />
              <span className="text-[9px] font-medium text-muted-foreground uppercase tracking-wide">Reasoning Ratio</span>
            </div>
            <div className={`text-base font-bold font-mono ${
              reasoningRatio === null ? "text-foreground"
              : summary!.reasoning_ratio_pct! > 60 ? "text-amber-400"
              : "text-emerald-400"
            }`}>
              {reasoningRatio ?? "—"}
            </div>
            <div className="text-[9px] text-muted-foreground mt-0.5">
              {reasoningRatio !== null
                ? summary!.reasoning_ratio_pct! > 60 ? "LLM-heavy — minimal tool use" : "Balanced LLM ÷ tool split"
                : "LLM time ÷ total time"}
            </div>
          </div>

          {/* Card 4 — Revenue at Risk */}
          <div className="bg-card border border-border rounded-lg p-2.5">
            <div className="flex items-center gap-1.5 mb-1">
              <DollarSign className="w-3 h-3 text-muted-foreground" />
              <span className="text-[9px] font-medium text-muted-foreground uppercase tracking-wide">Revenue at Risk</span>
            </div>
            <div className={`text-base font-bold font-mono ${
              revenueAtRisk === null || revenueAtRisk === "$0" ? "text-foreground" : "text-red-400"
            }`}>
              {revenueAtRisk ?? "—"}
            </div>
            <div className="text-[9px] text-muted-foreground mt-0.5">est. conversion impact</div>
          </div>
        </div>

        {/* Card 5 — Experience Score (full width) */}
        <div className={`border rounded-lg p-2.5 transition-all ${expScoreBg}`}>
          <div className="flex items-center gap-1.5 mb-1">
            <Gauge className="w-3 h-3 text-muted-foreground" />
            <span className="text-[9px] font-medium text-muted-foreground uppercase tracking-wide">Experience Score</span>
          </div>
          <div className="flex items-end gap-3">
            <div className={`text-base font-bold font-mono ${expScoreColor}`}>
              {experienceScore !== null ? `${experienceScore} / 100` : "—"}
            </div>
            {experienceScore !== null && (
              <div className="flex-1 mb-0.5">
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      experienceScore >= 80 ? "bg-emerald-500"
                      : experienceScore >= 50 ? "bg-amber-400"
                      : "bg-red-500"
                    }`}
                    style={{ width: `${experienceScore}%` }}
                  />
                </div>
              </div>
            )}
          </div>
          <div className="text-[9px] text-muted-foreground mt-0.5">
            {experienceScore !== null
              ? experienceScore >= 80 ? "Excellent — low friction"
              : experienceScore >= 50 ? "Degraded — user impact likely"
              : "Critical — intervention needed"
              : "composite KPI"}
          </div>
        </div>
      </div>

      <div className="px-4 py-2.5 flex-shrink-0 border-b border-border">
        <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-sm bg-emerald-500 inline-block" />
            Success
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-sm bg-amber-400 inline-block" />
            Latency &gt;3s
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-sm bg-red-500 inline-block" />
            Failure
          </div>
          <span className="ml-auto">Click bar for details</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {states.length === 0 && !isProcessing && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <div className="w-12 h-12 rounded-xl border border-border bg-card flex items-center justify-center">
              <Activity className="w-5 h-5 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">No trace data yet</p>
              <p className="text-xs text-muted-foreground/60 mt-0.5">Send a message to see the AI agent trace</p>
            </div>
          </div>
        )}

        {states.length === 0 && isProcessing && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <div className="w-12 h-12 rounded-xl border border-border bg-card flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-primary animate-spin" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">Collecting trace data…</p>
              <p className="text-xs text-muted-foreground mt-0.5">The AI agent is processing your request</p>
            </div>
          </div>
        )}

        {states.length > 0 && (
          <div className="space-y-2.5">
            {states.map((state, idx) => {
              const barWidth = Math.max(4, (state.duration_ms / maxDuration) * 100);
              const isSelected =
                selectedState?.state_name === state.state_name &&
                selectedState?.start_time === state.start_time;
              return (
                <div key={idx} className="flex items-center gap-3 slide-in-up">
                  <div className="w-32 flex-shrink-0">
                    <div className="flex items-center gap-1.5">
                      {getStatusIcon(state.status)}
                      <span className="text-xs text-foreground font-medium truncate" title={formatStateName(state.state_name)}>
                        {formatStateName(state.state_name)}
                      </span>
                    </div>
                  </div>
                  <div className="flex-1 relative h-6 bg-muted/30 rounded-md overflow-hidden">
                    <button
                      onClick={(e) => handleBarClick(state, e)}
                      className={`absolute left-0 top-0 h-full rounded-md border ${getBarColor(state.status, state.duration_ms)} ${getBarBorder(state.status, state.duration_ms)} transition-all cursor-pointer flex items-center px-2 ${
                        isSelected ? "opacity-100 ring-1 ring-white/30" : "opacity-85 hover:opacity-100"
                      }`}
                      style={{ width: `${barWidth}%`, minWidth: "2rem" }}
                      title={`Click to inspect — ${state.duration_ms}ms`}
                    >
                      <span className="text-[10px] font-mono text-white/90 font-semibold whitespace-nowrap">
                        {state.duration_ms >= 1000 ? `${(state.duration_ms / 1000).toFixed(1)}s` : `${state.duration_ms}ms`}
                      </span>
                    </button>
                  </div>
                  <div className="w-12 flex-shrink-0 text-right">
                    <span className="text-[10px] font-mono text-muted-foreground">
                      {state.duration_ms >= 1000 ? `${(state.duration_ms / 1000).toFixed(1)}s` : `${state.duration_ms}ms`}
                    </span>
                  </div>
                </div>
              );
            })}

            {isProcessing && (
              <div className="flex items-center gap-3">
                <div className="w-32 flex-shrink-0">
                  <div className="flex items-center gap-1.5">
                    <Loader2 className="w-3 h-3 text-blue-400 animate-spin flex-shrink-0" />
                    <span className="text-xs text-muted-foreground font-medium">Processing…</span>
                  </div>
                </div>
                <div className="flex-1 h-6 bg-muted/30 rounded-md overflow-hidden">
                  <div className="h-full w-full bg-gradient-to-r from-blue-500/40 via-blue-500/20 to-transparent animate-pulse rounded-md" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <StateDrawer state={selectedState} onClose={() => setSelectedState(null)} />
    </div>
  );
}
