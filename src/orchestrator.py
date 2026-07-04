# src/orchestrator.py

from datetime import datetime, timedelta

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

NO_HOTEL_KEYWORDS = (
    "no hotel",
    "not need a hotel", "not need any hotel", "not need hotel",
    "don't need a hotel", "don't need any hotel", "don't need hotel",
    "dont need a hotel", "dont need any hotel", "dont need hotel",
    "do not need a hotel", "do not need any hotel", "do not need hotel",
    "won't need a hotel", "won't need any hotel", "won't need hotel",
    "wont need a hotel", "wont need any hotel", "wont need hotel",
    "will not need a hotel", "will not need any hotel", "will not need hotel",
    "no need for a hotel", "no need for any hotel", "no need for hotel",
    "no need of a hotel", "no need of any hotel", "no need of hotel",
    "don't require a hotel", "dont require a hotel", "don't require hotel", "dont require hotel",
    "no accommodation", "not staying in a hotel", "not staying at a hotel", "not staying in any hotel",
    "no stay needed", "already have a place", "already booked a place", "already have accommodation",
    "staying with family", "staying with friends", "skip the hotel", "skip hotel",
)

HOTEL_TYPE_CHOICES = [
    ("no_hotel", NO_HOTEL_KEYWORDS),
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

BUDGET_UNCERTAIN_PATTERNS = (
    "don't know the budget", "dont know the budget", "don't know my budget", "dont know my budget",
    "not sure about the budget", "not sure what the budget", "not sure of my budget",
    "no budget in mind", "no fixed budget", "flexible budget", "whatever it costs",
    "help me estimate", "estimate the budget", "estimate my budget", "suggest a budget",
    "don't have a budget", "dont have a budget", "no idea about the budget", "no idea on budget",
)

HOTEL_NIGHTLY_RATES = {"budget": 2500, "mid_range": 5000, "luxury": 9000, "boutique": 7000, "no_hotel": 0}
DEFAULT_NIGHTLY_RATE = 4000
DAILY_ACTIVITIES_BUFFER = 800

# Realistic recommended check-in buffer before a transport's departure time, and
# where that buffer applies — used to give "smart" arrive-by advice per mode.
CHECKIN_BUFFER_MINUTES = {"flight": 120, "train": 45, "bus": 20, "ship": 90}
CHECKIN_PLACE_LABELS = {"flight": "the airport", "train": "the railway station",
                         "bus": "the bus terminus", "ship": "the port"}


def _subtract_minutes(time_str: str, minutes: int):
    """Parse a 'HH:MM AM/PM' clock time and return the clock time `minutes`
    earlier, formatted the same way. Returns None if the string can't be parsed
    (never crash the chat flow over a formatting quirk in a generated string)."""
    try:
        dt = datetime.strptime(time_str.strip(), "%I:%M %p")
    except (ValueError, AttributeError):
        return None
    return (dt - timedelta(minutes=minutes)).strftime("%I:%M %p")


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


def _is_budget_uncertain(text: str) -> bool:
    lowered = text.lower()
    return any(p in lowered for p in BUDGET_UNCERTAIN_PATTERNS)


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
        missing = []
        for f in BASIC_FIELDS:
            if f == "budget" and prefs.budget_flexible:
                continue  # user explicitly doesn't have a number yet — we'll estimate one later
            if not getattr(prefs, f):
                missing.append(f)
        return missing

    def is_only_missing_budget(self, state: TravelState) -> bool:
        """Used by the UI to offer a 'not sure yet' button instead of forcing a
        typed number, once every other basic field is already known."""
        return self._missing_basic_fields(state.preferences) == ["budget"]

    def _current_stage(self, p: TravelPreferences, has_itinerary: bool) -> str:
        if self._missing_basic_fields(p):
            return "basic_info"
        if not p.arrival_time or not p.transport_suggestions:
            return "transport"
        if not p.departure_time or not p.return_transport_suggestions:
            return "transport"
        if not p.hotel_type or not p.food_preferences:
            return "hotel_food"
        if not has_itinerary:
            return "ready_to_plan"
        return "complete"

    def _checkin_advice(self, mode: str, departure: str) -> str:
        """'Smart' arrive-by advice for a chosen transport option: how much buffer
        to leave before its departure time to comfortably complete check-in, per
        realistic rules for that mode (flight/train/bus/ship)."""
        mode = (mode or "").lower()
        buffer_minutes = CHECKIN_BUFFER_MINUTES.get(mode)
        place = CHECKIN_PLACE_LABELS.get(mode)
        if not buffer_minutes or not place:
            return ""
        arrive_by = _subtract_minutes(departure, buffer_minutes)
        if not arrive_by:
            return ""
        buffer_label = (f"{buffer_minutes // 60}h" if buffer_minutes % 60 == 0
                         else f"{buffer_minutes} min")
        return (f"Departure is at {departure}, so plan to reach {place} by **{arrive_by}** "
                f"(about a {buffer_label} buffer for check-in).")

    def estimate_trip_cost(self, destination: str, days: int, hotel_type: str = None) -> int:
        """Rough per-day cost heuristic in INR, used as a fallback advisory budget check
        before the user has picked a specific transport option or hotel tier."""
        per_day = HOTEL_NIGHTLY_RATES.get(hotel_type, DEFAULT_NIGHTLY_RATE)
        transport_buffer = 6000
        return per_day * (days or 0) + transport_buffer

    def budget_breakdown(self, state: TravelState) -> dict:
        """Accurate budget estimate built from the traveler's actual selections
        (transport option + hotel tier) rather than a flat heuristic. Falls back to
        0 for any piece not yet chosen, so it's safe to call at any stage."""
        p = state.preferences
        transport = (p.transport_cost or 0) + (p.return_transport_cost or 0)
        hotel_total = (p.hotel_cost_per_night or 0) * (p.days or 0)
        activities_buffer = DAILY_ACTIVITIES_BUFFER * (p.days or 0)
        grand_total = transport + hotel_total + activities_buffer
        return {
            "transport": transport,
            "hotel_total": hotel_total,
            "activities_buffer": activities_buffer,
            "grand_total": grand_total,
            "budget": p.budget,
            "over_budget": bool(p.budget and grand_total > p.budget),
        }

    def reset_state(self, state: TravelState) -> None:
        state.preferences = TravelPreferences()
        state.itinerary_data = None
        state.active_agent = "Concierge"
        state.dna_insights = []
        state.messages = []
        state.transport_options = []

    def _extract_preferences(self, state: TravelState, user_input: str) -> None:
        """Best-effort free-text extraction. This is an LLM call — only invoke it
        where a deterministic keyword match can't reasonably cover the input, so a
        single turn never has to wait on more than one LLM round trip unless the
        itinerary itself is being built."""
        try:
            extraction_result = self.extractor.run(state, user_input)
            updated_prefs = extraction_result.get("updated_preferences")
            if updated_prefs is not None:
                updated_data = state.preferences.model_dump()
                new_data = updated_prefs.model_dump()
                updated_data.update({k: v for k, v in new_data.items() if v not in (None, [], {})})
                state.preferences = TravelPreferences(**updated_data)
        except Exception:
            pass  # deterministic stage matchers still cover the flow

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

        state.messages.append({"role": "user", "content": user_input})
        p = state.preferences

        # Stage-driven conversation flow. Handlers may chain straight into the
        # next question within the same turn, so the stage is recomputed from the
        # final state afterwards rather than trusted from this initial dispatch.
        stage = self._current_stage(p, bool(state.itinerary_data))

        if stage == "basic_info":
            # Free-form input (destination/budget/days/origin) genuinely needs the
            # extractor — there's no fixed vocabulary to keyword-match against.
            self._extract_preferences(state, user_input)
            state.active_agent = "Concierge"
            response = self._handle_basic_info(state, user_input)
        elif stage == "transport":
            if not p.arrival_time:
                state.active_agent = "Concierge"
                response = self._handle_arrival_time(state, user_input)
            elif not p.transport_suggestions:
                state.active_agent = "Transport Suggestions"
                response = self._handle_transport_suggestions(state, user_input)
            elif not p.departure_time:
                state.active_agent = "Concierge"
                response = self._handle_departure_time(state, user_input)
            else:
                state.active_agent = "Transport Suggestions"
                response = self._handle_return_transport_suggestions(state, user_input)
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

        # Re-read from state rather than the possibly-stale `p`: any branch above
        # may have called _extract_preferences, which replaces state.preferences
        # with a new object instead of mutating it in place.
        state.preferences.planning_stage = self._current_stage(state.preferences, bool(state.itinerary_data))

        clean_response = response.replace('\\n', '\n')
        state.messages.append({"role": "assistant", "content": clean_response})
        return clean_response

    # ------------------------------------------------------------------
    # Stage handlers
    # ------------------------------------------------------------------
    def mark_budget_flexible(self, state: TravelState) -> str:
        """Called by the UI when the user clicks 'not sure yet' instead of typing
        a budget figure. Also reachable via typed phrases like "I don't know the
        budget" (see _is_budget_uncertain), handled inline in _handle_basic_info."""
        state.preferences.budget_flexible = True
        state.messages.append({"role": "user", "content": "[No fixed budget — please estimate it for me]"})

        missing = self._missing_basic_fields(state.preferences)
        if not missing:
            response = "No problem! " + self._arrival_time_prompt(state)
        else:
            response = ("No problem, I'll estimate a budget once I know your transport and hotel "
                        "choices. Could you tell me your " + ", ".join(missing) + "?")
        state.preferences.planning_stage = self._current_stage(state.preferences, bool(state.itinerary_data))
        state.messages.append({"role": "assistant", "content": response})
        return response

    def _maybe_estimate_budget(self, state: TravelState) -> str:
        """Once both a transport option and a hotel tier are chosen, a traveler
        who didn't have a fixed budget gets one computed from their actual
        selections — never left guessing, and never blocked on a number they
        said upfront they didn't have."""
        p = state.preferences
        if not (p.budget_flexible and p.budget is None
                and p.transport_cost is not None and p.hotel_cost_per_night is not None):
            return ""
        estimate = self.budget_breakdown(state)["grand_total"]
        p.budget = estimate
        total_transport = (p.transport_cost or 0) + (p.return_transport_cost or 0)
        return (f"Since you didn't have a fixed budget, here's an estimate based on your choices — "
                f"transport ₹{total_transport:,} (round trip), hotel ₹{p.hotel_cost_per_night:,}/night for "
                f"{p.days} nights, plus a rough allowance for food & activities: "
                f"**≈₹{estimate:,} total**. I've set that as your working budget — just let me know "
                f"if you'd like to adjust it.\n\n")

    def _handle_basic_info(self, state: TravelState, user_input: str) -> str:
        if not state.preferences.budget and not state.preferences.budget_flexible \
                and _is_budget_uncertain(user_input):
            state.preferences.budget_flexible = True

        try:
            concierge_result = self.concierge.run(state, user_input)
            if isinstance(concierge_result, dict):
                reply = concierge_result.get("reply", str(concierge_result))
            else:
                reply = str(concierge_result)
        except Exception:
            missing = self._missing_basic_fields(state.preferences)
            if missing:
                return "To get started, could you tell me your " + ", ".join(missing) + "?"
            reply = "Got it, I have everything I need for the basics!"

        if not self._missing_basic_fields(state.preferences):
            # All basic fields just became available in this turn (whether the user
            # gave everything in one message or just supplied the last piece) — chain
            # straight into the next question instead of waiting on a filler reply.
            return reply + "\n\n" + self._arrival_time_prompt(state)
        return reply

    def _arrival_time_prompt(self, state: TravelState) -> str:
        p = state.preferences
        return (f"When do you plan to reach {p.destination}? Choose one: **early morning, "
                f"morning, afternoon, evening, late evening, or night.**")

    def _handle_arrival_time(self, state: TravelState, user_input: str) -> str:
        matched = _match_choice(user_input, ARRIVAL_TIME_CHOICES)
        if not matched:
            # Fall back to the LLM extractor only if the keyword match missed —
            # keeps the common case (user picks one of the offered options) to a
            # single LLM call for the whole turn (the transport search below).
            self._extract_preferences(state, user_input)
            if state.preferences.arrival_time:
                matched = _match_choice(state.preferences.arrival_time, ARRIVAL_TIME_CHOICES)

        if matched:
            state.preferences.arrival_time = matched
            return self._handle_transport_suggestions(state, user_input)

        return self._arrival_time_prompt(state)

    def _fetch_transport_options(self, state: TravelState) -> list:
        try:
            result = self.transport.run(state, "")
            options = result.get("options") or []
        except Exception:
            options = []
        if not options:
            options = self.transport.get_mock_suggestions(
                state.preferences.origin, state.preferences.destination, state.preferences.arrival_time)
        return options

    def _transport_options_prompt(self, state: TravelState) -> str:
        lines = [
            f"- **{o['mode'].title()}**: ₹{o['price']:,}, {o['duration']} "
            f"({o['departure']} → {o['arrival']}) — {o['why']}"
            for o in state.transport_options
        ]
        return (f"Based on your **{state.preferences.arrival_time.replace('_', ' ')}** arrival "
                f"preference, here's what I found for {state.preferences.origin} → "
                f"{state.preferences.destination}:\n\n" + "\n".join(lines) +
                "\n\nPick one of the options above, or just tell me which one you'd like.")

    def _match_transport_option(self, options: list, text: str):
        lowered = text.lower()
        for opt in options:
            if opt["mode"].lower() in lowered:
                return opt
        return None

    def _handle_transport_suggestions(self, state: TravelState, user_input: str) -> str:
        # Options already on the table from a previous turn — try to match the
        # user's text against them instead of re-fetching (avoids a wasted LLM call
        # and lets typing "the flight" work the same as clicking that card).
        if state.transport_options:
            matched = self._match_transport_option(state.transport_options, user_input)
            if matched:
                return self.select_transport_option(state, matched, record_message=False)
            return self._transport_options_prompt(state)

        state.transport_options = self._fetch_transport_options(state)
        return self._transport_options_prompt(state)

    def select_transport_option(self, state: TravelState, option: dict, record_message: bool = True) -> str:
        """Called directly by the UI when the user clicks a transport option card
        (or matched from typed text). Bypasses process_turn entirely since there's
        no free text to interpret — the choice is already fully structured."""
        state.preferences.transport_cost = option["price"]
        state.preferences.transport_suggestions = (
            f"{option['mode'].title()} — ₹{option['price']:,}, {option['duration']} "
            f"({option['departure']} → {option['arrival']})")
        state.transport_options = []

        if record_message:
            state.messages.append({
                "role": "user",
                "content": f"[Selected transport: {option['mode'].title()} — ₹{option['price']:,}]"
            })
        advice = self._checkin_advice(option["mode"], option["departure"])
        state.preferences.checkin_advice = advice
        advice_note = f"\n\n🕐 {advice}" if advice else ""
        response = "Great choice!" + advice_note + "\n\n" + self._departure_time_prompt(state)
        state.preferences.planning_stage = self._current_stage(state.preferences, bool(state.itinerary_data))
        state.messages.append({"role": "assistant", "content": response})
        return response

    def _departure_time_prompt(self, state: TravelState) -> str:
        p = state.preferences
        return (f"Now let's sort out your return journey. When would you like to depart "
                f"{p.destination} to head back to {p.origin}? Choose one: **early morning, "
                f"morning, afternoon, evening, late evening, or night.**")

    def _handle_departure_time(self, state: TravelState, user_input: str) -> str:
        matched = _match_choice(user_input, ARRIVAL_TIME_CHOICES)
        if not matched:
            # Fall back to the LLM extractor only if the keyword match missed —
            # same reasoning as _handle_arrival_time.
            self._extract_preferences(state, user_input)
            if state.preferences.departure_time:
                matched = _match_choice(state.preferences.departure_time, ARRIVAL_TIME_CHOICES)

        if matched:
            state.preferences.departure_time = matched
            return self._handle_return_transport_suggestions(state, user_input)

        return self._departure_time_prompt(state)

    def _fetch_return_transport_options(self, state: TravelState) -> list:
        try:
            result = self.transport.run_return(state, "")
            options = result.get("options") or []
        except Exception:
            options = []
        if not options:
            options = self.transport.get_mock_suggestions(
                state.preferences.destination, state.preferences.origin, state.preferences.departure_time)
        return options

    def _return_transport_options_prompt(self, state: TravelState) -> str:
        lines = [
            f"- **{o['mode'].title()}**: ₹{o['price']:,}, {o['duration']} "
            f"({o['departure']} → {o['arrival']}) — {o['why']}"
            for o in state.transport_options
        ]
        return (f"Based on your **{state.preferences.departure_time.replace('_', ' ')}** departure "
                f"preference, here's what I found for the return trip, {state.preferences.destination} → "
                f"{state.preferences.origin}:\n\n" + "\n".join(lines) +
                "\n\nPick one of the options above, or just tell me which one you'd like.")

    def _handle_return_transport_suggestions(self, state: TravelState, user_input: str) -> str:
        if state.transport_options:
            matched = self._match_transport_option(state.transport_options, user_input)
            if matched:
                return self.select_return_transport_option(state, matched, record_message=False)
            return self._return_transport_options_prompt(state)

        state.transport_options = self._fetch_return_transport_options(state)
        return self._return_transport_options_prompt(state)

    def select_return_transport_option(self, state: TravelState, option: dict, record_message: bool = True) -> str:
        """Called directly by the UI when the user clicks a return-transport option
        card (or matched from typed text) — mirrors select_transport_option."""
        state.preferences.return_transport_cost = option["price"]
        state.preferences.return_transport_suggestions = (
            f"{option['mode'].title()} — ₹{option['price']:,}, {option['duration']} "
            f"({option['departure']} → {option['arrival']})")
        state.transport_options = []

        if record_message:
            state.messages.append({
                "role": "user",
                "content": f"[Selected return transport: {option['mode'].title()} — ₹{option['price']:,}]"
            })
        advice = self._checkin_advice(option["mode"], option["departure"])
        state.preferences.return_checkin_advice = advice
        advice_note = f"\n\n🕐 {advice}" if advice else ""
        response = "Return journey booked!" + advice_note + "\n\n" + self._hotel_type_prompt(state)
        state.preferences.planning_stage = self._current_stage(state.preferences, bool(state.itinerary_data))
        state.messages.append({"role": "assistant", "content": response})
        return response

    def _hotel_type_prompt(self, state: TravelState = None) -> str:
        destination = state.preferences.destination if state and state.preferences.destination else "your destination"
        return (f"What type of hotel do you prefer in {destination}? **Budget, Mid-range, Luxury, or "
                f"Boutique** — or just let me know if you don't need a hotel (staying with family, "
                f"already booked elsewhere, etc.).")

    def _hotel_tier_note(self, tier: str) -> str:
        return "Got it — no hotel needed, I won't budget for one. " if tier == "no_hotel" else ""

    def _food_preferences_prompt(self) -> str:
        return ("What are your food preferences? **Vegetarian, Vegan, Non-vegetarian, or No "
                "restrictions?** Feel free to mention favorite cuisines too.")

    def _handle_hotel_type(self, state: TravelState, user_input: str) -> str:
        matched = _match_choice(user_input, HOTEL_TYPE_CHOICES)
        if not matched:
            self._extract_preferences(state, user_input)
            if state.preferences.hotel_type:
                matched = _match_choice(state.preferences.hotel_type, HOTEL_TYPE_CHOICES)

        if matched:
            state.preferences.hotel_type = matched
            state.preferences.hotel_cost_per_night = HOTEL_NIGHTLY_RATES.get(matched, DEFAULT_NIGHTLY_RATE)
            tier_note = self._hotel_tier_note(matched)
            budget_note = self._maybe_estimate_budget(state)
            return tier_note + budget_note + self._handle_food_preferences(state, user_input, prompt_only=True)

        return self._hotel_type_prompt(state)

    def select_hotel_tier(self, state: TravelState, tier: str) -> str:
        """Called directly by the UI when the user clicks a hotel tier card."""
        state.preferences.hotel_type = tier
        state.preferences.hotel_cost_per_night = HOTEL_NIGHTLY_RATES.get(tier, DEFAULT_NIGHTLY_RATE)

        label = tier.replace('_', ' ').title()
        state.messages.append({"role": "user", "content": f"[Selected hotel tier: {label}]"})
        tier_note = self._hotel_tier_note(tier)
        budget_note = self._maybe_estimate_budget(state)
        response = tier_note + budget_note + self._food_preferences_prompt()
        state.preferences.planning_stage = self._current_stage(state.preferences, bool(state.itinerary_data))
        state.messages.append({"role": "assistant", "content": response})
        return response

    def _handle_food_preferences(self, state: TravelState, user_input: str, prompt_only: bool = False) -> str:
        if not prompt_only:
            matched = _match_food_preferences(user_input)
            if not matched:
                self._extract_preferences(state, user_input)
                if state.preferences.food_preferences:
                    matched = state.preferences.food_preferences
            if matched:
                state.preferences.food_preferences = matched
                return self._handle_ready_to_plan(state, user_input, summary_only=True)

        return self._food_preferences_prompt()

    def select_food_preferences(self, state: TravelState, choices: list) -> str:
        """Called directly by the UI when the user confirms food preference chips."""
        state.preferences.food_preferences = choices

        label = ", ".join(c.replace('_', ' ').title() for c in choices) if choices else "No preference"
        state.messages.append({"role": "user", "content": f"[Selected food preference: {label}]"})
        response = self._handle_ready_to_plan(state, "", summary_only=True)
        state.preferences.planning_stage = self._current_stage(state.preferences, bool(state.itinerary_data))
        state.messages.append({"role": "assistant", "content": response})
        return response

    def _handle_ready_to_plan(self, state: TravelState, user_input: str, summary_only: bool = False) -> str:
        if not summary_only:
            if _is_affirmative(user_input):
                return self._build_itinerary(state, user_input)
            # Not an obvious yes — maybe the user is adjusting a detail. Extraction
            # here is a fallback, not the common path, so it doesn't slow down the
            # simple confirm-and-build turn.
            self._extract_preferences(state, user_input)

        # Re-read after the possible extraction above: _extract_preferences replaces
        # state.preferences with a new object rather than mutating in place.
        p = state.preferences
        if p.transport_cost is not None and p.hotel_cost_per_night is not None:
            # Accurate estimate built from the traveler's actual selections.
            estimated_cost = self.budget_breakdown(state)["grand_total"]
        else:
            # No selections yet (e.g. answered entirely via free text) — fall back
            # to the flat heuristic.
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
                f"- **Return departure:** {p.departure_time.replace('_', ' ') if p.departure_time else '—'}\n"
                f"- **Hotel:** {p.hotel_type.replace('_', ' ') if p.hotel_type else '—'}\n"
                f"- **Food:** {', '.join(x.replace('_', ' ') for x in p.food_preferences) if p.food_preferences else '—'}"
                f"{warning}\n\nShall I go ahead and build your itinerary now?")

    def _build_itinerary(self, state: TravelState, user_input: str) -> str:
        state.active_agent = "Architect"
        try:
            architect_result = self.architect.run(state, user_input)
            itinerary_data = architect_result.get("itinerary")
            if itinerary_data and itinerary_data.get("itinerary"):
                state.itinerary_data = itinerary_data
                self.learner.run(state, user_input, plan=state.itinerary_data)
                return ("I've built the perfect itinerary for your trip! Please head over to the "
                        "**Itinerary** tab to view your day-by-day plan.")
            return "I've finalized your travel plan. Please check the Itinerary tab to view it."
        except Exception:
            return ("I ran into an issue while building your itinerary. Please try again in a "
                    "moment, or let me know if you'd like to adjust any details first.")
