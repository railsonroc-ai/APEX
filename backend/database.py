import sqlite3

from backend.config import (
    DATA_DIR,
    DATABASE_PATH,
    SQLITE_TIMEOUT_SECONDS,
    SQLITE_BUSY_TIMEOUT_MS,
)

def get_db_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=SQLITE_TIMEOUT_SECONDS,
    )
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection

def init_database():
    connection = get_db_connection()
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                area TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS learner_state (
                area TEXT PRIMARY KEY,
                current_concept TEXT,
                stage TEXT NOT NULL DEFAULT 'compreender',
                last_evidence TEXT,
                difficulty_count INTEGER NOT NULL DEFAULT 0,
                mastery REAL NOT NULL DEFAULT 0.0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()
    finally:
        connection.close()
