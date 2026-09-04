import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar

from backend.config import (
    DATA_DIR,
    DATABASE_PATH,
    SQLITE_TIMEOUT_SECONDS,
    SQLITE_BUSY_TIMEOUT_MS,
)
from backend.migrations import run_migrations


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


def _ensure_wal_mode(
    connection,
    attempts=5,
    retry_delay_seconds=0.05,
):
    for attempt in range(attempts):
        try:
            row = connection.execute(
                "PRAGMA journal_mode = WAL"
            ).fetchone()

            if (
                row is not None
                and str(row[0]).lower() == "wal"
            ):
                return

            raise RuntimeError(
                "SQLite não ativou journal_mode WAL."
            )

        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise

            try:
                current = connection.execute(
                    "PRAGMA journal_mode"
                ).fetchone()
            except sqlite3.OperationalError:
                current = None

            if (
                current is not None
                and str(current[0]).lower() == "wal"
            ):
                return

            if attempt == attempts - 1:
                raise

            time.sleep(
                retry_delay_seconds
                * (attempt + 1)
            )


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
    connection = _new_connection()

    try:
        _ensure_wal_mode(connection)
        run_migrations(connection)
    finally:
        connection.close()
