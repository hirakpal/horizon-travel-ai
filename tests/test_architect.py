# tests/test_architect.py
import os
from unittest.mock import patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from src.agents.architect import ItineraryArchitectAgent
from src.models.itinerary import ItineraryDay
from src.models.state import TravelState


def _fake_day(n, cost=None, crowd=None, transport=None, extra_segment=False):
    segments = [
        {"time": "09:00", "dur": 60, "icon": "🍳", "title": f"Breakfast day {n}",
         "desc": "Local breakfast", "conf": 90, "evidence": [["pref", "matches diet"]],
         "alt": None, "walk": 0.5, "cost": cost, "crowd": crowd, "transport": transport},
    ]
    if extra_segment:
        segments.append(
            {"time": "18:00", "dur": 90, "icon": "🌉", "title": f"Evening spot day {n}",
             "desc": "Evening walk", "conf": 85, "evidence": [["web", "popular spot"]],
             "alt": None, "walk": 1.0, "cost": 0, "crowd": "busy", "transport": None})
    return ItineraryDay(n=n, date=f"Day {n}", theme="Arrival" if n == 1 else "Exploring",
                        weather=None, walk=2.0, segments=segments)


def test_run_makes_one_llm_call_per_day_and_guarantees_the_day_count():
    """Regression test for real-world observation: asked for all N days in one
    structured-output call, gpt-4o-mini would sometimes produce one richly
    detailed day and silently stop, ignoring "produce exactly N days" — an
    array-length instruction the schema itself can't enforce. Generating one
    day per LLM call makes the day count a fact guaranteed by the Python loop,
    not something the model can get wrong."""
    agent = ItineraryArchitectAgent()
    state = TravelState(session_id="test")
    state.preferences.destination = "Goa"
    state.preferences.days = 3
    state.preferences.budget = 50000
    state.preferences.hotel_type = "mid_range"
    state.preferences.food_preferences = ["vegetarian"]

    fake_days = [_fake_day(1, cost=500, crowd="moderate", transport="Walk"),
                 _fake_day(2, cost=500, crowd="moderate", transport="Walk"),
                 _fake_day(3, cost=500, crowd="moderate", transport="Walk")]

    with patch.object(agent, "llm") as mock_llm:
        mock_llm.with_structured_output.return_value.invoke.side_effect = fake_days
        result = agent.run(state, "build it")

    days = result["itinerary"]["itinerary"]
    assert len(days) == 3
    assert [d["n"] for d in days] == [1, 2, 3]
    assert mock_llm.with_structured_output.return_value.invoke.call_count == 3


def test_backfill_fills_missing_cost_crowd_and_transport():
    """Regression test for real-world observation: the LLM often omits cost,
    crowd, and transport on individual segments even when explicitly instructed
    to fill them, leaving blank chips in the UI. The backfill must guarantee
    every segment has all three, and mark the last segment of the day as
    returning to the hotel rather than a generic 'Walk'."""
    agent = ItineraryArchitectAgent()
    state = TravelState(session_id="test")
    state.preferences.destination = "Goa"
    state.preferences.days = 1
    state.preferences.hotel_type = "mid_range"

    fake_day = _fake_day(1, cost=None, crowd=None, transport=None, extra_segment=True)

    with patch.object(agent, "llm") as mock_llm:
        mock_llm.with_structured_output.return_value.invoke.return_value = fake_day
        result = agent.run(state, "build it")

    segments = result["itinerary"]["itinerary"][0]["segments"]
    assert segments[0]["cost"] == 0
    assert segments[0]["crowd"] == "moderate"
    assert segments[0]["transport"] == "Walk"
    # Last segment of the day: not a generic "Walk" filler, should route back to the hotel
    assert segments[1]["transport"] == "Return to hotel"
    assert segments[1]["crowd"] == "busy"  # already-present values must not be overwritten
    assert segments[1]["cost"] == 0
