from src.agents.base import BaseAgent
from src.models.state import TravelState
from src.models.itinerary import ItineraryPlan

class ItineraryArchitectAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are a master travel planner. Generate detailed, logical, day-by-day travel "
            "itineraries that strictly follow the given schema. For every activity segment, write "
            "a specific, concrete title and description (never generic placeholders like "
            "'Activity'), a realistic cost in INR, a confidence score reflecting how well-known "
            "the recommendation is, and at least one evidence entry categorized as one of: "
            "dna, live, local, web, comm, pref."
        )
        super().__init__("Itinerary Architect", system_prompt)

    def run(self, state: TravelState, input_text: str) -> dict:
        prompt = f"""
        Build a {state.preferences.days}-day itinerary for {state.preferences.destination}.
        Budget: {state.preferences.budget} INR.
        Month: {state.preferences.month}.
        Origin: {state.preferences.origin}.
        Hotel preference: {state.preferences.hotel_type}.
        Food preferences: {state.preferences.food_preferences}.

        Produce one day per requested day, each with 3-4 activity segments covering the day
        from morning to evening, with realistic times, costs, and walking distances.
        """

        structured_llm = self.llm.with_structured_output(ItineraryPlan, method="function_calling")
        result = structured_llm.invoke(prompt)
        return {"itinerary": result.model_dump()}
