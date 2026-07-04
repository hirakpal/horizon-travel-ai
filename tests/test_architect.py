# tests/test_architect.py
import os
from unittest.mock import patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from src.agents.architect import ItineraryArchitectAgent
from src.models.itinerary import ItineraryPlan
from src.models.state import TravelState


def test_backfill_fills_missing_cost_crowd_and_transport():
    """Regression test for real-world observation: the LLM often omits cost,
    crowd, and transport on individual segments even when explicitly instructed
    to fill them, leaving blank chips in the UI. The backfill must guarantee
    every segment has all three, and mark the last segment of the day as
    returning to the hotel rather than a generic 'Walk'."""
    agent = ItineraryArchitectAgent()
    raw_plan = ItineraryPlan(itinerary=[
        {
            "n": 1, "date": "Day 1", "theme": "Arrival", "weather": None, "walk": 2.0,
            "segments": [
                {"time": "09:00", "dur": 60, "icon": "🍳", "title": "Breakfast",
                 "desc": "Local breakfast", "conf": 90, "evidence": [["pref", "matches diet"]],
                 "alt": None, "walk": 0.5, "cost": None, "crowd": None, "transport": None},
                {"time": "18:00", "dur": 90, "icon": "🌉", "title": "Bridge visit",
                 "desc": "Evening walk", "conf": 85, "evidence": [["web", "popular spot"]],
                 "alt": None, "walk": 1.0, "cost": 0, "crowd": "busy", "transport": None},
            ],
        }
    ])

    with patch.object(agent, "llm") as mock_llm:
        mock_llm.with_structured_output.return_value.invoke.return_value = raw_plan
        state = TravelState(session_id="test")
        result = agent.run(state, "build it")

    segments = result["itinerary"]["itinerary"][0]["segments"]
    assert segments[0]["cost"] == 0
    assert segments[0]["crowd"] == "moderate"
    assert segments[0]["transport"] == "Walk"
    # Last segment of the day: not a generic "Walk" filler, should route back to the hotel
    assert segments[1]["transport"] == "Return to hotel"
    assert segments[1]["crowd"] == "busy"  # already-present values must not be overwritten
    assert segments[1]["cost"] == 0
