# Expedia AI Travel Agent — Conviva Observability Demo

> **Principal Product Builder Interview Demo**
> Built to demonstrate Experience-Centric AI observability: tracking every phase of an agentic workflow in real-time to surface latency, failures, and user friction — the same philosophy Conviva applies to video delivery, applied to AI agents.

---

## What This Is

This is **not just a chatbot**. It's an **Observability Platform for Agentic AI**.

The Expedia Travel Concierge is the demo vehicle. The real product is the telemetry engine underneath it — a system that answers:

- *Where* in the agent pipeline is time being lost?
- *Which* external service call caused a failure?
- *How much* user experience degradation occurred, and what's the revenue impact?

Every message a user sends triggers a measurable, traceable pipeline. Every millisecond is recorded.

---

## Architecture

```
React Frontend (Replit)
        │
        │  POST /chat  ─────────────────────────────────────────────────────┐
        │  GET  /trace/{session_id} ◄── polls every 1s during agent run     │
        │  POST /chaos/toggle                                                │
        │  GET  /health                                                      │
        ▼                                                                    │
┌─────────────────────────────────────────────────────────────────────┐     │
│                     FastAPI Backend (This Repo)                      │     │
│                         Port 8002 · Azure VM                         │     │
│                                                                      │     │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────────┐  │     │
│  │ telemetry.py │    │    main.py       │    │   services.py     │  │     │
│  │              │    │                  │    │                   │  │     │
│  │ SessionStore │◄───│  ChatAgent       │───►│  MockExpedia      │  │     │
│  │ StateObject  │    │  ├─INTENT_MAP    │    │  search_flights   │  │     │
│  │ record_state │    │  ├─LLM_REASONING │    │  search_hotels    │  │     │
│  │ get_summary  │    │  ├─TOOL_CALL     │    │  confirm_booking  │  │     │
│  └──────────────┘    │  ├─TOOL_RESPONSE │    │                   │  │     │
│                      │  └─RESPONSE_SYN  │    │  CHAOS_MODE flag  │  │     │
│                      └──────────────────┘    └───────────────────┘  │     │
└─────────────────────────────────────────────────────────────────────┘     │
        │                                                                    │
        └────────────────────── Azure OpenAI (gpt-4.1) ──────────────────────┘
```

---

## The Five Agentic States

Every user message triggers this pipeline. Each phase is timed independently and stored as a `StateObject`:

| State | What It Measures |
|---|---|
| `INTENT_MAPPING` | How long it takes the LLM to classify what the user wants |
| `LLM_REASONING` | Pure model think-time — deciding which tools to call |
| `TOOL_CALL` | External service latency — waiting on MockExpedia |
| `TOOL_RESPONSE` | Time to inject tool results back into the conversation |
| `RESPONSE_SYNTHESIS` | Final LLM pass to compose the human-readable reply |

Each state has a `status`:
- `SUCCESS` — completed within 3 seconds
- `LATENCY_WARN` — completed but took over 3 seconds (UX friction)
- `FAIL` — raised an exception (booking lost, service down)

---

## The Core Conviva Insight

The `/trace` summary separates:

```
llm_reasoning_ms   ← Pure model think-time
tool_call_ms       ← External API I/O time
```

This split tells you **where to optimize**:
- `llm_reasoning_ms` high → switch to a faster/cheaper model
- `tool_call_ms` high → add caching, reduce API round trips

Without this split, "the agent is slow" is opaque. With it, you know exactly what to fix.

---

## Chaos Mode — The Demo Moment

`POST /chaos/toggle` flips `CHAOS_MODE` in `services.py`.

When active:
- **`search_flights` and `search_hotels`**: lag increases to 4.5–6.5s → every search shows `LATENCY_WARN` in the trace
- **`confirm_booking`**: sleeps 4 seconds then raises HTTP 500:

```json
{
  "error_type": "DOM_SELECTOR_NOT_FOUND",
  "target": "#checkout-button",
  "message": "Automation Error: DOM Selector #checkout-button not found (Stagehand Timeout)",
  "automation_framework": "Stagehand",
  "timeout_ms": 4000
}
```

This simulates what happens when a headless browser automation framework (Stagehand) can't find the checkout button in the DOM — a real failure mode in production booking systems.

The telemetry trace for a chaos booking attempt looks like:

```
INTENT_MAPPING      SUCCESS       800ms
LLM_REASONING       SUCCESS      1200ms
TOOL_CALL           LATENCY_WARN 5100ms  ← search degraded
TOOL_RESPONSE       SUCCESS         1ms
LLM_REASONING       SUCCESS       950ms
TOOL_CALL           FAIL         4012ms  ← booking crashed, chaos_triggered=true
TOOL_RESPONSE       SUCCESS         1ms
RESPONSE_SYNTHESIS  SUCCESS      1100ms

Experience Score:  65/100   ← −10 warn, −25 fail
Revenue at Risk:  $1,200    ← 1 failed booking × avg value
```

The frontend shows the chat appearing to hang — while the trace panel fills in live, showing exactly where and why.

---

## KPI Cards

All metrics are computed server-side in `telemetry.get_summary()`. The frontend reads them directly from `GET /trace/{session_id}` → `summary`:

| KPI | Field | Calculation |
|---|---|---|
| Total Latency | `total_latency_s` | Sum of all state durations in seconds |
| Success Rate | `success_rate_pct` | Successful tool calls / total tool calls × 100 |
| Experience Score | `experience_score` | 100 − (warnings × 10) − (failures × 25) |
| Revenue at Risk | `revenue_at_risk_usd` | Failed tool calls × $1,200 avg booking value |
| Reasoning Ratio | `reasoning_ratio_pct` | LLM time / total time × 100 |

---

## API Reference

### `POST /chat`
Run the agentic pipeline for one user message.

**Request:**
```json
{ "message": "Find me a business class flight from JFK to Paris on April 15", "session_id": "uuid-here" }
```
**Response:**
```json
{ "response": "I found 3 business class options...", "session_id": "uuid-here" }
```

---

### `GET /trace/{session_id}`
Returns the full chronological state timeline and KPI summary for a session.

**Response:**
```json
{
  "session_id": "...",
  "states": [
    {
      "state_name": "TOOL_CALL",
      "status": "FAIL",
      "start_time": "2026-03-23T18:30:00Z",
      "end_time": "2026-03-23T18:30:04Z",
      "duration_ms": 4012.5,
      "metadata": {
        "tool_name": "confirm_booking",
        "chaos_triggered": true,
        "error_detail": {
          "error_type": "DOM_SELECTOR_NOT_FOUND",
          "target": "#checkout-button",
          "message": "Automation Error: DOM Selector #checkout-button not found (Stagehand Timeout)"
        }
      }
    }
  ],
  "summary": {
    "total_latency_s": 13.2,
    "success_rate_pct": 66.7,
    "experience_score": 65,
    "revenue_at_risk_usd": 1200,
    "reasoning_ratio_pct": 17.4,
    "llm_reasoning_ms": 2300,
    "tool_call_ms": 9100,
    "state_count": 8,
    "latency_warnings": 1,
    "failures": 1
  },
  "messages": [
    { "role": "user", "content": "Find me a flight..." },
    { "role": "assistant", "content": "I found 3 options..." }
  ]
}
```

---

### `POST /chaos/toggle`
Flips the global `CHAOS_MODE` flag.

**Response:**
```json
{
  "chaos_mode": true,
  "message": "Chaos mode ENABLED. All searches will lag 4.5–6.5s (LATENCY_WARN). confirm_booking will fail after 4s: DOM Selector #checkout-button not found."
}
```

---

### `GET /health`
Liveness check — also exposes current chaos state.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-23T18:00:00Z",
  "chaos_mode": false,
  "azure_configured": true
}
```

---

## File Structure

```
ExpediaAI/
├── main.py          FastAPI app, ChatAgent agentic loop, all endpoints
├── telemetry.py     SessionStore, StateObject, record_state context manager, KPI summary
├── services.py      MockExpedia (search_flights, search_hotels, confirm_booking), CHAOS_MODE
├── requirements.txt Python dependencies
├── .env.example     Azure OpenAI config template
└── start.sh         Startup script (port 8002)
```

---

## Setup & Running

**1. Install dependencies**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
# Edit .env and fill in your Azure OpenAI credentials
```

**3. Start the server**
```bash
bash start.sh
# → http://0.0.0.0:8002
# → Docs: http://localhost:8002/docs
```

**Required environment variables:**
```
AZURE_OPENAI_KEY              Your Azure OpenAI API key
AZURE_OPENAI_ENDPOINT         https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME  gpt-4o (or your deployment name)
AZURE_OPENAI_API_VERSION      2025-01-01-preview
```

---

## Demo Script

**Normal flow — shows latency distribution:**
1. Ask: *"Find me a business class flight from JFK to Paris on April 15th, and also search hotels for 5 nights"*
2. Watch `/trace` fill in: INTENT_MAPPING → LLM_REASONING → parallel TOOL_CALLs → RESPONSE_SYNTHESIS
3. Note `tool_call_ms` vs `llm_reasoning_ms` split in summary

**Chaos flow — shows failure observability:**
1. `POST /chaos/toggle` (or click the UI toggle)
2. Ask: *"Book the Delta flight"*
3. Watch: searches show LATENCY_WARN → booking shows FAIL → Experience Score drops → Revenue at Risk appears
4. Click the red bar in the Gantt chart → see `DOM_SELECTOR_NOT_FOUND` error in metadata panel
5. `POST /chaos/toggle` again to restore normal operation

---

## Technical Notes

**Session memory**: Conversation history is stored in `SessionStore` per `session_id`. The same `session_id` must be sent on every `/chat` request within a conversation. The server never resets it unless restarted.

**Parallel tool calls**: When the user mentions multiple destinations or asks for both flights and hotels, the LLM fires multiple `TOOL_CALL` states in a single `LLM_REASONING` iteration. This is OpenAI parallel function-calling — working as designed.

**`import services` vs `from services import CHAOS_MODE`**: The module is imported by reference so that `services.CHAOS_MODE = True` in the toggle endpoint mutates the same variable that `MockExpedia` reads at call time. Importing the name directly would capture a snapshot and the toggle would have no effect.

**LATENCY_WARN threshold**: Set to 3000ms in `telemetry.py`. With MockExpedia's 1.5–4.0s random lag, roughly half of all tool calls will exceed this in normal mode — making the observability dashboard immediately compelling without needing chaos enabled.
