"""
Thin REST wrappers around three Google Maps Platform APIs:
  - Places API (New)        — text search for real attractions/restaurants, photos
  - Routes API              — real walking distance/duration between two points
  - Street View Static API  — a street-level image for a given coordinate

Every function here either returns data or raises — callers decide how to
degrade (this project's convention is: wrap the call site in try/except and
fall back to LLM-only content, never crash the chat over a maps API hiccup).

None of these functions read environment variables themselves; the API key is
always passed in explicitly, which keeps them trivially mockable in tests and
makes it obvious at the call site whether a key is configured at all.
"""
import requests

PLACES_BASE = "https://places.googleapis.com/v1"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
STREET_VIEW_URL = "https://maps.googleapis.com/maps/api/streetview"

_SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.rating,places.userRatingCount,places.photos,places.reviews"
)

REQUEST_TIMEOUT = 10


def text_search_places(query: str, api_key: str, max_results: int = 8) -> list:
    """Places API (New) Text Search. Returns a list of plain dicts:
    name, address, rating, review_snippet, photo_name, lat, lng, place_id."""
    response = requests.post(
        f"{PLACES_BASE}/places:searchText",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": _SEARCH_FIELD_MASK,
        },
        json={"textQuery": query, "maxResultCount": max_results},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    places = response.json().get("places", [])

    results = []
    for place in places:
        location = place.get("location") or {}
        reviews = place.get("reviews") or []
        photos = place.get("photos") or []
        results.append({
            "place_id": place.get("id"),
            "name": (place.get("displayName") or {}).get("text", ""),
            "address": place.get("formattedAddress"),
            "rating": place.get("rating"),
            "user_rating_count": place.get("userRatingCount"),
            "review_snippet": (reviews[0].get("text", {}) or {}).get("text") if reviews else None,
            "photo_name": photos[0].get("name") if photos else None,
            "lat": location.get("latitude"),
            "lng": location.get("longitude"),
        })
    return results


def fetch_place_photo(photo_name: str, api_key: str, max_width: int = 400) -> bytes:
    """Fetches the actual image bytes for a Places API (New) photo resource name
    (e.g. 'places/ABC123/photos/XYZ'). The API key travels server-to-Google only —
    callers must never forward the constructed URL to a browser."""
    response = requests.get(
        f"{PLACES_BASE}/{photo_name}/media",
        params={"maxWidthPx": max_width, "key": api_key},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.content


def fetch_street_view_image(lat: float, lng: float, api_key: str, size: str = "400x300") -> bytes:
    """Fetches a Street View Static API image for a coordinate. Google returns a
    generic placeholder (still HTTP 200) when there's no real imagery for a
    location — there is no reliable way to detect that from the response alone."""
    response = requests.get(
        STREET_VIEW_URL,
        params={"size": size, "location": f"{lat},{lng}", "key": api_key},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.content


def compute_walking_route(origin_lat: float, origin_lng: float,
                           dest_lat: float, dest_lng: float, api_key: str) -> dict:
    """Routes API computeRoutes for walking mode. Returns
    {"distance_km": float, "duration_min": int}."""
    response = requests.post(
        ROUTES_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
        },
        json={
            "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
            "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}},
            "travelMode": "WALK",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    routes = response.json().get("routes", [])
    if not routes:
        return None

    route = routes[0]
    distance_km = route.get("distanceMeters", 0) / 1000.0
    duration_str = route.get("duration", "0s")  # e.g. "600s"
    duration_min = round(int(duration_str.rstrip("s")) / 60.0)
    return {"distance_km": distance_km, "duration_min": duration_min}
