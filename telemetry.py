"""
telemetry.py — Conviva-Style Agentic State Tracking

This module is the observability core of the Expedia AI Travel Agent.
It tracks every phase of the agent's reasoning pipeline as discrete,
timed StateObjects — enabling real-time identification of latency,
failures, and friction in the agentic workflow.

Architecture principle: Telemetry is a first-class citizen.
The record_state context manager makes instrumentation impossible to forget —
you cannot call a tool or invoke the LLM without the wrapping.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Conviva insight: anything over 3 seconds in an agentic flow is a UX friction event.
LATENCY_WARN_THRESHOLD_MS: float = 3000.0


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StateName(str, Enum):
    """
    The five phases of the agentic pipeline — analogous to Conviva's
    video delivery states (Buffering, Playing, Stalled, etc.) but for AI agents.
    """
    INTENT_MAPPING     = "INTENT_MAPPING"      # Classifying what the user wants
    LLM_REASONING      = "LLM_REASONING"       # Model deciding what to do next
    TOOL_CALL          = "TOOL_CALL"           # Calling a MockExpedia service
    TOOL_RESPONSE      = "TOOL_RESPONSE"       # Injecting tool result into thread
    RESPONSE_SYNTHESIS = "RESPONSE_SYNTHESIS"  # Final LLM pass to compose reply


class StateStatus(str, Enum):
    """
    Outcome classification for each state — maps directly to what a Conviva
    dashboard would show: green (SUCCESS), yellow (LATENCY_WARN), red (FAIL).
    """
    SUCCESS      = "SUCCESS"
    FAIL         = "FAIL"
    LATENCY_WARN = "LATENCY_WARN"


# ---------------------------------------------------------------------------
# State Object — the fundamental record
# ---------------------------------------------------------------------------

class StateObject(BaseModel):
    """
    A single timed unit of agent work.

    Fields are intentionally flat (no nesting) so the trace endpoint can
    serialize them directly without transformation — ideal for a React
    dashboard to consume and render as a timeline.

    state_name:   What the agent was doing (from the StateName enum)
    start_time:   ISO-8601 UTC timestamp when the phase began
    end_time:     ISO-8601 UTC timestamp when it ended (set by record_state)
    duration_ms:  Milliseconds between start and end (computed, never caller-set)
    status:       SUCCESS / FAIL / LATENCY_WARN
    metadata:     Caller-enriched context — tool args, model params, result
                  snippets, chaos flags, etc. This is where the Conviva-level
                  diagnostic detail lives.
    """
    state_name:  StateName
    start_time:  str                             # ISO-8601
    end_time:    str = ""                        # filled in by record_state.__aexit__
    duration_ms: float = 0.0                    # filled in by record_state.__aexit__
    status:      StateStatus = StateStatus.SUCCESS
    metadata:    dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Session Store — in-memory session → trace map
# ---------------------------------------------------------------------------

class SessionStore:
    """
    Single source of truth for a session: telemetry states AND chat history.

    _states:   session_id → chronological list of StateObjects (telemetry)
    _messages: session_id → conversation message thread (chat context)

    Keeping both here means one place manages all per-session state,
    and the /trace endpoint can return everything in a single lookup.
    """

    def __init__(self) -> None:
        self._states: dict[str, list[StateObject]] = {}
        self._messages: dict[str, list[dict[str, Any]]] = {}

    def _ensure_session(self, session_id: str) -> None:
        if session_id not in self._states:
            self._states[session_id] = []
        if session_id not in self._messages:
            self._messages[session_id] = []

    # --- Telemetry state methods ---

    def append(self, session_id: str, state: StateObject) -> None:
        self._ensure_session(session_id)
        self._states[session_id].append(state)
        logger.debug(
            "Telemetry [%s...] %s → %s (%.0fms)",
            session_id[:8],
            state.state_name.value,
            state.status.value,
            state.duration_ms,
        )

    def get_trace(self, session_id: str) -> list[StateObject]:
        return list(self._states.get(session_id, []))

    # --- Conversation history methods ---

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Returns the stored conversation history (excludes system prompt)."""
        self._ensure_session(session_id)
        return self._messages[session_id]

    def append_message(self, session_id: str, message: dict[str, Any]) -> None:
        """Appends a single message dict (role + content) to the session history."""
        self._ensure_session(session_id)
        self._messages[session_id].append(message)

    def clear(self, session_id: str) -> None:
        self._states.pop(session_id, None)
        self._messages.pop(session_id, None)


# Module-level singleton — one store for the lifetime of the process.
_store = SessionStore()


# ---------------------------------------------------------------------------
# record_state — the core instrumentation primitive
# ---------------------------------------------------------------------------

@asynccontextmanager
async def record_state(
    session_id: str,
    state_name: StateName,
    metadata: dict[str, Any] | None = None,
) -> AsyncGenerator[StateObject, None]:
    """
    Async context manager that wraps any agent phase with automatic timing
    and status classification.

    Usage:
        async with record_state(session_id, StateName.TOOL_CALL, {"tool": "search_flights"}) as state:
            result = await expedia.search_flights(origin, dest, date)
            state.metadata["result_count"] = len(result)   # enrich mid-flight

    The StateObject is yielded so callers can attach result data before
    __aexit__ fires. Status logic:
      - Exception propagates → status = FAIL
      - duration_ms > LATENCY_WARN_THRESHOLD_MS → status = LATENCY_WARN
      - Otherwise → status = SUCCESS

    Telemetry NEVER swallows exceptions — errors always propagate to callers.
    """
    state = StateObject(
        state_name=state_name,
        start_time=datetime.now(timezone.utc).isoformat(),
        metadata=metadata or {},
    )
    _store._ensure_session(session_id)

    try:
        yield state

        # __aexit__ success path
        end_dt = datetime.now(timezone.utc)
        state.end_time = end_dt.isoformat()
        start_dt = datetime.fromisoformat(state.start_time)
        state.duration_ms = (end_dt - start_dt).total_seconds() * 1000
        state.status = (
            StateStatus.LATENCY_WARN
            if state.duration_ms > LATENCY_WARN_THRESHOLD_MS
            else StateStatus.SUCCESS
        )

    except Exception:
        # __aexit__ failure path — compute timing before re-raising
        end_dt = datetime.now(timezone.utc)
        state.end_time = end_dt.isoformat()
        start_dt = datetime.fromisoformat(state.start_time)
        state.duration_ms = (end_dt - start_dt).total_seconds() * 1000
        state.status = StateStatus.FAIL
        raise

    finally:
        # Always persist — even on exceptions the state is recorded
        _store.append(session_id, state)


# ---------------------------------------------------------------------------
# Public read API
# ---------------------------------------------------------------------------

def get_trace(session_id: str) -> list[StateObject]:
    """Returns the full chronological list of StateObjects for a session."""
    return _store.get_trace(session_id)


def get_messages(session_id: str) -> list[dict[str, Any]]:
    """Returns the persistent conversation history for a session."""
    return _store.get_messages(session_id)


def append_message(session_id: str, message: dict[str, Any]) -> None:
    """Appends a message to the session's persistent conversation history."""
    _store.append_message(session_id, message)


def get_summary(session_id: str) -> dict[str, Any]:
    """
    Computes aggregate statistics over a session's trace.

    The key Conviva insight: llm_reasoning_ms vs tool_call_ms tells you
    WHERE the latency lives.

      llm_reasoning_ms high → model is the bottleneck (try a faster/cheaper model)
      tool_call_ms high     → integrations are the bottleneck (add caching, reduce round trips)

    This separation is what makes this more than a chatbot — it's an
    Experience Analytics system for AI agents.
    """
    states = _store.get_trace(session_id)
    if not states:
        return {
            "state_count": 0,
            "latency_warnings": 0,
            "failures": 0,
            "successes": 0,
            "tool_calls_total": 0,
            "total_duration_ms": 0.0,
            "total_latency_s": 0.0,
            "llm_reasoning_ms": 0.0,
            "tool_call_ms": 0.0,
            "success_rate_pct": 100.0,
            "reasoning_ratio_pct": 0.0,
            "experience_score": 100,
            "revenue_at_risk_usd": 0,
        }

    total_ms = round(sum(s.duration_ms for s in states), 2)

    # LLM vs Tool latency split (the core Conviva insight)
    llm_ms = round(
        sum(s.duration_ms for s in states if s.state_name == StateName.LLM_REASONING), 2
    )
    tool_ms = round(
        sum(s.duration_ms for s in states if s.state_name == StateName.TOOL_CALL), 2
    )

    # Status counts
    latency_warnings = sum(1 for s in states if s.status == StateStatus.LATENCY_WARN)
    failures = sum(1 for s in states if s.status == StateStatus.FAIL)
    successes = sum(1 for s in states if s.status == StateStatus.SUCCESS)

    # --- KPI 1: Total Latency ---
    # Wall-clock time for the entire agent turn, in seconds for readability.
    total_latency_s = round(total_ms / 1000, 2)

    # --- KPI 2: Success Rate ---
    # Percentage of TOOL_CALL states that completed without FAIL.
    # We scope to TOOL_CALL only — LLM/intent states are internal overhead,
    # not user-visible operations. This answers "what % of Expedia API calls worked?"
    tool_calls = [s for s in states if s.state_name == StateName.TOOL_CALL]
    tool_calls_total = len(tool_calls)
    tool_calls_failed = sum(1 for s in tool_calls if s.status == StateStatus.FAIL)
    success_rate_pct = round(
        ((tool_calls_total - tool_calls_failed) / tool_calls_total * 100)
        if tool_calls_total > 0 else 100.0,
        1,
    )

    # --- KPI 3: Reasoning Ratio ---
    # LLM think-time as % of total — high means model is the bottleneck.
    reasoning_ratio_pct = round((llm_ms / total_ms * 100) if total_ms > 0 else 0.0, 1)

    # --- KPI 4: Experience Score (0–100) ---
    # Composite UX quality score analogous to Conviva's Video Quality Score.
    # Starts at 100, deducted for every friction event:
    #   -10 per LATENCY_WARN (slow but recoverable)
    #   -25 per FAIL (hard error — booking lost or search unavailable)
    experience_score = max(0, 100 - (latency_warnings * 10) - (failures * 25))

    # --- KPI 5: Revenue at Risk ---
    # Only FAIL states represent a lost booking — LATENCY_WARN is friction, not loss.
    # $1,200 = conservative average luxury flight/hotel booking value.
    AVERAGE_BOOKING_VALUE_USD = 1200
    revenue_at_risk_usd = tool_calls_failed * AVERAGE_BOOKING_VALUE_USD

    return {
        # Raw counts — for frontend tables and detail views
        "state_count": len(states),
        "latency_warnings": latency_warnings,
        "failures": failures,
        "successes": successes,
        "tool_calls_total": tool_calls_total,

        # Latency breakdown
        "total_duration_ms": total_ms,
        "total_latency_s": total_latency_s,         # KPI card: "Total Latency"
        "llm_reasoning_ms": llm_ms,
        "tool_call_ms": tool_ms,

        # KPI cards — all computed here, frontend just displays
        "success_rate_pct": success_rate_pct,        # KPI card: "Success Rate"
        "reasoning_ratio_pct": reasoning_ratio_pct,  # KPI card: "Reasoning Ratio"
        "experience_score": experience_score,         # KPI card: "Experience Score"
        "revenue_at_risk_usd": revenue_at_risk_usd,  # KPI card: "Revenue at Risk"
    }
