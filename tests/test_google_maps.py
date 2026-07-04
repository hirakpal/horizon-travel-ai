# tests/test_google_maps.py
from unittest.mock import patch, MagicMock

from src.tools import google_maps


def _mock_response(json_data=None, content=b""):
    resp = MagicMock()
    resp.json.return_value = json_data or {}
    resp.content = content
    resp.raise_for_status.return_value = None
    return resp


def test_text_search_places_parses_real_response_shape():
    fake_api_response = {
        "places": [
            {
                "id": "abc123",
                "displayName": {"text": "Victoria Memorial"},
                "formattedAddress": "1, Queens Way, Kolkata",
                "location": {"latitude": 22.5448, "longitude": 88.3426},
                "rating": 4.6,
                "userRatingCount": 45000,
                "reviews": [{"text": {"text": "Stunning architecture and gardens."}}],
                "photos": [{"name": "places/abc123/photos/xyz"}],
            }
        ]
    }
    with patch.object(google_maps.requests, "post", return_value=_mock_response(fake_api_response)) as mock_post:
        results = google_maps.text_search_places("top attractions in Kolkata", api_key="test-key")

    assert len(results) == 1
    place = results[0]
    assert place["name"] == "Victoria Memorial"
    assert place["address"] == "1, Queens Way, Kolkata"
    assert place["rating"] == 4.6
    assert place["review_snippet"] == "Stunning architecture and gardens."
    assert place["photo_name"] == "places/abc123/photos/xyz"
    assert place["lat"] == 22.5448 and place["lng"] == 88.3426
    # API key must go in the header, never the URL/body
    assert mock_post.call_args.kwargs["headers"]["X-Goog-Api-Key"] == "test-key"


def test_text_search_places_handles_missing_optional_fields():
    fake_api_response = {"places": [{"id": "x", "displayName": {"text": "Some Place"}}]}
    with patch.object(google_maps.requests, "post", return_value=_mock_response(fake_api_response)):
        results = google_maps.text_search_places("query", api_key="test-key")

    assert results[0]["name"] == "Some Place"
    assert results[0]["rating"] is None
    assert results[0]["review_snippet"] is None
    assert results[0]["photo_name"] is None


def test_fetch_place_photo_returns_raw_bytes():
    with patch.object(google_maps.requests, "get", return_value=_mock_response(content=b"\xff\xd8fakejpeg")):
        photo_bytes = google_maps.fetch_place_photo("places/abc/photos/xyz", api_key="test-key")

    assert photo_bytes == b"\xff\xd8fakejpeg"


def test_fetch_street_view_image_returns_raw_bytes():
    with patch.object(google_maps.requests, "get", return_value=_mock_response(content=b"streetviewbytes")):
        image_bytes = google_maps.fetch_street_view_image(22.5, 88.3, api_key="test-key")

    assert image_bytes == b"streetviewbytes"


def test_compute_walking_route_converts_meters_and_seconds():
    fake_api_response = {"routes": [{"distanceMeters": 850, "duration": "600s"}]}
    with patch.object(google_maps.requests, "post", return_value=_mock_response(fake_api_response)):
        route = google_maps.compute_walking_route(22.5448, 88.3426, 22.5626, 88.3529, api_key="test-key")

    assert route["distance_km"] == 0.85
    assert route["duration_min"] == 10


def test_compute_walking_route_returns_none_when_no_routes_found():
    with patch.object(google_maps.requests, "post", return_value=_mock_response({"routes": []})):
        route = google_maps.compute_walking_route(0, 0, 1, 1, api_key="test-key")

    assert route is None


def test_api_errors_propagate_for_caller_to_handle():
    """These wrapper functions must raise on failure, not swallow errors — the
    orchestrator/architect layer is responsible for the try/except fallback,
    consistent with every other external call in this project."""
    error_response = MagicMock()
    error_response.raise_for_status.side_effect = Exception("503 Service Unavailable")
    with patch.object(google_maps.requests, "post", return_value=error_response):
        try:
            google_maps.text_search_places("query", api_key="test-key")
            assert False, "expected an exception to propagate"
        except Exception as e:
            assert "503" in str(e)
