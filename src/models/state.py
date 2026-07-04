from pydantic import BaseModel
from typing import List, Dict, Any
from src.models.preferences import TravelPreferences

class TravelState(BaseModel):
    messages: List[Dict[str, str]] = []  # History of the chat
    preferences: TravelPreferences = TravelPreferences()
    active_agent: str = "Concierge"
    session_id: str
    
    # Allows for easy debugging: state.dict()
