import { useEffect } from "react";
import { X, Clock, Tag, CheckCircle, AlertCircle, Zap, ChevronRight, AlertTriangle } from "lucide-react";
import type { StateObject } from "@/lib/api";

interface StateDrawerProps {
  state: StateObject | null;
  onClose: () => void;
}

function isFail(status: string): boolean {
  return status === "FAIL" || status === "FAILURE" || status === "ERROR";
}

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${ms}ms`;
}

function formatStateName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ status }: { status: string }) {
  if (isFail(status)) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-500/15 text-red-400 border border-red-500/25">
        <AlertCircle className="w-3 h-3" />
        {status}
      </span>
    );
  }
  if (status === "LATENCY_WARN") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-400/15 text-amber-400 border border-amber-400/25">
        <Zap className="w-3 h-3" />
        {status}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/25">
      <CheckCircle className="w-3 h-3" />
      {status}
    </span>
  );
}

function renderMetaValue(val: unknown, depth = 0): React.ReactNode {
  if (val === null || val === undefined) {
    return <span className="text-muted-foreground italic text-xs">null</span>;
  }
  if (typeof val === "boolean") {
    return <span className={`text-xs font-mono font-semibold ${val ? "text-emerald-400" : "text-red-400"}`}>{String(val)}</span>;
  }
  if (typeof val === "number") {
    return <span className="text-xs font-mono text-amber-400">{val}</span>;
  }
  if (typeof val === "string") {
    return <span className="text-xs font-mono text-blue-300 break-all">"{val}"</span>;
  }
  if (Array.isArray(val)) {
    if (val.length === 0) return <span className="text-xs text-muted-foreground font-mono">[]</span>;
    return (
      <div className="mt-1 space-y-1 pl-3 border-l border-border">
        {val.slice(0, 8).map((item, i) => (
          <div key={i} className="flex gap-1.5 text-xs">
            <span className="text-muted-foreground font-mono flex-shrink-0">[{i}]</span>
            {renderMetaValue(item, depth + 1)}
          </div>
        ))}
        {val.length > 8 && (
          <span className="text-xs text-muted-foreground">…{val.length - 8} more</span>
        )}
      </div>
    );
  }
  if (typeof val === "object" && depth < 3) {
    const entries = Object.entries(val as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-xs text-muted-foreground font-mono">{"{}"}</span>;
    return (
      <div className="mt-1 space-y-1.5 pl-3 border-l border-border">
        {entries.map(([k, v]) => (
          <div key={k}>
            <span className="text-xs text-violet-400 font-mono">{k}:</span>
            <div className="ml-1 inline-block">{renderMetaValue(v, depth + 1)}</div>
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-xs font-mono text-foreground">{String(val)}</span>;
}

interface ErrorDetail {
  error_type?: string;
  target?: string;
  message?: string;
  automation_framework?: string;
}

function ErrorDetailPanel({ detail }: { detail: ErrorDetail }) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/5 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-red-500/20 bg-red-500/10">
        <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
        <span className="text-[10px] uppercase tracking-widest text-red-400 font-semibold">Error Detail</span>
      </div>
      <div className="p-3 space-y-2.5">
        {detail.error_type && (
          <div>
            <div className="text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">Error Type</div>
            <div className="text-xs font-mono font-semibold text-red-300">{detail.error_type}</div>
          </div>
        )}
        {detail.target && (
          <div>
            <div className="text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">Target</div>
            <div className="text-xs font-mono text-foreground break-all">{detail.target}</div>
          </div>
        )}
        {detail.message && (
          <div>
            <div className="text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">Message</div>
            <div className="text-xs text-red-200 leading-relaxed break-words">{detail.message}</div>
          </div>
        )}
        {detail.automation_framework && (
          <div>
            <div className="text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">Automation Framework</div>
            <div className="text-xs font-mono text-amber-300">{detail.automation_framework}</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function StateDrawer({ state, onClose }: StateDrawerProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const isOpen = state !== null;

  const errorDetail = state && isFail(state.status)
    ? (state.metadata?.error_detail as ErrorDetail | undefined)
    : undefined;

  const metadataWithoutErrorDetail = state?.metadata
    ? Object.fromEntries(Object.entries(state.metadata).filter(([k]) => k !== "error_detail"))
    : {};

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[1px]"
          onClick={onClose}
        />
      )}

      <div
        className={`fixed right-0 top-0 h-full z-50 w-80 bg-sidebar border-l border-border shadow-2xl flex flex-col transition-transform duration-300 ease-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className={`w-1 h-5 rounded-full ${state && isFail(state.status) ? "bg-red-500" : "bg-primary"}`} />
            <span className="text-sm font-semibold text-foreground">State Details</span>
          </div>
          <button
            onClick={onClose}
            className="w-6 h-6 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {state && (
          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Tag className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">State Name</span>
              </div>
              <p className="text-base font-bold text-foreground">{formatStateName(state.state_name)}</p>
              <div className="mt-2">
                <StatusBadge status={state.status} />
              </div>
            </div>

            {errorDetail && <ErrorDetailPanel detail={errorDetail} />}

            <div className="bg-card border border-border rounded-xl p-3 space-y-3">
              <div className="flex items-center gap-1.5 mb-0.5">
                <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">Timing</span>
              </div>
              <div className="flex justify-between items-baseline">
                <span className="text-xs text-muted-foreground">Duration</span>
                <span className="text-xl font-bold text-foreground font-mono">{formatMs(state.duration_ms)}</span>
              </div>
              <div className="w-full bg-muted/40 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full ${
                    isFail(state.status)
                      ? "bg-red-500"
                      : state.status === "LATENCY_WARN" || state.duration_ms > 3000
                      ? "bg-amber-400"
                      : "bg-emerald-500"
                  }`}
                  style={{ width: `${Math.min(100, (state.duration_ms / 10000) * 100)}%` }}
                />
              </div>
              <div className="grid grid-cols-2 gap-2 pt-1">
                <div>
                  <div className="text-[9px] text-muted-foreground mb-0.5">START</div>
                  <div className="text-[10px] font-mono text-foreground">
                    {new Date(state.start_time).toLocaleTimeString()}
                    <span className="text-muted-foreground">.{String(new Date(state.start_time).getMilliseconds()).padStart(3, "0")}</span>
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-muted-foreground mb-0.5">END</div>
                  <div className="text-[10px] font-mono text-foreground">
                    {new Date(state.end_time).toLocaleTimeString()}
                    <span className="text-muted-foreground">.{String(new Date(state.end_time).getMilliseconds()).padStart(3, "0")}</span>
                  </div>
                </div>
              </div>
            </div>

            {Object.keys(metadataWithoutErrorDetail).length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">Metadata</span>
                </div>
                <div className="bg-card border border-border rounded-xl p-3 space-y-2.5">
                  {Object.entries(metadataWithoutErrorDetail).map(([key, val]) => (
                    <div key={key}>
                      <div className="text-[10px] font-semibold text-violet-400 font-mono mb-0.5">{key}</div>
                      <div className="pl-1">{renderMetaValue(val)}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
