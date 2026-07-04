from src.agents.base import BaseAgent
from src.models.state import TravelState

class DNALearnerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "DNA Learner",
            "You are an analytical observer. After every interaction, you review the "
            "user's preferences and trip history to extract 'signals'. "
            "Update the Travel DNA profile with specific, attributable changes."
        )

    def run(self, state: TravelState, input_text: str) -> dict:
        # Learner reviews history and suggests updates
        update_suggestion = self.llm.invoke(
            f"Review history: {state.messages[-3:]}. "
            "Identify one new preference or trend to add to the Travel DNA."
        )
        return {"dna_update": update_suggestion.content}
