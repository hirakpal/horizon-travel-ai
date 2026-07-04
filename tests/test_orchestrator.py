# tests/test_orchestrator.py
import os
from unittest.mock import patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from src.orchestrator import RootOrchestrator
from src.models.state import TravelState
from src.models.preferences import TravelPreferences


def _orchestrator():
    return RootOrchestrator()


def _no_op_extractor(orchestrator):
    """Patch the extractor so tests exercise the deterministic stage logic,
    not a real LLM call."""
    return patch.object(orchestrator.extractor, "run", return_value={"updated_preferences": None})


def test_checkin_advice_per_transport_mode():
    orchestrator = _orchestrator()
    assert "2h buffer" in orchestrator._checkin_advice("flight", "09:30 AM")
    assert "07:30 AM" in orchestrator._checkin_advice("flight", "09:30 AM")
    assert "the airport" in orchestrator._checkin_advice("flight", "09:30 AM")

    assert "45 min buffer" in orchestrator._checkin_advice("train", "08:00 PM")
    assert "07:15 PM" in orchestrator._checkin_advice("train", "08:00 PM")
    assert "the railway station" in orchestrator._checkin_advice("train", "08:00 PM")

    assert "20 min buffer" in orchestrator._checkin_advice("bus", "06:00 AM")
    assert "the bus terminus" in orchestrator._checkin_advice("bus", "06:00 AM")

    assert "90 min buffer" in orchestrator._checkin_advice("ship", "10:00 AM")
    assert "08:30 AM" in orchestrator._checkin_advice("ship", "10:00 AM")
    assert "the port" in orchestrator._checkin_advice("ship", "10:00 AM")


def test_checkin_advice_handles_unparseable_or_unknown_mode_gracefully():
    orchestrator = _orchestrator()
    assert orchestrator._checkin_advice("car", "09:00 AM") == ""
    assert orchestrator._checkin_advice("flight", "not a time") == ""
    assert orchestrator._checkin_advice("flight", "") == ""


def test_orchestration_loop():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    assert state.active_agent == "Concierge"


def test_budget_without_destination_asks_for_destination_not_dead_end_menu():
    """Regression test: ConciergeAgent used to show a 'pick an experience tier' menu
    whenever budget was set but destination wasn't, with no code anywhere to process
    the user's reply to it — every subsequent turn re-triggered the same menu,
    producing an infinite loop the user could never escape (observed when the
    extractor captured budget from a message but missed the destination in it)."""
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.budget = 15000

    with patch.object(orchestrator.extractor, "run", return_value={"updated_preferences": None}), \
         patch.object(orchestrator.concierge, "llm") as mock_llm:
        # Exercise the real ConciergeAgent.run() logic (not a mocked reply) so this
        # test actually fails if the dead-end tier-menu branch comes back.
        mock_llm.invoke.return_value.content = "Could you tell me your destination?"
        response = orchestrator.process_turn(state, "Comfort explorer")

    assert "experience tier" not in response.lower()
    assert "budget backpacker" not in response.lower()
    mock_llm.invoke.assert_called_once()


def test_missing_basic_info_prompts_for_it():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    with _no_op_extractor(orchestrator), \
         patch.object(orchestrator.concierge, "run", side_effect=Exception("no llm")):
        response = orchestrator.process_turn(state, "hi there")
    assert state.preferences.planning_stage == "basic_info"
    assert "origin" in response and "destination" in response


def test_planning_stage_updates_after_extractor_fills_in_last_basic_field():
    """Regression test: the extractor replaces state.preferences with a brand new
    object rather than mutating it in place. process_turn must read the final
    planning_stage off the live state.preferences, not a pre-extraction local
    variable — otherwise the stage chip stays stuck on "basic_info" forever even
    once all the basic fields are actually filled in."""
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.destination = "North Goa"
    state.preferences.days = 5
    state.preferences.budget = 18000

    filled_prefs = TravelPreferences(
        destination="North Goa", days=5, budget=18000, origin="Bangalore", month="July")

    with patch.object(orchestrator.extractor, "run",
                       return_value={"updated_preferences": filled_prefs}), \
         patch.object(orchestrator.concierge, "run",
                       return_value={"reply": "All set, moving on!"}):
        orchestrator.process_turn(state, "Bangalore")

    assert state.preferences.origin == "Bangalore"
    assert state.preferences.planning_stage == "transport"


def test_full_stage_progression_to_ready_to_plan():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 100000

    with _no_op_extractor(orchestrator), \
         patch.object(orchestrator.transport, "run", side_effect=Exception("no llm")), \
         patch.object(orchestrator.transport, "run_return", side_effect=Exception("no llm")):
        r1 = orchestrator.process_turn(state, "early morning please")
        assert state.preferences.arrival_time == "early_morning"
        assert state.transport_options  # fallback mock options populated for the UI cards
        assert "pick one" in r1.lower()

        # User picks a transport option by naming its mode (matches a fallback option)
        r1b = orchestrator.process_turn(state, "flight")
        assert state.preferences.transport_suggestions is not None
        assert state.preferences.transport_cost is not None
        assert "return" in r1b.lower()

        r1c = orchestrator.process_turn(state, "evening")
        assert state.preferences.departure_time == "evening"
        assert state.transport_options
        assert "pick one" in r1c.lower()

        r1d = orchestrator.process_turn(state, "train")
        assert state.preferences.return_transport_suggestions is not None
        assert state.preferences.return_transport_cost is not None
        assert "hotel" in r1d.lower()

        r2 = orchestrator.process_turn(state, "a luxury hotel")
        assert state.preferences.hotel_type == "luxury"
        assert "food" in r2.lower()

        r3 = orchestrator.process_turn(state, "vegetarian")
        assert state.preferences.food_preferences == ["vegetarian"]
        assert state.preferences.planning_stage == "ready_to_plan"
        assert "build your itinerary" in r3.lower()


def test_arrival_time_keyword_match_skips_extractor_call():
    """A recognized answer (e.g. 'early morning') must not trigger an extra,
    redundant LLM extraction call in the same turn — only the transport search
    LLM call should fire. Two sequential LLM round trips on this turn was the
    cause of the reported "chat closes after entering arrival time" hang."""
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 100000

    with patch.object(orchestrator.extractor, "run") as mock_extract, \
         patch.object(orchestrator.transport, "run", side_effect=Exception("no llm")):
        orchestrator.process_turn(state, "early morning please")

    mock_extract.assert_not_called()
    assert state.preferences.arrival_time == "early_morning"


def test_ready_to_plan_budget_alert():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 10
    state.preferences.budget = 1000
    state.preferences.arrival_time = "morning"
    state.preferences.transport_suggestions = "x"
    state.preferences.departure_time = "evening"
    state.preferences.return_transport_suggestions = "x"
    state.preferences.hotel_type = "luxury"
    state.preferences.food_preferences = ["vegetarian"]

    with _no_op_extractor(orchestrator):
        response = orchestrator.process_turn(state, "tell me more")

    assert "Budget Alert" in response


def test_affirmative_confirmation_triggers_itinerary_build():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 2
    state.preferences.budget = 100000
    state.preferences.arrival_time = "morning"
    state.preferences.transport_suggestions = "x"
    state.preferences.departure_time = "evening"
    state.preferences.return_transport_suggestions = "x"
    state.preferences.hotel_type = "mid_range"
    state.preferences.food_preferences = ["vegetarian"]

    fake_itinerary = {
        "itinerary": [
            {"n": 1, "date": "Day 1", "theme": "Arrival", "weather": None, "walk": 1.0,
             "segments": [
                 {"time": "09:00", "dur": 60, "icon": "📍", "title": "Beach walk",
                  "desc": "A walk on the beach", "conf": 85, "evidence": [["dna", "you like beaches"]],
                  "alt": None, "walk": 1.0, "cost": 500, "crowd": "low", "transport": None},
             ]},
        ]
    }

    with _no_op_extractor(orchestrator), \
         patch.object(orchestrator.architect, "run", return_value={"itinerary": fake_itinerary}), \
         patch.object(orchestrator.learner, "run", return_value={"dna_insights": []}):
        response = orchestrator.process_turn(state, "yes, go ahead")

    assert state.itinerary_data is not None
    assert state.preferences.planning_stage == "complete"
    assert "itinerary" in response.lower()


def test_architect_failure_keeps_user_at_ready_to_plan():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 2
    state.preferences.budget = 100000
    state.preferences.arrival_time = "morning"
    state.preferences.transport_suggestions = "x"
    state.preferences.departure_time = "evening"
    state.preferences.return_transport_suggestions = "x"
    state.preferences.hotel_type = "mid_range"
    state.preferences.food_preferences = ["vegetarian"]

    with _no_op_extractor(orchestrator), \
         patch.object(orchestrator.architect, "run", side_effect=Exception("no llm")):
        response = orchestrator.process_turn(state, "yes")

    assert state.itinerary_data is None
    assert state.preferences.planning_stage == "ready_to_plan"
    assert "issue" in response.lower()


def test_replan_resets_state():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 50000
    state.itinerary_data = {"itinerary": []}

    response = orchestrator.process_turn(state, "let's replan this trip")

    assert state.preferences.destination is None
    assert state.itinerary_data is None
    assert state.preferences.planning_stage == "basic_info"
    assert "start fresh" in response.lower()


# ============================================================================
# Interactive card selection (transport / hotel / food) — the UI calls these
# methods directly on a button click, bypassing process_turn's text parsing.
# ============================================================================
def test_select_transport_option_sets_cost_and_advances_to_departure_time_prompt():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 50000
    state.preferences.arrival_time = "morning"
    state.transport_options = [
        {"mode": "flight", "price": 6000, "duration": "2h", "departure": "09:00 AM",
         "arrival": "11:00 AM", "why": "fastest"},
    ]

    response = orchestrator.select_transport_option(state, state.transport_options[0])

    assert state.preferences.transport_cost == 6000
    assert state.preferences.transport_suggestions is not None
    assert state.transport_options == []  # cards cleared once a choice is made
    assert "return" in response.lower()
    assert state.preferences.planning_stage == "transport"
    # "Smart" check-in buffer advice: a flight needs a 2h buffer before its
    # stated departure time.
    assert state.preferences.checkin_advice is not None
    assert "07:00 AM" in state.preferences.checkin_advice
    assert "the airport" in state.preferences.checkin_advice
    # The selection is recorded in the transcript like a normal turn
    assert any("flight" in m["content"].lower() for m in state.messages if m["role"] == "user")


def test_select_return_transport_option_sets_cost_and_advances_to_hotel_prompt():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 50000
    state.preferences.arrival_time = "morning"
    state.preferences.transport_suggestions = "Flight — ₹6,000"
    state.preferences.transport_cost = 6000
    state.preferences.departure_time = "evening"
    state.transport_options = [
        {"mode": "train", "price": 1500, "duration": "10h", "departure": "08:00 PM",
         "arrival": "06:00 AM", "why": "overnight and cheap"},
    ]

    response = orchestrator.select_return_transport_option(state, state.transport_options[0])

    assert state.preferences.return_transport_cost == 1500
    assert state.preferences.return_transport_suggestions is not None
    assert state.transport_options == []  # cards cleared once a choice is made
    assert "hotel" in response.lower()
    assert state.preferences.planning_stage == "hotel_food"
    # A train needs a 45-minute buffer before its stated departure time.
    assert state.preferences.return_checkin_advice is not None
    assert "07:15 PM" in state.preferences.return_checkin_advice
    assert "the railway station" in state.preferences.return_checkin_advice
    assert any("train" in m["content"].lower() for m in state.messages if m["role"] == "user")


def test_select_hotel_tier_sets_nightly_rate_and_advances_to_food_prompt():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 50000
    state.preferences.arrival_time = "morning"
    state.preferences.transport_suggestions = "Flight — ₹6,000"
    state.preferences.transport_cost = 6000

    response = orchestrator.select_hotel_tier(state, "luxury")

    assert state.preferences.hotel_type == "luxury"
    assert state.preferences.hotel_cost_per_night == 9000
    assert "food" in response.lower()


def test_typed_no_hotel_phrasing_is_recognized_and_budgets_zero():
    """Regression test: a user who says they don't need a hotel (staying with
    family, already booked elsewhere, etc.) used to get stuck being re-asked
    the hotel question forever, because HOTEL_TYPE_CHOICES had no entry for
    "no hotel" and the LLM extractor's free-form guess (if any) never matched
    the deterministic choices either."""
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Kolkata"
    state.preferences.destination = "Patna"
    state.preferences.days = 5
    state.preferences.budget = 50000
    state.preferences.arrival_time = "morning"
    state.preferences.transport_suggestions = "Train — ₹800"
    state.preferences.departure_time = "evening"
    state.preferences.return_transport_suggestions = "Train — ₹800"

    with _no_op_extractor(orchestrator):
        response = orchestrator.process_turn(state, "I don't need a hotel, staying with family")

    assert state.preferences.hotel_type == "no_hotel"
    assert state.preferences.hotel_cost_per_night == 0
    assert "food" in response.lower()
    assert "hotel" not in response.lower() or "no hotel" in response.lower()


def test_no_hotel_phrasing_variety_including_the_exact_reported_wording():
    """Regression test for a live production report: the user typed 'i dont
    need hotel in Kolkata in return' (no "a"/"any" article) and got endlessly
    re-asked the hotel question, because the original keyword list only
    matched phrasings with an article ("dont need a hotel")."""
    phrasings = [
        "i dont need hotel in Kolkata in return",  # exact reported phrasing
        "I don't need a hotel",
        "we won't need hotel this time",
        "no need for hotel, staying with relatives",
        "no need of a hotel",
        "don't require hotel",
    ]
    for phrase in phrasings:
        orchestrator = _orchestrator()
        state = TravelState(session_id="test")
        state.preferences.origin = "Kolkata"
        state.preferences.destination = "Patna"
        state.preferences.days = 5
        state.preferences.budget = 50000
        state.preferences.arrival_time = "morning"
        state.preferences.transport_suggestions = "Train — ₹800"
        state.preferences.departure_time = "evening"
        state.preferences.return_transport_suggestions = "Train — ₹800"

        with _no_op_extractor(orchestrator):
            response = orchestrator.process_turn(state, phrase)

        assert state.preferences.hotel_type == "no_hotel", f"failed for phrasing: {phrase!r}"
        assert state.preferences.hotel_cost_per_night == 0, f"failed for phrasing: {phrase!r}"
        assert "food" in response.lower(), f"failed for phrasing: {phrase!r}"


def test_select_hotel_tier_no_hotel_sets_zero_cost_and_correct_budget():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.days = 5
    state.preferences.budget = 50000
    state.preferences.transport_cost = 800
    state.preferences.return_transport_cost = 800

    response = orchestrator.select_hotel_tier(state, "no_hotel")

    assert state.preferences.hotel_type == "no_hotel"
    assert state.preferences.hotel_cost_per_night == 0
    assert "no hotel needed" in response.lower()
    breakdown = orchestrator.budget_breakdown(state)
    assert breakdown["hotel_total"] == 0
    assert breakdown["grand_total"] == 800 + 800 + 800 * 5


def test_select_food_preferences_advances_to_ready_to_plan_summary():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 50000
    state.preferences.arrival_time = "morning"
    state.preferences.transport_suggestions = "Flight — ₹6,000"
    state.preferences.transport_cost = 6000
    state.preferences.departure_time = "evening"
    state.preferences.return_transport_suggestions = "Train — ₹1,500"
    state.preferences.return_transport_cost = 1500
    state.preferences.hotel_type = "mid_range"
    state.preferences.hotel_cost_per_night = 5000

    response = orchestrator.select_food_preferences(state, ["vegetarian", "vegan"])

    assert state.preferences.food_preferences == ["vegetarian", "vegan"]
    assert state.preferences.planning_stage == "ready_to_plan"
    assert "shall i go ahead" in response.lower()


def test_budget_breakdown_uses_actual_selections_not_flat_heuristic():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.days = 5
    state.preferences.budget = 15000
    state.preferences.transport_cost = 6500
    state.preferences.hotel_cost_per_night = 2500  # budget tier

    breakdown = orchestrator.budget_breakdown(state)

    assert breakdown["transport"] == 6500
    assert breakdown["hotel_total"] == 2500 * 5
    assert breakdown["grand_total"] == 6500 + 2500 * 5 + 800 * 5
    assert breakdown["over_budget"] is True


def test_budget_breakdown_includes_return_transport_cost():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.days = 5
    state.preferences.budget = 25000
    state.preferences.transport_cost = 6500
    state.preferences.return_transport_cost = 4000
    state.preferences.hotel_cost_per_night = 2500

    breakdown = orchestrator.budget_breakdown(state)

    assert breakdown["transport"] == 6500 + 4000
    assert breakdown["grand_total"] == 6500 + 4000 + 2500 * 5 + 800 * 5


def test_budget_breakdown_defaults_to_zero_before_any_selection():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.days = 5
    state.preferences.budget = 15000

    breakdown = orchestrator.budget_breakdown(state)

    assert breakdown["transport"] == 0
    assert breakdown["hotel_total"] == 0
    assert breakdown["over_budget"] is False


def test_typing_transport_mode_name_matches_pending_option_cards():
    """A user who types instead of clicking should get the same result as clicking,
    as long as their text names one of the currently-offered options."""
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 50000
    state.preferences.arrival_time = "morning"
    state.transport_options = [
        {"mode": "train", "price": 1500, "duration": "10h", "departure": "20:00",
         "arrival": "06:00", "why": "overnight and cheap"},
    ]

    response = orchestrator.process_turn(state, "I'll take the train")

    assert state.preferences.transport_cost == 1500
    assert "return" in response.lower()
