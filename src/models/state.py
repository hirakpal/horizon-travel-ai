from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from src.models.preferences import TravelPreferences

class TravelState(BaseModel):
    messages: List[Dict[str, str]] = []  # History of the chat
    preferences: TravelPreferences = TravelPreferences()
    active_agent: str = "Concierge"
    session_id: str
    itinerary_data: Optional[Dict[str, Any]] = None  # Populated by Architect
    dna_insights: List[str] = Field(default_factory=list)  # Populated by DNALearner
    transport_options: List[Dict[str, Any]] = Field(default_factory=list)  # Candidate cards for the UI

    class Config:
        arbitrary_types_allowed = True
