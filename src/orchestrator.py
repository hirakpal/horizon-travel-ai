# src/orchestrator.py

import json
from src.models.state import TravelState
# Add these imports
from src.agents.concierge import ConciergeAgent
from src.agents.extractor import PreferenceExtractionAgent
from src.agents.architect import ItineraryArchitectAgent
from src.agents.dna_learner import DNALearnerAgent
class RootOrchestrator:
    def __init__(self):
        self.concierge = ConciergeAgent()
        self.extractor = PreferenceExtractionAgent()
        self.architect = ItineraryArchitectAgent()
        self.learner = DNALearnerAgent() # Ensure this is initialized

    def process_turn(self, state: TravelState, user_input: str) -> str:
        # 1. Extraction: Always update state with user input
        extraction_result = self.extractor.run(state, user_input)
        
        # Merge extraction into existing preferences
        updated_data = state.preferences.model_dump()
        updated_data.update({k: v for k, v in extraction_result.items() if v is not None})
        state.preferences = TravelPreferences(**updated_data)
        
        # Add user input to history
        state.messages.append({"role": "user", "content": user_input})

        # 2. Orchestration Logic - EXPLICITLY check all required fields
        p = state.preferences
        is_ready = all([p.destination, p.days, p.budget, p.month, p.origin])

        if is_ready:
            # Trigger Architect
            architect_result = self.architect.run(state, user_input)
            
            import re
            match = re.search(r'\{.*\}', architect_result['itinerary'], re.DOTALL)
            if match:
                state.itinerary_data = json.loads(match.group(0))
                state.active_agent = "Architect"
                self.learner.run(state, user_input, plan=state.itinerary_data)
                response = "I've built your itinerary! Check the Itinerary tab to see it."
            else:
                response = "I created a plan, but I'm having trouble displaying it."
        else:
            # Fallback to Concierge
            state.active_agent = "Concierge"
            concierge_result = self.concierge.run(state, user_input)
            
            # Extract reply text safely
            if isinstance(concierge_result, dict):
                response = concierge_result.get("reply", str(concierge_result))
            else:
                response = str(concierge_result)

        # Final cleanup and return
        clean_response = response.replace('\\n', '\n')
        state.messages.append({"role": "assistant", "content": clean_response})
        return clean_response
