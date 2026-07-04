from src.agents.base import BaseAgent
from src.models.state import TravelState
from src.models.itinerary import ItineraryDay

CROWD_LEVELS = {"low", "moderate", "busy"}


class ItineraryArchitectAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are a master travel planner. Generate detailed, logical, day-by-day travel "
            "itineraries that strictly follow the given schema. For every activity segment, write "
            "a specific, concrete title and description (never generic placeholders like "
            "'Activity'), a realistic cost in INR (0 if free — never leave cost blank), a crowd "
            "level (low/moderate/busy — never leave blank), transport guidance to the next segment "
            "(e.g. 'Walk 10 min', 'Auto-rickshaw 15 min', 'Return to hotel' on the day's last "
            "segment — never leave blank), a confidence score reflecting how well-known the "
            "recommendation is, and at least one evidence entry categorized as one of: dna, live, "
            "local, web, comm, pref. Every day must reflect the traveler's stated hotel tier and "
            "food preference — pick restaurants and areas consistent with a stay at that hotel "
            "tier, and every meal segment must match the stated food preference."
        )
        super().__init__("Itinerary Architect", system_prompt)

    def run(self, state: TravelState, input_text: str) -> dict:
        """Build the itinerary one day at a time rather than asking for the whole
        trip in a single structured-output call. Asked for "exactly N days" in one
        shot, the model would sometimes produce a single very detailed day and stop,
        silently truncating the trip — an easy failure mode with no schema-level way
        to enforce array length. Generating day-by-day makes the day count a fact
        guaranteed by this loop, not something the model can get wrong."""
        p = state.preferences
        total_days = p.days or 1
        day_entries = [self._build_day(state, day_n, total_days) for day_n in range(1, total_days + 1)]
        plan = {"itinerary": day_entries}
        return {"itinerary": self._backfill_missing_fields(plan)}

    def _build_day(self, state: TravelState, day_n: int, total_days: int) -> dict:
        p = state.preferences
        position_note = ""
        if day_n == 1:
            position_note = (
                f"This is day 1 — account for arriving via the researched transport option "
                f"({p.transport_suggestions}) at the {p.arrival_time} arrival time preference."
            )
        elif day_n == total_days:
            position_note = "This is the last day — keep the pace relaxed and account for departure logistics."

        prompt = f"""
        Build ONLY day {day_n} of a {total_days}-day itinerary for {p.destination}.
        Budget: {p.budget} INR for the whole trip. Month: {p.month}. Origin: {p.origin}.
        Hotel tier: {p.hotel_type}. Food preferences: {p.food_preferences}.
        {position_note}

        Produce exactly one day entry (n={day_n}) with 3-4 activity segments covering the day
        from morning to evening, with realistic times, costs, walking distances, crowd levels,
        and transport guidance.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        structured_llm = self.llm.with_structured_output(ItineraryDay, method="function_calling")
        result = structured_llm.invoke(messages)
        return result.model_dump()

    def _backfill_missing_fields(self, plan: dict) -> dict:
        """Deterministic safety net: LLMs don't reliably fill every optional field
        even when told to. Never show a blank cost/crowd/transport chip in the UI —
        fill anything missing with a clearly-labeled, sensible default instead."""
        for day in plan.get("itinerary", []):
            segments = day.get("segments", [])
            for i, seg in enumerate(segments):
                if seg.get("cost") is None:
                    seg["cost"] = 0
                if not seg.get("crowd") or seg["crowd"] not in CROWD_LEVELS:
                    seg["crowd"] = "moderate"
                if not seg.get("transport"):
                    seg["transport"] = "Return to hotel" if i == len(segments) - 1 else "Walk"
        return plan
