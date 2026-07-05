# tests/test_crowd.py
from datetime import datetime

from src.tools.crowd import estimate_crowd_level


def test_lunch_hour_is_busy_regardless_of_weekday():
    result = estimate_crowd_level(datetime(2026, 7, 6, 12, 30))  # Monday
    assert result["level"] == "busy"


def test_late_night_is_low():
    result = estimate_crowd_level(datetime(2026, 7, 6, 2, 0))  # Monday 2am
    assert result["level"] == "low"


def test_weekend_daytime_is_busy():
    result = estimate_crowd_level(datetime(2026, 7, 4, 15, 0))  # Saturday
    assert result["level"] == "busy"


def test_weekday_daytime_is_moderate():
    result = estimate_crowd_level(datetime(2026, 7, 6, 15, 0))  # Monday
    assert result["level"] == "moderate"


def test_every_result_includes_a_reason():
    for hour in range(24):
        result = estimate_crowd_level(datetime(2026, 7, 6, hour, 0))
        assert result["reason"]
