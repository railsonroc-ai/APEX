import json
import sqlite3

import pytest

import backend.database as database_module
from backend.identity import session_id_for_student
from backend.services.access_control import AccessControl, AccessRateLimiter
from backend.services.data_lifecycle import DataLifecycle
from backend.services.learning_task import LearningTask
from backend.services.process_learning_turn import ProcessLearningTurn


pytestmark = [pytest.mark.e2e, pytest.mark.reliability]


def _fresh_database(monkeypatch, tmp_path):
    path = tmp_path / "e2e-privacy.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def test_export_then_delete_removes_one_student_without_leaving_orphans(
    monkeypatch,
    tmp_path,
):
    path = _fresh_database(monkeypatch, tmp_path)
    student_id = "student_e2e_privacy"
    raw_key = "e2e-private-key-with-high-entropy-123456"

    credential_id = AccessControl.create_credential(
        student_id,
        "e2e-device",
        raw_key,
    )
    session_id = session_id_for_student(student_id, "ads")

    first = ProcessLearningTurn.commit_turn(
        "ads",
        "Quero aprender variáveis",
        "ads.variables",
        None,
        turn_id="privacy-turn-1",
        assistant_message="Explique o que é uma variável.",
        student_id=student_id,
        session_id=session_id,
    )
    assert first["teaching_action"] == "explicar"
    assert LearningTask.find_by_source_turn(
        "privacy-turn-1",
        student_id=student_id,
        session_id=session_id,
    ) is not None

    assert AccessRateLimiter.allow(
        credential_id,
        limit=10,
        window_seconds=60,
        now_epoch=1000,
    ) is True

    exported = DataLifecycle.export_student(student_id)
    encoded = json.dumps(exported, ensure_ascii=False)

    assert exported["student_id"] == student_id
    assert exported["datasets"]["learning_turns"][0]["turn_id"] == "privacy-turn-1"
    assert exported["datasets"]["learning_tasks"][0]["source_turn_id"] == "privacy-turn-1"
    assert raw_key not in encoded
    assert "key_hash" not in encoded

    receipt = DataLifecycle.delete_student(student_id)
    assert receipt["deleted"]["students"] == 1
    assert receipt["deleted"]["access_credentials"] == 1
    assert AccessControl.authenticate(raw_key) is None

    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM students WHERE id = ?",
            (student_id,),
        ).fetchone()[0] == 0

        tables = (
            "learning_sessions",
            "learning_session_states",
            "learner_state",
            "concept_progress",
            "learning_turns",
            "learning_tasks",
            "learning_attempts",
            "rubric_assessments",
            "evidence_events",
            "mastery_assessments",
            "assistance_events",
            "learning_session_events",
            "notes",
            "access_credentials",
        )
        for table in tables:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE student_id = ?",
                (student_id,),
            ).fetchone()[0]
            assert count == 0, table

        assert connection.execute(
            "SELECT COUNT(*) FROM api_rate_limits WHERE subject_id = ?",
            (credential_id,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM privacy_deletion_authorizations WHERE student_id = ?",
            (student_id,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []
        assert connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"
    finally:
        connection.close()
