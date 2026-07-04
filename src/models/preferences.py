from pydantic import BaseModel, Field
from typing import Optional, List

class TravelPreferences(BaseModel):
    # Basic trip details
    budget: Optional[int] = Field(None, description="Total budget in INR")
    budget_flexible: Optional[bool] = Field(
        None, description="True if the user has no fixed budget and wants one estimated from their choices")
    days: Optional[int] = Field(None, description="Number of days for the trip")
    month: Optional[str] = Field(None, description="Month of travel")
    origin: Optional[str] = Field(None, description="Starting city")
    destination: Optional[str] = Field(None, description="Target destination")
    fitness_level: Optional[str] = Field(None, description="Walking/fitness tolerance")
    
    # Transport & arrival preferences
    arrival_time: Optional[str] = Field(None, description="Preferred arrival time (early_morning, morning, afternoon, evening, late_evening, night)")
    transport_modes: Optional[List[str]] = Field(default_factory=list, description="Preferred transport modes (flight, rail, bus, sea)")
    transport_suggestions: Optional[str] = Field(None, description="Transport suggestions summary text from search (price, duration, etc)")
    transport_cost: Optional[int] = Field(None, description="Price in INR of the selected transport option")
    checkin_advice: Optional[str] = Field(None, description="Check-in buffer advice for the outbound transport (when to reach the airport/station/terminus)")

    # Return journey & departure preferences
    departure_time: Optional[str] = Field(None, description="Preferred departure time for the return journey (early_morning, morning, afternoon, evening, late_evening, night)")
    return_transport_suggestions: Optional[str] = Field(None, description="Return transport suggestions summary text from search (price, duration, etc)")
    return_transport_cost: Optional[int] = Field(None, description="Price in INR of the selected return transport option")
    return_checkin_advice: Optional[str] = Field(None, description="Check-in buffer advice for the return transport (when to reach the airport/station/terminus)")

    # Hotel preferences
    hotel_type: Optional[str] = Field(None, description="Hotel preference (budget, mid_range, luxury, boutique)")
    hotel_cost_per_night: Optional[int] = Field(None, description="Per-night cost in INR of the selected hotel tier")

    # Food preferences
    food_preferences: Optional[List[str]] = Field(default_factory=list, description="Food preferences (vegetarian, vegan, non_veg, no_restrictions)")
    cuisine_types: Optional[List[str]] = Field(default_factory=list, description="Preferred cuisines (e.g., Indian, Italian, Japanese)")
    
    # Planning stage
    planning_stage: Optional[str] = Field(default="basic_info", description="Current stage (basic_info, transport, hotel_food, ready_to_plan, planning, complete)")
