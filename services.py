"""
services.py — Mock Travel Service Layer

Simulates a travel booking API with realistic async latency.
Every method sleeps for 1.5–4.0 seconds to mirror real booking API
response times — ensuring the telemetry system reliably surfaces
LATENCY_WARN states during demos.

CHAOS_MODE is the killer demo feature: when enabled, searches degrade
to 4.5–6.5s lag (LATENCY_WARN) and confirm_booking randomly picks one
of seven realistic failure scenarios — DOM timeout, CAPTCHA, inventory
depletion, payment gateway failure, API 503, session expiry, or price
change — each with its own realistic sleep duration and structured error
payload visible in the telemetry trace metadata.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Global chaos toggle
# ---------------------------------------------------------------------------
# Mutated by POST /chaos/toggle in main.py.
# IMPORTANT: main.py must import this as `import services` (the module),
# not `from services import CHAOS_MODE` (a snapshot at import time).
# Reading `services.CHAOS_MODE` at call time picks up live mutations.
CHAOS_MODE: bool = False

# ---------------------------------------------------------------------------
# Chaos failure scenarios — randomly selected on each confirm_booking call
# ---------------------------------------------------------------------------
# Each entry has a `sleep_s` (realistic timeout duration for that failure type)
# plus the structured error payload stored verbatim in telemetry metadata.
# sleep_s is stripped before raising so it doesn't appear in the error detail.
CHAOS_SCENARIOS: list[dict[str, Any]] = [
    {
        "sleep_s": 4.0,
        "error_type": "DOM_SELECTOR_NOT_FOUND",
        "target": "#checkout-button",
        "message": "Automation Error: DOM Selector #checkout-button not found (Stagehand Timeout)",
        "automation_framework": "Stagehand",
        "timeout_ms": 4000,
    },
    {
        "sleep_s": 2.0,
        "error_type": "CAPTCHA_TRIGGERED",
        "target": "#captcha-challenge",
        "message": "Bot detection triggered: CAPTCHA challenge appeared, automation blocked",
        "automation_framework": "Stagehand",
        "timeout_ms": 2000,
    },
    {
        "sleep_s": 0.5,
        "error_type": "INVENTORY_DEPLETED",
        "target": "booking-api/reserve",
        "message": "Booking rejected: Selected fare is no longer available — seat sold between search and checkout.",
        "automation_framework": "BookingAPI",
        "timeout_ms": 500,
    },
    {
        "sleep_s": 6.0,
        "error_type": "PAYMENT_GATEWAY_TIMEOUT",
        "target": "payment-gateway/charge",
        "message": "Payment gateway timeout: No response after 6000ms. Transaction not processed.",
        "automation_framework": "PaymentGateway",
        "timeout_ms": 6000,
    },
    {
        "sleep_s": 1.0,
        "error_type": "BOOKING_API_503",
        "target": "booking-api/v3/bookings",
        "message": "Booking API unavailable: Service returned HTTP 503. Upstream provider temporarily down.",
        "automation_framework": "BookingAPI",
        "timeout_ms": 1000,
    },
    {
        "sleep_s": 1.0,
        "error_type": "SESSION_EXPIRED",
        "target": "booking-session/validate",
        "message": "Booking session expired: Search session token is no longer valid. Please re-search.",
        "automation_framework": "BookingAPI",
        "timeout_ms": 1000,
    },
    {
        "sleep_s": 0.8,
        "error_type": "PRICE_CHANGED",
        "target": "booking-api/price-lock",
        "message": "Fare no longer valid: Price increased since search. Booking rejected by pricing engine.",
        "automation_framework": "BookingAPI",
        "timeout_ms": 800,
    },
]


class MockTravelService:
    """
    Simulated travel booking API layer with realistic async latency.

    All methods use asyncio.sleep(random.uniform(1.5, 4.0)) to mirror
    real booking API response times. With a 3000ms LATENCY_WARN threshold
    in telemetry.py, roughly half of all tool calls will trigger a warning —
    making the observability dashboard immediately compelling in a live demo.

    The mock data is realistic enough to be convincing (real airline codes,
    IATA airports, Parisian luxury hotels) while being clearly synthetic
    (random price generation, no actual inventory).
    """

    async def search_flights(
        self,
        origin: str,
        destination: str,
        date: str,
    ) -> list[dict[str, Any]]:
        """
        Search for available flights between two airports on a specific date.

        Args:
            origin:      IATA airport code (e.g. "JFK", "LAX", "LHR")
            destination: IATA airport code (e.g. "CDG", "NRT", "DXB")
            date:        Departure date in ISO format YYYY-MM-DD

        Returns:
            List of 3 flight option dicts ordered best-to-cheapest.
        """
        # Chaos mode: extend lag well beyond the 3s LATENCY_WARN threshold
        # so every search shows as degraded in the telemetry timeline.
        lag = random.uniform(4.5, 6.5) if CHAOS_MODE else random.uniform(1.5, 4.0)
        await asyncio.sleep(lag)

        origin = origin.upper()
        destination = destination.upper()

        return [
            {
                "flight_id": f"FL-{random.randint(1000, 9999)}",
                "airline": "Delta Air Lines",
                "flight_number": f"DL{random.randint(100, 999)}",
                "origin": origin,
                "destination": destination,
                "departure": f"{date}T08:30:00Z",
                "arrival": f"{date}T22:15:00Z",
                "duration_hours": 13.75,
                "stops": 0,
                "cabin": "Business",
                "price_usd": round(random.uniform(2800.0, 4200.0), 2),
                "seats_remaining": random.randint(2, 8),
                "amenities": ["Lie-flat seat", "Premium dining", "Priority boarding"],
            },
            {
                "flight_id": f"FL-{random.randint(1000, 9999)}",
                "airline": "Air France",
                "flight_number": f"AF{random.randint(100, 999)}",
                "origin": origin,
                "destination": destination,
                "departure": f"{date}T11:00:00Z",
                "arrival": f"{date}T23:45:00Z",
                "duration_hours": 12.75,
                "stops": 0,
                "cabin": "Business",
                "price_usd": round(random.uniform(3100.0, 4800.0), 2),
                "seats_remaining": random.randint(1, 5),
                "amenities": ["La Première suite", "Champagne service", "Direct aisle access"],
            },
            {
                "flight_id": f"FL-{random.randint(1000, 9999)}",
                "airline": "American Airlines",
                "flight_number": f"AA{random.randint(100, 999)}",
                "origin": origin,
                "destination": destination,
                "departure": f"{date}T16:45:00Z",
                "arrival": f"{date}T10:30:00Z",  # next day
                "duration_hours": 17.75,
                "stops": 1,
                "stopover": "ORD",
                "cabin": "Premium Economy",
                "price_usd": round(random.uniform(1400.0, 1900.0), 2),
                "seats_remaining": random.randint(5, 15),
                "amenities": ["Extra legroom", "Priority check-in"],
            },
        ]

    async def search_hotels(
        self,
        destination: str,
        check_in: str,
        check_out: str,
    ) -> list[dict[str, Any]]:
        """
        Search for available hotels in a destination city for specific dates.

        Args:
            destination: City name (e.g. "Paris", "Tokyo", "Dubai")
            check_in:    ISO date string YYYY-MM-DD
            check_out:   ISO date string YYYY-MM-DD

        Returns:
            List of 3 hotel option dicts ordered luxury-to-accessible.
        """
        # Chaos mode: same degradation as search_flights
        lag = random.uniform(4.5, 6.5) if CHAOS_MODE else random.uniform(1.5, 4.0)
        await asyncio.sleep(lag)

        return [
            {
                "hotel_id": f"HTL-{random.randint(10000, 99999)}",
                "name": "Hôtel Le Meurice",
                "stars": 5,
                "destination": destination,
                "check_in": check_in,
                "check_out": check_out,
                "room_type": "Deluxe Suite with Eiffel Tower View",
                "price_per_night_usd": round(random.uniform(1200.0, 1800.0), 2),
                "amenities": [
                    "Michelin-starred Alain Ducasse restaurant",
                    "Spa & wellness center",
                    "24-hour butler service",
                    "Chanel concierge partnership",
                ],
                "cancellation_policy": "Free cancellation until 48h before check-in",
                "available_rooms": random.randint(1, 3),
                "neighborhood": "1st Arrondissement, Tuileries Garden views",
            },
            {
                "hotel_id": f"HTL-{random.randint(10000, 99999)}",
                "name": "Ritz Paris",
                "stars": 5,
                "destination": destination,
                "check_in": check_in,
                "check_out": check_out,
                "room_type": "Classic Room — Place Vendôme",
                "price_per_night_usd": round(random.uniform(900.0, 1400.0), 2),
                "amenities": [
                    "Hemingway Bar",
                    "L'Espadon Restaurant",
                    "Ritz Club indoor pool",
                    "Chanel spa",
                ],
                "cancellation_policy": "Non-refundable",
                "available_rooms": random.randint(2, 6),
                "neighborhood": "Place Vendôme, 1st Arrondissement",
            },
            {
                "hotel_id": f"HTL-{random.randint(10000, 99999)}",
                "name": "Pullman Paris Centre — Bercy",
                "stars": 4,
                "destination": destination,
                "check_in": check_in,
                "check_out": check_out,
                "room_type": "Superior Room",
                "price_per_night_usd": round(random.uniform(280.0, 420.0), 2),
                "amenities": [
                    "Fitness center",
                    "Rooftop bar",
                    "Business center",
                    "Direct metro access",
                ],
                "cancellation_policy": "Free cancellation until 24h before check-in",
                "available_rooms": random.randint(8, 20),
                "neighborhood": "12th Arrondissement, near Gare de Lyon",
            },
        ]

    async def confirm_booking(
        self,
        booking_type: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Confirm and finalize a flight or hotel booking.

        Args:
            booking_type: "flight" or "hotel"
            details:      Dict with flight_id or hotel_id plus passenger/guest info

        Returns:
            Confirmation dict with booking reference and cost summary.

        Raises:
            HTTPException(500): When CHAOS_MODE is True, randomly picks one
            of seven failure scenarios from CHAOS_SCENARIOS — each with its
            own realistic sleep duration and structured error payload. The
            sleep makes duration_ms realistic for that failure type (e.g.
            6s for payment timeout, 0.5s for instant inventory rejection).
            The error payload lands in telemetry metadata["error_detail"].
        """
        if CHAOS_MODE:
            scenario = random.choice(CHAOS_SCENARIOS)
            await asyncio.sleep(scenario["sleep_s"])
            raise HTTPException(
                status_code=500,
                detail={k: v for k, v in scenario.items() if k != "sleep_s"},
            )

        lag = random.uniform(1.5, 4.0)
        await asyncio.sleep(lag)

        # Extract price from details dict (handles both flight and hotel schemas)
        total_cost = details.get(
            "price_usd",
            details.get("price_per_night_usd", 0.0),
        )

        return {
            "confirmation_number": f"TRVL-{random.randint(100000, 999999)}",
            "booking_type": booking_type,
            "status": "CONFIRMED",
            "details": details,
            "total_cost_usd": total_cost,
            "confirmation_email": "sent to traveler@example.com",
            "estimated_check_in": details.get("check_in", details.get("departure", "N/A")),
            "support_line": "1-800-TRAVEL-AI",
            "cancellation_window": "48 hours before departure/check-in",
        }
