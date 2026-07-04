# src/orchestrator.py

import json
from src.models.state import TravelState
from src.models.preferences import TravelPreferences
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
        is_ready = all([state.preferences.destination, state.preferences.days, state.preferences.budget])

        if is_ready:
            # Trigger Architect
            state.active_agent = "Architect"
            architect_result = self.architect.run(state, user_input)
                        
            import re
            match = re.search(r'\{.*\}', architect_result['itinerary'], re.DOTALL)
            if match:
                state.itinerary_data = json.loads(match.group(0))
                # HAND-OFF: Trigger DNA Learner
                self.learner.run(state, user_input, plan=state.itinerary_data)
                # Keep the chat response brief
                response = "I've built the perfect itinerary for your trip! Please head over to the **Itinerary** tab to view your day-by-day plan."
            else:
                response = "I've finalized your travel plan. Please check the Itinerary tab to view it."
            # Budget Spill Check
            if state.preferences.budget and state.preferences.destination:
                estimated_cost = self.estimate_trip_cost(state.preferences.destination, state.preferences.days)
            if estimated_cost > state.preferences.budget:
                return (f"⚠️ Budget Alert: A {state.preferences.days}-day trip to {state.preferences.destination} "
                        f"is estimated at {estimated_cost} INR, which exceeds your {state.preferences.budget} INR budget. "
                        "Would you like to adjust your trip length or look at cheaper destination alternatives?")
        else:
            # Fallback to Concierge ONLY if not ready
            state.active_agent = "Concierge"
            concierge_result = self.concierge.run(state, user_input)
            response = concierge_result.get("reply", str(concierge_result))
            
            # Extract reply text safely
            if isinstance(concierge_result, dict):
                response = concierge_result.get("reply", str(concierge_result))
            else:
                response = str(concierge_result)

        # Final cleanup and return
        clean_response = response.replace('\\n', '\n')
        state.messages.append({"role": "assistant", "content": clean_response})
        return clean_response
