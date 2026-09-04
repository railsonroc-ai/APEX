import sqlite3

import pytest

import backend.database as database_module
import backend.services.process_learning_turn as turn_module
from backend.services.concept_progress import ConceptProgress
from backend.services.assistance_event import AssistanceEvent
from backend.services.learner_state import LearnerState
from backend.services.learning_history import LearningHistory
from backend.services.mastery_assessment import MasteryAssessment
from backend.services.mastery_policy import MasteryPolicy
from backend.services.process_learning_turn import ProcessLearningTurn


def prepare_database(monkeypatch, tmp_path, name="mastery.db"):
    path = tmp_path / name
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def evidence(outcome="demonstrated", confidence=0.95):
    return {
        "outcome": outcome,
        "confidence": confidence,
        "evidence": f"resultado {outcome}",
    }


def context(stage, answer):
    return {
        "concept_id": "ads.variables",
        "concept": "variáveis",
        "stage": stage,
        "tutor_message": f"Atividade na etapa {stage}.",
        "student_answer": answer,
    }


def commit_demo(turn_id, stage, answer, *, identified=None):
    action_by_stage = {
        "compreender": "explicar",
        "testar": "testar",
        "fixar": "consolidar",
        "reencontrar": "revisar",
    }
    source_turn_id = f"source-{turn_id}"
    tutor_message = f"Atividade na etapa {stage}."

    LearningHistory.record(
        turn_id=source_turn_id,
        area="ads",
        user_message="Preparar atividade.",
        assistant_message=tutor_message,
        concept="variáveis",
    )
    AssistanceEvent.record(
        turn_id=source_turn_id,
        area="ads",
        concept="variáveis",
        teaching_action=action_by_stage.get(stage, "explicar"),
    )

    evidence_context = context(stage, answer)
    evidence_context["tutor_message"] = tutor_message

    return ProcessLearningTurn.commit_turn(
        area="ads",
        user_message=answer,
        identified_concept=identified,
        semantic_evidence=evidence(),
        turn_id=turn_id,
        assistant_message=f"Resposta do tutor {turn_id}.",
        evidence_context=evidence_context,
    )


def test_confirmed_evidence_records_immutable_mastery_assessment(monkeypatch, tmp_path):
    path = prepare_database(monkeypatch, tmp_path)

    commit_demo(
        "mastery-turn-1",
        "compreender",
        "Uma variável guarda um valor.",
        identified="variáveis",
    )

    assessment = MasteryAssessment.for_turn("mastery-turn-1")

    assert assessment is not None
    assert assessment["concept_id"] == "ads.variables"
    assert assessment["concept"] == "variáveis"
    assert assessment["score"] == 0.2
    assert assessment["can_complete"] == 0
    assert assessment["applied_evidence_count"] == 1
    assert assessment["demonstrated_count"] == 1
    assert assessment["demonstrated_stage_count"] == 1
    assert assessment["policy_id"] == MasteryPolicy.POLICY_ID
    assert assessment["policy_version"] == MasteryPolicy.POLICY_VERSION
    assert MasteryPolicy.BLOCK_SCORE in assessment["blockers"]

    connection = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE mastery_assessments SET can_complete = 1 WHERE assessment_id = ?",
                (assessment["assessment_id"],),
            )
        connection.rollback()

        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "DELETE FROM mastery_assessments WHERE assessment_id = ?",
                (assessment["assessment_id"],),
            )
    finally:
        connection.close()


def test_fresh_concept_needs_portfolio_before_completion(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    commit_demo(
        "portfolio-1",
        "compreender",
        "Variável associa um nome a um valor.",
        identified="variáveis",
    )

    for index in (2, 3):
        commit_demo(
            f"portfolio-{index}",
            "fixar",
            f"Exemplo correto {index} de variável.",
        )
        assert LearnerState.get("ads")["stage"] == "fixar"
        assert ConceptProgress.get("ads", "ads.variables")["next_review_at"] is None

    commit_demo(
        "portfolio-4",
        "fixar",
        "Quarto exemplo correto e consistente.",
    )

    state = LearnerState.get("ads")
    assessment = MasteryAssessment.for_turn("portfolio-4")

    assert state["stage"] == "concluido"
    assert round(state["mastery"], 2) == 0.8
    assert assessment["can_complete"] == 1
    assert assessment["applied_evidence_count"] == 4
    assert assessment["demonstrated_count"] == 4
    assert assessment["demonstrated_stage_count"] == 2
    assert assessment["blockers"] == []
    assert ConceptProgress.get("ads", "ads.variables")["next_review_at"] is not None


def test_retry_does_not_duplicate_mastery_assessment(monkeypatch, tmp_path):
    path = prepare_database(monkeypatch, tmp_path)

    commit_demo(
        "mastery-retry",
        "compreender",
        "Resposta inicial.",
        identified="variáveis",
    )

    duplicate = ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Resposta inicial.",
        identified_concept=None,
        semantic_evidence=evidence(),
        turn_id="mastery-retry",
        evidence_context=context("compreender", "Resposta inicial."),
    )

    connection = sqlite3.connect(str(path))
    try:
        total = connection.execute(
            "SELECT COUNT(*) FROM mastery_assessments"
        ).fetchone()[0]
    finally:
        connection.close()

    assert duplicate["duplicate"] is True
    assert total == 1


def test_mastery_assessment_failure_rolls_back_turn_and_state(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    def fail_assessment(*args, **kwargs):
        raise RuntimeError("falha simulada no mastery ledger")

    monkeypatch.setattr(
        turn_module.MasteryAssessment,
        "record",
        fail_assessment,
    )

    with pytest.raises(RuntimeError, match="mastery ledger"):
        commit_demo(
            "mastery-rollback",
            "compreender",
            "Resposta que seria confirmada.",
            identified="variáveis",
        )

    state = LearnerState.get("ads")
    connection = database_module.get_db_connection()
    try:
        turns = connection.execute(
            "SELECT COUNT(*) FROM learning_turns WHERE turn_id='mastery-rollback'"
        ).fetchone()[0]
        evidence_events = connection.execute(
            "SELECT COUNT(*) FROM evidence_events WHERE turn_id='mastery-rollback'"
        ).fetchone()[0]
    finally:
        connection.close()

    assert state["current_concept_id"] is None
    assert state["mastery"] == 0.0
    assert turns == 0
    assert evidence_events == 0


def test_low_confidence_evidence_gets_audited_mastery_decision(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Resposta incerta.",
        identified_concept="variáveis",
        semantic_evidence=evidence(confidence=0.50),
        turn_id="mastery-low-confidence",
        assistant_message="Vamos obter outra evidência.",
        evidence_context=context("compreender", "Resposta incerta."),
    )

    assessment = MasteryAssessment.for_turn("mastery-low-confidence")

    assert assessment["can_complete"] == 0
    assert assessment["applied_evidence_count"] == 0
    assert MasteryPolicy.BLOCK_CURRENT_NOT_APPLIED in assessment["blockers"]


def test_mastery_assessments_are_isolated_between_students(monkeypatch, tmp_path):
    path = prepare_database(monkeypatch, tmp_path)

    connection = sqlite3.connect(str(path))
    try:
        connection.execute("INSERT INTO students (id) VALUES ('student_b')")
        connection.execute(
            """
            INSERT INTO learning_sessions (id, student_id, area)
            VALUES ('session_b_ads', 'student_b', 'ads')
            """
        )
        connection.commit()
    finally:
        connection.close()

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Resposta do aluno A.",
        identified_concept="variáveis",
        semantic_evidence=evidence(),
        turn_id="shared-mastery-turn",
        assistant_message="Continue A.",
        evidence_context=context("compreender", "Resposta do aluno A."),
    )

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Resposta do aluno B.",
        identified_concept="variáveis",
        semantic_evidence=evidence(),
        turn_id="shared-mastery-turn",
        assistant_message="Continue B.",
        student_id="student_b",
        session_id="session_b_ads",
        evidence_context=context("compreender", "Resposta do aluno B."),
    )

    assessment_a = MasteryAssessment.for_turn(
        "shared-mastery-turn",
        student_id="student_default",
    )
    assessment_b = MasteryAssessment.for_turn(
        "shared-mastery-turn",
        student_id="student_b",
    )

    assert assessment_a["student_id"] == "student_default"
    assert assessment_b["student_id"] == "student_b"
    assert assessment_a["assessment_id"] != assessment_b["assessment_id"]


def test_evidence_context_stage_mismatch_rolls_back_turn(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="etapa ativa"):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message="Resposta com contexto inconsistente.",
            identified_concept="variáveis",
            semantic_evidence=evidence(),
            turn_id="mastery-stage-mismatch",
            assistant_message="Resposta do tutor.",
            evidence_context=context(
                "testar",
                "Resposta com contexto inconsistente.",
            ),
        )

    state = LearnerState.get("ads")
    assert state["current_concept_id"] is None
    assert MasteryAssessment.for_turn("mastery-stage-mismatch") is None


def test_legacy_fixar_without_diversity_is_routed_through_testing(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    from backend.services.concept_activation import ConceptActivation

    ConceptActivation.activate("ads", "variáveis")
    LearnerState.update(
        "ads",
        stage="fixar",
        mastery=0.8,
    )

    commit_demo(
        "legacy-diversity-1",
        "fixar",
        "Primeira demonstração após legado.",
    )

    state = LearnerState.get("ads")
    first_assessment = MasteryAssessment.for_turn("legacy-diversity-1")
    assert state["stage"] == "testar"
    assert first_assessment["recommended_stage"] == "testar"

    commit_demo(
        "legacy-diversity-2",
        "testar",
        "Demonstração em contexto de teste.",
    )
    assert LearnerState.get("ads")["stage"] == "fixar"

    commit_demo(
        "legacy-diversity-3",
        "fixar",
        "Demonstração final de consolidação.",
    )

    state = LearnerState.get("ads")
    final_assessment = MasteryAssessment.for_turn("legacy-diversity-3")
    assert state["stage"] == "concluido"
    assert final_assessment["can_complete"] == 1
    assert final_assessment["demonstrated_stage_count"] == 2
