import { useState, useRef, useEffect } from "react";
import { Send, Plane, Bot, User, Loader2 } from "lucide-react";
import type { Message } from "@/pages/Dashboard";

interface ChatPanelProps {
  messages: Message[];
  isProcessing: boolean;
  onSendMessage: (text: string) => void;
}

const SUGGESTIONS = [
  "Find me flights from NYC to London next week",
  "What hotels are available in Paris for 2 adults?",
  "Book a round trip to Tokyo in April",
  "What's the cheapest way to get to Miami this weekend?",
];

export default function ChatPanel({ messages, isProcessing, onSendMessage }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isProcessing]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isProcessing) return;
    setInput("");
    onSendMessage(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-background">
      <div className="px-5 py-4 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-md">
            <Plane className="w-4 h-4 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-foreground">Travel AI</h2>
            <p className="text-xs text-muted-foreground">Travel Intelligence Agent</p>
          </div>
          <div className="ml-auto flex items-center gap-1.5 text-xs text-green-400">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 pulse-dot" />
            Online
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-6 py-8">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-700/20 border border-blue-500/20 flex items-center justify-center">
              <Plane className="w-8 h-8 text-blue-400" />
            </div>
            <div className="text-center">
              <h3 className="text-sm font-semibold text-foreground mb-1">Travel AI Assistant</h3>
              <p className="text-xs text-muted-foreground max-w-[260px]">
                Ask me anything about flights, hotels, or travel plans. Watch the observability panel come alive.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2 w-full max-w-[300px]">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => onSendMessage(s)}
                  disabled={isProcessing}
                  className="text-left text-xs px-3 py-2 rounded-lg border border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-2.5 slide-in-up ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
          >
            <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs ${
              msg.role === "user"
                ? "bg-primary text-primary-foreground"
                : "bg-gradient-to-br from-blue-500 to-blue-700"
            }`}>
              {msg.role === "user" ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5 text-white" />}
            </div>
            <div className={`max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1`}>
              <div className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground rounded-tr-sm"
                  : "bg-card border border-border text-foreground rounded-tl-sm"
              }`}>
                {msg.content}
              </div>
              <span className="text-[10px] text-muted-foreground px-1">
                {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          </div>
        ))}

        {isProcessing && (
          <div className="flex gap-2.5 slide-in-up">
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-white" />
            </div>
            <div className="px-3.5 py-2.5 rounded-2xl rounded-tl-sm bg-card border border-border flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
              <span className="text-xs text-muted-foreground">Processing your request…</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="px-4 pb-4 pt-2 flex-shrink-0 border-t border-border">
        <div className="flex gap-2 items-end bg-card border border-border rounded-xl p-2 focus-within:border-primary/60 transition-colors">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about flights, hotels, or travel plans…"
            disabled={isProcessing}
            rows={1}
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground resize-none outline-none min-h-[24px] max-h-[120px] py-1 px-1 leading-6 disabled:opacity-50"
            style={{ height: "auto" }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isProcessing}
            className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1.5 px-1">
          Press Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
