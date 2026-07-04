from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from src.models.preferences import TravelPreferences

class TravelState(BaseModel):
    messages: List[Dict[str, str]] = []  # History of the chat
    preferences: TravelPreferences = TravelPreferences()
    active_agent: str = "Concierge"
    session_id: str
    itinerary_data: Optional[Dict[str, Any]] = None  # Populated by Architect
    
    class Config:
        arbitrary_types_allowed = True
