def get_mock_weather(city: str):
    return {"temp": "22°C", "condition": "sunny", "confidence": 95}

def get_mock_crowd_level(place: str):
    return {"level": "moderate", "reason": "weekday cycle"}

def get_transport_options(start: str, end: str):
    return [{"type": "train", "duration": "45m", "cost": 500}]
