from src.agents.base import BaseAgent
from src.models.state import TravelState

class ConciergeAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are Horizon, an intelligent travel assistant. "
            "You are helpful, concise, and professional. "
            "If all trip details (destination, days, budget, month, origin) are present in the provided state, "
            "inform the user that you have everything you need and are ready to plan."
        )
        super().__init__("Concierge", system_prompt)

    def run(self, state: TravelState, input_text: str) -> dict:
        # Use model_dump() for Pydantic V2
        prefs = state.preferences.model_dump()
        
        # Identify missing fields
        missing = [k for k, v in prefs.items() if v is None and k != "fitness_level"]

        messages = self._get_messages(state, input_text)
        
        if missing:
            messages.append({
                "role": "system", 
                "content": f"The user is missing these details: {', '.join(missing)}. Ask for only the missing ones politely. Do not repeat what you already know."
            })
        else:
            messages.append({
                "role": "system", 
                "content": "All information is present. Tell the user you have everything and are ready to build the itinerary."
            })

        response = self.llm.invoke(messages)
        
        return {"reply": response.content}
