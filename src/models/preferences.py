from pydantic import BaseModel, Field
from typing import Optional, List

class TravelPreferences(BaseModel):
    # Basic trip details
    budget: Optional[int] = Field(None, description="Total budget in INR")
    days: Optional[int] = Field(None, description="Number of days for the trip")
    month: Optional[str] = Field(None, description="Month of travel")
    origin: Optional[str] = Field(None, description="Starting city")
    destination: Optional[str] = Field(None, description="Target destination")
    fitness_level: Optional[str] = Field(None, description="Walking/fitness tolerance")
    
    # Transport & arrival preferences
    arrival_time: Optional[str] = Field(None, description="Preferred arrival time (early_morning, morning, afternoon, evening, late_evening, night)")
    transport_modes: Optional[List[str]] = Field(None, description="Preferred transport modes (flight, rail, bus, sea)")
    transport_suggestions: Optional[dict] = Field(None, description="Transport suggestions from search (price, duration, etc)")
    
    # Hotel preferences
    hotel_type: Optional[str] = Field(None, description="Hotel preference (budget, mid_range, luxury, boutique)")
    
    # Food preferences
    food_preferences: Optional[List[str]] = Field(None, description="Food preferences (vegetarian, vegan, non_veg, no_restrictions)")
    cuisine_types: Optional[List[str]] = Field(None, description="Preferred cuisines (e.g., Indian, Italian, Japanese)")
    
    # Planning stage
    planning_stage: Optional[str] = Field(None, description="Current stage (basic_info, transport, hotel_food, ready_to_plan, planning, complete)")
