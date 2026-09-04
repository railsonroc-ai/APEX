from datetime import datetime, timezone
import sqlite3

import pytest

import backend.database as database_module
from backend.services.access_control import AccessControl
from backend.services.data_lifecycle import (
    DataLifecycle,
    DataLifecycleError,
)


def configure_database(monkeypatch, tmp_path):
    path = tmp_path / "privacy.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def test_export_contains_student_data_without_key_hash(monkeypatch, tmp_path):
    configure_database(monkeypatch, tmp_path)

    AccessControl.create_credential(
        "student_export",
        "celular",
        "segredo-export",
    )

    connection = database_module.get_db_connection()
    try:
        connection.execute(
            "INSERT INTO notes (student_id, text, area) VALUES (?, ?, 'ads')",
            ("student_export", "minha nota"),
        )
        connection.commit()
    finally:
        connection.close()

    payload = DataLifecycle.export_student("student_export")

    assert payload["student_id"] == "student_export"
    assert payload["format"] == "apex_student_export"
    assert payload["datasets"]["notes"][0]["text"] == "minha nota"
    credential = payload["datasets"]["access_credentials"][0]
    assert credential["label"] == "celular"
    assert "key_hash" not in credential
    assert "segredo-export" not in DataLifecycle.to_json_bytes(payload).decode("utf-8")


def test_export_is_isolated_by_student(monkeypatch, tmp_path):
    configure_database(monkeypatch, tmp_path)

    AccessControl.create_credential("student_a", "a", "key-a")
    AccessControl.create_credential("student_b", "b", "key-b")

    connection = database_module.get_db_connection()
    try:
        connection.execute(
            "INSERT INTO notes (student_id, text, area) VALUES ('student_a', 'nota-a', 'ads')"
        )
        connection.execute(
            "INSERT INTO notes (student_id, text, area) VALUES ('student_b', 'nota-b', 'ads')"
        )
        connection.commit()
    finally:
        connection.close()

    payload = DataLifecycle.export_student("student_a")
    serialized = DataLifecycle.to_json_bytes(payload).decode("utf-8")

    assert "nota-a" in serialized
    assert "nota-b" not in serialized
    assert "student_b" not in serialized


def test_immutable_ledgers_still_reject_normal_delete(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path)

    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            """
            INSERT INTO learning_session_events (
                event_id, student_id, session_id, area, event_type,
                status_before, status_after, policy_id, policy_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "privacy-event",
                "student_default",
                "session_default_ads",
                "ads",
                "paused",
                "studying",
                "paused",
                "session_lifecycle",
                1,
            ),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "DELETE FROM learning_session_events WHERE event_id='privacy-event'"
            )
    finally:
        connection.close()


def test_delete_student_removes_all_owned_data_and_credentials(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path)

    credential_id = AccessControl.create_credential(
        "student_delete",
        "notebook",
        "delete-key",
    )

    connection = database_module.get_db_connection()
    try:
        session_id = connection.execute(
            "SELECT id FROM learning_sessions WHERE student_id=? AND area='ads'",
            ("student_delete",),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO notes (student_id, text, area) VALUES (?, ?, 'ads')",
            ("student_delete", "apagar"),
        )
        connection.execute(
            """
            INSERT INTO learning_turns (
                student_id, session_id, turn_id, area, user_message, assistant_message
            ) VALUES (?, ?, ?, 'ads', ?, ?)
            """,
            (
                "student_delete",
                session_id,
                "turn-delete",
                "pergunta",
                "resposta",
            ),
        )
        connection.execute(
            """
            INSERT INTO learning_session_events (
                event_id, student_id, session_id, area, event_type,
                status_before, status_after, policy_id, policy_version
            ) VALUES (?, ?, ?, 'ads', 'paused', 'studying', 'paused', ?, 1)
            """,
            (
                "event-delete",
                "student_delete",
                session_id,
                "session_lifecycle",
            ),
        )
        connection.execute(
            """
            INSERT INTO learning_tasks (
                task_id, student_id, session_id, source_turn_id, area, concept_id,
                stage, teaching_action, task_kind, prompt_text, assistance_level,
                rubric_id, rubric_version, policy_id, policy_version
            ) VALUES (?, ?, ?, ?, 'ads', 'ads.variables', 'testar', 'testar',
                      'practice', 'Resolva.', 'independent', 'semantic_evidence', 2,
                      'learning_task_policy', 1)
            """,
            (
                "task-delete",
                "student_delete",
                session_id,
                "turn-delete",
            ),
        )
        connection.execute(
            """
            INSERT INTO learning_attempts (
                attempt_id, student_id, session_id, turn_id, source_turn_id, area,
                concept_id, stage, attempt_kind, student_answer, assistance_level,
                policy_id, policy_version, task_id
            ) VALUES (?, ?, ?, ?, ?, 'ads', 'ads.variables', 'testar', 'practice',
                      '42', 'independent', 'learning_attempt_policy', 2, ?)
            """,
            (
                "attempt-delete",
                "student_delete",
                session_id,
                "turn-delete",
                "turn-delete",
                "task-delete",
            ),
        )
        connection.execute(
            """
            INSERT INTO evidence_events (
                event_id, student_id, session_id, turn_id, area, concept_id,
                stage_before, stage_after, outcome, confidence, evidence_text,
                tutor_message, student_answer, assistance_level, rubric_id,
                rubric_version, policy_id, policy_version, source, applied,
                mastery_before, mastery_after
            ) VALUES (?, ?, ?, ?, 'ads', 'ads.variables', 'testar', 'fixar',
                      'demonstrated', 0.9, 'ok', 'Resolva.', '42', 'independent',
                      'semantic_evidence', 2, 'evidence_policy', 5, 'semantic_llm',
                      1, 0.5, 0.7)
            """,
            (
                "evidence-delete",
                "student_delete",
                session_id,
                "turn-delete",
            ),
        )
        connection.execute(
            """
            INSERT INTO assistance_events (
                assistance_id, student_id, session_id, turn_id, area, concept_id,
                teaching_action, assistance_level, policy_id, policy_version
            ) VALUES (?, ?, ?, ?, 'ads', 'ads.variables', 'testar', 'independent',
                      'server_teaching_assistance', 1)
            """,
            (
                "assistance-delete",
                "student_delete",
                session_id,
                "turn-delete",
            ),
        )
        connection.execute(
            """
            INSERT INTO mastery_assessments (
                assessment_id, student_id, session_id, turn_id, evidence_event_id,
                area, concept_id, score, can_complete, applied_evidence_count,
                demonstrated_count, demonstrated_stage_count,
                retention_demonstrated_count, low_assistance_demonstrated_count,
                latest_outcome, recommended_stage, blockers_json, policy_id,
                policy_version
            ) VALUES (?, ?, ?, ?, ?, 'ads', 'ads.variables', 0.7, 0, 1, 1, 1, 0, 1,
                      'demonstrated', 'testar', '[]', 'evidence_portfolio_mastery', 2)
            """,
            (
                "mastery-delete",
                "student_delete",
                session_id,
                "turn-delete",
                "evidence-delete",
            ),
        )
        connection.execute(
            """
            INSERT INTO rubric_assessments (
                assessment_id, student_id, session_id, turn_id, attempt_id,
                evidence_event_id, area, concept_id, task_response,
                conceptual_correctness, understanding_application,
                criteria_complete, outcome, outcome_source, confidence,
                rubric_id, rubric_version
            ) VALUES (?, ?, ?, ?, ?, ?, 'ads', 'ads.variables', 'met', 'met', 'met',
                      1, 'demonstrated', 'rubric', 0.9, 'semantic_evidence', 2)
            """,
            (
                "rubric-delete",
                "student_delete",
                session_id,
                "turn-delete",
                "attempt-delete",
                "evidence-delete",
            ),
        )
        connection.execute(
            "INSERT INTO api_rate_limits (subject_id, window_started_at, request_count) VALUES (?, 1, 1)",
            (credential_id,),
        )
        connection.commit()
    finally:
        connection.close()

    result = DataLifecycle.delete_student("student_delete")
    assert result["receipt_id"].startswith("privacy_")

    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM students WHERE id='student_delete'"
        ).fetchone()[0] == 0
        for table in (
            "learning_sessions",
            "learning_session_states",
            "learning_turns",
            "learning_session_events",
            "learning_tasks",
            "learning_attempts",
            "rubric_assessments",
            "evidence_events",
            "mastery_assessments",
            "assistance_events",
            "notes",
            "access_credentials",
        ):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE student_id='student_delete'"
            ).fetchone()[0]
            assert count == 0, table

        assert connection.execute(
            "SELECT COUNT(*) FROM api_rate_limits WHERE subject_id=?",
            (credential_id,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM privacy_deletion_authorizations"
        ).fetchone()[0] == 0
    finally:
        connection.close()

    assert AccessControl.authenticate("delete-key") is None


def test_delete_is_atomic_when_a_delete_fails(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path)
    AccessControl.create_credential("student_atomic", "a", "atomic-key")

    original = DataLifecycle.DELETE_ORDER
    monkeypatch.setattr(
        DataLifecycle,
        "DELETE_ORDER",
        ("notes", "table_that_does_not_exist"),
    )

    with pytest.raises(sqlite3.OperationalError):
        DataLifecycle.delete_student("student_atomic")

    monkeypatch.setattr(DataLifecycle, "DELETE_ORDER", original)

    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM students WHERE id='student_atomic'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM privacy_deletion_authorizations"
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_retention_is_dry_run_and_only_targets_revoked_non_default_students(
    monkeypatch,
    tmp_path,
):
    path = configure_database(monkeypatch, tmp_path)

    credential_id = AccessControl.create_credential(
        "student_old",
        "old",
        "old-key",
    )
    AccessControl.revoke(credential_id)

    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "UPDATE students SET updated_at='2024-01-01 00:00:00' WHERE id='student_old'"
        )
        connection.execute(
            "UPDATE learning_sessions SET started_at='2024-01-01 00:00:00' WHERE student_id='student_old'"
        )
        connection.execute(
            "UPDATE access_credentials SET created_at='2024-01-01 00:00:00', revoked_at='2024-01-02 00:00:00' WHERE student_id='student_old'"
        )
        connection.commit()
    finally:
        connection.close()

    result = DataLifecycle.apply_retention(
        365,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        dry_run=True,
    )

    assert [item["student_id"] for item in result["candidates"]] == [
        "student_old"
    ]
    assert result["deleted"] == []

    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM students WHERE id='student_old'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM students WHERE id='student_default'"
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_retention_rejects_too_short_window(monkeypatch, tmp_path):
    configure_database(monkeypatch, tmp_path)

    with pytest.raises(DataLifecycleError, match="pelo menos 30"):
        DataLifecycle.retention_candidates(29)


def test_retention_apply_deletes_candidate(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path)

    credential_id = AccessControl.create_credential(
        "student_retention_apply",
        "old",
        "retention-key",
    )
    AccessControl.revoke(credential_id)

    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "UPDATE students SET updated_at='2024-01-01 00:00:00' WHERE id='student_retention_apply'"
        )
        connection.execute(
            "UPDATE learning_sessions SET started_at='2024-01-01 00:00:00' WHERE student_id='student_retention_apply'"
        )
        connection.execute(
            "UPDATE access_credentials SET created_at='2024-01-01 00:00:00', revoked_at='2024-01-02 00:00:00' WHERE student_id='student_retention_apply'"
        )
        connection.commit()
    finally:
        connection.close()

    result = DataLifecycle.apply_retention(
        365,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        dry_run=False,
    )

    assert result["dry_run"] is False
    assert result["deleted"][0]["student_id"] == "student_retention_apply"

    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM students WHERE id='student_retention_apply'"
        ).fetchone()[0] == 0
    finally:
        connection.close()
