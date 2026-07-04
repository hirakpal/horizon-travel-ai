# src/agents/dna_learner.py

import json
import re

from src.agents.base import BaseAgent
from src.models.state import TravelState


class DNALearnerAgent(BaseAgent):
    def __init__(self):
        super().__init__("DNALearner", "You are an expert at extracting long-term user preferences.")

    def run(self, state: TravelState, user_input: str, plan: dict = None):
        """Extract 1-2 new Travel DNA insights from the interaction and append them to state."""
        prompt = f"""
        Analyze the trip to {state.preferences.destination}.
        User input: {user_input}
        Generated Itinerary: {plan}

        Extract 1-2 new 'Travel DNA' insights about the user's preferences (e.g., pace, food style, interest intensity).
        Return ONLY a JSON list of strings, e.g. ["insight one", "insight two"].
        """

        try:
            insights = self.llm.invoke(prompt)
            new_insights = self._parse_insights(insights.content)
        except Exception:
            new_insights = []

        state.dna_insights.extend(new_insights)
        return {"dna_insights": new_insights}

    def _parse_insights(self, content: str) -> list:
        """Parse the LLM's response into a clean list of insight strings."""
        if not content:
            return []

        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass

        # Fallback: treat each non-empty line as an insight
        return [line.strip("-• ").strip() for line in content.splitlines() if line.strip()]
