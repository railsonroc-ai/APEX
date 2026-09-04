import sqlite3

import pytest

import backend.database as database_module
import backend.services.process_learning_turn as turn_module
from backend.services.evidence_event import EvidenceEvent
from backend.services.evidence_policy import EvidencePolicy
from backend.services.learner_state import LearnerState
from backend.services.learning_history import LearningHistory
from backend.services.process_learning_turn import ProcessLearningTurn


def prepare_database(monkeypatch, tmp_path, name="evidence.db"):
    path = tmp_path / name
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def context(answer="Uma variável guarda um valor."):
    return {
        "concept": "variáveis",
        "stage": "compreender",
        "tutor_message": "Explique o que é uma variável.",
        "student_answer": answer,
    }


def evidence(confidence=0.95):
    return {
        "outcome": "demonstrated",
        "confidence": confidence,
        "evidence": "Explicou o conceito corretamente.",
    }


def test_confirmed_turn_records_immutable_evidence_event(
    monkeypatch,
    tmp_path,
):
    path = prepare_database(monkeypatch, tmp_path)

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence=evidence(),
        turn_id="evidence-turn-1",
        assistant_message="Agora aplique em um exemplo.",
        evidence_context=context(),
    )

    event = EvidenceEvent.for_turn("evidence-turn-1")

    assert event is not None
    assert event["student_id"] == "student_default"
    assert event["session_id"] == "session_default_ads"
    assert event["concept"] == "variáveis"
    assert event["stage_before"] == "compreender"
    assert event["stage_after"] == "fixar"
    assert event["outcome"] == "demonstrated"
    assert event["confidence"] == 0.95
    assert event["applied"] == 1
    assert event["mastery_before"] == 0.0
    assert event["mastery_after"] == 0.2
    assert event["assistance_level"] == "untracked"
    assert event["rubric_id"] == EvidencePolicy.RUBRIC_ID
    assert event["rubric_version"] == EvidencePolicy.RUBRIC_VERSION
    assert event["policy_id"] == EvidencePolicy.POLICY_ID
    assert event["policy_version"] == EvidencePolicy.POLICY_VERSION

    connection = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE evidence_events SET outcome = 'partial' WHERE event_id = ?",
                (event["event_id"],),
            )

        connection.rollback()

        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "DELETE FROM evidence_events WHERE event_id = ?",
                (event["event_id"],),
            )
    finally:
        connection.close()


def test_low_confidence_assessment_is_audited_but_not_applied(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence=evidence(confidence=0.50),
        turn_id="evidence-low-confidence",
        assistant_message="Vamos verificar isso com outro exemplo.",
        evidence_context=context(),
    )

    event = EvidenceEvent.for_turn("evidence-low-confidence")
    state = LearnerState.get("ads")

    assert event["applied"] == 0
    assert event["mastery_before"] == 0.0
    assert event["mastery_after"] == 0.0
    assert state["mastery"] == 0.0
    assert state["stage"] == "compreender"


def test_retry_does_not_duplicate_evidence_event(
    monkeypatch,
    tmp_path,
):
    path = prepare_database(monkeypatch, tmp_path)

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence=evidence(),
        turn_id="evidence-retry",
        assistant_message="Próxima orientação.",
        evidence_context=context(),
    )

    duplicate = ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence=evidence(),
        turn_id="evidence-retry",
        evidence_context=context(),
    )

    connection = sqlite3.connect(str(path))
    try:
        total = connection.execute(
            "SELECT COUNT(*) FROM evidence_events"
        ).fetchone()[0]
    finally:
        connection.close()

    assert duplicate["duplicate"] is True
    assert total == 1


def test_evidence_is_isolated_between_students(
    monkeypatch,
    tmp_path,
):
    path = prepare_database(monkeypatch, tmp_path)

    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "INSERT INTO students (id) VALUES ('student_b')"
        )
        connection.execute(
            """
            INSERT INTO learning_sessions (id, student_id, area)
            VALUES ('session_b_ads', 'student_b', 'ads')
            """
        )
        connection.commit()
    finally:
        connection.close()

    for student_id, session_id, answer in (
        (
            "student_default",
            "session_default_ads",
            "Uma variável guarda um valor.",
        ),
        (
            "student_b",
            "session_b_ads",
            "É um nome associado a um valor.",
        ),
    ):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message=answer,
            identified_concept="variáveis",
            semantic_evidence=evidence(),
            turn_id="same-turn-id",
            assistant_message="Continue.",
            student_id=student_id,
            session_id=session_id,
            evidence_context=context(answer),
        )

    event_a = EvidenceEvent.for_turn(
        "same-turn-id",
        student_id="student_default",
    )
    event_b = EvidenceEvent.for_turn(
        "same-turn-id",
        student_id="student_b",
    )

    assert event_a["student_answer"] == "Uma variável guarda um valor."
    assert event_b["student_answer"] == "É um nome associado a um valor."
    assert event_a["event_id"] != event_b["event_id"]


def test_evidence_failure_rolls_back_state_and_confirmed_turn(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    def fail_event(*args, **kwargs):
        raise RuntimeError("falha simulada no ledger")

    monkeypatch.setattr(
        turn_module.EvidenceEvent,
        "record",
        fail_event,
    )

    with pytest.raises(RuntimeError, match="ledger"):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message="Uma variável guarda um valor.",
            identified_concept="variáveis",
            semantic_evidence=evidence(),
            turn_id="evidence-rollback",
            assistant_message="Próxima orientação.",
            evidence_context=context(),
        )

    assert LearningHistory.find("evidence-rollback") is None

    state = LearnerState.get("ads")
    assert state["current_concept"] is None
    assert state["mastery"] == 0.0


def test_evidence_context_mismatch_rolls_back_turn(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    wrong_context = context("Outra resposta.")

    with pytest.raises(
        ValueError,
        match="evidence_context não corresponde",
    ):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message="Uma variável guarda um valor.",
            identified_concept="variáveis",
            semantic_evidence=evidence(),
            turn_id="evidence-context-mismatch",
            assistant_message="Próxima orientação.",
            evidence_context=wrong_context,
        )

    assert LearningHistory.find("evidence-context-mismatch") is None
    state = LearnerState.get("ads")
    assert state["current_concept"] is None
    assert state["mastery"] == 0.0
