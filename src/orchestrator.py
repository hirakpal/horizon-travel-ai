from src.models.state import TravelState
from src.agents.concierge import ConciergeAgent
from src.agents.extractor import PreferenceExtractionAgent
from src.agents.architect import ItineraryArchitectAgent
from src.agents.dna_learner import DNALearnerAgent

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
            response = f"I've built your itinerary! Here is the plan: {architect_result['itinerary']}"
            
            # Trigger DNA Learner in the background
            self.learner.run(state, user_input)
        else:
            # Trigger Concierge to ask for missing pieces
            concierge_result = self.concierge.run(state, user_input)
            response = concierge_result["reply"]
        
        # 3. Finalize State
        state.messages.append({"role": "assistant", "content": response})
        return response
