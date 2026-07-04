from src.models.state import TravelState
from src.agents.concierge import ConciergeAgent
from src.agents.extractor import PreferenceExtractionAgent

class RootOrchestrator:
    def __init__(self):
        self.concierge = ConciergeAgent()
        self.extractor = PreferenceExtractionAgent()

    def process_turn(self, state: TravelState, user_input: str) -> str:
        """
        The main routing logic:
        1. Extract new preferences from input.
        2. Update the shared state.
        3. Let the Concierge respond based on the newly updated state.
        """
        
        # 1. Specialist: Extract
        extraction_result = self.extractor.run(state, user_input)
        
        # 2. Update state (Orchestrator owns the state mutation)
        updated_prefs = extraction_result["updated_preferences"]
        # Merge new preferences into existing state
        state.preferences = state.preferences.copy(update=updated_prefs.dict(exclude_unset=True))
        
        # 3. Specialist: Concierge
        # We append the user input to history before the concierge responds
        state.messages.append({"role": "user", "content": user_input})
        
        concierge_result = self.concierge.run(state, user_input)
        
        # 4. Save response to history
        response = concierge_result["reply"]
        state.messages.append({"role": "assistant", "content": response})
        
        return response
