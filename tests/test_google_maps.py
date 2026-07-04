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


def test_text_search_places_applies_location_bias_when_given():
    fake_api_response = {"places": []}
    with patch.object(google_maps.requests, "post", return_value=_mock_response(fake_api_response)) as mock_post:
        google_maps.text_search_places("attractions", api_key="test-key",
                                        location_bias={"lat": 25.6, "lng": 85.1})

    body = mock_post.call_args.kwargs["json"]
    assert body["locationBias"]["circle"]["center"] == {"latitude": 25.6, "longitude": 85.1}
    assert body["locationBias"]["circle"]["radius"] == google_maps.DEFAULT_BIAS_RADIUS_METERS


def test_text_search_places_omits_location_bias_when_not_given():
    with patch.object(google_maps.requests, "post", return_value=_mock_response({"places": []})) as mock_post:
        google_maps.text_search_places("attractions", api_key="test-key")

    assert "locationBias" not in mock_post.call_args.kwargs["json"]


def test_autocomplete_place_id_returns_top_suggestion():
    fake_api_response = {"suggestions": [
        {"placePrediction": {"placeId": "ChIJ_patna123", "text": {"text": "Patna, Bihar, India"}}},
        {"placePrediction": {"placeId": "ChIJ_other456", "text": {"text": "Patna, Somewhere Else"}}},
    ]}
    with patch.object(google_maps.requests, "post", return_value=_mock_response(fake_api_response)):
        place_id = google_maps.autocomplete_place_id("Patna", api_key="test-key")

    assert place_id == "ChIJ_patna123"


def test_autocomplete_place_id_returns_none_when_no_suggestions():
    with patch.object(google_maps.requests, "post", return_value=_mock_response({"suggestions": []})):
        assert google_maps.autocomplete_place_id("asdkjaskdjaskd", api_key="test-key") is None


def test_get_place_location_parses_lat_lng():
    fake_api_response = {"location": {"latitude": 25.5941, "longitude": 85.1376}}
    with patch.object(google_maps.requests, "get", return_value=_mock_response(fake_api_response)) as mock_get:
        location = google_maps.get_place_location("ChIJ_patna123", api_key="test-key")

    assert location == {"lat": 25.5941, "lng": 85.1376}
    assert mock_get.call_args.kwargs["headers"]["X-Goog-Api-Key"] == "test-key"


def test_get_place_location_returns_none_when_missing():
    with patch.object(google_maps.requests, "get", return_value=_mock_response({})):
        assert google_maps.get_place_location("ChIJ_x", api_key="test-key") is None


def test_resolve_place_id_uses_autocomplete_then_place_details():
    autocomplete_response = _mock_response({
        "suggestions": [{"placePrediction": {"placeId": "ChIJ_patna123", "text": {"text": "Patna"}}}]
    })
    details_response = _mock_response({"location": {"latitude": 25.5941, "longitude": 85.1376}})

    with patch.object(google_maps.requests, "post", return_value=autocomplete_response), \
         patch.object(google_maps.requests, "get", return_value=details_response):
        result = google_maps.resolve_place_id("Patna", api_key="test-key")

    assert result == {"place_id": "ChIJ_patna123", "lat": 25.5941, "lng": 85.1376}


def test_resolve_place_id_falls_back_to_text_search_when_autocomplete_empty():
    empty_autocomplete = _mock_response({"suggestions": []})
    text_search_result = _mock_response({"places": [{
        "id": "abc123", "displayName": {"text": "Patna"},
        "location": {"latitude": 25.5941, "longitude": 85.1376},
    }]})

    with patch.object(google_maps.requests, "post", side_effect=[empty_autocomplete, text_search_result]):
        result = google_maps.resolve_place_id("Patna", api_key="test-key")

    assert result == {"place_id": "abc123", "lat": 25.5941, "lng": 85.1376}


def test_resolve_place_id_returns_none_when_nothing_matches():
    empty_autocomplete = _mock_response({"suggestions": []})
    empty_text_search = _mock_response({"places": []})

    with patch.object(google_maps.requests, "post", side_effect=[empty_autocomplete, empty_text_search]):
        assert google_maps.resolve_place_id("asdkjaskdjaskd", api_key="test-key") is None


def test_fetch_trip_static_map_labels_each_point_and_returns_bytes():
    points = [{"lat": 22.57, "lng": 88.36}, {"lat": 22.58, "lng": 88.37}]
    with patch.object(google_maps.requests, "get",
                       return_value=_mock_response(content=b"fakepngbytes")) as mock_get:
        image_bytes = google_maps.fetch_trip_static_map(points, api_key="test-key")

    assert image_bytes == b"fakepngbytes"
    params = mock_get.call_args.kwargs["params"]
    markers = [v for k, v in params if k == "markers"]
    assert markers == ["label:1|22.57,88.36", "label:2|22.58,88.37"]
    assert ("key", "test-key") in params


def test_fetch_trip_static_map_returns_none_for_no_points():
    assert google_maps.fetch_trip_static_map([], api_key="test-key") is None


def test_fetch_trip_static_map_reuses_last_label_beyond_alphabet():
    points = [{"lat": i, "lng": i} for i in range(40)]
    with patch.object(google_maps.requests, "get",
                       return_value=_mock_response(content=b"x")) as mock_get:
        google_maps.fetch_trip_static_map(points, api_key="test-key")

    params = mock_get.call_args.kwargs["params"]
    markers = [v for k, v in params if k == "markers"]
    assert len(markers) == 40
    assert markers[-1].startswith("label:Z|")  # last unique label, reused for the overflow


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
