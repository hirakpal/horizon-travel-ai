"""
Thin REST wrapper around Open-Meteo's free, keyless geocoding + forecast APIs
— used for the Home page's "live monitoring" panel. Unlike the Google Maps
tools in this package, these endpoints need no API key at all, so weather
monitoring works even when GOOGLE_MAPS_API_KEY isn't configured.

Same convention as google_maps.py: these functions raise on failure; the
call site decides how to degrade (this project never lets an external API
hiccup crash the UI).
"""
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

REQUEST_TIMEOUT = 10

# WMO weather interpretation codes (used by Open-Meteo) -> (label, emoji).
# https://open-meteo.com/en/docs -> "WMO Weather interpretation codes"
_WMO_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"), 48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Dense drizzle", "🌦️"),
    56: ("Freezing drizzle", "🌦️"), 57: ("Freezing drizzle", "🌦️"),
    61: ("Slight rain", "🌧️"), 63: ("Rain", "🌧️"), 65: ("Heavy rain", "🌧️"),
    66: ("Freezing rain", "🌧️"), 67: ("Freezing rain", "🌧️"),
    71: ("Slight snow", "🌨️"), 73: ("Snow", "🌨️"), 75: ("Heavy snow", "🌨️"), 77: ("Snow grains", "🌨️"),
    80: ("Slight showers", "🌦️"), 81: ("Showers", "🌦️"), 82: ("Violent showers", "⛈️"),
    85: ("Slight snow showers", "🌨️"), 86: ("Snow showers", "🌨️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm with hail", "⛈️"), 99: ("Thunderstorm with hail", "⛈️"),
}


def weather_label(code: int) -> tuple:
    """(label, emoji) for a WMO weather code, with a safe fallback for
    codes outside the documented table."""
    return _WMO_CODES.get(code, ("Conditions unavailable", "🌡️"))


def geocode_destination(name: str):
    """Resolves a free-text place name (e.g. "Kyoto, Japan") to
    {"lat", "lng", "name", "country"}, or None if nothing matched.
    Takes only the part before the first comma — Open-Meteo's geocoder
    matches city/place names, not full "City, Country" strings."""
    city = name.split(",")[0].strip()
    response = requests.get(
        GEOCODING_URL, params={"name": city, "count": 1}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        return None
    top = results[0]
    return {"lat": top["latitude"], "lng": top["longitude"],
            "name": top.get("name", city), "country": top.get("country")}


def fetch_current_conditions(lat: float, lng: float) -> dict:
    """Current weather for a coordinate. Returns temperature, condition
    label/emoji, precipitation, wind, and the destination's own local time
    (via timezone=auto) so callers can reason about "now" at the
    destination rather than the server's own clock."""
    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat, "longitude": lng,
            "current": "temperature_2m,precipitation,weather_code,wind_speed_10m,is_day",
            "timezone": "auto",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    current = data.get("current") or {}
    label, emoji = weather_label(current.get("weather_code"))
    return {
        "temp_c": current.get("temperature_2m"),
        "precipitation_mm": current.get("precipitation"),
        "wind_kph": current.get("wind_speed_10m"),
        "is_day": bool(current.get("is_day", 1)),
        "weather_label": label,
        "weather_emoji": emoji,
        "local_time": current.get("time"),  # ISO string, destination-local
        "timezone": data.get("timezone"),
    }
