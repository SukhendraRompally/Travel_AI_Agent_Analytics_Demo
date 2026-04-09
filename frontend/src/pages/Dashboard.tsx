import { useState, useRef, useEffect, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import ChatPanel from "@/components/ChatPanel";
import TracePanel from "@/components/TracePanel";
import ControlSidebar from "@/components/ControlSidebar";
import { postChat, getTrace, postChaosToggle, getHealth } from "@/lib/api";
import type { StateObject, TraceSummary } from "@/lib/api";
import { Activity } from "lucide-react";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export default function Dashboard() {
  const sessionIdRef = useRef<string>(uuidv4());
  const [messages, setMessages] = useState<Message[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [states, setStates] = useState<StateObject[]>([]);
  const [summary, setSummary] = useState<TraceSummary | null>(null);
  const [chaosMode, setChaosMode] = useState(false);
  const [chaosLoading, setChaosLoading] = useState(false);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => {
        setBackendOnline(true);
        if (h.chaos_mode !== undefined) setChaosMode(h.chaos_mode);
      })
      .catch(() => setBackendOnline(false));
  }, []);

  const startPolling = useCallback(() => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(async () => {
      try {
        const trace = await getTrace(sessionIdRef.current);
        setStates(trace.states ?? []);
        setSummary(trace.summary ?? null);
      } catch {
        // ignore polling errors silently
      }
    }, 800);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const sendMessage = useCallback(async (text: string) => {
    const userMsg: Message = {
      id: uuidv4(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsProcessing(true);
    setStates([]);
    setSummary(null);
    startPolling();

    try {
      const result = await postChat(text, sessionIdRef.current);
      stopPolling();
      const finalTrace = await getTrace(sessionIdRef.current);
      setStates(finalTrace.states ?? []);
      setSummary(finalTrace.summary ?? null);

      const assistantMsg: Message = {
        id: uuidv4(),
        role: "assistant",
        content: result.response,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      stopPolling();
      const errorMsg: Message = {
        id: uuidv4(),
        role: "assistant",
        content: "Sorry, I encountered an error reaching the backend. Please check your connection.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsProcessing(false);
    }
  }, [startPolling, stopPolling]);

  const handleChaosToggle = useCallback(async () => {
    setChaosLoading(true);
    try {
      const result = await postChaosToggle();
      setChaosMode(result.chaos_mode);
    } catch {
      // ignore
    } finally {
      setChaosLoading(false);
    }
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-background overflow-hidden">
      <header className="flex items-center justify-between px-5 py-2.5 border-b border-border bg-sidebar flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-primary flex items-center justify-center">
              <Activity className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-sm font-semibold text-foreground tracking-tight">AI Observer</span>
          </div>
          <span className="text-border text-sm">|</span>
          <span className="text-muted-foreground text-xs">Travel AI Observability</span>
          {backendOnline !== null && (
            <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${
              backendOnline
                ? "bg-green-500/15 text-green-400"
                : "bg-red-500/15 text-red-400"
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? "bg-green-400 pulse-dot" : "bg-red-400"}`} />
              {backendOnline ? "Backend Online" : "Backend Offline"}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
          <span className="text-muted-foreground/50">session</span>
          <span>{sessionIdRef.current.slice(0, 12)}…</span>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <ControlSidebar
          chaosMode={chaosMode}
          chaosLoading={chaosLoading}
          onChaosToggle={handleChaosToggle}
          sessionId={sessionIdRef.current}
          isProcessing={isProcessing}
          stateCount={states.length}
        />

        <div className="flex flex-1 overflow-hidden">
          <div className="w-1/2 border-r border-border flex flex-col overflow-hidden">
            <ChatPanel
              messages={messages}
              isProcessing={isProcessing}
              onSendMessage={sendMessage}
            />
          </div>
          <div className="w-1/2 flex flex-col overflow-hidden">
            <TracePanel
              states={states}
              summary={summary}
              isProcessing={isProcessing}
              chaosMode={chaosMode}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
