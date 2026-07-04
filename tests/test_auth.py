# tests/test_auth.py
import time
from unittest.mock import patch

import pytest

from src.auth import db, repository, security, service
from src.auth.service import AuthError


@pytest.fixture
def conn():
    """A fresh in-memory DB per test. Must be the single shared connection
    object for the whole test — SQLite's ':memory:' DB doesn't persist
    across separate connect() calls."""
    connection = db.get_connection(":memory:")
    yield connection
    connection.close()


# ============================================================================
# security.py
# ============================================================================
def test_hash_password_roundtrip_verifies_correctly():
    password_hash, salt = security.hash_password("correct-horse-battery-staple")
    assert security.verify_password("correct-horse-battery-staple", password_hash, salt)
    assert not security.verify_password("wrong-password", password_hash, salt)


def test_hash_password_same_password_different_salts_produces_different_hashes():
    hash_a, salt_a = security.hash_password("same-password")
    hash_b, salt_b = security.hash_password("same-password")
    assert salt_a != salt_b
    assert hash_a != hash_b


def test_generate_reset_token_is_8_char_alphanumeric():
    token = security.generate_reset_token()
    assert len(token) == 8
    assert token.isalnum()


def test_generate_reset_token_is_random():
    tokens = {security.generate_reset_token() for _ in range(20)}
    assert len(tokens) == 20  # no collisions in 20 draws


# ============================================================================
# sign_up / login
# ============================================================================
def test_sign_up_creates_user_and_login_succeeds(conn):
    user = service.sign_up(conn, email="traveler@example.com", phone=None,
                            password="hunter22isgood", name="Asha")
    assert user.email == "traveler@example.com"

    logged_in = service.login(conn, "traveler@example.com", "hunter22isgood")
    assert logged_in is not None
    assert logged_in.id == user.id


def test_login_fails_with_wrong_password(conn):
    service.sign_up(conn, email="traveler@example.com", phone=None, password="correct-password")
    assert service.login(conn, "traveler@example.com", "wrong-password") is None


def test_login_fails_for_unknown_identifier(conn):
    assert service.login(conn, "nobody@example.com", "whatever123") is None


def test_sign_up_rejects_duplicate_email(conn):
    service.sign_up(conn, email="dupe@example.com", phone=None, password="password123")
    with pytest.raises(AuthError):
        service.sign_up(conn, email="dupe@example.com", phone=None, password="anotherpassword")


def test_sign_up_rejects_short_password(conn):
    with pytest.raises(AuthError):
        service.sign_up(conn, email="short@example.com", phone=None, password="short")


def test_sign_up_requires_email_or_phone(conn):
    with pytest.raises(AuthError):
        service.sign_up(conn, email=None, phone=None, password="password123")


def test_sign_up_with_phone_only_and_login_by_phone(conn):
    service.sign_up(conn, email=None, phone="+919876543210", password="password123")
    assert service.login(conn, "+919876543210", "password123") is not None


# ============================================================================
# Forgot password flow
# ============================================================================
def test_request_password_reset_unknown_identifier_reports_not_found(conn):
    result = service.request_password_reset(conn, "nobody@example.com")
    assert result["found"] is False
    assert result["dev_token"] is None


def test_request_password_reset_falls_back_to_dev_token_when_no_smtp_configured(conn, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    service.sign_up(conn, email="reset-me@example.com", phone=None, password="original-pw")

    result = service.request_password_reset(conn, "reset-me@example.com")

    assert result["found"] is True
    assert result["delivered"] is False
    assert result["channel"] == "email"
    assert result["dev_token"] is not None
    assert len(result["dev_token"]) == 8


def test_request_password_reset_uses_sms_channel_for_phone_identifier(conn, monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    service.sign_up(conn, email=None, phone="+919876500000", password="original-pw")

    result = service.request_password_reset(conn, "+919876500000")

    assert result["channel"] == "sms"
    assert result["dev_token"] is not None


def test_reset_password_with_valid_token_changes_password_and_consumes_token(conn):
    service.sign_up(conn, email="reset-flow@example.com", phone=None, password="old-password1")
    result = service.request_password_reset(conn, "reset-flow@example.com")
    token = result["dev_token"]

    assert service.reset_password(conn, token, "brand-new-password1") is True
    # Old password no longer works, new one does
    assert service.login(conn, "reset-flow@example.com", "old-password1") is None
    assert service.login(conn, "reset-flow@example.com", "brand-new-password1") is not None

    # Token is single-use
    assert service.reset_password(conn, token, "yet-another-password1") is False


def test_reset_password_rejects_invalid_token(conn):
    service.sign_up(conn, email="someone@example.com", phone=None, password="password123")
    assert service.reset_password(conn, "BOGUS123", "new-password1") is False


def test_reset_password_rejects_expired_token(conn):
    service.sign_up(conn, email="expiring@example.com", phone=None, password="password123")
    result = service.request_password_reset(conn, "expiring@example.com")
    token = result["dev_token"]

    # Force the stored token into the past
    conn.execute("UPDATE password_reset_tokens SET expires_at = ? WHERE token = ?",
                 ("2000-01-01T00:00:00+00:00", token))
    conn.commit()

    assert service.reset_password(conn, token, "new-password1") is False


def test_reset_password_rejects_short_new_password(conn):
    service.sign_up(conn, email="weak-reset@example.com", phone=None, password="password123")
    result = service.request_password_reset(conn, "weak-reset@example.com")
    with pytest.raises(AuthError):
        service.reset_password(conn, result["dev_token"], "short")


# ============================================================================
# Profile + Travel DNA sync
# ============================================================================
def test_update_profile_persists_fields(conn):
    user = service.sign_up(conn, email="profile@example.com", phone=None, password="password123")

    updated = service.update_profile(
        conn, user.id,
        name="Priya Sharma", date_of_birth="1990-04-12", sex="female",
        address="Bangalore, India", food_preferences=["vegetarian"],
        travel_preferences=["adventure"], inflight_preferences=["window seat"],
        hotel_preferences={"budget_tier": "medium", "bed_type": "king", "view": "sea",
                            "pool": True, "gym": False, "spa": True},
    )

    assert updated.profile.name == "Priya Sharma"
    assert updated.profile.food_preferences == ["vegetarian"]
    assert updated.profile.hotel_preferences.budget_tier == "medium"
    assert updated.profile.hotel_preferences.pool is True

    # Fetching fresh from the DB reflects the same values
    reloaded = repository.get_user_by_id(conn, user.id)
    assert reloaded.profile.name == "Priya Sharma"


def test_update_profile_partial_update_preserves_untouched_fields(conn):
    user = service.sign_up(conn, email="partial@example.com", phone=None, password="password123")
    service.update_profile(conn, user.id, name="First Name", food_preferences=["vegan"])

    updated = service.update_profile(conn, user.id, address="Mumbai, India")

    assert updated.profile.name == "First Name"  # untouched by the second call
    assert updated.profile.food_preferences == ["vegan"]  # untouched
    assert updated.profile.address == "Mumbai, India"  # newly set


def test_save_completed_trip_persists_a_trip_row_and_updates_profile():
    from src.models.preferences import TravelPreferences

    conn_ = db.get_connection(":memory:")
    user = service.sign_up(conn_, email="dna@example.com", phone=None, password="password123")
    service.update_profile(conn_, user.id, food_preferences=["vegetarian"])

    prefs = TravelPreferences(
        destination="Goa", food_preferences=["non_veg"], hotel_type="luxury",
        fitness_level="moderate", transport_modes=["flight"],
    )
    dna_insights = ["Prefers slow-paced mornings", "Loves street food"]

    updated = service.save_completed_trip(conn_, user.id, prefs, {"itinerary": []}, dna_insights)

    trips = repository.list_trips_for_user(conn_, user.id)
    assert len(trips) == 1
    assert trips[0]["destination"] == "Goa"
    assert trips[0]["dna_insights"] == dna_insights

    assert set(updated.profile.food_preferences) == {"vegetarian", "non_veg"}
    assert updated.profile.hotel_preferences.budget_tier == "high"
    assert "moderate" in updated.profile.travel_preferences
    assert "prefers flight" in updated.profile.travel_preferences
    assert "Prefers slow-paced mornings" in updated.profile.travel_dna_notes
    assert "Loves street food" in updated.profile.travel_dna_notes
    conn_.close()


def test_save_completed_trip_twice_does_not_duplicate_entries():
    from src.models.preferences import TravelPreferences

    conn_ = db.get_connection(":memory:")
    user = service.sign_up(conn_, email="dna2@example.com", phone=None, password="password123")
    prefs = TravelPreferences(food_preferences=["vegetarian"], fitness_level="high")
    dna_insights = ["Enjoys museums"]

    service.save_completed_trip(conn_, user.id, prefs, None, dna_insights)
    updated = service.save_completed_trip(conn_, user.id, prefs, None, dna_insights)

    assert len(repository.list_trips_for_user(conn_, user.id)) == 2  # two trips recorded...
    assert updated.profile.food_preferences.count("vegetarian") == 1  # ...but no duplicate preference entries
    assert updated.profile.travel_dna_notes.count("Enjoys museums") == 1
    conn_.close()


def test_recompute_profile_from_trip_history_aggregates_across_multiple_trips():
    from src.models.preferences import TravelPreferences

    conn_ = db.get_connection(":memory:")
    user = service.sign_up(conn_, email="multi-trip@example.com", phone=None, password="password123")

    trip1 = TravelPreferences(destination="Goa", food_preferences=["vegetarian"], hotel_type="budget")
    trip2 = TravelPreferences(destination="Kyoto", food_preferences=["non_veg"], hotel_type="luxury",
                               transport_modes=["flight"])

    service.save_completed_trip(conn_, user.id, trip1, None, ["Enjoys beaches"])
    updated = service.save_completed_trip(conn_, user.id, trip2, None, ["Enjoys temples"])

    assert len(repository.list_trips_for_user(conn_, user.id)) == 2
    # Food preferences accumulate across both trips
    assert set(updated.profile.food_preferences) == {"vegetarian", "non_veg"}
    # Hotel tier reflects the MOST RECENT trip (luxury/high), not the first (budget)
    assert updated.profile.hotel_preferences.budget_tier == "high"
    assert "prefers flight" in updated.profile.travel_preferences
    assert set(updated.profile.travel_dna_notes) == {"Enjoys beaches", "Enjoys temples"}
    conn_.close()


def test_recompute_profile_from_trip_history_is_a_no_op_with_no_trips():
    conn_ = db.get_connection(":memory:")
    user = service.sign_up(conn_, email="no-trips@example.com", phone=None, password="password123")
    service.update_profile(conn_, user.id, name="Someone")

    updated = service.recompute_profile_from_trip_history(conn_, user.id)

    assert updated.profile.name == "Someone"
    assert updated.profile.food_preferences == []
    conn_.close()


def test_list_trips_for_user_orders_most_recent_first():
    from src.models.preferences import TravelPreferences

    conn_ = db.get_connection(":memory:")
    user = service.sign_up(conn_, email="ordering@example.com", phone=None, password="password123")
    service.save_completed_trip(conn_, user.id, TravelPreferences(destination="Goa"), None, [])
    service.save_completed_trip(conn_, user.id, TravelPreferences(destination="Kyoto"), None, [])

    trips = repository.list_trips_for_user(conn_, user.id)

    assert [t["destination"] for t in trips] == ["Kyoto", "Goa"]
    conn_.close()


def test_delete_account_removes_user_and_all_their_data():
    from src.models.preferences import TravelPreferences

    conn_ = db.get_connection(":memory:")
    user = service.sign_up(conn_, email="delete-me@example.com", phone=None, password="password123")
    service.save_completed_trip(conn_, user.id, TravelPreferences(destination="Goa"), None, ["Loves beaches"])
    result = service.request_password_reset(conn_, "delete-me@example.com")
    assert result["found"] is True  # sanity: a reset token row now exists too

    service.delete_account(conn_, user.id)

    assert repository.get_user_by_id(conn_, user.id) is None
    assert repository.get_user_by_email(conn_, "delete-me@example.com") is None
    assert repository.list_trips_for_user(conn_, user.id) == []
    assert repository.get_valid_reset_token_user_id(conn_, result["dev_token"]) is None
    conn_.close()


def test_delete_account_only_removes_the_target_user():
    conn_ = db.get_connection(":memory:")
    user_a = service.sign_up(conn_, email="keep-me@example.com", phone=None, password="password123")
    user_b = service.sign_up(conn_, email="delete-me-too@example.com", phone=None, password="password123")

    service.delete_account(conn_, user_b.id)

    assert repository.get_user_by_id(conn_, user_a.id) is not None
    assert repository.get_user_by_id(conn_, user_b.id) is None
    conn_.close()


def test_login_fails_after_account_deletion():
    conn_ = db.get_connection(":memory:")
    user = service.sign_up(conn_, email="gone@example.com", phone=None, password="password123")
    service.delete_account(conn_, user.id)

    assert service.login(conn_, "gone@example.com", "password123") is None
    conn_.close()
