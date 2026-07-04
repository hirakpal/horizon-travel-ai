# src/orchestrator.py

import json
import re

from src.models.state import TravelState
from src.models.preferences import TravelPreferences
from src.agents.concierge import ConciergeAgent
from src.agents.extractor import PreferenceExtractionAgent
from src.agents.architect import ItineraryArchitectAgent
from src.agents.dna_learner import DNALearnerAgent
from src.agents.transport_suggestions import TransportSuggestionsAgent

BASIC_FIELDS = ["origin", "destination", "days", "budget"]

ARRIVAL_TIME_CHOICES = [
    ("late_evening", ("late evening", "late-evening")),
    ("early_morning", ("early morning", "early-morning", "dawn", "sunrise", "before sunrise")),
    ("morning", ("morning",)),
    ("afternoon", ("afternoon", "noon", "midday")),
    ("evening", ("evening", "dusk", "sunset")),
    ("night", ("night", "midnight", "late night")),
]

HOTEL_TYPE_CHOICES = [
    ("luxury", ("luxury", "5 star", "5-star", "five star", "five-star")),
    ("boutique", ("boutique", "design hotel", "unique stay")),
    ("budget", ("budget", "hostel", "cheap", "backpacker")),
    ("mid_range", ("mid range", "mid-range", "midrange", "3 star", "3-star", "moderate", "comfortable")),
]

FOOD_PREF_CHOICES = [
    ("vegan", ("vegan",)),
    ("vegetarian", ("vegetarian", "veggie", "veg only", "pure veg")),
    ("non_veg", ("non-veg", "non veg", "nonvegetarian", "non-vegetarian", "meat", "chicken", "seafood", "fish")),
    ("no_restrictions", ("no restriction", "anything", "no preference", "eat everything", "open to all", "all cuisines")),
]

AFFIRMATIVE_PATTERNS = (
    "yes", "yeah", "yep", "yup", "sure", "go ahead", "goahead", "sounds good",
    "let's do it", "lets do it", "build it", "build the itinerary", "confirm",
    "i'm ready", "im ready", "ready", "ok", "okay", "please proceed", "proceed",
    "let's go", "lets go", "do it",
)

REPLAN_PATTERNS = (
    "replan", "restart", "start over", "start fresh", "reset", "new trip",
    "begin again", "plan a new trip", "start again",
)


def _match_choice(text: str, choices):
    lowered = text.lower()
    for key, keywords in choices:
        if any(kw in lowered for kw in keywords):
            return key
    return None


def _match_food_preferences(text: str) -> list:
    lowered = text.lower()
    return [key for key, keywords in FOOD_PREF_CHOICES if any(kw in lowered for kw in keywords)]


def _is_replan_request(text: str) -> bool:
    lowered = text.lower().strip()
    return any(p in lowered for p in REPLAN_PATTERNS)


def _is_affirmative(text: str) -> bool:
    lowered = f" {text.lower().strip()} "
    return any(lowered.strip() == p or lowered.strip().startswith(p) or f" {p} " in lowered
               for p in AFFIRMATIVE_PATTERNS)


class RootOrchestrator:
    def __init__(self):
        self.concierge = ConciergeAgent()
        self.extractor = PreferenceExtractionAgent()
        self.architect = ItineraryArchitectAgent()
        self.learner = DNALearnerAgent()
        self.transport = TransportSuggestionsAgent()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _missing_basic_fields(self, prefs: TravelPreferences) -> list:
        return [f for f in BASIC_FIELDS if not getattr(prefs, f)]

    def _current_stage(self, p: TravelPreferences, has_itinerary: bool) -> str:
        if self._missing_basic_fields(p):
            return "basic_info"
        if not p.arrival_time or not p.transport_suggestions:
            return "transport"
        if not p.hotel_type or not p.food_preferences:
            return "hotel_food"
        if not has_itinerary:
            return "ready_to_plan"
        return "complete"

    def estimate_trip_cost(self, destination: str, days: int, hotel_type: str = None) -> int:
        """Rough per-day cost heuristic in INR, used only as an advisory budget check."""
        per_day = {"budget": 2500, "mid_range": 5000, "luxury": 9000, "boutique": 7000}.get(hotel_type, 4000)
        transport_buffer = 6000
        return per_day * (days or 0) + transport_buffer

    def reset_state(self, state: TravelState) -> None:
        state.preferences = TravelPreferences()
        state.itinerary_data = None
        state.active_agent = "Concierge"
        state.dna_insights = []
        state.messages = []

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def process_turn(self, state: TravelState, user_input: str) -> str:
        # 0. "replan" / "start fresh" always takes priority over everything else
        if _is_replan_request(user_input):
            self.reset_state(state)
            response = ("No problem — I've cleared your current plan. Let's start fresh! "
                        "Where are you traveling from, where would you like to go, how many days, "
                        "and what's your budget?")
            state.messages.append({"role": "user", "content": user_input})
            state.messages.append({"role": "assistant", "content": response})
            return response

        # 1. Extraction: best-effort update of preferences from free-text input
        try:
            extraction_result = self.extractor.run(state, user_input)
            updated_prefs = extraction_result.get("updated_preferences")
            if updated_prefs is not None:
                updated_data = state.preferences.model_dump()
                new_data = updated_prefs.model_dump()
                updated_data.update({k: v for k, v in new_data.items() if v not in (None, [], {})})
                state.preferences = TravelPreferences(**updated_data)
        except Exception:
            pass  # deterministic stage matchers below still cover the flow

        state.messages.append({"role": "user", "content": user_input})
        p = state.preferences

        # 2. Stage-driven conversation flow. Handlers may chain straight into the
        # next question within the same turn, so the stage is recomputed from the
        # final state afterwards rather than trusted from this initial dispatch.
        stage = self._current_stage(p, bool(state.itinerary_data))

        if stage == "basic_info":
            state.active_agent = "Concierge"
            response = self._handle_basic_info(state, user_input)
        elif stage == "transport":
            if not p.arrival_time:
                state.active_agent = "Concierge"
                response = self._handle_arrival_time(state, user_input)
            else:
                state.active_agent = "Transport Suggestions"
                response = self._handle_transport_suggestions(state, user_input)
        elif stage == "hotel_food":
            state.active_agent = "Concierge"
            if not p.hotel_type:
                response = self._handle_hotel_type(state, user_input)
            else:
                response = self._handle_food_preferences(state, user_input)
        elif stage == "ready_to_plan":
            state.active_agent = "Concierge"
            response = self._handle_ready_to_plan(state, user_input)
        else:
            response = ("Your itinerary is ready! Head over to the **Itinerary** tab to view it, "
                        "or type **replan** if you'd like to start planning a new trip.")

        p.planning_stage = self._current_stage(p, bool(state.itinerary_data))

        clean_response = response.replace('\\n', '\n')
        state.messages.append({"role": "assistant", "content": clean_response})
        return clean_response

    # ------------------------------------------------------------------
    # Stage handlers
    # ------------------------------------------------------------------
    def _handle_basic_info(self, state: TravelState, user_input: str) -> str:
        try:
            concierge_result = self.concierge.run(state, user_input)
            if isinstance(concierge_result, dict):
                return concierge_result.get("reply", str(concierge_result))
            return str(concierge_result)
        except Exception:
            missing = self._missing_basic_fields(state.preferences)
            return ("To get started, could you tell me your " +
                    ", ".join(missing) + "?")

    def _handle_arrival_time(self, state: TravelState, user_input: str) -> str:
        matched = _match_choice(user_input, ARRIVAL_TIME_CHOICES)
        if matched:
            state.preferences.arrival_time = matched
            return self._handle_transport_suggestions(state, user_input)

        p = state.preferences
        return (f"Great, I have your trip basics for **{p.destination}** "
                f"({p.days} days, budget {p.budget} INR from {p.origin}). "
                f"When do you plan to reach {p.destination}? Choose one: **early morning, "
                f"morning, afternoon, evening, late evening, or night.**")

    def _handle_transport_suggestions(self, state: TravelState, user_input: str) -> str:
        suggestions_text = None
        try:
            result = self.transport.run(state, user_input)
            suggestions_text = result.get("suggestions")
        except Exception:
            suggestions_text = None

        if not suggestions_text:
            mock = self.transport.get_mock_suggestions(
                state.preferences.origin, state.preferences.destination, state.preferences.arrival_time)
            suggestions_text = "\n".join(
                f"- {mode.title()}: {info['price']}, {info['duration']} ({info['availability']})"
                for mode, info in mock.items())

        state.preferences.transport_suggestions = {"raw": suggestions_text}

        return (f"Based on your **{state.preferences.arrival_time.replace('_', ' ')}** arrival "
                f"preference, here's what I found for {state.preferences.origin} → "
                f"{state.preferences.destination}:\n\n{suggestions_text}\n\n"
                "Now, what type of hotel do you prefer? **Budget, Mid-range, Luxury, or Boutique.**")

    def _handle_hotel_type(self, state: TravelState, user_input: str) -> str:
        matched = _match_choice(user_input, HOTEL_TYPE_CHOICES)
        if matched:
            state.preferences.hotel_type = matched
            return self._handle_food_preferences(state, user_input, prompt_only=True)

        return "What type of hotel do you prefer? **Budget, Mid-range, Luxury, or Boutique.**"

    def _handle_food_preferences(self, state: TravelState, user_input: str, prompt_only: bool = False) -> str:
        if not prompt_only:
            matched = _match_food_preferences(user_input)
            if matched:
                state.preferences.food_preferences = matched
                return self._handle_ready_to_plan(state, user_input, summary_only=True)

        return ("What are your food preferences? **Vegetarian, Vegan, Non-vegetarian, or No "
                "restrictions?** Feel free to mention favorite cuisines too.")

    def _handle_ready_to_plan(self, state: TravelState, user_input: str, summary_only: bool = False) -> str:
        p = state.preferences

        if not summary_only and _is_affirmative(user_input):
            return self._build_itinerary(state, user_input)

        estimated_cost = self.estimate_trip_cost(p.destination, p.days, p.hotel_type)
        warning = ""
        if p.budget and estimated_cost > p.budget:
            warning = (f"\n\n⚠️ Budget Alert: This trip is roughly estimated at {estimated_cost} INR, "
                       f"which is above your {p.budget} INR budget. You can still proceed, or tell me "
                       "to adjust the budget, days, or hotel type.")

        return (f"Here's what I have so far:\n\n"
                f"- **From:** {p.origin} → **To:** {p.destination}\n"
                f"- **Days:** {p.days}  ·  **Budget:** {p.budget} INR\n"
                f"- **Arrival:** {p.arrival_time.replace('_', ' ') if p.arrival_time else '—'}\n"
                f"- **Hotel:** {p.hotel_type.replace('_', ' ') if p.hotel_type else '—'}\n"
                f"- **Food:** {', '.join(x.replace('_', ' ') for x in p.food_preferences) if p.food_preferences else '—'}"
                f"{warning}\n\nShall I go ahead and build your itinerary now?")

    def _build_itinerary(self, state: TravelState, user_input: str) -> str:
        state.active_agent = "Architect"
        try:
            architect_result = self.architect.run(state, user_input)
            match = re.search(r'\{.*\}', architect_result['itinerary'], re.DOTALL)
            if match:
                state.itinerary_data = json.loads(match.group(0))
                self.learner.run(state, user_input, plan=state.itinerary_data)
                return ("I've built the perfect itinerary for your trip! Please head over to the "
                        "**Itinerary** tab to view your day-by-day plan.")
            return "I've finalized your travel plan. Please check the Itinerary tab to view it."
        except Exception:
            return ("I ran into an issue while building your itinerary. Please try again in a "
                    "moment, or let me know if you'd like to adjust any details first.")
