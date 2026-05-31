"""
main.py — Travel AI Agent
Agentic Observability Demo

Orchestration layer: FastAPI routes, the ChatAgent agentic loop,
and OpenAI function-calling instrumented at every phase with telemetry.

Architecture at a glance:
  POST /chat      → ChatAgent.run() → 5-phase pipeline (all telemetry-wrapped)
  GET /trace/{}   → SessionStore chronological trace + summary stats
  POST /chaos/toggle → flip CHAOS_MODE in services.py
  GET /health     → liveness check

The telemetry summary on GET /trace separates:
  llm_reasoning_ms  (pure model think-time)
  tool_call_ms      (external service I/O time)

This split tells you whether to optimize the model or the integrations —
without it, "slow agent" is opaque.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel

import services  # module import (NOT from services import CHAOS_MODE) — see toggle endpoint
from services import MockTravelService
from telemetry import (
    StateName, StateStatus, append_message, get_messages, get_summary, get_trace, record_state,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required environment variables — validated at startup
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = [
    "DEEPSEEK_API_KEY",
]

# ---------------------------------------------------------------------------
# OpenAI Tool Schema Definitions (function-calling format)
# Defined once at module level — reused on every LLM_REASONING call.
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": (
                "Search for available flights between two airports on a specific date. "
                "Returns a list of flight options with airline, pricing, cabin class, "
                "and seat availability. Use IATA airport codes (JFK, CDG, LHR, NRT, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "IATA airport code for departure city (e.g. 'JFK', 'LAX', 'LHR')",
                    },
                    "destination": {
                        "type": "string",
                        "description": "IATA airport code for arrival city (e.g. 'CDG', 'NRT', 'DXB')",
                    },
                    "date": {
                        "type": "string",
                        "description": "Departure date in ISO format YYYY-MM-DD (e.g. '2026-04-15')",
                    },
                },
                "required": ["origin", "destination", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": (
                "Search for available hotels in a destination city for specific dates. "
                "Returns a list of hotel options with star ratings, amenities, nightly "
                "rates, and cancellation policies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "City name (e.g. 'Paris', 'Tokyo', 'Dubai', 'New York')",
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date in ISO format YYYY-MM-DD",
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date in ISO format YYYY-MM-DD",
                    },
                },
                "required": ["destination", "check_in", "check_out"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_booking",
            "description": (
                "Confirm and finalize a flight or hotel booking. "
                "Use this ONLY after the client explicitly confirms they want to proceed "
                "with a specific option. Returns a confirmation number and cost summary. "
                "May fail if the booking system encounters an error."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_type": {
                        "type": "string",
                        "enum": ["flight", "hotel"],
                        "description": "Type of booking to confirm",
                    },
                    "details": {
                        "type": "object",
                        "description": (
                            "The full object from search results for the chosen option. "
                            "Must include the flight_id or hotel_id AND the price fields "
                            "(price_usd for flights, price_per_night_usd + check_in + check_out for hotels). "
                            "Copy the entire result object from the search — do not omit price fields."
                        ),
                    },
                },
                "required": ["booking_type", "details"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are a luxury travel concierge, serving discerning clients \
who expect precision, elegance, and zero friction in their travel arrangements.

Your responsibilities:
- Understand travel needs and preferences with empathy and discretion
- Search for flights and hotels that match the client's standards and budget
- Present options clearly, leading with the best value and highlighting premium features
- Book travel ONLY when the client explicitly says they want to proceed
- Handle booking failures gracefully with immediate alternative suggestions

Communication style:
- Concise but warm — never robotic or overly formal
- Lead with the best option, then offer alternatives briefly
- Proactively flag low seat availability, cancellation policy differences, and price validity
- When a booking fails, acknowledge the inconvenience sincerely and offer alternatives instantly
- Never apologize excessively — move to solutions quickly

Tools available: search_flights, search_hotels, confirm_booking.
Always use real data from tool results. Never fabricate prices, flight numbers, or confirmation codes."""


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str  # Caller mints or reuses a UUID — keeps server stateless


class ChatResponse(BaseModel):
    response: str
    session_id: str


class TraceResponse(BaseModel):
    session_id: str
    states: list[dict[str, Any]]
    summary: dict[str, Any]
    messages: list[dict[str, Any]]  # full chat history for this session


class ChaosToggleResponse(BaseModel):
    chaos_mode: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    chaos_mode: bool
    llm_configured: bool


# ---------------------------------------------------------------------------
# ChatAgent — one agentic turn, fully telemetry-instrumented
# ---------------------------------------------------------------------------

class ChatAgent:
    """
    Orchestrates a single agentic turn using OpenAI function-calling.

    Pipeline phases (each wrapped in record_state):
      1. INTENT_MAPPING     — classify what the user wants (fast LLM call)
      2. LLM_REASONING      — main reasoning call with tool definitions attached
      3. TOOL_CALL          — execute each MockTravelService method the model requested
      4. TOOL_RESPONSE      — inject tool results back into the message thread
      5. RESPONSE_SYNTHESIS — final LLM pass to compose the human-readable reply
                              (only fires if the last reasoning step had no text content)

    Max 5 tool-calling iterations to prevent runaway loops on ambiguous requests.
    One instance per request — the Azure client is created and implicitly closed per turn.
    """

    MAX_ITERATIONS = 5

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.travel_service = MockTravelService()
        self.llm = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )
        self.deployment = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        # Dispatch table maps OpenAI tool name → coroutine function
        self._tool_dispatch: dict[str, Any] = {
            "search_flights":  self._call_search_flights,
            "search_hotels":   self._call_search_hotels,
            "confirm_booking": self._call_confirm_booking,
        }

    async def run(self, user_message: str) -> str:
        """
        Execute the full agentic pipeline for one user turn.

        Returns the final text response string to be sent back to the client.
        All telemetry is written to the SessionStore as a side effect —
        the caller retrieves it via GET /trace/{session_id}.
        """
        # Phase 1: Classify intent before reasoning (fast, no tools)
        intent = await self._detect_intent(user_message)

        # Load prior conversation history from SessionStore (empty on first turn)
        history = get_messages(self.session_id)

        # Build full message thread: system prompt + history + new user message
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": user_message},
        ]

        # Phases 2–4: Reasoning + Tool Calls loop
        for iteration in range(self.MAX_ITERATIONS):
            # Phase 2: LLM_REASONING — ask the model what to do next
            async with record_state(
                self.session_id,
                StateName.LLM_REASONING,
                metadata={
                    "iteration": iteration,
                    "detected_intent": intent,
                    "model": self.deployment,
                    "temperature": 0.3,
                    "message_count": len(messages),
                    "chaos_mode": services.CHAOS_MODE,
                },
            ) as reasoning_state:
                response = await self.llm.chat.completions.create(
                    model=self.deployment,
                    temperature=0.3,
                    timeout=60.0,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                )
                choice = response.choices[0]
                reasoning_state.metadata["finish_reason"] = choice.finish_reason
                reasoning_state.metadata["tool_calls_requested"] = (
                    len(choice.message.tool_calls) if choice.message.tool_calls else 0
                )

            # If the model is done (no tool calls), check for inline text response
            if choice.finish_reason == "stop" or not choice.message.tool_calls:
                if choice.message.content:
                    # Model gave us a final answer directly — no synthesis needed
                    final = choice.message.content
                    append_message(self.session_id, {"role": "user", "content": user_message})
                    append_message(self.session_id, {"role": "assistant", "content": final})
                    return final
                break  # No content, no tools — fall through to synthesis

            # Append the assistant's tool-calling turn to the thread
            messages.append(choice.message)

            # Phase 3: TOOL_CALL — execute each tool the model requested
            for tool_call in choice.message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                    logger.warning("Failed to parse tool args for %s", tool_name)

                async with record_state(
                    self.session_id,
                    StateName.TOOL_CALL,
                    metadata={
                        "tool_name": tool_name,
                        "tool_call_id": tool_call.id,
                        "args": tool_args,
                        "chaos_mode": services.CHAOS_MODE,
                    },
                ) as tool_state:
                    try:
                        dispatch_fn = self._tool_dispatch.get(tool_name)
                        if dispatch_fn is None:
                            tool_result: Any = {
                                "error": f"Unknown tool '{tool_name}'. Available: search_flights, search_hotels, confirm_booking"
                            }
                        else:
                            tool_result = await dispatch_fn(**tool_args)

                        # Enrich telemetry with result metadata
                        tool_state.metadata["result_count"] = (
                            len(tool_result) if isinstance(tool_result, list) else 1
                        )
                        if isinstance(tool_result, dict) and "confirmation_number" in tool_result:
                            tool_state.metadata["confirmation_number"] = tool_result["confirmation_number"]
                        # Store prices from search results so revenue calculation can use
                        # actual fares even when confirm_booking args omit price fields.
                        if tool_name in ("search_flights", "search_hotels") and isinstance(tool_result, list):
                            tool_state.metadata["result_prices"] = [
                                r.get("price_usd") or r.get("price_per_night_usd")
                                for r in tool_result if isinstance(r, dict)
                            ]
                            # Also store check-in/check-out for hotel night calculation
                            if tool_name == "search_hotels" and tool_result:
                                tool_state.metadata["hotel_check_in"] = tool_result[0].get("check_in")
                                tool_state.metadata["hotel_check_out"] = tool_result[0].get("check_out")

                    except HTTPException as exc:
                        # Chaos mode 500 — we catch here so the LLM can respond
                        # gracefully, but we must manually force FAIL status because
                        # the exception never propagates to record_state.__aexit__.
                        tool_result = {
                            "error": exc.detail,
                            "status_code": exc.status_code,
                        }
                        tool_state.status = StateStatus.FAIL  # force — exception was swallowed
                        tool_state.metadata["chaos_triggered"] = True
                        # Store the full structured error so /trace exposes it
                        tool_state.metadata["error_detail"] = (
                            exc.detail if isinstance(exc.detail, dict)
                            else {"message": exc.detail}
                        )
                        logger.warning(
                            "Chaos mode triggered for session %s: %s",
                            self.session_id[:8],
                            exc.detail,
                        )

                # Phase 4: TOOL_RESPONSE — inject result into conversation thread
                async with record_state(
                    self.session_id,
                    StateName.TOOL_RESPONSE,
                    metadata={
                        "tool_name": tool_name,
                        "tool_call_id": tool_call.id,
                        # Truncated snippet for dashboard display
                        "result_snippet": str(tool_result)[:300],
                    },
                ):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, default=str),
                    })

        # Phase 5: RESPONSE_SYNTHESIS — compose the final human-readable reply
        # from all accumulated tool results in the message thread.
        async with record_state(
            self.session_id,
            StateName.RESPONSE_SYNTHESIS,
            metadata={
                "model": self.deployment,
                "temperature": 0.5,
                "total_messages": len(messages),
                "detected_intent": intent,
            },
        ) as synth_state:
            synth_response = await self.llm.chat.completions.create(
                model=self.deployment,
                temperature=0.5,  # Slightly warmer for natural language fluency
                timeout=60.0,
                messages=messages,
            )
            final_text = synth_response.choices[0].message.content or (
                "I apologize — I was unable to formulate a response. "
                "Please try rephrasing your request."
            )
            synth_state.metadata["response_length_chars"] = len(final_text)

        # Persist this turn into SessionStore conversation history
        append_message(self.session_id, {"role": "user", "content": user_message})
        append_message(self.session_id, {"role": "assistant", "content": final_text})

        return final_text

    async def _detect_intent(self, message: str) -> str:
        """
        Phase 1: INTENT_MAPPING — fast single-turn LLM call to classify
        what the user wants before the main reasoning loop begins.

        Returns one of: SEARCH_FLIGHTS | SEARCH_HOTELS | BOOK_TRAVEL |
                        GENERAL_INQUIRY | MULTI_INTENT

        This creates a distinct telemetry state separate from LLM_REASONING,
        so the dashboard can show intent detection latency independently.
        """
        async with record_state(
            self.session_id,
            StateName.INTENT_MAPPING,
            metadata={
                "user_message_length": len(message),
                "model": self.deployment,
            },
        ) as intent_state:
            response = await self.llm.chat.completions.create(
                model=self.deployment,
                temperature=0.0,  # Deterministic classification
                timeout=15.0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a travel intent classifier. "
                            "Classify the user message into exactly ONE label. "
                            "Valid labels: SEARCH_FLIGHTS, SEARCH_HOTELS, BOOK_TRAVEL, "
                            "GENERAL_INQUIRY, MULTI_INTENT. "
                            "Respond with ONLY the label — no explanation, no punctuation."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
            )
            intent = (
                response.choices[0].message.content or "GENERAL_INQUIRY"
            ).strip().upper()

            # Validate — fall back to GENERAL_INQUIRY if model hallucinated a label
            valid_intents = {
                "SEARCH_FLIGHTS", "SEARCH_HOTELS", "BOOK_TRAVEL",
                "GENERAL_INQUIRY", "MULTI_INTENT",
            }
            if intent not in valid_intents:
                intent = "GENERAL_INQUIRY"

            intent_state.metadata["detected_intent"] = intent

        return intent

    # ---------------------------------------------------------------------------
    # Tool dispatch helpers — thin async wrappers keyed to TOOL_DEFINITIONS names
    # ---------------------------------------------------------------------------

    async def _call_search_flights(
        self, origin: str, destination: str, date: str
    ) -> list[dict[str, Any]]:
        return await self.travel_service.search_flights(origin, destination, date)

    async def _call_search_hotels(
        self, destination: str, check_in: str, check_out: str
    ) -> list[dict[str, Any]]:
        return await self.travel_service.search_hotels(destination, check_in, check_out)

    async def _call_confirm_booking(
        self, booking_type: str, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # details is occasionally omitted by the LLM — default to empty dict
        # so the call doesn't hard-crash and the agent can handle it gracefully
        return await self.travel_service.confirm_booking(booking_type, details or {})


# ---------------------------------------------------------------------------
# App Lifespan — startup validation
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [k for k in REQUIRED_ENV_VARS if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"Travel AI Agent cannot start — missing environment variables: {missing}\n"
            "Copy .env.example to .env and fill in your DeepSeek credentials."
        )
    logger.info(
        "Travel AI Agent started | Model: %s | Chaos: %s",
        os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        services.CHAOS_MODE,
    )
    yield
    logger.info("Travel AI Agent shutdown.")


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Travel AI Agent",
    description=(
        "Agentic travel concierge with real-time observability. "
        "Tracks INTENT_MAPPING, LLM_REASONING, TOOL_CALL, "
        "TOOL_RESPONSE, and RESPONSE_SYNTHESIS phases with millisecond precision."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: open to all origins so the frontend can reach the API cross-domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Meta"])
async def health() -> HealthResponse:
    """
    Liveness check. Also exposes current CHAOS_MODE status so the frontend
    can reflect it in the UI without a separate state-fetch call.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        chaos_mode=services.CHAOS_MODE,
        llm_configured=bool(os.getenv("DEEPSEEK_API_KEY")),
    )


@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main agentic endpoint. Runs the full 5-phase pipeline and returns
    the LLM's final text response.

    The session_id groups all states from this turn into a single trace.
    Use the same session_id across multiple turns to accumulate a full
    conversation trace — or mint a new UUID per turn for isolated traces.
    All telemetry is queryable immediately after this call via GET /trace/{session_id}.
    """
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(
        "POST /chat | session=%s... | message_len=%d | chaos=%s",
        session_id[:8],
        len(request.message),
        services.CHAOS_MODE,
    )

    try:
        agent = ChatAgent(session_id=session_id)
        response_text = await agent.run(request.message)
    except Exception as exc:
        logger.exception("Unhandled error in /chat for session %s", session_id[:8])
        raise HTTPException(
            status_code=500,
            detail=f"Agent pipeline error: {type(exc).__name__}: {exc}",
        )

    return ChatResponse(response=response_text, session_id=session_id)


@app.get("/trace/{session_id}", response_model=TraceResponse, tags=["Telemetry"])
async def get_trace_endpoint(session_id: str) -> TraceResponse:
    """
    Returns the full chronological timeline of all captured StateObjects
    for the given session, plus an observability summary.

    Summary KPI fields (all computed server-side):
      total_latency_s       — wall-clock seconds for the full turn
      success_rate_pct      — % of tool calls that didn't FAIL
      experience_score      — 0–100 UX quality score (−10/warn, −25/fail)
      revenue_at_risk_usd   — failed tool calls × $1,200 avg booking value
      reasoning_ratio_pct   — LLM think-time as % of total
      llm_reasoning_ms      — pure model latency, isolated from tool I/O
      tool_call_ms          — external API latency, isolated from model
    """
    states = get_trace(session_id)
    summary = get_summary(session_id)

    return TraceResponse(
        session_id=session_id,
        states=[s.model_dump() for s in states],
        summary=summary,
        messages=get_messages(session_id),
    )


@app.post("/chaos/toggle", response_model=ChaosToggleResponse, tags=["Debug"])
async def toggle_chaos() -> ChaosToggleResponse:
    """
    Flips the global CHAOS_MODE flag in services.py.

    When CHAOS_MODE is True:
      - search_flights and search_hotels lag 4.5–6.5s (always LATENCY_WARN)
      - confirm_booking sleeps then raises HTTP 500 with a structured error

    In the telemetry trace, this produces:
      - TOOL_CALL StateObjects with status=LATENCY_WARN on all searches
      - A TOOL_CALL StateObject with status=FAIL on confirm_booking
      - duration_ms reflects actual sleep duration
      - metadata.chaos_triggered = true
      - metadata.error_detail = the structured error dict
    """
    services.CHAOS_MODE = not services.CHAOS_MODE
    enabled = services.CHAOS_MODE
    status_word = "ENABLED" if enabled else "DISABLED"

    logger.warning("CHAOS_MODE %s via /chaos/toggle", status_word)

    return ChaosToggleResponse(
        chaos_mode=enabled,
        message=(
            f"Chaos mode {status_word}. "
            + (
                "All searches will lag 4.5–6.5s (LATENCY_WARN). "
                "confirm_booking will randomly fail with: DOM timeout, CAPTCHA, "
                "inventory depletion, payment gateway failure, API 503, session expiry, or price change."
                if enabled
                else "All services restored to normal operation."
            )
        ),
    )
