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
    (5, "add_student_identity"),
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
        "students",
        "learning_sessions",
    }.issubset(tables)

    assert "concept" in turn_columns
    assert "student_id" in turn_columns
    assert "session_id" in turn_columns


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
                student_id,
                session_id,
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

    assert turn["student_id"] == "student_default"
    assert turn["session_id"] == "session_default_ads"
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


def test_v4_database_is_backfilled_to_default_student(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="v4-to-v5.db",
    )
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:4],
    )
    database_module.init_database()

    connection = connect(path)
    connection.execute(
        "INSERT INTO notes (text, area) VALUES ('nota', 'ads')"
    )
    connection.execute(
        """
        INSERT INTO learner_state (
            area,
            current_concept,
            stage,
            mastery
        )
        VALUES ('ads', 'variáveis', 'testar', 0.6)
        """
    )
    connection.execute(
        """
        INSERT INTO concept_progress (
            area,
            concept,
            mastery,
            next_review_at
        )
        VALUES (
            'ads',
            'variáveis',
            0.6,
            '2026-09-05T12:00:00+00:00'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO learning_turns (
            turn_id,
            area,
            user_message,
            assistant_message,
            concept
        )
        VALUES (
            'turn-v4',
            'ads',
            'Pergunta',
            'Resposta',
            'variáveis'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO learning_turn_leases (
            area,
            owner_token,
            acquired_at,
            expires_at
        )
        VALUES (
            'ads',
            'owner-v4',
            '2026-09-04T12:00:00+00:00',
            '2026-09-04T12:01:00+00:00'
        )
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations,
    )
    database_module.init_database()

    connection = connect(path)
    try:
        assert connection.execute(
            "SELECT student_id FROM notes"
        ).fetchone()["student_id"] == "student_default"

        assert connection.execute(
            "SELECT student_id FROM learner_state"
        ).fetchone()["student_id"] == "student_default"

        assert connection.execute(
            "SELECT student_id FROM concept_progress"
        ).fetchone()["student_id"] == "student_default"

        turn = connection.execute(
            """
            SELECT student_id, session_id
            FROM learning_turns
            WHERE turn_id = 'turn-v4'
            """
        ).fetchone()
        assert turn["student_id"] == "student_default"
        assert turn["session_id"] == "session_default_ads"

        assert connection.execute(
            "SELECT student_id FROM learning_turn_leases"
        ).fetchone()["student_id"] == "student_default"

        assert connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []

        assert connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"
    finally:
        connection.close()


def test_identity_migration_rolls_back_schema_and_data_together(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="identity-rollback.db",
    )
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:4],
    )
    database_module.init_database()

    connection = connect(path)
    connection.execute(
        """
        INSERT INTO learner_state (
            area,
            current_concept,
            stage,
            mastery
        )
        VALUES ('ads', 'variáveis', 'testar', 0.6)
        """
    )
    connection.commit()
    connection.close()

    def failing_identity_migration(connection):
        migrations_module.add_student_identity(connection)
        raise RuntimeError("falha depois da reconstrução")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:4]
        + (
            Migration(
                5,
                "add_student_identity",
                failing_identity_migration,
            ),
        ),
    )

    with pytest.raises(
        MigrationError,
        match="Falha ao aplicar migração 5",
    ):
        database_module.init_database()

    connection = connect(path)
    try:
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
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(learner_state)"
            ).fetchall()
        }
        state = connection.execute(
            """
            SELECT current_concept, mastery
            FROM learner_state
            WHERE area = 'ads'
            """
        ).fetchone()
        applied = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

        assert "students" not in tables
        assert "learning_sessions" not in tables
        assert "student_id" not in columns
        assert state["current_concept"] == "variáveis"
        assert state["mastery"] == 0.6
        assert [row["version"] for row in applied] == [
            1,
            2,
            3,
            4,
        ]
    finally:
        connection.close()
