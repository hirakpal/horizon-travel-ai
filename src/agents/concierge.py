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

    # Only these fields are Concierge's concern; later stages (transport/hotel/food)
    # are collected deterministically by the orchestrator.
    BASIC_FIELDS = ["origin", "destination", "days", "budget", "month"]

    def run(self, state: TravelState, input_text: str) -> dict:
        # Use model_dump() for Pydantic V2
        prefs = state.preferences.model_dump()
        if prefs.get("budget") and not prefs.get("destination"):
            # This logic mimics a "budget-aware menu"
            options = [
                "Budget Backpacker: Hostels & local transit (~budget/3)",
                "Comfort Explorer: 3-star hotels & mixed transit (~budget/2)",
                "Premium Traveler: 4-star hotels & private transfers (~budget)",
                "Luxury Seeker: 5-star resorts & private guides (~budget * 1.5)",
                "Ultra-Premium: Bespoke experiences & VIP access (~budget * 2.5)"
            ]

            # Logic to check budget spill
            warning = ""
            if prefs["budget"] < 50000:  # Example threshold
                warning = "⚠️ Note: Your current budget is quite tight for this region, which may limit hotel choices."

            reply = f"I've analyzed your {prefs['budget']} INR budget. To help me build the right plan, please pick an experience tier:\n\n" + \
                    "\n".join(options) + f"\n\n{warning}"
            return {"reply": reply}
        # Identify missing basic fields only
        missing = [k for k in self.BASIC_FIELDS if not prefs.get(k)]

        messages = self._get_messages(state, input_text)

        if missing:
            messages.append({
                "role": "system",
                "content": f"The user is missing these details: {', '.join(missing)}. Ask for only the missing ones politely. Do not repeat what you already know."
            })
        else:
            messages.append({
                "role": "system",
                "content": "All basic trip information is present. Tell the user you have everything you need for the basics and are moving on to the next step."
            })

        response = self.llm.invoke(messages)

        return {"reply": response.content}
