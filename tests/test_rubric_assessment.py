import sqlite3

import pytest

import backend.database as database_module
import backend.services.process_learning_turn as turn_module
from backend.services.learning_attempt import LearningAttempt
from backend.services.rubric_assessment import RubricAssessment
from backend.services.process_learning_turn import ProcessLearningTurn


def prepare_database(monkeypatch, tmp_path, name="rubric.db"):
    path = tmp_path / name
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def semantic_evidence():
    return {
        "outcome": "demonstrated",
        "confidence": 0.95,
        "evidence": "Explicou corretamente.",
        "criteria": {
            "task_response": "met",
            "conceptual_correctness": "met",
            "understanding_application": "met",
        },
        "rubric_complete": True,
        "outcome_source": "rubric",
    }


def context(answer="Uma variável guarda um valor."):
    return {
        "concept_id": "ads.variables",
        "concept": "variáveis",
        "stage": "compreender",
        "tutor_message": "Explique o que é uma variável.",
        "student_answer": answer,
    }


def test_confirmed_evidence_records_attempt_and_rubric(monkeypatch, tmp_path):
    path = prepare_database(monkeypatch, tmp_path)

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence=semantic_evidence(),
        turn_id="rubric-turn",
        assistant_message="Agora dê um exemplo.",
        evidence_context=context(),
    )

    attempt = LearningAttempt.for_turn("rubric-turn")
    rubric = RubricAssessment.for_turn("rubric-turn")

    assert attempt is not None
    assert attempt["attempt_kind"] == "comprehension"
    assert rubric is not None
    assert rubric["attempt_id"] == attempt["attempt_id"]
    assert rubric["task_response"] == "met"
    assert rubric["conceptual_correctness"] == "met"
    assert rubric["understanding_application"] == "met"
    assert rubric["criteria_complete"] == 1
    assert rubric["outcome"] == "demonstrated"
    assert rubric["outcome_source"] == "rubric"
    assert rubric["rubric_version"] == 2

    connection = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE rubric_assessments SET outcome='partial' WHERE turn_id='rubric-turn'"
            )
    finally:
        connection.close()


def test_incomplete_internal_evidence_is_audited_as_legacy_not_invented(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence={
            "outcome": "partial",
            "confidence": 0.9,
            "evidence": "Resposta incompleta.",
        },
        turn_id="legacy-rubric-turn",
        assistant_message="Vamos completar.",
        evidence_context=context(),
    )

    rubric = RubricAssessment.for_turn("legacy-rubric-turn")
    assert rubric["criteria_complete"] == 0
    assert rubric["outcome"] == "partial"
    assert rubric["outcome_source"] == "legacy_outcome"
    assert rubric["task_response"] == "unknown"


def test_attempt_or_rubric_failure_rolls_back_confirmed_turn(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    monkeypatch.setattr(
        turn_module.RubricAssessment,
        "record",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("rubric ledger falhou")),
    )

    with pytest.raises(RuntimeError, match="rubric ledger"):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message="Uma variável guarda um valor.",
            identified_concept="variáveis",
            semantic_evidence=semantic_evidence(),
            turn_id="rubric-rollback",
            assistant_message="Continue.",
            evidence_context=context(),
        )

    assert LearningAttempt.for_turn("rubric-rollback") is None
    assert RubricAssessment.for_turn("rubric-rollback") is None
