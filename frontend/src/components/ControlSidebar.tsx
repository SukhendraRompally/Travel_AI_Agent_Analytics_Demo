import { AlertTriangle, RefreshCw } from "lucide-react";

interface ControlSidebarProps {
  chaosMode: boolean;
  chaosLoading: boolean;
  onChaosToggle: () => void;
  sessionId: string;
  isProcessing: boolean;
  stateCount: number;
}

export default function ControlSidebar({
  chaosMode,
  chaosLoading,
  onChaosToggle,
}: ControlSidebarProps) {
  return (
    <div className="w-14 flex-shrink-0 border-r border-border bg-sidebar flex flex-col items-center py-4 gap-5">
      <div className="flex flex-col items-center gap-1.5">
        <button
          onClick={onChaosToggle}
          disabled={chaosLoading}
          title={chaosMode ? "Disable chaos mode" : "Simulate Agent Failure"}
          className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all border ${
            chaosMode
              ? "bg-red-500/20 border-red-500/40 text-red-400"
              : "bg-muted border-border text-muted-foreground hover:border-red-500/40 hover:text-red-400 hover:bg-red-500/10"
          } ${chaosLoading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
        >
          {chaosLoading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <AlertTriangle className="w-4 h-4" />
          )}
        </button>
        <span className={`text-[8px] uppercase tracking-wide text-center leading-tight ${chaosMode ? "text-red-400 font-semibold" : "text-muted-foreground"}`}>
          {chaosMode ? "Chaos" : "Failure"}
        </span>
      </div>

      {chaosMode && (
        <div className="w-1.5 h-1.5 rounded-full bg-red-500 pulse-dot" />
      )}
    </div>
  );
}
