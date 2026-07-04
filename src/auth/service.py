"""
High-level auth operations combining the repository, password hashing, and
notification channels. This is the module app.py's Login/Sign Up/Forgot
Password/Profile pages call into — none of them touch sqlite3 or hashlib
directly.
"""
import sqlite3
from typing import Optional

from src.auth import notifications, repository, security
from src.models.preferences import TravelPreferences
from src.models.user import User

MIN_PASSWORD_LENGTH = 8

HOTEL_TIER_MAP = {"budget": "budget", "mid_range": "medium", "luxury": "high", "boutique": "high"}


class AuthError(Exception):
    """Raised for user-facing sign-up/login problems (duplicate account,
    weak password, etc.) — the message is safe to show directly in the UI."""


def _looks_like_email(identifier: str) -> bool:
    return "@" in identifier


def sign_up(conn: sqlite3.Connection, email: Optional[str], phone: Optional[str],
            password: str, name: Optional[str] = None) -> User:
    email = email.strip() if email else None
    phone = phone.strip() if phone else None

    if not email and not phone:
        raise AuthError("Enter an email address or phone number to sign up.")
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if email and repository.get_user_by_email(conn, email):
        raise AuthError("An account with that email already exists.")
    if phone and repository.get_user_by_phone(conn, phone):
        raise AuthError("An account with that phone number already exists.")

    password_hash, salt = security.hash_password(password)
    try:
        return repository.create_user(conn, email, phone, password_hash, salt, name=name)
    except sqlite3.IntegrityError:
        raise AuthError("An account with that email or phone number already exists.")


def login(conn: sqlite3.Connection, identifier: str, password: str) -> Optional[User]:
    identifier = (identifier or "").strip()
    if not identifier or not password:
        return None
    row = repository.get_credentials_by_identifier(conn, identifier)
    if row is None:
        return None
    if not security.verify_password(password, row["password_hash"], row["password_salt"]):
        return None
    return repository.get_user_by_id(conn, row["id"])


def request_password_reset(conn: sqlite3.Connection, identifier: str) -> dict:
    """Looks up the identifier, generates+stores a token, and attempts
    delivery. `dev_token` is only populated when real delivery didn't
    happen (no provider configured, or the send failed) — production
    delivery never echoes the token back to the caller."""
    identifier = (identifier or "").strip()
    user = repository.get_user_by_identifier(conn, identifier) if identifier else None
    if user is None:
        return {"found": False, "delivered": False, "channel": None, "dev_token": None}

    token = security.generate_reset_token()
    repository.create_reset_token(conn, user.id, token)

    subject = "Your Horizon Travel AI password reset code"
    body = f"Your password reset code is: {token}\nIt expires in 30 minutes."

    if _looks_like_email(identifier):
        channel = "email"
        delivered = notifications.send_email(identifier, subject, body)
    else:
        channel = "sms"
        delivered = notifications.send_sms(identifier, body)

    return {
        "found": True,
        "delivered": delivered,
        "channel": channel,
        "dev_token": None if delivered else token,
    }


def reset_password(conn: sqlite3.Connection, token: str, new_password: str) -> bool:
    if not new_password or len(new_password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    user_id = repository.get_valid_reset_token_user_id(conn, token)
    if user_id is None:
        return False
    password_hash, salt = security.hash_password(new_password)
    repository.update_password(conn, user_id, password_hash, salt)
    repository.mark_token_used(conn, token)
    return True


def update_profile(conn: sqlite3.Connection, user_id: int, **fields) -> User:
    return repository.update_profile(conn, user_id, **fields)


def delete_account(conn: sqlite3.Connection, user_id: int) -> None:
    """Permanently deletes the account and every trip/token tied to it. The
    caller is responsible for logging the user out afterward — this function
    only touches the database."""
    repository.delete_user(conn, user_id)


def save_completed_trip(conn: sqlite3.Connection, user_id: int, preferences: TravelPreferences,
                         itinerary_data: Optional[dict], dna_insights: list) -> User:
    """Persists a completed trip against the user (so Travel DNA survives
    browser sessions and reflects real trip history), then recomputes the
    profile's aggregate preferences from that full history."""
    repository.create_trip(conn, user_id, preferences.model_dump(), itinerary_data, dna_insights)
    return recompute_profile_from_trip_history(conn, user_id)


def recompute_profile_from_trip_history(conn: sqlite3.Connection, user_id: int) -> User:
    """Folds every trip stored for this user into the profile's food/travel
    preferences and Travel DNA notes — not just whatever happens to be in
    the current browser session. Additive: preferences the user typed
    directly into Profile are never discarded, only added to. Safe to call
    any time (e.g. a manual "recompute" action); a no-op if there's no trip
    history yet."""
    trips = repository.list_trips_for_user(conn, user_id)  # most recent first
    user = repository.get_user_by_id(conn, user_id)
    if not trips:
        return user

    food = list(user.profile.food_preferences)
    travel_prefs = list(user.profile.travel_preferences)
    dna_notes = list(user.profile.travel_dna_notes)
    hotel_tier = None
    for trip in trips:
        prefs = trip["preferences"]
        for f in prefs.get("food_preferences") or []:
            if f not in food:
                food.append(f)
        if prefs.get("fitness_level") and prefs["fitness_level"] not in travel_prefs:
            travel_prefs.append(prefs["fitness_level"])
        for mode in prefs.get("transport_modes") or []:
            tag = f"prefers {mode}"
            if tag not in travel_prefs:
                travel_prefs.append(tag)
        if hotel_tier is None and prefs.get("hotel_type") in HOTEL_TIER_MAP:
            hotel_tier = HOTEL_TIER_MAP[prefs["hotel_type"]]  # newest-first, so the first hit is most recent
        for note in trip["dna_insights"] or []:
            if note not in dna_notes:
                dna_notes.append(note)

    hotel_prefs = user.profile.hotel_preferences.model_dump()
    if hotel_tier:
        hotel_prefs["budget_tier"] = hotel_tier

    return repository.update_profile(
        conn, user_id,
        food_preferences=food,
        travel_preferences=travel_prefs,
        hotel_preferences=hotel_prefs,
        travel_dna_notes=dna_notes,
    )
