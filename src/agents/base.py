import os
from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI
from src.models.state import TravelState

class BaseAgent(ABC):
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.llm = ChatOpenAI(
            model="openai/gpt-4o-mini",
            temperature=0,
            openai_api_key=os.environ.get("OPENROUTER_API_KEY"),
            # Use base_url instead of openai_api_base
            # Ensure it ends with /v1/chat/completions or just points to the API root
            base_url="https://openrouter.ai/api/v1",
            max_tokens=8000,
            timeout=20,
            max_retries=1,
        )

    @abstractmethod
    def run(self, state: TravelState, input_text: str) -> dict:
        """
        Every specialist agent must implement this method.
        It accepts the current state and the user's latest input.
        Returns an update to the state or a response for the user.
        """
        pass

    def _get_messages(self, state: TravelState, input_text: str):
        """Helper to format the chat history with the system prompt."""
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(state.messages)
        messages.append({"role": "user", "content": input_text})
        return messages
