import sqlite3

import pytest

import backend.database as database_module
from backend.services.learning_attempt import LearningAttempt
from backend.services.learning_history import LearningHistory


def prepare_database(monkeypatch, tmp_path):
    path = tmp_path / "attempt.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def record_turn(turn_id, user_message, assistant_message, concept_id="ads.variables"):
    return LearningHistory.record(
        turn_id=turn_id,
        area="ads",
        user_message=user_message,
        assistant_message=assistant_message,
        concept_id=concept_id,
        session_id="session_default_ads",
    )


def test_learning_attempt_is_immutable_and_bound_to_confirmed_turn(monkeypatch, tmp_path):
    path = prepare_database(monkeypatch, tmp_path)
    record_turn("source-turn", "Quero estudar.", "Explique o que é uma variável.")
    record_turn("attempt-turn", "Uma variável guarda um valor.", "Continue praticando.")

    attempt = LearningAttempt.record(
        turn_id="attempt-turn",
        source_turn_id="source-turn",
        area="ads",
        concept_id="ads.variables",
        stage="testar",
        student_answer="Uma variável guarda um valor.",
        session_id="session_default_ads",
        assistance_level="independent",
    )

    assert attempt["attempt_kind"] == "practice"
    assert attempt["source_turn_id"] == "source-turn"
    assert attempt["assistance_level"] == "independent"

    connection = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE learning_attempts SET stage='fixar' WHERE attempt_id=?",
                (attempt["attempt_id"],),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "DELETE FROM learning_attempts WHERE attempt_id=?",
                (attempt["attempt_id"],),
            )
    finally:
        connection.close()


def test_attempt_rejects_answer_or_source_from_another_context(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)
    record_turn("attempt-turn", "Resposta real.", "Continue.")

    with pytest.raises(ValueError, match="resposta não corresponde"):
        LearningAttempt.record(
            turn_id="attempt-turn",
            area="ads",
            concept_id="ads.variables",
            stage="testar",
            student_answer="Resposta adulterada.",
            session_id="session_default_ads",
        )
