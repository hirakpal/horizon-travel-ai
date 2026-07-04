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
        state.preferences = state.preferences.model_copy(update=extraction_result)
        
        # Add user input to history
        state.messages.append({"role": "user", "content": user_input})

        # 2. Orchestration Logic
        is_ready = all([state.preferences.destination, state.preferences.days, state.preferences.budget])

        if is_ready:
            # Trigger Architect
            architect_result = self.architect.run(state, user_input)
            
            # Robust JSON extraction
            import re
            match = re.search(r'\{.*\}', architect_result['itinerary'], re.DOTALL)
            if match:
                state.itinerary_data = json.loads(match.group(0))
                state.active_agent = "Architect"
                
                # HAND-OFF: Trigger DNA Learner after planning
                # Pass the input + the generated plan so the learner can extract new DNA
                self.learner.run(state, user_input, plan=state.itinerary_data)
                
                response = "I've built your itinerary! Check the Itinerary tab to see it."
            else:
                response = "I created a plan, but I'm having trouble displaying it."
        else:
            # Fallback to Concierge
            state.active_agent = "Concierge"
            response = self.concierge.run(state, user_input)

        state.messages.append({"role": "assistant", "content": response})
        return response
