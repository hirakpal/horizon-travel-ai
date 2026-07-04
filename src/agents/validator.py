from src.agents.base import BaseAgent
from src.models.state import TravelState
from src.models.itinerary import ItineraryValidationResult


class ItineraryValidationAgent(BaseAgent):
    """Reviews a built itinerary for factual plausibility, internal
    consistency, and fit to the traveler's stated preferences — a second
    pair of eyes on the Architect's own output, not a rubber stamp."""

    def __init__(self):
        system_prompt = (
            "You are a meticulous travel itinerary fact-checker and quality reviewer. Given a "
            "day-by-day itinerary and the traveler's stated preferences, check for: unrealistic "
            "or wildly inconsistent costs, illogical time sequencing within a day, meals that "
            "don't match the stated food preference, pacing that doesn't fit the stated fitness "
            "level, and places or names that seem implausible or invented for the destination. "
            "Be specific and concrete about any issue found — a vague complaint isn't actionable. "
            "If the itinerary genuinely has no problems, say so and give it a high confidence score."
        )
        super().__init__("Itinerary Validator", system_prompt)

    def run(self, state: TravelState, input_text: str, itinerary_plan: dict = None) -> dict:
        p = state.preferences
        prompt = f"""
        Review this {p.days}-day itinerary for {p.destination}.
        Traveler preferences: budget {p.budget} INR total, hotel tier {p.hotel_type}, food
        preferences {p.food_preferences}, fitness level {p.fitness_level}.

        Itinerary:
        {itinerary_plan}

        Assess factual plausibility, internal consistency (timing, sequencing), and fit to the
        stated preferences. Give a confidence score from 0-100 and list any concrete issues found.
        """
        structured_llm = self.llm.with_structured_output(ItineraryValidationResult, method="function_calling")
        # A bare string to .invoke() becomes a single human message, silently dropping
        # self.system_prompt — pass it as an explicit system message instead.
        result = structured_llm.invoke([
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ])
        return {"confidence_score": result.confidence_score, "issues": result.issues}
