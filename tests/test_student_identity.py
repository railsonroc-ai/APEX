import sqlite3

import pytest

import backend.database as database_module
from backend.identity import (
    DEFAULT_STUDENT_ID,
    default_session_id,
)
from backend.services.concept_progress import ConceptProgress
from backend.services.learner_state import LearnerState
from backend.services.learning_history import LearningHistory
from backend.services.learning_turn_lease import LearningTurnLease
from backend.services.process_learning_turn import ProcessLearningTurn
from backend.services.review_queue import ReviewQueue
from backend.services.student_context import StudentContext


SECOND_STUDENT_ID = "student_second"
SECOND_SESSION_ADS = "session_second_ads"


def prepare_database(monkeypatch, tmp_path):
    path = tmp_path / "student-identity.db"

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

    database_module.init_database()

    connection = database_module.get_db_connection()
    try:
        connection.execute(
            "INSERT INTO students (id) VALUES (?)",
            (SECOND_STUDENT_ID,),
        )
        connection.execute(
            """
            INSERT INTO learning_sessions (
                id,
                student_id,
                area
            )
            VALUES (?, ?, 'ads')
            """,
            (
                SECOND_SESSION_ADS,
                SECOND_STUDENT_ID,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return path


def demonstrated_evidence(text):
    return {
        "outcome": "demonstrated",
        "confidence": 0.95,
        "evidence": text,
    }


def test_server_context_resolves_only_default_student():
    assert StudentContext.resolve("ads") == {
        "student_id": DEFAULT_STUDENT_ID,
        "session_id": default_session_id("ads"),
        "area": "ads",
    }

    assert StudentContext.resolve("it") == {
        "student_id": DEFAULT_STUDENT_ID,
        "session_id": default_session_id("it"),
        "area": "it",
    }


def test_learner_state_is_isolated_between_students(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    LearnerState.update(
        "ads",
        current_concept="variáveis",
        stage="testar",
        mastery=0.6,
        student_id=DEFAULT_STUDENT_ID,
    )
    LearnerState.update(
        "ads",
        current_concept="funções",
        stage="compreender",
        mastery=0.2,
        student_id=SECOND_STUDENT_ID,
    )

    first = LearnerState.get(
        "ads",
        student_id=DEFAULT_STUDENT_ID,
    )
    second = LearnerState.get(
        "ads",
        student_id=SECOND_STUDENT_ID,
    )

    assert first["current_concept"] == "variáveis"
    assert first["mastery"] == 0.6
    assert second["current_concept"] == "funções"
    assert second["mastery"] == 0.2


def test_concept_progress_and_reviews_are_isolated(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    ConceptProgress.update(
        "ads",
        "variáveis",
        mastery=0.9,
        next_review_at="2026-09-01T12:00:00+00:00",
        student_id=DEFAULT_STUDENT_ID,
    )
    ConceptProgress.update(
        "ads",
        "variáveis",
        mastery=0.3,
        next_review_at="2026-09-20T12:00:00+00:00",
        student_id=SECOND_STUDENT_ID,
    )

    first = ConceptProgress.get(
        "ads",
        "variáveis",
        student_id=DEFAULT_STUDENT_ID,
    )
    second = ConceptProgress.get(
        "ads",
        "variáveis",
        student_id=SECOND_STUDENT_ID,
    )

    assert first["mastery"] == 0.9
    assert second["mastery"] == 0.3

    assert [
        item["concept"]
        for item in ReviewQueue.due(
            "ads",
            student_id=DEFAULT_STUDENT_ID,
        )
    ] == ["variáveis"]

    assert ReviewQueue.due(
        "ads",
        student_id=SECOND_STUDENT_ID,
    ) == []


def test_same_turn_id_is_scoped_to_student(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    LearningHistory.record(
        turn_id="shared-turn",
        area="ads",
        user_message="Mensagem A",
        assistant_message="Resposta A",
        concept="variáveis",
        student_id=DEFAULT_STUDENT_ID,
        session_id=default_session_id("ads"),
    )
    LearningHistory.record(
        turn_id="shared-turn",
        area="ads",
        user_message="Mensagem B",
        assistant_message="Resposta B",
        concept="variáveis",
        student_id=SECOND_STUDENT_ID,
        session_id=SECOND_SESSION_ADS,
    )

    first = LearningHistory.find(
        "shared-turn",
        student_id=DEFAULT_STUDENT_ID,
    )
    second = LearningHistory.find(
        "shared-turn",
        student_id=SECOND_STUDENT_ID,
    )

    assert first["assistant_message"] == "Resposta A"
    assert second["assistant_message"] == "Resposta B"

    assert LearningHistory.get_messages(
        "ads",
        concept="variáveis",
        student_id=DEFAULT_STUDENT_ID,
    )[-1]["content"] == "Resposta A"

    assert LearningHistory.get_messages(
        "ads",
        concept="variáveis",
        student_id=SECOND_STUDENT_ID,
    )[-1]["content"] == "Resposta B"


def test_session_cannot_be_attached_to_another_student(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        LearningHistory.record(
            turn_id="wrong-session",
            area="ads",
            user_message="Mensagem",
            assistant_message="Resposta",
            student_id=SECOND_STUDENT_ID,
            session_id=default_session_id("ads"),
        )


def test_lease_serializes_student_and_area_not_global_area(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    assert LearningTurnLease.acquire(
        "ads",
        "owner-default",
        student_id=DEFAULT_STUDENT_ID,
    ) is True

    assert LearningTurnLease.acquire(
        "ads",
        "owner-second",
        student_id=SECOND_STUDENT_ID,
    ) is True

    assert LearningTurnLease.acquire(
        "ads",
        "owner-default-2",
        student_id=DEFAULT_STUDENT_ID,
    ) is False


def test_process_turn_keeps_students_independent(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence=demonstrated_evidence(
            "Resposta correta do aluno padrão."
        ),
        turn_id="turn-001",
        assistant_message="Continue.",
        student_id=DEFAULT_STUDENT_ID,
        session_id=default_session_id("ads"),
    )

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma função agrupa comportamento.",
        identified_concept="funções",
        semantic_evidence=demonstrated_evidence(
            "Resposta correta do segundo aluno."
        ),
        turn_id="turn-001",
        assistant_message="Continue também.",
        student_id=SECOND_STUDENT_ID,
        session_id=SECOND_SESSION_ADS,
    )

    first = LearnerState.get(
        "ads",
        student_id=DEFAULT_STUDENT_ID,
    )
    second = LearnerState.get(
        "ads",
        student_id=SECOND_STUDENT_ID,
    )

    assert first["current_concept"] == "variáveis"
    assert second["current_concept"] == "funções"
    assert first["last_evidence"] != second["last_evidence"]
