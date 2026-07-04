# tests/test_architect.py
import os
from unittest.mock import patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from src.agents.architect import ItineraryArchitectAgent
from src.models.itinerary import ItineraryDay
from src.models.state import TravelState
from src.tools import google_maps


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


# ============================================================================
# Real-place grounding (Google Places/Routes) — all of this must be a complete
# no-op when GOOGLE_MAPS_API_KEY isn't configured, which is the case for every
# test above this point (no key is ever set in the test environment).
# ============================================================================
FAKE_PLACES = [
    {"place_id": "p1", "name": "Victoria Memorial", "address": "Kolkata, WB",
     "rating": 4.6, "review_snippet": "Stunning architecture.",
     "photo_name": "places/p1/photos/x", "lat": 22.5448, "lng": 88.3426},
    {"place_id": "p2", "name": "Peter Cat Restaurant", "address": "Park Street, Kolkata",
     "rating": 4.3, "review_snippet": "Legendary chelo kebab.",
     "photo_name": "places/p2/photos/y", "lat": 22.5535, "lng": 88.3520},
]


def test_run_without_maps_api_key_never_calls_google(monkeypatch):
    """No GOOGLE_MAPS_API_KEY configured -> the whole grounding pipeline must be
    skipped, not attempted-and-failed. Confirms zero behavior change for anyone
    who hasn't set up Google Maps."""
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    agent = ItineraryArchitectAgent()
    state = TravelState(session_id="test")
    state.preferences.destination = "Kolkata"
    state.preferences.days = 1

    with patch.object(agent, "llm") as mock_llm, \
         patch.object(google_maps, "text_search_places") as mock_search:
        mock_llm.with_structured_output.return_value.invoke.return_value = _fake_day(1)
        result = agent.run(state, "build it")

    mock_search.assert_not_called()
    assert "place_id" not in result["itinerary"]["itinerary"][0]["segments"][0]


def test_run_grounds_matching_segment_titles_in_real_places(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    agent = ItineraryArchitectAgent()
    state = TravelState(session_id="test")
    state.preferences.destination = "Kolkata"
    state.preferences.days = 1
    state.preferences.food_preferences = ["non_veg"]

    day = ItineraryDay(n=1, date="Day 1", theme="Culture", weather=None, walk=3.0, segments=[
        {"time": "10:00", "dur": 90, "icon": "🏛️", "title": "Victoria Memorial",
         "desc": "Visit the museum.", "conf": 90, "evidence": [["dna", "matches culture interest"]],
         "alt": None, "walk": 1.0, "cost": 50, "crowd": "moderate", "transport": None},
        {"time": "13:00", "dur": 60, "icon": "🍽️", "title": "A generic unmatched lunch spot",
         "desc": "Lunch.", "conf": 80, "evidence": [["web", "popular"]],
         "alt": None, "walk": 0.5, "cost": 600, "crowd": "moderate", "transport": None},
    ])

    with patch.object(agent, "llm") as mock_llm, \
         patch.object(google_maps, "text_search_places", return_value=FAKE_PLACES) as mock_search:
        mock_llm.with_structured_output.return_value.invoke.return_value = day
        result = agent.run(state, "build it")

    assert mock_search.call_count == 2  # one attractions search, one restaurant search
    segments = result["itinerary"]["itinerary"][0]["segments"]
    assert segments[0]["place_id"] == "p1"
    assert segments[0]["rating"] == 4.6
    assert segments[0]["lat"] == 22.5448
    assert any("Stunning architecture" in e[1] for e in segments[0]["evidence"])
    # A title with no reasonable match must not be forced onto an unrelated real place
    assert "place_id" not in segments[1]


def test_run_applies_real_walking_distance_between_grounded_segments(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    agent = ItineraryArchitectAgent()
    state = TravelState(session_id="test")
    state.preferences.destination = "Kolkata"
    state.preferences.days = 1

    day = ItineraryDay(n=1, date="Day 1", theme="Culture", weather=None, walk=3.0, segments=[
        {"time": "10:00", "dur": 90, "icon": "🏛️", "title": "Victoria Memorial",
         "desc": "Visit.", "conf": 90, "evidence": [["dna", "x"]], "alt": None,
         "walk": 1.0, "cost": 50, "crowd": "moderate", "transport": None},
        {"time": "13:00", "dur": 60, "icon": "🍽️", "title": "Peter Cat Restaurant",
         "desc": "Lunch.", "conf": 80, "evidence": [["web", "x"]], "alt": None,
         "walk": 0.5, "cost": 600, "crowd": "moderate", "transport": None},
    ])

    with patch.object(agent, "llm") as mock_llm, \
         patch.object(google_maps, "text_search_places", return_value=FAKE_PLACES), \
         patch.object(google_maps, "compute_walking_route",
                       return_value={"distance_km": 1.2, "duration_min": 15}) as mock_route:
        mock_llm.with_structured_output.return_value.invoke.return_value = day
        result = agent.run(state, "build it")

    mock_route.assert_called_once()
    first_segment = result["itinerary"]["itinerary"][0]["segments"][0]
    assert first_segment["walk"] == 1.2
    assert "15 min" in first_segment["transport"]
    assert "1.2 km" in first_segment["transport"]


def test_run_degrades_gracefully_when_places_search_fails(monkeypatch):
    """A Google API outage must not break itinerary building — it should just
    fall back to the LLM-only itinerary, same as when no key is configured."""
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    agent = ItineraryArchitectAgent()
    state = TravelState(session_id="test")
    state.preferences.destination = "Kolkata"
    state.preferences.days = 1

    with patch.object(agent, "llm") as mock_llm, \
         patch.object(google_maps, "text_search_places", side_effect=Exception("503")):
        mock_llm.with_structured_output.return_value.invoke.return_value = _fake_day(1)
        result = agent.run(state, "build it")

    assert result["itinerary"]["itinerary"][0]["n"] == 1
    assert "place_id" not in result["itinerary"]["itinerary"][0]["segments"][0]
