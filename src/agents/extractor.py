from src.agents.base import BaseAgent
from src.models.state import TravelState
from src.models.preferences import TravelPreferences

class PreferenceExtractionAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are an expert travel assistant. Your goal is to extract structured "
            "trip preferences from user input. Always update the existing preferences "
            "with new information provided in the user's latest message."
        )
        super().__init__("Preference Extractor", system_prompt)

    def run(self, state: TravelState, input_text: str) -> dict:
        # Create a structured LLM call
        structured_llm = self.llm.with_structured_output(TravelPreferences)
        
        # Prepare the current state as context for the model
        current_prefs_json = state.preferences.json()
        
        # Call the LLM to extract new data
        updated_prefs = structured_llm.invoke(
            f"Current preferences: {current_prefs_json}. "
            f"New user input: '{input_text}'. "
            "Extract any new or updated information into the schema."
        )
        
        # Return the update for the orchestrator to merge into the state
        return {"updated_preferences": updated_prefs}
