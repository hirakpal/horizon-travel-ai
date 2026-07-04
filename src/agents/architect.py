from src.agents.base import BaseAgent
from src.models.state import TravelState

class ItineraryArchitectAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are a master planner. Generate detailed, logical, day-by-day travel itineraries. "
            "You must return ONLY valid JSON. "
            "For every activity segment, you must include: "
            "'time', 'dur' (minutes), 'icon', 'title', 'desc', 'conf' (0-100), "
            "'evidence' (list of lists, e.g., [['dna', 'explanation']]), "
            "'alt' (list of 2 strings: ['Title', 'Description'], or null), "
            "'walk' (km), 'cost' (int), 'crowd' ('low'/'moderate'/'busy'), and 'transport' (str or null)."
        )
        super().__init__("Itinerary Architect", system_prompt)

    def run(self, state: TravelState, input_text: str) -> dict:
        prompt = f"""
        Build a {state.preferences.days}-day itinerary for {state.preferences.destination}.
        Budget: {state.preferences.budget} INR.
        Month: {state.preferences.month}.
        Origin: {state.preferences.origin}.

        Return the itinerary as a JSON object with a key 'itinerary' containing a list of days.
        Each day must have 'n', 'date', 'theme', 'weather', 'walk', and a 'segments' list.
        Ensure every segment strictly follows the structure defined in the system prompt.
        """
        
        response = self.llm.invoke(prompt)
        return {"itinerary": response.content}
