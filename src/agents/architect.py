from src.agents.base import BaseAgent
from src.models.state import TravelState

class ItineraryArchitectAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "Itinerary Architect",
            "You are a master planner. Generate detailed, logical, day-by-day travel "
            "itineraries. Always include transport, estimated costs, and walking distances. "
            "You must provide a confidence score (0-100) and evidence for every recommendation."
        )

    def run(self, state: TravelState, input_text: str) -> dict:
        # Here, the agent would eventually call tools from mock_data.py
        # For now, it returns a structured plan draft
        response = self.llm.invoke(
            f"Build a {state.preferences.days}-day itinerary for {state.preferences.destination}. "
            f"Budget: {state.preferences.budget}. "
            "Output must be a structured JSON format following the ItinerarySegment model."
        )
        return {"itinerary": response.content}
