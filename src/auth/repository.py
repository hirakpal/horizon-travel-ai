"""
SQLite CRUD for users and password-reset tokens. Every function takes an
explicit connection rather than opening its own — that's what lets tests
share a single ':memory:' connection across a whole scenario (SQLite's
in-memory DBs don't persist across separate connect() calls), while
production code just passes the one long-lived connection from db.py.
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.models.user import User, UserProfile, HotelPreferences

RESET_TOKEN_VALIDITY_MINUTES = 30

PROFILE_LIST_FIELDS = ("food_preferences", "travel_preferences", "inflight_preferences", "travel_dna_notes")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_user(row: sqlite3.Row) -> User:
    profile = UserProfile(
        name=row["name"],
        date_of_birth=row["date_of_birth"],
        sex=row["sex"],
        address=row["address"],
        food_preferences=json.loads(row["food_preferences"]),
        travel_preferences=json.loads(row["travel_preferences"]),
        inflight_preferences=json.loads(row["inflight_preferences"]),
        hotel_preferences=HotelPreferences(**json.loads(row["hotel_preferences"])),
        travel_dna_notes=json.loads(row["travel_dna_notes"]),
    )
    return User(id=row["id"], email=row["email"], phone=row["phone"], profile=profile)


def create_user(conn: sqlite3.Connection, email: Optional[str], phone: Optional[str],
                 password_hash: str, password_salt: str, name: Optional[str] = None) -> User:
    now = _now()
    cursor = conn.execute(
        """INSERT INTO users (email, phone, password_hash, password_salt, name, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (email, phone, password_hash, password_salt, name, now, now),
    )
    conn.commit()
    return get_user_by_id(conn, cursor.lastrowid)


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[User]:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_email(conn: sqlite3.Connection, email: str) -> Optional[User]:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_phone(conn: sqlite3.Connection, phone: str) -> Optional[User]:
    row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_identifier(conn: sqlite3.Connection, identifier: str) -> Optional[User]:
    """identifier is whatever the user typed in — an email address or a phone number."""
    return get_user_by_email(conn, identifier) or get_user_by_phone(conn, identifier)


def get_credentials_by_identifier(conn: sqlite3.Connection, identifier: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT id, password_hash, password_salt FROM users WHERE email = ? OR phone = ?",
        (identifier, identifier),
    ).fetchone()


def update_password(conn: sqlite3.Connection, user_id: int, password_hash: str, password_salt: str) -> None:
    conn.execute(
        "UPDATE users SET password_hash = ?, password_salt = ?, updated_at = ? WHERE id = ?",
        (password_hash, password_salt, _now(), user_id),
    )
    conn.commit()


def update_profile(conn: sqlite3.Connection, user_id: int, **fields) -> User:
    """Merge-updates whichever profile fields are passed; anything not
    supplied keeps its current stored value. List/dict fields are JSON-encoded."""
    current = get_user_by_id(conn, user_id)
    if current is None:
        raise ValueError(f"No user with id {user_id}")
    profile = current.profile.model_dump()
    profile.update(fields)

    conn.execute(
        """UPDATE users SET name = ?, date_of_birth = ?, sex = ?, address = ?,
           food_preferences = ?, travel_preferences = ?, inflight_preferences = ?,
           hotel_preferences = ?, travel_dna_notes = ?, updated_at = ? WHERE id = ?""",
        (
            profile["name"], profile["date_of_birth"], profile["sex"], profile["address"],
            json.dumps(profile["food_preferences"]), json.dumps(profile["travel_preferences"]),
            json.dumps(profile["inflight_preferences"]), json.dumps(profile["hotel_preferences"]),
            json.dumps(profile["travel_dna_notes"]), _now(), user_id,
        ),
    )
    conn.commit()
    return get_user_by_id(conn, user_id)


def create_reset_token(conn: sqlite3.Connection, user_id: int, token: str) -> str:
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_VALIDITY_MINUTES)).isoformat()
    conn.execute(
        "INSERT INTO password_reset_tokens (user_id, token, expires_at, used, created_at) VALUES (?, ?, ?, 0, ?)",
        (user_id, token, expires_at, _now()),
    )
    conn.commit()
    return token


def get_valid_reset_token_user_id(conn: sqlite3.Connection, token: str) -> Optional[int]:
    row = conn.execute(
        "SELECT user_id, expires_at, used FROM password_reset_tokens WHERE token = ? ORDER BY id DESC LIMIT 1",
        (token,),
    ).fetchone()
    if row is None or row["used"]:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        return None
    return row["user_id"]


def mark_token_used(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE token = ?", (token,))
    conn.commit()
