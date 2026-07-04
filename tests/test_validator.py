# tests/test_validator.py
import os
from unittest.mock import patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from src.agents.validator import ItineraryValidationAgent
from src.models.itinerary import ItineraryValidationResult
from src.models.state import TravelState


def test_run_returns_confidence_score_and_issues():
    agent = ItineraryValidationAgent()
    state = TravelState(session_id="test")
    state.preferences.destination = "Goa"
    state.preferences.days = 2
    state.preferences.budget = 30000

    fake_result = ItineraryValidationResult(confidence_score=42, issues=["Day 2 lunch is vegetarian-only "
                                                                          "but the traveler asked for non-veg"])

    with patch.object(agent, "llm") as mock_llm:
        mock_llm.with_structured_output.return_value.invoke.return_value = fake_result
        result = agent.run(state, "", itinerary_plan={"itinerary": []})

    assert result["confidence_score"] == 42
    assert "vegetarian-only" in result["issues"][0]


def test_run_passes_system_prompt_as_explicit_message():
    """A bare string to .invoke() becomes a single human message, silently
    dropping the system prompt — must be passed as an explicit system message."""
    agent = ItineraryValidationAgent()
    state = TravelState(session_id="test")
    state.preferences.destination = "Goa"

    with patch.object(agent, "llm") as mock_llm:
        mock_llm.with_structured_output.return_value.invoke.return_value = ItineraryValidationResult(
            confidence_score=90, issues=[])
        agent.run(state, "", itinerary_plan={"itinerary": []})

    messages = mock_llm.with_structured_output.return_value.invoke.call_args[0][0]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == agent.system_prompt
