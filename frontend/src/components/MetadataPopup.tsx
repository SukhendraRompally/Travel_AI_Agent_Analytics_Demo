import { X } from "lucide-react";
import type { StateObject } from "@/lib/api";

interface MetadataPopupProps {
  state: StateObject;
  position: { x: number; y: number };
  onClose: () => void;
}

function formatStateName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${ms}ms`;
}

function renderValue(val: unknown, indent = 0): JSX.Element {
  if (val === null || val === undefined) {
    return <span className="text-muted-foreground italic">null</span>;
  }
  if (typeof val === "boolean") {
    return <span className={val ? "text-emerald-400" : "text-red-400"}>{String(val)}</span>;
  }
  if (typeof val === "number") {
    return <span className="text-amber-400 font-mono">{val}</span>;
  }
  if (typeof val === "string") {
    return <span className="text-blue-300 font-mono">"{val}"</span>;
  }
  if (Array.isArray(val)) {
    return (
      <span className="text-muted-foreground">
        [{val.length} items]
      </span>
    );
  }
  if (typeof val === "object") {
    return (
      <div className="ml-2 space-y-0.5">
        {Object.entries(val as Record<string, unknown>).map(([k, v]) => (
          <div key={k} className="flex gap-1.5 text-[10px]">
            <span className="text-violet-400 font-mono flex-shrink-0">{k}:</span>
            <span>{renderValue(v, indent + 1)}</span>
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-foreground font-mono">{String(val)}</span>;
}

export default function MetadataPopup({ state, position, onClose }: MetadataPopupProps) {
  const statusColor =
    state.status === "FAILURE" || state.status === "ERROR"
      ? "text-red-400 bg-red-500/10 border-red-500/20"
      : state.status === "LATENCY_WARN"
      ? "text-amber-400 bg-amber-400/10 border-amber-400/20"
      : "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";

  const startTime = new Date(state.start_time);
  const endTime = new Date(state.end_time);

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div
        className="fixed z-50 w-72 bg-card border border-border rounded-xl shadow-2xl slide-in-up overflow-hidden"
        style={{
          left: Math.min(position.x, window.innerWidth - 300),
          top: Math.min(position.y, window.innerHeight - 320),
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-sidebar">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-4 rounded-sm bg-primary" />
            <span className="text-xs font-semibold text-foreground">{formatStateName(state.state_name)}</span>
          </div>
          <button
            onClick={onClose}
            className="w-5 h-5 rounded flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </div>

        <div className="p-3 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-muted/30 rounded-lg px-2.5 py-2">
              <div className="text-[9px] text-muted-foreground uppercase tracking-wide mb-0.5">Duration</div>
              <div className="text-sm font-bold text-foreground font-mono">{formatMs(state.duration_ms)}</div>
            </div>
            <div className={`rounded-lg px-2.5 py-2 border ${statusColor}`}>
              <div className="text-[9px] uppercase tracking-wide mb-0.5 opacity-70">Status</div>
              <div className="text-xs font-bold font-mono">{state.status}</div>
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-[9px] text-muted-foreground uppercase tracking-wide">Timing</div>
            <div className="bg-muted/20 rounded-lg px-2.5 py-2 space-y-1">
              <div className="flex justify-between text-[10px]">
                <span className="text-muted-foreground">Start</span>
                <span className="font-mono text-foreground">{startTime.toLocaleTimeString()}.{String(startTime.getMilliseconds()).padStart(3, "0")}</span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span className="text-muted-foreground">End</span>
                <span className="font-mono text-foreground">{endTime.toLocaleTimeString()}.{String(endTime.getMilliseconds()).padStart(3, "0")}</span>
              </div>
            </div>
          </div>

          {state.metadata && Object.keys(state.metadata).length > 0 && (
            <div className="space-y-1">
              <div className="text-[9px] text-muted-foreground uppercase tracking-wide">Metadata</div>
              <div className="bg-muted/20 rounded-lg px-2.5 py-2 max-h-32 overflow-y-auto">
                <div className="space-y-0.5">
                  {Object.entries(state.metadata).map(([key, val]) => (
                    <div key={key} className="flex gap-1.5 text-[10px] flex-wrap">
                      <span className="text-violet-400 font-mono font-semibold flex-shrink-0">{key}:</span>
                      <span>{renderValue(val)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
