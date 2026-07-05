"""
Deterministic time-of-day/day-of-week crowd estimate. There is no reliable
free, public "live crowd sensor" API for arbitrary destinations — rather
than fake one, this gives an honest, explainable estimate based on when
people typically go out, labeled as an estimate everywhere it's shown
(never claimed as live sensor data).
"""
from datetime import datetime

MEAL_HOURS = {12, 13, 19, 20}
QUIET_HOURS = set(range(0, 6)) | set(range(22, 24))
WEEKEND_DAYTIME_HOURS = set(range(10, 19))


def estimate_crowd_level(local_dt: datetime) -> dict:
    """Returns {"level": "low"|"moderate"|"busy", "reason": str} for the
    given local date/time at the destination."""
    hour = local_dt.hour
    is_weekend = local_dt.weekday() >= 5  # Saturday=5, Sunday=6

    if hour in MEAL_HOURS:
        return {"level": "busy", "reason": "Meal-time hours are typically the most crowded window."}
    if hour in QUIET_HOURS:
        return {"level": "low", "reason": "Late-night/early-morning hours are typically quiet."}
    if is_weekend and hour in WEEKEND_DAYTIME_HOURS:
        return {"level": "busy", "reason": "Weekend daytime draws the biggest crowds."}
    if not is_weekend and hour in WEEKEND_DAYTIME_HOURS:
        return {"level": "moderate", "reason": "Weekday daytime is moderately busy."}
    return {"level": "moderate", "reason": "Typical traffic for this time of day."}
