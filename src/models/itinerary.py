from pydantic import BaseModel, Field
from typing import List, Optional


class ItinerarySegment(BaseModel):
    time: str = Field(description="e.g. '09:00'")
    dur: int = Field(description="Duration in minutes")
    icon: str = Field(description="A single emoji representing the activity")
    title: str
    desc: str
    conf: int = Field(description="Confidence score 0-100")
    evidence: List[List[str]] = Field(
        default_factory=list,
        description="List of [category, explanation] pairs. Category should be one of: "
                    "dna, live, local, web, comm, pref")
    alt: Optional[List[str]] = Field(
        None, description="Optional alternative as [title, description], or omit if none")
    walk: float = Field(0.0, description="Walking distance in km for this segment")
    cost: Optional[int] = Field(None, description="Cost in INR, 0 if free")
    crowd: Optional[str] = Field(None, description="One of: low, moderate, busy")
    transport: Optional[str] = Field(None, description="Transport to the next segment, or omit if none")


class ItineraryDay(BaseModel):
    n: int = Field(description="Day number, starting at 1")
    date: str
    theme: str
    weather: Optional[str] = None
    walk: float = Field(0.0, description="Total walking distance in km for the day")
    segments: List[ItinerarySegment] = Field(default_factory=list)


class ItineraryPlan(BaseModel):
    itinerary: List[ItineraryDay] = Field(default_factory=list)


class ItineraryValidationResult(BaseModel):
    confidence_score: int = Field(
        description="0-100 confidence that this itinerary is factually sound, internally "
                    "consistent, and matches the traveler's stated preferences")
    issues: List[str] = Field(
        default_factory=list,
        description="Specific, concrete problems found (e.g. unrealistic costs, illogical "
                    "sequencing/timing, a meal segment that violates the stated food preference, "
                    "pacing that doesn't fit the traveler's fitness level, a place that doesn't "
                    "plausibly exist in this destination). Empty if none found.")
