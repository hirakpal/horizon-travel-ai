# tests/test_orchestrator.py
import os
from unittest.mock import patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from src.orchestrator import RootOrchestrator
from src.models.state import TravelState


def _orchestrator():
    return RootOrchestrator()


def _no_op_extractor(orchestrator):
    """Patch the extractor so tests exercise the deterministic stage logic,
    not a real LLM call."""
    return patch.object(orchestrator.extractor, "run", return_value={"updated_preferences": None})


def test_orchestration_loop():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    assert state.active_agent == "Concierge"


def test_missing_basic_info_prompts_for_it():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    with _no_op_extractor(orchestrator), \
         patch.object(orchestrator.concierge, "run", side_effect=Exception("no llm")):
        response = orchestrator.process_turn(state, "hi there")
    assert state.preferences.planning_stage == "basic_info"
    assert "origin" in response and "destination" in response


def test_full_stage_progression_to_ready_to_plan():
    orchestrator = _orchestrator()
    state = TravelState(session_id="test")
    state.preferences.origin = "Mumbai"
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 100000

    with _no_op_extractor(orchestrator), \
         patch.object(orchestrator.transport, "run", side_effect=Exception("no llm")):
        r1 = orchestrator.process_turn(state, "early morning please")
        assert state.preferences.arrival_time == "early_morning"
        assert state.preferences.transport_suggestions is not None
        assert "hotel" in r1.lower()

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
    state.preferences.hotel_type = "mid_range"
    state.preferences.food_preferences = ["vegetarian"]

    fake_itinerary = (
        '{"itinerary": [{"day": 1, "title": "Arrival", "total_cost": 1000, "activities": []}], '
        '"total_budget": 100000, "total_spent": 50000}'
    )

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
