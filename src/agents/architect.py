from src.agents.base import BaseAgent
from src.models.state import TravelState
from src.models.itinerary import ItineraryPlan

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
        p = state.preferences
        prompt = f"""
        Build a {p.days}-day itinerary for {p.destination}.
        Budget: {p.budget} INR.
        Month: {p.month}.
        Origin: {p.origin}.
        Arrival time preference: {p.arrival_time}.
        Hotel tier: {p.hotel_type}.
        Food preferences: {p.food_preferences}.
        Transport already booked/researched: {p.transport_suggestions}.

        Produce exactly {p.days} day entries (n=1 through n={p.days}), each with 3-4 activity
        segments covering the day from morning to evening, with realistic times, costs, walking
        distances, crowd levels, and transport guidance. Day 1 should account for arriving via
        the researched transport option above at the stated arrival time preference. Every
        activity, meal, and neighborhood choice should be consistent with the stated hotel tier
        and food preference.
        """

        structured_llm = self.llm.with_structured_output(ItineraryPlan, method="function_calling")
        result = structured_llm.invoke(prompt)
        plan = self._backfill_missing_fields(result)
        return {"itinerary": plan}

    def _backfill_missing_fields(self, result: ItineraryPlan) -> dict:
        """Deterministic safety net: LLMs don't reliably fill every optional field
        even when told to. Never show a blank cost/crowd/transport chip in the UI —
        fill anything missing with a clearly-labeled, sensible default instead."""
        plan = result.model_dump()
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
