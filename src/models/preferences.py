from pydantic import BaseModel, Field
from typing import Optional

class TravelPreferences(BaseModel):
    budget: Optional[int] = Field(None, description="Total budget in INR")
    days: Optional[int] = Field(None, description="Number of days for the trip")
    month: Optional[str] = Field(None, description="Month of travel")
    origin: Optional[str] = Field(None, description="Starting city")
    destination: Optional[str] = Field(None, description="Target destination")
    fitness_level: Optional[str] = Field(None, description="Walking/fitness tolerance")
