"""
Transport Suggestions Agent - Searches for and suggests transportation options
"""
import os
from src.agents.base import BaseAgent
from src.models.state import TravelState

class TransportSuggestionsAgent(BaseAgent):
    """
    Suggests flight, rail, bus, and sea routes based on origin, destination, and arrival time.
    Uses mock data for now; can be enhanced with real APIs like SerpAPI or Skyscanner.
    """
    
    def __init__(self):
        system_prompt = (
            "You are a travel transport expert. Provide realistic transport options "
            "(flights, trains, buses, ships) with estimated prices, duration, and availability. "
            "Format suggestions clearly with option numbers. Consider the user's arrival time preference."
        )
        super().__init__("Transport Suggestions", system_prompt)
    
    def run(self, state: TravelState, input_text: str) -> dict:
        """
        Generate transport suggestions based on origin, destination, and arrival time.
        """
        prefs = state.preferences
        
        if not (prefs.origin and prefs.destination and prefs.arrival_time):
            return {
                "suggestions": None,
                "message": "Need origin, destination, and arrival time preference to search transport."
            }
        
        # Build a prompt for the LLM to generate realistic suggestions
        prompt = f"""
        Based on the following travel details, suggest 3-4 realistic transport options:
        
        Origin: {prefs.origin}
        Destination: {prefs.destination}
        Preferred Arrival Time: {prefs.arrival_time}
        Travel Date: {prefs.month}
        Budget: ₹{prefs.budget}
        
        For each option, provide:
        - Transport type (flight/train/bus/ship)
        - Estimated price
        - Duration
        - Departure and arrival times
        - Why it suits the arrival preference
        
        Format as numbered list. Make prices realistic for India.
        """
        
        response = self.llm.invoke(prompt)
        suggestions_text = response.content
        
        return {
            "suggestions": suggestions_text,
            "message": "Here are your transport options based on your preferences."
        }
    
    def get_mock_suggestions(self, origin: str, destination: str, arrival_time: str) -> dict:
        """
        Fallback mock suggestions if LLM call fails.
        """
        mock_options = {
            "flight": {"price": "₹5,000-8,000", "duration": "2-3 hours", "availability": "Frequent"},
            "train": {"price": "₹2,000-3,500", "duration": "8-12 hours", "availability": "Daily"},
            "bus": {"price": "₹1,500-2,500", "duration": "12-18 hours", "availability": "Multiple times"},
            "ship": {"price": "₹3,000-5,000", "duration": "16-24 hours", "availability": "Limited"}
        }
        return mock_options
