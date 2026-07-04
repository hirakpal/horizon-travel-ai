"""
SQLite storage for user accounts, profiles, and password-reset tokens.

The DB path is resolved from the HORIZON_DB_PATH env var (defaulting to
data/horizon_users.db) so tests can point at a throwaway file or ':memory:'
without touching real user data.
"""
import os
import sqlite3

DEFAULT_DB_PATH = os.path.join("data", "horizon_users.db")


def get_db_path() -> str:
    return os.environ.get("HORIZON_DB_PATH", DEFAULT_DB_PATH)


def get_connection(db_path: str = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    if path != ":memory:":
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    # check_same_thread=False: Streamlit can rerun a session's script on a
    # different worker thread than the one that opened this connection (it's
    # stored once in st.session_state and reused across reruns) — sqlite3
    # otherwise raises ProgrammingError the moment that happens. Safe here
    # since each Streamlit session's reruns execute one at a time, never
    # concurrently against the same connection.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            phone TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            name TEXT,
            date_of_birth TEXT,
            sex TEXT,
            address TEXT,
            food_preferences TEXT NOT NULL DEFAULT '[]',
            travel_preferences TEXT NOT NULL DEFAULT '[]',
            inflight_preferences TEXT NOT NULL DEFAULT '[]',
            hotel_preferences TEXT NOT NULL DEFAULT '{}',
            travel_dna_notes TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_reset_tokens_token ON password_reset_tokens(token);

        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            destination TEXT,
            origin TEXT,
            days INTEGER,
            month TEXT,
            budget INTEGER,
            preferences TEXT NOT NULL,
            itinerary_data TEXT,
            dna_insights TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id);
    """)
    conn.commit()
