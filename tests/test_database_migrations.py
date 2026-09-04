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
    (6, "create_evidence_events"),
    (7, "add_concept_catalog"),
    (8, "create_mastery_assessments"),
    (9, "create_assistance_events"),
    (10, "create_learning_attempts_and_rubric_assessments"),
    (11, "create_learning_tasks"),
    (12, "create_learning_session_lifecycle"),
    (13, "create_access_control"),
    (14, "enable_privacy_lifecycle"),
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
        "evidence_events",
        "concept_definitions",
        "concept_aliases",
        "mastery_assessments",
        "assistance_events",
        "learning_attempts",
        "rubric_assessments",
        "learning_tasks",
        "learning_session_states",
        "learning_session_events",
        "access_credentials",
        "api_rate_limits",
        "privacy_deletion_authorizations",
    }.issubset(tables)

    assert "concept_id" in turn_columns
    assert "concept" not in turn_columns
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
                concept_id
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
    assert turn["concept_id"] is None


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


def test_v5_database_receives_empty_evidence_ledger(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="v5-to-v6.db",
    )
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:5],
    )
    database_module.init_database()

    connection = connect(path)
    connection.execute(
        """
        INSERT INTO learning_turns (
            student_id,
            session_id,
            turn_id,
            area,
            user_message,
            assistant_message,
            concept
        )
        VALUES (
            'student_default',
            'session_default_ads',
            'turn-before-ledger',
            'ads',
            'Pergunta',
            'Resposta',
            'variáveis'
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
        total = connection.execute(
            "SELECT COUNT(*) FROM evidence_events"
        ).fetchone()[0]
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        turns = connection.execute(
            "SELECT COUNT(*) FROM learning_turns"
        ).fetchone()[0]

        assert total == 0
        assert turns == 1
        assert [row["version"] for row in versions] == list(range(1, 15))
        assert connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []
        assert connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"
    finally:
        connection.close()


def test_evidence_migration_rolls_back_schema_and_version_together(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="evidence-rollback.db",
    )
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:5],
    )
    database_module.init_database()

    def failing_evidence_migration(connection):
        migrations_module.create_evidence_events(connection)
        raise RuntimeError("falha depois do ledger")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:5]
        + (
            Migration(
                6,
                "create_evidence_events",
                failing_evidence_migration,
            ),
        ),
    )

    with pytest.raises(
        MigrationError,
        match="Falha ao aplicar migração 6",
    ):
        database_module.init_database()

    connection = connect(path)
    try:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'evidence_events'
            """
        ).fetchone()
        trigger = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'trigger'
              AND name = 'evidence_events_no_update'
            """
        ).fetchone()
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()

        assert table is None
        assert trigger is None
        assert [row["version"] for row in versions] == [1, 2, 3, 4, 5]
    finally:
        connection.close()



def test_v6_concepts_are_backfilled_to_stable_ids(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="v6-to-v7.db")
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(migrations_module, "MIGRATIONS", current_migrations[:6])
    database_module.init_database()

    connection = connect(path)
    connection.execute(
        """
        INSERT INTO learner_state (
            student_id, area, current_concept, stage, mastery
        ) VALUES ('student_default', 'ads', 'Variáveis', 'testar', 0.6)
        """
    )
    connection.execute(
        """
        INSERT INTO concept_progress (
            student_id, area, concept, mastery
        ) VALUES ('student_default', 'ads', 'variaveis', 0.6)
        """
    )
    connection.execute(
        """
        INSERT INTO learning_turns (
            student_id, session_id, turn_id, area,
            user_message, assistant_message, concept
        ) VALUES (
            'student_default', 'session_default_ads', 'turn-v6', 'ads',
            'Pergunta', 'Resposta', 'variables'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO evidence_events (
            event_id, student_id, session_id, turn_id, area, concept,
            stage_before, stage_after, outcome, confidence,
            tutor_message, student_answer, assistance_level,
            rubric_id, rubric_version, policy_id, policy_version,
            source, applied, mastery_before, mastery_after
        ) VALUES (
            'event-v6', 'student_default', 'session_default_ads', 'turn-v6',
            'ads', 'variáveis', 'testar', 'fixar', 'demonstrated', 0.9,
            'Tutor', 'Aluno', 'untracked', 'rubric', 1,
            'policy', 1, 'semantic_llm', 1, 0.6, 0.8
        )
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(migrations_module, "MIGRATIONS", current_migrations)
    database_module.init_database()

    connection = connect(path)
    try:
        assert connection.execute(
            "SELECT current_concept_id FROM learner_state"
        ).fetchone()[0] == "ads.variables"
        assert connection.execute(
            "SELECT concept_id FROM concept_progress"
        ).fetchone()[0] == "ads.variables"
        assert connection.execute(
            "SELECT concept_id FROM learning_turns WHERE turn_id='turn-v6'"
        ).fetchone()[0] == "ads.variables"
        assert connection.execute(
            "SELECT concept_id FROM evidence_events WHERE event_id='event-v6'"
        ).fetchone()[0] == "ads.variables"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_unknown_legacy_concept_is_preserved_but_not_selectable(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="legacy-concept-v7.db")
    current_migrations = migrations_module.MIGRATIONS
    monkeypatch.setattr(migrations_module, "MIGRATIONS", current_migrations[:6])
    database_module.init_database()

    connection = connect(path)
    connection.execute(
        """
        INSERT INTO concept_progress (
            student_id, area, concept, mastery
        ) VALUES ('student_default', 'ads', 'conceito estranho legado', 0.4)
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(migrations_module, "MIGRATIONS", current_migrations)
    database_module.init_database()

    connection = connect(path)
    try:
        row = connection.execute(
            """
            SELECT d.concept_id, d.canonical_name, d.selectable, d.source
            FROM concept_progress p
            JOIN concept_definitions d
              ON d.area = p.area AND d.concept_id = p.concept_id
            """
        ).fetchone()
        assert row["concept_id"].startswith("legacy.ads.")
        assert row["canonical_name"].startswith("Conceito legado ")
        assert row["selectable"] == 0
        assert row["source"] == "legacy_migration"
    finally:
        connection.close()


def test_concept_catalog_migration_rolls_back_atomically(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="concept-v7-rollback.db")
    current_migrations = migrations_module.MIGRATIONS
    monkeypatch.setattr(migrations_module, "MIGRATIONS", current_migrations[:6])
    database_module.init_database()

    def failing(connection):
        migrations_module.add_concept_catalog(connection)
        raise RuntimeError("falha depois do catálogo")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:6] + (Migration(7, "add_concept_catalog", failing),),
    )

    with pytest.raises(MigrationError, match="Falha ao aplicar migração 7"):
        database_module.init_database()

    connection = connect(path)
    try:
        tables = {
            row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        columns = {
            row["name"] for row in connection.execute(
                "PRAGMA table_info(concept_progress)"
            ).fetchall()
        }
        versions = [
            row["version"] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        assert "concept_definitions" not in tables
        assert "concept_aliases" not in tables
        assert "concept" in columns
        assert "concept_id" not in columns
        assert versions == [1, 2, 3, 4, 5, 6]
    finally:
        connection.close()


def test_v7_merges_semantic_duplicate_progress_rows(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="v7-merge-aliases.db")
    current_migrations = migrations_module.MIGRATIONS
    monkeypatch.setattr(migrations_module, "MIGRATIONS", current_migrations[:6])
    database_module.init_database()

    connection = connect(path)
    connection.execute(
        """
        INSERT INTO concept_progress (
            student_id, area, concept, mastery, difficulty_count,
            last_evidence, review_count, next_review_at,
            last_reviewed_at, updated_at
        ) VALUES (
            'student_default', 'ads', 'Variáveis', 0.6, 1,
            'evidência antiga', 2, '2026-09-10T00:00:00+00:00',
            '2026-09-01T00:00:00+00:00', '2026-09-02T00:00:00+00:00'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO concept_progress (
            student_id, area, concept, mastery, difficulty_count,
            last_evidence, review_count, next_review_at,
            last_reviewed_at, updated_at
        ) VALUES (
            'student_default', 'ads', 'variaveis', 0.85, 3,
            'evidência mais recente', 4, '2026-09-08T00:00:00+00:00',
            '2026-09-03T00:00:00+00:00', '2026-09-04T00:00:00+00:00'
        )
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(migrations_module, "MIGRATIONS", current_migrations)
    database_module.init_database()

    connection = connect(path)
    try:
        rows = connection.execute(
            """
            SELECT concept_id, mastery, difficulty_count, last_evidence,
                   review_count, next_review_at, last_reviewed_at, updated_at
            FROM concept_progress
            WHERE student_id = 'student_default' AND area = 'ads'
            """
        ).fetchall()

        assert len(rows) == 1
        row = rows[0]
        assert row["concept_id"] == "ads.variables"
        assert row["mastery"] == 0.85
        assert row["difficulty_count"] == 3
        assert row["last_evidence"] == "evidência mais recente"
        assert row["review_count"] == 4
        assert row["next_review_at"] == "2026-09-08T00:00:00+00:00"
        assert row["last_reviewed_at"] == "2026-09-03T00:00:00+00:00"
        assert row["updated_at"] == "2026-09-04T00:00:00+00:00"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()



def test_v7_database_receives_empty_mastery_assessment_ledger(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="v7-to-v8.db")
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:7],
    )
    database_module.init_database()

    connection = connect(path)
    try:
        connection.execute(
            """
            INSERT INTO concept_progress (
                student_id, area, concept_id, mastery
            ) VALUES (
                'student_default', 'ads', 'ads.variables', 0.8
            )
            """
        )
        connection.execute(
            """
            INSERT INTO learning_turns (
                student_id, session_id, turn_id, area,
                user_message, assistant_message, concept_id
            ) VALUES (
                'student_default', 'session_default_ads', 'turn-v7-before-v8',
                'ads', 'Pergunta', 'Resposta', 'ads.variables'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO evidence_events (
                event_id, student_id, session_id, turn_id, area, concept_id,
                stage_before, stage_after, outcome, confidence,
                tutor_message, student_answer, assistance_level,
                rubric_id, rubric_version, policy_id, policy_version,
                source, applied, mastery_before, mastery_after
            ) VALUES (
                'event-v7-before-v8', 'student_default', 'session_default_ads',
                'turn-v7-before-v8', 'ads', 'ads.variables',
                'fixar', 'fixar', 'demonstrated', 0.95,
                'Tutor', 'Aluno', 'untracked', 'semantic_evidence', 1,
                'learner_state_transition', 1, 'semantic_llm', 1, 0.6, 0.8
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations,
    )
    database_module.init_database()

    connection = connect(path)
    try:
        total = connection.execute(
            "SELECT COUNT(*) FROM mastery_assessments"
        ).fetchone()[0]
        versions = [
            row["version"] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        preserved_evidence = connection.execute(
            "SELECT COUNT(*) FROM evidence_events WHERE event_id='event-v7-before-v8'"
        ).fetchone()[0]
        assert total == 0
        assert preserved_evidence == 1
        assert versions == list(range(1, 15))
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_mastery_assessment_migration_rolls_back_schema_and_version(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="mastery-v8-rollback.db")
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:7],
    )
    database_module.init_database()

    def failing(connection):
        migrations_module.create_mastery_assessments(connection)
        raise RuntimeError("falha depois do mastery ledger")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:7]
        + (
            Migration(
                8,
                "create_mastery_assessments",
                failing,
            ),
        ),
    )

    with pytest.raises(MigrationError, match="Falha ao aplicar migração 8"):
        database_module.init_database()

    connection = connect(path)
    try:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='mastery_assessments'
            """
        ).fetchone()
        trigger = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='trigger' AND name='mastery_assessments_no_update'
            """
        ).fetchone()
        versions = [
            row["version"] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        assert table is None
        assert trigger is None
        assert versions == [1, 2, 3, 4, 5, 6, 7]
    finally:
        connection.close()



def test_v8_database_receives_empty_assistance_ledger(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="v8-to-v9.db")
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:8],
    )
    database_module.init_database()

    connection = connect(path)
    try:
        connection.execute(
            """
            INSERT INTO learning_turns (
                student_id, session_id, turn_id, area,
                user_message, assistant_message, concept_id
            ) VALUES (
                'student_default', 'session_default_ads', 'turn-v8-before-v9',
                'ads', 'Pergunta', 'Resposta', 'ads.variables'
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations,
    )
    database_module.init_database()

    connection = connect(path)
    try:
        total = connection.execute(
            "SELECT COUNT(*) FROM assistance_events"
        ).fetchone()[0]
        versions = [
            row["version"] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        preserved_turn = connection.execute(
            "SELECT COUNT(*) FROM learning_turns WHERE turn_id='turn-v8-before-v9'"
        ).fetchone()[0]
        assert total == 0
        assert preserved_turn == 1
        assert versions == list(range(1, 15))
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_assistance_migration_rolls_back_schema_and_version(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="assistance-v9-rollback.db")
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:8],
    )
    database_module.init_database()

    def failing(connection):
        migrations_module.create_assistance_events(connection)
        raise RuntimeError("falha depois do assistance ledger")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:8]
        + (
            Migration(
                9,
                "create_assistance_events",
                failing,
            ),
        ),
    )

    with pytest.raises(MigrationError, match="Falha ao aplicar migração 9"):
        database_module.init_database()

    connection = connect(path)
    try:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='assistance_events'
            """
        ).fetchone()
        trigger = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='trigger' AND name='assistance_events_no_update'
            """
        ).fetchone()
        versions = [
            row["version"] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        assert table is None
        assert trigger is None
        assert versions == [1, 2, 3, 4, 5, 6, 7, 8]
    finally:
        connection.close()


def test_v9_database_receives_empty_attempt_and_rubric_ledgers(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="v9-to-v10.db")
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:9],
    )
    database_module.init_database()

    connection = connect(path)
    try:
        connection.execute(
            """
            INSERT INTO learning_turns (
                student_id, session_id, turn_id, area,
                user_message, assistant_message, concept_id
            ) VALUES (
                'student_default', 'session_default_ads', 'turn-v9-before-v10',
                'ads', 'Pergunta', 'Resposta', 'ads.variables'
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations,
    )
    database_module.init_database()

    connection = connect(path)
    try:
        attempts = connection.execute(
            "SELECT COUNT(*) FROM learning_attempts"
        ).fetchone()[0]
        rubrics = connection.execute(
            "SELECT COUNT(*) FROM rubric_assessments"
        ).fetchone()[0]
        preserved_turn = connection.execute(
            "SELECT COUNT(*) FROM learning_turns WHERE turn_id='turn-v9-before-v10'"
        ).fetchone()[0]
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]

        assert attempts == 0
        assert rubrics == 0
        assert preserved_turn == 1
        assert versions == list(range(1, 15))
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_attempt_rubric_migration_rolls_back_schema_and_version(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="attempt-v10-rollback.db")
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:9],
    )
    database_module.init_database()

    def failing(connection):
        migrations_module.create_learning_attempts_and_rubric_assessments(connection)
        raise RuntimeError("falha depois dos ledgers de tentativa/rubrica")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:9]
        + (
            Migration(
                10,
                "create_learning_attempts_and_rubric_assessments",
                failing,
            ),
        ),
    )

    with pytest.raises(MigrationError, match="Falha ao aplicar migração 10"):
        database_module.init_database()

    connection = connect(path)
    try:
        attempt_table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='learning_attempts'
            """
        ).fetchone()
        rubric_table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rubric_assessments'
            """
        ).fetchone()
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]

        assert attempt_table is None
        assert rubric_table is None
        assert versions == list(range(1, 10))
    finally:
        connection.close()


def test_v10_database_receives_empty_task_ledger_without_inventing_links(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="v10-to-v11.db")
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:10],
    )
    database_module.init_database()

    connection = connect(path)
    try:
        connection.execute(
            """
            INSERT INTO learning_turns (
                student_id, session_id, turn_id, area,
                user_message, assistant_message, concept_id
            ) VALUES (
                'student_default', 'session_default_ads', 'turn-v10-before-v11',
                'ads', 'Pergunta', 'Tarefa antiga', 'ads.variables'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO learning_attempts (
                attempt_id, student_id, session_id, turn_id, source_turn_id,
                area, concept_id, stage, attempt_kind, student_answer, artifact_ref,
                assistance_level, policy_id, policy_version
            ) VALUES (
                'attempt-v10-before-v11', 'student_default', 'session_default_ads',
                'turn-v10-before-v11', NULL, 'ads', 'ads.variables', 'testar',
                'practice', 'Pergunta', NULL, 'untracked', 'learning_attempt', 1
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations,
    )
    database_module.init_database()

    connection = connect(path)
    try:
        tasks = connection.execute(
            "SELECT COUNT(*) FROM learning_tasks"
        ).fetchone()[0]
        attempt_task = connection.execute(
            "SELECT task_id FROM learning_attempts WHERE attempt_id='attempt-v10-before-v11'"
        ).fetchone()[0]
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]

        assert tasks == 0
        assert attempt_task is None
        assert versions == list(range(1, 15))
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_learning_task_migration_rolls_back_schema_and_version(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path, name="task-v11-rollback.db")
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:10],
    )
    database_module.init_database()

    def failing(connection):
        migrations_module.create_learning_tasks(connection)
        raise RuntimeError("falha depois do ledger de tarefas")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:10]
        + (
            Migration(11, "create_learning_tasks", failing),
        ),
    )

    with pytest.raises(MigrationError, match="Falha ao aplicar migração 11"):
        database_module.init_database()

    connection = connect(path)
    try:
        task_table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='learning_tasks'
            """
        ).fetchone()
        attempt_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(learning_attempts)"
            ).fetchall()
        }
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]

        assert task_table is None
        assert "task_id" not in attempt_columns
        assert versions == list(range(1, 11))
    finally:
        connection.close()


def test_v11_database_receives_session_runtime_without_inventing_events(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="v11-to-v12.db",
    )
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:11],
    )
    database_module.init_database()

    connection = connect(path)
    try:
        session_count = connection.execute(
            "SELECT COUNT(*) FROM learning_sessions"
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO learning_turns (
                student_id, session_id, turn_id, area,
                user_message, assistant_message, concept_id
            ) VALUES (
                'student_default', 'session_default_ads', 'turn-v11-before-v12',
                'ads', 'Resposta antiga', 'Tarefa antiga', 'ads.variables'
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations,
    )
    database_module.init_database()

    connection = connect(path)
    try:
        states = connection.execute(
            "SELECT COUNT(*) FROM learning_session_states"
        ).fetchone()[0]
        events = connection.execute(
            "SELECT COUNT(*) FROM learning_session_events"
        ).fetchone()[0]
        status = connection.execute(
            """
            SELECT status
            FROM learning_session_states
            WHERE student_id='student_default'
              AND session_id='session_default_ads'
              AND area='ads'
            """
        ).fetchone()[0]
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]

        assert states == session_count
        assert events == 0
        assert status == "studying"
        assert versions == list(range(1, 15))
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_learning_session_lifecycle_migration_rolls_back_schema_and_version(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="session-v12-rollback.db",
    )
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:11],
    )
    database_module.init_database()

    def failing(connection):
        migrations_module.create_learning_session_lifecycle(connection)
        raise RuntimeError("falha depois do lifecycle de sessão")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:11]
        + (
            Migration(
                12,
                "create_learning_session_lifecycle",
                failing,
            ),
        ),
    )

    with pytest.raises(MigrationError, match="Falha ao aplicar migração 12"):
        database_module.init_database()

    connection = connect(path)
    try:
        states = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='learning_session_states'
            """
        ).fetchone()
        events = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='learning_session_events'
            """
        ).fetchone()
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]

        assert states is None
        assert events is None
        assert versions == list(range(1, 12))
    finally:
        connection.close()


def test_session_lifecycle_schema_has_runtime_and_immutable_event_guards(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="session-v12-schema.db",
    )
    database_module.init_database()

    connection = connect(path)
    try:
        state_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(learning_session_states)"
            ).fetchall()
        }
        event_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(learning_session_events)"
            ).fetchall()
        }
        triggers = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='trigger'
                  AND name LIKE 'learning_session_%'
                """
            ).fetchall()
        }
        indexes = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='index'
                  AND name LIKE 'idx_learning_session_%'
                """
            ).fetchall()
        }

        assert {
            "student_id",
            "session_id",
            "area",
            "status",
            "resume_concept_id",
            "resume_stage",
            "review_task_id",
            "paused_at",
            "last_resumed_at",
            "updated_at",
        }.issubset(state_columns)

        assert {
            "event_id",
            "student_id",
            "session_id",
            "area",
            "event_type",
            "status_before",
            "status_after",
            "concept_id",
            "stage_snapshot",
            "policy_id",
            "policy_version",
            "created_at",
        }.issubset(event_columns)

        assert {
            "learning_session_events_no_update",
            "learning_session_events_no_delete",
            "learning_session_states_review_task_scope_insert",
            "learning_session_states_review_task_scope_update",
        }.issubset(triggers)

        assert {
            "idx_learning_session_states_status",
            "idx_learning_session_states_review_task",
            "idx_learning_session_events_session_created",
            "idx_learning_session_events_policy",
        }.issubset(indexes)
    finally:
        connection.close()


def test_access_control_migration_creates_hashed_credentials_and_rate_limit_schema(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="access-v13-schema.db",
    )
    database_module.init_database()

    connection = connect(path)
    try:
        credential_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(access_credentials)"
            ).fetchall()
        }
        rate_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(api_rate_limits)"
            ).fetchall()
        }
        applied = connection.execute(
            "SELECT version, name FROM schema_migrations WHERE version = 13"
        ).fetchone()

        assert applied["version"] == 13
        assert applied["name"] == "create_access_control"
        assert {
            "credential_id",
            "student_id",
            "label",
            "key_hash",
            "is_active",
            "revoked_at",
        }.issubset(credential_columns)
        assert {
            "subject_id",
            "window_started_at",
            "request_count",
        }.issubset(rate_columns)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_access_control_migration_rolls_back_schema_and_version(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="access-v13-rollback.db",
    )
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:12],
    )
    database_module.init_database()

    def failing(connection):
        migrations_module.create_access_control(connection)
        raise RuntimeError("falha depois do access control")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:12] + (
            Migration(13, "create_access_control", failing),
        ),
    )

    with pytest.raises(MigrationError, match="Falha ao aplicar migração 13"):
        database_module.init_database()

    connection = connect(path)
    try:
        credentials = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='access_credentials'"
        ).fetchone()
        limits = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='api_rate_limits'"
        ).fetchone()
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        assert credentials is None
        assert limits is None
        assert versions == list(range(1, 13))
    finally:
        connection.close()



def test_privacy_lifecycle_migration_authorizes_only_explicit_student_deletion(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="privacy-v14-schema.db",
    )
    database_module.init_database()

    connection = connect(path)
    try:
        latest = connection.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchone()
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='evidence_events_no_delete'"
        ).fetchone()["sql"]

        assert latest["version"] == 14
        assert latest["name"] == "enable_privacy_lifecycle"
        assert "privacy_deletion_authorizations" in tables
        assert "privacy_deletion_authorizations" in trigger_sql
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_privacy_lifecycle_migration_rolls_back_trigger_changes(
    monkeypatch,
    tmp_path,
):
    path = configure_database(
        monkeypatch,
        tmp_path,
        name="privacy-v14-rollback.db",
    )
    current_migrations = migrations_module.MIGRATIONS

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:13],
    )
    database_module.init_database()

    def failing(connection):
        migrations_module.enable_privacy_lifecycle(connection)
        raise RuntimeError("falha depois do privacy lifecycle")

    monkeypatch.setattr(
        migrations_module,
        "MIGRATIONS",
        current_migrations[:13] + (
            Migration(14, "enable_privacy_lifecycle", failing),
        ),
    )

    with pytest.raises(MigrationError, match="Falha ao aplicar migração 14"):
        database_module.init_database()

    connection = connect(path)
    try:
        privacy_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='privacy_deletion_authorizations'"
        ).fetchone()
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='evidence_events_no_delete'"
        ).fetchone()["sql"]
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]

        assert privacy_table is None
        assert "privacy_deletion_authorizations" not in trigger_sql
        assert versions == list(range(1, 14))
    finally:
        connection.close()
