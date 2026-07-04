from src.models.state import TravelState
from src.agents.concierge import ConciergeAgent
from src.agents.extractor import PreferenceExtractionAgent
from src.agents.architect import ItineraryArchitectAgent
from src.agents.dna_learner import DNALearnerAgent
import json
class RootOrchestrator:
    def __init__(self):
        self.concierge = ConciergeAgent()
        self.extractor = PreferenceExtractionAgent()
        self.architect = ItineraryArchitectAgent()
        self.learner = DNALearnerAgent()

    def process_turn(self, state: TravelState, user_input: str) -> str:
        # 1. Extraction: Always update state with user input
        extraction_result = self.extractor.run(state, user_input)
        state.preferences = state.preferences.copy(update=extraction_result["updated_preferences"].dict(exclude_unset=True))
        
        # Add user input to history
        state.messages.append({"role": "user", "content": user_input})
        print(f"DEBUG: Current State Preferences: {state.preferences.dict()}")
        # 2. Routing Logic
        # Check if we have enough info to build an itinerary
        # We check if destination, days, and budget are set
        is_ready = all([
            state.preferences.destination,
            state.preferences.days,
            state.preferences.budget
        ])
        
        if is_ready:
            # Trigger Architect
            architect_result = self.architect.run(state, user_input)
            raw_response = architect_result['itinerary']
            
            # 1. More robust extraction: find the first '{' and last '}'
            try:
                start = raw_response.find('{')
                end = raw_response.rfind('}') + 1
                if start == -1 or end == 0:
                    raise ValueError("No JSON found in response")
                
                clean_json = raw_response[start:end]
                state.itinerary_data = json.loads(clean_json)
                state.active_agent = "Architect"
                response = "I've built your itinerary! Check the Itinerary tab to see it."
                
            except Exception as e:
                # Fallback if parsing fails
                print(f"DEBUG: JSON Parse Error: {e}. Raw response: {raw_response}")
                response = "I created a plan, but I'm having trouble displaying it. Please try asking again."
            
            # Trigger DNA Learner in the background
            self.learner.run(state, user_input)
        else:
            # Trigger Concierge to ask for missing pieces
            concierge_result = self.concierge.run(state, user_input)
            response = concierge_result["reply"]
        
        # 3. Finalize State
        state.messages.append({"role": "assistant", "content": response})
        return response
