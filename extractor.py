# agents/extractor.py
import json
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

# 1. Define the schema for structured extraction
class TripPreferencesSchema(BaseModel):
    budget: Optional[int] = Field(
        default=None, 
        description="Total budget for the trip in INR. Convert shorthand like '95k' to 95000."
    )
    days: Optional[int] = Field(
        default=None, 
        description="Number of days for the trip. Must be an integer."
    )
    month: Optional[str] = Field(
        default=None, 
        description="Month of travel (e.g., 'November', 'April')."
    )
    origin: Optional[str] = Field(
        default=None, 
        description="City of origin (e.g., 'Osaka', 'Delhi')."
    )

class PreferenceExtractorAgent:
    def __init__(self, llm_client):
        """
        Initializes the agent with an OpenAI client instance.
        """
        self.client = llm_client
        self.model = "gpt-4o"

    def extract(self, user_message: str, current_prefs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts preferences using GPT-4o function calling.
        """
        tools = [{
            "type": "function",
            "function": {
                "name": "extract_trip_preferences",
                "description": "Extract travel parameters from user input.",
                "parameters": TripPreferencesSchema.model_json_schema()
            }
        }]

        system_prompt = (
            "You are the Horizon Preference Extraction Agent. "
            "Extract trip constraints strictly. Do not guess values. "
            "Current preferences: " + json.dumps(current_prefs)
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "extract_trip_preferences"}}
        )

        # Parse the tool call
        tool_call = response.choices[0].message.tool_calls[0]
        extracted_data = json.loads(tool_call.function.arguments)

        # Align 'origin' with UI's 'from' key
        if "origin" in extracted_data:
            extracted_data["from"] = extracted_data.pop("origin")

        # Merge results
        updated_prefs = {**current_prefs}
        for key, value in extracted_data.items():
            if value is not None:
                updated_prefs[key] = value

        return updated_prefs
