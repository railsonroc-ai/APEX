import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar

from backend.config import (
    DATA_DIR,
    DATABASE_PATH,
    SQLITE_TIMEOUT_SECONDS,
    SQLITE_BUSY_TIMEOUT_MS,
)


_active_transaction = ContextVar(
    "apex_database_transaction",
    default=None,
)


class _TransactionConnectionProxy:
    def __init__(self, connection):
        self._connection = connection

    def commit(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        return getattr(self._connection, name)


def _new_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=SQLITE_TIMEOUT_SECONDS,
    )
    connection.row_factory = sqlite3.Row
    connection.execute(
        f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}"
    )
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA synchronous = NORMAL")

    return connection


def get_db_connection():
    active = _active_transaction.get()

    if active is not None:
        return _TransactionConnectionProxy(active)

    return _new_connection()


@contextmanager
def transaction():
    active = _active_transaction.get()

    if active is not None:
        yield _TransactionConnectionProxy(active)
        return

    connection = _new_connection()
    token = _active_transaction.set(connection)

    try:
        connection.execute("BEGIN IMMEDIATE")
        yield _TransactionConnectionProxy(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        _active_transaction.reset(token)
        connection.close()



@contextmanager
def preview_transaction():
    active = _active_transaction.get()

    if active is not None:
        raise RuntimeError(
            "preview_transaction nao pode ser aninhada"
        )

    connection = _new_connection()
    token = _active_transaction.set(connection)

    try:
        connection.execute("BEGIN IMMEDIATE")
        yield _TransactionConnectionProxy(connection)
    finally:
        connection.rollback()
        _active_transaction.reset(token)
        connection.close()


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

        connection.execute("""
            CREATE TABLE IF NOT EXISTS concept_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area TEXT NOT NULL,
                concept TEXT NOT NULL,
                mastery REAL NOT NULL DEFAULT 0.0,
                difficulty_count INTEGER NOT NULL DEFAULT 0,
                last_evidence TEXT,
                review_count INTEGER NOT NULL DEFAULT 0,
                next_review_at TEXT,
                last_reviewed_at TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(area, concept)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS learning_turns (
                turn_id TEXT PRIMARY KEY,
                area TEXT NOT NULL,
                user_message TEXT NOT NULL,
                assistant_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()
    finally:
        connection.close()
