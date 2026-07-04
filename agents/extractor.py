import json
from src.agents.base import BaseAgent
from src.models.state import TravelState
from src.models.preferences import TravelPreferences

class PreferenceExtractionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Preference Extractor", "Extract travel data as JSON.")

    def run(self, state: TravelState, input_text: str) -> dict:
        # Create a light prompt instead of a structured tool call
        prompt = f"""
        Extract trip details from the user input into JSON format. 
        Schema: {TravelPreferences.schema_json()}
        Current state: {state.preferences.json()}
        User input: "{input_text}"
        Return ONLY valid JSON.
        """
        
        response = self.llm.invoke(prompt)
        
        # Clean the response (remove potential markdown ```json wrappers)
        content = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        
        # Manually create the model instance
        updated_prefs = TravelPreferences(**data)
        return {"updated_preferences": updated_prefs}
