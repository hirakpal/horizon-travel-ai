def get_weather(destination: str, date: str) -> dict:
    """Simulates a live weather API call."""
    return {"temp": "28°C", "condition": "Sunny", "risk": "Low"}

def get_crowd_levels(destination: str) -> dict:
    """Simulates a live crowd/footfall API call."""
    return {"level": "Moderate", "peak_hours": "14:00-16:00"}

def get_flight_status(origin: str, dest: str) -> dict:
    """Simulates a flight availability/pricing lookup."""
    return {"price_estimate": "₹12,000", "on_time_performance": "98%"}
