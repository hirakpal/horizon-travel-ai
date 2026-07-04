from pydantic import BaseModel, Field
from typing import List


class TransportOption(BaseModel):
    mode: str = Field(description="One of: flight, train, bus, ship")
    price: int = Field(description="Estimated price in INR")
    duration: str = Field(description="e.g. '2h 30m'")
    departure: str = Field(description="e.g. '06:00 AM'")
    arrival: str = Field(description="e.g. '08:30 AM'")
    why: str = Field(description="Why this option suits the traveler's arrival time preference")


class TransportOptionsList(BaseModel):
    options: List[TransportOption] = Field(default_factory=list)
