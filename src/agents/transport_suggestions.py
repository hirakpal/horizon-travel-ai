"""
Transport Suggestions Agent - Searches for and suggests transportation options
"""
from src.agents.base import BaseAgent
from src.models.state import TravelState
from src.models.transport import TransportOptionsList

MOCK_OPTIONS = [
    {"mode": "flight", "price": 6500, "duration": "2h 30m", "departure": "07:00 AM",
     "arrival": "09:30 AM", "why": "Fastest option, arrives in the morning"},
    {"mode": "train", "price": 2500, "duration": "10h", "departure": "08:00 PM",
     "arrival": "06:00 AM", "why": "Overnight journey, budget-friendly"},
    {"mode": "bus", "price": 1800, "duration": "14h", "departure": "06:00 PM",
     "arrival": "08:00 AM", "why": "Cheapest option for a tight budget"},
]


class TransportSuggestionsAgent(BaseAgent):
    """
    Suggests flight, rail, bus, and sea routes based on origin, destination, and arrival time.
    Uses the LLM's general knowledge for now; can be swapped for a real search API later
    (e.g. SerpAPI, Skyscanner) without changing the option shape consumed by the UI.
    """

    def __init__(self):
        system_prompt = (
            "You are a travel transport expert. Provide realistic transport options "
            "(flights, trains, buses, ships) with estimated prices, duration, and availability. "
            "Consider the user's arrival time preference and make prices realistic for India."
        )
        super().__init__("Transport Suggestions", system_prompt)

    def run(self, state: TravelState, input_text: str) -> dict:
        """Generate 3-4 structured transport options based on origin, destination, arrival time."""
        prefs = state.preferences

        if not (prefs.origin and prefs.destination and prefs.arrival_time):
            return {"options": []}

        prompt = f"""
        Suggest 3-4 realistic transport options for this trip:

        Origin: {prefs.origin}
        Destination: {prefs.destination}
        Preferred Arrival Time: {prefs.arrival_time}
        Travel Date: {prefs.month}
        Budget: ₹{prefs.budget}

        Include a mix of modes (flight/train/bus/ship as applicable) with realistic Indian
        pricing, and explain why each option suits the stated arrival time preference.
        """

        structured_llm = self.llm.with_structured_output(TransportOptionsList, method="function_calling")
        result = structured_llm.invoke(prompt)
        return {"options": [opt.model_dump() for opt in result.options]}

    def get_mock_suggestions(self, origin: str, destination: str, arrival_time: str) -> list:
        """Fallback structured options if the LLM call fails."""
        return [dict(opt) for opt in MOCK_OPTIONS]
