# Travel AI Agent — Observability Demo

> An agentic travel assistant with a real-time observability dashboard: every phase of the AI pipeline is tracked, timed, and surfaced in a live trace panel.

---

## What This Is

This is **not just a chatbot**. It's an **Observability Platform for Agentic AI**.

The travel assistant is the demo vehicle. The real value is the telemetry engine underneath — a system that answers:

- *Where* in the agent pipeline is time being lost?
- *Which* external service call caused a failure?
- *How much* user experience degradation occurred, and what's the estimated revenue impact?

Every message a user sends triggers a measurable, traceable pipeline. Every millisecond is recorded.

---

## Architecture

```
React Frontend (Vercel)
        │
        │  POST /chat
        │  GET  /trace/{session_id}   ← polls every 800ms during agent run
        │  POST /chaos/toggle
        │  GET  /health
        ▼
┌──────────────────────────────────────────────────────┐
│              FastAPI Backend (Render)                 │
│                                                      │
│  ┌─────────────┐   ┌───────────────┐   ┌──────────┐ │
│  │ telemetry.py│   │    main.py    │   │services.py│ │
│  │             │   │               │   │           │ │
│  │ SessionStore│◄──│  ChatAgent    │──►│MockTravel │ │
│  │ StateObject │   │  INTENT_MAP   │   │search_    │ │
│  │ record_state│   │  LLM_REASON   │   │  flights  │ │
│  │ get_summary │   │  TOOL_CALL    │   │search_    │ │
│  └─────────────┘   │  TOOL_RESP    │   │  hotels   │ │
│                    │  RESP_SYNTH   │   │confirm_   │ │
│                    └───────────────┘   │  booking  │ │
│                                        └──────────┘ │
└──────────────────────────────────────────────────────┘
        │
        └──────────────── Azure OpenAI (gpt-4o) ──────────────────
```

---

## The Five Agentic States

Every user message triggers this pipeline. Each phase is timed independently and stored as a `StateObject`:

| State | What It Measures |
|---|---|
| `INTENT_MAPPING` | How long it takes the LLM to classify what the user wants |
| `LLM_REASONING` | Pure model think-time — deciding which tools to call |
| `TOOL_CALL` | External service latency — waiting on the mock booking API |
| `TOOL_RESPONSE` | Time to inject tool results back into the conversation |
| `RESPONSE_SYNTHESIS` | Final LLM pass to compose the human-readable reply |

Each state has a `status`:
- `SUCCESS` — completed within 3 seconds
- `LATENCY_WARN` — completed but took over 3 seconds (UX friction)
- `FAIL` — raised an exception (booking lost, service down)

---

## The Core Observability Insight

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
- **`search_flights` and `search_hotels`**: lag increases to 4.5–6.5s → every search shows `LATENCY_WARN`
- **`confirm_booking`**: randomly picks one of seven realistic failure scenarios:

| Failure Type | Sleep | Description |
|---|---|---|
| `DOM_SELECTOR_NOT_FOUND` | 4s | Headless browser can't find checkout button |
| `CAPTCHA_TRIGGERED` | 2s | Bot detection blocked automation |
| `INVENTORY_DEPLETED` | 0.5s | Seat sold between search and checkout |
| `PAYMENT_GATEWAY_TIMEOUT` | 6s | Payment API no response |
| `BOOKING_API_503` | 1s | Upstream provider temporarily down |
| `SESSION_EXPIRED` | 1s | Search token no longer valid |
| `PRICE_CHANGED` | 0.8s | Fare increased since search |

The telemetry trace for a chaos booking attempt looks like:

```
INTENT_MAPPING      SUCCESS       800ms
LLM_REASONING       SUCCESS      1200ms
TOOL_CALL           LATENCY_WARN 5100ms  ← search degraded
TOOL_RESPONSE       SUCCESS         1ms
LLM_REASONING       SUCCESS       950ms
TOOL_CALL           FAIL         4012ms  ← booking crashed
TOOL_RESPONSE       SUCCESS         1ms
RESPONSE_SYNTHESIS  SUCCESS      1100ms

Experience Score:  65/100   ← −10 warn, −25 fail
Revenue at Risk:  ~$3,400   ← actual fare from search results
```

The frontend shows the chat appearing to hang — while the trace panel fills in live, showing exactly where and why.

---

## KPI Cards

All metrics are computed server-side in `telemetry.get_summary()`. The frontend reads them from `GET /trace/{session_id}` → `summary`:

| KPI | Field | Calculation |
|---|---|---|
| Total Latency | `total_latency_s` | Sum of all state durations in seconds |
| Success Rate | `success_rate_pct` | Successful tool calls / total tool calls × 100 |
| Experience Score | `experience_score` | 100 − (warnings × 10) − (failures × 25) |
| Revenue at Risk | `revenue_at_risk_usd` | Value of the last failed booking (from actual search prices) |
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
      "start_time": "2026-04-15T18:30:00Z",
      "end_time": "2026-04-15T18:30:04Z",
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
    "revenue_at_risk_usd": 3400,
    "reasoning_ratio_pct": 17.4,
    "llm_reasoning_ms": 2300,
    "tool_call_ms": 9100,
    "state_count": 8,
    "latency_warnings": 1,
    "failures": 1
  }
}
```

---

### `POST /chaos/toggle`
Flips the global `CHAOS_MODE` flag.

---

### `GET /health`
Liveness check — also exposes current chaos state.

---

## File Structure

```
Travel_AI_Agent_Analytics_Demo/
├── main.py          FastAPI app, ChatAgent agentic loop, all endpoints
├── telemetry.py     SessionStore, StateObject, record_state context manager, KPI summary
├── services.py      MockTravelService (search_flights, search_hotels, confirm_booking), CHAOS_MODE
├── requirements.txt Python dependencies
├── render.yaml      Render deployment config
├── .env.example     Backend environment template
├── start.sh         Local startup script
└── frontend/
    ├── src/
    │   ├── pages/Dashboard.tsx      Main layout, polling logic, state management
    │   ├── components/ChatPanel.tsx  Chat interface
    │   ├── components/TracePanel.tsx Gantt-style trace + KPI cards
    │   ├── components/StateDrawer.tsx Click-through metadata inspector
    │   └── lib/api.ts               Typed fetch wrappers
    ├── .env.example  Frontend environment template
    ├── package.json
    └── vite.config.ts
```

---

## Deploying to Render + Vercel

### Backend → Render

1. Push this repo to GitHub (already done).
2. In Render dashboard: **New → Web Service** → connect the repo.
3. Settings:
   - **Root Directory**: `.` (repo root)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Runtime**: Python 3
4. Add environment variables in Render dashboard:
   ```
   AZURE_OPENAI_KEY              your-key
   AZURE_OPENAI_ENDPOINT         https://YOUR-RESOURCE.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT_NAME  gpt-4o
   AZURE_OPENAI_API_VERSION      2024-02-01
   ```
5. Deploy. Note the Render URL (e.g. `https://travel-ai-agent-backend.onrender.com`).

### Frontend → Vercel

1. In Vercel dashboard: **New Project** → import the same repo.
2. Settings:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. Add environment variable:
   ```
   VITE_BACKEND_URL=https://travel-ai-agent-backend.onrender.com
   ```
4. Deploy.

---

## Local Development

**1. Backend**
```bash
cd Travel_AI_Agent_Analytics_Demo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
bash start.sh
# → http://localhost:8002
# → Docs: http://localhost:8002/docs
```

**2. Frontend**
```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local: VITE_BACKEND_URL=http://localhost:8002
npm run dev
# → http://localhost:3000
```

---

## Demo Script

**Normal flow — shows latency distribution:**
1. Ask: *"Find me a business class flight from JFK to Paris on April 15th, and also search hotels for 5 nights"*
2. Watch the trace fill in: INTENT_MAPPING → LLM_REASONING → parallel TOOL_CALLs → RESPONSE_SYNTHESIS
3. Note the `tool_call_ms` vs `llm_reasoning_ms` split in the summary — the external API is the bottleneck, not the model

**Chaos flow — shows failure observability:**
1. Click the ⚠ button in the sidebar to enable Chaos Mode
2. Ask: *"Book the Delta flight"*
3. Watch: searches show LATENCY_WARN → booking shows FAIL → Experience Score drops → Revenue at Risk appears
4. Click any red bar in the trace → see the structured error detail in the metadata panel
5. Click ⚠ again to disable Chaos Mode and restore normal operation

---

## Technical Notes

**Session memory**: Conversation history is stored in `SessionStore` per `session_id`. The same `session_id` must be sent on every `/chat` request within a conversation.

**Parallel tool calls**: When the user mentions multiple destinations or asks for both flights and hotels, the LLM fires multiple `TOOL_CALL` states in a single `LLM_REASONING` iteration via OpenAI parallel function-calling.

**`import services` vs `from services import CHAOS_MODE`**: The module is imported by reference so that `services.CHAOS_MODE = True` in the toggle endpoint mutates the same variable that `MockTravelService` reads at call time.

**LATENCY_WARN threshold**: Set to 3000ms in `telemetry.py`. With the mock service's 1.5–4.0s random lag, roughly half of all tool calls will exceed this in normal mode — making the observability dashboard immediately compelling without needing Chaos Mode.

**Revenue at Risk calculation**: Uses the actual fare from search results when the LLM omits price fields in `confirm_booking` args, falling back to a $1,200 average only when no price data is available.
