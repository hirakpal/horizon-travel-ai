# tests/test_weather.py
from unittest.mock import patch, MagicMock

from src.tools import weather


def _mock_response(json_data=None):
    resp = MagicMock()
    resp.json.return_value = json_data or {}
    resp.raise_for_status.return_value = None
    return resp


def test_geocode_destination_parses_top_result():
    fake_response = {"results": [
        {"latitude": 35.0116, "longitude": 135.7681, "name": "Kyoto", "country": "Japan"},
        {"latitude": 1.0, "longitude": 1.0, "name": "Kyoto Other", "country": "Nowhere"},
    ]}
    with patch.object(weather.requests, "get", return_value=_mock_response(fake_response)) as mock_get:
        result = weather.geocode_destination("Kyoto, Japan")

    assert result == {"lat": 35.0116, "lng": 135.7681, "name": "Kyoto", "country": "Japan"}
    # only the part before the comma is sent to the geocoder
    assert mock_get.call_args.kwargs["params"]["name"] == "Kyoto"


def test_geocode_destination_returns_none_when_nothing_matches():
    with patch.object(weather.requests, "get", return_value=_mock_response({"results": []})):
        assert weather.geocode_destination("asdkjaskdjaskd") is None


def test_fetch_current_conditions_parses_real_response_shape():
    fake_response = {
        "timezone": "Asia/Tokyo",
        "current": {
            "temperature_2m": 18.4, "precipitation": 0.0, "weather_code": 2,
            "wind_speed_10m": 9.1, "is_day": 1, "time": "2026-07-05T14:00",
        },
    }
    with patch.object(weather.requests, "get", return_value=_mock_response(fake_response)):
        result = weather.fetch_current_conditions(35.01, 135.76)

    assert result["temp_c"] == 18.4
    assert result["weather_label"] == "Partly cloudy"
    assert result["weather_emoji"] == "⛅"
    assert result["is_day"] is True
    assert result["timezone"] == "Asia/Tokyo"
    assert result["local_time"] == "2026-07-05T14:00"


def test_weather_label_falls_back_for_unknown_code():
    label, emoji = weather.weather_label(999)
    assert label == "Conditions unavailable"
    assert emoji == "🌡️"


def test_api_errors_propagate_for_caller_to_handle():
    error_response = MagicMock()
    error_response.raise_for_status.side_effect = Exception("503 Service Unavailable")
    with patch.object(weather.requests, "get", return_value=error_response):
        try:
            weather.geocode_destination("Kyoto")
            assert False, "expected an exception to propagate"
        except Exception as e:
            assert "503" in str(e)
