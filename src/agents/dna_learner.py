# src/agents/dna_learner.py

from src.agents.base import BaseAgent
from src.models.state import TravelState

class DNALearnerAgent(BaseAgent):
    def __init__(self):
        super().__init__("DNALearner", "You are an expert at extracting long-term user preferences.")

    def run(self, state: TravelState, user_input: str, plan: dict = None):
        # Identify new preferences based on the interaction and the final plan
        prompt = f"""
        Analyze the trip to {state.preferences.destination}. 
        User input: {user_input}
        Generated Itinerary: {plan}
        
        Extract 1-2 new 'Travel DNA' insights about the user's preferences (e.g., pace, food style, interest intensity).
        Return these as a JSON list of strings.
        """
        
        # Call LLM to identify changes
        insights = self.llm.invoke(prompt)
        
        # Append insights to state
        # Assuming you have a 'dna_insights' list in your TravelState
        state.dna_insights.extend(self._parse_insights(insights.content))
