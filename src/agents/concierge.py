from src.agents.base import BaseAgent
from src.models.state import TravelState

class ConciergeAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are Horizon, an intelligent travel assistant. Your goal is to guide "
            "the user through trip planning. You are transparent and helpful. "
            "If the user has provided all necessary details (budget, days, month, origin, destination), "
            "tell them you are ready to build the itinerary. If details are missing, "
            "politely ask for them, but never guess."
        )
        super().__init__("Concierge", system_prompt)

    def run(self, state: TravelState, input_text: str) -> dict:
        # Check for missing info
        missing = [
            k for k, v in state.preferences.dict().items() 
            if v is None and k != "fitness_level" # fitness is optional for MVP
        ]

        # Prepare messages for LLM
        messages = self._get_messages(state, input_text)
        
        # If slots are missing, explicitly instruct the LLM to ask for them
        if missing:
            messages.append({
                "role": "system", 
                "content": f"The user is missing these details: {', '.join(missing)}. Ask for them politely."
            })
        else:
            messages.append({
                "role": "system", 
                "content": "All information is present. Confirm you are ready to build the itinerary."
            })

        response = self.llm.invoke(messages)
        
        return {"reply": response.content}
