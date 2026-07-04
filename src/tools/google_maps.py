"""
Thin REST wrappers around four Google Maps Platform APIs:
  - Places API (New)        — text search for real attractions/restaurants, photos,
                               plus Autocomplete/Place Details for place_id resolution
  - Routes API              — real walking distance/duration between two points
  - Street View Static API  — a street-level image for a given coordinate
  - Maps Static API         — one rendered map image with a marker per place,
                               for showing the whole trip laid out geographically

Every function here either returns data or raises — callers decide how to
degrade (this project's convention is: wrap the call site in try/except and
fall back to LLM-only content, never crash the chat over a maps API hiccup).

None of these functions read environment variables themselves; the API key is
always passed in explicitly, which keeps them trivially mockable in tests and
makes it obvious at the call site whether a key is configured at all.

Several Google Maps Platform APIs (Place Details, and any locationBias tied to
a specific place) require a place_id rather than a free-text city/landmark
name. resolve_place_id() is the entry point for that: it turns "Patna" or
"Eiffel Tower" into a concrete place_id plus coordinates, via Autocomplete
first and a plain text search as a fallback.
"""
import string

import requests

PLACES_BASE = "https://places.googleapis.com/v1"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
STREET_VIEW_URL = "https://maps.googleapis.com/maps/api/streetview"
STATIC_MAP_URL = "https://maps.googleapis.com/maps/api/staticmap"

# Static Maps API marker labels are a single alphanumeric character — this
# covers a typical multi-day itinerary's worth of grounded segments (1-9 then
# A-Z) before labels start repeating.
MAP_MARKER_LABELS = "123456789" + string.ascii_uppercase

_SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.rating,places.userRatingCount,places.photos,places.reviews"
)

REQUEST_TIMEOUT = 10
DEFAULT_BIAS_RADIUS_METERS = 20_000.0


def text_search_places(query: str, api_key: str, max_results: int = 8, location_bias: dict = None) -> list:
    """Places API (New) Text Search. Returns a list of plain dicts:
    name, address, rating, review_snippet, photo_name, lat, lng, place_id.

    `location_bias`, if given, is {"lat": float, "lng": float, "radius": float}
    (radius in meters, optional) — steers results toward that area, which
    matters for ambiguous names (many cities/streets share a name worldwide)."""
    body = {"textQuery": query, "maxResultCount": max_results}
    if location_bias:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": location_bias["lat"], "longitude": location_bias["lng"]},
                "radius": location_bias.get("radius", DEFAULT_BIAS_RADIUS_METERS),
            }
        }

    response = requests.post(
        f"{PLACES_BASE}/places:searchText",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": _SEARCH_FIELD_MASK,
        },
        json=body,
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


def autocomplete_place_id(query: str, api_key: str):
    """Places API (New) Autocomplete. Returns the top-matching place_id for a
    free-text query (city, landmark, address), or None if nothing matched."""
    response = requests.post(
        f"{PLACES_BASE}/places:autocomplete",
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key},
        json={"input": query},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    suggestions = response.json().get("suggestions", [])
    if not suggestions:
        return None
    return suggestions[0].get("placePrediction", {}).get("placeId")


def get_place_location(place_id: str, api_key: str):
    """Place Details (New), location field only. Returns {"lat": float, "lng": float}
    for a place_id, or None if the place has no location on record."""
    response = requests.get(
        f"{PLACES_BASE}/places/{place_id}",
        headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "location"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    location = response.json().get("location")
    if not location:
        return None
    return {"lat": location.get("latitude"), "lng": location.get("longitude")}


def resolve_place_id(query: str, api_key: str):
    """Resolves a free-text place name to {"place_id", "lat", "lng"} — the
    entry point for any call site that has a city/landmark name but needs a
    place_id (or a reliable lat/lng to bias other searches around). Tries
    Autocomplete first; if that finds nothing, falls back to the top result
    of a plain text search rather than giving up."""
    place_id = autocomplete_place_id(query, api_key)
    if place_id:
        location = get_place_location(place_id, api_key)
        if location:
            return {"place_id": place_id, "lat": location["lat"], "lng": location["lng"]}

    results = text_search_places(query, api_key, max_results=1)
    if not results:
        return None
    top = results[0]
    return {"place_id": top["place_id"], "lat": top["lat"], "lng": top["lng"]}


def fetch_trip_static_map(points: list, api_key: str, size: str = "640x400"):
    """Maps Static API. Renders one map image with a labeled marker per point,
    for showing an entire trip's grounded places at a glance. `points` is a
    list of {"lat": float, "lng": float} dicts, in the order they should be
    numbered (typically day-by-day, morning-to-evening). Returns the raw PNG
    bytes, or None if there's nothing to plot."""
    if not points:
        return None
    params = [("size", size), ("maptype", "roadmap"), ("key", api_key)]
    for i, point in enumerate(points):
        label = MAP_MARKER_LABELS[min(i, len(MAP_MARKER_LABELS) - 1)]
        params.append(("markers", f"label:{label}|{point['lat']},{point['lng']}"))

    response = requests.get(STATIC_MAP_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.content
