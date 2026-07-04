import json
import os
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from openai import OpenAI

# 1. Schema remains the same
class TripPreferencesSchema(BaseModel):
    budget: Optional[int] = Field(default=None, description="Total budget in INR.")
    days: Optional[int] = Field(default=None, description="Trip duration in days.")
    month: Optional[str] = Field(default=None, description="Month of travel.")
    origin: Optional[str] = Field(default=None, description="City of origin.")

class PreferenceExtractorAgent:
    def __init__(self):
        # Initialize client pointing to OpenRouter
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        self.model = "openai/gpt-5.5"

    def extract(self, user_message: str, current_prefs: Dict[str, Any]) -> Dict[str, Any]:
        tools = [{
            "type": "function",
            "function": {
                "name": "extract_trip_preferences",
                "description": "Extract travel parameters from user input.",
                "parameters": TripPreferencesSchema.model_json_schema()
            }
        }]

        # OpenRouter-specific headers for attribution
        extra_headers = {
            "HTTP-Referer": "http://localhost:8501", # Your Streamlit URL
            "X-Title": "Horizon Travel AI"
        }

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are Horizon's preference extractor. Extract constraints strictly."},
                {"role": "user", "content": user_message}
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "extract_trip_preferences"}},
            max_tokens=500,
            extra_headers=extra_headers
        )

        tool_call = response.choices[0].message.tool_calls[0]
        extracted_data = json.loads(tool_call.function.arguments)

        if "origin" in extracted_data:
            extracted_data["from"] = extracted_data.pop("origin")

        updated_prefs = {**current_prefs}
        for key, value in extracted_data.items():
            if value is not None:
                updated_prefs[key] = value

        return updated_prefs
