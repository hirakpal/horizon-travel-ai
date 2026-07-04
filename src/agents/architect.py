import difflib
import os

from src.agents.base import BaseAgent
from src.models.state import TravelState
from src.models.itinerary import ItineraryDay
from src.tools import google_maps

CROWD_LEVELS = {"low", "moderate", "busy"}
PLACE_MATCH_THRESHOLD = 0.55


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
            "tier, and every meal segment must match the stated food preference. When a list of "
            "real researched places is provided, prefer using their exact names rather than "
            "inventing your own — but never force a mismatch just to use one."
        )
        super().__init__("Itinerary Architect", system_prompt)

    def run(self, state: TravelState, input_text: str) -> dict:
        """Build the itinerary one day at a time rather than asking for the whole
        trip in a single structured-output call. Asked for "exactly N days" in one
        shot, the model would sometimes produce a single very detailed day and stop,
        silently truncating the trip — an easy failure mode with no schema-level way
        to enforce array length. Generating day-by-day makes the day count a fact
        guaranteed by this loop, not something the model can get wrong.

        If GOOGLE_MAPS_API_KEY is configured, real candidate places are fetched
        once up front and threaded through every day's prompt (a lightweight
        retrieval-then-generate pattern), then matched back onto whatever the
        model actually wrote so the UI can show real ratings/addresses/photos
        and real walking distances. Without a key, this is a complete no-op —
        the itinerary is built exactly as before, LLM-only."""
        p = state.preferences
        total_days = p.days or 1
        candidates = self._fetch_place_candidates(p.destination, p.food_preferences)

        used_names = set()
        day_entries = []
        for day_n in range(1, total_days + 1):
            day = self._build_day(state, day_n, total_days, candidates, used_names)
            day = self._backfill_day(day)
            if candidates:
                day = self._ground_day_with_real_places(day, candidates, used_names)
            day_entries.append(day)

        plan = {"itinerary": day_entries}
        if candidates:
            plan = self._apply_real_distances(plan)
        return {"itinerary": plan}

    def _build_day(self, state: TravelState, day_n: int, total_days: int,
                    candidates: list, used_names: set) -> dict:
        p = state.preferences
        position_note = ""
        if day_n == 1:
            position_note = (
                f"This is day 1 — account for arriving via the researched transport option "
                f"({p.transport_suggestions}) at the {p.arrival_time} arrival time preference."
            )
        elif day_n == total_days:
            position_note = "This is the last day — keep the pace relaxed and account for departure logistics."

        places_note = self._places_note(candidates, used_names)

        prompt = f"""
        Build ONLY day {day_n} of a {total_days}-day itinerary for {p.destination}.
        Budget: {p.budget} INR for the whole trip. Month: {p.month}. Origin: {p.origin}.
        Hotel tier: {p.hotel_type}. Food preferences: {p.food_preferences}.
        {position_note}
        {places_note}

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

    def _places_note(self, candidates: list, used_names: set) -> str:
        if not candidates:
            return ""
        available = [c for c in candidates if c["name"] not in used_names]
        pool = available or candidates  # allow reuse once the whole list has been covered
        lines = "\n".join(
            f"- {c['name']}"
            + (f" ({c['rating']}★)" if c.get("rating") else "")
            + (f" — {c['address']}" if c.get("address") else "")
            for c in pool[:12] if c.get("name")
        )
        return f"Real places researched for this destination (prefer these by exact name):\n{lines}"

    def _backfill_day(self, day: dict) -> dict:
        """Deterministic safety net: LLMs don't reliably fill every optional field
        even when told to. Never show a blank cost/crowd/transport chip in the UI —
        fill anything missing with a clearly-labeled, sensible default instead."""
        segments = day.get("segments", [])
        for i, seg in enumerate(segments):
            if seg.get("cost") is None:
                seg["cost"] = 0
            if not seg.get("crowd") or seg["crowd"] not in CROWD_LEVELS:
                seg["crowd"] = "moderate"
            if not seg.get("transport"):
                seg["transport"] = "Return to hotel" if i == len(segments) - 1 else "Walk"
        return day

    def _fetch_place_candidates(self, destination: str, food_preferences: list) -> list:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key or not destination:
            return []
        try:
            attractions = google_maps.text_search_places(
                f"top tourist attractions in {destination}", api_key, max_results=8)
            cuisine = " ".join((food_preferences or [])).replace("_", " ").strip()
            query = f"best {cuisine} restaurants in {destination}" if cuisine else f"best restaurants in {destination}"
            restaurants = google_maps.text_search_places(query, api_key, max_results=8)
            return attractions + restaurants
        except Exception:
            return []

    def _best_candidate_match(self, title: str, candidates: list):
        best, best_score = None, 0.0
        for c in candidates:
            if not c.get("name"):
                continue
            score = difflib.SequenceMatcher(None, title.lower(), c["name"].lower()).ratio()
            if score > best_score:
                best, best_score = c, score
        return best if best_score >= PLACE_MATCH_THRESHOLD else None

    def _ground_day_with_real_places(self, day: dict, candidates: list, used_names: set) -> dict:
        for seg in day.get("segments", []):
            match = self._best_candidate_match(seg.get("title", ""), candidates)
            if not match:
                continue
            seg["place_id"] = match.get("place_id")
            seg["address"] = match.get("address")
            seg["rating"] = match.get("rating")
            seg["photo_name"] = match.get("photo_name")
            seg["lat"] = match.get("lat")
            seg["lng"] = match.get("lng")
            if match.get("review_snippet"):
                seg.setdefault("evidence", []).append(["web", match["review_snippet"]])
            used_names.add(match["name"])
        return day

    def _apply_real_distances(self, plan: dict) -> dict:
        """Replace the LLM's guessed walking distance/transport text with a real
        computed value wherever two consecutive segments both got grounded to a
        real place with coordinates."""
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return plan
        for day in plan.get("itinerary", []):
            segments = day.get("segments", [])
            for i in range(len(segments) - 1):
                a, b = segments[i], segments[i + 1]
                if a.get("lat") is None or b.get("lat") is None:
                    continue
                try:
                    route = google_maps.compute_walking_route(a["lat"], a["lng"], b["lat"], b["lng"], api_key)
                except Exception:
                    route = None
                if route:
                    a["walk"] = route["distance_km"]
                    a["transport"] = f"Walk ~{route['duration_min']} min ({route['distance_km']:.1f} km)"
        return plan
