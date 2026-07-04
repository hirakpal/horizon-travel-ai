from pydantic import BaseModel, Field
from typing import Optional, List


class HotelPreferences(BaseModel):
    budget_tier: Optional[str] = Field(None, description="budget, medium, or high")
    bed_type: Optional[str] = Field(None, description="e.g. single, double, king, twin")
    view: Optional[str] = Field(None, description="e.g. sea view, city view, garden view, no preference")
    pool: bool = False
    gym: bool = False
    spa: bool = False


class UserProfile(BaseModel):
    name: Optional[str] = None
    date_of_birth: Optional[str] = None  # ISO date string, e.g. "1994-05-21"
    sex: Optional[str] = None
    address: Optional[str] = None
    food_preferences: List[str] = Field(default_factory=list)
    travel_preferences: List[str] = Field(default_factory=list)
    inflight_preferences: List[str] = Field(default_factory=list)
    hotel_preferences: HotelPreferences = Field(default_factory=HotelPreferences)
    travel_dna_notes: List[str] = Field(default_factory=list)


class User(BaseModel):
    id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    profile: UserProfile = Field(default_factory=UserProfile)
