import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

import backend.database as database_module
import backend.migrations as migrations_module
from backend.migrations import (
    Migration,
    MigrationError,
)


EXPECTED_MIGRATIONS = [
    (1, "create_core_schema"),
    (2, "create_learning_turns"),
    (3, "add_learning_turn_concept"),
    (4, "create_learning_turn_leases"),
]


def configure_database(monkeypatch, tmp_path, name="migrations.db"):
    path = tmp_path / name

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        path,
    )
    monkeypatch.setattr(
        database_module,
        "DATA_DIR",
        tmp_path,
    )

    return path


def connect(path):
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


def test_new_database_applies_ordered_migrations(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
    )

    database_module.init_database()

    connection = connect(path)

    try:
        applied = connection.execute(
            """
            SELECT version, name
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

        tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        turn_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(learning_turns)"
            ).fetchall()
        }

    finally:
        connection.close()

    assert [
        (row["version"], row["name"])
        for row in applied
    ] == EXPECTED_MIGRATIONS

    assert {
        "schema_migrations",
        "notes",
        "learner_state",
        "concept_progress",
        "learning_turns",
        "learning_turn_leases",
    }.issubset(tables)

    assert "concept" in turn_columns


def test_running_migrations_twice_is_idempotent(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
    )

    database_module.init_database()
    database_module.init_database()

    connection = connect(path)

    try:
        applied = connection.execute(
            """
            SELECT version, name
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()
    finally:
        connection.close()

    assert [
        (row["version"], row["name"])
        for row in applied
    ] == EXPECTED_MIGRATIONS


def test_legacy_database_is_upgraded_without_losing_turns(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="legacy-migrations.db",
    )

    connection = connect(path)
    connection.execute(
        """
        CREATE TABLE learning_turns (
            turn_id TEXT PRIMARY KEY,
            area TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO learning_turns (
            turn_id,
            area,
            user_message,
            assistant_message
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "legacy-turn",
            "ads",
            "Pergunta preservada",
            "Resposta preservada",
        ),
    )
    connection.commit()
    connection.close()

    database_module.init_database()

    connection = connect(path)

    try:
        turn = connection.execute(
            """
            SELECT
                turn_id,
                user_message,
                assistant_message,
                concept
            FROM learning_turns
            WHERE turn_id = 'legacy-turn'
            """
        ).fetchone()
    finally:
        connection.close()

    assert turn["turn_id"] == "legacy-turn"
    assert turn["user_message"] == "Pergunta preservada"
    assert turn["assistant_message"] == "Resposta preservada"
    assert turn["concept"] is None


def test_migration_and_version_record_roll_back_together(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
    )

    def failing_migration(connection):
        connection.execute(
            "CREATE TABLE incomplete_change (id INTEGER)"
        )
        raise RuntimeError(
            "falha simulada"
        )

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        (
            Migration(
                1,
                "failing_migration",
                failing_migration,
            ),
        ),
    )

    with pytest.raises(
        MigrationError,
        match="Falha ao aplicar migração 1",
    ):
        database_module.init_database()

    connection = connect(path)

    try:
        changed_table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'incomplete_change'
            """
        ).fetchone()

        applied = connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall()
    finally:
        connection.close()

    assert changed_table is None
    assert applied == []


def test_detects_applied_migration_name_drift(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
    )

    database_module.init_database()

    connection = connect(path)
    connection.execute(
        """
        UPDATE schema_migrations
        SET name = 'nome_incorreto'
        WHERE version = 1
        """
    )
    connection.commit()
    connection.close()

    with pytest.raises(
        MigrationError,
        match="não corresponde",
    ):
        database_module.init_database()


def test_concurrent_initialization_applies_each_migration_once(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="concurrent-migrations.db",
    )
    barrier = Barrier(2)

    def initialize(_):
        barrier.wait()
        database_module.init_database()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(initialize, range(2)))

    connection = connect(path)

    try:
        applied = connection.execute(
            """
            SELECT version, name
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()
    finally:
        connection.close()

    assert [
        (row["version"], row["name"])
        for row in applied
    ] == EXPECTED_MIGRATIONS
