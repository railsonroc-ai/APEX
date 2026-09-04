import sqlite3

import pytest

import backend.database as database_module
from backend.services.learning_attempt import LearningAttempt
from backend.services.learning_history import LearningHistory
from backend.services.learning_task import LearningTask
from backend.services.process_learning_turn import ProcessLearningTurn


def prepare_database(monkeypatch, tmp_path):
    path = tmp_path / "learning-task.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def test_learning_task_is_immutable_and_idempotent_per_source_turn(monkeypatch, tmp_path):
    path = prepare_database(monkeypatch, tmp_path)
    LearningHistory.record(
        turn_id="task-source",
        area="ads",
        user_message="Quero estudar variáveis.",
        assistant_message="Explique com suas palavras o que é uma variável.",
        concept_id="ads.variables",
        session_id="session_default_ads",
    )

    first = LearningTask.record(
        source_turn_id="task-source",
        area="ads",
        concept_id="ads.variables",
        stage="compreender",
        teaching_action="explicar",
        prompt_text="Explique com suas palavras o que é uma variável.",
        session_id="session_default_ads",
    )
    second = LearningTask.record(
        source_turn_id="task-source",
        area="ads",
        concept_id="ads.variables",
        stage="compreender",
        teaching_action="explicar",
        prompt_text="Explique com suas palavras o que é uma variável.",
        session_id="session_default_ads",
    )

    assert first["task_id"] == second["task_id"]
    assert first["task_kind"] == "guided_check"
    assert first["assistance_level"] == "guided"
    assert first["rubric_id"] == "semantic_evidence"
    assert first["rubric_version"] == 2

    connection = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE learning_tasks SET stage='testar' WHERE task_id=?",
                (first["task_id"],),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "DELETE FROM learning_tasks WHERE task_id=?",
                (first["task_id"],),
            )
    finally:
        connection.close()


def test_process_links_confirmed_task_to_next_attempt(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    first = ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Quero estudar variáveis.",
        identified_concept="variáveis",
        semantic_evidence=None,
        turn_id="task-turn-1",
        assistant_message="Explique com suas palavras o que é uma variável.",
    )
    assert first["teaching_action"] == "explicar"

    task = LearningTask.find_by_source_turn(
        "task-turn-1",
        session_id="session_default_ads",
    )
    assert task is not None
    assert task["concept_id"] == "ads.variables"
    assert task["stage"] == "compreender"

    answer = "Uma variável associa um nome a um valor que pode ser usado depois."
    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message=answer,
        identified_concept=None,
        semantic_evidence={
            "criteria": {
                "task_response": "met",
                "conceptual_correctness": "met",
                "understanding_application": "met",
            },
            "outcome": "demonstrated",
            "confidence": 0.95,
            "evidence": "Definição própria e correta.",
        },
        turn_id="task-turn-2",
        assistant_message="Agora dê um exemplo simples de variável.",
        evidence_context={
            "task_id": task["task_id"],
            "source_turn_id": task["source_turn_id"],
            "task_kind": task["task_kind"],
            "concept_id": task["concept_id"],
            "concept": "variáveis",
            "stage": task["stage"],
            "tutor_message": task["prompt_text"],
            "student_answer": answer,
        },
    )

    attempt = LearningAttempt.for_turn("task-turn-2")
    assert attempt is not None
    assert attempt["task_id"] == task["task_id"]
    assert attempt["source_turn_id"] == "task-turn-1"


def test_task_scope_mismatch_is_rejected_for_attempt(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Quero estudar variáveis.",
        identified_concept="variáveis",
        semantic_evidence=None,
        turn_id="scope-source",
        assistant_message="Explique o que é uma variável.",
    )
    task = LearningTask.find_by_source_turn(
        "scope-source",
        session_id="session_default_ads",
    )

    LearningHistory.record(
        turn_id="scope-answer",
        area="ads",
        user_message="Resposta.",
        assistant_message="Continue.",
        concept_id="ads.variables",
        session_id="session_default_ads",
    )

    with pytest.raises(ValueError, match="turno fonte"):
        LearningAttempt.record(
            turn_id="scope-answer",
            source_turn_id=None,
            task_id=task["task_id"],
            area="ads",
            concept_id="ads.variables",
            stage="testar",
            student_answer="Resposta.",
            session_id="session_default_ads",
        )


def test_learning_task_failure_rolls_back_confirmed_turn_and_state(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    def fail_record(**kwargs):
        raise RuntimeError("falha no ledger de tarefa")

    monkeypatch.setattr(LearningTask, "record", fail_record)

    with pytest.raises(RuntimeError, match="ledger de tarefa"):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message="Quero estudar variáveis.",
            identified_concept="variáveis",
            semantic_evidence=None,
            turn_id="task-rollback",
            assistant_message="Explique o que é uma variável.",
        )

    assert LearningHistory.find("task-rollback") is None

    connection = database_module.get_db_connection()
    try:
        state = connection.execute(
            "SELECT current_concept_id FROM learner_state WHERE student_id=? AND area=?",
            ("student_default", "ads"),
        ).fetchone()
        assistance = connection.execute(
            "SELECT COUNT(*) FROM assistance_events WHERE turn_id=?",
            ("task-rollback",),
        ).fetchone()[0]
    finally:
        connection.close()

    assert state is None or state["current_concept_id"] is None
    assert assistance == 0
